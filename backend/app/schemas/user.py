"""User schemas."""
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.models.user import UserRole

# ── Shared ────────────────────────────────────────────────────────────────────

Username = Annotated[str, StringConstraints(min_length=3, max_length=100, strip_whitespace=True)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class _UserBase(BaseModel):
    username: Username
    role: UserRole = UserRole.field_officer


# ── Request schemas ───────────────────────────────────────────────────────────

class UserCreate(_UserBase):
    """Payload to register a new user."""
    password: Password


class UserUpdate(BaseModel):
    """All fields optional – send only what you want to change."""
    username: Username | None = None
    role: UserRole | None = None
    password: Password | None = None


# ── Response schemas ──────────────────────────────────────────────────────────

class UserRead(_UserBase):
    """Safe outbound representation – never includes password_hash."""
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
