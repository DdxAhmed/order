from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.salla import SallaApiError, SallaClient, customer_email, normalize_email, order_is_eligible, order_items, order_reference, refresh_access_token, token_ciphertext, token_expiry
from app.models import SallaAccessSession, SallaMerchantAuthorization, SallaOrderVerification, SallaProductMapping, UsageCounter, UsagePolicy, UsageRecord
from app.security import decrypt_salla_secret, new_random_token, sha256, utcnow


class SallaVerificationError(ValueError):
    pass


def _window_cutoff(now: datetime, period_seconds: int) -> datetime:
    """Return the exclusive lower bound for a rolling usage window."""
    return now - timedelta(seconds=period_seconds)


async def active_authorization(session: AsyncSession, merchant_id: int) -> SallaMerchantAuthorization | None:
    return await session.scalar(select(SallaMerchantAuthorization).where(SallaMerchantAuthorization.merchant_id == merchant_id, SallaMerchantAuthorization.revoked_at.is_(None)))


async def verify_order(session: AsyncSession, *, reference: str, purchaser_email: str) -> tuple[str, SallaOrderVerification]:
    raw_reference = reference.strip()
    # Salla dashboards commonly show an order number with a leading '#',
    # while the Orders API may return/query the same reference without it.
    # Keep one canonical value in our database but try both API spellings.
    reference = raw_reference.lstrip("#").strip()
    email = normalize_email(purchaser_email)
    if not reference or "@" not in email:
        raise SallaVerificationError("بيانات التحقق غير مكتملة")
    authorizations = (await session.scalars(select(SallaMerchantAuthorization).where(SallaMerchantAuthorization.revoked_at.is_(None)))).all()
    if not authorizations:
        raise SallaVerificationError("تكامل المتجر غير مفعّل")
    found: tuple[SallaMerchantAuthorization, dict[str, Any]] | None = None
    for auth in authorizations:
        try:
            if auth.token_expires_at <= utcnow() + timedelta(seconds=30):
                locked = await session.scalar(select(SallaMerchantAuthorization).where(SallaMerchantAuthorization.id == auth.id).with_for_update())
                if locked and locked.token_expires_at <= utcnow() + timedelta(seconds=30):
                    refreshed = await refresh_access_token(decrypt_salla_secret(locked.refresh_token_ciphertext))
                    locked.access_token_ciphertext = token_ciphertext(refreshed["access_token"])
                    locked.refresh_token_ciphertext = token_ciphertext(refreshed["refresh_token"])
                    locked.token_expires_at = token_expiry(refreshed.get("expires", int(utcnow().timestamp()) + 1209600))
                    auth = locked
            token = decrypt_salla_secret(auth.access_token_ciphertext)
            client = SallaClient(token)
            for query_reference in dict.fromkeys((raw_reference, reference)):
                orders = await client.list_orders_by_reference(query_reference)
                for candidate in orders:
                    candidate_reference = order_reference(candidate).lstrip("#").strip()
                    if candidate_reference == reference:
                        order_id = int(candidate.get("id") or 0)
                        detailed = await client.get_order(order_id)
                        detailed["items"] = await client.list_order_items(order_id)
                        found = (auth, detailed)
                        break
                if found:
                    break
            if found:
                break
        except SallaApiError as exc:
            if exc.code == "token_expired":
                auth.last_error_code = "token_expired_reauthorization_required"
            continue
    if not found:
        raise SallaVerificationError("تعذر التحقق من الطلب")
    auth, order = found
    expected_email = customer_email(order)
    if not expected_email or not hmac_compare(expected_email, email) or not order_is_eligible(order):
        raise SallaVerificationError("الطلب غير مؤهل أو بيانات المشتري لا تطابق")
    order_id = int(order.get("id") or 0)
    if not order_id:
        raise SallaVerificationError("استجابة الطلب غير صالحة")
    mappings = (await session.scalars(select(SallaProductMapping).where(SallaProductMapping.merchant_id == auth.merchant_id, SallaProductMapping.is_active.is_(True)))).all()
    item_values = {
        str(item.get("product_id") or (item.get("product") or {}).get("id") or "")
        for item in order_items(order)
        if isinstance(item.get("product"), dict) or item.get("product_id") is not None
    }
    item_skus = {str(item.get("sku") or "") for item in order_items(order)}
    service_keys = sorted({
        mapping.service_key
        for mapping in mappings
        if (mapping.product_id is not None and str(mapping.product_id) in item_values)
        or (mapping.sku and mapping.sku in item_skus)
    })
    if not service_keys:
        raise SallaVerificationError("منتج الطلب غير مهيأ للخدمة")
    existing = await session.scalar(select(SallaOrderVerification).where(SallaOrderVerification.merchant_id == auth.merchant_id, SallaOrderVerification.reference_id == reference).with_for_update())
    now = utcnow()
    if existing:
        if existing.purchaser_email_hash != sha256(email):
            raise SallaVerificationError("بيانات المشتري لا تطابق")
        verification = existing
        verification.salla_order_id = order_id
        verification.service_keys = service_keys
        verification.status_slug = str((order.get("status") or {}).get("slug") or "unknown")
        verification.payment_eligible = True
        verification.revoked_at = None
        verification.expires_at = now + timedelta(hours=1)
    else:
        await session.execute(pg_insert(SallaOrderVerification).values(id=uuid.uuid4(), merchant_id=auth.merchant_id, salla_order_id=order_id, reference_id=reference, purchaser_email_hash=sha256(email), service_keys=service_keys, status_slug=str((order.get("status") or {}).get("slug") or "unknown"), payment_eligible=True, expires_at=now + timedelta(hours=1)).on_conflict_do_nothing(index_elements=["merchant_id", "reference_id"]))
        verification = await session.scalar(select(SallaOrderVerification).where(SallaOrderVerification.merchant_id == auth.merchant_id, SallaOrderVerification.reference_id == reference).with_for_update())
        if not verification:
            raise SallaVerificationError("تعذر حفظ تحقق الطلب")
    raw_token = new_random_token(32)
    session.add(SallaAccessSession(verification_id=verification.id, token_hash=sha256(raw_token), csrf_token=new_random_token(24), expires_at=verification.expires_at))
    return raw_token, verification


