from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parseaddr

from app.mail.imap_provider import ParsedMailMessage
from app.services.inventory import normalize_identifier


@dataclass(frozen=True)
class ExtractedVerificationCode:
    code: str
    message_date: datetime


class SteamMailAdapter:
    """Profile-driven parser. It remains disabled until an owner validates a real authorized sample."""

    REQUIRED_PROFILE_FIELDS = {"sender_domains", "account_pattern", "code_pattern", "required_auth_result"}

    def __init__(self, profile: dict):
        self.profile = profile

    @property
    def configured(self) -> bool:
        has_account_patterns = bool(self.profile.get("account_pattern") or self.profile.get("account_patterns"))
        has_code_patterns = bool(self.profile.get("code_pattern") or self.profile.get("code_patterns"))
        return (
            {"sender_domains", "required_auth_result"}.issubset(self.profile)
            and has_account_patterns
            and has_code_patterns
            and bool(self.profile.get("sample_verified_at"))
        )

    def _patterns(self, singular_key: str, plural_key: str) -> list[str]:
        configured = self.profile.get(plural_key)
        if isinstance(configured, list):
            return [str(item) for item in configured if str(item).strip()]
        value = self.profile.get(singular_key)
        return [str(value)] if value else []

    def extract(self, message: ParsedMailMessage, expected_account_identifier: str, requested_after: datetime) -> ExtractedVerificationCode | None:
        if not self.configured:
            return None
        if message.message_date < requested_after.astimezone(UTC):
            return None
        address = parseaddr(message.from_address)[1].casefold()
        allowed = {str(item).casefold().lstrip("@") for item in self.profile["sender_domains"]}
        if not address or address.rsplit("@", 1)[-1] not in allowed:
            return None
        # A configured provider-side Authentication-Results requirement prevents accepting a display-name spoof.
        required_auth = str(self.profile.get("required_auth_result", "dkim=pass")).casefold()
        if required_auth and required_auth not in message.authentication_results.casefold():
            return None
        body = f"{message.subject}\n{message.text}\n{message.html}"
        account_matches: list[str | tuple[str, ...]] = []
        for pattern in self._patterns("account_pattern", "account_patterns"):
            account_matches.extend(re.findall(pattern, body, re.IGNORECASE | re.MULTILINE))
        normalized_matches = {
            normalize_identifier(match if isinstance(match, str) else match[0])
            for match in account_matches
            if match
        }
        if normalized_matches != {normalize_identifier(expected_account_identifier)}:
            return None
        code_matches: list[str | tuple[str, ...]] = []
        for pattern in self._patterns("code_pattern", "code_patterns"):
            code_matches.extend(re.findall(pattern, body, re.IGNORECASE | re.MULTILINE))
        codes = {match if isinstance(match, str) else match[0] for match in code_matches if match}
        if len(codes) != 1:
            return None
        code = next(iter(codes)).strip()
        if not code or len(code) > 64:
            return None
        return ExtractedVerificationCode(code=code, message_date=message.message_date)
