"""AuditTrail schemas."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class _AuditTrailBase(BaseModel):
    action: str = Field(..., max_length=150)
    details: dict[str, Any] | None = None
    document_id: int | None = None


# ── Request schemas ───────────────────────────────────────────────────────────

class AuditTrailCreate(_AuditTrailBase):
    """user_id is injected from the auth token server-side."""
    pass


# ── Response schemas ──────────────────────────────────────────────────────────

class AuditTrailRead(_AuditTrailBase):
    id: int
    user_id: int | None
    timestamp: datetime

    model_config = {"from_attributes": True}
