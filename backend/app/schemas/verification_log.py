"""VerificationLog schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class _VerificationLogBase(BaseModel):
    document_id: int
    field_name: str = Field(..., max_length=150)
    old_value: str | None = None
    new_value: str | None = None


# ── Request schemas ───────────────────────────────────────────────────────────

class VerificationLogCreate(_VerificationLogBase):
    """verifier_id is injected from the auth token server-side."""
    pass


# ── Response schemas ──────────────────────────────────────────────────────────

class VerificationLogRead(_VerificationLogBase):
    id: int
    verifier_id: int | None
    timestamp: datetime

    model_config = {"from_attributes": True}
