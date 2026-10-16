"""Validation for the inventory CSV preview flow.

The browser route persists a preview only after these pure checks complete.  Keeping
this logic independent of FastAPI makes the security-sensitive import rules easy to
test without an HTTP upload or a live database.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Callable


REQUIRED_COLUMNS = {"platform", "account_identifier", "mailbox_reference", "status", "notes"}
MAX_CSV_BYTES = 2_000_000


class CsvImportError(ValueError):
    """Raised for a file that cannot be safely previewed."""


@dataclass(frozen=True)
class PreparedImportRow:
    row_number: int
    platform: str
    account_identifier: str
    mailbox_reference: str
    status: str
    notes: str
    error: str | None


def parse_inventory_csv(raw: bytes) -> list[dict[str, str]]:
    if len(raw) > MAX_CSV_BYTES:
        raise CsvImportError("حجم الملف يتجاوز 2MB")
    try:
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise CsvImportError("ملف CSV غير صالح أو ليس UTF-8") from exc
    if not rows or not REQUIRED_COLUMNS.issubset(rows[0]):
        raise CsvImportError("الأعمدة المطلوبة غير مكتملة")
    return rows


def prepare_inventory_rows(
    rows: list[dict[str, str]],
    *,
    platform_codes: set[str],
    mailbox_labels: set[str],
    allowed_statuses: set[str],
    existing_keys: set[tuple[str, str]],
    normalizer: Callable[[str], str],
) -> list[PreparedImportRow]:
    """Return every input row with a user-facing, row-local validation error."""
    seen: set[tuple[str, str]] = set()
    prepared: list[PreparedImportRow] = []
    for number, row in enumerate(rows, start=2):
        platform = row["platform"].strip().casefold()
        identifier = row["account_identifier"].strip()
        mailbox = row["mailbox_reference"].strip()
        status = row["status"].strip().casefold() or "available"
        key = (platform, normalizer(identifier))
        error: str | None = None
        if not identifier or platform not in platform_codes or mailbox not in mailbox_labels or status not in allowed_statuses:
            error = "قيم مطلوبة أو منصة أو صندوق بريد أو حالة غير صالحة"
        elif key in seen:
            error = "مكرر داخل الملف"
        else:
            seen.add(key)
            if key in existing_keys:
                error = "الحساب موجود بالفعل"
        prepared.append(
            PreparedImportRow(
                row_number=number,
                platform=platform,
                account_identifier=identifier,
                mailbox_reference=mailbox,
                status=status,
                notes=row["notes"].strip(),
                error=error,
            )
        )
    return prepared
