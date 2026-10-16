from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.config import get_settings
from app.security import encrypt_salla_secret

SALLA_API = "https://api.salla.dev/admin/v2"
SALLA_ACCOUNTS = "https://accounts.salla.sa"
SALLA_USER_AGENT = "TrofeBot/1.0"


class SallaApiError(RuntimeError):
    def __init__(self, code: str, status: int | None = None, retry_after: int | None = None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.retry_after = retry_after


def verify_webhook_signature(body: bytes, supplied: str | None, secret: str | None) -> bool:
    """Verify Salla's documented SHA-256 body/secret signature in constant time.

    Salla describes this as a SHA-256 hash of the request body using the webhook
    secret. HMAC is used here, which is the standard keyed SHA-256 construction
    and matches Salla's 64-character signature format.
    """
    if not supplied or not secret:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied.strip().lower())


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def merchant_id_from_payload(payload: dict[str, Any], data: dict[str, Any] | None = None) -> int | None:
    """Read the merchant identifier from Salla's documented event shapes.

    Salla's app events use a numeric top-level ``merchant`` field. Some
    integrations/proxies may wrap it as ``{"id": ...}``, while older payloads
    can place it in ``data.merchant_id``; accept all three without loosening
    validation of the authorization tokens themselves.
    """
    raw_merchant = payload.get("merchant")
    if isinstance(raw_merchant, dict):
        raw_merchant = raw_merchant.get("id")
    if raw_merchant is None and isinstance(data, dict):
        raw_merchant = data.get("merchant_id")
    try:
        return int(raw_merchant) if raw_merchant is not None else None
    except (TypeError, ValueError):
        return None


def order_is_eligible(order: dict[str, Any]) -> bool:
    status = str((order.get("status") or {}).get("slug") or order.get("status_slug") or "").casefold()
    if status in {"cancelled", "canceled", "refunded", "deleted", "failed", "rejected"}:
        return False
    if order.get("is_pending_payment") is True:
        return False
    actions = order.get("actions") or {}
    if isinstance(actions, dict) and actions.get("payable") is True:
        return False
    payment_actions = order.get("payment_actions") or {}
    remaining = payment_actions.get("remaining_action") if isinstance(payment_actions, dict) else None
    if isinstance(remaining, dict) and remaining.get("has_remaining_amount") is True:
        return False
    payment = str(order.get("payment_status") or "").casefold()
    if payment in {"unpaid", "pending", "failed", "cancelled", "canceled", "refunded"}:
        return False
    return status in {"paid", "completed", "processing", "shipped", "delivered", "in_progress"} or (not status and payment == "paid")


def customer_email(order: dict[str, Any]) -> str | None:
    customer = order.get("customer") or {}
    email = customer.get("email") if isinstance(customer, dict) else None
    return normalize_email(email) if isinstance(email, str) and "@" in email else None


def order_reference(order: dict[str, Any]) -> str:
    return str(order.get("reference_id") or order.get("reference") or "").strip()


def order_items(order: dict[str, Any]) -> list[dict[str, Any]]:
    items = order.get("items") or order.get("products") or []
    return [item for item in items if isinstance(item, dict)]


@dataclass(frozen=True)
class SallaOrder:
    merchant_id: int
    order_id: int
    reference_id: str
    raw: dict[str, Any]


class SallaClient:
    def __init__(self, access_token: str):
        self.access_token = access_token

    def _request_sync(self, method: str, url: str, *, body: bytes | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
        request = urllib.request.Request(url, data=body, method=method, headers={"Accept": "application/json", "User-Agent": SALLA_USER_AGENT, **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read()
                return json.loads(raw or b"{}")
        except urllib.error.HTTPError as exc:
            retry = exc.headers.get("Retry-After")
            if exc.code == 429:
                raise SallaApiError("rate_limited", exc.code, int(retry) if retry and retry.isdigit() else 30) from exc
            if exc.code == 401:
                raise SallaApiError("token_expired", exc.code) from exc
            raise SallaApiError("salla_http_error", exc.code) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise SallaApiError("salla_unavailable") from exc

    async def _request(self, method: str, url: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._request_sync, method, url, headers={"Authorization": f"Bearer {self.access_token}"})

    async def list_orders_by_reference(self, reference: str) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"reference_id": reference, "per_page": 30})
        payload = await self._request("GET", f"{SALLA_API}/orders?{query}")
        data = payload.get("data") or []
        return [item for item in data if isinstance(item, dict)]

    async def get_order(self, order_id: int) -> dict[str, Any]:
        payload = await self._request("GET", f"{SALLA_API}/orders/{order_id}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise SallaApiError("invalid_salla_order_response")
        return data

    async def list_order_items(self, order_id: int) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"order_id": order_id})
        payload = await self._request("GET", f"{SALLA_API}/orders/items?{query}")
        data = payload.get("data") or []
        return [item for item in data if isinstance(item, dict)]


def _refresh_sync(refresh_token: str, client_id: str, client_secret: str) -> dict[str, Any]:
    form = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id, "client_secret": client_secret}).encode()
    request = urllib.request.Request(f"{SALLA_ACCOUNTS}/oauth2/token", data=form, method="POST", headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read() or b"{}")
            if not isinstance(data.get("access_token"), str) or not isinstance(data.get("refresh_token"), str):
                raise SallaApiError("invalid_refresh_response")
            return data
    except urllib.error.HTTPError as exc:
        raise SallaApiError("refresh_rejected", exc.code) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SallaApiError("salla_unavailable") from exc


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.salla_client_id or not settings.salla_client_secret or not settings.salla_client_secret.get_secret_value():
        raise SallaApiError("salla_client_credentials_missing")
    return await asyncio.to_thread(_refresh_sync, refresh_token, settings.salla_client_id, settings.salla_client_secret.get_secret_value())


def token_ciphertext(value: str) -> bytes:
    return encrypt_salla_secret(value)


def token_expiry(expires: int | float | str) -> datetime:
    try:
        return datetime.fromtimestamp(float(expires), tz=UTC)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("invalid_token_expiry") from exc


def install_url() -> str | None:
    app_id = get_settings().salla_app_id
    return f"https://s.salla.sa/apps/install/{app_id}" if app_id else None
