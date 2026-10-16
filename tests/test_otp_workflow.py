from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.mail.imap_provider import ParsedMailMessage
from app.models import (
    AccountAssignment,
    AdminUser,
    Customer,
    CustomerSession,
    InventoryAccount,
    Mailbox,
    Order,
    Platform,
    VerificationRequest,
    VerificationStatus,
)

from app.security import decrypt_secret, hash_password, make_csrf_token, new_random_token, sha256, utcnow
from app.services.verification import acquire_request, fetch_code


async def create_otp_test_context(session: AsyncSession) -> dict:
    """Setup an isolated customer, platform, mailbox, account, order and assignment."""
    platform = await session.scalar(select(Platform).where(Platform.code == "steam"))
    mail_profile = {
        "sender_domains": ["steampowered.com"],
        "required_auth_result": "dkim=pass",
        "sample_verified_at": "2026-09-08T00:00:00Z",
        "account_patterns": [r"Dear\s+([A-Za-z0-9_]+)"],
        "code_patterns": [r"login code is\s+([A-Z0-9]{5})"],
    }

    if not platform:
        platform = Platform(
            code="steam",
            name="Steam Test",
            is_enabled=True,
            mail_profile=mail_profile,
        )
        session.add(platform)
        await session.flush()
    else:
        platform.is_enabled = True
        platform.mail_profile = mail_profile
        await session.flush()

    mailbox = Mailbox(
        label=f"mb_{uuid.uuid4().hex[:8]}",
        host="imap.example.com",
        port=993,
        username=f"gamer_{uuid.uuid4().hex[:6]}@example.com",
        auth_mode="imap_password",
        is_active=True,
    )
    session.add(mailbox)
    await session.flush()

    unique_ident = f"gamer_{uuid.uuid4().hex[:6]}"
    account = InventoryAccount(
        platform_id=platform.id,
        mailbox_id=mailbox.id,
        identifier=unique_ident,
        normalized_identifier=unique_ident,
        status="assigned",
    )
    session.add(account)
    await session.flush()

    admin = AdminUser(
        email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password("DummyPass123!"),
        role="owner",
        is_active=True,
    )
    session.add(admin)
    await session.flush()

    customer = Customer(display_name="Test Customer")
    session.add(customer)
    await session.flush()

    raw_token = new_random_token()
    cust_session = CustomerSession(
        customer_id=customer.id,
        token_hash=sha256(raw_token),
        csrf_token=make_csrf_token(),
        expires_at=utcnow() + timedelta(hours=2),
    )
    session.add(cust_session)
    await session.flush()

    order = Order(
        external_reference=f"ORD-OTP-{uuid.uuid4().hex[:6]}",
        customer_id=customer.id,
        status="activated",
    )
    session.add(order)
    await session.flush()

    assignment = AccountAssignment(
        account_id=account.id,
        order_id=order.id,
        customer_id=customer.id,
        assigned_by_admin_id=admin.id,
    )
    session.add(assignment)
    await session.flush()

    return {
        "platform_id": platform.id,
        "mailbox_id": mailbox.id,
        "account_id": account.id,
        "account_identifier": unique_ident,
        "assignment_id": assignment.id,
        "order_id": order.id,
        "customer_id": customer.id,
        "cust_session_id": cust_session.id,
    }


@pytest.mark.asyncio
async def test_otp_retrieval_success_with_matching_steam_fixture():
    """Test full OTP flow when a matching synthetic Steam email arrives."""
    now = datetime.now(UTC)

    async with SessionLocal.begin() as session:
        ctx = await create_otp_test_context(session)
        v_req = VerificationRequest(
            assignment_id=ctx["assignment_id"],
            requested_by_web_session_id=ctx["cust_session_id"],
            status=VerificationStatus.QUEUED.value,
            expires_at=utcnow() + timedelta(minutes=5),
        )
        session.add(v_req)
        await session.flush()
        req_id = v_req.id
        ident = ctx["account_identifier"]

    synthetic_email = ParsedMailMessage(
        uidvalidity="1",
        uid="1001",
        message_date=now,
        from_address="Steam Support <noreply@steampowered.com>",
        subject="Your Steam account: Access from new web or mobile device",
        text=f"Dear {ident},\nHere is your Steam Guard code. Your login code is K9X42.\n",
        html="",
        authentication_results="dkim=pass header.i=@steampowered.com",
        message_id="msg-1001",
        headers={"message-id": "msg-1001"},
    )

    with patch("app.services.verification.ImapMailProvider.recent_messages", return_value=[synthetic_email]):
        async with SessionLocal.begin() as session:
            result = await fetch_code(session, req_id)
            assert result == "matched"

        async with SessionLocal.begin() as session:
            updated_req = await session.get(VerificationRequest, req_id)
            assert updated_req.status == VerificationStatus.SUCCEEDED.value
            assert updated_req.result_ciphertext is not None
            assert decrypt_secret(updated_req.result_ciphertext) == "K9X42"


