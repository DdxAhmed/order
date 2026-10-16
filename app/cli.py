from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.mail import ImapMailProvider, MicrosoftGraphMailProvider
from app.models import AdminRole, AdminUser, Mailbox, Platform
from app.security import encrypt_secret, hash_password, utcnow


async def create_admin(email: str, password: str | None = None) -> int:
    if not password:
        password = getpass.getpass("كلمة مرور المدير: ")
        confirmation = getpass.getpass("أعد كلمة المرور: ")
        if len(password) < 14 or password != confirmation:
            print("يجب أن تتطابق كلمة المرور وأن تكون 14 حرفًا على الأقل.", file=sys.stderr)
            return 2
    elif len(password) < 14:
        print("يجب أن تكون كلمة المرور 14 حرفًا على الأقل.", file=sys.stderr)
        return 2
    async with SessionLocal.begin() as session:
        if await session.scalar(select(AdminUser).where(AdminUser.email == email.casefold().strip())):
            print("هذا المدير موجود بالفعل.", file=sys.stderr)
            return 2
        session.add(AdminUser(email=email.casefold().strip(), password_hash=hash_password(password), role=AdminRole.OWNER.value))
    print("تم إنشاء مدير المالك. لا توجد بيانات دخول افتراضية.")
    return 0


async def change_password(email: str, password: str | None = None) -> int:
    if not password:
        password = getpass.getpass("كلمة المرور الجديدة: ")
        confirmation = getpass.getpass("أعد كلمة المرور الجديدة: ")
        if len(password) < 14 or password != confirmation:
            print("يجب أن تتطابق كلمة المرور وأن تكون 14 حرفًا على الأقل.", file=sys.stderr)
            return 2
    elif len(password) < 14:
        print("يجب أن تكون كلمة المرور 14 حرفًا على الأقل.", file=sys.stderr)
        return 2
    async with SessionLocal.begin() as session:
        admin = await session.scalar(select(AdminUser).where(AdminUser.email == email.casefold().strip()))
        if not admin:
            print("المدير غير موجود.", file=sys.stderr)
            return 2
        admin.password_hash = hash_password(password)
    print("تم تحديث كلمة مرور المدير بنجاح.")
    return 0


async def test_mailbox(label: str) -> int:
    async with SessionLocal.begin() as session:
        mailbox = await session.scalar(select(Mailbox).where(Mailbox.label == label))
        if not mailbox:
            print("صندوق البريد غير موجود.", file=sys.stderr)
            return 2
        try:
            provider = (
                MicrosoftGraphMailProvider(mailbox)
                if mailbox.auth_mode == "microsoft_graph"
                else ImapMailProvider(mailbox)
            )
            messages = await asyncio.to_thread(provider.recent_messages, utcnow())
            if getattr(provider, "rotated_refresh_token", None):
                mailbox.oauth_refresh_token = encrypt_secret(provider.rotated_refresh_token)
        except Exception:
            print("تعذر الاتصال بصندوق البريد. راجع الإعدادات دون مشاركة كلمة المرور.", file=sys.stderr)
            return 1
    print(f"نجح اتصال IMAP بشكل آمن. الرسائل المطابقة اليوم: {len(messages)}. لم يُعرض محتوى الرسائل.")
    return 0


async def configure_mailbox(label: str) -> int:
    settings = get_settings()
    if not settings.imap_host or not settings.imap_username or not settings.imap_password:
        print("IMAP_HOST وIMAP_USERNAME وIMAP_PASSWORD مطلوبة.", file=sys.stderr)
        return 2
    async with SessionLocal.begin() as session:
        mailbox = await session.scalar(select(Mailbox).where(Mailbox.label == label).with_for_update())
        if mailbox:
            mailbox.host = settings.imap_host
            mailbox.port = settings.imap_port
            mailbox.username = settings.imap_username
            mailbox.encrypted_password = encrypt_secret(settings.imap_password.get_secret_value())
            mailbox.is_active = True
        else:
            session.add(
                Mailbox(
                    label=label,
                    host=settings.imap_host,
                    port=settings.imap_port,
                    username=settings.imap_username,
                    encrypted_password=encrypt_secret(settings.imap_password.get_secret_value()),
                )
            )
    print("تم حفظ إعداد صندوق البريد مشفرًا.")
    return 0


async def configure_steam(profile_json: str, enable: bool) -> int:
    try:
        profile = json.loads(profile_json)
    except json.JSONDecodeError:
        print("profile-json ليس JSON صالحًا.", file=sys.stderr)
        return 2
    required = {"sender_domains", "account_pattern", "code_pattern", "required_auth_result", "sample_verified_at"}
    if enable and not required.issubset(profile):
        print("لا يمكن تفعيل Steam قبل توثيق عينة فعلية وإدخال قواعد المطابقة المطلوبة.", file=sys.stderr)
        return 2
    async with SessionLocal.begin() as session:
        platform = await session.scalar(select(Platform).where(Platform.code == "steam").with_for_update())
        if not platform:
            print("نفّذ migrations أولًا.", file=sys.stderr)
            return 2
        platform.mail_profile = profile
        platform.is_enabled = enable
    print("تم حفظ إعداد Steam. لا يعني ذلك نجاح التكامل قبل Smoke Test مصرح به.")
    return 0


async def set_webhook() -> int:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_webhook_url or not settings.telegram_webhook_secret:
        print("TELEGRAM_BOT_TOKEN وTELEGRAM_WEBHOOK_URL وTELEGRAM_WEBHOOK_SECRET مطلوبة.", file=sys.stderr)
        return 2
    from aiogram import Bot

    bot = Bot(settings.telegram_bot_token.get_secret_value())
    await bot.set_webhook(settings.telegram_webhook_url, secret_token=settings.telegram_webhook_secret.get_secret_value(), drop_pending_updates=False)
    print("تم ضبط Telegram Webhook دون إسقاط تحديثات معلقة.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="steam-codes")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin")
    create.add_argument("--email", required=True)
    create.add_argument("--password", required=False, default=None)
    chpass = sub.add_parser("change-password")
    chpass.add_argument("--email", required=True)
    chpass.add_argument("--password", required=False, default=None)
    mailbox = sub.add_parser("test-mailbox")
    mailbox.add_argument("--label", required=True)
    configure_mail = sub.add_parser("configure-mailbox")
    configure_mail.add_argument("--label", default=None)
    steam = sub.add_parser("configure-steam")
    steam.add_argument("--profile-json", required=True)
    steam.add_argument("--enable", action="store_true")
    sub.add_parser("set-webhook")
    args = parser.parse_args()
    if args.command == "create-admin":
        code = asyncio.run(create_admin(args.email, args.password))
    elif args.command == "change-password":
        code = asyncio.run(change_password(args.email, args.password))
    elif args.command == "test-mailbox":
        code = asyncio.run(test_mailbox(args.label))
    elif args.command == "configure-mailbox":
        code = asyncio.run(configure_mailbox(args.label or get_settings().imap_label))
    elif args.command == "configure-steam":
        code = asyncio.run(configure_steam(args.profile_json, args.enable))
    else:
        code = asyncio.run(set_webhook())
    raise SystemExit(code)


if __name__ == "__main__":
    main()
