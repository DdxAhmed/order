from __future__ import annotations

import asyncio
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record
from app.config import get_settings
from app.mail import ImapMailProvider, MicrosoftGraphMailProvider
from app.models import (
    AccountAssignment,
    InventoryAccount,
    MailMessageClaim,
    Mailbox,
    Platform,
    VerificationRequest,
    VerificationStatus,
    WorkerJob,
)
from app.platforms import SteamMailAdapter
from app.security import code_hash, encrypt_secret, utcnow


async def acquire_request(session: AsyncSession, request_id: uuid.UUID) -> VerificationRequest | None:
    request = await session.scalar(
        select(VerificationRequest).where(VerificationRequest.id == request_id).with_for_update(skip_locked=True)
    )
    if not request or request.status in {"succeeded", "cancelled", "expired", "failed"}:
        return None
    if request.expires_at <= utcnow():
        request.status = VerificationStatus.EXPIRED.value
        return None
    request.status = VerificationStatus.PROCESSING.value
    request.lease_expires_at = utcnow() + timedelta(seconds=30)
    return request


async def fetch_code(session: AsyncSession, request_id: uuid.UUID) -> str:
    request = await acquire_request(session, request_id)
    if not request:
        return "done"
    assignment = await session.get(AccountAssignment, request.assignment_id)
    if not assignment or assignment.revoked_at is not None:
        request.status = VerificationStatus.CANCELLED.value
        return "done"
    account = await session.get(InventoryAccount, assignment.account_id)
    if not account:
        request.status = VerificationStatus.FAILED.value
        request.failure_code = "account_missing"
        return "done"
    platform = await session.get(Platform, account.platform_id)
    mailbox = await session.get(Mailbox, account.mailbox_id)
    if not platform or platform.code != "steam" or not platform.is_enabled:
        request.status = VerificationStatus.FAILED.value
        request.failure_code = "platform_not_ready"
        return "done"
    adapter = SteamMailAdapter(platform.mail_profile)
    if not adapter.configured or not mailbox or not mailbox.is_active:
        request.status = VerificationStatus.FAILED.value
        request.failure_code = "mail_profile_not_verified"
        return "done"
    try:
        provider = (
            MicrosoftGraphMailProvider(mailbox)
            if mailbox.auth_mode == "microsoft_graph"
            else ImapMailProvider(mailbox)
        )
        messages = await asyncio.to_thread(
            provider.recent_messages,
            request.created_at - timedelta(seconds=60),
        )
        if getattr(provider, "rotated_refresh_token", None):
            mailbox.oauth_refresh_token = encrypt_secret(provider.rotated_refresh_token)
    except Exception:
        mailbox.last_error_code = "imap_unavailable"
        request.status = VerificationStatus.WAITING_MAIL.value
        request.lease_expires_at = None
        return "retry"
    for message in messages:
        extracted = adapter.extract(message, account.identifier, request.created_at - timedelta(seconds=60))
        if not extracted:
            continue
        claim = MailMessageClaim(
            mailbox_id=mailbox.id,
            uidvalidity=message.uidvalidity,
            uid=message.uid,
            verification_request_id=request.id,
            message_date=message.message_date,
        )
        try:
            async with session.begin_nested():
                session.add(claim)
                await session.flush()
        except IntegrityError:
            continue
        request.result_ciphertext = encrypt_secret(extracted.code)
        request.result_hash = code_hash(extracted.code)
        request.result_expires_at = utcnow() + timedelta(seconds=get_settings().result_retention_seconds)
        request.status = VerificationStatus.SUCCEEDED.value
        request.lease_expires_at = None
        if request.requested_by_telegram_id is not None:
            session.add(
                WorkerJob(
                    kind="send_verification_result",
                    idempotency_key=str(request.id),
                    payload={"verification_request_id": str(request.id)},
                )
            )
        mailbox.last_checked_at = utcnow()
        await record(session, "verification.code_matched", "verification_request", str(request.id))
        return "matched"
    request.status = VerificationStatus.WAITING_MAIL.value
    request.lease_expires_at = None
    return "retry"
