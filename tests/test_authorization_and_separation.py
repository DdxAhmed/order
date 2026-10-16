from __future__ import annotations

import uuid
from datetime import timedelta
import pytest
from httpx import ASGITransport, AsyncClient

from app.db import SessionLocal
from app.main import app
from app.models import (
    AccountAssignment,
    AdminRole,
    AdminSession,
    AdminUser,
    Customer,
    CustomerSession,
    InventoryAccount,
    Mailbox,
    Order,
    Platform,
)
from app.security import hash_password, make_csrf_token, new_random_token, sha256, utcnow


@pytest.fixture
async def multi_customer_context():
    """Setup two distinct customers with their own orders and assignments."""
    async with SessionLocal.begin() as session:
        # Platform & Mailbox
        platform = Platform(
            code=f"steam_{uuid.uuid4().hex[:6]}",
            name="Steam",
            is_enabled=True,
        )
        session.add(platform)
        await session.flush()

        mailbox = Mailbox(
            label=f"mb_{uuid.uuid4().hex[:8]}",
            host="imap.example.com",
            port=993,
            username=f"mb_{uuid.uuid4().hex[:6]}@example.com",
            auth_mode="imap_password",
            is_active=True,
        )
        session.add(mailbox)
        await session.flush()

        # Admin
        admin = AdminUser(
            email=f"admin_{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("Pass123!"),
            role="owner",
            is_active=True,
        )
        session.add(admin)
        await session.flush()

        # Customer A
        cust_a = Customer(display_name="Customer A")
        session.add(cust_a)
        await session.flush()

        token_a = new_random_token()
        session_a = CustomerSession(
            customer_id=cust_a.id,
            token_hash=sha256(token_a),
            csrf_token=make_csrf_token(),
            expires_at=utcnow() + timedelta(hours=2),
        )
        session.add(session_a)
        await session.flush()

        order_a = Order(external_reference=f"ORD-A-{uuid.uuid4().hex[:6]}", customer_id=cust_a.id, status="activated")
        session.add(order_a)
        await session.flush()

        acc_a = InventoryAccount(
            platform_id=platform.id,
            mailbox_id=mailbox.id,
            identifier=f"user_a_{uuid.uuid4().hex[:6]}",
            normalized_identifier=f"user_a_{uuid.uuid4().hex[:6]}",
            status="assigned",
        )
        session.add(acc_a)
        await session.flush()

        asgn_a = AccountAssignment(
            account_id=acc_a.id,
            order_id=order_a.id,
            customer_id=cust_a.id,
            assigned_by_admin_id=admin.id,
        )
        session.add(asgn_a)
        await session.flush()

        # Customer B
        cust_b = Customer(display_name="Customer B")
        session.add(cust_b)
        await session.flush()

        token_b = new_random_token()
        session_b = CustomerSession(
            customer_id=cust_b.id,
            token_hash=sha256(token_b),
            csrf_token=make_csrf_token(),
            expires_at=utcnow() + timedelta(hours=2),
        )
        session.add(session_b)
        await session.flush()

        order_b = Order(external_reference=f"ORD-B-{uuid.uuid4().hex[:6]}", customer_id=cust_b.id, status="activated")
        session.add(order_b)
        await session.flush()

        acc_b = InventoryAccount(
            platform_id=platform.id,
            mailbox_id=mailbox.id,
            identifier=f"user_b_{uuid.uuid4().hex[:6]}",
            normalized_identifier=f"user_b_{uuid.uuid4().hex[:6]}",
            status="assigned",
        )
        session.add(acc_b)
        await session.flush()

        asgn_b = AccountAssignment(
            account_id=acc_b.id,
            order_id=order_b.id,
            customer_id=cust_b.id,
            assigned_by_admin_id=admin.id,
        )
        session.add(asgn_b)
        await session.flush()

        ctx = {
            "token_a": token_a,
            "assignment_a_id": asgn_a.id,
            "token_b": token_b,
            "assignment_b_id": asgn_b.id,
        }
    return ctx


@pytest.mark.asyncio
async def test_unauthenticated_visitor_cannot_access_admin_endpoints():
    """Anonymous visitors receive 401 on admin endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/admin/dashboard")
        assert resp.status_code == 401
        assert "يلزم تسجيل الدخول كمسؤول" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_customer_token_cannot_access_admin_dashboard(multi_customer_context):
    """Customer session token must be strictly rejected on admin routes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Pass customer token in headers
        headers = {"Authorization": f"Bearer {multi_customer_context['token_a']}"}
        resp = await client.get("/api/v1/admin/dashboard", headers=headers)
        assert resp.status_code == 401
        assert "يلزم تسجيل الدخول كمسؤول" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cross_customer_object_level_authorization(multi_customer_context):
    """Customer A must NOT be able to request or access Customer B's assignment/OTP."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Customer A authenticates with token A
        headers = {
            "Authorization": f"Bearer {multi_customer_context['token_a']}",
            "X-Customer-Session": multi_customer_context["token_a"],
        }
        # Customer A tries to verify assignment B
        b_id = multi_customer_context["assignment_b_id"]
        resp = await client.post(f"/api/v1/customer/assignments/{b_id}/verify", headers=headers)
        # Must return 404 Not Found (object does not belong to Customer A)
        assert resp.status_code == 404
        assert "لا يمكن الوصول إلى هذا الحساب" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_security_headers_present():
    """Verify security headers are injected into HTTP responses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
