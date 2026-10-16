from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_db_session_commit, require_admin_roles
from app.audit import record
from app.config import get_settings
from app.models import (
    AccountAssignment,
    AdminRole,
    AdminSession,
    AdminUser,
    Customer,
    InventoryAccount,
    Order,
    Platform,
)
from app.services.inventory import assign_account

router = APIRouter(prefix="/admin/orders", tags=["Admin Orders"])
settings = get_settings()


class OrderCreateRequest(BaseModel):
    external_reference: str
    customer_id: str


class AssignmentCreateRequest(BaseModel):
    account_id: str
    order_id: str
    reassign_reason: Optional[str] = None


@router.get("")
async def list_orders(
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value, AdminRole.SUPPORT.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    customers_raw = (await session.scalars(select(Customer).order_by(Customer.display_name))).all()
    customers = [{"id": str(c.id), "display_name": c.display_name} for c in customers_raw]

    order_rows = (
        await session.execute(
            select(Order, Customer.display_name)
            .join(Customer, Customer.id == Order.customer_id)
            .order_by(Order.created_at.desc())
            .limit(150)
        )
    ).all()

    # Get active assignments for all these orders
    order_ids = [order.id for order, _ in order_rows]
    assignments_map = {}
    if order_ids:
        assignments_raw = (
            await session.execute(
                select(AccountAssignment, InventoryAccount.identifier, Platform.name, Platform.code)
                .join(InventoryAccount, InventoryAccount.id == AccountAssignment.account_id)
                .join(Platform, Platform.id == InventoryAccount.platform_id)
                .where(
                    AccountAssignment.order_id.in_(order_ids),
                    AccountAssignment.revoked_at.is_(None),
                )
            )
        ).all()
        for asgn, ident, p_name, p_code in assignments_raw:
            assignments_map[asgn.order_id] = {
                "id": str(asgn.id),
                "account_id": str(asgn.account_id),
                "account_identifier": ident,
                "platform_name": p_name,
                "platform_code": p_code,
                "assigned_at": asgn.created_at.isoformat() if asgn.created_at else None,
            }

    orders = [
        {
            "id": str(order.id),
            "external_reference": order.external_reference,
            "status": order.status,
            "customer_id": str(order.customer_id),
            "customer_name": name,
            "assignment": assignments_map.get(order.id),
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }
        for order, name in order_rows
    ]

    assignable = (
        await session.scalars(
            select(InventoryAccount)
            .where(InventoryAccount.status.in_(["available", "assigned"]))
            .order_by(InventoryAccount.identifier)
        )
    ).all()
    assignable_accounts = [
        {"id": str(a.id), "identifier": a.identifier, "status": a.status}
        for a in assignable
    ]

    return {
        "orders": orders,
        "customers": customers,
        "assignable_accounts": assignable_accounts,
    }


@router.post("")
async def create_order(
    payload: OrderCreateRequest,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    clean_reference = payload.external_reference.strip()
    if not clean_reference:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="مرجع الطلب مطلوب")

    try:
        customer_uuid = uuid.UUID(payload.customer_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="معرف العميل غير صالح")

    customer = await session.get(Customer, customer_uuid)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="العميل غير موجود")

    order = Order(external_reference=clean_reference, customer_id=customer_uuid)
    session.add(order)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="مرجع الطلب مستخدم بالفعل",
        )

    await record(session, "order.created", "order", str(order.id), actor_admin_id=admin.id)

    return {
        "status": "success",
        "message": "تم إنشاء الطلب بنجاح",
        "order": {
            "id": str(order.id),
            "external_reference": order.external_reference,
            "status": order.status,
            "customer_id": str(order.customer_id),
            "customer_name": customer.display_name,
        },
    }


@router.post("/assignments")
async def create_assignment(
    payload: AssignmentCreateRequest,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    try:
        account_uuid = uuid.UUID(payload.account_id)
        order_uuid = uuid.UUID(payload.order_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="معرف الحساب أو الطلب غير صالح")

    try:
        assignment = await assign_account(
            session,
            account_id=account_uuid,
            order_id=order_uuid,
            actor_admin_id=admin.id,
            reassign_reason=payload.reassign_reason.strip() if payload.reassign_reason else None,
        )
    except (ValueError, IntegrityError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {
        "status": "success",
        "message": "تم تخصيص الحساب للطلب بنجاح",
        "assignment_id": str(assignment.id),
    }


@router.post("/{order_id}/activation")
async def generate_activation_link(
    order_id: uuid.UUID,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    order = await session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="الطلب غير موجود")

    has_assignment = await session.scalar(
        select(AccountAssignment.id).where(
            AccountAssignment.order_id == order.id,
            AccountAssignment.revoked_at.is_(None),
        )
    )
    if not has_assignment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="خصص حسابًا للطلب أولاً لتفعيل الرابط",
        )

    link = settings.public_base_url.rstrip("/") + "/"
    await record(
        session,
        "order.shared_web_link_issued",
        "order",
        str(order.id),
        actor_admin_id=admin.id,
        metadata={"link": link},
    )

    return {
        "status": "success",
        "link": link,
        "external_reference": order.external_reference,
    }
