from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminSession, AdminUser
from app.services.access import get_admin_session


async def current_admin(request: Request, session: AsyncSession) -> tuple[AdminUser, AdminSession]:
    found = await get_admin_session(session, request.cookies.get("admin_session"))
    if not found:
        raise HTTPException(status_code=401, detail="يلزم تسجيل الدخول")
    return found


async def require_role(request: Request, session: AsyncSession, roles: set[str]) -> tuple[AdminUser, AdminSession]:
    admin, admin_session = await current_admin(request, session)
    if admin.role not in roles:
        raise HTTPException(status_code=403, detail="لا تملك هذه الصلاحية")
    return admin, admin_session


def check_csrf(request: Request, admin_session: AdminSession, submitted: str | None) -> None:
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and submitted != admin_session.csrf_token:
        raise HTTPException(status_code=403, detail="رمز الحماية غير صالح")
