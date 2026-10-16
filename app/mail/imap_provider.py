from __future__ import annotations

import email
import imaplib
import socket
import ssl
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime

from app.models import Mailbox
from app.security import decrypt_secret


class MailProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedMailMessage:
    uidvalidity: str
    uid: str
    message_date: datetime
    from_address: str
    subject: str
    text: str
    html: str
    authentication_results: str
    message_id: str = ""
    headers: dict[str, str] = field(default_factory=dict)


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for item, encoding in decode_header(value):
        if isinstance(item, bytes):
            parts.append(item.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(item)
    return "".join(parts)


def _message_date(value: str | None) -> datetime:
    try:
        dt = parsedate_to_datetime(value or "")
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (TypeError, ValueError, IndexError):
        return datetime.now(UTC)


def _part_text(part: Message) -> str:
    raw = part.get_payload(decode=True)
    if raw is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def parse_message(uidvalidity: str, uid: str, raw: bytes) -> ParsedMailMessage:
    message = email.message_from_bytes(raw)
    text_parts: list[str] = []
    html_parts: list[str] = []
    for part in message.walk():
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        content_type = part.get_content_type()
        if content_type == "text/plain":
            text_parts.append(_part_text(part))
        elif content_type == "text/html":
            html_parts.append(_part_text(part))
    headers: dict[str, str] = {}
    for name, value in message.items():
        key = name.casefold()
        decoded = _decode_header(value)
        headers[key] = f"{headers[key]}\n{decoded}".strip() if key in headers else decoded
    return ParsedMailMessage(
        uidvalidity=uidvalidity,
        uid=uid,
        message_date=_message_date(message.get("Date")),
        from_address=_decode_header(message.get("From")),
        subject=_decode_header(message.get("Subject")),
        text="\n".join(text_parts),
        html="\n".join(html_parts),
        authentication_results=_decode_header(message.get("Authentication-Results")),
        message_id=_decode_header(message.get("Message-ID")).strip(),
        headers=headers,
    )


class ImapMailProvider:
    """Read-only IMAP client. It never marks messages read or deletes them."""

    def __init__(self, mailbox: Mailbox, timeout_seconds: int = 10):
        self.mailbox = mailbox
        self.timeout_seconds = timeout_seconds

    def recent_messages(self, since: datetime, limit: int = 30) -> list[ParsedMailMessage]:
        context = ssl.create_default_context()
        original_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self.timeout_seconds)
        client: imaplib.IMAP4_SSL | None = None
        try:
            client = imaplib.IMAP4_SSL(self.mailbox.host, self.mailbox.port, ssl_context=context, timeout=self.timeout_seconds)
            if not self.mailbox.encrypted_password:
                raise MailProviderError("imap_password_not_configured")
            client.login(self.mailbox.username, decrypt_secret(self.mailbox.encrypted_password))
            status, _ = client.select(self.mailbox.mail_folder or "INBOX", readonly=True)
            if status != "OK":
                raise MailProviderError("imap_select_failed")
            uidvalidity_response = client.response("UIDVALIDITY")[1]
            uidvalidity = (uidvalidity_response[0].decode("ascii") if uidvalidity_response else "unknown")
            criteria_date = since.astimezone(UTC).strftime("%d-%b-%Y")
            status, data = client.uid("SEARCH", None, "SINCE", criteria_date)
            if status != "OK":
                raise MailProviderError("imap_search_failed")
            uids = data[0].split()[-limit:]
            messages: list[ParsedMailMessage] = []
            for uid_bytes in uids:
                uid = uid_bytes.decode("ascii", errors="strict")
                status, fetched = client.uid("FETCH", uid, "(BODY.PEEK[])")
                if status != "OK" or not fetched or not isinstance(fetched[0], tuple):
                    continue
                messages.append(parse_message(uidvalidity, uid, fetched[0][1]))
            return messages
        except (imaplib.IMAP4.error, OSError, ValueError) as exc:
            raise MailProviderError("imap_connection_or_protocol_error") from exc
        finally:
            socket.setdefaulttimeout(original_timeout)
            if client:
                try:
                    client.logout()
                except (imaplib.IMAP4.error, OSError):
                    pass
