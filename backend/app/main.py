from __future__ import annotations

import hashlib
import asyncio
import json
import logging
import re
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.audit import record
from app.bot import feed_webhook_update
from app.config import get_settings
from app.db import SessionLocal, engine
from app.i18n import language_meta, normalize_language, translate
from app.models import (
    AccountAssignment,
    AdminRole,
    AdminUser,
    AuditEvent,
    Customer,
    CustomerSession,
    ImportBatch,
    ImportRow,
    InventoryAccount,
    InventoryStatus,
    LocalAccessSession,
    LocalUsageIdentity,
    Mailbox,
    MailboxOAuthState,
    Order,
    Platform,
    VerificationRequest,
    SallaMerchantAuthorization,
    SallaOrderVerification,
    SallaProductMapping,
    SallaWebhookEvent,
    UsagePolicy,
)
from app.security import decrypt_secret, encrypt_salla_secret, encrypt_secret, mask_account_identifier, new_random_token, sha256, utcnow, verify_password
from app.mail.microsoft import (
    build_authorization_url,
    exchange_authorization_code,
    microsoft_oauth_configured,
    pkce_challenge,
    pkce_verifier,
)
from app.mail import ImapMailProvider, MicrosoftGraphMailProvider
from app.mail.imap_provider import MailProviderError
from app.platforms import (
    INVENTORY_PLATFORM_CODES,
    PLATFORM_CATALOG,
    SUPPORTED_PLATFORM_CODES,
    is_supported_platform,
)
from app.services.access import check_login_rate_limit, consume_rate_limit, create_admin_session, revoke_admin_session
from app.services.csv_import import CsvImportError, parse_inventory_csv, prepare_inventory_rows
from app.services.inventory import assign_account, normalize_identifier
from app.services.inventory import create_verification_request
from app.services.customer import (
    CustomerAccessError,
    access_order_for_web,
    activate_order_for_web,
    assignments_for_web,
    get_customer_web_session,
    result_for_web,
    verification_statuses_for_web,
)
from app.web.deps import check_csrf, current_admin, require_role
from app.integrations.salla import install_url, merchant_id_from_payload, token_expiry, verify_webhook_signature
from app.services.local_access import (
    LocalAccessError,
    consume_local_usage,
    create_local_access,
    local_usage_summaries,
)
from app.services.non_sensitive_services import is_registered_non_sensitive_service, registered_service_keys

