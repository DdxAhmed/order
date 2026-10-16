from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

_password_hasher = PasswordHasher()


def utcnow() -> datetime:
    return datetime.now(UTC)


def sha256(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def new_random_token(bytes_count: int = 32) -> str:
    return secrets.token_urlsafe(bytes_count)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _password_hasher.check_needs_rehash(password_hash)


def encrypt_secret(value: str) -> bytes:
    key = get_settings().mail_credentials_key.get_secret_value().encode("utf-8")
    return Fernet(key).encrypt(value.encode("utf-8"))


def decrypt_secret(value: bytes) -> str:
    key = get_settings().mail_credentials_key.get_secret_value().encode("utf-8")
    try:
        return Fernet(key).decrypt(value).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("لا يمكن فك بيانات صندوق البريد بالمفتاح الحالي") from exc


def encrypt_salla_secret(value: str) -> bytes:
    settings = get_settings()
    configured = settings.salla_token_key.get_secret_value() if settings.salla_token_key else ""
    key = (configured or settings.mail_credentials_key.get_secret_value()).encode("utf-8")
    return Fernet(key).encrypt(value.encode("utf-8"))


def decrypt_salla_secret(value: bytes) -> str:
    settings = get_settings()
    configured = settings.salla_token_key.get_secret_value() if settings.salla_token_key else ""
    key = (configured or settings.mail_credentials_key.get_secret_value()).encode("utf-8")
    try:
        return Fernet(key).decrypt(value).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("لا يمكن فك رمز Salla بالمفتاح الحالي") from exc


def session_expiry() -> datetime:
    return utcnow() + timedelta(hours=get_settings().admin_session_hours)


def activation_expiry() -> datetime:
    return utcnow() + timedelta(hours=get_settings().activation_token_hours)


def customer_session_expiry() -> datetime:
    return utcnow() + timedelta(minutes=get_settings().customer_session_minutes)


def make_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def mask_account_identifier(value: str) -> str:
    value = value.strip()
    if len(value) <= 2:
        return "***"
    if len(value) < 7:
        return f"{value[0]}***{value[-1]}"
    return f"{value[:3]}***{value[-3:]}"


def code_hash(code: str) -> str:
    return sha256(code)


def safe_b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")
