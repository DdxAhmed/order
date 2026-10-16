from __future__ import annotations

import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_db_session_commit, require_admin_roles
from app.audit import record
from app.models import AdminRole, AdminSession, AdminUser, Customer, Order

router = APIRouter(prefix="/admin/customers", tags=["Admin Customers"])


class CustomerCreateRequest(BaseModel):
    display_name: str
    telegram_user_id: Optional[int] = None
    notes: Optional[str] = None


@router.get("")
async def list_customers(
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value, AdminRole.SUPPORT.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    customers = (await session.scalars(select(Customer).order_by(Customer.created_at.desc()).limit(150))).all()

    # Get order counts per customer
    order_counts_raw = (
        await session.execute(
            select(Order.customer_id, func.count()).group_by(Order.customer_id)
        )
    ).all()
    order_counts = {cid: cnt for cid, cnt in order_counts_raw}

    data = [
        {
            "id": str(c.id),
            "display_name": c.display_name,
            "telegram_user_id": c.telegram_user_id,
            "notes": c.notes,
            "orders_count": order_counts.get(c.id, 0),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in customers
    ]

    return {"customers": data}


@router.post("")
async def create_customer(
    payload: CustomerCreateRequest,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    clean_name = payload.display_name.strip()
    if not clean_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="اسم العميل مطلوب")

    customer = Customer(
        display_name=clean_name,
        telegram_user_id=payload.telegram_user_id,
        notes=payload.notes.strip() if payload.notes else None,
    )
    session.add(customer)
    await session.flush()

    await record(
        session,
        "customer.created",
        "customer",
        str(customer.id),
        actor_admin_id=admin.id,
    )

    return {
        "status": "success",
        "message": "تمت إضافة العميل بنجاح",
        "customer": {
            "id": str(customer.id),
            "display_name": customer.display_name,
            "telegram_user_id": customer.telegram_user_id,
            "notes": customer.notes,
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
        },
    }