from fastapi.middleware.cors import CORSMiddleware
from app.api import api_router

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))
settings = get_settings()
app = FastAPI(title="Steam Code Delivery", docs_url="/api/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://ordertrofy.store",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
logger = logging.getLogger(__name__)


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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception on %s %s", request.method, request.url.path)
    return Response(
        content=json.dumps({"detail": "حدث خطأ غير متوقع في الخادم، يرجى المحاولة لاحقاً"}),
        status_code=500,
        media_type="application/json",
    )


@app.get("/health")
async def health_check():
    try:
        async with SessionLocal() as session:
            await session.execute(select(func.now()))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return Response(content=json.dumps({"status": "unhealthy", "error": str(e)}), status_code=503, media_type="application/json")


async def local_access_context(request: Request, session: object):
    token = request.cookies.get("local_access_session")
    if not token:
        return None
    found = await session.scalar(select(LocalAccessSession).where(LocalAccessSession.token_hash == sha256(token), LocalAccessSession.revoked_at.is_(None), LocalAccessSession.expires_at > utcnow()))  # type: ignore[attr-defined]
    return found


def redirect(path: str, message: str | None = None) -> RedirectResponse:
    if message:
        joiner = "&" if "?" in path else "?"
        path = f"{path}{joiner}message={quote(message)}"
    return RedirectResponse(path, status_code=303)


def page(request: Request, name: str, **context: object) -> HTMLResponse:
    context.setdefault("message", request.query_params.get("message"))
    # The customer-facing product remains Arabic-first, while a safe query
    # parameter lets support preview the same layout in English/LTR. Steam
    # email language parsing is independent from portal copy.
    requested_language = context.pop("language", None) or request.query_params.get("lang")
    language = normalize_language(str(requested_language or "ar"))
    context.setdefault("lang", language)
    context.setdefault("direction", language_meta(language)["direction"])
    context.setdefault("t", lambda key, **values: translate(language, key, **values))
    return templates.TemplateResponse(request, name, context)


def notification_profile_values(
    sender_domains: str,
    subject_patterns: str,
) -> tuple[list[str], list[str]]:
    """Parse the admin's explicit trust profile without widening it implicitly."""
    domains = [item.strip().casefold().lstrip("@") for item in re.split(r"[,\n]", sender_domains) if item.strip()]
    patterns = [item.strip() for item in subject_patterns.splitlines() if item.strip()]
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", domain) for domain in domains):
        raise ValueError("نطاق المرسل غير صالح")
    if len(domains) > 20 or len(patterns) > 20 or any(len(pattern) > 240 for pattern in patterns):
        raise ValueError("ملف الثقة كبير جدًا")
    try:
        for pattern in patterns:
            literal_signal = re.sub(r"\\.|[\^$.*+?()[\]{}|]", "", pattern)
            if not re.search(r"[A-Za-z0-9\u0600-\u06ff]", literal_signal):
                raise ValueError("نمط عنوان الرسالة واسع جدًا")
            re.compile(pattern, re.IGNORECASE)
    except (re.error, ValueError) as exc:
        raise ValueError("نمط عنوان الرسالة غير صالح") from exc
    return domains, patterns


async def admin_page_context(request: Request, session: object) -> dict:
    admin, admin_session = await current_admin(request, session)  # type: ignore[arg-type]
    return {"admin": admin, "csrf_token": admin_session.csrf_token}


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


@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    """The store's public entry point lives at the purchased domain root."""
    return await local_access_page(request)


@app.get("/salla", response_class=HTMLResponse)
async def salla_form(request: Request) -> HTMLResponse:
    # Preserve existing bookmarked links while keeping the customer-facing URL
    # at the domain root.
    return RedirectResponse("/", status_code=308)


async def local_access_page(
    request: Request,
    *,
    message: str | None = None,
    selected_platform: str = "steam",
    active_platform: str | None = None,
    services: list[dict[str, int | str]] | None = None,
) -> HTMLResponse:
    """Render the complete, non-sensitive local-access flow on one page."""
    if active_platform is None:
        async with SessionLocal() as session:
            access = await local_access_context(request, session)
            if access:
                identity = await session.get(LocalUsageIdentity, access.identity_id)
                if identity:
                    selected_platform = identity.platform_code
                    active_platform = identity.platform_code
                    services = await local_usage_summaries(session, identity_id=identity.id)
    return page(
        request,
        "salla.html",
        admin=None,
        verified=None,
        message=message,
        platforms=PLATFORM_CATALOG,
        selected_platform=selected_platform,
        active_platform=active_platform,
        services=services or [],
    )


@app.post("/", response_class=HTMLResponse)
@app.post("/access")
@app.post("/salla/access")
async def create_usage_access(
    request: Request,
    order_reference: str = Form(),
    account_alias: str = Form(""),
    platform_code: str = Form("steam"),
) -> Response:
    async with SessionLocal.begin() as session:
        client_ip = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip() or (request.client.host if request.client else "unknown")
        if not await consume_rate_limit(session, "local_access_ip", client_ip, 900, 10):
            return await local_access_page(request, message="تم تجاوز عدد المحاولات المؤقتة، حاول لاحقًا", selected_platform=platform_code)
        session_cookie = request.cookies.get("local_access_session")
        if session_cookie and not await consume_rate_limit(session, "local_access_session", session_cookie, 900, 20):
            return await local_access_page(request, message="تم تجاوز عدد المحاولات المؤقتة، حاول لاحقًا", selected_platform=platform_code)
        try:
            raw_token, access, identity = await create_local_access(
                session,
                order_reference=order_reference,
                account_alias=account_alias,
                platform_code=platform_code,
                session_minutes=settings.salla_customer_session_minutes,
            )
        except LocalAccessError as exc:
            return await local_access_page(request, message=str(exc), selected_platform=platform_code)
        services = await local_usage_summaries(session, identity_id=identity.id)
        canonical_platform = identity.platform_code
    response = await local_access_page(
        request,
        message="تم فتح جلسة الاستخدام",
        selected_platform=canonical_platform,
        active_platform=canonical_platform,
        services=services,
    )
    response.set_cookie("local_access_session", raw_token, httponly=True, secure=settings.cookie_secure, samesite="strict", max_age=settings.salla_customer_session_minutes * 60, path="/")
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/access/status", response_class=HTMLResponse)
@app.get("/salla/status", response_class=HTMLResponse)
async def salla_status(request: Request) -> HTMLResponse:
    return await local_access_page(request)


@app.post("/api/services/{service_key}/use")
async def use_authorized_service(request: Request, service_key: str, idempotency_key: str = Form(), csrf_token: str = Form()) -> dict[str, object]:
    if not service_key or len(service_key) > 100 or not idempotency_key or len(idempotency_key) > 160:
        raise HTTPException(status_code=400, detail="invalid_request")
    if not is_registered_non_sensitive_service(service_key):
        raise HTTPException(status_code=404, detail="service_not_available")
    async with SessionLocal.begin() as session:
        access = await local_access_context(request, session)
        if not access or csrf_token != access.csrf_token:
            raise HTTPException(status_code=403, detail="forbidden")
        identity = await session.get(LocalUsageIdentity, access.identity_id)
        if not identity:
            raise HTTPException(status_code=403, detail="local_access_unavailable")
        result = await consume_local_usage(session, identity_id=identity.id, service_key=service_key, idempotency_key=idempotency_key)
    if not result["accepted"]:
        status = 429 if result.get("reason") == "cooldown" else 403
        raise HTTPException(status_code=status, detail=result)
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


def set_customer_cookie(response: Response, raw_token: str, expires_at: object) -> None:
    max_age = max(1, int((expires_at - utcnow()).total_seconds()))  # type: ignore[operator]
    response.set_cookie(
        "customer_session",
        raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=max_age,
        path="/",
    )


@app.get("/activate/{raw_token}", response_class=HTMLResponse)
async def activate_form(request: Request, raw_token: str) -> HTMLResponse:
    response = page(request, "activate_web.html", admin=None, raw_token=raw_token)
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/activate")
async def activate_web(request: Request, activation_token: str = Form()) -> Response:
    subject = f"{request.client.host if request.client else 'unknown'}:{activation_token[:16]}"
    async with SessionLocal.begin() as session:
        if not await consume_rate_limit(session, "web_activation", subject, 900, 10):
            return redirect("/", "تم تجاوز عدد المحاولات المؤقتة")
        try:
            raw_session, customer_session = await activate_order_for_web(session, activation_token.strip())
        except CustomerAccessError:
            return redirect("/", "رابط التفعيل غير صالح أو منتهٍ")
    response = redirect("/portal", "تم تفعيل الطلب")
    set_customer_cookie(response, raw_session, customer_session.expires_at)
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.post("/customer/access")
async def customer_access(
    request: Request,
    order_reference: str = Form(),
    steam_username: str = Form(),
    platform_code: str = Form("steam"),
) -> Response:
    """Open the shared customer portal using the order reference and Steam user."""
    if platform_code.strip().casefold() != "steam":
        return redirect("/", "هذه المنصة متاحة لإدارة المخزون فقط حاليًا")
    clean_reference = order_reference.strip()
    clean_username = steam_username.strip()
    client_ip = request.client.host if request.client else "unknown"
    subject = f"{client_ip}:{sha256(clean_reference.casefold() + ':' + clean_username.casefold())}"
    async with SessionLocal.begin() as session:
        # Apply both an IP-wide limit and a per-identity limit. Using only a
        # hash of the submitted values would let an attacker bypass throttling
        # by changing the guess on every request.
        if not await consume_rate_limit(session, "web_identity_ip", client_ip, 900, 30):
            return redirect("/", "تم تجاوز عدد المحاولات المؤقتة، حاول لاحقًا")
        if not await consume_rate_limit(session, "web_identity", subject, 900, 8):
            return redirect("/", "تم تجاوز عدد المحاولات المؤقتة، حاول لاحقًا")
        try:
            raw_session, customer_session = await access_order_for_web(
                session,
                external_reference=clean_reference,
                account_identifier=clean_username,
                platform_code=platform_code,
            )
        except CustomerAccessError:
            return redirect("/", "رقم الطلب أو User Steam غير صحيح")
    response = redirect("/portal", "تم فتح الطلب")
    set_customer_cookie(response, raw_session, customer_session.expires_at)
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


async def customer_page_context(request: Request, session: object) -> tuple[Customer, CustomerSession] | None:
    return await get_customer_web_session(session, request.cookies.get("customer_session"))  # type: ignore[arg-type]


@app.get("/portal", response_class=HTMLResponse)
async def customer_portal(request: Request) -> Response:
    async with SessionLocal() as session:
        found = await customer_page_context(request, session)
        if not found:
            return redirect("/", "افتح رابط التفعيل أولًا")
        customer, customer_session = found
        assignments = await assignments_for_web(session, customer.id)
        requests = await verification_statuses_for_web(session, customer_session.id)
        statuses = {}
        for item in requests:
            statuses.setdefault(item.assignment_id, item)
        request_results = {}
        for item in requests:
            result = await result_for_web(session, item.id, customer_session.id)
            if result:
                request_results[item.id] = result
        rows = [
            (assignment, mask_account_identifier(account.identifier), statuses.get(assignment.id))
            for assignment, account in assignments
        ]
        language = "ar"
        return page(
            request,
            "portal.html",
            admin=None,
            customer=customer,
            customer_session=customer_session,
            rows=rows,
            requests=requests,
            request_results=request_results,
            status_labels={
                status: translate(language, f"status_{status}")
                for status in (
                    "queued",
                    "processing",
                    "waiting_mail",
                    "succeeded",
                    "failed",
                    "expired",
                    "delivery_uncertain",
                )
            },
        )


@app.post("/portal/logout")
async def customer_logout(request: Request, csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        found = await customer_page_context(request, session)
        if found and csrf_token != found[1].csrf_token:
            raise HTTPException(status_code=403, detail="forbidden")
        if found:
            found[1].revoked_at = utcnow()
    response = redirect("/", "تم تسجيل الخروج")
    response.delete_cookie("customer_session", path="/")
    return response


@app.post("/portal/assignments/{assignment_id}/verify")
async def customer_request_code(request: Request, assignment_id: uuid.UUID, csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        found = await customer_page_context(request, session)
        if not found:
            return redirect("/", "انتهت جلسة العميل")
        customer, customer_session = found
        if csrf_token != customer_session.csrf_token:
            raise HTTPException(status_code=403, detail="forbidden")
        if not await consume_rate_limit(session, "web_verify", str(customer_session.id), 600, 5):
            return redirect("/portal", "تم تجاوز الحد المؤقت، حاول لاحقًا")
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
            return redirect("/portal", "لا يمكن الوصول إلى هذا الحساب")
        await create_verification_request(
            session,
            assignment,
            settings.verification_wait_seconds,
            web_session_id=customer_session.id,
        )
    return redirect("/portal", "تم استلام الطلب. حدّث الصفحة لمتابعة الحالة")


@app.get("/admin/login", response_class=HTMLResponse)
async def login_form(request: Request) -> HTMLResponse:
    return page(request, "login.html", admin=None)


@app.post("/admin/login")
async def login(request: Request, email: str = Form(), password: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        if not await check_login_rate_limit(session, f"{request.client.host if request.client else 'unknown'}:{email.casefold()}"):
            return redirect("/admin/login", "تم تجاوز عدد محاولات الدخول، حاول لاحقًا")
        admin = await session.scalar(select(AdminUser).where(AdminUser.email == email.strip().casefold()))
        if not admin or not admin.is_active or not verify_password(admin.password_hash, password):
            return redirect("/admin/login", "بيانات الدخول غير صحيحة")
        raw_session, db_session = await create_admin_session(session, admin)
    response = redirect("/admin")
    response.set_cookie(
        "admin_session",
        raw_session,
        httponly=True,
        secure=settings.cookie_secure,
        # Microsoft returns to this site via a top-level cross-site GET. Lax
        # sends the session cookie for that navigation while still blocking it
        # on cross-site POSTs; OAuth state and PKCE provide the CSRF binding.
        samesite="lax",
        max_age=int((db_session.expires_at - utcnow()).total_seconds()),
        path="/",
    )
    return response


@app.post("/admin/logout")
async def logout(request: Request, csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        _, auth_session = await current_admin(request, session)
        check_csrf(request, auth_session, csrf_token)
        await revoke_admin_session(session, request.cookies.get("admin_session"))
    response = redirect("/admin/login", "تم تسجيل الخروج")
    response.delete_cookie("admin_session", path="/")
    return response


@app.get("/admin", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    async with SessionLocal() as session:
        context = await admin_page_context(request, session)
        available = await session.scalar(select(func.count()).select_from(InventoryAccount).where(InventoryAccount.status == "available"))
        assigned = await session.scalar(select(func.count()).select_from(InventoryAccount).where(InventoryAccount.status == "assigned"))
        orders = await session.scalar(select(func.count()).select_from(Order))
        errors = await session.scalar(select(func.count()).select_from(VerificationRequest).where(VerificationRequest.status == "failed"))
        steam = await session.scalar(select(Platform).where(Platform.code == "steam"))
        status = "غير مهيأ"
        if steam:
            status = "جاهز للاختبار بعينة فعلية" if steam.is_enabled and steam.mail_profile.get("sample_verified_at") else "بانتظار عينة فعلية مصرح بها"
        return page(request, "dashboard.html", **context, counts={"available": available or 0, "assigned": assigned or 0, "orders": orders or 0, "errors": errors or 0}, steam_status=status)


@app.get("/admin/salla", response_class=HTMLResponse)
async def admin_salla(request: Request) -> HTMLResponse:
    async with SessionLocal() as session:
        context = await admin_page_context(request, session)
        auths = (await session.scalars(select(SallaMerchantAuthorization).order_by(SallaMerchantAuthorization.merchant_id))).all()
        mappings = (await session.scalars(select(SallaProductMapping).order_by(SallaProductMapping.created_at.desc()).limit(100))).all()
        policies = (await session.scalars(select(UsagePolicy).order_by(UsagePolicy.service_key))).all()
        return page(
            request,
            "salla_admin.html",
            **context,
            auths=auths,
            mappings=mappings,
            policies=policies,
            registered_services=registered_service_keys(),
            install_url=install_url(),
        )


@app.post("/admin/salla/mappings")
async def add_salla_mapping(request: Request, merchant_id: int = Form(), product_id: str = Form(""), sku: str = Form(""), service_key: str = Form(), csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value, AdminRole.OPERATOR.value})
        check_csrf(request, auth, csrf_token)
        key = service_key.strip()
        if not is_registered_non_sensitive_service(key):
            return redirect("/admin/salla", "لا توجد خدمة عامة منفذة ومراجعة بهذا المفتاح؛ لم يُحفظ أي ربط")
        if not key or len(key) > 100 or (not product_id.strip() and not sku.strip()) or (product_id.strip() and not product_id.strip().isdigit()):
            return redirect("/admin/salla", "أدخل service key ومعرف المنتج أو SKU")
        mapping = SallaProductMapping(merchant_id=merchant_id, product_id=int(product_id) if product_id.strip().isdigit() else None, sku=sku.strip() or None, service_key=key)
        session.add(mapping)
        try:
            await session.flush()
        except (ValueError, IntegrityError):
            await session.rollback()
            return redirect("/admin/salla", "تعذر حفظ الربط؛ تحقق من القيم أو التكرار")
        if not await session.scalar(select(UsagePolicy).where(UsagePolicy.service_key == key)):
            session.add(UsagePolicy(service_key=key, max_uses=settings.salla_usage_max, period_seconds=settings.salla_usage_period_seconds, cooldown_seconds=settings.salla_usage_cooldown_seconds))
        await record(session, "salla.mapping_created", "salla_product_mapping", str(mapping.id), actor_admin_id=admin.id, metadata={"merchant_id": merchant_id, "service_key": key})
    return redirect("/admin/salla", "تم حفظ ربط المنتج")


@app.post("/admin/salla/policies")
async def save_salla_policy(request: Request, service_key: str = Form(), max_uses: int = Form(), period_seconds: int = Form(), cooldown_seconds: int = Form(), csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value})
        check_csrf(request, auth, csrf_token)
        key = service_key.strip()
        if not is_registered_non_sensitive_service(key):
            return redirect("/admin/salla", "لا توجد خدمة عامة منفذة ومراجعة بهذا المفتاح؛ لم تُحفظ سياسة")
        if not key or not 1 <= max_uses <= 100 or not 60 <= period_seconds <= 604800 or not 0 <= cooldown_seconds <= 3600:
            return redirect("/admin/salla", "قيم سياسة الاستخدام غير صالحة")
        policy = await session.scalar(select(UsagePolicy).where(UsagePolicy.service_key == key).with_for_update())
        if not policy:
            policy = UsagePolicy(service_key=key)
            session.add(policy)
        policy.max_uses, policy.period_seconds, policy.cooldown_seconds, policy.is_active = max_uses, period_seconds, cooldown_seconds, True
        await record(session, "salla.usage_policy_saved", "usage_policy", str(policy.id), actor_admin_id=admin.id, metadata={"service_key": key, "max_uses": max_uses})
    return redirect("/admin/salla", "تم حفظ سياسة الاستخدام")


@app.get("/admin/accounts", response_class=HTMLResponse)
async def accounts_page(request: Request, q: str = "", status: str = "", platform: str = "") -> HTMLResponse:
    async with SessionLocal() as session:
        context = await admin_page_context(request, session)
        query = select(InventoryAccount, Platform.name, Mailbox.label).join(Platform).join(Mailbox).order_by(InventoryAccount.created_at.desc())
        if q.strip():
            query = query.where(InventoryAccount.normalized_identifier.contains(normalize_identifier(q)))
        if status in {item.value for item in InventoryStatus}:
            query = query.where(InventoryAccount.status == status)
        selected_platform = platform.strip().casefold()
        if selected_platform in SUPPORTED_PLATFORM_CODES:
            query = query.where(Platform.code == selected_platform)
        rows = (await session.execute(query.limit(100))).all()
        platforms = (
            await session.scalars(
                select(Platform).where(Platform.code.in_(INVENTORY_PLATFORM_CODES)).order_by(Platform.name)
            )
        ).all()
        mailboxes = (await session.scalars(select(Mailbox).where(Mailbox.is_active.is_(True)))).all()
        accounts = [{"id": a.id, "identifier": a.identifier, "status": a.status, "platform": p, "mailbox": m} for a, p, m in rows]
        return page(request, "accounts.html", **context, accounts=accounts, platforms=platforms, mailboxes=mailboxes, q=q, status=status, platform=selected_platform, statuses=[item.value for item in InventoryStatus])


@app.post("/admin/accounts")
async def add_account(request: Request, platform_id: str = Form(), mailbox_id: str = Form(), identifier: str = Form(), notes: str = Form(""), csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value, AdminRole.OPERATOR.value})
        check_csrf(request, auth, csrf_token)
        if not identifier.strip():
            return redirect("/admin/accounts", "معرف الحساب مطلوب")
        try:
            platform = await session.get(Platform, uuid.UUID(platform_id))
            mailbox_uuid = uuid.UUID(mailbox_id)
        except ValueError:
            platform = None
            mailbox_uuid = None
        mailbox = await session.get(Mailbox, mailbox_uuid) if mailbox_uuid is not None else None
        if not platform or not is_supported_platform(platform.code) or not mailbox:
            return redirect("/admin/accounts", "المنصة أو صندوق البريد غير صالح")
        account = InventoryAccount(platform_id=platform.id, mailbox_id=mailbox_uuid, identifier=identifier.strip(), normalized_identifier=normalize_identifier(identifier), notes=notes.strip() or None)
        session.add(account)
        try:
            await session.flush()
        except IntegrityError:
            return redirect("/admin/accounts", "هذا الحساب موجود بالفعل لهذه المنصة")
        await record(
            session,
            "inventory.account_created",
            "inventory_account",
            str(account.id),
            actor_admin_id=admin.id,
            metadata={"platform_code": platform.code, "platform_name": platform.name},
        )
    return redirect("/admin/accounts", "تمت إضافة الحساب")


@app.get("/admin/accounts/{account_id}/edit", response_class=HTMLResponse)
async def edit_account_page(request: Request, account_id: uuid.UUID) -> HTMLResponse:
    async with SessionLocal() as session:
        context = await admin_page_context(request, session)
        account = await session.get(InventoryAccount, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="الحساب غير موجود")
        mailboxes = (await session.scalars(select(Mailbox).where(Mailbox.is_active.is_(True)))).all()
        platforms = list(
            (await session.scalars(select(Platform).where(Platform.code.in_(INVENTORY_PLATFORM_CODES)).order_by(Platform.name))).all()
        )
        existing_platform = await session.get(Platform, account.platform_id)
        if existing_platform and existing_platform.id not in {item.id for item in platforms}:
            # Keep legacy records editable without making a disabled future
            # platform selectable for newly created inventory.
            platforms.insert(0, existing_platform)
        return page(request, "account_edit.html", **context, account=account, mailboxes=mailboxes, platforms=platforms)


@app.post("/admin/accounts/{account_id}/edit")
async def edit_account(
    request: Request,
    account_id: uuid.UUID,
    platform_id: str = Form(),
    identifier: str = Form(),
    mailbox_id: str = Form(),
    status: str | None = Form(None),
    notes: str = Form(""),
    csrf_token: str = Form(),
) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value, AdminRole.OPERATOR.value})
        check_csrf(request, auth, csrf_token)
        account = await session.scalar(select(InventoryAccount).where(InventoryAccount.id == account_id).with_for_update())
        if not account or not identifier.strip():
            return redirect("/admin/accounts", "الحساب غير موجود أو معرفه فارغ")
        try:
            platform = await session.get(Platform, uuid.UUID(platform_id))
            mailbox_uuid = uuid.UUID(mailbox_id)
        except ValueError:
            platform = None
            mailbox_uuid = None
        mailbox = await session.get(Mailbox, mailbox_uuid) if mailbox_uuid is not None else None
        is_legacy_current_platform = bool(account and platform and platform.id == account.platform_id and platform.code == "playstation")
        if not platform or (not is_supported_platform(platform.code) and not is_legacy_current_platform) or not mailbox:
            return redirect(f"/admin/accounts/{account_id}/edit", "المنصة أو صندوق البريد غير صالح")
        if account.status == InventoryStatus.ASSIGNED.value and platform.id != account.platform_id:
            return redirect(f"/admin/accounts/{account_id}/edit", "لا يمكن تغيير منصة حساب مخصص")
        editable_statuses = {
            InventoryStatus.AVAILABLE.value,
            InventoryStatus.RESERVED.value,
            InventoryStatus.DISABLED.value,
            InventoryStatus.ARCHIVED.value,
        }
        if account.status == InventoryStatus.ASSIGNED.value:
            if status not in {None, "", InventoryStatus.ASSIGNED.value}:
                return redirect(f"/admin/accounts/{account_id}/edit", "لا يمكن تغيير حالة حساب مخصص؛ استخدم إعادة التخصيص الصريحة")
        elif status not in editable_statuses:
            return redirect(f"/admin/accounts/{account_id}/edit", "اختر حالة الإتاحة الصحيحة للحساب")
        old_platform = await session.get(Platform, account.platform_id)
        old_platform_code = old_platform.code if old_platform else None
        old_status = account.status
        account.platform_id = platform.id
        account.identifier = identifier.strip()
        account.normalized_identifier = normalize_identifier(identifier)
        account.mailbox_id = mailbox_uuid
        if account.status != InventoryStatus.ASSIGNED.value and status:
            account.status = status
        account.notes = notes.strip() or None
        try:
            await session.flush()
        except IntegrityError:
            return redirect(f"/admin/accounts/{account_id}/edit", "المعرف مستخدم بالفعل لهذه المنصة")
        await record(
            session,
            "inventory.account_edited",
            "inventory_account",
            str(account.id),
            actor_admin_id=admin.id,
            metadata={
                "platform_code": platform.code,
                "previous_platform_code": old_platform_code,
                "previous_status": old_status,
                "status": account.status,
            },
        )
    return redirect("/admin/accounts", "تم تعديل الحساب")


@app.post("/admin/accounts/{account_id}/status")
async def update_account_status(request: Request, account_id: uuid.UUID, status: str = Form(), csrf_token: str = Form()) -> Response:
    if status not in {InventoryStatus.AVAILABLE.value, InventoryStatus.DISABLED.value, InventoryStatus.ARCHIVED.value}:
        return redirect("/admin/accounts", "حالة غير صالحة")
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value, AdminRole.OPERATOR.value})
        check_csrf(request, auth, csrf_token)
        account = await session.scalar(select(InventoryAccount).where(InventoryAccount.id == account_id).with_for_update())
        if not account:
            return redirect("/admin/accounts", "الحساب غير موجود")
        if account.status == InventoryStatus.ASSIGNED.value:
            return redirect("/admin/accounts", "لا يمكن تغيير حساب مخصص؛ استخدم إعادة التخصيص الصريحة")
        account.status = status
        platform = await session.get(Platform, account.platform_id)
        await record(session, "inventory.account_status_changed", "inventory_account", str(account.id), actor_admin_id=admin.id, metadata={"status": status, "platform_code": platform.code if platform else None})
    return redirect("/admin/accounts", "تم تحديث حالة الحساب")


