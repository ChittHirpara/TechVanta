"""
Pipeline integration tests using mocked OCR + LLM.

All tests use SQLite in-memory (via conftest engine fixture) — no Tesseract
or OpenAI key required.
"""
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.document import Document, DocumentStatus
from app.models.extracted_field import ExtractedField
from app.models.audit_trail import AuditTrail


# ─────────────────────────────────────────────────────────────────────────────
# Mock factories
# ─────────────────────────────────────────────────────────────────────────────

def _mock_ocr(avg_conf: float = 0.88, text: str = "Owner: Ram Kumar. Survey: 78-B"):
    from app.services.ocr import OCRResult, WordConfidence
    provider = MagicMock()
    provider.extract_text = AsyncMock(return_value=OCRResult(
        raw_text=text,
        avg_confidence=avg_conf,
        word_confidences=[WordConfidence(w, avg_conf) for w in text.split()[:5]],
        page_count=1,
        provider="mock",
    ))
    return provider


def _mock_extraction(all_null: bool = False):
    from app.services.extraction import ExtractionResult, FieldExtraction

    conf = "low" if all_null else "high"
    val  = None if all_null else "dummy"
    fields = {
        "owner_name":          FieldExtraction(None if all_null else "Ram Kumar Singh", conf),
        "survey_number":       FieldExtraction(None if all_null else "78-B", conf),
        "khasra_number":       FieldExtraction(None if all_null else "451/2", conf),
        "khata_number":        FieldExtraction(None if all_null else "112", conf),
        "plot_area":           FieldExtraction(None if all_null else "2 Bigha", conf),
        "village":             FieldExtraction(None if all_null else "Rampur", conf),
        "tehsil":              FieldExtraction(None if all_null else "Sanganer", conf),
        "district":            FieldExtraction(None if all_null else "Jaipur", conf),
        "land_classification": FieldExtraction(val, conf),
        "ownership_details":   FieldExtraction(val, conf),
        "mutation_record":     FieldExtraction(val, conf),
        "registration_info":   FieldExtraction(val, conf),
    }
    return ExtractionResult(
        fields=fields,
        raw_llm_response='{"fields":{}}',
        model="mock-gpt",
        attempt_count=1,
    )


async def _seed_doc(session: AsyncSession, path: str) -> int:
    doc = Document(
        filename="test.pdf",
        storage_path=path,
        uploaded_by=None,
        status=DocumentStatus.uploaded,
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc.id


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pipeline_happy_path(engine, db: AsyncSession):
    """Full pipeline → status=verified when all fields extracted cleanly."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF mock")
        tmp = f.name

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    doc_id = await _seed_doc(db, tmp)

    with (
        patch("app.services.pipeline.get_ocr_provider", return_value=_mock_ocr()),
        patch("app.services.pipeline.extract_fields",
              AsyncMock(return_value=_mock_extraction())),
        patch("app.services.pipeline.AsyncSessionLocal", SessionLocal),
    ):
        from app.services.pipeline import process_document
        result = await process_document(doc_id, db=None)

    assert result.success
    assert result.final_status == "verified"
    assert result.fields_saved == 12
    assert result.ocr_avg_confidence == pytest.approx(0.88, abs=0.01)

    # Verify DB state
    doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one()
    assert doc.status == DocumentStatus.verified

    field_count = (await db.execute(
        select(func.count()).where(ExtractedField.document_id == doc_id)
    )).scalar_one()
    assert field_count == 12

    Path(tmp).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_pipeline_needs_review_on_null_extraction(engine, db: AsyncSession):
    """All-null extraction → fields flagged → status=needs_review."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF mock")
        tmp = f.name

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    doc_id = await _seed_doc(db, tmp)

    with (
        patch("app.services.pipeline.get_ocr_provider",
              return_value=_mock_ocr(avg_conf=0.20)),
        patch("app.services.pipeline.extract_fields",
              AsyncMock(return_value=_mock_extraction(all_null=True))),
        patch("app.services.pipeline.AsyncSessionLocal", SessionLocal),
    ):
        from app.services.pipeline import process_document
        result = await process_document(doc_id, db=None)

    assert result.final_status == "needs_review"
    assert result.fields_flagged > 0

    doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one()
    assert doc.status == DocumentStatus.needs_review

    Path(tmp).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_pipeline_recovers_from_missing_file(engine, db: AsyncSession):
    """Missing storage file → graceful failure, no document stuck at processing."""
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    doc_id = await _seed_doc(db, "/nonexistent/path/deed.pdf")

    with patch("app.services.pipeline.AsyncSessionLocal", SessionLocal):
        from app.services.pipeline import process_document
        result = await process_document(doc_id, db=None)

    assert not result.success
    assert result.error is not None
    # Must NOT be stuck at processing
    doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one()
    assert doc.status != DocumentStatus.processing


@pytest.mark.asyncio
async def test_pipeline_recovers_from_ocr_crash(engine, db: AsyncSession):
    """OCR exception → document status=needs_review, not stuck at processing."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF mock"); tmp = f.name

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    doc_id = await _seed_doc(db, tmp)

    broken_provider = MagicMock()
    broken_provider.extract_text = AsyncMock(
        side_effect=RuntimeError("Tesseract binary not found")
    )

    with (
        patch("app.services.pipeline.get_ocr_provider", return_value=broken_provider),
        patch("app.services.pipeline.AsyncSessionLocal", SessionLocal),
    ):
        from app.services.pipeline import process_document
        result = await process_document(doc_id, db=None)

    assert not result.success
    assert "Tesseract" in (result.error or "")

    doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one()
    assert doc.status == DocumentStatus.needs_review

    Path(tmp).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_pipeline_idempotency(engine, db: AsyncSession):
    """Running the pipeline twice must not double ExtractedField rows."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF mock"); tmp = f.name

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    doc_id = await _seed_doc(db, tmp)

    async def _run():
        with (
            patch("app.services.pipeline.get_ocr_provider",
                  return_value=_mock_ocr()),
            patch("app.services.pipeline.extract_fields",
                  AsyncMock(return_value=_mock_extraction())),
            patch("app.services.pipeline.AsyncSessionLocal", SessionLocal),
        ):
            from app.services.pipeline import process_document
            return await process_document(doc_id, db=None)

    await _run()
    await _run()

    count = (await db.execute(
        select(func.count()).where(ExtractedField.document_id == doc_id)
    )).scalar_one()
    assert count == 12, f"Expected 12 rows after 2 runs, got {count}"

    Path(tmp).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_pipeline_writes_audit_trail(engine, db: AsyncSession):
    """Pipeline must write pipeline_started and pipeline_complete to AuditTrail."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF mock"); tmp = f.name

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    doc_id = await _seed_doc(db, tmp)

    with (
        patch("app.services.pipeline.get_ocr_provider", return_value=_mock_ocr()),
        patch("app.services.pipeline.extract_fields",
              AsyncMock(return_value=_mock_extraction())),
        patch("app.services.pipeline.AsyncSessionLocal", SessionLocal),
    ):
        from app.services.pipeline import process_document
        await process_document(doc_id, db=None)

    audit_rows = (await db.execute(
        select(AuditTrail).where(AuditTrail.document_id == doc_id)
    )).scalars().all()

    actions = {r.action for r in audit_rows}
    assert "pipeline_started" in actions
    assert "pipeline_complete" in actions

    Path(tmp).unlink(missing_ok=True)
