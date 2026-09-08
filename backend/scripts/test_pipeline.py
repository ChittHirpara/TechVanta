#!/usr/bin/env python3
"""
Pipeline integration test script.

Tests process_document() end-to-end using a real (SQLite in-memory) database
and a mock OCR + mock LLM so no external services are needed.

Usage
─────
    # Run all tests
    python scripts/test_pipeline.py

    # Run against a real file (needs real Tesseract + LLM key in .env)
    python scripts/test_pipeline.py --real --file path/to/scan.pdf --doc-id 1

    # JSON output
    python scripts/test_pipeline.py --json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── ANSI helpers ──────────────────────────────────────────────────────────────
_TTY = sys.stdout.isatty()


def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _TTY else t


def bold(t: str)   -> str: return _c("1",  t)
def cyan(t: str)   -> str: return _c("96", t)
def green(t: str)  -> str: return _c("92", t)
def yellow(t: str) -> str: return _c("93", t)
def red(t: str)    -> str: return _c("91", t)
def grey(t: str)   -> str: return _c("90", t)

PASS = green("✔ PASS")
FAIL = red("✘ FAIL")

# ─────────────────────────────────────────────────────────────────────────────
# Mock helpers
# ─────────────────────────────────────────────────────────────────────────────

_SAMPLE_TEXT = """
District: Jaipur | Tehsil: Sanganer | Village: Rampur Kalan
Owner: Ram Kumar Singh | Khasra No: 451/2 | Survey No: 78-B
Area: 2 Bigha 14 Biswa | Classification: Agricultural
Mutation: Entry 23, 15-Mar-2019 | Reg: Deed 4521/2019
""".strip()


def _make_ocr_result(text: str = _SAMPLE_TEXT, avg_conf: float = 0.88):
    """Build a fake OCRResult."""
    from app.services.ocr import OCRResult, WordConfidence
    words = [WordConfidence(w, avg_conf) for w in text.split()[:10]]
    return OCRResult(
        raw_text=text,
        avg_confidence=avg_conf,
        word_confidences=words,
        page_count=1,
        provider="mock-tesseract",
    )


def _make_extraction_result(owner: str = "Ram Kumar Singh", survey: str = "78-B"):
    """Build a fake ExtractionResult with high confidence on key fields."""
    from app.services.extraction import ExtractionResult, FieldExtraction, FIELD_NAMES
    fields = {
        "owner_name":        FieldExtraction(owner, "high"),
        "survey_number":     FieldExtraction(survey, "high"),
        "khasra_number":     FieldExtraction("451/2", "high"),
        "khata_number":      FieldExtraction("112", "medium"),
        "plot_area":         FieldExtraction("2 Bigha 14 Biswa", "high"),
        "village":           FieldExtraction("Rampur Kalan", "high"),
        "tehsil":            FieldExtraction("Sanganer", "high"),
        "district":          FieldExtraction("Jaipur", "high"),
        "land_classification": FieldExtraction("Agricultural", "medium"),
        "ownership_details": FieldExtraction("Single owner", "medium"),
        "mutation_record":   FieldExtraction("Entry 23, 15-Mar-2019", "medium"),
        "registration_info": FieldExtraction("Deed 4521/2019", "medium"),
    }
    return ExtractionResult(
        fields=fields,
        raw_llm_response='{"fields": {}, "extraction_confidence": {}}',
        model="mock-gpt",
        attempt_count=1,
    )


def _make_bad_extraction_result():
    """Extraction with all nulls → should force needs_review."""
    from app.services.extraction import ExtractionResult, FieldExtraction
    fields = {
        "owner_name":        FieldExtraction(None, "low"),
        "survey_number":     FieldExtraction(None, "low"),
        "khasra_number":     FieldExtraction(None, "low"),
        "khata_number":      FieldExtraction(None, "low"),
        "plot_area":         FieldExtraction(None, "low"),
        "village":           FieldExtraction(None, "low"),
        "tehsil":            FieldExtraction(None, "low"),
        "district":          FieldExtraction(None, "low"),
        "land_classification": FieldExtraction(None, "low"),
        "ownership_details": FieldExtraction(None, "low"),
        "mutation_record":   FieldExtraction(None, "low"),
        "registration_info": FieldExtraction(None, "low"),
    }
    return ExtractionResult(
        fields=fields, raw_llm_response="", model="mock-gpt", attempt_count=2,
        parse_error="Mocked parse failure",
    )


# ─────────────────────────────────────────────────────────────────────────────
# In-memory SQLite database setup
# ─────────────────────────────────────────────────────────────────────────────

async def _setup_db():
    """Create SQLite in-memory DB with all tables and return a session."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.db.session import Base
    import app.models  # register all ORM models

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    return Session, engine


async def _seed_document(session, storage_path: str, status: str = "uploaded"):
    """Insert a Document row and return its id."""
    from app.models.document import Document, DocumentStatus
    doc = Document(
        filename="test_deed.pdf",
        storage_path=storage_path,
        uploaded_by=None,
        status=DocumentStatus(status),
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)
    return doc.id


