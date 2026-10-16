"""Read-only Salla notification ingestion and local entitlement verification."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import re
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.salla_notifications import SallaNotificationError, parse_salla_order_notification
from app.audit import record
from app.mail import ImapMailProvider, MicrosoftGraphMailProvider
from app.mail.imap_provider import ParsedMailMessage
from app.models import Mailbox, SallaAccessSession, SallaNotificationClaim, SallaOrderVerification
from app.security import encrypt_secret, new_random_token, sha256, utcnow


class SallaNotificationVerificationError(ValueError):
    pass


def _subject_search_term(patterns: list[str]) -> str | None:
    """Return a literal term suitable for Graph's server-side subject filter."""
    for pattern in patterns:
        terms = re.findall(r"[\w\u0600-\u06ff]{3,}", pattern, re.UNICODE)
        if terms:
            return terms[0]
    return None


def normalize_account_alias(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _mailbox_source_id(mailbox_id: uuid.UUID) -> int:
    """Stable positive bigint namespace for email-only entitlements."""
    return int(sha256(f"salla-email:{mailbox_id}")[:15], 16)


async def ingest_salla_notification_message(
    session: AsyncSession,
    *,
    mailbox: Mailbox,
    message: ParsedMailMessage,
) -> str:
    notification = parse_salla_order_notification(
        message,
        allowed_sender_domains=list(mailbox.notification_sender_domains or []),
        subject_patterns=list(mailbox.notification_subject_patterns or []),
    )
    event_key = sha256(f"{mailbox.id}:{notification.order_reference}:{notification.status}")
    claim = SallaNotificationClaim(
        mailbox_id=mailbox.id,
        external_message_id=notification.external_message_id,
        order_reference=notification.order_reference,
        status=notification.status,
        event_key=event_key,
        message_date=message.message_date,
    )
    try:
        async with session.begin_nested():
            session.add(claim)
            await session.flush()
    except IntegrityError:
        return "duplicate"

    now = utcnow()
    entitlement = await session.scalar(
        select(SallaOrderVerification)
        .where(
            SallaOrderVerification.source == "salla_email",
            SallaOrderVerification.notification_mailbox_id == mailbox.id,
            SallaOrderVerification.reference_id == notification.order_reference,
        )
        .with_for_update()
    )
    username_hash = sha256(normalize_account_alias(notification.requested_username)) if notification.requested_username else None
    customer_hash = sha256(notification.customer_identifier.casefold()) if notification.customer_identifier else None
    values = {
        "external_message_id": notification.external_message_id,
        "product_id": notification.product_id,
        "sku": notification.sku,
        "product_name": notification.product_name,
        "quantity": notification.quantity,
        "customer_identifier_hash": customer_hash,
        "requested_username_hash": username_hash,
        "ownership_method": notification.ownership_method,
        "status_slug": notification.status,
        "payment_eligible": notification.eligible,
        "revoked_at": None if notification.eligible else now,
        "expires_at": now + timedelta(hours=24),
    }
    if not entitlement:
        entitlement = SallaOrderVerification(
            source="salla_email",
            notification_mailbox_id=mailbox.id,
            merchant_id=_mailbox_source_id(mailbox.id),
            salla_order_id=None,
            reference_id=notification.order_reference,
            purchaser_email_hash=None,
            service_keys=[],
            **values,
        )
        session.add(entitlement)
    else:
        for key, value in values.items():
            setattr(entitlement, key, value)
    await record(
        session,
        "salla_notification.entitlement_updated",
        "salla_order_verification",
        str(entitlement.id),
        metadata={
            "source": "salla_email",
            "status": notification.status,
            "eligible": notification.eligible,
            "reference_hash": sha256(notification.order_reference),
            "has_requested_username": bool(username_hash),
        },
    )
    return "imported"


async def ingest_salla_notification_mailbox(session: AsyncSession, mailbox: Mailbox) -> dict[str, int]:
    """Fetch only configured notification mailboxes; raw emails are never kept."""
    if not mailbox.is_active or mailbox.purpose != "salla_notifications":
        return {"imported": 0, "duplicate": 0, "rejected": 0}
    since = mailbox.notification_last_scanned_at or (utcnow() - timedelta(days=7))
    provider = MicrosoftGraphMailProvider(mailbox) if mailbox.auth_mode == "microsoft_graph" else ImapMailProvider(mailbox)
    try:
        subject_term = _subject_search_term(list(mailbox.notification_subject_patterns or []))
        if isinstance(provider, MicrosoftGraphMailProvider):
            messages = await asyncio.to_thread(provider.recent_messages, since, 50, subject_contains=subject_term)
        else:
            messages = await asyncio.to_thread(provider.recent_messages, since, 50)
        if getattr(provider, "rotated_refresh_token", None):
            mailbox.oauth_refresh_token = encrypt_secret(provider.rotated_refresh_token)
    except Exception:
        mailbox.notification_last_error_code = "notification_mailbox_unavailable"
        raise
    result = {"imported": 0, "duplicate": 0, "rejected": 0}
    for message in messages:
        try:
            outcome = await ingest_salla_notification_message(session, mailbox=mailbox, message=message)
            result[outcome] += 1
        except SallaNotificationError:
            result["rejected"] += 1
    mailbox.notification_last_scanned_at = utcnow()
    mailbox.notification_last_error_code = None
    return result


async def verify_salla_email_entitlement(
    session: AsyncSession,
    *,
    order_reference: str,
    account_alias: str,
) -> tuple[str, SallaOrderVerification]:
    reference = order_reference.strip().lstrip("#")
    alias = normalize_account_alias(account_alias)
    if not reference or not alias:
        raise SallaNotificationVerificationError("بيانات التحقق غير مكتملة")
    rows = (
        await session.scalars(
            select(SallaOrderVerification)
            .where(
                SallaOrderVerification.source == "salla_email",
                SallaOrderVerification.reference_id == reference,
            )
            .order_by(SallaOrderVerification.updated_at.desc())
        )
    ).all()
    if not rows:
        raise SallaNotificationVerificationError("تعذر التحقق من بيانات الطلب")
    if len(rows) > 1:
        raise SallaNotificationVerificationError("تعذر التحقق من بيانات الطلب")
    entitlement = rows[0]
    if not entitlement.requested_username_hash:
        raise SallaNotificationVerificationError("تعذر التحقق من بيانات الطلب")
    if entitlement.requested_username_hash != sha256(alias):
        raise SallaNotificationVerificationError("تعذر التحقق من بيانات الطلب")
    # Once the caller has proven the alias captured in the merchant's own
    # notification, it is safe and useful to distinguish an ineligible order
    # from an unknown one. Before that match every failure remains generic.
    if not entitlement.payment_eligible or entitlement.revoked_at:
        raise SallaNotificationVerificationError("الطلب غير مؤهل أو غير مدفوع")
    entitlement.expires_at = utcnow() + timedelta(hours=1)
    raw_token = new_random_token(32)
    session.add(
        SallaAccessSession(
            verification_id=entitlement.id,
            token_hash=sha256(raw_token),
            csrf_token=new_random_token(24),
            expires_at=entitlement.expires_at,
        )
    )
    return raw_token, entitlement
