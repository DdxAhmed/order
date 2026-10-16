from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_customer, get_db_session, get_db_session_commit
from app.config import get_settings
from app.models import AccountAssignment, Customer, CustomerSession, Order
from app.security import mask_account_identifier, sha256, utcnow
from app.services.access import consume_rate_limit
from app.services.customer import (
    CustomerAccessError,
    access_order_for_web,
    activate_order_for_web,
    assignments_for_web,
    result_for_web,
    verification_statuses_for_web,
)
from app.services.inventory import create_verification_request

router = APIRouter(prefix="/customer", tags=["Customer Portal"])
settings = get_settings()


class CustomerAccessRequest(BaseModel):
    order_reference: str
    steam_username: str
    platform_code: str = "steam"


class ActivationRequest(BaseModel):
    activation_token: str


@router.post("/access")
async def customer_access(
    payload: CustomerAccessRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    if payload.platform_code.strip().casefold() != "steam":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="هذه المنصة متاحة لإدارة المخزون فقط حاليًا",
        )

    clean_ref = payload.order_reference.strip()
    clean_user = payload.steam_username.strip()
    client_ip = request.client.host if request.client else "unknown"
    subject = f"{client_ip}:{sha256(clean_ref.casefold() + ':' + clean_user.casefold())}"

    if not await consume_rate_limit(session, "web_identity_ip", client_ip, 900, 30):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تم تجاوز عدد المحاولات المؤقتة، الرجاء المحاولة لاحقًا",
        )
    if not await consume_rate_limit(session, "web_identity", subject, 900, 8):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تم تجاوز عدد المحاولات المؤقتة، الرجاء المحاولة لاحقًا",
        )

    try:
        raw_session, customer_session = await access_order_for_web(
            session,
            external_reference=clean_ref,
            account_identifier=clean_user,
            platform_code=payload.platform_code,
        )
    except CustomerAccessError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="رقم الطلب أو اسم مستخدم Steam غير صحيح",
        )

    response.set_cookie(
        key="customer_session",
        value=raw_session,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.customer_session_minutes * 60,
        path="/",
    )

    return {
        "status": "success",
        "session_token": raw_session,
        "expires_at": customer_session.expires_at.isoformat(),
        "csrf_token": customer_session.csrf_token,
    }


@router.post("/activate")
async def customer_activate(
    payload: ActivationRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    token_clean = payload.activation_token.strip()
    client_ip = request.client.host if request.client else "unknown"
    subject = f"{client_ip}:{token_clean[:16]}"

    if not await consume_rate_limit(session, "web_activation", subject, 900, 10):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تم تجاوز عدد المحاولات المؤقتة",
        )

    try:
        raw_session, customer_session = await activate_order_for_web(session, token_clean)
    except CustomerAccessError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="رابط أو رمز التفعيل غير صالح أو منتهٍ",
        )

    response.set_cookie(
        key="customer_session",
        value=raw_session,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.customer_session_minutes * 60,
        path="/",
    )

    return {
        "status": "success",
        "session_token": raw_session,
        "expires_at": customer_session.expires_at.isoformat(),
        "csrf_token": customer_session.csrf_token,
    }


@router.get("/portal")
async def get_portal_data(
    customer_and_session: Annotated[
        tuple[Customer, CustomerSession],
        Depends(get_current_customer),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    customer, customer_session = customer_and_session

    assignments = await assignments_for_web(session, customer.id)
    requests = await verification_statuses_for_web(session, customer_session.id)

    statuses = {}
    for item in requests:
        statuses.setdefault(item.assignment_id, item)

    request_results = {}
    for item in requests:
        res = await result_for_web(session, item.id, customer_session.id)
        if res:
            request_results[str(item.id)] = res

    rows = []
    for asgn, account in assignments:
        st = statuses.get(asgn.id)
        rows.append({
            "assignment_id": str(asgn.id),
            "account_identifier_masked": mask_account_identifier(account.identifier),
            "platform_name": "Steam",
            "current_status": st.status if st else "ready",
            "last_request_id": str(st.id) if st else None,
            "verification_code": request_results.get(str(st.id)) if st else None,
            "requested_at": st.created_at.isoformat() if st and st.created_at else None,
        })

    return {
        "customer": {
            "id": str(customer.id),
            "display_name": customer.display_name,
        },
        "csrf_token": customer_session.csrf_token,
        "assignments": rows,
        "expires_at": customer_session.expires_at.isoformat() if customer_session.expires_at else None,
    }


@router.post("/assignments/{assignment_id}/verify")
async def request_verification_code(
    assignment_id: uuid.UUID,
    customer_and_session: Annotated[
        tuple[Customer, CustomerSession],
        Depends(get_current_customer),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    customer, customer_session = customer_and_session

    if not await consume_rate_limit(session, "web_verify", str(customer_session.id), 600, 5):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تم تجاوز الحد المؤقت لطلبات الرموز، الرجاء الانتظار قليلاً",
        )

    assignment = await session.scalar(
        select(AccountAssignment)
        .join(Order, Order.id == AccountAssignment.order_id)
        .where(
            AccountAssignment.id == assignment_id,
            AccountAssignment.customer_id == customer.id,
            AccountAssignment.revoked_at.is_(None),
            Order.status == "activated",
        )
        .with_for_update()
    )
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="لا يمكن الوصول إلى هذا الحساب أو الطلب غير مفعّل",
        )

    req = await create_verification_request(
        session,
        assignment,
        settings.verification_wait_seconds,
        web_session_id=customer_session.id,
    )

    return {
        "status": "success",
        "message": "تم تقديم طلب استخراج رمز الدخول، جاري الفحص التلقائي...",
        "request_id": str(req.id),
    }


@router.post("/logout")
async def customer_logout(
    response: Response,
    customer_and_session: Annotated[
        tuple[Customer, CustomerSession],
        Depends(get_current_customer),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    _, customer_session = customer_and_session
    customer_session.revoked_at = utcnow()
    response.delete_cookie(key="customer_session", path="/")
    return {"status": "success", "message": "تم تسجيل الخروج بنجاح"}
