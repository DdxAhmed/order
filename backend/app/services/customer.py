from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record
from app.models import (
    AccountAssignment,
    ActivationToken,
    Customer,
    CustomerSession,
    InventoryAccount,
    Order,
    OrderStatus,
    Platform,
    VerificationRequest,
)
from app.security import (
    code_hash,
    customer_session_expiry,
    decrypt_secret,
    make_csrf_token,
    mask_account_identifier,
    new_random_token,
    sha256,
    utcnow,
)
from app.services.inventory import normalize_identifier


class CustomerAccessError(ValueError):
    pass


async def activate_order(session: AsyncSession, raw_token: str, telegram_user_id: int) -> list[AccountAssignment]:
    token = await session.scalar(
        select(ActivationToken).where(ActivationToken.token_hash == code_hash(raw_token)).with_for_update()
    )
    if not token or token.used_at or token.revoked_at or token.expires_at <= utcnow():
        raise CustomerAccessError("رمز التفعيل غير صالح أو منتهٍ")
    order = await session.scalar(select(Order).where(Order.id == token.order_id).with_for_update())
    if not order or order.status == OrderStatus.CANCELLED.value:
        raise CustomerAccessError("لا يمكن تفعيل هذا الطلب")
    customer = await session.scalar(select(Customer).where(Customer.id == order.customer_id).with_for_update())
    if not customer:
        raise CustomerAccessError("لا يمكن تفعيل هذا الطلب")
    if customer.telegram_user_id is not None and customer.telegram_user_id != telegram_user_id:
        raise CustomerAccessError("لا يمكن تفعيل هذا الطلب")
    customer.telegram_user_id = telegram_user_id
    token.used_at = utcnow()
    order.status = OrderStatus.ACTIVATED.value
    assignments = (
        await session.scalars(
            select(AccountAssignment).where(
                AccountAssignment.order_id == order.id, AccountAssignment.revoked_at.is_(None)
            )
        )
    ).all()
    await record(
        session,
        "order.activated",
        "order",
        str(order.id),
        actor_telegram_id=telegram_user_id,
    )
    return list(assignments)


async def activate_order_for_web(session: AsyncSession, raw_token: str) -> tuple[str, CustomerSession]:
    """Consume an activation token and issue a short-lived browser session."""
    token = await session.scalar(
        select(ActivationToken).where(ActivationToken.token_hash == code_hash(raw_token)).with_for_update()
    )
    if not token or token.used_at or token.revoked_at or token.expires_at <= utcnow():
        raise CustomerAccessError("رمز التفعيل غير صالح أو منتهٍ")
    order = await session.scalar(select(Order).where(Order.id == token.order_id).with_for_update())
    if not order or order.status == OrderStatus.CANCELLED.value:
        raise CustomerAccessError("لا يمكن تفعيل هذا الطلب")
    customer = await session.scalar(select(Customer).where(Customer.id == order.customer_id).with_for_update())
    if not customer:
        raise CustomerAccessError("لا يمكن تفعيل هذا الطلب")
    raw_session = new_random_token()
    customer_session = CustomerSession(
        customer_id=customer.id,
        token_hash=sha256(raw_session),
        csrf_token=make_csrf_token(),
        expires_at=customer_session_expiry(),
    )
    session.add(customer_session)
    await session.flush()
    token.used_at = utcnow()
    order.status = OrderStatus.ACTIVATED.value
    await record(session, "order.activated.web", "order", str(order.id))
    return raw_session, customer_session


async def access_order_for_web(
    session: AsyncSession,
    *,
    external_reference: str,
    account_identifier: str,
    platform_code: str,
) -> tuple[str, CustomerSession]:
    """Issue a short-lived web session from the shared order access form.

    The order reference and the exact assigned platform identifier must match in
    the same transaction. A generic error is raised for every mismatch so the
    public form cannot be used to enumerate orders or usernames.
    """
    reference = external_reference.strip()
    normalized_identifier = normalize_identifier(account_identifier)
    platform = platform_code.strip().casefold()
    if not reference or not normalized_identifier or not platform:
        raise CustomerAccessError("بيانات الدخول غير صحيحة")
    order = await session.scalar(
        select(Order)
        .where(Order.external_reference == reference)
        .with_for_update()
    )
    assignment = None
    if order and order.status != OrderStatus.CANCELLED.value:
        assignment = await session.scalar(
            select(AccountAssignment)
            .join(InventoryAccount, InventoryAccount.id == AccountAssignment.account_id)
            .join(Platform, Platform.id == InventoryAccount.platform_id)
            .where(
                AccountAssignment.order_id == order.id,
                AccountAssignment.revoked_at.is_(None),
                InventoryAccount.normalized_identifier == normalized_identifier,
                Platform.code == platform,
            )
        )
    if not order or not assignment:
        raise CustomerAccessError("بيانات الدخول غير صحيحة")
    customer = await session.scalar(select(Customer).where(Customer.id == order.customer_id).with_for_update())
    if not customer:
        raise CustomerAccessError("بيانات الدخول غير صحيحة")
    raw_session = new_random_token()
    customer_session = CustomerSession(
        customer_id=customer.id,
        token_hash=sha256(raw_session),
        csrf_token=make_csrf_token(),
        expires_at=customer_session_expiry(),
    )
    session.add(customer_session)
    await session.flush()
    order.status = OrderStatus.ACTIVATED.value
    await record(session, "order.activated.web_identity", "order", str(order.id))
    return raw_session, customer_session