@app.get("/admin/customers", response_class=HTMLResponse)
async def customers_page(request: Request) -> HTMLResponse:
    async with SessionLocal() as session:
        context = await admin_page_context(request, session)
        customers = (await session.scalars(select(Customer).order_by(Customer.created_at.desc()).limit(100))).all()
        return page(request, "customers.html", **context, customers=customers)


@app.post("/admin/customers")
async def add_customer(request: Request, display_name: str = Form(), notes: str = Form(""), csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value, AdminRole.OPERATOR.value})
        check_csrf(request, auth, csrf_token)
        customer = Customer(display_name=display_name.strip(), notes=notes.strip() or None)
        if not customer.display_name:
            return redirect("/admin/customers", "اسم العميل مطلوب")
        session.add(customer)
        await session.flush()
        await record(session, "customer.created", "customer", str(customer.id), actor_admin_id=admin.id)
    return redirect("/admin/customers", "تمت إضافة العميل")


@app.get("/admin/orders", response_class=HTMLResponse)
async def orders_page(request: Request) -> HTMLResponse:
    async with SessionLocal() as session:
        context = await admin_page_context(request, session)
        customers = (await session.scalars(select(Customer).order_by(Customer.display_name))).all()
        order_rows = (
            await session.execute(select(Order, Customer.display_name).join(Customer).order_by(Order.created_at.desc()).limit(100))
        ).all()
        orders = [{"id": order.id, "external_reference": order.external_reference, "status": order.status, "customer_name": name} for order, name in order_rows]
        assignable = (await session.scalars(select(InventoryAccount).where(InventoryAccount.status.in_(["available", "assigned"])).order_by(InventoryAccount.identifier))).all()
        return page(request, "orders.html", **context, customers=customers, orders=orders, assignable_accounts=assignable)


