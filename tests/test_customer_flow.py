from __future__ import annotations

import uuid
import httpx
import pytest
from sqlalchemy import select
from app.db import SessionLocal
from app.models import (
    AccountAssignment,
    AdminUser,
    Customer,
    InventoryAccount,
    InventoryStatus,
    Mailbox,
    Order,
    OrderStatus,
    Platform,
    VerificationRequest,
)
from app.security import encrypt_secret


@pytest.mark.asyncio
async def test_customer_portal_authentication_and_verification_request():
    async with SessionLocal.begin() as session:
        # Ensure Steam platform is enabled
        platform = await session.scalar(select(Platform).where(Platform.code == "steam"))
        if not platform:
            platform = Platform(id=uuid.uuid4(), code="steam", name="Steam", is_enabled=True, mail_profile={})
            session.add(platform)
        else:
            platform.is_enabled = True

        # Ensure mailbox exists
        mailbox = await session.scalar(select(Mailbox).where(Mailbox.label == "test-seed-mailbox"))
        if not mailbox:
            mailbox = Mailbox(
                label="test-seed-mailbox",
                host="127.0.0.1",
                port=993,
                username="test_seed@ordertrofy.store",
                encrypted_password=encrypt_secret("dummy-secret-1234"),
                is_active=True,
            )
            session.add(mailbox)
            await session.flush()

        # Create or fetch Customer
        customer = await session.scalar(select(Customer).where(Customer.display_name == "سعد الأحمدي"))
        if not customer:
            customer = Customer(display_name="سعد الأحمدي", notes="عميل تجريبي")
            session.add(customer)
            await session.flush()

        # Create or fetch Order
        order = await session.scalar(select(Order).where(Order.external_reference == "ORD-99999"))
        if not order:
            order = Order(
                customer_id=customer.id,
                external_reference="ORD-99999",
                status=OrderStatus.ASSIGNED.value,
            )
            session.add(order)
            await session.flush()

        # Create or fetch InventoryAccount
        account = await session.scalar(
            select(InventoryAccount).where(InventoryAccount.identifier == "steam_test_account")
        )
        if not account:
            account = InventoryAccount(
                platform_id=platform.id,
                mailbox_id=mailbox.id,
                identifier="steam_test_account",
                normalized_identifier="steam_test_account",
                status=InventoryStatus.ASSIGNED.value,
            )
            session.add(account)
            await session.flush()

        admin = await session.scalar(select(AdminUser).where(AdminUser.email == "admin@ordertrofy.store"))
        # Create or fetch Assignment
        assignment = await session.scalar(
            select(AccountAssignment).where(AccountAssignment.order_id == order.id)
        )
        if not assignment:
            assignment = AccountAssignment(
                account_id=account.id,
                order_id=order.id,
                customer_id=customer.id,
                assigned_by_admin_id=admin.id,
            )
            session.add(assignment)
            await session.flush()

    # Now test Customer Portal API
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        # 1. Customer Access / Login
        access_payload = {
            "order_reference": "ORD-99999",
            "steam_username": "steam_test_account",
            "platform_code": "steam",
        }
        resp = await client.post("/api/v1/customer/access", json=access_payload)
        assert resp.status_code == 200, f"Access failed: {resp.text}"
        data = resp.json()
        assert data["status"] == "success"
        # Cookie was set in response
        cookies = resp.cookies

        # 2. Get customer portal current state
        portal_resp = await client.get("/api/v1/customer/portal", cookies=cookies)
        assert portal_resp.status_code == 200
        portal_data = portal_resp.json()
        assert len(portal_data.get("assignments", [])) > 0
        account_data = portal_data["assignments"][0]
        assert "assignment_id" in account_data

        assignment_id = account_data["assignment_id"]

        # 3. Request OTP Verification
        req_resp = await client.post(f"/api/v1/customer/assignments/{assignment_id}/verify", cookies=cookies)
        assert req_resp.status_code == 200
        req_data = req_resp.json()
        assert req_data["status"] == "success"
        assert "request_id" in req_data
