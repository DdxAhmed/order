from __future__ import annotations

import logging
import uuid

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update

from app.config import get_settings
from app.db import SessionLocal
from app.models import VerificationRequest, VerificationStatus
from app.security import mask_account_identifier
from app.services.customer import (
    CustomerAccessError,
    activate_order,
    assignments_for_telegram,
    result_for_customer,
    verification_statuses_for_telegram,
)
from app.services.inventory import create_verification_request
from app.services.access import consume_rate_limit

router = Router()
logger = logging.getLogger(__name__)


def _bot() -> Bot | None:
    token = get_settings().telegram_bot_token
    return Bot(token=token.get_secret_value()) if token else None


@router.message(Command("start"))
async def start(message: Message, command: CommandObject) -> None:
    if not message.from_user:
        return
    async with SessionLocal.begin() as session:
        allowed = await consume_rate_limit(session, "telegram_accounts", str(message.from_user.id), 60, 20)
    if not allowed:
        await message.answer("تم تجاوز الحد المؤقت. حاول بعد دقيقة.")
        return
    if command.args:
        async with SessionLocal.begin() as session:
            try:
                await activate_order(session, command.args.strip(), message.from_user.id)
            except CustomerAccessError:
                await message.answer("تعذر تفعيل الطلب. راجع المتجر إذا استمرت المشكلة.")
                return
        await message.answer("تم تفعيل طلبك بنجاح ✅ أرسل /accounts لعرض الحسابات المخصصة لك.")
        return
    await message.answer("أهلًا بك. افتح رابط التفعيل أو استخدم /activate ثم الرمز، وبعدها أرسل /accounts.")


@router.message(Command("activate"))
async def activate(message: Message, command: CommandObject) -> None:
    if not message.from_user or not command.args:
        await message.answer("استخدم: /activate رمز_التفعيل")
        return
    async with SessionLocal.begin() as session:
        try:
            await activate_order(session, command.args.strip(), message.from_user.id)
        except CustomerAccessError:
            await message.answer("تعذر تفعيل الطلب. راجع المتجر إذا استمرت المشكلة.")
            return
    await message.answer("تم تفعيل طلبك بنجاح ✅ أرسل /accounts لعرض الحسابات.")


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer("الأوامر: /activate رمز، /accounts، /status. لا تطلب منك الخدمة كلمات مرور أو محتوى البريد.")


@router.message(Command("accounts"))
async def accounts(message: Message) -> None:
    if not message.from_user:
        return
    async with SessionLocal() as session:
        items = await assignments_for_telegram(session, message.from_user.id)
    if not items:
        await message.answer("لا توجد حسابات مخصصة لك حاليًا.")
        return
    buttons = [
        [InlineKeyboardButton(text=f"طلب رمز {mask_account_identifier(account.identifier)}", callback_data=f"verify:{assignment.id}")]
        for assignment, account in items
    ]
    await message.answer("اختر الحساب المطلوب:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.message(Command("status"))
async def verification_status(message: Message) -> None:
    if not message.from_user:
        return
    async with SessionLocal() as session:
        requests = await verification_statuses_for_telegram(session, message.from_user.id)
        uncertain = next((request for request in requests if request.status == VerificationStatus.DELIVERY_UNCERTAIN.value), None)
        if uncertain:
            result = await result_for_customer(session, uncertain.id, message.from_user.id)
            if result:
                account, code = result
                await message.answer(f"رمز الحساب {account} هو: {code}\nلا تشاركه مع أي شخص.")
                return
    if not requests:
        await message.answer("لا توجد طلبات تحقق حديثة.")
        return
    labels = {"queued": "في الانتظار", "processing": "جارٍ البحث", "waiting_mail": "بانتظار الرسالة", "succeeded": "تم الإرسال", "failed": "تعذر البحث", "expired": "انتهت المهلة", "delivery_uncertain": "حالة الإرسال غير مؤكدة"}
    await message.answer("آخر الحالات:\n" + "\n".join(f"• {labels.get(item.status, 'حالة غير معروفة')}" for item in requests))


@router.callback_query(lambda callback: callback.data and callback.data.startswith("verify:"))
async def request_code(callback: CallbackQuery) -> None:
    if not callback.from_user or not callback.data:
        return
    try:
        assignment_id = uuid.UUID(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("طلب غير صالح", show_alert=True)
        return
    async with SessionLocal.begin() as session:
        if not await consume_rate_limit(session, "telegram_verify", str(callback.from_user.id), 600, 5):
            await callback.answer("تم تجاوز الحد المؤقت. حاول لاحقًا.", show_alert=True)
            return
        items = await assignments_for_telegram(session, callback.from_user.id)
        assignment = next((item[0] for item in items if item[0].id == assignment_id), None)
        if not assignment:
            await callback.answer("لا يمكن الوصول إلى هذا الحساب", show_alert=True)
            return
        await create_verification_request(
            session,
            assignment,
            get_settings().verification_wait_seconds,
            telegram_user_id=callback.from_user.id,
        )
    await callback.answer("تم استلام الطلب")
    await callback.message.answer("نبحث عن رمز التحقق الآن. أرسل /accounts لاحقًا لمتابعة الحساب.")


async def feed_webhook_update(payload: dict) -> None:
    bot = _bot()
    if not bot:
        return
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.feed_update(bot, Update.model_validate(payload))


async def send_result_if_ready(verification_request_id: uuid.UUID) -> bool:
    """Used by a notifier job once a code exists. Never sends body content or mailbox credentials."""
    bot = _bot()
    if not bot:
        return False
    async with SessionLocal() as session:
        request = await session.get(VerificationRequest, verification_request_id)
        if not request:
            return False
        result = await result_for_customer(session, request.id, request.requested_by_telegram_id)
    if not result:
        return False
    account, code = result
    try:
        await bot.send_message(
            request.requested_by_telegram_id,
            f"تم التحقق من طلبك بنجاح ✅\nرمز التحقق الخاص بحسابك {account} هو: {code}\nلا تشاركه مع أي شخص.",
        )
        async with SessionLocal.begin() as session:
            db_request = await session.get(VerificationRequest, verification_request_id, with_for_update=True)
            if db_request:
                db_request.delivered_at = __import__("app.security", fromlist=["utcnow"]).utcnow()
                db_request.status = VerificationStatus.SUCCEEDED.value
        return True
    except Exception:
        logger.warning("telegram delivery uncertain for verification request %s", verification_request_id)
        async with SessionLocal.begin() as session:
            db_request = await session.get(VerificationRequest, verification_request_id, with_for_update=True)
            if db_request and db_request.status == VerificationStatus.SUCCEEDED.value:
                db_request.status = VerificationStatus.DELIVERY_UNCERTAIN.value
        return False
