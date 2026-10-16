from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_db_session_commit, require_admin_roles
from app.audit import record
from app.models import AdminRole, AdminSession, AdminUser, InventoryAccount, InventoryStatus, Mailbox, Platform
from app.platforms import INVENTORY_PLATFORM_CODES, SUPPORTED_PLATFORM_CODES, is_supported_platform
from app.security import encrypt_secret
from app.services.inventory import normalize_identifier

router = APIRouter(prefix="/admin/accounts", tags=["Admin Accounts"])


class AccountCreateRequest(BaseModel):
    platform_id: str
    mailbox_id: str
    identifier: str
    password: Optional[str] = None
    notes: Optional[str] = None


class AccountEditRequest(BaseModel):
    platform_id: str
    mailbox_id: str
    identifier: str
    status: Optional[str] = None
    notes: Optional[str] = None


class AccountStatusRequest(BaseModel):
    status: str


@router.get("")
async def list_accounts(
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value, AdminRole.SUPPORT.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    q: str = Query("", description="Search identifier"),
    status_filter: str = Query("", alias="status", description="Filter by status"),
    platform: str = Query("", description="Filter by platform code"),
):
    query = (
        select(InventoryAccount, Platform.name, Platform.code, Mailbox.label)
        .join(Platform, Platform.id == InventoryAccount.platform_id)
        .join(Mailbox, Mailbox.id == InventoryAccount.mailbox_id)
        .order_by(InventoryAccount.created_at.desc())
    )

    if q.strip():
        query = query.where(InventoryAccount.normalized_identifier.contains(normalize_identifier(q)))
    if status_filter in {item.value for item in InventoryStatus}:
        query = query.where(InventoryAccount.status == status_filter)

    selected_platform = platform.strip().casefold()
    if selected_platform in SUPPORTED_PLATFORM_CODES:
        query = query.where(Platform.code == selected_platform)

    rows = (await session.execute(query.limit(200))).all()

    platforms_raw = (
        await session.scalars(
            select(Platform).where(Platform.code.in_(INVENTORY_PLATFORM_CODES)).order_by(Platform.name)
        )
    ).all()
    platforms = [{"id": str(p.id), "code": p.code, "name": p.name} for p in platforms_raw]

    mailboxes_raw = (await session.scalars(select(Mailbox).where(Mailbox.is_active.is_(True)))).all()
    mailboxes = [{"id": str(m.id), "label": m.label, "auth_mode": m.auth_mode} for m in mailboxes_raw]

    accounts = [
        {
            "id": str(a.id),
            "identifier": a.identifier,
            "status": a.status,
            "platform_name": p_name,
            "platform_code": p_code,
            "platform_id": str(a.platform_id),
            "mailbox_id": str(a.mailbox_id),
            "mailbox_label": m_label,
            "notes": a.notes,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a, p_name, p_code, m_label in rows
    ]

    return {
        "accounts": accounts,
        "platforms": platforms,
        "mailboxes": mailboxes,
        "statuses": [item.value for item in InventoryStatus],
    }


@router.post("")
async def create_account(
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value})),
    ],
    payload: AccountCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    clean_identifier = payload.identifier.strip()
    if not clean_identifier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="معرف الحساب مطلوب")

    try:
        platform_uuid = uuid.UUID(payload.platform_id)
        mailbox_uuid = uuid.UUID(payload.mailbox_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="معرف المنصة أو البريد غير صالح")

    platform = await session.get(Platform, platform_uuid)
    mailbox = await session.get(Mailbox, mailbox_uuid)

    if not platform or not is_supported_platform(platform.code) or not mailbox:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="المنصة أو صندوق البريد غير صالح")

    secret_encrypted = encrypt_secret(payload.password) if payload.password else None
    account = InventoryAccount(
        platform_id=platform.id,
        mailbox_id=mailbox.id,
        identifier=clean_identifier,
        normalized_identifier=normalize_identifier(clean_identifier),
        secret_encrypted=secret_encrypted,
        status=InventoryStatus.AVAILABLE.value,
        notes=payload.notes.strip() if payload.notes else None,
    )
    session.add(account)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="المعرف مستخدم بالفعل لهذه المنصة",
        )

    await record(
        session,
        "inventory.account_created",
        "inventory_account",
        str(account.id),
        actor_admin_id=admin.id,
        metadata={"platform_code": platform.code},
    )

    return {"status": "success", "id": str(account.id), "message": "تمت إضافة الحساب بنجاح"}


