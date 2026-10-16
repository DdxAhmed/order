from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent

_SENSITIVE = {"password", "token", "code", "secret", "ciphertext", "authorization", "email_body"}


def redact(value: Any, key: str = "") -> Any:
    if any(fragment in key.lower() for fragment in _SENSITIVE):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


async def record(
    session: AsyncSession,
    event_type: str,
    entity_type: str,
    entity_id: str,
    *,
    actor_admin_id: object | None = None,
    actor_telegram_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor_admin_id=actor_admin_id,
            actor_telegram_id=actor_telegram_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            event_metadata=redact(metadata or {}),
        )
    )
