from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_root_returns_json_not_html():
    """Verify that root / returns a clean JSON response instead of HTML."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")
        data = resp.json()
        assert data.get("service") == "ordertrofy-api"
        assert data.get("status") == "ok"
        assert data.get("docs") == "/api/docs"


@pytest.mark.asyncio
async def test_health_endpoints():
    """Verify that health check endpoints return expected JSON."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # /health/live
        live_resp = await client.get("/health/live")
        assert live_resp.status_code == 200
        assert live_resp.json() == {"status": "ok"}

        # /health
        health_resp = await client.get("/health")
        assert health_resp.status_code in (200, 503)
        assert "status" in health_resp.json()

        # /health/ready
        ready_resp = await client.get("/health/ready")
        assert ready_resp.status_code in (200, 503)


@pytest.mark.asyncio
async def test_api_docs_available():
    """Verify OpenAPI swagger docs remain available at /api/docs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/docs")
        assert resp.status_code == 200
        assert "swagger" in resp.text.lower() or "openapi" in resp.text.lower() or "html" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_legacy_html_routes_return_404_json():
    """Legacy server-rendered HTML routes must return 404 JSON, not HTML templates."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        legacy_paths = [
            "/portal",
            "/admin",
            "/admin/login",
            "/salla",
            "/access",
            "/admin/accounts",
            "/admin/customers",
            "/admin/orders",
            "/admin/mailboxes",
            "/admin/platforms",
            "/admin/import",
            "/admin/audit",
            "/activate/sample-token",
        ]
        for path in legacy_paths:
            resp = await client.get(path)
            assert resp.status_code == 404, f"Expected 404 for {path}, got {resp.status_code}"
            assert "application/json" in resp.headers.get("content-type", ""), f"Expected JSON 404 for {path}"
            assert "detail" in resp.json()


@pytest.mark.asyncio
async def test_openapi_schema_contains_required_api_v1_endpoints():
    """Verify OpenAPI specification includes all required React and admin endpoints."""
    schema = app.openapi()
    paths = schema.get("paths", {})

    expected_endpoints = [
        "/api/v1/auth/login",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/admin/dashboard",
        "/api/v1/admin/accounts",
        "/api/v1/admin/orders",
        "/api/v1/admin/assignments",
        "/api/v1/admin/customers",
        "/api/v1/admin/mailboxes",
        "/api/v1/admin/platforms",
        "/api/v1/admin/import/preview",
        "/api/v1/admin/salla",
        "/api/v1/admin/audit",
        "/api/v1/customer/access",
        "/api/v1/customer/activate",
        "/api/v1/customer/portal",
        "/api/v1/salla/access",
        "/api/v1/salla/status",
    ]

    for endpoint in expected_endpoints:
        assert endpoint in paths, f"Expected endpoint {endpoint} in OpenAPI schema"


@pytest.mark.asyncio
async def test_preserved_integrations_routes():
    """Verify preserved integration routes exist and are not 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Salla webhook without signature should return 403, not 404
        salla_resp = await client.post("/api/integrations/salla/webhook", content=b"{}")
        assert salla_resp.status_code in (400, 403), f"Expected 400/403 for Salla webhook, got {salla_resp.status_code}"

        # Telegram webhook without secret should return 403, not 404
        tg_resp = await client.post("/telegram/webhook", content=b"{}")
        assert tg_resp.status_code in (400, 403), f"Expected 400/403 for Telegram webhook, got {tg_resp.status_code}"

        # OAuth callback without code/state should return 400, not 404
        oauth_resp = await client.get("/admin/mailboxes/oauth/callback")
        assert oauth_resp.status_code == 400, f"Expected 400 for OAuth callback without params, got {oauth_resp.status_code}"


@pytest.mark.asyncio
async def test_cors_headers_and_vercel_origin():
    """Verify CORS configuration allows production Vercel and local origins."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Preflight from Vercel preview domain
        headers = {
            "Origin": "https://ordertrofy-frontend-test.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type, x-admin-session",
        }
        resp = await client.options("/api/v1/auth/login", headers=headers)
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "https://ordertrofy-frontend-test.vercel.app"
        assert resp.headers.get("access-control-allow-credentials") == "true"
