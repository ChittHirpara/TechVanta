"""Centralized audit logging service."""
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_trail import AuditTrail

logger = logging.getLogger(__name__)


async def write_audit(
    db: AsyncSession,
    action: str,
    *,
    document_id: int | None = None,
    user_id: int | None = None,
    details: dict[str, Any] | None = None,
    flush: bool = False,
) -> AuditTrail:
    """Append a row to audit_trails."""
    entry = AuditTrail(
        document_id=document_id,
        user_id=user_id,
        action=action,
        details=details or {},
    )
    db.add(entry)
    if flush:
        try:
            await db.flush()
        except Exception as exc:  # pragma: no cover
            logger.warning("[audit_service] AuditTrail flush failed: %s", exc)
    return entry
