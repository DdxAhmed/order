from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_db_session_commit, require_admin_roles
from app.audit import record
from app.config import get_settings
from app.integrations.salla import install_url
from app.models import (
    AdminRole,
    AdminSession,
    AdminUser,
    SallaMerchantAuthorization,
    SallaProductMapping,
    UsagePolicy,
)
from app.services.non_sensitive_services import (
    is_registered_non_sensitive_service,
    registered_service_keys,
)

router = APIRouter(prefix="/admin/salla", tags=["Admin Salla"])
settings = get_settings()


class MappingCreateRequest(BaseModel):
    merchant_id: int
    product_id: Optional[str] = None
    sku: Optional[str] = None
    service_key: str


class PolicySaveRequest(BaseModel):
    service_key: str
    max_uses: int
    period_seconds: int
    cooldown_seconds: int


@router.get("")
async def get_salla_admin_data(
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value, AdminRole.SUPPORT.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    auths = (
        await session.scalars(
            select(SallaMerchantAuthorization).order_by(SallaMerchantAuthorization.merchant_id)
        )
    ).all()
    mappings = (
        await session.scalars(
            select(SallaProductMapping).order_by(SallaProductMapping.created_at.desc()).limit(100)
        )
    ).all()
    policies = (
        await session.scalars(select(UsagePolicy).order_by(UsagePolicy.service_key))
    ).all()

    return {
        "authorizations": [
            {
                "id": str(a.id),
                "merchant_id": a.merchant_id,
                "merchant_name": a.merchant_name,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in auths
        ],
        "mappings": [
            {
                "id": str(m.id),
                "merchant_id": m.merchant_id,
                "product_id": m.product_id,
                "sku": m.sku,
                "service_key": m.service_key,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in mappings
        ],
        "policies": [
            {
                "id": str(p.id),
                "service_key": p.service_key,
                "max_uses": p.max_uses,
                "period_seconds": p.period_seconds,
                "cooldown_seconds": p.cooldown_seconds,
                "is_active": p.is_active,
            }
            for p in policies
        ],
        "registered_services": registered_service_keys(),
        "install_url": install_url(),
    }


@router.post("/mappings")
async def create_mapping(
    payload: MappingCreateRequest,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    key = payload.service_key.strip()
    if not is_registered_non_sensitive_service(key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لا توجد خدمة عامة منفذة ومراجعة بهذا المفتاح",
        )

    pid_str = payload.product_id.strip() if payload.product_id else ""
    sku_str = payload.sku.strip() if payload.sku else ""
    if not pid_str and not sku_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="أدخل معرف المنتج الرقمي أو رمز SKU",
        )

    mapping = SallaProductMapping(
        merchant_id=payload.merchant_id,
        product_id=int(pid_str) if pid_str.isdigit() else None,
        sku=sku_str or None,
        service_key=key,
    )
    session.add(mapping)
    try:
        await session.flush()
    except (ValueError, IntegrityError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="تعذر حفظ الربط؛ تحقق من صحة القيم أو عدم التكرار",
        )

    if not await session.scalar(select(UsagePolicy).where(UsagePolicy.service_key == key)):
        session.add(
            UsagePolicy(
                service_key=key,
                max_uses=settings.salla_usage_max,
                period_seconds=settings.salla_usage_period_seconds,
                cooldown_seconds=settings.salla_usage_cooldown_seconds,
            )
        )

    await record(
        session,
        "salla.mapping_created",
        "salla_product_mapping",
        str(mapping.id),
        actor_admin_id=admin.id,
        metadata={"merchant_id": payload.merchant_id, "service_key": key},
    )

    return {"status": "success", "id": str(mapping.id), "message": "تم حفظ ربط المنتج بنجاح"}


@router.post("/policies")
async def save_policy(
    payload: PolicySaveRequest,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    key = payload.service_key.strip()
    if not is_registered_non_sensitive_service(key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لا توجد خدمة عامة منفذة ومراجعة بهذا المفتاح",
        )

    if not (1 <= payload.max_uses <= 100 and 60 <= payload.period_seconds <= 604800 and 0 <= payload.cooldown_seconds <= 3600):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="قيم سياسة الاستخدام غير صالحة")

    policy = await session.scalar(
        select(UsagePolicy).where(UsagePolicy.service_key == key).with_for_update()
    )
    if not policy:
        policy = UsagePolicy(service_key=key)
        session.add(policy)

    policy.max_uses = payload.max_uses
    policy.period_seconds = payload.period_seconds
    policy.cooldown_seconds = payload.cooldown_seconds
    policy.is_active = True

    await record(
        session,
        "salla.usage_policy_saved",
        "usage_policy",
        str(policy.id),
        actor_admin_id=admin.id,
        metadata={"service_key": key, "max_uses": payload.max_uses},
    )

    return {"status": "success", "message": "تم حفظ سياسة الاستخدام بنجاح"}
