"""
Document processing pipeline.

Entry-point
───────────
    await process_document(document_id, triggered_by_user_id=user_id)

Designed to run as a FastAPI BackgroundTask — it owns its own DB session
so the caller's request session can close normally after the upload response.

Pipeline steps
──────────────
    1. Load Document row and validate storage path exists
    2. Set status → "processing", log to AuditTrail
    3. Run OCR  (TesseractProvider or configured provider)
    4. Run LLM extraction  (extract_fields)
    5. Run validation  (validate_fields + compute_confidence per field)
    6. Persist ExtractedField rows  (delete-then-insert for idempotency)
    7. Determine final status: "needs_review" | "verified"
    8. Update Document.status + Document.updated_at
    9. Log completion (or failure) to AuditTrail

Error handling
──────────────
    Each step is wrapped individually.  If a step fails the document is
    left in "needs_review" (not "processing") so it does not get stuck,
    and the error is recorded in the AuditTrail.

Usage in a route
────────────────
    from fastapi import BackgroundTasks
    from app.services.pipeline import process_document

    @router.post("/documents/upload", ...)
    async def upload(background_tasks: BackgroundTasks, ...):
        doc = await create_document(db, payload)
        background_tasks.add_task(process_document, doc.id,
                                  triggered_by_user_id=current_user.id)
        return DocumentRead.model_validate(doc)
"""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.audit_trail import AuditTrail
from app.models.document import Document, DocumentStatus
from app.models.extracted_field import ExtractedField
from app.services.extraction import extract_fields
from app.services.ocr import get_ocr_provider
from app.services.validation import build_field_reports, validate_fields

log = logging.getLogger(__name__)


class PipelineEventBroadcaster:
    """In-memory event broadcaster for real-time pipeline status updates (SSE)."""

    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue]] = {}
        self._history: dict[int, list[dict[str, Any]]] = {}

    def subscribe(self, document_id: int) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(document_id, set()).add(q)
        for ev in self._history.get(document_id, []):
            q.put_nowait(ev)
        return q

    def unsubscribe(self, document_id: int, q: asyncio.Queue) -> None:
        if document_id in self._subscribers:
            self._subscribers[document_id].discard(q)
            if not self._subscribers[document_id]:
                del self._subscribers[document_id]

    async def broadcast(self, document_id: int, event_data: dict[str, Any]) -> None:
        self._history.setdefault(document_id, []).append(event_data)
        if len(self._history[document_id]) > 25:
            self._history[document_id].pop(0)

        for q in list(self._subscribers.get(document_id, [])):
            try:
                q.put_nowait(event_data)
            except Exception:
                pass


pipeline_broadcaster = PipelineEventBroadcaster()

# ─────────────────────────────────────────────────────────────────────────────
# Result / step tracking types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class StepResult:
    name: str
    success: bool
    duration_s: float
    detail: str = ""
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "step": self.name,
            "success": self.success,
            "duration_s": round(self.duration_s, 3),
            "detail": self.detail,
            **({"error": self.error} if self.error else {}),
        }


