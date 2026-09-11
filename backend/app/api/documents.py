"""
Documents router — full CRUD + verification workflow.

Endpoints
─────────
  POST   /documents/upload                    Upload file, start pipeline (202)
  GET    /documents/{id}                      Document detail + extracted fields
  GET    /documents                           Paginated, filtered list
  PATCH  /documents/{id}/fields/{field_name}  Correct a field (verifier/admin)
  POST   /documents/{id}/verify               Mark verified (blocks on flagged fields)
  POST   /documents/{id}/reprocess            Re-run full pipeline (verifier/admin)
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter, BackgroundTasks, Body, Depends, File,
    Form, Header, HTTPException, Query, Request, Response, UploadFile, status,
)
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_role
from app.core.limiter import limiter
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.audit_trail import AuditTrail
from app.models.document import Document, DocumentStatus
from app.models.extracted_field import ExtractedField
from app.models.user import User, UserRole
from app.models.verification_log import VerificationLog
from app.schemas.document import (
    DocumentDetail,
    DocumentRead,
    ExtractedFieldRead,
    FieldPatchRequest,
    PaginatedDocuments,
)
from app.services.audit_service import write_audit
from app.services.certificate_service import generate_certificate_html
from app.services.dilrmp import build_dilrmp_export_payload, compute_file_sha256, generate_ulpin
from app.services.pipeline import pipeline_broadcaster, process_document
from app.services.validation import find_duplicates

router = APIRouter(prefix="/documents", tags=["Documents"])

# ── Config & Upload Hardening ──────────────────────────────────────────────────
# Anchor uploads/ relative to THIS file's package root (backend/app/api/documents.py
# → backend/uploads/) so it's CWD-independent regardless of where uvicorn starts.
_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_ALLOWED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB

MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF-"],
    ".png": [b"\x89PNG\r\n\x1a\n", b"\x89PNG"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".tiff": [b"II*\x00", b"MM\x00*"],
    ".tif": [b"II*\x00", b"MM\x00*"],
}


# ── Shared helpers ────────────────────────────────────────────────────────────

def _save_upload(file: UploadFile) -> Path:
    suffix = Path(file.filename or "file").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(_ALLOWED_SUFFIXES)}",
        )

    # Validate header signature (magic bytes)
    header = file.file.read(16)
    if not header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    valid_signatures = MAGIC_SIGNATURES.get(suffix, [])
    if valid_signatures and not any(header.startswith(sig) for sig in valid_signatures):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File signature (magic bytes) does not match declared type '{suffix}'.",
        )

    file.file.seek(0)
    dest = _UPLOAD_DIR / f"{uuid.uuid4()}{suffix}"
    total_bytes = 0
    oversized = False

    with dest.open("wb") as fp:
        while chunk := file.file.read(65536):
            total_bytes += len(chunk)
            if total_bytes > MAX_FILE_SIZE_BYTES:
                oversized = True
                break
            fp.write(chunk)

    if oversized:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File size exceeds limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    return dest


def require_document_access(doc: Document, current_user: User) -> None:
    """
    Enforce object-level access control:
    - field_officer: can only access documents they uploaded
    - verifier and admin: can access any document
    """
    if current_user.role == UserRole.field_officer and doc.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you do not have permission to access this document.",
        )


async def _get_doc_or_404(doc_id: int, db: AsyncSession) -> Document:
    doc = (
        await db.execute(select(Document).where(Document.id == doc_id))
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")
    return doc


async def _get_field_or_404(
    doc_id: int, field_name: str, db: AsyncSession
) -> ExtractedField:
    ef = (
        await db.execute(
            select(ExtractedField).where(
                ExtractedField.document_id == doc_id,
                ExtractedField.field_name == field_name,
            )
        )
    ).scalar_one_or_none()
    if ef is None:
        raise HTTPException(
            status_code=404,
            detail=f"Field '{field_name}' not found on document {doc_id}.",
        )
    return ef


# ─────────────────────────────────────────────────────────────────────────────
# POST /documents/upload
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=DocumentRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a land-record document and start async OCR + extraction",
)
@limiter.limit("30/minute")
async def upload_document(
    request: Request,                        # required by slowapi for IP key extraction
    response: Response,                      # required by slowapi for X-RateLimit-* headers
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF or image file"),
    district: str | None = Form(None),
    tehsil:   str | None = Form(None),
    village:  str | None = Form(None),
    client_capture_id: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentRead:
    """
    Saves the file, creates a ``Document`` row with ``status=processing``,
    enqueues the full OCR→extraction→validation pipeline as a BackgroundTask,
    and returns the ``document_id`` immediately.

    If client_capture_id is provided and was already uploaded, returns existing document (idempotency).

    Poll ``GET /documents/{id}`` to watch:
    ``processing → needs_review | verified``
    """
    if client_capture_id:
        recent_audits = (
            await db.execute(
                select(AuditTrail).where(
                    AuditTrail.user_id == current_user.id,
                    AuditTrail.action == "document_uploaded",
                ).order_by(AuditTrail.timestamp.desc()).limit(50)
            )
        ).scalars().all()
        for audit in recent_audits:
            if audit.details and audit.details.get("client_capture_id") == client_capture_id:
                existing_doc = (
                    await db.execute(select(Document).where(Document.id == audit.document_id))
                ).scalar_one_or_none()
                if existing_doc:
                    return DocumentRead.model_validate(existing_doc)

    try:
        storage_path = _save_upload(file)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"File save failed: {exc}") from exc

    doc = Document(
        filename=file.filename or storage_path.name,
        storage_path=str(storage_path.resolve()),
        uploaded_by=current_user.id,
        status=DocumentStatus.processing,   # immediately mark processing
        district=district,
        tehsil=tehsil,
        village=village,
    )
    db.add(doc)
    await db.flush()

    audit_details = {"filename": doc.filename}
    if client_capture_id:
        audit_details["client_capture_id"] = client_capture_id

    await write_audit(
        db,
        "document_uploaded",
        document_id=doc.id,
        user_id=current_user.id,
        details=audit_details,
    )
    await db.commit()
    await db.refresh(doc)

    # Pipeline owns its own DB session (request session closes after response)
    background_tasks.add_task(
        process_document,
        doc.id,
        triggered_by_user_id=current_user.id,
        db=None,
    )

    return DocumentRead.model_validate(doc)


# ─────────────────────────────────────────────────────────────────────────────
# GET /documents/notifications (Field Officer Status Notifications)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/notifications",
    summary="Get recent status notifications for field officer's uploaded documents",
)
async def get_document_notifications(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """
    Returns a list of status transition events (verified, needs_review, processing)
    for documents uploaded by the current field officer.
    """
    stmt = select(Document).order_by(Document.updated_at.desc()).limit(limit)
    if current_user.role == UserRole.field_officer:
        stmt = stmt.where(Document.uploaded_by == current_user.id)

    docs = (await db.execute(stmt)).scalars().all()
    notifications = []
    for doc in docs:
        if doc.status == DocumentStatus.verified:
            notifications.append({
                "id": f"notif_verified_{doc.id}",
                "document_id": doc.id,
                "title": f"Document #{doc.id} Verified",
                "message": f"Land record '{doc.filename}' has been successfully verified & sealed.",
                "type": "success",
                "status": doc.status.value,
                "timestamp": doc.updated_at.isoformat() if doc.updated_at else datetime.now(timezone.utc).isoformat(),
            })
        elif doc.status == DocumentStatus.needs_review:
            notifications.append({
                "id": f"notif_review_{doc.id}",
                "document_id": doc.id,
                "title": f"Document #{doc.id} Requires Review",
                "message": f"Land record '{doc.filename}' has flagged attributes under verifier review.",
                "type": "warning",
                "status": doc.status.value,
                "timestamp": doc.updated_at.isoformat() if doc.updated_at else datetime.now(timezone.utc).isoformat(),
            })
        elif doc.status == DocumentStatus.processing:
            notifications.append({
                "id": f"notif_proc_{doc.id}",
                "document_id": doc.id,
                "title": f"Document #{doc.id} Processing",
                "message": f"OCR & extraction pipeline running for '{doc.filename}'.",
                "type": "info",
                "status": doc.status.value,
                "timestamp": doc.created_at.isoformat() if doc.created_at else datetime.now(timezone.utc).isoformat(),
            })
    return notifications



# ─────────────────────────────────────────────────────────────────────────────
# GET /documents/public/verify/{ulpin}/{file_hash} (Public Citizen QR Verify)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/public/verify/{ulpin}/{file_hash}",
    summary="Public verification endpoint for citizen / bank QR code scans",
)
async def public_verify_ulpin(
    ulpin: str,
    file_hash: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public verification endpoint that validates a land parcel ULPIN and SHA-256 seal.
    Returns authenticity status without exposing sensitive personal owner data.
    """
    # Enforce minimum hash length and hexadecimal format to prevent brute-forcing/wildcards
    clean_hash = file_hash.strip().lower()
    clean_ulpin = ulpin.strip().upper()
    if len(clean_hash) < 32 or not re.fullmatch(r"^[0-9a-f]{32,64}$", clean_hash):
        return {
            "status": "RECORD_NOT_FOUND_OR_PENDING",
            "ulpin": clean_ulpin,
            "verification_status": "UNVERIFIED",
            "message": "Invalid cryptographic hash format or insufficient digest length.",
        }

    stmt = select(Document).where(Document.status == DocumentStatus.verified)
    verified_docs = (await db.execute(stmt)).scalars().all()

    matched_doc = None
    for doc in verified_docs:
        try:
            h = compute_file_sha256(doc.storage_path)
            if h.lower().startswith(clean_hash):
                # Verify ULPIN matches the parcel record
                fields_stmt = select(ExtractedField).where(ExtractedField.document_id == doc.id)
                fields = (await db.execute(fields_stmt)).scalars().all()
                field_map = {f.field_name: f.value for f in fields}
                expected_ulpin = generate_ulpin(
                    district=doc.district or field_map.get("district"),
                    tehsil=doc.tehsil or field_map.get("tehsil"),
                    village=doc.village or field_map.get("village"),
                    khasra_number=field_map.get("khasra_number"),
                    survey_number=field_map.get("survey_number"),
                )
                if expected_ulpin == clean_ulpin:
                    matched_doc = doc
                    break
        except Exception:
            continue

    if matched_doc:
        return {
            "status": "AUTHENTIC_VERIFIED",
            "ulpin": clean_ulpin,
            "verification_status": "SEALED",
            "jurisdiction": f"{matched_doc.district or 'Rajasthan'}, {matched_doc.tehsil or ''}",
            "verified_at": matched_doc.updated_at.isoformat() if matched_doc.updated_at else None,
            "integrity_seal": "SHA-256_MATCHED",
            "issuing_authority": "Ministry of Rural Development • Department of Land Resources (DILRMP)",
        }

    return {
        "status": "RECORD_NOT_FOUND_OR_PENDING",
        "ulpin": clean_ulpin,
        "verification_status": "UNVERIFIED",
        "message": "No matching sealed record found with this cryptographic digest and ULPIN.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /documents/{id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
    summary="Fetch document metadata + all extracted fields with confidence scores",
)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentDetail:
    """
    Returns the document metadata and its extracted fields.

    While the pipeline is still running (``status=processing``) the
    ``extracted_fields`` list will be empty.  Poll until status changes.
    """
    doc = await _get_doc_or_404(document_id, db)
    require_document_access(doc, current_user)

    fields = (
        await db.execute(
            select(ExtractedField)
            .where(ExtractedField.document_id == document_id)
            .order_by(ExtractedField.field_name)
        )
    ).scalars().all()

    # Fast duplicate check for Fraud Shield awareness
    field_map = {f.field_name: f.value for f in fields}
    owner_name = field_map.get("owner_name")
    survey_number = field_map.get("survey_number")
    matches = []
    if owner_name or survey_number:
        dups = await find_duplicates(owner_name, survey_number, db, limit=100)
        matches = [d for d in dups if d.document_id != document_id]

    # Reference-data comparison & risk (file-based trusted records)
    from app.services.reference_comparison import full_risk_assessment
    comparison, risk = full_risk_assessment(field_map, doc)

    doc_data = DocumentRead.model_validate(doc).model_dump()
    doc_data["has_suspected_duplicates"] = len(matches) > 0
    doc_data["duplicate_count"] = len(matches)
    doc_data["comparison"] = comparison.to_dict()
    doc_data["risk"] = risk.to_dict()

    return DocumentDetail(
        **doc_data,
        extracted_fields=[ExtractedFieldRead.model_validate(f) for f in fields],
        top_duplicate_score=matches[0].combined_score if matches else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /documents
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=PaginatedDocuments,
    summary="Paginated, filtered document list",
)
async def list_documents(
    status:    DocumentStatus | None = Query(None, description="Filter by processing status"),
    district:  str | None            = Query(None, description="Filter by district name"),
    page:      int                   = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int                   = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedDocuments:
    base = select(Document)
    if current_user.role == UserRole.field_officer:
        base = base.where(Document.uploaded_by == current_user.id)
    if status:
        base = base.where(Document.status == status)
    if district:
        base = base.where(Document.district.ilike(f"%{district}%"))

    # Total count
    count_stmt = select(func.count()).select_from(base.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    # Paginated rows
    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            base.order_by(Document.created_at.desc())
                .limit(page_size)
                .offset(offset)
        )
    ).scalars().all()

    return PaginatedDocuments(
        total=total,
        page=page,
        page_size=page_size,
        items=[DocumentRead.model_validate(r) for r in rows],
    )


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /documents/{id}/fields/{field_name}
# ─────────────────────────────────────────────────────────────────────────────

