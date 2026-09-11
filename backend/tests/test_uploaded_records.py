"""
Tests for the uploaded-records persistence layer + pipeline integration.

Covers the three required scenarios:
  1. Matching PDF        → verification unchanged, record saved      (LOW risk)
  2. Mismatching PDF     → mismatch/risk unchanged, record saved      (HIGH risk)
  3. Unknown PDF         → REFERENCE_NOT_FOUND / UNVERIFIED (non-zero risk,
     					   not applicable) and record still saved separately

Also verifies that saving never touches the trusted reference file.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import uploaded_records


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for the persistence service itself
# ─────────────────────────────────────────────────────────────────────────────

def test_file_created_on_first_save(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "uploaded_land_records.json"
    monkeypatch.setattr(uploaded_records, "_UPLOADED_FILE", target)
    assert not target.exists()

    rec = uploaded_records.save_uploaded_record(
        document_id=1,
        source_filename="deed.pdf",
        extracted_data={"owner_name": "Ram Kumar Singh", "survey_number": "78-B"},
    )

    assert target.exists()
    assert rec is not None
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["records"]) == 1
    saved = payload["records"][0]
    assert saved["documentId"] == 1
    assert saved["sourceFileName"] == "deed.pdf"
    assert saved["id"].startswith("UPLOAD-")
    assert "uploadedAt" in saved
    assert saved["extractedData"] == {
        "owner_name": "Ram Kumar Singh",
        "survey_number": "78-B",
    }


def test_append_preserves_existing_records(tmp_path, monkeypatch):
    target = tmp_path / "uploaded_land_records.json"
    monkeypatch.setattr(uploaded_records, "_UPLOADED_FILE", target)

    uploaded_records.save_uploaded_record(1, "a.pdf", {"owner_name": "A"})
    uploaded_records.save_uploaded_record(2, "b.pdf", {"owner_name": "B"})

    payload = json.loads(target.read_text(encoding="utf-8"))
    ids = [r["documentId"] for r in payload["records"]]
    assert ids == [1, 2]


def test_deduplication_skips_same_document(tmp_path, monkeypatch):
    target = tmp_path / "uploaded_land_records.json"
    monkeypatch.setattr(uploaded_records, "_UPLOADED_FILE", target)

    first = uploaded_records.save_uploaded_record(7, "deed.pdf", {"owner_name": "A"})
    second = uploaded_records.save_uploaded_record(7, "deed.pdf", {"owner_name": "B"})

    assert first is not None
    assert second is None  # duplicate → skipped

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert len(payload["records"]) == 1


def test_corrupted_json_handled_safely(tmp_path, monkeypatch):
    target = tmp_path / "uploaded_land_records.json"
    monkeypatch.setattr(uploaded_records, "_UPLOADED_FILE", target)
    target.write_text("{ this is not valid json", encoding="utf-8")

    # Must not raise — falls back to empty then writes clean file
    rec = uploaded_records.save_uploaded_record(3, "c.pdf", {"owner_name": "C"})
    assert rec is not None
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert [r["documentId"] for r in payload["records"]] == [3]


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline integration: matching / mismatching / unknown docs
# ─────────────────────────────────────────────────────────────────────────────

def _mock_ocr(text: str = "Owner: Meera Deshmukh"):
    from app.services.ocr import OCRResult, WordConfidence
    provider = MagicMock()
    provider.extract_text = AsyncMock(return_value=OCRResult(
        raw_text=text,
        avg_confidence=0.92,
        word_confidences=[WordConfidence(w, 0.92) for w in text.split()[:5]],
        page_count=1,
        provider="mock",
    ))
    return provider


def _extraction(fields: dict) -> "object":
    from app.services.extraction import ExtractionResult, FieldExtraction
    fmap = {
        k: FieldExtraction(v if v is not None else None, "low" if v is None else "high")
        for k, v in fields.items()
    }
    return ExtractionResult(fields=fmap, raw_llm_response="{}", model="mock", attempt_count=1)


async def _run_pipeline(db, engine, storage_path: str, extraction_result):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.models.document import Document, DocumentStatus

    doc = Document(
        filename="scenario.pdf",
        storage_path=storage_path,
        uploaded_by=None,
        status=DocumentStatus.uploaded,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    with (
        patch("app.services.pipeline.get_ocr_provider", return_value=_mock_ocr()),
        patch("app.services.pipeline.extract_fields",
              AsyncMock(return_value=extraction_result)),
        patch("app.services.pipeline.AsyncSessionLocal", SessionLocal),
    ):
        from app.services.pipeline import process_document
        return doc.id, await process_document(doc.id, db=None)


@pytest.mark.asyncio
async def test_matching_pdf_saved_and_verified(engine, db, tmp_path):
    """Scenario 1: matching extraction → verified, and record appended."""
    uploaded_file = tmp_path / "uploaded_land_records.json"

    pdf = tmp_path / "matching.pdf"
    pdf.write_bytes(b"%PDF mock")

    extraction = _extraction({
        "owner_name": "Meera Deshmukh",
        "co_owner": "Arjun Deshmukh",
        "survey_number": "126-A",
        "khasra_number": "126/3",
        "khata_number": "307",
        "plot_area": "3.25 Acres",
        "village": "Karanjwan",
        "tehsil": "Dindori",
        "district": "Nashik",
        "land_classification": "Agricultural - Dry Crop",
        "ownership_details": "Joint ownership - 2 co-owners",
        "mutation_record": "Entry 41, 22-Nov-2021",
        "registration_info": "Deed 7814/2021",
    })

    doc_id, result = await _run_pipeline(db, engine, str(pdf), extraction)

    assert result.final_status == "verified"
    assert result.risk_level == "LOW"

    records = json.loads(uploaded_file.read_text(encoding="utf-8"))["records"]
    assert any(r["documentId"] == doc_id for r in records)


@pytest.mark.asyncio
async def test_mismatching_pdf_saved_and_flagged(engine, db, tmp_path):
    """Scenario 2: tampered extraction → HIGH risk, and record appended."""
    uploaded_file = tmp_path / "uploaded_land_records.json"

    pdf = tmp_path / "mismatching.pdf"
    pdf.write_bytes(b"%PDF mock")

    extraction = _extraction({
        "owner_name": "Meera Deshmukh",
        "co_owner": "Arjun Deshmukh",
        "survey_number": "126-A",
        "khasra_number": "126/8",          # tampered
        "khata_number": "307",
        "plot_area": "4.25 Acres",         # tampered
        "village": "Karanjwan",
        "tehsil": "Dindori",
        "district": "Nashik",
        "land_classification": "Agricultural - Dry Crop",
        "ownership_details": "Joint ownership - 2 co-owners",
        "mutation_record": "Entry 41, 22-Nov-2021",
        "registration_info": "Deed 7814/2021",
    })

    doc_id, result = await _run_pipeline(db, engine, str(pdf), extraction)

    assert result.risk_level == "HIGH"
    assert result.risk_mismatches >= 2
    assert result.final_status == "needs_review"

    records = json.loads(uploaded_file.read_text(encoding="utf-8"))["records"]
    assert any(r["documentId"] == doc_id for r in records)


@pytest.mark.asyncio
async def test_unknown_pdf_saved_and_not_applicable(engine, db, tmp_path):
    """Scenario 3: no trusted reference → risk not applicable, record saved."""
    uploaded_file = tmp_path / "uploaded_land_records.json"

    pdf = tmp_path / "unknown.pdf"
    pdf.write_bytes(b"%PDF mock")

    extraction = _extraction({
        "owner_name": "Stranger Tester",
        "survey_number": "999-X",
        "khasra_number": "999/1",
        "khata_number": "999",
        "plot_area": "9.9 Acres",
        "village": "Unknownville",
        "tehsil": "Nowhere",
        "district": "Somewhere",
        "land_classification": "Agricultural",
        "ownership_details": "Single owner",
        "mutation_record": "None",
        "registration_info": "None",
    })

    doc_id, result = await _run_pipeline(db, engine, str(pdf), extraction)

    assert result.risk_applicable is False
    assert result.risk_score > 0

    records = json.loads(uploaded_file.read_text(encoding="utf-8"))["records"]
    assert any(r["documentId"] == doc_id for r in records)


# ─────────────────────────────────────────────────────────────────────────────
# Trusted reference file is NEVER modified by saving uploaded records
# ─────────────────────────────────────────────────────────────────────────────

def test_reference_records_not_modified(tmp_path, monkeypatch):
    from app.services.reference_comparison import _REFERENCE_FILE

    original = _REFERENCE_FILE.read_bytes()
    target = tmp_path / "uploaded_land_records.json"
    monkeypatch.setattr(uploaded_records, "_UPLOADED_FILE", target)

    uploaded_records.save_uploaded_record(42, "deed.pdf", {"owner_name": "X"})

    assert _REFERENCE_FILE.read_bytes() == original