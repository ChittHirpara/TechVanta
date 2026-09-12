"""
Jurisdiction-based document routing, verifier scoping, claiming, and escalation services.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Sequence

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.audit_trail import AuditTrail
from app.models.document import Document, DocumentStatus
from app.models.user import User, UserRole
from app.models.verifier_jurisdiction import VerifierJurisdiction
from app.services.audit_service import write_audit

log = logging.getLogger(__name__)


def _normalize(val: str | None) -> str | None:
    if val is None:
        return None
    s = val.strip()
    return s if s else None


async def get_verifiers_for_jurisdiction(
    db: AsyncSession,
    district: str | None,
    tehsil: str | None = None,
    village: str | None = None,
) -> list[int]:
    """
    Find distinct verifier user IDs covering the given geographical hierarchy.
    Hierarchical matching rule:
    - Match on exact (district, tehsil, village) if specified.
    - Match on (district, tehsil) where village IS NULL (verifier covers whole tehsil).
    - Match on (district) where tehsil IS NULL and village IS NULL (verifier covers whole district).
    """
    clean_district = _normalize(district)
    clean_tehsil = _normalize(tehsil)
    clean_village = _normalize(village)

    if not clean_district:
        return []

    # Build hierarchical OR condition
    conditions = [
        # Verifier covers the entire district (tehsil is NULL and village is NULL)
        and_(
            func.lower(VerifierJurisdiction.district) == clean_district.lower(),
            VerifierJurisdiction.tehsil.is_(None),
            VerifierJurisdiction.village.is_(None),
        )
    ]

    if clean_tehsil:
        # Verifier covers this specific tehsil (village is NULL)
        conditions.append(
            and_(
                func.lower(VerifierJurisdiction.district) == clean_district.lower(),
                func.lower(VerifierJurisdiction.tehsil) == clean_tehsil.lower(),
                VerifierJurisdiction.village.is_(None),
            )
        )

    if clean_tehsil and clean_village:
        # Verifier covers this specific village
        conditions.append(
            and_(
                func.lower(VerifierJurisdiction.district) == clean_district.lower(),
                func.lower(VerifierJurisdiction.tehsil) == clean_tehsil.lower(),
                func.lower(VerifierJurisdiction.village) == clean_village.lower(),
            )
        )

    stmt = (
        select(VerifierJurisdiction.user_id)
        .join(User, User.id == VerifierJurisdiction.user_id)
        .where(
            User.role.in_([UserRole.verifier, UserRole.admin]),
            or_(*conditions),
        )
        .distinct()
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def route_document(db: AsyncSession, doc: Document) -> dict[str, Any]:
    """
    Route a document based on its jurisdiction:
    1. Single verifier: Auto-assign directly to that verifier.
    2. Multiple verifiers: Place in unassigned shared pool for that jurisdiction.
    3. Zero verifiers: Flag as escalated with reason UNASSIGNED_JURISDICTION.
    """
    verifier_ids = await get_verifiers_for_jurisdiction(
        db,
        district=doc.district,
        tehsil=doc.tehsil,
        village=doc.village,
    )

    if len(verifier_ids) == 1:
        doc.assigned_verifier_id = verifier_ids[0]
        doc.claimed_at = datetime.now(timezone.utc)
        if doc.escalation_reason == "UNASSIGNED_JURISDICTION":
            doc.is_escalated = False
            doc.escalation_reason = None
        log.info("[routing] Document %d auto-assigned to verifier %d", doc.id, verifier_ids[0])
        return {"action": "auto_assigned", "verifier_id": verifier_ids[0]}

    if len(verifier_ids) > 1:
        doc.assigned_verifier_id = None
        doc.claimed_at = None
        if doc.escalation_reason == "UNASSIGNED_JURISDICTION":
            doc.is_escalated = False
            doc.escalation_reason = None
        log.info("[routing] Document %d routed to shared pool for verifiers %s", doc.id, verifier_ids)
        return {"action": "shared_pool", "verifier_ids": verifier_ids}

    # Zero verifiers (or unmapped jurisdiction)
    doc.assigned_verifier_id = None
    doc.claimed_at = None
    doc.is_escalated = True
    doc.escalation_reason = "UNASSIGNED_JURISDICTION"
    log.warning("[routing] Document %d has no assigned verifier - escalated to admin", doc.id)
    return {"action": "unassigned_escalated"}


async def claim_document(db: AsyncSession, doc: Document, current_user: User) -> Document:
    """
    Claim ownership of an unassigned document in a shared pool.
    Raises 409 Conflict if already claimed by someone else.
    """
    if doc.assigned_verifier_id is not None and doc.assigned_verifier_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document {doc.id} is already claimed by another verifier.",
        )

    doc.assigned_verifier_id = current_user.id
    doc.claimed_at = datetime.now(timezone.utc)
    if doc.escalation_reason == "UNASSIGNED_JURISDICTION":
        doc.is_escalated = False
        doc.escalation_reason = None

    await write_audit(
        db,
        action="document_claimed",
        document_id=doc.id,
        user_id=current_user.id,
        details={"claimed_by": current_user.username},
    )
    await db.commit()
    await db.refresh(doc)
    return doc


async def get_verifier_jurisdictions(db: AsyncSession, user_id: int) -> list[VerifierJurisdiction]:
    """Fetch all jurisdiction rows assigned to a verifier."""
    stmt = (
        select(VerifierJurisdiction)
        .where(VerifierJurisdiction.user_id == user_id)
        .order_by(VerifierJurisdiction.district, VerifierJurisdiction.tehsil)
    )
    return list((await db.execute(stmt)).scalars().all())


async def build_verifier_document_filter(db: AsyncSession, user_id: int):
    """
    Builds a SQLAlchemy filter expression for verifier document listings:
    A verifier can see:
    - Any document directly assigned to them (doc.assigned_verifier_id == user_id)
    - OR any unassigned document (doc.assigned_verifier_id IS NULL) in their covered jurisdictions.
    """
    jurisdictions = await get_verifier_jurisdictions(db, user_id)
    if not jurisdictions:
        # If verifier has no jurisdictions assigned, they only see documents explicitly assigned to them
        return Document.assigned_verifier_id == user_id

    pool_conditions = []
    for j in jurisdictions:
        clean_d = _normalize(j.district)
        clean_t = _normalize(j.tehsil)
        clean_v = _normalize(j.village)

        if clean_d and not clean_t and not clean_v:
            # Covers entire district
            pool_conditions.append(func.lower(Document.district) == clean_d.lower())
        elif clean_d and clean_t and not clean_v:
            # Covers specific tehsil
            pool_conditions.append(
                and_(
                    func.lower(Document.district) == clean_d.lower(),
                    func.lower(Document.tehsil) == clean_t.lower(),
                )
            )
        elif clean_d and clean_t and clean_v:
            # Covers specific village
            pool_conditions.append(
                and_(
                    func.lower(Document.district) == clean_d.lower(),
                    func.lower(Document.tehsil) == clean_t.lower(),
                    func.lower(Document.village) == clean_v.lower(),
                )
            )

    return or_(
        Document.assigned_verifier_id == user_id,
        and_(
            Document.assigned_verifier_id.is_(None),
            or_(*pool_conditions),
        ),
    )


async def get_escalations_summary(db: AsyncSession, sla_hours: int | None = None) -> dict[str, Any]:
    """
    Collects and categorizes all escalated documents for Admin review:
    1. SLA breached documents (unverified and older than SLA window).
    2. High-severity fraud / duplicate / discrepancy flags.
    3. Unassigned jurisdiction documents.
    """
    settings = get_settings()
    sla_limit = sla_hours if sla_hours is not None else settings.verification_sla_hours
    sla_cutoff = datetime.now(timezone.utc) - timedelta(hours=sla_limit)

    # 1. SLA breached
    sla_stmt = (
        select(Document)
        .where(
            Document.status.in_([
                DocumentStatus.uploaded,
                DocumentStatus.processing,
                DocumentStatus.needs_review,
            ]),
            Document.created_at <= sla_cutoff,
        )
        .order_by(Document.created_at.asc())
    )
    sla_docs = list((await db.execute(sla_stmt)).scalars().all())

    # 2. High Fraud Risk
    fraud_stmt = (
        select(Document)
        .where(
            Document.is_escalated.is_(True),
            Document.escalation_reason.in_(["HIGH_RISK_FRAUD", "HIGH_DISCREPANCY_FRAUD"]),
        )
        .order_by(Document.created_at.desc())
    )
    fraud_docs = list((await db.execute(fraud_stmt)).scalars().all())

    # 3. Unassigned Jurisdiction
    unassigned_stmt = (
        select(Document)
        .where(
            Document.assigned_verifier_id.is_(None),
            Document.is_escalated.is_(True),
            Document.escalation_reason == "UNASSIGNED_JURISDICTION",
        )
        .order_by(Document.created_at.desc())
    )
    unassigned_docs = list((await db.execute(unassigned_stmt)).scalars().all())

    # Ensure uniqueness of document IDs across total
    all_escalated_ids = {d.id for d in sla_docs} | {d.id for d in fraud_docs} | {d.id for d in unassigned_docs}

    return {
        "total_escalated": len(all_escalated_ids),
        "sla_breached_count": len(sla_docs),
        "fraud_risk_count": len(fraud_docs),
        "unassigned_count": len(unassigned_docs),
        "sla_breached_documents": sla_docs,
        "fraud_risk_documents": fraud_docs,
        "unassigned_documents": unassigned_docs,
    }
