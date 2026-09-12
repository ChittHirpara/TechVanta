"""Jurisdiction schemas."""
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.user import UserRole
from app.schemas.document import DocumentRead


class VerifierJurisdictionCreate(BaseModel):
    user_id: int = Field(..., description="ID of the verifier user")
    district: str = Field(..., min_length=1, max_length=150, description="District name")
    tehsil: str | None = Field(None, max_length=150, description="Optional Tehsil/Subdistrict name")
    village: str | None = Field(None, max_length=150, description="Optional Village name")


class VerifierJurisdictionRead(BaseModel):
    id: int
    user_id: int
    district: str
    tehsil: str | None = None
    village: str | None = None
    created_at: datetime
    verifier_username: str | None = None

    model_config = {"from_attributes": True}


class VerifierUserSummary(BaseModel):
    id: int
    username: str
    role: UserRole
    jurisdiction_count: int = 0

    model_config = {"from_attributes": True}


class EscalationsSummary(BaseModel):
    total_escalated: int
    sla_breached_count: int
    fraud_risk_count: int
    unassigned_count: int
    sla_breached_documents: list[DocumentRead] = []
    fraud_risk_documents: list[DocumentRead] = []
    unassigned_documents: list[DocumentRead] = []