@pytest.mark.asyncio
async def test_otp_retrieval_ignores_missing_message():
    """When mailbox has no messages, verification request enters waiting_mail."""
    async with SessionLocal.begin() as session:
        ctx = await create_otp_test_context(session)
        v_req = VerificationRequest(
            assignment_id=ctx["assignment_id"],
            requested_by_web_session_id=ctx["cust_session_id"],
            status=VerificationStatus.QUEUED.value,
            expires_at=utcnow() + timedelta(minutes=5),
        )
        session.add(v_req)
        await session.flush()
        req_id = v_req.id

    with patch("app.services.verification.ImapMailProvider.recent_messages", return_value=[]):
        async with SessionLocal.begin() as session:
            result = await fetch_code(session, req_id)
            assert result == "retry"

        async with SessionLocal.begin() as session:
            updated_req = await session.get(VerificationRequest, req_id)
            assert updated_req.status == VerificationStatus.WAITING_MAIL.value
            assert updated_req.result_ciphertext is None


@pytest.mark.asyncio
async def test_otp_retrieval_handles_expired_request():
    """Expired requests are marked as expired and ignored."""
    async with SessionLocal.begin() as session:
        ctx = await create_otp_test_context(session)
        v_req = VerificationRequest(
            assignment_id=ctx["assignment_id"],
            requested_by_web_session_id=ctx["cust_session_id"],
            status=VerificationStatus.QUEUED.value,
            expires_at=utcnow() - timedelta(seconds=10),
        )
        session.add(v_req)
        await session.flush()
        req_id = v_req.id

    async with SessionLocal.begin() as session:
        req = await acquire_request(session, req_id)
        assert req is None
        checked = await session.get(VerificationRequest, req_id)
        assert checked.status == VerificationStatus.EXPIRED.value


@pytest.mark.asyncio
async def test_otp_retrieval_handles_cancelled_revoked_order():
    """If an assignment was revoked, fetch_code marks request cancelled."""
    async with SessionLocal.begin() as session:
        ctx = await create_otp_test_context(session)
        asgn = await session.get(AccountAssignment, ctx["assignment_id"])
        asgn.revoked_at = utcnow()
        v_req = VerificationRequest(
            assignment_id=ctx["assignment_id"],
            requested_by_web_session_id=ctx["cust_session_id"],
            status=VerificationStatus.QUEUED.value,
            expires_at=utcnow() + timedelta(minutes=5),
        )
        session.add(v_req)
        await session.flush()
        req_id = v_req.id

    async with SessionLocal.begin() as session:
        result = await fetch_code(session, req_id)
        assert result == "done"
        updated_req = await session.get(VerificationRequest, req_id)
        assert updated_req.status == VerificationStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_otp_retrieval_ignores_malformed_and_mismatched_fixtures():
    """Malformed body, wrong account name, and failed DKIM are ignored."""
    now = datetime.now(UTC)

    async with SessionLocal.begin() as session:
        ctx = await create_otp_test_context(session)
        v_req = VerificationRequest(
            assignment_id=ctx["assignment_id"],
            requested_by_web_session_id=ctx["cust_session_id"],
            status=VerificationStatus.QUEUED.value,
            expires_at=utcnow() + timedelta(minutes=5),
        )
        session.add(v_req)
        await session.flush()
        req_id = v_req.id
        ident = ctx["account_identifier"]

    malformed_fixtures = [
        # 1. Wrong user
        ParsedMailMessage(
            uidvalidity="1",
            uid="2001",
            message_date=now,
            from_address="Steam Support <noreply@steampowered.com>",
            subject="Your Steam code",
            text="Dear completely_different_user,\nYour login code is ABC12.",
            html="",
            authentication_results="dkim=pass",
            message_id="msg-2001",
            headers={},
        ),
        # 2. Missing OTP pattern
        ParsedMailMessage(
            uidvalidity="1",
            uid="2002",
            message_date=now,
            from_address="Steam Support <noreply@steampowered.com>",
            subject="Your Steam code",
            text=f"Dear {ident},\nThere is no code in this email.",
            html="",
            authentication_results="dkim=pass",
            message_id="msg-2002",
            headers={},
        ),
        # 3. Spoofed sender / failed dkim
        ParsedMailMessage(
            uidvalidity="1",
            uid="2003",
            message_date=now,
            from_address="Hacker <hacker@fake.com>",
            subject="Your Steam code",
            text=f"Dear {ident},\nYour login code is HACK1.",
            html="",
            authentication_results="dkim=fail",
            message_id="msg-2003",
            headers={},
        ),
    ]

    with patch("app.services.verification.ImapMailProvider.recent_messages", return_value=malformed_fixtures):
        async with SessionLocal.begin() as session:
            result = await fetch_code(session, req_id)
            assert result == "retry"

        async with SessionLocal.begin() as session:
            updated_req = await session.get(VerificationRequest, req_id)
            assert updated_req.status == VerificationStatus.WAITING_MAIL.value
            assert updated_req.result_ciphertext is None
