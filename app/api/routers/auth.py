from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db_session_commit
from app.audit import record
from app.config import get_settings
from app.models import AdminUser
from app.security import verify_password
from app.services.access import (
    check_login_rate_limit,
    create_admin_session,
    revoke_admin_session,
)

router = APIRouter(prefix="/auth", tags=["Admin Auth"])
settings = get_settings()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminUserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool


@router.post("/login")
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    ip = request.client.host if request.client else "unknown"
    fingerprint = f"{ip}:{payload.email.lower().strip()}"
    if not await check_login_rate_limit(session, fingerprint):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تم تجاوز عدد المحاولات المؤقتة، الرجاء المحاولة لاحقًا",
        )

    admin = await session.scalar(
        select(AdminUser).where(AdminUser.email == payload.email.lower().strip())
    )
    if not admin or not admin.is_active or not verify_password(admin.password_hash, payload.password):
        await record(session, "admin.login_failed", "admin_user", payload.email.lower().strip(), metadata={"ip": ip})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="البريد الإلكتروني أو كلمة المرور غير صحيحة",
        )

    raw_token, db_session = await create_admin_session(session, admin)

    response.set_cookie(
        key="admin_session",
        value=raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.admin_session_hours * 3600,
        path="/",
    )

    return {
        "status": "success",
        "token": raw_token,
        "csrf_token": db_session.csrf_token,
        "user": {
            "id": str(admin.id),
            "email": admin.email,
            "role": admin.role,
        },
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    token = request.headers.get("x-admin-session") or request.cookies.get("admin_session")
    if not token and "authorization" in request.headers:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split("Bearer ", 1)[1].strip()

    if token:
        await revoke_admin_session(session, token)

    response.delete_cookie(key="admin_session", path="/")
    return {"status": "success", "message": "تم تسجيل الخروج بنجاح"}


@router.get("/me")
async def me(
    admin_and_session: Annotated[tuple, Depends(get_current_admin)],
):
    admin, db_session = admin_and_session
    return {
        "user": {
            "id": str(admin.id),
            "email": admin.email,
            "role": admin.role,
        },
        "csrf_token": db_session.csrf_token,
    }