@dataclass
class PipelineResult:
    """
    Returned from process_document for observability / testing.
    The BackgroundTask runner ignores the return value, but tests can await it.
    """
    document_id: int
    final_status: str
    ocr_avg_confidence: float
    fields_saved: int
    fields_flagged: int
    violations_count: int
    total_duration_s: float
    steps: list[StepResult] = field(default_factory=list)
    error: str | None = None         # set if an unrecoverable error occurred

    @property
    def success(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "final_status": self.final_status,
            "ocr_avg_confidence": self.ocr_avg_confidence,
            "fields_saved": self.fields_saved,
            "fields_flagged": self.fields_flagged,
            "violations_count": self.violations_count,
            "total_duration_s": round(self.total_duration_s, 3),
            "success": self.success,
            "steps": [s.to_dict() for s in self.steps],
            **({"error": self.error} if self.error else {}),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

from app.services.audit_service import write_audit


async def _log_audit(
    db: AsyncSession,
    *,
    document_id: int | None,
    user_id: int | None,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Append a row to audit_trails via centralized audit service."""
    await write_audit(
        db,
        action,
        document_id=document_id,
        user_id=user_id,
        details=details,
        flush=True,
    )


async def _set_document_status(
    db: AsyncSession,
    document_id: int,
    status: str,
) -> None:
    """
    Update Document.status and explicitly bump updated_at via server-side now().

    NOTE: We must set updated_at explicitly here because SQLAlchemy's
    ``onupdate=func.now()`` only fires for ORM-level attribute changes,
    NOT for raw ``session.execute(update(...).values(...))`` statements.
    """
    from sqlalchemy import func, update
    from app.models.document import Document, DocumentStatus

    new_status = DocumentStatus(status)
    stmt = (
        update(Document)
        .where(Document.id == document_id)
        .values(status=new_status, updated_at=func.now())  # explicit bump — do NOT remove
    )
    await db.execute(stmt)
    await db.flush()


@asynccontextmanager
async def _step(name: str, results: list[StepResult]):
    """
    Async context manager that times a pipeline step and records its result.

    Usage::

        async with _step("ocr", step_results) as step:
            ...
            step.detail = "1 page, avg_conf=0.92"
    """
    sr = StepResult(name=name, success=False, duration_s=0.0)
    t0 = time.perf_counter()
    try:
        yield sr
        sr.success = True
    except Exception as exc:
        sr.error = str(exc)
        raise
    finally:
        sr.duration_s = time.perf_counter() - t0
        results.append(sr)
        status = "✔" if sr.success else "✘"
        log.info("[pipeline] step %-20s %s  %.2fs", name, status, sr.duration_s)


# ─────────────────────────────────────────────────────────────────────────────
# Session management
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def _get_session(provided: AsyncSession | None):
    """
    Yield *provided* session if given (for tests), otherwise open a fresh one.

    BackgroundTasks run after the response is sent and the request's session
    is closed — always pass ``db=None`` from a BackgroundTask.
    """
    if provided is not None:
        yield provided
    else:
        async with AsyncSessionLocal() as session:
            yield session


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def process_document(
    document_id: int,
    *,
    triggered_by_user_id: int | None = None,
    db: AsyncSession | None = None,
) -> PipelineResult:
    """
    Full OCR → Extraction → Validation → Persistence pipeline.

    Args:
        document_id:          Primary key of the Document to process.
        triggered_by_user_id: User who initiated the upload (for AuditTrail).
                              Pass None for system-triggered reprocessing.
        db:                   Inject a session for testing. Leave None when
                              called from a BackgroundTask (creates own session).

    Returns:
        PipelineResult  (BackgroundTask ignores return value).
    """
    wall_start = time.perf_counter()
    step_results: list[StepResult] = []

    # Mutable state threaded through steps
    doc              = None
    raw_text: str    = ""
    ocr_avg_conf     = 0.0
    extraction_result = None
    field_reports: list = []
    fields_flagged   = 0
    violations_count = 0
    final_status     = "needs_review"    # safe default if we abort early

    async with _get_session(db) as session:

        # ── Step 1: Load document ─────────────────────────────────────────────
        try:
            async with _step("load_document", step_results) as step:
                from app.models.document import Document

                result = await session.execute(
                    select(Document).where(Document.id == document_id)
                )
                doc = result.scalar_one_or_none()
                if doc is None:
                    raise ValueError(f"Document id={document_id} not found in database.")

                storage_path = Path(doc.storage_path)
                if not storage_path.exists():
                    raise FileNotFoundError(
                        f"Storage file not found: {storage_path}. "
                        "Check that the upload path is mounted correctly."
                    )
                step.detail = f"filename={doc.filename!r} path={storage_path}"
                await pipeline_broadcaster.broadcast(document_id, {
                    "event": "step",
                    "step": "load_document",
                    "percent": 15,
                    "status": "processing",
                    "message": f"Document loaded: {doc.filename}",
                })
        except Exception as exc:
            log.error("[pipeline] load_document failed: %s", exc)
            await pipeline_broadcaster.broadcast(document_id, {
                "event": "error",
                "step": "load_document",
                "percent": 100,
                "status": "needs_review",
                "message": f"Document load error: {exc}",
            })
            return PipelineResult(
                document_id=document_id,
                final_status="needs_review",
                ocr_avg_confidence=0.0,
                fields_saved=0,
                fields_flagged=0,
                violations_count=0,
                total_duration_s=time.perf_counter() - wall_start,
                steps=step_results,
                error=str(exc),
            )

        # ── Step 2: Mark processing + initial audit ───────────────────────────
        async with _step("set_processing", step_results) as step:
            await _set_document_status(session, document_id, "processing")
            await _log_audit(
                session,
                document_id=document_id,
                user_id=triggered_by_user_id,
                action="pipeline_started",
                details={"filename": doc.filename, "triggered_by": triggered_by_user_id},
            )
            await session.commit()
            step.detail = "status=processing"
            await pipeline_broadcaster.broadcast(document_id, {
                "event": "step",
                "step": "set_processing",
                "percent": 25,
                "status": "processing",
                "message": "Initialized pipeline worker session",
            })

        # ── Step 3: OCR ───────────────────────────────────────────────────────
        try:
            async with _step("ocr", step_results) as step:
                await pipeline_broadcaster.broadcast(document_id, {
                    "event": "step",
                    "step": "ocr_started",
                    "percent": 35,
                    "status": "processing",
                    "message": "Running OCR engine on scanned record...",
                })
                provider  = get_ocr_provider()
                ocr_result = await provider.extract_text(storage_path)
                raw_text   = ocr_result.raw_text
                ocr_avg_conf = ocr_result.avg_confidence

                await _log_audit(
                    session,
                    document_id=document_id,
                    user_id=triggered_by_user_id,
                    action="ocr_complete",
                    details={
                        "provider": ocr_result.provider,
                        "page_count": ocr_result.page_count,
                        "avg_confidence": ocr_avg_conf,
                        "text_length": len(raw_text),
                    },
                )
                await session.commit()
                step.detail = (
                    f"provider={ocr_result.provider} pages={ocr_result.page_count} "
                    f"avg_conf={ocr_avg_conf:.3f} chars={len(raw_text)}"
                )
                await pipeline_broadcaster.broadcast(document_id, {
                    "event": "step",
                    "step": "ocr_complete",
                    "percent": 55,
                    "status": "processing",
                    "message": f"OCR complete ({ocr_avg_conf:.1%} avg confidence)",
                    "detail": {"avg_confidence": ocr_avg_conf, "pages": ocr_result.page_count},
                })
        except Exception as exc:
            log.error("[pipeline] OCR step failed: %s", exc)
            await _set_document_status(session, document_id, "needs_review")
            await _log_audit(
                session,
                document_id=document_id,
                user_id=triggered_by_user_id,
                action="pipeline_error",
                details={"step": "ocr", "error": str(exc)},
            )
            await session.commit()
            await pipeline_broadcaster.broadcast(document_id, {
                "event": "error",
                "step": "ocr_failed",
                "percent": 100,
                "status": "needs_review",
                "message": f"OCR extraction failed: {exc}",
            })
            return PipelineResult(
                document_id=document_id,
                final_status="needs_review",
                ocr_avg_confidence=0.0,
                fields_saved=0,
                fields_flagged=0,
                violations_count=0,
                total_duration_s=time.perf_counter() - wall_start,
                steps=step_results,
                error=f"OCR failed: {exc}",
            )

        # ── Step 4: LLM field extraction ──────────────────────────────────────
        try:
            async with _step("extraction", step_results) as step:
                await pipeline_broadcaster.broadcast(document_id, {
                    "event": "step",
                    "step": "extraction_started",
                    "percent": 65,
                    "status": "processing",
                    "message": "AI extracting structured revenue fields...",
                })
                extraction_result = await extract_fields(raw_text)

                await _log_audit(
                    session,
                    document_id=document_id,
                    user_id=triggered_by_user_id,
                    action="extraction_complete",
                    details={
                        "model": extraction_result.model,
                        "attempt_count": extraction_result.attempt_count,
                        "parse_error": extraction_result.parse_error,
                        "fields_non_null": sum(
                            1 for fe in extraction_result.fields.values()
                            if fe.value is not None
                        ),
                    },
                )
                await session.commit()
                step.detail = (
                    f"model={extraction_result.model} "
                    f"attempts={extraction_result.attempt_count} "
                    f"parse_error={'yes' if extraction_result.parse_error else 'no'}"
                )
                await pipeline_broadcaster.broadcast(document_id, {
                    "event": "step",
                    "step": "extraction_complete",
                    "percent": 80,
                    "status": "processing",
                    "message": f"AI extraction completed ({extraction_result.model})",
                })
        except Exception as exc:
            log.error("[pipeline] extraction step failed: %s", exc)
            await _set_document_status(session, document_id, "needs_review")
            await _log_audit(
                session,
                document_id=document_id,
                user_id=triggered_by_user_id,
                action="pipeline_error",
                details={"step": "extraction", "error": str(exc)},
            )
            await session.commit()
            await pipeline_broadcaster.broadcast(document_id, {
                "event": "error",
                "step": "extraction_failed",
                "percent": 100,
                "status": "needs_review",
                "message": f"Extraction failed: {exc}",
            })
            return PipelineResult(
                document_id=document_id,
                final_status="needs_review",
                ocr_avg_confidence=ocr_avg_conf,
                fields_saved=0,
                fields_flagged=0,
                violations_count=0,
                total_duration_s=time.perf_counter() - wall_start,
                steps=step_results,
                error=f"Extraction failed: {exc}",
            )

        # ── Step 5: Validation + confidence scoring ───────────────────────────
        async with _step("validation", step_results) as step:
            extracted_values = extraction_result.flat_values()
            violations       = validate_fields(extracted_values)
            violations_count = len(violations)

            # Use document-level OCR confidence for all fields
            # (per-field mapping would require bounding-box alignment — future work)
            ocr_conf_per_field = {k: ocr_avg_conf for k in extracted_values}
            ext_conf_per_field = {
                k: fe.confidence
                for k, fe in extraction_result.fields.items()
            }

            field_reports = build_field_reports(
                extracted_values,
                ocr_conf_per_field,
                ext_conf_per_field,
                violations,
            )
            fields_flagged = sum(1 for r in field_reports if r.is_flagged)

            await _log_audit(
                session,
                document_id=document_id,
                user_id=triggered_by_user_id,
                action="validation_complete",
                details={
                    "violations": violations_count,
                    "errors": sum(1 for v in violations if v.severity == "error"),
                    "warnings": sum(1 for v in violations if v.severity == "warning"),
                    "fields_flagged": fields_flagged,
                },
            )
            await session.commit()
            step.detail = (
                f"violations={violations_count} "
                f"flagged={fields_flagged}/{len(field_reports)}"
            )
            await pipeline_broadcaster.broadcast(document_id, {
                "event": "step",
                "step": "validation",
                "percent": 90,
                "status": "processing",
                "message": f"Validation complete: {fields_flagged} fields flagged for review",
            })

        # ── Step 6: Persist ExtractedField rows ───────────────────────────────
        async with _step("persist_fields", step_results) as step:
            # Idempotency: delete any existing rows for this document
            await session.execute(
                delete(ExtractedField).where(ExtractedField.document_id == document_id)
            )

            for report in field_reports:
                ef = ExtractedField(
                    document_id=document_id,
                    field_name=report.field_name,
                    value=report.value,
                    confidence_score=report.combined_confidence,
                    is_flagged=report.is_flagged,
                )
                session.add(ef)

            await session.flush()
            fields_saved = len(field_reports)

            # ── Update geography fields on Document if extracted ───────────────
            from app.models.document import Document
            geo_updates: dict[str, str | None] = {}
            for geo in ("district", "tehsil", "village"):
                val = extracted_values.get(geo)
                if val:
                    geo_updates[geo] = val[:150]   # respect column width

            if geo_updates:
                from sqlalchemy import update
                await session.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(**geo_updates)
                )

            await session.commit()
            step.detail = f"saved={fields_saved} deleted_old=yes geo_updated={bool(geo_updates)}"
            await pipeline_broadcaster.broadcast(document_id, {
                "event": "step",
                "step": "persist_fields",
                "percent": 95,
                "status": "processing",
                "message": f"Persisted {fields_saved} extracted attributes",
            })

        # ── Step 7: Determine and set final document status ───────────────────
        async with _step("set_final_status", step_results) as step:
            has_errors = any(v.severity == "error" for v in violations)

            if fields_flagged > 0 or has_errors:
                final_status = "needs_review"
            else:
                final_status = "verified"

            await _set_document_status(session, document_id, final_status)
            await _log_audit(
                session,
                document_id=document_id,
                user_id=triggered_by_user_id,
                action="pipeline_complete",
                details={
                    "final_status": final_status,
                    "fields_saved": fields_saved,
                    "fields_flagged": fields_flagged,
                    "violations": violations_count,
                    "ocr_avg_confidence": ocr_avg_conf,
                    "total_duration_s": round(time.perf_counter() - wall_start, 3),
                },
            )
            await session.commit()
            step.detail = f"status={final_status}"
            await pipeline_broadcaster.broadcast(document_id, {
                "event": "complete",
                "step": "complete",
                "percent": 100,
                "status": final_status,
                "message": f"Pipeline complete. Status: {final_status}",
                "fields_flagged": fields_flagged,
                "confidence": round(ocr_avg_conf, 3),
            })

    # ─────────────────────────────────────────────────────────────────────────
    total_s = time.perf_counter() - wall_start
    log.info(
        "[pipeline] document_id=%d DONE status=%s fields=%d flagged=%d "
        "violations=%d ocr_conf=%.3f total=%.2fs",
        document_id,
        final_status,
        fields_saved,
        fields_flagged,
        violations_count,
        ocr_avg_conf,
        total_s,
    )

    return PipelineResult(
        document_id=document_id,
        final_status=final_status,
        ocr_avg_confidence=ocr_avg_conf,
        fields_saved=fields_saved,
        fields_flagged=fields_flagged,
        violations_count=violations_count,
        total_duration_s=total_s,
        steps=step_results,
    )