@router.get("/{account_id}")
async def get_account(
    account_id: uuid.UUID,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value, AdminRole.SUPPORT.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    account = await session.get(InventoryAccount, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الحساب غير موجود")

    platform = await session.get(Platform, account.platform_id)
    mailbox = await session.get(Mailbox, account.mailbox_id)

    return {
        "id": str(account.id),
        "identifier": account.identifier,
        "status": account.status,
        "platform_id": str(account.platform_id),
        "platform_name": platform.name if platform else "",
        "platform_code": platform.code if platform else "",
        "mailbox_id": str(account.mailbox_id),
        "mailbox_label": mailbox.label if mailbox else "",
        "notes": account.notes,
        "created_at": account.created_at.isoformat() if account.created_at else None,
    }


@router.post("/{account_id}/edit")
@router.put("/{account_id}")
async def update_account(
    account_id: uuid.UUID,
    payload: AccountEditRequest,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    clean_identifier = payload.identifier.strip()
    if not clean_identifier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="معرف الحساب مطلوب")

    account = await session.scalar(
        select(InventoryAccount).where(InventoryAccount.id == account_id).with_for_update()
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الحساب غير موجود")

    try:
        platform_uuid = uuid.UUID(payload.platform_id)
        mailbox_uuid = uuid.UUID(payload.mailbox_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="معرف المنصة أو البريد غير صالح")

    platform = await session.get(Platform, platform_uuid)
    mailbox = await session.get(Mailbox, mailbox_uuid)

    is_legacy = bool(account and platform and platform.id == account.platform_id and platform.code == "playstation")
    if not platform or (not is_supported_platform(platform.code) and not is_legacy) or not mailbox:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="المنصة أو صندوق البريد غير صالح")

    if account.status == InventoryStatus.ASSIGNED.value and platform.id != account.platform_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="لا يمكن تغيير منصة حساب مخصص")

    editable_statuses = {
        InventoryStatus.AVAILABLE.value,
        InventoryStatus.RESERVED.value,
        InventoryStatus.DISABLED.value,
        InventoryStatus.ARCHIVED.value,
    }

    if account.status == InventoryStatus.ASSIGNED.value:
        if payload.status not in {None, "", InventoryStatus.ASSIGNED.value}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="لا يمكن تغيير حالة حساب مخصص مباشرة، استخدم إعادة التخصيص",
            )
    elif payload.status and payload.status not in editable_statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="حالة الحساب غير صالحة")

    account.platform_id = platform.id
    account.identifier = clean_identifier
    account.normalized_identifier = normalize_identifier(clean_identifier)
    account.mailbox_id = mailbox_uuid
    if account.status != InventoryStatus.ASSIGNED.value and payload.status:
        account.status = payload.status
    account.notes = payload.notes.strip() if payload.notes else None

    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="المعرف مستخدم بالفعل لهذه المنصة",
        )

    await record(
        session,
        "inventory.account_edited",
        "inventory_account",
        str(account.id),
        actor_admin_id=admin.id,
        metadata={"platform_code": platform.code, "status": account.status},
    )

    return {"status": "success", "message": "تم تعديل الحساب بنجاح"}


@router.post("/{account_id}/status")
async def change_status(
    account_id: uuid.UUID,
    payload: AccountStatusRequest,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    allowed = {InventoryStatus.AVAILABLE.value, InventoryStatus.DISABLED.value, InventoryStatus.ARCHIVED.value}
    if payload.status not in allowed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="الحالة المطلوبة غير صالحة")

    account = await session.scalar(
        select(InventoryAccount).where(InventoryAccount.id == account_id).with_for_update()
    )
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الحساب غير موجود")
    if account.status == InventoryStatus.ASSIGNED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لا يمكن تغيير حالة حساب مخصص مباشرة",
        )

    account.status = payload.status
    await record(
        session,
        "inventory.status_changed",
        "inventory_account",
        str(account.id),
        actor_admin_id=admin.id,
        metadata={"status": account.status},
    )

    return {"status": "success", "new_status": account.status, "message": "تم تغيير حالة الحساب بنجاح"}