def hmac_compare(left: str, right: str) -> bool:
    import hmac
    return hmac.compare_digest(left, right)


async def consume_usage(session: AsyncSession, *, verification_id: uuid.UUID, service_key: str, idempotency_key: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    policy = await session.scalar(select(UsagePolicy).where(UsagePolicy.service_key == service_key, UsagePolicy.is_active.is_(True)).with_for_update())
    if not policy:
        raise SallaVerificationError("الخدمة غير مهيأة")
    existing = await session.scalar(select(UsageRecord).where(UsageRecord.verification_id == verification_id, UsageRecord.service_key == service_key, UsageRecord.idempotency_key == idempotency_key))
    if existing:
        counter = await session.scalar(select(UsageCounter).where(UsageCounter.verification_id == verification_id, UsageCounter.service_key == service_key, UsageCounter.period_start == existing.period_start))
        return {"accepted": True, "replayed": True, "remaining": max(0, policy.max_uses - (counter.used_count if counter else 0)), "retry_after": 0}
    cutoff = _window_cutoff(now, policy.period_seconds)
    counter = await session.scalar(
        select(UsageCounter)
        .where(
            UsageCounter.verification_id == verification_id,
            UsageCounter.service_key == service_key,
            UsageCounter.period_start > cutoff,
        )
        .order_by(UsageCounter.period_start.desc())
        .limit(1)
        .with_for_update()
    )
    if not counter:
        await session.execute(pg_insert(UsageCounter).values(verification_id=verification_id, service_key=service_key, period_start=now, used_count=0).on_conflict_do_nothing(index_elements=["verification_id", "service_key", "period_start"]))
        counter = await session.scalar(select(UsageCounter).where(UsageCounter.verification_id == verification_id, UsageCounter.service_key == service_key, UsageCounter.period_start == now).with_for_update())
        if not counter:
            raise SallaVerificationError("تعذر قفل عداد الاستخدام")
    if counter.last_used_at:
        elapsed = int((now - counter.last_used_at).total_seconds())
        if elapsed < policy.cooldown_seconds:
            return {"accepted": False, "remaining": policy.max_uses - counter.used_count, "retry_after": policy.cooldown_seconds - elapsed, "reason": "cooldown"}
    if counter.used_count >= policy.max_uses:
        window_end = counter.period_start + timedelta(seconds=policy.period_seconds)
        return {"accepted": False, "remaining": 0, "retry_after": max(0, int((window_end - now).total_seconds())), "reason": "limit"}
    inserted = await session.execute(pg_insert(UsageRecord).values(verification_id=verification_id, service_key=service_key, idempotency_key=idempotency_key, period_start=counter.period_start).on_conflict_do_nothing(index_elements=["verification_id", "service_key", "idempotency_key"]))
    if not inserted.rowcount:
        return {"accepted": True, "replayed": True, "remaining": max(0, policy.max_uses - counter.used_count), "retry_after": 0}
    counter.used_count += 1
    counter.last_used_at = now
    return {"accepted": True, "replayed": False, "remaining": policy.max_uses - counter.used_count, "retry_after": 0}


async def usage_summaries(session: AsyncSession, *, verification_id: uuid.UUID, service_keys: list[str]) -> list[dict[str, int | str]]:
    """Return only services authorized by this order and their current window."""
    if not service_keys:
        return []
    now = utcnow()
    policies = (await session.scalars(select(UsagePolicy).where(UsagePolicy.service_key.in_(service_keys), UsagePolicy.is_active.is_(True)))).all()
    summaries: list[dict[str, int | str]] = []
    for policy in policies:
        cutoff = _window_cutoff(now, policy.period_seconds)
        counter = await session.scalar(
            select(UsageCounter)
            .where(
                UsageCounter.verification_id == verification_id,
                UsageCounter.service_key == policy.service_key,
                UsageCounter.period_start > cutoff,
            )
            .order_by(UsageCounter.period_start.desc())
            .limit(1)
        )
        summaries.append({"service_key": policy.service_key, "remaining": max(0, policy.max_uses - (counter.used_count if counter else 0)), "period_seconds": policy.period_seconds, "cooldown_seconds": policy.cooldown_seconds})
    return summaries
