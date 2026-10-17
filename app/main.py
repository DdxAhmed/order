from __future__ import annotations

import asyncio
import json
import logging
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, update

from app.api import api_router
from app.audit import record
from app.bot import feed_webhook_update
from app.config import get_settings
from app.db import SessionLocal, engine
from app.integrations.salla import merchant_id_from_payload, token_expiry, verify_webhook_signature
from app.mail.imap_provider import MailProviderError
from app.mail.microsoft import exchange_authorization_code
from app.models import (
    LocalAccessSession,
    LocalUsageIdentity,
    Mailbox,
    MailboxOAuthState,
    SallaMerchantAuthorization,
    SallaOrderVerification,
    SallaWebhookEvent,
    TelegramUpdate,
)
from app.security import (
    decrypt_secret,
    encrypt_salla_secret,
    encrypt_secret,
    sha256,
    utcnow,
)
from app.services.local_access import consume_local_usage
from app.services.non_sensitive_services import is_registered_non_sensitive_service
from app.web.deps import current_admin

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="OrderTrofy API",
    description="OrderTrofy Backend REST API serving React frontend and external integrations",
    docs_url="/api/docs",
    redoc_url=None,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://ordertrofy.store",
        "https://www.ordertrofy.store",
        "https://api.ordertrofy.store",
    ],
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1)(:[0-9]+)?|https://([a-zA-Z0-9-]+\.)*vercel\.app)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount versioned API routes under /api/v1
app.include_router(api_router)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    # Enforce request size limit (10MB max body)
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 10 * 1024 * 1024:
                return Response(
                    content=json.dumps({"detail": "حجم الطلب يتجاوز الحد الأقصى المسموح"}),
                    status_code=413,
                    media_type="application/json",
                )
        except ValueError:
            pass

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    headers = getattr(exc, "headers", None) or {}
    return Response(
        content=json.dumps({"detail": exc.detail}),
        status_code=exc.status_code,
        media_type="application/json",
        headers=headers,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception on %s %s", request.method, request.url.path)
    return Response(
        content=json.dumps({"detail": "حدث خطأ غير متوقع في الخادم، يرجى المحاولة لاحقاً"}),
        status_code=500,
        media_type="application/json",
    )


@app.get("/")
async def root() -> dict[str, str]:
    """Root API endpoint returning metadata and health confirmation in JSON."""
    return {
        "service": "ordertrofy-api",
        "status": "ok",
        "docs": "/api/docs",
    }


@app.get("/health")
async def health_check():
    try:
        async with SessionLocal() as session:
            await session.execute(select(func.now()))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return Response(
            content=json.dumps({"status": "unhealthy", "error": str(e)}),
            status_code=503,
            media_type="application/json",
        )


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    try:
        async with engine.connect() as connection:
            await connection.execute(select(1))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="not ready") from exc
    return {"status": "ready"}


async def local_access_context(request: Request, session: object):
    token = request.headers.get("x-local-session") or request.cookies.get("local_access_session")
    if not token and "authorization" in request.headers:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split("Bearer ", 1)[1].strip()
    if not token:
        return None
    found = await session.scalar(
        select(LocalAccessSession).where(
            LocalAccessSession.token_hash == sha256(token),
            LocalAccessSession.revoked_at.is_(None),
            LocalAccessSession.expires_at > utcnow(),
        )
    )
    return found


# --- Preserved Non-Versioned Integrations and Webhooks ---


@app.post("/api/services/{service_key}/use")
async def use_authorized_service(
    request: Request,
    service_key: str,
    idempotency_key: str = Form(...),
    csrf_token: str = Form(""),
) -> dict[str, object]:
    if not service_key or len(service_key) > 100 or not idempotency_key or len(idempotency_key) > 160:
        raise HTTPException(status_code=400, detail="invalid_request")
    if not is_registered_non_sensitive_service(service_key):
        raise HTTPException(status_code=404, detail="service_not_available")
    async with SessionLocal.begin() as session:
        access = await local_access_context(request, session)
        if not access:
            raise HTTPException(status_code=403, detail="forbidden")
        if csrf_token and csrf_token != access.csrf_token:
            raise HTTPException(status_code=403, detail="forbidden")
        identity = await session.get(LocalUsageIdentity, access.identity_id)
        if not identity:
            raise HTTPException(status_code=403, detail="local_access_unavailable")
        result = await consume_local_usage(
            session,
            identity_id=identity.id,
            service_key=service_key,
            idempotency_key=idempotency_key,
        )
    if not result["accepted"]:
        status_code = 429 if result.get("reason") == "cooldown" else 403
        raise HTTPException(status_code=status_code, detail=result)
    return result