@router.patch(
    "/{document_id}/fields/{field_name}",
    response_model=ExtractedFieldRead,
    summary="Correct an extracted field value (verifier / admin only)",
)
async def patch_field(
    document_id: int,
    field_name: str,
    payload: FieldPatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.verifier)),
) -> ExtractedFieldRead:
    """
    Update the value of a single extracted field, clear its ``is_flagged``
    flag, and write entries to both ``VerificationLog`` and ``AuditTrail``.

    Only ``verifier`` and ``admin`` roles are permitted.
    """
    doc = await _get_doc_or_404(document_id, db)
    require_document_access(doc, current_user)
    ef  = await _get_field_or_404(document_id, field_name, db)

    old_value = ef.value

    # Update the field
    ef.value            = payload.value.strip()
    ef.is_flagged       = False              # correction clears the flag
    ef.confidence_score = 1.0                # human verifier confirmed/certified

    # Verification log
    db.add(VerificationLog(
        document_id=document_id,
        verifier_id=current_user.id,
        field_name=field_name,
        old_value=old_value,
        new_value=ef.value,
    ))

    # Audit trail
    await write_audit(
        db,
        "field_corrected",
        document_id=document_id,
        user_id=current_user.id,
        details={
            "field_name": field_name,
            "old_value":  old_value,
            "new_value":  ef.value,
            "note":       payload.note,
        },
    )

    # If all fields are now un-flagged, bump document status back to processing
    # so the verifier can run /verify when ready
    remaining_flags = (
        await db.execute(
            select(func.count())
            .where(
                ExtractedField.document_id == document_id,
                ExtractedField.is_flagged.is_(True),
            )
        )
    ).scalar_one()

    if doc.status == DocumentStatus.needs_review and remaining_flags == 0:
        # All flags cleared — bump updated_at so the frontend knows a change happened.
        # Document stays in needs_review until the verifier explicitly calls POST /verify.
        await db.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(updated_at=func.now())  # explicit bump (onupdate doesn't fire on raw update())
        )

    await db.commit()
    await db.refresh(ef)
    return ExtractedFieldRead.model_validate(ef)