@app.post("/admin/orders")
async def add_order(request: Request, external_reference: str = Form(), customer_id: str = Form(), csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value, AdminRole.OPERATOR.value})
        check_csrf(request, auth, csrf_token)
        order = Order(external_reference=external_reference.strip(), customer_id=uuid.UUID(customer_id))
        if not order.external_reference:
            return redirect("/admin/orders", "مرجع الطلب مطلوب")
        session.add(order)
        try:
            await session.flush()
        except IntegrityError:
            return redirect("/admin/orders", "مرجع الطلب مستخدم بالفعل")
        await record(session, "order.created", "order", str(order.id), actor_admin_id=admin.id)
    return redirect("/admin/orders", "تم إنشاء الطلب")


@app.post("/admin/assignments")
async def add_assignment(request: Request, account_id: str = Form(), order_id: str = Form(), reassign_reason: str = Form(""), csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value, AdminRole.OPERATOR.value})
        check_csrf(request, auth, csrf_token)
        try:
            await assign_account(session, account_id=uuid.UUID(account_id), order_id=uuid.UUID(order_id), actor_admin_id=admin.id, reassign_reason=reassign_reason.strip() or None)
        except (ValueError, IntegrityError) as exc:
            return redirect("/admin/orders", str(exc))
    return redirect("/admin/orders", "تم تخصيص الحساب")


