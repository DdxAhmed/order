"""Local access keyed by a merchant-approved, unverified external reference.

This flow intentionally does not call Salla, inspect notification mail, or
assert that a submitted number is a real order.  It only creates a local
usage identity and applies the generic non-sensitive service quota.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record
from app.models import (
    LocalAccessSession,
    LocalUsageCounter,
    LocalUsageIdentity,
    LocalUsageRecord,
    UsagePolicy,
)
from app.platforms import platform_definition
from app.security import new_random_token, sha256, utcnow
from app.services.non_sensitive_services import registered_service_keys


REFERENCE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._/\-]{0,119}$")


class LocalAccessError(ValueError):
    pass


def normalize_order_reference(value: str) -> str:
    normalized = value.strip().lstrip("#").strip().upper()
    if not normalized or len(normalized) > 120 or not REFERENCE_PATTERN.fullmatch(normalized):
        raise LocalAccessError("رقم الطلب غير صالح")
    return normalized


def normalize_account_alias(value: str) -> str:
    stripped = value.strip()
    # Reject control characters before whitespace normalization.  Calling
    # ``split()`` first would silently turn a newline into a normal space and
    # allow malformed aliases through the validation boundary.
    if any(ord(char) < 32 or ord(char) == 127 for char in stripped):
        raise LocalAccessError("اسم المستخدم غير صالح")
    normalized = " ".join(stripped.split())
    if not normalized or len(normalized) > 255:
        raise LocalAccessError("اسم المستخدم غير صالح")
    return normalized


def normalize_platform_code(value: str) -> str:
    normalized = value.strip().casefold()
    if not platform_definition(normalized):
        raise LocalAccessError("المنصة غير صالحة")
    return normalized


def _window_cutoff(now: datetime, period_seconds: int) -> datetime:
    return now - timedelta(seconds=period_seconds)


async def create_local_access(
    session: AsyncSession,
    *,
    order_reference: str,
    account_alias: str,
    platform_code: str = "steam",
    session_minutes: int,
) -> tuple[str, LocalAccessSession, LocalUsageIdentity]:
    """Create/reuse a local identity and issue an access session.

    The identity lookup is serialized by PostgreSQL. Repeated submissions for
    the same normalized reference never create another identity.
    """

    reference = normalize_order_reference(order_reference)
    alias = normalize_account_alias(account_alias)
    platform = normalize_platform_code(platform_code)
    identity = await session.scalar(
        select(LocalUsageIdentity).where(LocalUsageIdentity.reference_key == reference).with_for_update()
    )
    created = False
    if identity is None:
        await session.execute(
            pg_insert(LocalUsageIdentity)
            .values(reference_key=reference, platform_code=platform, account_alias=alias)
            .on_conflict_do_nothing(index_elements=["reference_key"])
        )
        identity = await session.scalar(
            select(LocalUsageIdentity).where(LocalUsageIdentity.reference_key == reference).with_for_update()
        )
        if identity is None:
            raise LocalAccessError("تعذر إنشاء جلسة الاستخدام")
        created = True
    else:
        identity.platform_code = platform
        identity.account_alias = alias

    raw_token = new_random_token(32)
    access = LocalAccessSession(
        identity_id=identity.id,
        token_hash=sha256(raw_token),
        csrf_token=new_random_token(24),
        expires_at=utcnow() + timedelta(minutes=session_minutes),
    )
    session.add(access)
    await record(
        session,
        "local_access.session_created",
        "local_usage_identity",
        str(identity.id),
        metadata={
            "reference_hash": sha256(reference),
            "alias_hash": sha256(alias.casefold()),
            "platform_code": platform,
            "identity_created": created,
            "unverified_external_reference": True,
        },
    )
    return raw_token, access, identity


async def local_usage_summaries(
    session: AsyncSession,
    *,
    identity_id: uuid.UUID,
) -> list[dict[str, int | str]]:
    keys = registered_service_keys()
    if not keys:
        return []
    now = utcnow()
    policies = (
        await session.scalars(select(UsagePolicy).where(UsagePolicy.service_key.in_(keys), UsagePolicy.is_active.is_(True)))
    ).all()
    summaries: list[dict[str, int | str]] = []
    for policy in policies:
        cutoff = _window_cutoff(now, policy.period_seconds)
        counter = await session.scalar(
            select(LocalUsageCounter)
            .where(
                LocalUsageCounter.identity_id == identity_id,
                LocalUsageCounter.service_key == policy.service_key,
                LocalUsageCounter.period_start > cutoff,
            )
            .order_by(LocalUsageCounter.period_start.desc())
            .limit(1)
        )
        summaries.append(
            {
                "service_key": policy.service_key,
                "remaining": max(0, policy.max_uses - (counter.used_count if counter else 0)),
                "period_seconds": policy.period_seconds,
                "cooldown_seconds": policy.cooldown_seconds,
            }
        )
    return summaries


async def consume_local_usage(
    session: AsyncSession,
    *,
    identity_id: uuid.UUID,
    service_key: str,
    idempotency_key: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Atomically enforce quota, cooldown, and idempotent replay per reference."""

    now = now or utcnow()
    policy = await session.scalar(
        select(UsagePolicy).where(UsagePolicy.service_key == service_key, UsagePolicy.is_active.is_(True)).with_for_update()
    )
    if not policy:
        raise LocalAccessError("الخدمة غير مهيأة")
    existing = await session.scalar(
        select(LocalUsageRecord).where(
            LocalUsageRecord.identity_id == identity_id,
            LocalUsageRecord.service_key == service_key,
            LocalUsageRecord.idempotency_key == idempotency_key,
        )
    )
    if existing:
        counter = await session.scalar(
            select(LocalUsageCounter).where(
                LocalUsageCounter.identity_id == identity_id,
                LocalUsageCounter.service_key == service_key,
                LocalUsageCounter.period_start == existing.period_start,
            )
        )
        return {
            "accepted": True,
            "replayed": True,
            "remaining": max(0, policy.max_uses - (counter.used_count if counter else 0)),
            "retry_after": 0,
        }
    cutoff = _window_cutoff(now, policy.period_seconds)
    counter = await session.scalar(
        select(LocalUsageCounter)
        .where(
            LocalUsageCounter.identity_id == identity_id,
            LocalUsageCounter.service_key == service_key,
            LocalUsageCounter.period_start > cutoff,
        )
        .order_by(LocalUsageCounter.period_start.desc())
        .limit(1)
        .with_for_update()
    )
    if not counter:
        await session.execute(
            pg_insert(LocalUsageCounter)
            .values(identity_id=identity_id, service_key=service_key, period_start=now, used_count=0)
            .on_conflict_do_nothing(index_elements=["identity_id", "service_key", "period_start"])
        )
        counter = await session.scalar(
            select(LocalUsageCounter)
            .where(
                LocalUsageCounter.identity_id == identity_id,
                LocalUsageCounter.service_key == service_key,
                LocalUsageCounter.period_start == now,
            )
            .with_for_update()
        )
        if not counter:
            raise LocalAccessError("تعذر قفل عداد الاستخدام")
    if counter.last_used_at:
        elapsed = int((now - counter.last_used_at).total_seconds())
        if elapsed < policy.cooldown_seconds:
            return {
                "accepted": False,
                "remaining": policy.max_uses - counter.used_count,
                "retry_after": policy.cooldown_seconds - elapsed,
                "reason": "cooldown",
            }
    if counter.used_count >= policy.max_uses:
        window_end = counter.period_start + timedelta(seconds=policy.period_seconds)
        return {
            "accepted": False,
            "remaining": 0,
            "retry_after": max(0, int((window_end - now).total_seconds())),
            "reason": "limit",
        }
    inserted = await session.execute(
        pg_insert(LocalUsageRecord)
        .values(
            identity_id=identity_id,
            service_key=service_key,
            idempotency_key=idempotency_key,
            period_start=counter.period_start,
        )
        .on_conflict_do_nothing(index_elements=["identity_id", "service_key", "idempotency_key"])
    )
    if not inserted.rowcount:
        return {
            "accepted": True,
            "replayed": True,
            "remaining": max(0, policy.max_uses - counter.used_count),
            "retry_after": 0,
        }
    counter.used_count += 1
    counter.last_used_at = now
    return {
        "accepted": True,
        "replayed": False,
        "remaining": policy.max_uses - counter.used_count,
        "retry_after": 0,
    }
