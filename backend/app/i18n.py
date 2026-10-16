from __future__ import annotations

from typing import Any


SUPPORTED_LANGUAGES = {
    "ar": {"label": "العربية", "direction": "rtl"},
    "en": {"label": "English", "direction": "ltr"},
    "es": {"label": "Español", "direction": "ltr"},
}


TRANSLATIONS: dict[str, dict[str, str]] = {
    "ar": {
        "brand": "تسليم الأكواد",
        "public_title": "بوابة تسليم أكواد Steam",
        "language": "اللغة",
        "admin_title": "إدارة تسليم الأكواد",
        "home_heading": "بوابة تسليم أكواد Steam",
        "home_intro": "لا يوجد تسجيل عام أو كلمة مرور للعميل. المتجر ينشئ طلبك ويرسل لك رابطًا أو رمز تفعيل خاصًا.",
        "activation_token": "رمز التفعيل",
        "open_order": "فتح الطلب",
        "home_hint": "إذا وصلك رابط كامل، افتحه مباشرة من الرسالة. لا تطلب الخدمة كلمة مرور حساب Steam.",
        "activate_heading": "تفعيل طلبك",
        "activate_intro": "هذا رابط دخول خاص بالعميل، وليس رمز Steam نفسه. اضغط للمتابعة إلى بوابة حسابك؛ الرابط ينتهي تلقائيًا.",
        "activate_button": "تفعيل الطلب والدخول",
        "portal_welcome": "مرحبًا {name}",
        "portal_session": "هذه البوابة مرتبطة بطلبك فقط. تنتهي الجلسة تلقائيًا.",
        "logout": "تسجيل الخروج",
        "assigned_accounts": "الحسابات المخصصة",
        "portal_hint": "اختر الحساب ثم اطلب رمز Steam. سيظهر الرمز هنا بعد وصول رسالة التحقق.",
        "steam_assigned": "حساب Steam مخصص",
        "refresh_later": "حدّث الصفحة بعد قليل",
        "keep_code": "احتفظ بالرمز ولا تشاركه.",
        "request_code": "طلب رمز التحقق",
        "no_accounts": "لا توجد حسابات مفعلة لهذا الرابط.",
        "recent_requests": "آخر الطلبات",
        "no_requests": "لم تطلب رمزًا بعد.",
        "status_queued": "تم الاستلام",
        "status_processing": "جارٍ البحث",
        "status_waiting_mail": "بانتظار رسالة Steam",
        "status_succeeded": "تم العثور على الرمز",
        "status_failed": "تعذر إكمال البحث",
        "status_expired": "انتهت المهلة",
        "status_delivery_uncertain": "الإرسال غير مؤكد",
    },
    "en": {
        "brand": "Code Delivery",
        "public_title": "Steam Code Delivery Portal",
        "language": "Language",
        "admin_title": "Code Delivery Admin",
        "home_heading": "Steam Code Delivery Portal",
        "home_intro": "There is no public registration or customer password. The store creates an order and sends a private activation link or token.",
        "activation_token": "Activation token",
        "open_order": "Open order",
        "home_hint": "If you received a complete link, open it directly. The service never asks for your Steam account password.",
        "activate_heading": "Activate your order",
        "activate_intro": "This is a private customer access link, not the Steam code itself. Continue to your account portal; the link expires automatically.",
        "activate_button": "Activate and continue",
        "portal_welcome": "Welcome, {name}",
        "portal_session": "This portal is limited to your order. Your session expires automatically.",
        "logout": "Sign out",
        "assigned_accounts": "Assigned accounts",
        "portal_hint": "Choose an account and request a Steam code. It will appear here after the verification email arrives.",
        "steam_assigned": "Assigned Steam account",
        "refresh_later": "Refresh the page shortly",
        "keep_code": "Keep the code private and do not share it.",
        "request_code": "Request verification code",
        "no_accounts": "No active accounts are available for this link.",
        "recent_requests": "Recent requests",
        "no_requests": "You have not requested a code yet.",
        "status_queued": "Received",
        "status_processing": "Searching",
        "status_waiting_mail": "Waiting for Steam email",
        "status_succeeded": "Code found",
        "status_failed": "Could not complete the search",
        "status_expired": "Expired",
        "status_delivery_uncertain": "Delivery uncertain",
    },
    "es": {
        "brand": "Entrega de códigos",
        "public_title": "Portal de entrega de códigos Steam",
        "language": "Idioma",
        "admin_title": "Administración de entrega de códigos",
        "home_heading": "Portal de entrega de códigos Steam",
        "home_intro": "No hay registro público ni contraseña para el cliente. La tienda crea el pedido y envía un enlace o token de activación privado.",
        "activation_token": "Token de activación",
        "open_order": "Abrir pedido",
        "home_hint": "Si recibiste un enlace completo, ábrelo directamente. El servicio nunca solicita la contraseña de tu cuenta de Steam.",
        "activate_heading": "Activar tu pedido",
        "activate_intro": "Este es un enlace privado de acceso del cliente, no el código de Steam. Continúa al portal de tu cuenta; el enlace caduca automáticamente.",
        "activate_button": "Activar y continuar",
        "portal_welcome": "Bienvenido, {name}",
        "portal_session": "Este portal está limitado a tu pedido. La sesión caduca automáticamente.",
        "logout": "Cerrar sesión",
        "assigned_accounts": "Cuentas asignadas",
        "portal_hint": "Elige una cuenta y solicita un código de Steam. Aparecerá aquí cuando llegue el correo de verificación.",
        "steam_assigned": "Cuenta de Steam asignada",
        "refresh_later": "Actualiza la página en unos instantes",
        "keep_code": "Mantén el código privado y no lo compartas.",
        "request_code": "Solicitar código de verificación",
        "no_accounts": "No hay cuentas activas para este enlace.",
        "recent_requests": "Solicitudes recientes",
        "no_requests": "Todavía no has solicitado ningún código.",
        "status_queued": "Recibida",
        "status_processing": "Buscando",
        "status_waiting_mail": "Esperando el correo de Steam",
        "status_succeeded": "Código encontrado",
        "status_failed": "No se pudo completar la búsqueda",
        "status_expired": "Caducada",
        "status_delivery_uncertain": "Entrega no confirmada",
    },
}


def normalize_language(value: str | None) -> str:
    return value if value in SUPPORTED_LANGUAGES else "ar"


def language_meta(language: str) -> dict[str, str]:
    return SUPPORTED_LANGUAGES[normalize_language(language)]


def translate(language: str, key: str, **values: Any) -> str:
    lang = normalize_language(language)
    text = TRANSLATIONS.get(lang, TRANSLATIONS["ar"]).get(key, TRANSLATIONS["ar"].get(key, key))
    return text.format(**values) if values else text
