from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models import AdminRole, AdminSession, AdminUser, Customer, CustomerSession
from app.services.access import get_admin_session
from app.services.customer import get_customer_web_session


async def get_db_session():
    async with SessionLocal() as session:
        yield session


async def get_db_session_commit():
    async with SessionLocal.begin() as session:
        yield session


async def get_current_admin(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> tuple[AdminUser, AdminSession]:
    token = request.cookies.get("admin_session")
    if not token and "authorization" in request.headers:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split("Bearer ", 1)[1].strip()
    if not token and "x-admin-session" in request.headers:
        token = request.headers.get("x-admin-session")

    found = await get_admin_session(session, token)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="يلزم تسجيل الدخول كمسؤول",
        )
    return found


def require_admin_roles(allowed_roles: set[str]):
    async def role_checker(
        admin_and_session: Annotated[tuple[AdminUser, AdminSession], Depends(get_current_admin)],
    ) -> tuple[AdminUser, AdminSession]:
        admin, session_obj = admin_and_session
        if admin.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="لا تملك الصلاحية للقيام بهذا الإجراء",
            )
        return admin, session_obj

    return role_checker


async def get_current_customer(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> tuple[Customer, CustomerSession]:
    token = request.cookies.get("customer_session")
    if not token and "authorization" in request.headers:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split("Bearer ", 1)[1].strip()
    if not token and "x-customer-session" in request.headers:
        token = request.headers.get("x-customer-session")

    found = await get_customer_web_session(session, token)
    if not found:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="جلسة العميل غير موجودة أو منتهية",
        )
    return found
