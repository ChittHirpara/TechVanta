"""Document schemas."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.document import DocumentStatus


# ── Shared base ───────────────────────────────────────────────────────────────

class _DocumentBase(BaseModel):
    filename: str = Field(..., max_length=255)
    district: str | None = Field(None, max_length=150)
    tehsil:   str | None = Field(None, max_length=150)
    village:  str | None = Field(None, max_length=150)


# ── Request schemas ───────────────────────────────────────────────────────────

class DocumentCreate(_DocumentBase):
    """Used when uploading a new document (storage_path set server-side)."""
    storage_path: str = Field(..., max_length=512)


class DocumentUpdate(BaseModel):
    """Patch endpoint payload – all optional."""
    status:   DocumentStatus | None = None
    district: str | None = Field(None, max_length=150)
    tehsil:   str | None = Field(None, max_length=150)
    village:  str | None = Field(None, max_length=150)


# ── Extracted field ───────────────────────────────────────────────────────────

class ExtractedFieldRead(BaseModel):
    id:               int
    field_name:       str
    value:            str | None
    confidence_score: float | None
    is_flagged:       bool
    created_at:       datetime

    model_config = {"from_attributes": True}


class FieldPatchRequest(BaseModel):
    """Body for PATCH /documents/{id}/fields/{field_name}."""
    value: str = Field(..., min_length=1, description="Corrected field value")
    note:  str | None = Field(None, description="Optional verifier note for the audit log")


# ── Response schemas ──────────────────────────────────────────────────────────

class DocumentRead(_DocumentBase):
    """Flat document metadata – used in list responses."""
    id:          int
    storage_path: str
    uploaded_by:  int | None
    status:       DocumentStatus
    created_at:   datetime
    updated_at:   datetime

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentRead):
    """Full document detail – includes extracted fields."""
    extracted_fields: list[ExtractedFieldRead] = []


# ── Pagination wrapper ────────────────────────────────────────────────────────

class PaginatedDocuments(BaseModel):
    total:     int
    page:      int
    page_size: int
    items:     list[DocumentRead]
