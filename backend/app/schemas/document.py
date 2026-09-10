"""Document schemas."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

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
    confidence_tier:  str = "medium"
    confidence_color: str = "yellow"

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def compute_tier(self) -> "ExtractedFieldRead":
        score = self.confidence_score if self.confidence_score is not None else 0.0
        if self.is_flagged or score < 0.70:
            self.confidence_tier = "low"
            self.confidence_color = "red"
        elif score >= 0.85:
            self.confidence_tier = "high"
            self.confidence_color = "green"
        else:
            self.confidence_tier = "medium"
            self.confidence_color = "yellow"
        return self


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
    has_suspected_duplicates: bool = False
    duplicate_count:          int = 0

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentRead):
    """Full document detail – includes extracted fields."""
    extracted_fields:    list[ExtractedFieldRead] = []
    top_duplicate_score: float | None = None


# ── Pagination wrapper ────────────────────────────────────────────────────────

class PaginatedDocuments(BaseModel):
    total:     int
    page:      int
    page_size: int
    items:     list[DocumentRead]
