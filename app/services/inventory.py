from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record
from app.models import (
    AccountAssignment,
    ActivationToken,
    InventoryAccount,
    InventoryStatus,
    Order,
    OrderStatus,
    Platform,
    VerificationRequest,
    VerificationStatus,
    WorkerJob,
)
from app.security import activation_expiry, code_hash, new_random_token, utcnow


def normalize_identifier(identifier: str) -> str:
    return " ".join(identifier.strip().casefold().split())


async def assign_account(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    order_id: uuid.UUID,
    actor_admin_id: uuid.UUID,
    reassign_reason: str | None = None,
) -> AccountAssignment:
    account = await session.scalar(select(InventoryAccount).where(InventoryAccount.id == account_id).with_for_update())
    order = await session.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if not account or not order:
        raise ValueError("الحساب أو الطلب غير موجود")
    if account.status not in {InventoryStatus.AVAILABLE.value, InventoryStatus.ASSIGNED.value}:
        raise ValueError("الحساب غير متاح للتخصيص")
    current = await session.scalar(
        select(AccountAssignment)
        .where(AccountAssignment.account_id == account_id, AccountAssignment.revoked_at.is_(None))
        .with_for_update()
    )
    if current:
        if not reassign_reason:
            raise ValueError("الحساب مخصص بالفعل؛ أدخل سبب إعادة التخصيص")
        current.revoked_at = utcnow()
        current.revoke_reason = reassign_reason[:250]
        await session.execute(
            select(ActivationToken).where(ActivationToken.order_id == current.order_id).with_for_update()
        )
        for token in (await session.scalars(select(ActivationToken).where(ActivationToken.order_id == current.order_id))).all():
            token.revoked_at = utcnow()
        for request in (
            await session.scalars(
                select(VerificationRequest).where(
                    VerificationRequest.assignment_id == current.id,
                    VerificationRequest.status.in_(
                        ["queued", "processing", "waiting_mail", "delivery_uncertain"]
                    ),
                )
            )
        ).all():
            request.status = VerificationStatus.CANCELLED.value
    existing_order_assignment = await session.scalar(
        select(AccountAssignment)
        .where(AccountAssignment.order_id == order_id, AccountAssignment.revoked_at.is_(None))
        .with_for_update()
    )
    if existing_order_assignment:
        raise ValueError("للطلب حساب مخصص بالفعل")
    assignment = AccountAssignment(
        account_id=account.id,
        order_id=order.id,
        customer_id=order.customer_id,
        assigned_by_admin_id=actor_admin_id,
    )
    session.add(assignment)
    await session.flush()
    account.status = InventoryStatus.ASSIGNED.value
    order.status = OrderStatus.ASSIGNED.value
    platform = await session.get(Platform, account.platform_id)
    await record(
        session,
        "inventory.account_assigned",
        "account_assignment",
        str(assignment.id),
        actor_admin_id=actor_admin_id,
        metadata={
            "account_id": str(account.id),
            "order_id": str(order.id),
            "reassigned": bool(current),
            "platform_code": platform.code if platform else None,
            "platform_name": platform.name if platform else None,
        },
    )
    return assignment


async def create_activation_token(
    session: AsyncSession, order: Order, actor_admin_id: uuid.UUID
) -> str:
    raw_token = new_random_token(32)
    session.add(ActivationToken(token_hash=code_hash(raw_token), order_id=order.id, expires_at=activation_expiry()))
    await record(
        session,
        "order.activation_issued",
        "order",
        str(order.id),
        actor_admin_id=actor_admin_id,
        metadata={"expires_at": activation_expiry().isoformat()},
    )
    return raw_token


async def create_verification_request(
    session: AsyncSession,
    assignment: AccountAssignment,
    wait_seconds: int,
    *,
    telegram_user_id: int | None = None,
    web_session_id: uuid.UUID | None = None,
) -> VerificationRequest:
    if (telegram_user_id is None) == (web_session_id is None):
        raise ValueError("يجب تحديد جلسة العميل")
    active = await session.scalar(
        select(VerificationRequest)
        .where(
            VerificationRequest.assignment_id == assignment.id,
            VerificationRequest.status.in_(["queued", "processing", "waiting_mail", "delivery_uncertain"]),
        )
        .with_for_update()
    )
    if active:
        return active
    request = VerificationRequest(
        assignment_id=assignment.id,
        requested_by_telegram_id=telegram_user_id,
        requested_by_web_session_id=web_session_id,
        expires_at=utcnow() + timedelta(seconds=wait_seconds),
    )
    session.add(request)
    await session.flush()
    session.add(
        WorkerJob(
            kind="fetch_verification_code",
            idempotency_key=str(request.id),
            payload={"verification_request_id": str(request.id)},
        )
    )
    await record(
        session,
        "verification.requested",
        "verification_request",
        str(request.id),
        actor_telegram_id=telegram_user_id,
    )
    return request
