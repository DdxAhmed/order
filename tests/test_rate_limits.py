from __future__ import annotations

import asyncio
from datetime import timedelta
import uuid
import pytest

from app.db import SessionLocal
from app.models import LocalUsageIdentity, UsagePolicy
from app.security import utcnow
from app.services.access import consume_rate_limit
from app.services.local_access import consume_local_usage


@pytest.mark.asyncio
async def test_consume_rate_limit_enforces_maximum():
    async with SessionLocal.begin() as session:
        subject = f"test_rate_limit_{uuid.uuid4().hex}"
        scope = "unit_test_rate_limit"
        max_attempts = 5
        window_seconds = 3600

        # Attempts 1 to 5 should succeed
        for i in range(max_attempts):
            allowed = await consume_rate_limit(session, scope, subject, window_seconds, max_attempts)
            assert allowed is True, f"Attempt {i+1} should be allowed"

        # 6th attempt must be rejected (False)
        exceeded = await consume_rate_limit(session, scope, subject, window_seconds, max_attempts)
        assert exceeded is False, "Attempt beyond maximum must be rejected"


@pytest.mark.asyncio
async def test_usage_policy_cooldown_and_five_request_limit():
    """Verify 5-request quota and 30-second cooldown."""
    service_key = f"svc_{uuid.uuid4().hex[:8]}"

    async with SessionLocal.begin() as session:
        # Create policy with 5 max uses and 30s cooldown
        policy = UsagePolicy(
            service_key=service_key,
            max_uses=5,
            period_seconds=86400,
            cooldown_seconds=30,
            is_active=True,
        )
        session.add(policy)

        # Create identity with correct model columns
        identity = LocalUsageIdentity(
            reference_key=f"ORD-RL-{uuid.uuid4().hex[:8]}",
            account_alias="test_alias",
            platform_code="steam",
        )
        session.add(identity)
        await session.flush()
        identity_id = identity.id

    now = utcnow()

    # 1. First usage at t=0
    async with SessionLocal.begin() as session:
        res1 = await consume_local_usage(
            session,
            identity_id=identity_id,
            service_key=service_key,
            idempotency_key=str(uuid.uuid4()),
            now=now,
        )
        assert res1["accepted"] is True
        assert res1["remaining"] == 4

    # 2. Immediate second usage at t=10s (< 30s cooldown) -> Must be rejected with reason='cooldown'
    async with SessionLocal.begin() as session:
        res2 = await consume_local_usage(
            session,
            identity_id=identity_id,
            service_key=service_key,
            idempotency_key=str(uuid.uuid4()),
            now=now + timedelta(seconds=10),
        )
        assert res2["accepted"] is False
        assert res2["reason"] == "cooldown"
        assert res2["retry_after"] == 20

    # 3. Third usage at t=31s (> 30s cooldown) -> Accepted (remaining 3)
    async with SessionLocal.begin() as session:
        res3 = await consume_local_usage(
            session,
            identity_id=identity_id,
            service_key=service_key,
            idempotency_key=str(uuid.uuid4()),
            now=now + timedelta(seconds=31),
        )
        assert res3["accepted"] is True
        assert res3["remaining"] == 3

    # 4. Usages 3, 4, 5 (spaced by 31s each)
    t = now + timedelta(seconds=31)
    for expected_remaining in [2, 1, 0]:
        t += timedelta(seconds=31)
        async with SessionLocal.begin() as session:
            res = await consume_local_usage(
                session,
                identity_id=identity_id,
                service_key=service_key,
                idempotency_key=str(uuid.uuid4()),
                now=t,
            )
            assert res["accepted"] is True
            assert res["remaining"] == expected_remaining

    # 5. Sixth usage at t=200s (exceeded 5 max uses) -> Must be rejected with reason='limit'
    async with SessionLocal.begin() as session:
        res_limit = await consume_local_usage(
            session,
            identity_id=identity_id,
            service_key=service_key,
            idempotency_key=str(uuid.uuid4()),
            now=t + timedelta(seconds=35),
        )
        assert res_limit["accepted"] is False
        assert res_limit["reason"] == "limit"
        assert res_limit["remaining"] == 0


@pytest.mark.asyncio
async def test_concurrent_requests_cannot_bypass_cooldown_and_limit():
    """Verify concurrent requests are serialized by database row locks."""
    service_key = f"svc_concurrent_{uuid.uuid4().hex[:8]}"

    async with SessionLocal.begin() as session:
        policy = UsagePolicy(
            service_key=service_key,
            max_uses=5,
            period_seconds=86400,
            cooldown_seconds=30,
            is_active=True,
        )
        session.add(policy)

        identity = LocalUsageIdentity(
            reference_key=f"ORD-CONCUR-{uuid.uuid4().hex[:8]}",
            account_alias="concurrent_alias",
            platform_code="steam",
        )
        session.add(identity)
        await session.flush()
        identity_id = identity.id

    now = utcnow()

    async def send_concurrent_attempt(attempt_idx: int):
        async with SessionLocal.begin() as session:
            return await consume_local_usage(
                session,
                identity_id=identity_id,
                service_key=service_key,
                idempotency_key=f"concurrent_key_{attempt_idx}_{uuid.uuid4().hex}",
                now=now,
            )

    # Launch 10 concurrent requests at the exact same moment
    results = await asyncio.gather(*(send_concurrent_attempt(i) for i in range(10)))

    accepted = [r for r in results if r.get("accepted") is True]
    cooldowns = [r for r in results if r.get("reason") == "cooldown"]

    # Exactly 1 request must be accepted, and remaining 9 must be rejected with 'cooldown'
    assert len(accepted) == 1, f"Expected exactly 1 accepted, got {len(accepted)}"
    assert len(cooldowns) == 9, f"Expected 9 cooldown rejections, got {len(cooldowns)}"