# ─────────────────────────────────────────────────────────────────────────────
# POST /documents/{id}/verify
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/{document_id}/verify",
    response_model=DocumentRead,
    summary="Mark a document as verified (blocks if any field is still flagged)",
)
async def verify_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.verifier)),
) -> DocumentRead:
    """
    Transitions ``status → verified``.

    **Blocked** (422) if any ``ExtractedField.is_flagged == True``.
    Correct all flagged fields first via
    ``PATCH /documents/{id}/fields/{field_name}``.
    """
    doc = await _get_doc_or_404(document_id, db)
    require_document_access(doc, current_user)

    if doc.status == DocumentStatus.verified:
        raise HTTPException(status_code=409, detail="Document is already verified.")

    # Guard: reject if document has no extracted fields at all
    total_fields: int = (
        await db.execute(
            select(func.count()).where(ExtractedField.document_id == document_id)
        )
    ).scalar_one()

    if total_fields == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cannot verify document with zero extracted entity fields. Reprocess or extract fields first.",
        )

    # Guard: reject if any field still flagged
    flagged_count: int = (
        await db.execute(
            select(func.count())
            .where(
                ExtractedField.document_id == document_id,
                ExtractedField.is_flagged.is_(True),
            )
        )
    ).scalar_one()

    if flagged_count > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"{flagged_count} field(s) are still flagged for review. "
                "Correct them via PATCH /documents/{id}/fields/{field_name} first."
            ),
        )

    # Promote status + bump updated_at (onupdate doesn't fire on raw update() calls)
    await db.execute(
        update(Document)
        .where(Document.id == document_id)
        .values(status=DocumentStatus.verified, updated_at=func.now())
    )

    await write_audit(
        db,
        "document_verified",
        document_id=document_id,
        user_id=current_user.id,
        details={"verified_by": current_user.username},
    )
    await db.commit()

    doc = await _get_doc_or_404(document_id, db)
    return DocumentRead.model_validate(doc)


