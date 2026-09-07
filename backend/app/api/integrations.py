"""
Government integration endpoints.

POST /integrations/lrms/push/{document_id}  – push to Land Record Management System
POST /integrations/gis/push/{document_id}   – push to GIS portal

Both endpoints:
  1. Verify the document exists and is in `verified` status
  2. Load all ExtractedField values
  3. Build the system-specific payload
  4. Log the full payload to AuditTrail (permanent record of what was sent)
  5. Call the mock push function (swap for real HTTP when ready)
  6. Return the push result including the fake government reference ID

Access: admin + verifier roles only.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_role
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.extracted_field import ExtractedField
from app.models.user import User, UserRole
from app.services.audit_service import write_audit
from app.services.integrations import (
    build_gis_payload,
    build_lrms_payload,
    mock_push_gis,
    mock_push_lrms,
)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


# ── Response schema ───────────────────────────────────────────────────────────

class IntegrationResponse(BaseModel):
    system:       str
    document_id:  int
    reference_id: str
    status:       str
    pushed_at:    str
    mock:         bool
    payload_logged: bool = True  # confirms AuditTrail write succeeded


# ── Shared helpers ────────────────────────────────────────────────────────────

async def _load_verified_document(doc_id: int, db: AsyncSession) -> Document:
    """Load the document, enforcing verified status."""
    doc = (
        await db.execute(select(Document).where(Document.id == doc_id))
    ).scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found.")

    if doc.status != DocumentStatus.verified:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Document {doc_id} has status '{doc.status.value}'. "
                "Only 'verified' documents may be pushed to external systems. "
                "Complete verification first via POST /documents/{id}/verify."
            ),
        )
    return doc


async def _load_fields_dict(doc_id: int, db: AsyncSession) -> dict[str, str | None]:
    """Return {field_name: value} for all ExtractedField rows of a document."""
    rows = (
        await db.execute(
            select(ExtractedField).where(ExtractedField.document_id == doc_id)
        )
    ).scalars().all()
    return {row.field_name: row.value for row in rows}


# ─────────────────────────────────────────────────────────────────────────────
# POST /integrations/lrms/push/{document_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/lrms/push/{document_id}",
    response_model=IntegrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Push a verified document to the Land Record Management System (LRMS)",
)
async def push_to_lrms(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.verifier)),
) -> IntegrationResponse:
    """
    Builds the LRMS payload from the verified document's extracted fields,
    logs the full payload to ``AuditTrail``, and returns a mock acceptance
    response with a government-style reference ID.

    **Fields included in the LRMS payload:**
    owner_name, survey_number, khasra_number, khata_number, plot_area,
    land_classification, ownership_details, mutation_record, registration_info,
    district, tehsil, village.

    When wired to a real LRMS endpoint, replace ``mock_push_lrms`` in
    ``app/services/integrations.py`` with the actual HTTP call — this
    router and audit code stay unchanged.
    """
    doc    = await _load_verified_document(document_id, db)
    fields = await _load_fields_dict(document_id, db)

    pushed_at = datetime.now(timezone.utc).isoformat()

    payload = build_lrms_payload(
        doc_id=document_id,
        filename=doc.filename,
        district=doc.district,
        tehsil=doc.tehsil,
        village=doc.village,
        uploaded_by=doc.uploaded_by,
        verified_at=pushed_at,
        fields=fields,
    )

    # ── Mock push ─────────────────────────────────────────────────────────────
    result = mock_push_lrms(document_id, doc.district, payload)

    # ── Audit: log the full payload + reference ID permanently ───────────────
    await write_audit(
        db,
        "lrms_push",
        document_id=document_id,
        user_id=current_user.id,
        details={
            "reference_id": result.reference_id,
            "status":       result.status,
            "pushed_at":    result.pushed_at,
            "mock":         result.mock,
            "payload":      payload,              # full payload for audit trail
        },
    )
    await db.commit()

    return IntegrationResponse(
        system=result.system,
        document_id=result.document_id,
        reference_id=result.reference_id,
        status=result.status,
        pushed_at=result.pushed_at,
        mock=result.mock,
        payload_logged=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /integrations/gis/push/{document_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/gis/push/{document_id}",
    response_model=IntegrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Push verified geospatial metadata to the State GIS portal",
)
async def push_to_gis(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.verifier)),
) -> IntegrationResponse:
    """
    Builds the GIS portal geo-package for the verified document,
    pushes it (mocked), and logs the full payload to ``AuditTrail``.

    GIS updates are typically asynchronous in real portals — the ``status``
    field will read ``"queued"`` to reflect this.
    """
    doc    = await _load_verified_document(document_id, db)
    fields = await _load_fields_dict(document_id, db)

    pushed_at = datetime.now(timezone.utc).isoformat()

    payload = build_gis_payload(
        doc_id=document_id,
        district=doc.district,
        tehsil=doc.tehsil,
        village=doc.village,
        verified_at=pushed_at,
        fields=fields,
    )

    # ── Mock push ─────────────────────────────────────────────────────────────
    result = mock_push_gis(document_id, doc.district, payload)

    # ── Audit: log the full payload + reference ID permanently ───────────────
    await write_audit(
        db,
        "gis_push",
        document_id=document_id,
        user_id=current_user.id,
        details={
            "reference_id": result.reference_id,
            "status":       result.status,
            "pushed_at":    result.pushed_at,
            "mock":         result.mock,
            "payload":      payload,
        },
    )
    await db.commit()

    return IntegrationResponse(
        system=result.system,
        document_id=result.document_id,
        reference_id=result.reference_id,
        status=result.status,
        pushed_at=result.pushed_at,
        mock=result.mock,
        payload_logged=True,
    )
