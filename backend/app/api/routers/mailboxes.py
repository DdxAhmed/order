from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_db_session_commit, require_admin_roles
from app.audit import record
from app.config import get_settings
from app.mail import ImapMailProvider, MicrosoftGraphMailProvider
from app.mail.imap_provider import MailProviderError
from app.mail.microsoft import (
    build_authorization_url,
    microsoft_oauth_configured,
    pkce_challenge,
    pkce_verifier,
)
from app.models import (
    AdminRole,
    AdminSession,
    AdminUser,
    InventoryAccount,
    Mailbox,
    MailboxOAuthState,
)
from app.security import encrypt_secret, new_random_token, sha256, utcnow

router = APIRouter(prefix="/admin/mailboxes", tags=["Admin Mailboxes"])
settings = get_settings()


class MailboxCreateRequest(BaseModel):
    label: str
    host: str
    port: int = 993
    username: str
    password: str
    mail_folder: str = "INBOX"


class MailboxEditRequest(BaseModel):
    label: str
    host: str
    port: int = 993
    username: str
    password: Optional[str] = None
    purpose: str = "inventory"
    mail_folder: str = "INBOX"
    is_active: bool = True


class MailboxOAuthRequest(BaseModel):
    label: str
    username: str


@router.get("")
async def list_mailboxes(
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value, AdminRole.SUPPORT.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    items = (await session.scalars(select(Mailbox).order_by(Mailbox.label))).all()
    usage_rows = (
        await session.execute(
            select(InventoryAccount.mailbox_id, func.count()).group_by(InventoryAccount.mailbox_id)
        )
    ).all()
    usage_counts = {str(mid): cnt for mid, cnt in usage_rows if mid}

    mailboxes = [
        {
            "id": str(m.id),
            "label": m.label,
            "host": m.host,
            "port": m.port,
            "username": m.username,
            "auth_mode": m.auth_mode,
            "purpose": m.purpose,
            "mail_folder": m.mail_folder,
            "is_active": m.is_active,
            "last_checked_at": m.last_checked_at.isoformat() if m.last_checked_at else None,
            "last_error_code": m.last_error_code,
            "accounts_count": usage_counts.get(str(m.id), 0),
        }
        for m in items
    ]

    return {
        "mailboxes": mailboxes,
        "microsoft_oauth_configured": microsoft_oauth_configured(settings),
    }


@router.post("")
async def create_mailbox(
    payload: MailboxCreateRequest,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    clean_label = payload.label.strip()
    clean_host = payload.host.strip()
    clean_user = payload.username.strip()
    if not clean_label or not clean_host or not clean_user or not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="جميع حقول صندوق البريد مطلوبة")

    mailbox = Mailbox(
        label=clean_label,
        host=clean_host,
        port=payload.port,
        username=clean_user,
        mail_folder=payload.mail_folder.strip() or "INBOX",
        encrypted_password=encrypt_secret(payload.password),
        auth_mode="imap_password",
        is_active=True,
    )
    session.add(mailbox)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="اسم صندوق البريد مستخدم بالفعل",
        )

    await record(session, "mailbox.created", "mailbox", clean_label, actor_admin_id=admin.id)
    return {"status": "success", "id": str(mailbox.id), "message": "تمت إضافة صندوق البريد وتشفير بياناته بنجاح"}


@router.post("/{mailbox_id}/test")
async def test_mailbox(
    mailbox_id: uuid.UUID,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    mailbox = await session.scalar(select(Mailbox).where(Mailbox.id == mailbox_id).with_for_update())
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="صندوق البريد غير موجود")

    provider = MicrosoftGraphMailProvider(mailbox) if mailbox.auth_mode == "microsoft_graph" else ImapMailProvider(mailbox)
    try:
        await asyncio.to_thread(provider.recent_messages, utcnow() - timedelta(minutes=1), 1)
        if getattr(provider, "rotated_refresh_token", None):
            mailbox.oauth_refresh_token = encrypt_secret(provider.rotated_refresh_token)
        mailbox.last_checked_at = utcnow()
        mailbox.last_error_code = None
        await record(
            session,
            "mailbox.connection_tested",
            "mailbox",
            str(mailbox.id),
            actor_admin_id=admin.id,
            metadata={"provider": mailbox.auth_mode, "result": "ok"},
        )
        return {"status": "success", "connected": True, "message": "نجح اختبار الاتصال بصندوق البريد"}
    except MailProviderError as exc:
        mailbox.last_checked_at = utcnow()
        mailbox.last_error_code = "connection_test_failed"
        await record(
            session,
            "mailbox.connection_tested",
            "mailbox",
            str(mailbox.id),
            actor_admin_id=admin.id,
            metadata={"provider": mailbox.auth_mode, "result": "failed"},
        )
        return {
            "status": "error",
            "connected": False,
            "message": f"فشل اختبار الاتصال: {str(exc)}",
        }


@router.post("/{mailbox_id}/disable")
async def toggle_mailbox_active(
    mailbox_id: uuid.UUID,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    mailbox = await session.scalar(select(Mailbox).where(Mailbox.id == mailbox_id).with_for_update())
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="صندوق البريد غير موجود")

    mailbox.is_active = not mailbox.is_active
    await record(
        session,
        "mailbox.status_toggled",
        "mailbox",
        str(mailbox.id),
        actor_admin_id=admin.id,
        metadata={"is_active": mailbox.is_active},
    )
    return {
        "status": "success",
        "is_active": mailbox.is_active,
        "message": f"تم {'تفعيل' if mailbox.is_active else 'تعطيل'} صندوق البريد بنجاح",
    }


@router.delete("/{mailbox_id}")
async def delete_mailbox_endpoint(
    mailbox_id: uuid.UUID,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    mailbox = await session.scalar(select(Mailbox).where(Mailbox.id == mailbox_id).with_for_update())
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="صندوق البريد غير موجود")

    usage_count = await session.scalar(
        select(func.count()).select_from(InventoryAccount).where(InventoryAccount.mailbox_id == mailbox.id)
    )
    if usage_count and usage_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"لا يمكن حذف صندوق البريد لوجود {usage_count} حساب/حسابات مرتبطة به. عطل الصندوق بدلاً من حذفه.",
        )

    await session.delete(mailbox)
    await record(session, "mailbox.deleted", "mailbox", str(mailbox.id), actor_admin_id=admin.id)
    return {"status": "success", "message": "تم حذف صندوق البريد بنجاح"}
