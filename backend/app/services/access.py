from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import record
from app.models import AdminSession, AdminUser, RateLimitWindow
from app.security import make_csrf_token, new_random_token, session_expiry, sha256, utcnow


async def create_admin_session(session: AsyncSession, admin: AdminUser) -> tuple[str, AdminSession]:
    raw_token = new_random_token()
    db_session = AdminSession(
        admin_id=admin.id,
        token_hash=sha256(raw_token),
        csrf_token=make_csrf_token(),
        expires_at=session_expiry(),
    )
    session.add(db_session)
    await record(session, "admin.session_created", "admin", str(admin.id), actor_admin_id=admin.id)
    return raw_token, db_session


async def get_admin_session(session: AsyncSession, raw_token: str | None) -> tuple[AdminUser, AdminSession] | None:
    if not raw_token:
        return None
    now = utcnow()
    result = await session.execute(
        select(AdminUser, AdminSession)
        .join(AdminSession, AdminSession.admin_id == AdminUser.id)
        .where(
            AdminSession.token_hash == sha256(raw_token),
            AdminSession.revoked_at.is_(None),
            AdminSession.expires_at > now,
            AdminUser.is_active.is_(True),
        )
    )
    return result.one_or_none()


async def revoke_admin_session(session: AsyncSession, raw_token: str | None) -> None:
    if not raw_token:
        return
    db_session = await session.scalar(
        select(AdminSession).where(AdminSession.token_hash == sha256(raw_token)).with_for_update()
    )
    if db_session and db_session.revoked_at is None:
        db_session.revoked_at = utcnow()
        await record(session, "admin.session_revoked", "admin_session", str(db_session.id), actor_admin_id=db_session.admin_id)


async def check_login_rate_limit(session: AsyncSession, fingerprint: str) -> bool:
    """Database-backed fixed window; intentionally small and shared by all web workers."""
    return await consume_rate_limit(session, "admin_login", fingerprint, 3600, 10)


async def consume_rate_limit(
    session: AsyncSession, scope: str, subject: str, window_seconds: int, maximum: int
) -> bool:
    now = utcnow()
    window_start = now - timedelta(seconds=now.timestamp() % window_seconds)
    subject_hash = sha256(subject)
    statement = (
        insert(RateLimitWindow)
        .values(scope=scope, subject_hash=subject_hash, window_start=window_start, count=1)
        .on_conflict_do_update(
            constraint="uq_rate_limit_window",
            set_={"count": RateLimitWindow.count + 1},
            where=RateLimitWindow.count < maximum,
        )
        .returning(RateLimitWindow.count)
    )
    return (await session.scalar(statement)) is not None