@app.post("/admin/orders/{order_id}/activation", response_class=HTMLResponse)
async def issue_activation(request: Request, order_id: uuid.UUID, csrf_token: str = Form()) -> HTMLResponse:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value, AdminRole.OPERATOR.value})
        check_csrf(request, auth, csrf_token)
        order = await session.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=404, detail="الطلب غير موجود")
        has_assignment = await session.scalar(select(AccountAssignment.id).where(AccountAssignment.order_id == order.id, AccountAssignment.revoked_at.is_(None)))
        if not has_assignment:
            return page(request, "orders.html", **{"admin": admin, "csrf_token": auth.csrf_token}, customers=[], orders=[], assignable_accounts=[], message="خصص حسابًا للطلب أولًا")
        await record(
            session,
            "order.shared_web_link_issued",
            "order",
            str(order.id),
            actor_admin_id=admin.id,
            metadata={"link": settings.public_base_url.rstrip("/") + "/"},
        )
    link = settings.public_base_url.rstrip("/") + "/"
    return page(request, "activation.html", admin=admin, csrf_token=auth.csrf_token, link=link)


@app.get("/admin/mailboxes", response_class=HTMLResponse)
async def mailboxes_page(request: Request) -> HTMLResponse:
    async with SessionLocal() as session:
        context = await admin_page_context(request, session)
        items = (await session.scalars(select(Mailbox).order_by(Mailbox.label))).all()
        usage_rows = (
            await session.execute(
                select(InventoryAccount.mailbox_id, func.count())
                .group_by(InventoryAccount.mailbox_id)
            )
        ).all()
        usage_counts = {mailbox_id: count for mailbox_id, count in usage_rows}
        return page(request, "mailboxes.html", **context, mailboxes=items, usage_counts=usage_counts)


@app.post("/admin/mailboxes/oauth/start")
async def start_mailbox_oauth(
    request: Request,
    label: str = Form(),
    username: str = Form(),
    csrf_token: str = Form(),
) -> Response:
    if not microsoft_oauth_configured(settings):
        return redirect("/admin/mailboxes", "لم يتم إعداد Microsoft OAuth2 في إعدادات السيرفر بعد")
    clean_label = label.strip()
    clean_username = username.strip().casefold()
    if not clean_label or "@" not in clean_username:
        return redirect("/admin/mailboxes", "أدخل اسمًا وبريد Outlook صحيحًا")
    raw_state = new_random_token(32)
    verifier = pkce_verifier()
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value})
        check_csrf(request, auth, csrf_token)
        existing = await session.scalar(select(Mailbox).where(Mailbox.label == clean_label))
        if existing and existing.auth_mode != "microsoft_graph":
            return redirect("/admin/mailboxes", "اسم صندوق البريد مستخدم؛ اختر اسمًا جديدًا لـ OAuth2")
        session.add(
            MailboxOAuthState(
                state_hash=sha256(raw_state),
                admin_id=admin.id,
                label=clean_label,
                username=clean_username,
                code_verifier_encrypted=encrypt_secret(verifier),
                expires_at=utcnow() + timedelta(minutes=10),
            )
        )
        await record(
            session,
            "mailbox.oauth_started",
            "mailbox",
            clean_label,
            actor_admin_id=admin.id,
            metadata={"provider": "microsoft_graph"},
        )
    return RedirectResponse(build_authorization_url(raw_state, code_challenge=pkce_challenge(verifier)), status_code=303)


@app.post("/admin/mailboxes/{mailbox_id}/oauth/reauthorize")
async def reauthorize_mailbox_oauth(request: Request, mailbox_id: uuid.UUID, csrf_token: str = Form()) -> Response:
    """Start a fresh consent flow using the one server-wide Microsoft app."""
    if not microsoft_oauth_configured(settings):
        return redirect("/admin/mailboxes", "لم يتم إعداد Microsoft OAuth2 في إعدادات السيرفر بعد")
    raw_state = new_random_token(32)
    verifier = pkce_verifier()
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value})
        check_csrf(request, auth, csrf_token)
        mailbox = await session.scalar(select(Mailbox).where(Mailbox.id == mailbox_id).with_for_update())
        if not mailbox or mailbox.auth_mode != "microsoft_graph":
            return redirect("/admin/mailboxes", "إعادة التفويض متاحة فقط لصندوق Outlook مربوط")
        session.add(
            MailboxOAuthState(
                state_hash=sha256(raw_state),
                admin_id=admin.id,
                label=mailbox.label,
                username=mailbox.username,
                code_verifier_encrypted=encrypt_secret(verifier),
                expires_at=utcnow() + timedelta(minutes=10),
            )
        )
        await record(
            session,
            "mailbox.oauth_reauthorization_started",
            "mailbox",
            str(mailbox.id),
            actor_admin_id=admin.id,
            metadata={"provider": "microsoft_graph"},
        )
    return RedirectResponse(build_authorization_url(raw_state, code_challenge=pkce_challenge(verifier)), status_code=303)


