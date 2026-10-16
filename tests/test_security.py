from __future__ import annotations

import pytest
from app.security import (
    activation_expiry,
    code_hash,
    customer_session_expiry,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    mask_account_identifier,
    new_random_token,
    sha256,
    utcnow,
    verify_password,
)


def test_password_hashing_and_verification():
    raw_password = "SuperSecretPassword2026!"
    hashed = hash_password(raw_password)
    assert hashed != raw_password
    assert hashed.startswith("$argon2id$")                 
    assert verify_password(hashed, raw_password) is True
    assert verify_password(hashed, "WrongPassword123!") is False


def test_mask_account_identifier():
    assert mask_account_identifier("ab") == "***"
    assert mask_account_identifier("gamer") == "g***r"
    assert mask_account_identifier("steampower123") == "ste***123"


def test_secret_encryption_and_decryption():
    secret = "my_mail_app_password_999"
    encrypted = encrypt_secret(secret)
    assert isinstance(encrypted, bytes)
    assert encrypted != secret.encode()
    decrypted = decrypt_secret(encrypted)
    assert decrypted == secret


def test_sha256_and_token():
    token = new_random_token(32)
    assert len(token) > 30
    h1 = sha256(token)
    h2 = sha256(token)
    assert h1 == h2
    assert len(h1) == 64
    assert code_hash("12345") == sha256("12345")


def test_customer_session_expiry_uses_minutes():
    from datetime import UTC, timedelta
    from unittest.mock import patch
    from app.config import get_settings

    settings = get_settings()
    t_before = utcnow()
    exp = customer_session_expiry()
    t_after = utcnow()

    # Must be UTC-aware datetime
    assert exp.tzinfo is not None
    assert exp.tzinfo == UTC or exp.utcoffset() == timedelta(0)

    # Difference matches configured customer_session_minutes
    expected_delta = timedelta(minutes=settings.customer_session_minutes)
    assert t_before + expected_delta <= exp <= t_after + expected_delta

    # Test dynamic calculation with custom minutes
    with patch("app.security.get_settings") as mock_get_settings:
        mock_settings = type("MockSettings", (), {
            "customer_session_minutes": 45,
            "activation_token_hours": 24,
            "admin_session_hours": 12,
        })()
        mock_get_settings.return_value = mock_settings

        t0 = utcnow()
        exp_45 = customer_session_expiry()
        assert (exp_45 - t0).total_seconds() == pytest.approx(45 * 60, abs=2)


def test_activation_expiry_independent_from_customer_session_expiry():
    from datetime import timedelta
    from unittest.mock import patch

    with patch("app.security.get_settings") as mock_get_settings:
        mock_settings = type("MockSettings", (), {
            "customer_session_minutes": 60,
            "activation_token_hours": 24,
            "admin_session_hours": 12,
        })()
        mock_get_settings.return_value = mock_settings

        t0 = utcnow()
        act_exp_1 = activation_expiry()
        cust_exp_1 = customer_session_expiry()

        assert (act_exp_1 - t0).total_seconds() == pytest.approx(24 * 3600, abs=2)
        assert (cust_exp_1 - t0).total_seconds() == pytest.approx(60 * 60, abs=2)

        # Change activation_token_hours to 72 hours; customer session duration MUST remain 60 minutes
        mock_settings.activation_token_hours = 72
        act_exp_2 = activation_expiry()
        cust_exp_2 = customer_session_expiry()

        assert (act_exp_2 - t0).total_seconds() == pytest.approx(72 * 3600, abs=2)
        assert (cust_exp_2 - t0).total_seconds() == pytest.approx(60 * 60, abs=2)

        # Conversely, change customer_session_minutes to 15 minutes; activation token duration MUST remain 72 hours
        mock_settings.customer_session_minutes = 15
        act_exp_3 = activation_expiry()
        cust_exp_3 = customer_session_expiry()

        assert (act_exp_3 - t0).total_seconds() == pytest.approx(72 * 3600, abs=2)
        assert (cust_exp_3 - t0).total_seconds() == pytest.approx(15 * 60, abs=2)
    