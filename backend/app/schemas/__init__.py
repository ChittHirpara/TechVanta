"""Pydantic schemas package – re-exports everything for easy importing."""
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.schemas.document import DocumentCreate, DocumentRead, DocumentUpdate
from app.schemas.extracted_field import ExtractedFieldCreate, ExtractedFieldRead, ExtractedFieldUpdate
from app.schemas.verification_log import VerificationLogCreate, VerificationLogRead
from app.schemas.audit_trail import AuditTrailCreate, AuditTrailRead

__all__ = [
    "UserCreate", "UserRead", "UserUpdate",
    "DocumentCreate", "DocumentRead", "DocumentUpdate",
    "ExtractedFieldCreate", "ExtractedFieldRead", "ExtractedFieldUpdate",
    "VerificationLogCreate", "VerificationLogRead",
    "AuditTrailCreate", "AuditTrailRead",
]