@app.get("/admin/mailboxes/oauth/callback")
async def mailbox_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> Response:
    # Uvicorn's access logger includes the ASGI query string. Remove it after
    # FastAPI has parsed the callback parameters so authorization codes and
    # state values never enter application access logs.
    request.scope["query_string"] = b""
    if error or not code or not state:
        return redirect("/admin/mailboxes", "لم تكتمل موافقة Microsoft OAuth2")
    async with SessionLocal() as session:
        try:
            admin, _ = await current_admin(request, session)
        except HTTPException as exc:
            if exc.status_code == 401:
                logger.warning("microsoft_oauth_callback_failed stage=session_cookie reason=missing_admin_session")
                return redirect("/admin/login", "انتهت جلسة الإدارة؛ سجّل الدخول وابدأ ربط Outlook من جديد")
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
            return redirect("/admin/mailboxes", "رابط OAuth2 منتهٍ أو غير صالح؛ ابدأ الربط من جديد")
        if not pending.code_verifier_encrypted:
            logger.warning("microsoft_oauth_callback_failed stage=pkce_lookup reason=missing_verifier")
            return redirect("/admin/mailboxes", "حالة OAuth2 قديمة؛ ابدأ الربط من جديد")
        try:
            code_verifier = decrypt_secret(pending.code_verifier_encrypted)
        except Exception:
            logger.warning("microsoft_oauth_callback_failed stage=pkce_lookup reason=decrypt_failed")
            return redirect("/admin/mailboxes", "تعذر استعادة جلسة OAuth2؛ ابدأ الربط من جديد")
    try:
        token_result = await asyncio.to_thread(exchange_authorization_code, code, code_verifier)
    except MailProviderError as exc:
        reason = str(exc) if str(exc).isidentifier() else "provider_error"
        logger.warning("microsoft_oauth_callback_failed stage=token_exchange reason=%s", reason)
        return redirect("/admin/mailboxes", "تعذر إكمال ربط Microsoft؛ ابدأ الربط من جديد")
    except Exception:
        logger.warning("microsoft_oauth_callback_failed stage=token_exchange reason=unexpected_error")
        return redirect("/admin/mailboxes", "تعذر إكمال ربط Microsoft؛ ابدأ الربط من جديد")
    refresh_token = token_result.get("refresh_token")
    if not refresh_token:
        logger.warning("microsoft_oauth_callback_failed stage=token_response reason=missing_refresh_token")
        return redirect("/admin/mailboxes", "لم تُرجع Microsoft Refresh Token؛ ابدأ الربط من جديد")
    try:
        async with SessionLocal.begin() as session:
            try:
                admin, _ = await current_admin(request, session)
            except HTTPException as exc:
                if exc.status_code == 401:
                    logger.warning("microsoft_oauth_callback_failed stage=session_cookie reason=missing_admin_session_after_exchange")
                    return redirect("/admin/login", "انتهت جلسة الإدارة؛ سجّل الدخول وابدأ ربط Outlook من جديد")
                raise
            pending = await session.scalar(
                select(MailboxOAuthState)
                .where(MailboxOAuthState.state_hash == sha256(state), MailboxOAuthState.admin_id == admin.id)
                .with_for_update()
            )
            if not pending or pending.used_at is not None or pending.expires_at <= utcnow():
                logger.warning("microsoft_oauth_callback_failed stage=state_validation reason=used_or_expired_state")
                return redirect("/admin/mailboxes", "تم استخدام رابط OAuth2 أو انتهت صلاحيته؛ ابدأ الربط من جديد")
            mailbox = await session.scalar(select(Mailbox).where(Mailbox.label == pending.label).with_for_update())
            if mailbox and mailbox.auth_mode != "microsoft_graph":
                logger.warning("microsoft_oauth_callback_failed stage=database_storage reason=mailbox_mode_conflict")
                return redirect("/admin/mailboxes", "اسم صندوق البريد مستخدم بطريقة IMAP؛ اختر اسمًا جديدًا")
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
        return redirect("/admin/mailboxes", "تعذر حفظ صندوق Outlook؛ ابدأ الربط من جديد")
    return redirect("/admin/mailboxes", "تم ربط بريد Outlook عبر OAuth2 بنجاح")


@app.post("/admin/mailboxes")
async def add_mailbox(request: Request, label: str = Form(), host: str = Form(), port: int = Form(993), username: str = Form(), password: str = Form(), csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value})
        check_csrf(request, auth, csrf_token)
        if not label.strip() or not host.strip() or not username.strip() or not password:
            return redirect("/admin/mailboxes", "كل حقول صندوق البريد مطلوبة")
        session.add(Mailbox(label=label.strip(), host=host.strip(), port=port, username=username.strip(), encrypted_password=encrypt_secret(password)))
        try:
            await session.flush()
        except IntegrityError:
            return redirect("/admin/mailboxes", "اسم صندوق البريد مستخدم بالفعل")
        await record(session, "mailbox.created", "mailbox", label.strip(), actor_admin_id=admin.id)
    return redirect("/admin/mailboxes", "تم حفظ صندوق البريد مشفرًا")


@app.post("/admin/mailboxes/{mailbox_id}/test")
async def test_mailbox_connection(request: Request, mailbox_id: uuid.UUID, csrf_token: str = Form()) -> Response:
    """Prove a read-only connection without storing or showing message content."""
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value, AdminRole.OPERATOR.value})
        check_csrf(request, auth, csrf_token)
        mailbox = await session.scalar(select(Mailbox).where(Mailbox.id == mailbox_id).with_for_update())
        if not mailbox:
            return redirect("/admin/mailboxes", "صندوق البريد غير موجود")
        provider = MicrosoftGraphMailProvider(mailbox) if mailbox.auth_mode == "microsoft_graph" else ImapMailProvider(mailbox)
        try:
            await asyncio.to_thread(provider.recent_messages, utcnow() - timedelta(minutes=1), 1)
            if getattr(provider, "rotated_refresh_token", None):
                mailbox.oauth_refresh_token = encrypt_secret(provider.rotated_refresh_token)
            mailbox.last_checked_at = utcnow()
            mailbox.last_error_code = None
            await record(
                session,
                "mailbox.connection_tested",
                "mailbox",
                str(mailbox.id),
                actor_admin_id=admin.id,
                metadata={"provider": mailbox.auth_mode, "result": "ok"},
            )
        except MailProviderError:
            mailbox.last_checked_at = utcnow()
            mailbox.last_error_code = "connection_test_failed"
            await record(
                session,
                "mailbox.connection_tested",
                "mailbox",
                str(mailbox.id),
                actor_admin_id=admin.id,
                metadata={"provider": mailbox.auth_mode, "result": "failed"},
            )
            return redirect(f"/admin/mailboxes/{mailbox_id}/edit", "تعذر الاتصال؛ راجع الإعدادات دون مشاركة كلمة مرور أو توكن")
    return redirect(f"/admin/mailboxes/{mailbox_id}/edit", "نجح اتصال القراءة فقط؛ لم يتم حفظ أو عرض أي رسالة")