# ─────────────────────────────────────────────────────────────────────────────
# Test cases
# ─────────────────────────────────────────────────────────────────────────────

async def test_happy_path(args: argparse.Namespace) -> dict:
    """All fields extracted with high confidence → status = 'verified'."""
    print(bold("\n  ── Test: Happy path (all fields found, no flags) ──"))

    Session, engine = await _setup_db()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 mock")
        tmp_path = f.name

    mock_ocr_result  = _make_ocr_result()
    mock_ext_result  = _make_extraction_result()

    mock_provider = MagicMock()
    mock_provider.extract_text = AsyncMock(return_value=mock_ocr_result)

    async with Session() as session:
        doc_id = await _seed_document(session, tmp_path)

    with (
        patch("app.services.pipeline.get_ocr_provider", return_value=mock_provider),
        patch("app.services.pipeline.extract_fields", AsyncMock(return_value=mock_ext_result)),
        patch("app.services.pipeline.AsyncSessionLocal", Session),
    ):
        from app.services.pipeline import process_document
        result = await process_document(doc_id, triggered_by_user_id=None, db=None)

    print(f"  final_status      : {cyan(result.final_status)}")
    print(f"  fields_saved      : {result.fields_saved}")
    print(f"  fields_flagged    : {result.fields_flagged}")
    print(f"  ocr_avg_confidence: {result.ocr_avg_confidence:.3f}")
    print(f"  violations        : {result.violations_count}")
    _print_steps(result.steps)

    ok = (
        result.final_status == "verified"
        and result.fields_saved == 12
        and result.error is None
        and result.success
    )
    print(f"  → {PASS if ok else FAIL}")
    Path(tmp_path).unlink(missing_ok=True)
    await engine.dispose()
    return {"test": "happy_path", "passed": ok, "result": result.to_dict()}


async def test_needs_review(args: argparse.Namespace) -> dict:
    """Null extraction → fields flagged → status = 'needs_review'."""
    print(bold("\n  ── Test: Needs review (all fields null/low confidence) ──"))

    Session, engine = await _setup_db()

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(b"\x89PNG")
        tmp_path = f.name

    mock_ocr_result = _make_ocr_result(avg_conf=0.25)
    mock_ext_result = _make_bad_extraction_result()

    mock_provider = MagicMock()
    mock_provider.extract_text = AsyncMock(return_value=mock_ocr_result)

    async with Session() as session:
        doc_id = await _seed_document(session, tmp_path)

    with (
        patch("app.services.pipeline.get_ocr_provider", return_value=mock_provider),
        patch("app.services.pipeline.extract_fields", AsyncMock(return_value=mock_ext_result)),
        patch("app.services.pipeline.AsyncSessionLocal", Session),
    ):
        from importlib import reload
        import app.services.pipeline as pipe_module
        reload(pipe_module)
        result = await pipe_module.process_document(doc_id, db=None)

    print(f"  final_status      : {cyan(result.final_status)}")
    print(f"  fields_flagged    : {result.fields_flagged}/12")
    print(f"  violations        : {result.violations_count}")
    _print_steps(result.steps)

    ok = result.final_status == "needs_review" and result.fields_flagged > 0
    print(f"  → {PASS if ok else FAIL}")
    Path(tmp_path).unlink(missing_ok=True)
    await engine.dispose()
    return {"test": "needs_review", "passed": ok, "result": result.to_dict()}


async def test_missing_file(args: argparse.Namespace) -> dict:
    """Document row exists but file is gone → pipeline fails gracefully."""
    print(bold("\n  ── Test: Missing storage file → graceful failure ──"))

    Session, engine = await _setup_db()

    async with Session() as session:
        doc_id = await _seed_document(session, "/nonexistent/path/deed.pdf")

    with patch("app.services.pipeline.AsyncSessionLocal", Session):
        from importlib import reload
        import app.services.pipeline as pipe_module
        reload(pipe_module)
        result = await pipe_module.process_document(doc_id, db=None)

    print(f"  success           : {result.success}")
    print(f"  error             : {red(result.error or 'none')}")
    print(f"  final_status      : {cyan(result.final_status)}")
    _print_steps(result.steps)

    ok = not result.success and result.error is not None
    print(f"  → {PASS if ok else FAIL}")
    await engine.dispose()
    return {"test": "missing_file", "passed": ok, "result": result.to_dict()}


