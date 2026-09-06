"""Document model."""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class DocumentStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    needs_review = "needs_review"
    verified = "verified"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    uploaded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="documentstatus"),
        nullable=False,
        default=DocumentStatus.uploaded,
        index=True,
    )
    district: Mapped[str | None] = mapped_column(String(150), nullable=True)
    tehsil: Mapped[str | None] = mapped_column(String(150), nullable=True)
    village: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships (lazy="select" is the async-safe default with explicit loads)
    uploader = relationship("User", foreign_keys=[uploaded_by], lazy="select")
    extracted_fields = relationship(
        "ExtractedField", back_populates="document", cascade="all, delete-orphan", lazy="select"
    )
    verification_logs = relationship(
        "VerificationLog", back_populates="document", cascade="all, delete-orphan", lazy="select"
    )
    audit_trails = relationship(
        "AuditTrail", back_populates="document", cascade="all, delete-orphan", lazy="select"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Document id={self.id} filename={self.filename!r} status={self.status}>"
