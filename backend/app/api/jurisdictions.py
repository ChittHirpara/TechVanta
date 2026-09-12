"""
Jurisdiction Management & Escalation router for Admins.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_role
from app.db.session import get_db
from app.models.document import Document
from app.models.user import User, UserRole
from app.models.verifier_jurisdiction import VerifierJurisdiction
from app.schemas.document import DocumentRead
from app.schemas.jurisdiction import (
    EscalationsSummary,
    VerifierJurisdictionCreate,
    VerifierJurisdictionRead,
    VerifierUserSummary,
)
from app.services.audit_service import write_audit
from app.services.jurisdiction_service import get_escalations_summary

router = APIRouter(prefix="/jurisdictions", tags=["Jurisdictions"])


@router.get(
    "",
    response_model=list[VerifierJurisdictionRead],
    summary="List all verifier-to-jurisdiction assignments (Admin only)",
)
async def list_jurisdictions(
    user_id: int | None = Query(None, description="Filter by specific verifier user ID"),
    district: str | None = Query(None, description="Filter by district name"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> list[VerifierJurisdictionRead]:
    stmt = (
        select(VerifierJurisdiction, User.username.label("verifier_username"))
        .join(User, User.id == VerifierJurisdiction.user_id)
        .order_by(VerifierJurisdiction.district, VerifierJurisdiction.tehsil, VerifierJurisdiction.village)
    )
    if user_id:
        stmt = stmt.where(VerifierJurisdiction.user_id == user_id)
    if district:
        stmt = stmt.where(VerifierJurisdiction.district.ilike(f"%{district.strip()}%"))

    rows = (await db.execute(stmt)).all()
    results = []
    for vj, username in rows:
        item = VerifierJurisdictionRead(
            id=vj.id,
            user_id=vj.user_id,
            district=vj.district,
            tehsil=vj.tehsil,
            village=vj.village,
            created_at=vj.created_at,
            verifier_username=username,
        )
        results.append(item)
    return results


@router.post(
    "",
    response_model=VerifierJurisdictionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a verifier to a jurisdiction (Admin only)",
)
async def create_jurisdiction_assignment(
    payload: VerifierJurisdictionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> VerifierJurisdictionRead:
    # 1. Verify user exists and is verifier or admin
    target_user = (
        await db.execute(select(User).where(User.id == payload.user_id))
    ).scalar_one_or_none()

    if not target_user:
        raise HTTPException(status_code=404, detail=f"User {payload.user_id} not found.")

    if target_user.role not in (UserRole.verifier, UserRole.admin):
        raise HTTPException(
            status_code=400,
            detail=f"User '{target_user.username}' has role '{target_user.role.value}'. Only verifiers or admins can be assigned jurisdictions.",
        )

    # Clean strings
    district_clean = payload.district.strip()
    tehsil_clean = payload.tehsil.strip() if payload.tehsil and payload.tehsil.strip() else None
    village_clean = payload.village.strip() if payload.village and payload.village.strip() else None

    # 2. Check for duplicate mapping
    dup_stmt = select(VerifierJurisdiction).where(
        VerifierJurisdiction.user_id == payload.user_id,
        func.lower(VerifierJurisdiction.district) == district_clean.lower(),
        func.lower(VerifierJurisdiction.tehsil) == (tehsil_clean.lower() if tehsil_clean else None),
        func.lower(VerifierJurisdiction.village) == (village_clean.lower() if village_clean else None),
    )
    dup = (await db.execute(dup_stmt)).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="This exact jurisdiction mapping already exists for this verifier.")

    new_vj = VerifierJurisdiction(
        user_id=payload.user_id,
        district=district_clean,
        tehsil=tehsil_clean,
        village=village_clean,
    )
    db.add(new_vj)
    await db.flush()

    await write_audit(
        db,
        action="jurisdiction_assigned",
        user_id=current_user.id,
        details={
            "assigned_user_id": target_user.id,
            "assigned_username": target_user.username,
            "district": district_clean,
            "tehsil": tehsil_clean,
            "village": village_clean,
        },
    )
    await db.commit()
    await db.refresh(new_vj)

    return VerifierJurisdictionRead(
        id=new_vj.id,
        user_id=new_vj.user_id,
        district=new_vj.district,
        tehsil=new_vj.tehsil,
        village=new_vj.village,
        created_at=new_vj.created_at,
        verifier_username=target_user.username,
    )


@router.delete(
    "/{jurisdiction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a verifier-to-jurisdiction assignment (Admin only)",
)
async def delete_jurisdiction_assignment(
    jurisdiction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    vj = (
        await db.execute(select(VerifierJurisdiction).where(VerifierJurisdiction.id == jurisdiction_id))
    ).scalar_one_or_none()

    if not vj:
        raise HTTPException(status_code=404, detail="Jurisdiction assignment not found.")

    await write_audit(
        db,
        action="jurisdiction_removed",
        user_id=current_user.id,
        details={
            "removed_assignment_id": vj.id,
            "user_id": vj.user_id,
            "district": vj.district,
            "tehsil": vj.tehsil,
            "village": vj.village,
        },
    )
    await db.delete(vj)
    await db.commit()
    return None


@router.get(
    "/verifiers",
    response_model=list[VerifierUserSummary],
    summary="List all verifiers and their assignment counts (Admin only)",
)
async def list_verifier_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> list[VerifierUserSummary]:
    stmt = (
        select(
            User.id,
            User.username,
            User.role,
            func.count(VerifierJurisdiction.id).label("jurisdiction_count"),
        )
        .outerjoin(VerifierJurisdiction, VerifierJurisdiction.user_id == User.id)
        .where(User.role.in_([UserRole.verifier, UserRole.admin]))
        .group_by(User.id, User.username, User.role)
        .order_by(User.username.asc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        VerifierUserSummary(
            id=r[0],
            username=r[1],
            role=r[2],
            jurisdiction_count=int(r[3] or 0),
        )
        for r in rows
    ]


@router.get(
    "/escalations",
    response_model=EscalationsSummary,
    summary="Fetch all categorized admin escalations: SLA breach, fraud risk, unassigned (Admin only)",
)
async def list_admin_escalations(
    sla_hours: int | None = Query(None, description="Override SLA hours"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> EscalationsSummary:
    summary_data = await get_escalations_summary(db, sla_hours=sla_hours)
    return EscalationsSummary(
        total_escalated=summary_data["total_escalated"],
        sla_breached_count=summary_data["sla_breached_count"],
        fraud_risk_count=summary_data["fraud_risk_count"],
        unassigned_count=summary_data["unassigned_count"],
        sla_breached_documents=[DocumentRead.model_validate(d) for d in summary_data["sla_breached_documents"]],
        fraud_risk_documents=[DocumentRead.model_validate(d) for d in summary_data["fraud_risk_documents"]],
        unassigned_documents=[DocumentRead.model_validate(d) for d in summary_data["unassigned_documents"]],
    )