async def test_ocr_failure(args: argparse.Namespace) -> dict:
    """OCR raises an exception → document status = needs_review, not stuck at processing."""
    print(bold("\n  ── Test: OCR crash → status recovers to needs_review ──"))

    Session, engine = await _setup_db()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF mock")
        tmp_path = f.name

    async with Session() as session:
        doc_id = await _seed_document(session, tmp_path)

    broken_provider = MagicMock()
    broken_provider.extract_text = AsyncMock(
        side_effect=RuntimeError("Tesseract binary not found")
    )

    with (
        patch("app.services.pipeline.get_ocr_provider", return_value=broken_provider),
        patch("app.services.pipeline.AsyncSessionLocal", Session),
    ):
        from importlib import reload
        import app.services.pipeline as pipe_module
        reload(pipe_module)
        result = await pipe_module.process_document(doc_id, db=None)

    print(f"  success           : {result.success}")
    print(f"  final_status      : {cyan(result.final_status)}")
    print(f"  error             : {red(str(result.error))}")
    _print_steps(result.steps)

    ok = (
        not result.success
        and result.final_status == "needs_review"
        and "Tesseract" in (result.error or "")
    )
    print(f"  → {PASS if ok else FAIL}")
    Path(tmp_path).unlink(missing_ok=True)
    await engine.dispose()
    return {"test": "ocr_failure", "passed": ok, "result": result.to_dict()}


async def test_idempotency(args: argparse.Namespace) -> dict:
    """Running pipeline twice should not duplicate ExtractedField rows."""
    print(bold("\n  ── Test: Idempotency (reprocess same document twice) ──"))

    Session, engine = await _setup_db()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF mock")
        tmp_path = f.name

    mock_provider = MagicMock()
    mock_provider.extract_text = AsyncMock(return_value=_make_ocr_result())
    mock_ext = _make_extraction_result()

    async with Session() as session:
        doc_id = await _seed_document(session, tmp_path)

    run_kwargs = dict(
        ocr_provider=mock_provider, ext=mock_ext, Session=Session
    )

    async def _run():
        with (
            patch("app.services.pipeline.get_ocr_provider", return_value=mock_provider),
            patch("app.services.pipeline.extract_fields", AsyncMock(return_value=mock_ext)),
            patch("app.services.pipeline.AsyncSessionLocal", Session),
        ):
            from importlib import reload
            import app.services.pipeline as pipe_module
            reload(pipe_module)
            return await pipe_module.process_document(doc_id, db=None)

    r1 = await _run()
    r2 = await _run()

    # Count ExtractedField rows
    from app.models.extracted_field import ExtractedField
    from sqlalchemy import select, func
    async with Session() as session:
        count = (
            await session.execute(
                select(func.count()).where(ExtractedField.document_id == doc_id)
            )
        ).scalar()

    print(f"  Run 1 fields_saved: {r1.fields_saved}")
    print(f"  Run 2 fields_saved: {r2.fields_saved}")
    print(f"  Rows in DB        : {count}")

    ok = count == 12  # exactly 12, not 24
    print(f"  → {PASS if ok else FAIL}  (expected 12 rows, got {count})")
    Path(tmp_path).unlink(missing_ok=True)
    await engine.dispose()
    return {"test": "idempotency", "passed": ok, "row_count": count}


# ── Pretty step table ─────────────────────────────────────────────────────────

def _print_steps(steps) -> None:
    if not steps:
        return
    print()
    print(f"  {'Step':<22} {'OK':>4}  {'Time':>7}  Detail")
    print("  " + "─" * 58)
    for s in steps:
        tick = green("✔") if s.success else red("✘")
        detail = (s.error or s.detail)[:35]
        print(f"  {s.name:<22} {tick:>4}  {s.duration_s:>5.2f}s  {grey(detail)}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Entry-point
# ─────────────────────────────────────────────────────────────────────────────

async def main(args: argparse.Namespace) -> int:
    # Ensure aiosqlite is available (only needed for test script)
    try:
        import aiosqlite  # noqa: F401
    except ImportError:
        print(f"{red('Error:')} aiosqlite not installed.")
        print("Run: pip install aiosqlite")
        return 1

    tests = [
        test_happy_path,
        test_needs_review,
        test_missing_file,
        test_ocr_failure,
        test_idempotency,
    ]

    print()
    print(bold("═" * 64))
    print(bold("  Pipeline Integration Tests"))
    print(bold("═" * 64))

    results = []
    for t in tests:
        try:
            r = await t(args)
            results.append(r)
        except Exception as exc:
            print(f"  {red('ERROR')} in {t.__name__}: {exc}")
            import traceback
            traceback.print_exc()
            results.append({"test": t.__name__, "passed": False, "error": str(exc)})

    if args.json:
        print(json.dumps(results, indent=2, default=str))
        return 0

    # Summary
    passed = sum(1 for r in results if r.get("passed"))
    total  = len(results)
    print(bold("═" * 64))
    print(bold(f"  Results: {passed}/{total} passed"))
    for r in results:
        status = PASS if r.get("passed") else FAIL
        print(f"    {status}  {r['test']}")
    print(bold("═" * 64))
    print()
    return 0 if passed == total else 2


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Integration tests for the document processing pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--json", action="store_true", help="Output JSON results.")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(_parse_args())))