@app.post("/admin/mailboxes/{mailbox_id}/disable")
async def disable_mailbox(request: Request, mailbox_id: uuid.UUID, csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value})
        check_csrf(request, auth, csrf_token)
        mailbox = await session.scalar(select(Mailbox).where(Mailbox.id == mailbox_id).with_for_update())
        if not mailbox:
            return redirect("/admin/mailboxes", "صندوق البريد غير موجود")
        mailbox.is_active = False
        await record(session, "mailbox.disabled", "mailbox", str(mailbox.id), actor_admin_id=admin.id)
    return redirect("/admin/mailboxes", "تم تعطيل صندوق البريد؛ يمكن إعادة تفعيله من التعديل")


@app.get("/admin/mailboxes/{mailbox_id}/edit", response_class=HTMLResponse)
async def edit_mailbox_page(request: Request, mailbox_id: uuid.UUID) -> HTMLResponse:
    async with SessionLocal() as session:
        context = await admin_page_context(request, session)
        mailbox = await session.get(Mailbox, mailbox_id)
        if not mailbox:
            raise HTTPException(status_code=404, detail="صندوق البريد غير موجود")
        usage_count = await session.scalar(
            select(func.count()).select_from(InventoryAccount).where(InventoryAccount.mailbox_id == mailbox.id)
        )
        return page(request, "mailbox_edit.html", **context, mailbox=mailbox, usage_count=usage_count or 0)


@app.post("/admin/mailboxes/{mailbox_id}/edit")
async def edit_mailbox(
    request: Request,
    mailbox_id: uuid.UUID,
    label: str = Form(),
    host: str = Form(),
    port: int = Form(993),
    username: str = Form(),
    password: str = Form(""),
    purpose: str = Form("inventory"),
    mail_folder: str = Form("INBOX"),
    notification_sender_domains: str = Form(""),
    notification_subject_patterns: str = Form(""),
    is_active: str | None = Form(None),
    csrf_token: str = Form(),
) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value})
        check_csrf(request, auth, csrf_token)
        mailbox = await session.scalar(select(Mailbox).where(Mailbox.id == mailbox_id).with_for_update())
        if not mailbox:
            return redirect("/admin/mailboxes", "صندوق البريد غير موجود")
        clean_label = label.strip()
        clean_host = host.strip()
        clean_username = username.strip()
        clean_folder = mail_folder.strip()
        if purpose not in {"inventory", "salla_notifications"}:
            return redirect(f"/admin/mailboxes/{mailbox_id}/edit", "غرض صندوق البريد غير صالح")
        if not clean_label or not clean_host or not clean_username or not clean_folder or len(clean_folder) > 255 or not 1 <= port <= 65535:
            return redirect(f"/admin/mailboxes/{mailbox_id}/edit", "الاسم والمضيف والمستخدم والمنفذ مطلوبة")
        usage_count = await session.scalar(
            select(func.count()).select_from(InventoryAccount).where(InventoryAccount.mailbox_id == mailbox.id)
        )
        if purpose == "salla_notifications" and usage_count:
            return redirect(f"/admin/mailboxes/{mailbox_id}/edit", "لا يمكن تحويل صندوق مستخدم في المخزون إلى صندوق إشعارات Salla")
        try:
            domains, patterns = notification_profile_values(notification_sender_domains, notification_subject_patterns)
        except ValueError as exc:
            return redirect(f"/admin/mailboxes/{mailbox_id}/edit", str(exc))
        if purpose == "salla_notifications" and (not domains or not patterns):
            return redirect(f"/admin/mailboxes/{mailbox_id}/edit", "صندوق إشعارات Salla يحتاج نطاقات مرسل وأنماط عناوين موثقة")
        if mailbox.auth_mode == "microsoft_graph" and (clean_host != mailbox.host or clean_username.casefold() != mailbox.username.casefold() or port != mailbox.port):
            return redirect(f"/admin/mailboxes/{mailbox_id}/edit", "بيانات Outlook مربوطة بالتفويض؛ استخدم إعادة التفويض بدل تغييرها يدويًا")
        mailbox.label = clean_label
        mailbox.host = clean_host
        mailbox.port = port
        mailbox.username = clean_username
        mailbox.purpose = purpose
        mailbox.mail_folder = clean_folder
        mailbox.notification_sender_domains = domains if purpose == "salla_notifications" else []
        mailbox.notification_subject_patterns = patterns if purpose == "salla_notifications" else []
        mailbox.is_active = bool(is_active)
        if password:
            if mailbox.auth_mode == "microsoft_graph":
                return redirect(f"/admin/mailboxes/{mailbox_id}/edit", "لا تقبل صناديق Outlook كلمة مرور؛ استخدم إعادة التفويض")
            mailbox.encrypted_password = encrypt_secret(password)
            mailbox.auth_mode = "imap_password"
            mailbox.oauth_refresh_token = None
        try:
            await session.flush()
        except IntegrityError:
            return redirect(f"/admin/mailboxes/{mailbox_id}/edit", "اسم صندوق البريد مستخدم بالفعل")
        await record(
            session,
            "mailbox.updated",
            "mailbox",
            str(mailbox.id),
            actor_admin_id=admin.id,
            metadata={"label": mailbox.label, "is_active": mailbox.is_active, "purpose": mailbox.purpose},
        )
    return redirect("/admin/mailboxes", "تم تعديل صندوق البريد")


@app.post("/admin/mailboxes/{mailbox_id}/delete")
async def delete_mailbox(
    request: Request,
    mailbox_id: uuid.UUID,
    confirm_label: str = Form(""),
    csrf_token: str = Form(),
) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value})
        check_csrf(request, auth, csrf_token)
        mailbox = await session.scalar(select(Mailbox).where(Mailbox.id == mailbox_id).with_for_update())
        if not mailbox:
            return redirect("/admin/mailboxes", "صندوق البريد غير موجود")
        if confirm_label.strip() != mailbox.label:
            return redirect(f"/admin/mailboxes/{mailbox_id}/edit", "اكتب اسم صندوق البريد كما هو لتأكيد الحذف أو التعطيل")
        usage_count = await session.scalar(
            select(func.count()).select_from(InventoryAccount).where(InventoryAccount.mailbox_id == mailbox.id)
        )
        if usage_count:
            mailbox.is_active = False
            await record(
                session,
                "mailbox.disabled",
                "mailbox",
                str(mailbox.id),
                actor_admin_id=admin.id,
                metadata={"label": mailbox.label, "usage_count": usage_count},
            )
            return redirect("/admin/mailboxes", "الصندوق مستخدم في المخزون؛ تم تعطيله بدل حذفه")
        label = mailbox.label
        await session.delete(mailbox)
        await record(session, "mailbox.deleted", "mailbox", str(mailbox_id), actor_admin_id=admin.id, metadata={"label": label})
    return redirect("/admin/mailboxes", "تم حذف صندوق البريد")


@app.get("/admin/platforms", response_class=HTMLResponse)
async def platforms_page(request: Request) -> HTMLResponse:
    async with SessionLocal() as session:
        context = await admin_page_context(request, session)
        platforms = (await session.scalars(select(Platform).order_by(Platform.name))).all()
        steam = next((platform for platform in platforms if platform.code == "steam"), None)
        return page(request, "platforms.html", **context, platforms=platforms, steam_profile=json.dumps(steam.mail_profile if steam else {}, ensure_ascii=False, indent=2), steam_enabled=bool(steam and steam.is_enabled))