@app.post("/api/integrations/salla/webhook")
async def salla_webhook(request: Request) -> dict[str, object]:
    body = await request.body()
    secret = settings.salla_webhook_secret.get_secret_value() if settings.salla_webhook_secret else None
    strategy = request.headers.get("X-Salla-Security-Strategy", "Signature").casefold()
    signature = request.headers.get("X-Salla-Signature")
    if strategy != "signature" or not verify_webhook_signature(body, signature, secret):
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid_json") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("event"), str):
        raise HTTPException(status_code=400, detail="invalid_payload")
    event_name = payload["event"]
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    merchant_id = merchant_id_from_payload(payload, data)
    event_key = sha256(body)
    async with SessionLocal.begin() as session:
        existing = await session.scalar(select(SallaWebhookEvent).where(SallaWebhookEvent.event_key == event_key))
        if existing:
            return {"ok": True, "duplicate": True}
        session.add(SallaWebhookEvent(event_key=event_key, event_name=event_name, merchant_id=merchant_id, processed_at=utcnow()))
        if event_name == "app.store.authorize":
            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")
            expires = data.get("expires")
            if merchant_id is None or not isinstance(access_token, str) or not isinstance(refresh_token, str):
                raise HTTPException(status_code=400, detail="invalid_authorization_payload")
            try:
                expiry = token_expiry(expires)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="invalid_authorization_expiry") from exc
            auth = await session.scalar(select(SallaMerchantAuthorization).where(SallaMerchantAuthorization.merchant_id == merchant_id).with_for_update())
            if not auth:
                auth = SallaMerchantAuthorization(merchant_id=merchant_id, access_token_ciphertext=encrypt_salla_secret(access_token), refresh_token_ciphertext=encrypt_salla_secret(refresh_token), token_expires_at=expiry, scopes=str(data.get("scope") or ""))
                session.add(auth)
            else:
                auth.access_token_ciphertext = encrypt_salla_secret(access_token)
                auth.refresh_token_ciphertext = encrypt_salla_secret(refresh_token)
                auth.token_expires_at = expiry
                auth.scopes = str(data.get("scope") or auth.scopes)
                auth.revoked_at = None
                auth.last_error_code = None
        elif event_name == "app.uninstalled" and merchant_id is not None:
            auth = await session.scalar(select(SallaMerchantAuthorization).where(SallaMerchantAuthorization.merchant_id == merchant_id).with_for_update())
            if auth:
                auth.revoked_at = utcnow()
        elif event_name in {"order.cancelled", "order.refunded", "order.deleted"} and merchant_id is not None:
            raw_order_id = data.get("id") or data.get("order_id")
            raw_reference = data.get("reference_id") or data.get("reference")
            query = update(SallaOrderVerification).where(SallaOrderVerification.merchant_id == merchant_id)
            if raw_order_id is not None:
                try:
                    query = query.where(SallaOrderVerification.salla_order_id == int(raw_order_id))
                except (TypeError, ValueError):
                    raw_order_id = None
            if raw_order_id is None and raw_reference:
                query = query.where(SallaOrderVerification.reference_id == str(raw_reference))
            if raw_order_id is not None or raw_reference:
                await session.execute(query.values(revoked_at=utcnow(), payment_eligible=False))
    return {"ok": True}


