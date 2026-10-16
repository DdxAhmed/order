from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db_session
from app.models import (
    AdminSession,
    AdminUser,
    AuditEvent,
    Customer,
    InventoryAccount,
    Mailbox,
    Order,
    Platform,
    VerificationRequest,
)

router = APIRouter(prefix="/admin/dashboard", tags=["Admin Dashboard"])


@router.get("")
async def get_dashboard_stats(
    admin_and_session: Annotated[tuple[AdminUser, AdminSession], Depends(get_current_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    admin, _ = admin_and_session

    available = await session.scalar(
        select(func.count()).select_from(InventoryAccount).where(InventoryAccount.status == "available")
    ) or 0
    assigned = await session.scalar(
        select(func.count()).select_from(InventoryAccount).where(InventoryAccount.status == "assigned")
    ) or 0
    disabled = await session.scalar(
        select(func.count()).select_from(InventoryAccount).where(InventoryAccount.status == "disabled")
    ) or 0
    total_accounts = available + assigned + disabled

    orders_count = await session.scalar(select(func.count()).select_from(Order)) or 0
    customers_count = await session.scalar(select(func.count()).select_from(Customer)) or 0
    mailboxes_count = await session.scalar(
        select(func.count()).select_from(Mailbox).where(Mailbox.is_active.is_(True))
    ) or 0
    failed_requests = await session.scalar(
        select(func.count()).select_from(VerificationRequest).where(VerificationRequest.status == "failed")
    ) or 0

    steam = await session.scalar(select(Platform).where(Platform.code == "steam"))
    steam_status = "غير مهيأ"
    if steam:
        steam_status = (
            "جاهز للاختبار بعينة فعلية"
            if steam.is_enabled and steam.mail_profile.get("sample_verified_at")
            else "بانتظار عينة فعلية مصرح بها"
        )

    # Recent 5 audit events
    recent_events_raw = (
        await session.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(5))
    ).all()
    recent_events = [
        {
            "id": str(ev.id),
            "action": ev.event_type,
            "target_type": ev.entity_type,
            "target_id": ev.entity_id,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
            "metadata": ev.event_metadata,
        }
        for ev in recent_events_raw
    ]

    return {
        "counts": {
            "available_accounts": available,
            "assigned_accounts": assigned,
            "disabled_accounts": disabled,
            "total_accounts": total_accounts,
            "orders": orders_count,
            "customers": customers_count,
            "mailboxes": mailboxes_count,
            "failed_verifications": failed_requests,
        },
        "steam_status": steam_status,
        "recent_events": recent_events,
    }
