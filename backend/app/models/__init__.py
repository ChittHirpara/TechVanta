"""ORM models – import all here so Alembic autogenerate can see them."""
from app.models.user import User
from app.models.document import Document
from app.models.extracted_field import ExtractedField
from app.models.verifier_jurisdiction import VerifierJurisdiction
from app.models.verification_log import VerificationLog
from app.models.audit_trail import AuditTrail

__all__ = ["User", "Document", "ExtractedField", "VerificationLog", "AuditTrail", "VerifierJurisdiction"]