@app.get("/admin/mailboxes/oauth/callback")
async def mailbox_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> dict[str, str]:
    request.scope["query_string"] = b""
    if error or not code or not state:
        raise HTTPException(status_code=400, detail="لم تكتمل موافقة Microsoft OAuth2")
    async with SessionLocal() as session:
        try:
            admin, _ = await current_admin(request, session)
        except HTTPException as exc:
            if exc.status_code == 401:
                logger.warning("microsoft_oauth_callback_failed stage=session_cookie reason=missing_admin_session")
                raise HTTPException(status_code=401, detail="انتهت جلسة الإدارة؛ سجّل الدخول وابدأ ربط Outlook من جديد")
            raise
        pending = await session.scalar(
            select(MailboxOAuthState)
            .where(
                MailboxOAuthState.state_hash == sha256(state),
                MailboxOAuthState.admin_id == admin.id,
                MailboxOAuthState.used_at.is_(None),
                MailboxOAuthState.expires_at > utcnow(),
            )
        )
        if not pending:
            logger.warning("microsoft_oauth_callback_failed stage=state_validation reason=missing_or_expired_state")
            raise HTTPException(status_code=400, detail="رابط OAuth2 منتهٍ أو غير صالح؛ ابدأ الربط من جديد")
        if not pending.code_verifier_encrypted:
            logger.warning("microsoft_oauth_callback_failed stage=pkce_lookup reason=missing_verifier")
            raise HTTPException(status_code=400, detail="حالة OAuth2 قديمة؛ ابدأ الربط من جديد")
        try:
            code_verifier = decrypt_secret(pending.code_verifier_encrypted)
        except Exception:
            logger.warning("microsoft_oauth_callback_failed stage=pkce_lookup reason=decrypt_failed")
            raise HTTPException(status_code=500, detail="تعذر استعادة جلسة OAuth2؛ ابدأ الربط من جديد")
    try:
        token_result = await asyncio.to_thread(exchange_authorization_code, code, code_verifier)
    except MailProviderError as exc:
        reason = str(exc) if str(exc).isidentifier() else "provider_error"
        logger.warning("microsoft_oauth_callback_failed stage=token_exchange reason=%s", reason)
        raise HTTPException(status_code=400, detail="تعذر إكمال ربط Microsoft؛ ابدأ الربط من جديد")
    except Exception:
        logger.warning("microsoft_oauth_callback_failed stage=token_exchange reason=unexpected_error")
        raise HTTPException(status_code=500, detail="تعذر إكمال ربط Microsoft؛ ابدأ الربط من جديد")
    refresh_token = token_result.get("refresh_token")
    if not refresh_token:
        logger.warning("microsoft_oauth_callback_failed stage=token_response reason=missing_refresh_token")
        raise HTTPException(status_code=400, detail="لم تُرجع Microsoft Refresh Token؛ ابدأ الربط من جديد")
    try:
        async with SessionLocal.begin() as session:
            try:
                admin, _ = await current_admin(request, session)
            except HTTPException as exc:
                if exc.status_code == 401:
                    logger.warning("microsoft_oauth_callback_failed stage=session_cookie reason=missing_admin_session_after_exchange")
                    raise HTTPException(status_code=401, detail="انتهت جلسة الإدارة؛ سجّل الدخول وابدأ ربط Outlook من جديد")
                raise
            pending = await session.scalar(
                select(MailboxOAuthState)
                .where(MailboxOAuthState.state_hash == sha256(state), MailboxOAuthState.admin_id == admin.id)
                .with_for_update()
            )
            if not pending or pending.used_at is not None or pending.expires_at <= utcnow():
                logger.warning("microsoft_oauth_callback_failed stage=state_validation reason=used_or_expired_state")
                raise HTTPException(status_code=400, detail="تم استخدام رابط OAuth2 أو انتهت صلاحيته؛ ابدأ الربط من جديد")
            mailbox = await session.scalar(select(Mailbox).where(Mailbox.label == pending.label).with_for_update())
            if mailbox and mailbox.auth_mode != "microsoft_graph":
                logger.warning("microsoft_oauth_callback_failed stage=database_storage reason=mailbox_mode_conflict")
                raise HTTPException(status_code=400, detail="اسم صندوق البريد مستخدم بطريقة IMAP؛ اختر اسمًا جديدًا")
            if not mailbox:
                mailbox = Mailbox(
                    label=pending.label,
                    host="graph.microsoft.com",
                    port=443,
                    username=pending.username,
                    encrypted_password=None,
                    auth_mode="microsoft_graph",
                    oauth_refresh_token=encrypt_secret(str(refresh_token)),
                )
                session.add(mailbox)
            else:
                mailbox.host = "graph.microsoft.com"
                mailbox.port = 443
                mailbox.username = pending.username
                mailbox.encrypted_password = None
                mailbox.auth_mode = "microsoft_graph"
                mailbox.oauth_refresh_token = encrypt_secret(str(refresh_token))
                mailbox.is_active = True
            pending.used_at = utcnow()
            await record(
                session,
                "mailbox.oauth_connected",
                "mailbox",
                pending.label,
                actor_admin_id=admin.id,
                metadata={"provider": "microsoft_graph", "username": pending.username},
            )
    except HTTPException:
        raise
    except Exception:
        logger.warning("microsoft_oauth_callback_failed stage=database_storage reason=unexpected_error")
        raise HTTPException(status_code=500, detail="تعذر حفظ صندوق Outlook؛ ابدأ الربط من جديد")
    return {"status": "success", "message": "تم ربط بريد Outlook عبر OAuth2 بنجاح"}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> Response:
    expected = settings.telegram_webhook_secret.get_secret_value() if settings.telegram_webhook_secret else None
    if not expected or request.headers.get("X-Telegram-Bot-Api-Secret-Token") != expected:
        raise HTTPException(status_code=403, detail="forbidden")
    payload = await request.json()
    update_id = payload.get("update_id")
    if not isinstance(update_id, int):
        raise HTTPException(status_code=400, detail="invalid update")
    async with SessionLocal() as session:
        if await session.get(TelegramUpdate, update_id):
            return Response(status_code=200)
    await feed_webhook_update(payload)
    async with SessionLocal.begin() as session:
        if not await session.get(TelegramUpdate, update_id):
            session.add(TelegramUpdate(update_id=update_id))
    return Response(status_code=200)