async def get_customer_web_session(
    session: AsyncSession, raw_token: str | None
) -> tuple[Customer, CustomerSession] | None:
    if not raw_token:
        return None
    result = await session.execute(
        select(Customer, CustomerSession)
        .join(CustomerSession, CustomerSession.customer_id == Customer.id)
        .where(
            CustomerSession.token_hash == sha256(raw_token),
            CustomerSession.revoked_at.is_(None),
            CustomerSession.expires_at > utcnow(),
        )
    )
    found = result.one_or_none()
    if found:
        found[1].last_seen_at = utcnow()
    return found


async def assignments_for_telegram(session: AsyncSession, telegram_user_id: int) -> list[tuple[AccountAssignment, InventoryAccount]]:
    return list(
        (
            await session.execute(
                select(AccountAssignment, InventoryAccount)
                .join(InventoryAccount, InventoryAccount.id == AccountAssignment.account_id)
                .join(Order, Order.id == AccountAssignment.order_id)
                .join(Customer, Customer.id == Order.customer_id)
                .where(
                    Customer.telegram_user_id == telegram_user_id,
                    AccountAssignment.revoked_at.is_(None),
                    Order.status == OrderStatus.ACTIVATED.value,
                )
                .order_by(AccountAssignment.created_at.desc())
            )
        ).all()
    )


async def assignments_for_web(
    session: AsyncSession, customer_id: uuid.UUID
) -> list[tuple[AccountAssignment, InventoryAccount]]:
    return list(
        (
            await session.execute(
                select(AccountAssignment, InventoryAccount)
                .join(InventoryAccount, InventoryAccount.id == AccountAssignment.account_id)
                .join(Order, Order.id == AccountAssignment.order_id)
                .where(
                    AccountAssignment.customer_id == customer_id,
                    AccountAssignment.revoked_at.is_(None),
                    Order.status == OrderStatus.ACTIVATED.value,
                )
                .order_by(AccountAssignment.created_at.desc())
            )
        ).all()
    )


async def result_for_customer(
    session: AsyncSession, verification_request_id: uuid.UUID, telegram_user_id: int
) -> tuple[str, str] | None:
    result = await session.execute(
        select(VerificationRequest, InventoryAccount)
        .join(AccountAssignment, AccountAssignment.id == VerificationRequest.assignment_id)
        .join(InventoryAccount, InventoryAccount.id == AccountAssignment.account_id)
        .join(Order, Order.id == AccountAssignment.order_id)
        .join(Customer, Customer.id == Order.customer_id)
        .where(
            VerificationRequest.id == verification_request_id,
            VerificationRequest.requested_by_telegram_id == telegram_user_id,
            Customer.telegram_user_id == telegram_user_id,
            AccountAssignment.revoked_at.is_(None),
        )
    )
    row = result.one_or_none()
    if not row:
        return None
    request, account = row
    if not request.result_ciphertext or not request.result_expires_at or request.result_expires_at <= utcnow():
        return None
    return mask_account_identifier(account.identifier), decrypt_secret(request.result_ciphertext)


async def result_for_web(
    session: AsyncSession, verification_request_id: uuid.UUID, customer_session_id: uuid.UUID
) -> tuple[str, str] | None:
    result = await session.execute(
        select(VerificationRequest, InventoryAccount)
        .join(AccountAssignment, AccountAssignment.id == VerificationRequest.assignment_id)
        .join(InventoryAccount, InventoryAccount.id == AccountAssignment.account_id)
        .join(Order, Order.id == AccountAssignment.order_id)
        .join(CustomerSession, CustomerSession.customer_id == Order.customer_id)
        .where(
            VerificationRequest.id == verification_request_id,
            VerificationRequest.requested_by_web_session_id == customer_session_id,
            CustomerSession.id == customer_session_id,
            CustomerSession.revoked_at.is_(None),
            CustomerSession.expires_at > utcnow(),
            AccountAssignment.revoked_at.is_(None),
        )
    )
    row = result.one_or_none()
    if not row:
        return None
    request, account = row
    if not request.result_ciphertext or not request.result_expires_at or request.result_expires_at <= utcnow():
        return None
    return mask_account_identifier(account.identifier), decrypt_secret(request.result_ciphertext)


async def verification_statuses_for_web(
    session: AsyncSession, customer_session_id: uuid.UUID
) -> list[VerificationRequest]:
    return list(
        (
            await session.scalars(
                select(VerificationRequest)
                .join(AccountAssignment, AccountAssignment.id == VerificationRequest.assignment_id)
                .join(Order, Order.id == AccountAssignment.order_id)
                .where(
                    VerificationRequest.requested_by_web_session_id == customer_session_id,
                    AccountAssignment.revoked_at.is_(None),
                )
                .order_by(VerificationRequest.created_at.desc())
                .limit(20)
            )
        ).all()
    )


async def verification_statuses_for_telegram(
    session: AsyncSession, telegram_user_id: int
) -> list[VerificationRequest]:
    return list(
        (
            await session.scalars(
                select(VerificationRequest)
                .join(AccountAssignment, AccountAssignment.id == VerificationRequest.assignment_id)
                .join(Order, Order.id == AccountAssignment.order_id)
                .join(Customer, Customer.id == Order.customer_id)
                .where(
                    Customer.telegram_user_id == telegram_user_id,
                    AccountAssignment.revoked_at.is_(None),
                    VerificationRequest.requested_by_telegram_id == telegram_user_id,
                )
                .order_by(VerificationRequest.created_at.desc())
                .limit(10)
            )
        ).all()
    )
