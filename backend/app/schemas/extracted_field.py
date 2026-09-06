"""ExtractedField schemas."""
from datetime import datetime

from pydantic import BaseModel, Field


class _ExtractedFieldBase(BaseModel):
    field_name: str = Field(..., max_length=150)
    value: str | None = None
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)
    is_flagged: bool = False


# ── Request schemas ───────────────────────────────────────────────────────────

class ExtractedFieldCreate(_ExtractedFieldBase):
    document_id: int


class ExtractedFieldUpdate(BaseModel):
    value: str | None = None
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)
    is_flagged: bool | None = None


# ── Response schemas ──────────────────────────────────────────────────────────

class ExtractedFieldRead(_ExtractedFieldBase):
    id: int
    document_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
