from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_db_session_commit
from app.config import get_settings
from app.models import LocalAccessSession, LocalUsageIdentity
from app.platforms import PLATFORM_CATALOG
from app.security import sha256, utcnow
from app.services.access import consume_rate_limit
from app.services.local_access import (
    LocalAccessError,
    consume_local_usage,
    create_local_access,
    local_usage_summaries,
)
from app.services.non_sensitive_services import is_registered_non_sensitive_service

router = APIRouter(prefix="/salla", tags=["Salla Public & Local Access"])
settings = get_settings()


class LocalAccessRequest(BaseModel):
    order_reference: str
    account_alias: Optional[str] = ""
    platform_code: str = "steam"


class ServiceUsageRequest(BaseModel):
    idempotency_key: str


async def get_local_access_session(
    request: Request,
    session: AsyncSession,
) -> tuple[LocalAccessSession, LocalUsageIdentity]:
    token = request.cookies.get("local_access_session")
    if not token and "authorization" in request.headers:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split("Bearer ", 1)[1].strip()
    if not token and "x-local-session" in request.headers:
        token = request.headers.get("x-local-session")

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="جلسة الوصول المحلي غير موجودة")

    access = await session.scalar(
        select(LocalAccessSession).where(
            LocalAccessSession.token_hash == sha256(token),
            LocalAccessSession.revoked_at.is_(None),
            LocalAccessSession.expires_at > utcnow(),
        )
    )
    if not access:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="جلسة الوصول منتهية أو ملغاة")

    identity = await session.get(LocalUsageIdentity, access.identity_id)
    if not identity:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="هوية الاستخدام غير موجودة")

    return access, identity


@router.post("/access")
async def create_access(
    payload: LocalAccessRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    client_ip = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip() or (
        request.client.host if request.client else "unknown"
    )

    if not await consume_rate_limit(session, "local_access_ip", client_ip, 900, 10):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تم تجاوز عدد المحاولات المؤقتة، الرجاء المحاولة لاحقًا",
        )

    try:
        raw_token, access, identity = await create_local_access(
            session,
            order_reference=payload.order_reference,
            account_alias=payload.account_alias or "",
            platform_code=payload.platform_code,
            session_minutes=settings.salla_customer_session_minutes,
        )
    except LocalAccessError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    services = await local_usage_summaries(session, identity_id=identity.id)

    response.set_cookie(
        key="local_access_session",
        value=raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.salla_customer_session_minutes * 60,
        path="/",
    )

    return {
        "status": "success",
        "session_token": raw_token,
        "csrf_token": access.csrf_token,
        "platform_code": identity.platform_code,
        "services": services,
        "expires_at": access.expires_at.isoformat(),
    }


@router.get("/status")
async def get_status(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    token = request.cookies.get("local_access_session")
    if not token and "authorization" in request.headers:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split("Bearer ", 1)[1].strip()

    services = []
    active_platform = None
    if token:
        access = await session.scalar(
            select(LocalAccessSession).where(
                LocalAccessSession.token_hash == sha256(token),
                LocalAccessSession.revoked_at.is_(None),
                LocalAccessSession.expires_at > utcnow(),
            )
        )
        if access:
            identity = await session.get(LocalUsageIdentity, access.identity_id)
            if identity:
                active_platform = identity.platform_code
                services = await local_usage_summaries(session, identity_id=identity.id)

    return {
        "platforms": PLATFORM_CATALOG,
        "active_platform": active_platform or "steam",
        "has_active_session": active_platform is not None,
        "services": services,
    }


@router.post("/services/{service_key}/use")
async def use_service(
    service_key: str,
    payload: ServiceUsageRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    if not service_key or len(service_key) > 100 or not payload.idempotency_key or len(payload.idempotency_key) > 160:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="طلب غير صالح")

    if not is_registered_non_sensitive_service(service_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الخدمة المطلوبة غير متوفرة")

    access, identity = await get_local_access_session(request, session)
    result = await consume_local_usage(
        session,
        identity_id=identity.id,
        service_key=service_key,
        idempotency_key=payload.idempotency_key,
    )

    if not result.get("accepted"):
        status_code = status.HTTP_429_TOO_MANY_REQUESTS if result.get("reason") == "cooldown" else status.HTTP_403_FORBIDDEN
        raise HTTPException(status_code=status_code, detail=result)

    return result
