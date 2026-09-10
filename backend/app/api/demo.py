"""
Demo orchestration API for Smart India Hackathon (SIH) 2026.

Provides endpoints to inspect showcase records and reset the system into a
known-good rehearsal state for zero-risk live jury presentations.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.document import Document
from app.models.extracted_field import ExtractedField
from app.models.user import User
from app.services.demo_seeder import DEMO_DOCUMENTS, DEMO_USERS, reset_and_seed_database

router = APIRouter(prefix="/demo", tags=["Demo & Presentation"])


@router.post(
    "/seed",
    status_code=status.HTTP_200_OK,
    summary="Reset database and seed 5 benchmark showcase records for live demo",
)
async def seed_demo_mode(db: AsyncSession = Depends(get_db)):
    """
    Wipes the database and seeds 5 carefully crafted evaluation scenarios:
    1. **Jaipur Clean Khasra**: Verified, >90% confidence, compliant with DILRMP 2.0 and ULPIN.
    2. **Jodhpur Plot Deed**: Needs review, degraded historic scan with 3 flagged fields.
    3. **Jaipur Fraud Duplicate**: Needs review, 96% duplicate conflict triggering Fraud Shield.
    4. **Varanasi Hindi Record**: Verified, authentic Devanagari Hindi multilingual demonstration.
    5. **Sanganer In-Flight**: Processing, demonstrates live real-time SSE progress streaming.
    """
    result = await reset_and_seed_database(db)
    return result


@router.get(
    "/status",
    summary="Inspect current demo readiness and scenario roster",
)
async def get_demo_status(db: AsyncSession = Depends(get_db)):
    """
    Returns the count of active documents, users, and scenarios available
    for demonstration.
    """
    doc_count = (await db.execute(select(func.count(Document.id)))).scalar_one()
    user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    field_count = (await db.execute(select(func.count(ExtractedField.id)))).scalar_one()

    return {
        "is_ready": doc_count >= 3,
        "database_counts": {
            "documents": doc_count,
            "users": user_count,
            "extracted_fields": field_count,
        },
        "credentials": [
            {"username": "alice", "password": "Admin1234!", "role": "admin"},
            {"username": "bob", "password": "Verif5678!", "role": "verifier"},
            {"username": "carol", "password": "FieldOfficer123!", "role": "field_officer"},
        ],
        "scenarios_available": [
            {
                "filename": d["filename"],
                "title": d["scenario_title"],
                "target_status": d["status"].value,
            }
            for d in DEMO_DOCUMENTS
        ],
    }
