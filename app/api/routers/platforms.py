from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_db_session_commit, require_admin_roles
from app.audit import record
from app.models import AdminRole, AdminSession, AdminUser, Platform

router = APIRouter(prefix="/admin/platforms", tags=["Admin Platforms"])


class SteamConfigRequest(BaseModel):
    profile: dict[str, Any]
    enable: bool = False


@router.get("")
async def list_platforms(
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value, AdminRole.SUPPORT.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    platforms = (await session.scalars(select(Platform).order_by(Platform.name))).all()
    steam = next((p for p in platforms if p.code == "steam"), None)

    return {
        "platforms": [
            {
                "id": str(p.id),
                "code": p.code,
                "name": p.name,
                "is_enabled": p.is_enabled,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in platforms
        ],
        "steam": {
            "id": str(steam.id) if steam else None,
            "is_enabled": steam.is_enabled if steam else False,
            "mail_profile": steam.mail_profile if steam else {},
        }
        if steam
        else None,
    }


@router.post("/steam")
async def update_steam_platform(
    payload: SteamConfigRequest,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    profile = payload.profile

    if payload.enable and not {"sender_domains", "account_pattern", "code_pattern", "required_auth_result", "sample_verified_at"}.issubset(profile):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="يلزم توثيق العينة وإدخال قواعد المطابقة المطلوبة قبل التفعيل",
        )

    steam = await session.scalar(select(Platform).where(Platform.code == "steam").with_for_update())
    if not steam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="منصة Steam غير موجودة")

    steam.mail_profile = profile
    steam.is_enabled = payload.enable

    await record(
        session,
        "platform.steam_configured",
        "platform",
        str(steam.id),
        actor_admin_id=admin.id,
        metadata={"enabled": steam.is_enabled, "profile_keys": list(profile.keys())},
    )

    return {
        "status": "success",
        "message": "تم حفظ إعدادات منصة Steam بنجاح",
        "is_enabled": steam.is_enabled,
    }
