from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_admin_login_and_me():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        # 1. Successful login
        payload = {"email": "admin@ordertrofy.store", "password": "OrderTrofyAdmin2026!"}
        resp = await client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "token" in data
        assert data["user"]["email"] == "admin@ordertrofy.store"
        assert data["user"]["role"] == "owner"

        token = data["token"]

        # 2. Authenticated /me endpoint
        me_resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["user"]["email"] == "admin@ordertrofy.store"

        # 3. Invalid credentials rejected
        bad_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@ordertrofy.store", "password": "WrongPassword999!"},
        )
        assert bad_resp.status_code == 401
