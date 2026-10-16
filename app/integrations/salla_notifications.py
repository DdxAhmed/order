"""Strict parser for merchant-configured Salla order-notification messages.

This module deliberately extracts entitlement metadata only.  It has no
knowledge of Steam Guard, login codes, passwords, or account credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from email.utils import parseaddr
from html import unescape
import re

from app.mail.imap_provider import ParsedMailMessage


class SallaNotificationError(ValueError):
    pass


@dataclass(frozen=True)
class SallaOrderNotification:
    external_message_id: str
    order_reference: str
    status: str
    eligible: bool
    product_id: str | None
    sku: str | None
    product_name: str | None
    quantity: int | None
    requested_username: str | None
    customer_identifier: str | None
    ownership_method: str


def _html_to_text(value: str) -> str:
    # Preserve boundaries between common message-table cells and blocks. A
    # plain tag strip would concatenate labels and values from adjacent cells.
    value = re.sub(r"<\s*br\s*/?\s*>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"</?\s*(?:p|div|tr|li|h[1-6])\b[^>]*>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"</?\s*(?:td|th)\b[^>]*>", " | ", value, flags=re.IGNORECASE)
    return re.sub(r"[ \t\r\f\v]+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _message_text(message: ParsedMailMessage) -> str:
    return "\n".join(item for item in (message.text, _html_to_text(message.html)) if item).strip()


def _value_after_label(text: str, labels: tuple[str, ...], limit: int = 255) -> str | None:
    for label in labels:
        match = re.search(rf"(?:^|\n|\s){label}\s*[:#\-]?\s*(?:\|\s*)*([^\n|<]{{1,{limit}}})", text, re.IGNORECASE)
        if match:
            value = re.sub(r"\s+", " ", match.group(1)).strip(" .:-")
            if value:
                return value
    return None


def _normalize_status(text: str) -> str | None:
    value = text.casefold()
    if re.search(r"\b(refund(?:ed)?|cancel(?:led|ed)?|void)\b|ملغ[ىي]|مسترد", value):
        return "refunded" if "refund" in value or "مسترد" in value else "cancelled"
    if re.search(r"\b(unpaid|pending|failed|awaiting payment)\b|غير مدفوع|بانتظار الدفع|فشل الدفع", value):
        return "unpaid"
    if re.search(r"\b(paid|payment successful|completed)\b|تم الدفع|مدفوع|مكتمل", value):
        return "paid"
    # Salla can issue a zero-value order (for example, a fully discounted
    # order) with the payment method shown as "مجاني".  This is a settled
    # commerce state, not an unpaid/failed payment.  Keep it normalized to the
    # existing paid state so the entitlement rules remain centralized.
    if re.search(r"\bfree\b|مجاني(?:ة)?", value):
        return "paid"
    return None


def _extract_product_name(text: str) -> str | None:
    """Extract a product from Salla's Arabic table-style notification.

    Some Salla templates render ``المنتج الكمية السعر`` as a header followed
    by a product row, rather than providing a dedicated ``المنتج:`` label.
    This helper deliberately skips URLs, table headers, numeric price rows,
    totals, and footer text.  It returns only the product name.
    """
    labeled = _value_after_label(text, (r"product\s*name",), 255)
    if labeled and labeled.casefold() not in {"name", "product", "quantity", "price"}:
        return labeled.strip(" []")

    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        if not re.search(r"^\s*(?:المنتج|product)\b", line, re.IGNORECASE):
            continue
        for candidate in lines[index + 1 : index + 8]:
            candidate = candidate.strip(" []")
            if not candidate or candidate.startswith("http") or candidate.startswith("["):
                continue
            if re.search(r"(?:الكمية|السعر|quantity|price|sku|رقم الطلب|العميل|الإجمالي|total|كوبون)", candidate, re.IGNORECASE):
                continue
            if re.fullmatch(r"[\d\s.,:+-]+(?:\s*[A-Z]{3})?", candidate, re.IGNORECASE):
                continue
            # A product row may be repeated once; the first non-tabular text
            # is sufficient and avoids capturing the following footer.
            return candidate
    return None


def _extract_quantity(text: str) -> int | None:
    """Extract a positive line-item quantity without retaining message text."""
    labeled = _value_after_label(text, (r"quantity", r"الكمية"), 32)
    if labeled:
        match = re.search(r"\b(\d{1,6})\b", labeled)
        if match:
            return int(match.group(1))
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    for index, line in enumerate(lines):
        if not re.search(r"^\s*(?:المنتج|product)\b", line, re.IGNORECASE):
            continue
        for candidate in lines[index + 1 : index + 8]:
            match = re.match(r"^(\d{1,6})(?=\s|$)", candidate)
            if match:
                return int(match.group(1))
    return None


def _sender_domain(value: str) -> str:
    _, address = parseaddr(value)
    return address.rsplit("@", 1)[-1].casefold() if "@" in address else ""


def _domain_allowed(sender_domain: str, allowed_domains: list[str]) -> bool:
    for configured in allowed_domains:
        domain = configured.strip().casefold().lstrip("@")
        if domain and (sender_domain == domain or sender_domain.endswith(f".{domain}")):
            return True
    return False


def _authentication_domain_allowed(authentication: str, allowed_domains: list[str]) -> bool:
    """Require a passing DKIM/SPF identity aligned with the trusted sender.

    Merely finding `dkim=pass` is insufficient: an attacker can have a valid
    signature for an unrelated domain. The received Authentication-Results
    identity must also match the merchant-approved domain profile.
    """
    for dkim_domain in re.findall(r"dkim=pass\b[^\n;]*\bheader\.d=([a-z0-9.-]+)", authentication, re.IGNORECASE):
        if _domain_allowed(dkim_domain, allowed_domains):
            return True
    for spf_identity in re.findall(r"spf=pass\b[^\n;]*\b(?:smtp\.mailfrom|envelope-from)=<?([^\s;>]+)", authentication, re.IGNORECASE):
        domain = spf_identity.rsplit("@", 1)[-1]
        if _domain_allowed(domain, allowed_domains):
            return True
    return False


def parse_salla_order_notification(
    message: ParsedMailMessage,
    *,
    allowed_sender_domains: list[str],
    subject_patterns: list[str],
) -> SallaOrderNotification:
    """Validate and extract only order metadata from a trusted email profile.

    A mailbox with no configured sender domains or subject patterns is fail
    closed.  This prevents a generic incoming email from becoming an order.
    """

    if not allowed_sender_domains or not subject_patterns:
        raise SallaNotificationError("notification_profile_not_configured")
    if not message.message_id.strip():
        raise SallaNotificationError("notification_message_id_missing")
    sender_domain = _sender_domain(message.from_address)
    if not _domain_allowed(sender_domain, allowed_sender_domains):
        raise SallaNotificationError("notification_sender_untrusted")
    try:
        subject_matches = any(re.search(pattern, message.subject, re.IGNORECASE) for pattern in subject_patterns)
    except re.error as exc:
        raise SallaNotificationError("notification_subject_pattern_invalid") from exc
    if not subject_matches:
        raise SallaNotificationError("notification_subject_untrusted")
    authentication = message.authentication_results + "\n" + message.headers.get("authentication-results", "")
    if not _authentication_domain_allowed(authentication, allowed_sender_domains):
        raise SallaNotificationError("notification_authentication_untrusted")
    text = _message_text(message)
    if len(text) < 20:
        raise SallaNotificationError("notification_structure_invalid")
    reference = _value_after_label(text, (r"order\s*(?:number|no\.?|#)", r"رقم\s*الطلب"), 120)
    status_value = _value_after_label(text, (r"(?:payment\s*)?status", r"حالة\s*(?:الطلب|الدفع)"), 80)
    payment_value = _value_after_label(text, (r"payment\s*(?:method|type)", r"طريقة\s*(?:الدفع|السداد)"), 80)
    status = _normalize_status(status_value or payment_value or text)
    product_id = _value_after_label(text, (r"product\s*id", r"معر[فف]\s*المنتج"), 120)
    sku = _value_after_label(text, (r"sku", r"رمز\s*المنتج"), 160)
    product_name = _extract_product_name(text)
    quantity = _extract_quantity(text)
    if not reference or not status or not (product_id or sku or product_name):
        raise SallaNotificationError("notification_structure_invalid")
    username = _value_after_label(
        text,
        (r"steam\s*username", r"username", r"account\s*alias", r"user\s*steam", r"اسم\s*المستخدم", r"يوزر", r"معرف\s*الحساب"),
        255,
    )
    buyer_email = _value_after_label(text, (r"buyer\s*email", r"customer\s*email", r"بريد\s*(?:المشتري|العميل)"), 254)
    phone_last4 = _value_after_label(text, (r"phone(?:\s*last\s*four)?", r"آخر\s*4\s*(?:أرقام|ارقام)\s*(?:الجوال|الهاتف)"), 32)
    customer_identifier = buyer_email or phone_last4
    ownership_method = "username" if username else ("buyer_identifier" if customer_identifier else "missing")
    return SallaOrderNotification(
        external_message_id=message.message_id.strip(),
        order_reference=reference.strip().lstrip("#"),
        status=status,
        eligible=status == "paid",
        product_id=product_id,
        sku=sku,
        product_name=product_name,
        quantity=quantity,
        requested_username=username,
        customer_identifier=customer_identifier,
        ownership_method=ownership_method,
    )
