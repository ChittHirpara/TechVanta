"""VerifierJurisdiction model."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class VerifierJurisdiction(Base):
    __tablename__ = "verifier_jurisdictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    district: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    tehsil: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    village: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id], lazy="select")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<VerifierJurisdiction id={self.id} user_id={self.user_id} district={self.district!r} tehsil={self.tehsil!r} village={self.village!r}>"