@app.post("/admin/platforms/steam")
async def save_steam_platform(request: Request, profile_json: str = Form(), enable: str | None = Form(None), csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value})
        check_csrf(request, auth, csrf_token)
        try:
            profile = json.loads(profile_json)
        except json.JSONDecodeError:
            return redirect("/admin/platforms", "صيغة JSON غير صالحة")
        if not isinstance(profile, dict):
            return redirect("/admin/platforms", "إعداد Steam يجب أن يكون كائن JSON")
        if enable and not {"sender_domains", "account_pattern", "code_pattern", "required_auth_result", "sample_verified_at"}.issubset(profile):
            return redirect("/admin/platforms", "يلزم توثيق العينة وإدخال قواعد المطابقة قبل التفعيل")
        steam = await session.scalar(select(Platform).where(Platform.code == "steam").with_for_update())
        if not steam:
            return redirect("/admin/platforms", "نفّذ migrations أولًا")
        steam.mail_profile = profile
        steam.is_enabled = bool(enable)
        await record(session, "platform.steam_configured", "platform", str(steam.id), actor_admin_id=admin.id, metadata={"enabled": steam.is_enabled, "profile_keys": list(profile)})
    return redirect("/admin/platforms", "تم حفظ إعداد Steam")


@app.get("/admin/import", response_class=HTMLResponse)
async def import_page(request: Request, batch_id: uuid.UUID | None = None) -> HTMLResponse:
    async with SessionLocal() as session:
        context = await admin_page_context(request, session)
        batch = await session.get(ImportBatch, batch_id) if batch_id else None
        rows = (await session.scalars(select(ImportRow).where(ImportRow.batch_id == batch.id).order_by(ImportRow.row_number))) .all() if batch else []
        return page(request, "import.html", **context, batch=batch, rows=rows)


@app.post("/admin/import/preview")
async def preview_import(request: Request, csv_file: UploadFile = File(), csrf_token: str = Form()) -> Response:
    raw = await csv_file.read(2_000_001)
    try:
        rows = parse_inventory_csv(raw)
    except CsvImportError as exc:
        return redirect("/admin/import", str(exc))
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value, AdminRole.OPERATOR.value})
        check_csrf(request, auth, csrf_token)
        digest = hashlib.sha256(raw).hexdigest()
        prior = await session.scalar(select(ImportBatch).where(ImportBatch.sha256 == digest))
        if prior:
            return redirect(f"/admin/import?batch_id={prior.id}", "هذا الملف تمت معاينته سابقًا")
        platform_codes = {
            p.code
            for p in (await session.scalars(select(Platform))).all()
            if p.code in INVENTORY_PLATFORM_CODES
        }
        mailbox_labels = {m.label for m in (await session.scalars(select(Mailbox))).all()}
        existing_keys = {
            (platform_code, normalized_identifier)
            for platform_code, normalized_identifier in (
                await session.execute(
                    select(Platform.code, InventoryAccount.normalized_identifier).join(InventoryAccount)
                )
            ).all()
        }
        batch = ImportBatch(created_by_admin_id=admin.id, sha256=digest)
        session.add(batch)
        await session.flush()
        prepared_rows = prepare_inventory_rows(
            rows,
            platform_codes=platform_codes,
            mailbox_labels=mailbox_labels,
            allowed_statuses={item.value for item in InventoryStatus},
            existing_keys=existing_keys,
            normalizer=normalize_identifier,
        )
        errors = sum(row.error is not None for row in prepared_rows)
        for row in prepared_rows:
            session.add(ImportRow(batch_id=batch.id, row_number=row.row_number, data={"platform": row.platform, "account_identifier": row.account_identifier, "mailbox_reference": row.mailbox_reference, "status": row.status, "notes": row.notes}, error=row.error))
        batch.error_count = errors
        await record(session, "import.preview_created", "import_batch", str(batch.id), actor_admin_id=admin.id, metadata={"row_count": len(rows), "error_count": errors})
    return redirect(f"/admin/import?batch_id={batch.id}")


@app.post("/admin/import/{batch_id}/commit")
async def commit_import(request: Request, batch_id: uuid.UUID, csrf_token: str = Form()) -> Response:
    async with SessionLocal.begin() as session:
        admin, auth = await require_role(request, session, {AdminRole.OWNER.value, AdminRole.OPERATOR.value})
        check_csrf(request, auth, csrf_token)
        batch = await session.scalar(select(ImportBatch).where(ImportBatch.id == batch_id).with_for_update())
        if not batch or batch.status != "preview" or batch.error_count:
            return redirect("/admin/import", "لا يمكن تأكيد هذه الدفعة")
        rows = (await session.scalars(select(ImportRow).where(ImportRow.batch_id == batch.id).with_for_update())).all()
        platforms = {p.code: p.id for p in (await session.scalars(select(Platform))).all()}
        mailboxes = {m.label: m.id for m in (await session.scalars(select(Mailbox))).all()}
        for row in rows:
            data = row.data
            account = InventoryAccount(platform_id=platforms[data["platform"]], mailbox_id=mailboxes[data["mailbox_reference"]], identifier=data["account_identifier"], normalized_identifier=normalize_identifier(data["account_identifier"]), status=data["status"], notes=data["notes"] or None)
            session.add(account)
            await session.flush()
            await record(
                session,
                "inventory.account_created",
                "inventory_account",
                str(account.id),
                actor_admin_id=admin.id,
                metadata={"platform_code": data["platform"], "source": "csv_import"},
            )
        batch.status = "committed"
        await record(session, "import.committed", "import_batch", str(batch.id), actor_admin_id=admin.id, metadata={"row_count": len(rows)})
    return redirect("/admin/accounts", "تم استيراد الحسابات")


@app.get("/admin/audit", response_class=HTMLResponse)
async def audit_page(request: Request, platform: str = "") -> HTMLResponse:
    async with SessionLocal() as session:
        context = await admin_page_context(request, session)
        selected_platform = platform.strip().casefold()
        query = select(AuditEvent).order_by(AuditEvent.created_at.desc())
        if selected_platform in SUPPORTED_PLATFORM_CODES:
            query = query.where(AuditEvent.event_metadata["platform_code"].as_string() == selected_platform)
        events = (await session.scalars(query.limit(150))).all()
        audit_platforms = (await session.scalars(select(Platform).where(Platform.code.in_(SUPPORTED_PLATFORM_CODES)).order_by(Platform.name))).all()
        return page(request, "audit.html", **context, events=events, platform=selected_platform, audit_platforms=audit_platforms)


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request) -> Response:
    expected = settings.telegram_webhook_secret.get_secret_value() if settings.telegram_webhook_secret else None
    if not expected or request.headers.get("X-Telegram-Bot-Api-Secret-Token") != expected:
        raise HTTPException(status_code=403, detail="forbidden")
    payload = await request.json()
    update_id = payload.get("update_id")
    if not isinstance(update_id, int):
        raise HTTPException(status_code=400, detail="invalid update")
    from app.models import TelegramUpdate
    async with SessionLocal() as session:
        if await session.get(TelegramUpdate, update_id):
            return Response(status_code=200)
    await feed_webhook_update(payload)
    async with SessionLocal.begin() as session:
        if not await session.get(TelegramUpdate, update_id):
            session.add(TelegramUpdate(update_id=update_id))
    return Response(status_code=200)
