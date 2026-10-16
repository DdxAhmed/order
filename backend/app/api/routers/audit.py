from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_admin_roles
from app.models import AdminRole, AdminSession, AdminUser, AuditEvent, Platform
from app.platforms import SUPPORTED_PLATFORM_CODES

router = APIRouter(prefix="/admin/audit", tags=["Admin Audit"])


@router.get("")
async def get_audit_logs(
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value, AdminRole.SUPPORT.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    platform: str = Query("", description="Filter by platform code"),
):
    query = select(AuditEvent).order_by(AuditEvent.created_at.desc())

    selected_platform = platform.strip().casefold()
    if selected_platform in SUPPORTED_PLATFORM_CODES:
        query = query.where(
            AuditEvent.event_metadata["platform_code"].as_string() == selected_platform
        )

    events_raw = (await session.scalars(query.limit(200))).all()
    audit_platforms_raw = (
        await session.scalars(
            select(Platform).where(Platform.code.in_(SUPPORTED_PLATFORM_CODES)).order_by(Platform.name)
        )
    ).all()

    events = [
        {
            "id": str(ev.id),
            "action": ev.event_type,
            "target_type": ev.entity_type,
            "target_id": ev.entity_id,
            "actor_admin_id": str(ev.actor_admin_id) if ev.actor_admin_id else None,
            "actor_telegram_id": ev.actor_telegram_id,
            "metadata": ev.event_metadata,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        }
        for ev in events_raw
    ]

    return {
        "events": events,
        "platforms": [
            {"id": str(p.id), "code": p.code, "name": p.name} for p in audit_platforms_raw
        ],
    }