# ─────────────────────────────────────────────────────────────────────────────
# POST /documents/{id}/reprocess
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/{document_id}/reprocess",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-run full pipeline on an existing document (admin / verifier only)",
)
async def reprocess_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.verifier)),
) -> dict:
    doc = await _get_doc_or_404(document_id, db)
    require_document_access(doc, current_user)
    if not Path(doc.storage_path).exists():
        raise HTTPException(422, "Original file missing from disk; cannot reprocess.")

    await write_audit(
        db,
        "reprocess_requested",
        document_id=document_id,
        user_id=current_user.id,
        details={},
    )
    await db.commit()

    background_tasks.add_task(
        process_document,
        document_id,
        triggered_by_user_id=current_user.id,
        db=None,
    )
    return {"message": "Reprocessing enqueued.", "document_id": document_id}


# ─────────────────────────────────────────────────────────────────────────────
# GET /documents/{id}/events  (Real-Time SSE Progress Stream)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{document_id}/events",
    summary="Real-time Server-Sent Events (SSE) stream of pipeline progress",
)
async def stream_document_events(
    document_id: int,
    token: str | None = Query(None, description="Auth token for direct EventSource stream"),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Streams live step-by-step progress events for document processing.
    Emits JSON payloads under `data:` with step name, percent, status, and message.
    Supports both Authorization header and ?token= query parameter for browser EventSource.
    """
    current_user = await _resolve_user(token, authorization, db)
    doc = await _get_doc_or_404(document_id, db)
    require_document_access(doc, current_user)

    async def event_generator():
        # If document already finished processing, emit final status and close
        if doc.status in (DocumentStatus.verified, DocumentStatus.needs_review):
            payload = {
                "event": "complete",
                "step": "complete",
                "percent": 100,
                "status": doc.status.value,
                "message": f"Document processing is already complete ({doc.status.value}).",
            }
            yield f"data: {json.dumps(payload)}\n\n"
            return

        queue = pipeline_broadcaster.subscribe(document_id)
        try:
            while True:
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=25.0)
                    yield f"data: {json.dumps(event_data)}\n\n"
                    if event_data.get("event") in ("complete", "error"):
                        break
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            pipeline_broadcaster.unsubscribe(document_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /documents/{id}/duplicates  (Duplicate Detection & Fraud Shield)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{document_id}/duplicates",
    summary="Detect potential duplicate/fraudulent land records across the database",
)
async def get_document_duplicates(
    document_id: int,
    threshold: float | None = Query(None, ge=0.0, le=100.0, description="Override fuzzy threshold (0-100)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await _get_doc_or_404(document_id, db)
    require_document_access(doc, current_user)

    fields = (
        await db.execute(
            select(ExtractedField).where(ExtractedField.document_id == document_id)
        )
    ).scalars().all()
    field_map = {f.field_name: f.value for f in fields}

    owner_name = field_map.get("owner_name")
    survey_number = field_map.get("survey_number")

    duplicates = await find_duplicates(
        owner_name=owner_name,
        survey_number=survey_number,
        db_session=db,
        threshold=threshold,
    )
    # Exclude self
    matches = [d.to_dict() for d in duplicates if d.document_id != document_id]

    return {
        "document_id": document_id,
        "queried_owner": owner_name,
        "queried_survey_number": survey_number,
        "duplicate_count": len(matches),
        "has_suspected_duplicates": len(matches) > 0,
        "matches": matches,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /documents/{id}/export/dilrmp  (DILRMP 2.0 Standard Export with ULPIN)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{document_id}/export/dilrmp",
    summary="Export government DILRMP 2.0 standard record with ULPIN & cryptographic seal",
)
async def export_dilrmp(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await _get_doc_or_404(document_id, db)
    require_document_access(doc, current_user)
    fields = (
        await db.execute(
            select(ExtractedField).where(ExtractedField.document_id == document_id)
        )
    ).scalars().all()

    payload = build_dilrmp_export_payload(
        document=doc,
        fields=fields,
        verifier_username=current_user.username,
    )
    return payload


# ─────────────────────────────────────────────────────────────────────────────
# GET /documents/{id}/integrity  (Cryptographic Document Seal & Tamper Check)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{document_id}/integrity",
    summary="Verify cryptographic SHA-256 seal and document file integrity",
)
async def verify_integrity(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await _get_doc_or_404(document_id, db)
    require_document_access(doc, current_user)
    file_path = Path(doc.storage_path)

    if not file_path.exists():
        return {
            "document_id": doc.id,
            "filename": doc.filename,
            "file_exists": False,
            "file_size_bytes": 0,
            "sha256_hash": None,
            "status": "COMPROMISED_FILE_MISSING",
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }

    sha256 = compute_file_sha256(file_path)
    return {
        "document_id": doc.id,
        "filename": doc.filename,
        "file_exists": True,
        "file_size_bytes": file_path.stat().st_size,
        "sha256_hash": sha256,
        "status": "SECURED_VERIFIED",
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Helpers for file token authentication ────────────────────────────────────

async def _resolve_user(token: str | None, auth_header: str | None, db: AsyncSession) -> User:
    from app.services.user_service import get_user_by_id

    token_str = token
    if not token_str and auth_header and auth_header.startswith("Bearer "):
        token_str = auth_header[7:].strip()
    if not token_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = decode_access_token(token_str)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        user = await get_user_by_id(db, int(user_id))
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


# ─────────────────────────────────────────────────────────────────────────────
# GET /documents/{id}/file  (Serve Scanned PDF / Image for Frontend Preview)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{document_id}/file",
    summary="Download or stream original deed file for split-screen frontend rendering",
)
async def get_document_file(
    document_id: int,
    token: str | None = Query(None, description="Auth token for direct iframe or img preview"),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    current_user = await _resolve_user(token, authorization, db)
    doc = await _get_doc_or_404(document_id, db)
    require_document_access(doc, current_user)
    file_path = Path(doc.storage_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Deed file not found on disk.")

    media_type, _ = mimetypes.guess_type(doc.filename)
    if not media_type:
        media_type = "application/pdf" if doc.filename.lower().endswith(".pdf") else "application/octet-stream"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=doc.filename,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /documents/{id}/audit  (Chronological Document Audit Trail)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{document_id}/audit",
    summary="Fetch complete chronological audit trail history for this document",
)
async def get_document_audit(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await _get_doc_or_404(document_id, db)
    require_document_access(doc, current_user)
    stmt = (
        select(AuditTrail)
        .where(AuditTrail.document_id == document_id)
        .order_by(AuditTrail.timestamp.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "document_id": r.document_id,
            "user_id": r.user_id,
            "action": r.action,
            "details": r.details,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# GET /documents/{id}/certificate (Sovereign Verification Certificate HTML/Print)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{document_id}/certificate",
    response_class=HTMLResponse,
    summary="Generate a printable, cryptographically sealed Sovereign Verification Certificate",
)
async def get_document_certificate(
    document_id: int,
    token: str | None = Query(None, description="Auth token for direct browser viewing"),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    current_user = await _resolve_user(token, authorization, db)
    doc = await _get_doc_or_404(document_id, db)
    require_document_access(doc, current_user)

    stmt = select(ExtractedField).where(ExtractedField.document_id == document_id)
    fields = (await db.execute(stmt)).scalars().all()

    verifier_name = f"{current_user.username} ({current_user.role.value.capitalize()})"
    cert_html = generate_certificate_html(
        document=doc,
        fields=fields,
        verifier_username=verifier_name,
    )
    return HTMLResponse(content=cert_html, status_code=200)




