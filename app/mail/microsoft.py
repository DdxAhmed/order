from __future__ import annotations

import json
import base64
import hashlib
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from app.config import Settings, get_settings
from app.mail.imap_provider import MailProviderError, ParsedMailMessage
from app.models import Mailbox
from app.security import decrypt_secret


MICROSOFT_SCOPES = ("openid", "profile", "email", "offline_access", "Mail.Read")
GRAPH_MESSAGES_URL = "https://graph.microsoft.com/v1.0/me/mailFolders/{folder}/messages"


def microsoft_oauth_configured(settings: Settings | None = None) -> bool:
    """Return whether the configured OAuth client is usable for this environment."""
    settings = settings or get_settings()
    if not settings.microsoft_oauth_client_id:
        return False
    # Production is registered as a confidential Web application.  Do not
    # start or redeem a production flow without its matching client secret.
    return not settings.is_production or bool(settings.microsoft_oauth_client_secret)


def microsoft_redirect_uri(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return settings.microsoft_oauth_redirect_uri or (
        f"{settings.public_base_url.rstrip('/')}/admin/mailboxes/oauth/callback"
    )


def _oauth_endpoint(settings: Settings, path: str) -> str:
    tenant = urllib.parse.quote(settings.microsoft_oauth_tenant, safe="")
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/{path}"


def build_authorization_url(
    state: str,
    settings: Settings | None = None,
    code_challenge: str | None = None,
) -> str:
    settings = settings or get_settings()
    if not microsoft_oauth_configured(settings):
        raise MailProviderError("microsoft_oauth_not_configured")
    query = urllib.parse.urlencode(
        {
            "client_id": settings.microsoft_oauth_client_id,
            "response_type": "code",
            "redirect_uri": microsoft_redirect_uri(settings),
            "response_mode": "query",
            "scope": " ".join(MICROSOFT_SCOPES),
            "state": state,
            "prompt": "select_account",
            **({"code_challenge": code_challenge, "code_challenge_method": "S256"} if code_challenge else {}),
        }
    )
    return f"{_oauth_endpoint(settings, 'authorize')}?{query}"


def _post_form(url: str, values: dict[str, str]) -> dict:
    body = urllib.parse.urlencode(values).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise MailProviderError("microsoft_oauth_exchange_failed") from exc


def exchange_authorization_code(
    code: str,
    code_verifier: str | None = None,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    if not microsoft_oauth_configured(settings):
        raise MailProviderError("microsoft_oauth_not_configured")
    values = {
        "client_id": settings.microsoft_oauth_client_id,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": microsoft_redirect_uri(settings),
        "scope": " ".join(MICROSOFT_SCOPES),
    }
    if code_verifier:
        values["code_verifier"] = code_verifier
    # A configured production Web app always reaches this branch with a
    # secret; the conditional keeps development/public-client tests usable.
    if settings.microsoft_oauth_client_secret:
        values["client_secret"] = settings.microsoft_oauth_client_secret.get_secret_value()
    result = _post_form(_oauth_endpoint(settings, "token"), values)
    if not result.get("refresh_token"):
        raise MailProviderError("microsoft_oauth_missing_refresh_token")
    return result


def pkce_verifier() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode("ascii")


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def refresh_access_token(refresh_token: str, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    if not microsoft_oauth_configured(settings):
        raise MailProviderError("microsoft_oauth_not_configured")
    values = {
        "client_id": settings.microsoft_oauth_client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": " ".join(MICROSOFT_SCOPES),
    }
    if settings.microsoft_oauth_client_secret:
        values["client_secret"] = settings.microsoft_oauth_client_secret.get_secret_value()
    result = _post_form(_oauth_endpoint(settings, "token"), values)
    if not result.get("access_token"):
        raise MailProviderError("microsoft_oauth_refresh_failed")
    return result


def _graph_message_date(value: str | None) -> datetime:
    try:
        parsed = datetime.fromisoformat((value or "").replace("Z", "+00:00"))
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)).astimezone(UTC)
    except (TypeError, ValueError):
        return datetime.now(UTC)


class MicrosoftGraphMailProvider:
    """Read-only Outlook provider using delegated OAuth2 and Microsoft Graph."""

    def __init__(self, mailbox: Mailbox, timeout_seconds: int = 15):
        self.mailbox = mailbox
        self.timeout_seconds = timeout_seconds
        self.rotated_refresh_token: str | None = None

    def _access_token(self) -> str:
        if not self.mailbox.oauth_refresh_token:
            raise MailProviderError("microsoft_oauth_not_connected")
        result = refresh_access_token(decrypt_secret(self.mailbox.oauth_refresh_token))
        self.rotated_refresh_token = result.get("refresh_token")
        return str(result["access_token"])

    def recent_messages(
        self,
        since: datetime,
        limit: int = 30,
        *,
        subject_contains: str | None = None,
    ) -> list[ParsedMailMessage]:
        access_token = self._access_token()
        since_value = since.astimezone(UTC).isoformat().replace("+00:00", "Z")
        filters = [f"receivedDateTime ge {since_value}"]
        if subject_contains:
            # OData string literals escape apostrophes by doubling them.  A
            # server-side subject filter keeps unrelated mailbox bodies out
            # of the Salla-notification pipeline.
            filters.append(f"contains(subject,'{subject_contains.replace(chr(39), chr(39) * 2)}')")
        query = urllib.parse.urlencode(
            {
                "$filter": " and ".join(filters),
                "$top": str(limit),
                "$select": "id,internetMessageId,from,subject,receivedDateTime,body,internetMessageHeaders",
                **({} if subject_contains else {"$orderby": "receivedDateTime desc"}),
            }
        )
        folder = self.mailbox.mail_folder or "inbox"
        if folder.casefold() == "inbox":
            folder = "inbox"
        request = urllib.request.Request(
            f"{GRAPH_MESSAGES_URL.format(folder=urllib.parse.quote(folder, safe=''))}?{query}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
                # Plain text preserves the line boundaries used by the verified Steam profile.
                "Prefer": 'outlook.body-content-type="text"',
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise MailProviderError("microsoft_graph_read_failed") from exc
        messages: list[ParsedMailMessage] = []
        for item in payload.get("value", []):
            sender = ((item.get("from") or {}).get("emailAddress") or {}).get("address", "")
            body = item.get("body") or {}
            content = str(body.get("content") or "")
            content_type = str(body.get("contentType") or "html").casefold()
            headers = item.get("internetMessageHeaders") or []
            header_values = {
                str(header.get("name") or "").casefold(): str(header.get("value") or "")
                for header in headers
                if header.get("name")
            }
            authentication_results = "\n".join(
                str(header.get("value") or "")
                for header in headers
                if str(header.get("name") or "").casefold() == "authentication-results"
            )
            messages.append(
                ParsedMailMessage(
                    uidvalidity="microsoft-graph-v1",
                    uid=str(item.get("id") or ""),
                    message_date=_graph_message_date(item.get("receivedDateTime")),
                    from_address=sender,
                    subject=str(item.get("subject") or ""),
                    text=content if content_type == "text" else "",
                    html=content if content_type != "text" else "",
                    authentication_results=authentication_results,
                    message_id=str(item.get("internetMessageId") or header_values.get("message-id") or item.get("id") or ""),
                    headers=header_values,
                )
            )
        return messages
