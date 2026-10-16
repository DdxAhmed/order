from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest
from app.mail.imap_provider import ParsedMailMessage
from app.platforms.steam import SteamMailAdapter


@pytest.fixture
def sample_steam_profile():
    return {
        "sender_domains": ["steampowered.com"],
        "required_auth_result": "dkim=pass",
        "sample_verified_at": "2026-09-08T00:00:00Z",
        "account_patterns": [
            r"Dear\s+([A-Za-z0-9_]+)",
            r"Estimado/a\s+([A-Za-z0-9_]+)",
            r"Скъпи\s+([A-Za-z0-9_]+)",
        ],
        "code_patterns": [
            r"login code is\s+([A-Z0-9]{5})",
            r"código de inicio de sesión es\s+([A-Z0-9]{5})",
            r"код за влизане е\s+([A-Z0-9]{5})",
        ],
    }


def test_adapter_configuration(sample_steam_profile):
    adapter = SteamMailAdapter(sample_steam_profile)
    assert adapter.configured is True

    unconfigured = SteamMailAdapter({})
    assert unconfigured.configured is False


def test_english_steam_email_extraction(sample_steam_profile):
    adapter = SteamMailAdapter(sample_steam_profile)
    now = datetime.now(UTC)
    message = ParsedMailMessage(
        uidvalidity="1",
        uid="100",
        message_date=now,
        from_address="Steam Support <noreply@steampowered.com>",
        subject="Your Steam account: Access from new web or mobile device",
        text="Dear gamer_pro,\nHere is your Steam Guard code. Your login code is G7K9Q.\nIf you did not request this, ignore.",
        html="",
        authentication_results="dkim=pass header.i=@steampowered.com",
        message_id="msg-1",
        headers={"message-id": "msg-1"},
    )

    extracted = adapter.extract(message, "gamer_pro", now - timedelta(minutes=5))
    assert extracted is not None
    assert extracted.code == "G7K9Q"


def test_spanish_steam_email_extraction(sample_steam_profile):
    adapter = SteamMailAdapter(sample_steam_profile)
    now = datetime.now(UTC)
    message = ParsedMailMessage(
        uidvalidity="1",
        uid="101",
        message_date=now,
        from_address="Soporte de Steam <noreply@steampowered.com>",
        subject="Tu cuenta de Steam: acceso desde un nuevo dispositivo",
        text="Estimado/a gamer_pro,\nTu código de inicio de sesión es ABC12.\nSaludos.",
        html="",
        authentication_results="dkim=pass header.i=@steampowered.com",
        message_id="msg-2",
        headers={"message-id": "msg-2"},
    )

    extracted = adapter.extract(message, "gamer_pro", now - timedelta(minutes=5))
    assert extracted is not None
    assert extracted.code == "ABC12"


def test_rejection_of_spoofed_or_mismatched(sample_steam_profile):
    adapter = SteamMailAdapter(sample_steam_profile)
    now = datetime.now(UTC)

    # 1. Spoofed domain
    spoofed = ParsedMailMessage(
        uidvalidity="1",
        uid="102",
        message_date=now,
        from_address="Steam Support <fake@hacker.com>",
        subject="Your code",
        text="Dear gamer_pro,\nYour login code is G7K9Q.",
        html="",
        authentication_results="dkim=pass",
        message_id="msg-3",
        headers={},
    )
    assert adapter.extract(spoofed, "gamer_pro", now - timedelta(minutes=5)) is None

    # 2. Failed DKIM
    no_dkim = ParsedMailMessage(
        uidvalidity="1",
        uid="103",
        message_date=now,
        from_address="Steam Support <noreply@steampowered.com>",
        subject="Your code",
        text="Dear gamer_pro,\nYour login code is G7K9Q.",
        html="",
        authentication_results="dkim=fail",
        message_id="msg-4",
        headers={},
    )
    assert adapter.extract(no_dkim, "gamer_pro", now - timedelta(minutes=5)) is None

    # 3. Wrong account username
    wrong_user = ParsedMailMessage(
        uidvalidity="1",
        uid="104",
        message_date=now,
        from_address="Steam Support <noreply@steampowered.com>",
        subject="Your code",
        text="Dear another_user,\nYour login code is G7K9Q.",
        html="",
        authentication_results="dkim=pass",
        message_id="msg-5",
        headers={},
    )
    assert adapter.extract(wrong_user, "gamer_pro", now - timedelta(minutes=5)) is None
