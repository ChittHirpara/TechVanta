"""
Dashboard / statistics router.

GET /dashboard/stats  –  aggregate metrics for the ops dashboard
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.extracted_field import ExtractedField
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ── Response schema ───────────────────────────────────────────────────────────

class DistrictBreakdown(BaseModel):
    district: str | None
    total_documents: int
    verified: int
    needs_review: int
    processing: int


class DashboardStats(BaseModel):
    # Volume
    total_documents: int
    total_processed: int          # uploaded+processing excluded
    pending_review: int           # status = needs_review
    verified: int                 # status = verified

    # Quality
    avg_confidence: float | None  # mean confidence_score across all ExtractedFields
    flagged_field_count: int      # ExtractedFields where is_flagged = True
    total_fields: int             # all ExtractedFields ever saved

    # Breakdown
    district_breakdown: list[DistrictBreakdown]


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get(
    "/stats",
    response_model=DashboardStats,
    summary="Aggregate processing stats and district-wise breakdown",
)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardStats:
    """
    Returns system-wide metrics:

    - **total_documents**: every document ever uploaded
    - **total_processed**: documents that have left the upload/processing phase
    - **pending_review**: documents waiting for a verifier
    - **verified**: documents fully signed-off
    - **avg_confidence**: mean confidence score across all saved ``ExtractedField`` rows
    - **flagged_field_count**: fields that still need manual correction
    - **district_breakdown**: per-district totals with status sub-counts
    """

    # ── Document counts ───────────────────────────────────────────────────────
    doc_counts = (
        await db.execute(
            select(
                func.count().label("total"),
                func.sum(
                    case(
                        (Document.status == DocumentStatus.needs_review, 1),
                        else_=0,
                    )
                ).label("needs_review"),
                func.sum(
                    case(
                        (Document.status == DocumentStatus.verified, 1),
                        else_=0,
                    )
                ).label("verified"),
                func.sum(
                    case(
                        (Document.status.in_([
                            DocumentStatus.uploaded,
                            DocumentStatus.processing,
                        ]), 1),
                        else_=0,
                    )
                ).label("in_progress"),
            )
        )
    ).one()

    total_documents = doc_counts.total or 0
    pending_review  = int(doc_counts.needs_review or 0)
    verified_count  = int(doc_counts.verified or 0)
    in_progress     = int(doc_counts.in_progress or 0)
    total_processed = total_documents - in_progress

    # ── Field metrics ─────────────────────────────────────────────────────────
    field_stats = (
        await db.execute(
            select(
                func.count().label("total_fields"),
                func.avg(ExtractedField.confidence_score).label("avg_confidence"),
                func.sum(
                    case((ExtractedField.is_flagged.is_(True), 1), else_=0)
                ).label("flagged_count"),
            )
        )
    ).one()

    total_fields        = int(field_stats.total_fields or 0)
    avg_confidence_raw  = field_stats.avg_confidence
    avg_confidence      = round(float(avg_confidence_raw), 4) if avg_confidence_raw is not None else None
    flagged_field_count = int(field_stats.flagged_count or 0)

    # ── District breakdown ────────────────────────────────────────────────────
    district_rows = (
        await db.execute(
            select(
                Document.district,
                func.count().label("total"),
                func.sum(
                    case((Document.status == DocumentStatus.verified, 1), else_=0)
                ).label("verified"),
                func.sum(
                    case((Document.status == DocumentStatus.needs_review, 1), else_=0)
                ).label("needs_review"),
                func.sum(
                    case(
                        (Document.status.in_([
                            DocumentStatus.uploaded,
                            DocumentStatus.processing,
                        ]), 1),
                        else_=0,
                    )
                ).label("processing"),
            )
            .group_by(Document.district)
            .order_by(func.count().desc())
        )
    ).all()

    district_breakdown = [
        DistrictBreakdown(
            district=row.district,
            total_documents=row.total,
            verified=int(row.verified or 0),
            needs_review=int(row.needs_review or 0),
            processing=int(row.processing or 0),
        )
        for row in district_rows
    ]

    return DashboardStats(
        total_documents=total_documents,
        total_processed=total_processed,
        pending_review=pending_review,
        verified=verified_count,
        avg_confidence=avg_confidence,
        flagged_field_count=flagged_field_count,
        total_fields=total_fields,
        district_breakdown=district_breakdown,
    )
