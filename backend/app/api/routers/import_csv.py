from __future__ import annotations

import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, get_db_session_commit, require_admin_roles
from app.audit import record
from app.models import (
    AdminRole,
    AdminSession,
    AdminUser,
    ImportBatch,
    ImportRow,
    InventoryAccount,
    InventoryStatus,
    Mailbox,
    Platform,
)
from app.platforms import INVENTORY_PLATFORM_CODES
from app.services.csv_import import CsvImportError, parse_inventory_csv, prepare_inventory_rows
from app.services.inventory import normalize_identifier

router = APIRouter(prefix="/admin/import", tags=["Admin CSV Import"])


@router.post("/preview")
async def preview_csv(
    csv_file: UploadFile = File(...),
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value})),
    ] = None,
    session: Annotated[AsyncSession, Depends(get_db_session_commit)] = None,
):
    admin, _ = admin_and_session
    raw = await csv_file.read(2_000_001)
    try:
        rows = parse_inventory_csv(raw)
    except CsvImportError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    digest = hashlib.sha256(raw).hexdigest()
    prior = await session.scalar(select(ImportBatch).where(ImportBatch.sha256 == digest))

    platform_codes = {
        p.code
        for p in (await session.scalars(select(Platform))).all()
        if p.code in INVENTORY_PLATFORM_CODES
    }
    mailbox_labels = {m.label for m in (await session.scalars(select(Mailbox))).all()}
    existing_keys = {
        (platform_code, normalized_identifier)
        for platform_code, normalized_identifier in (
            await session.execute(
                select(Platform.code, InventoryAccount.normalized_identifier).join(InventoryAccount)
            )
        ).all()
    }

    batch = ImportBatch(created_by_admin_id=admin.id, sha256=digest)
    session.add(batch)
    await session.flush()

    prepared_rows = prepare_inventory_rows(
        rows,
        platform_codes=platform_codes,
        mailbox_labels=mailbox_labels,
        allowed_statuses={item.value for item in InventoryStatus},
        existing_keys=existing_keys,
        normalizer=normalize_identifier,
    )
    errors = sum(row.error is not None for row in prepared_rows)

    preview_items = []
    for row in prepared_rows:
        row_dict = {
            "platform": row.platform,
            "account_identifier": row.account_identifier,
            "mailbox_reference": row.mailbox_reference,
            "status": row.status,
            "notes": row.notes,
        }
        session.add(
            ImportRow(
                batch_id=batch.id,
                row_number=row.row_number,
                data=row_dict,
                error=row.error,
            )
        )
        preview_items.append({
            "row_number": row.row_number,
            "data": row_dict,
            "error": row.error,
        })

    batch.error_count = errors
    await record(
        session,
        "import.preview_created",
        "import_batch",
        str(batch.id),
        actor_admin_id=admin.id,
        metadata={"row_count": len(rows), "error_count": errors},
    )

    return {
        "status": "success",
        "batch_id": str(batch.id),
        "total_rows": len(rows),
        "error_count": errors,
        "rows": preview_items,
        "is_duplicate": prior is not None,
    }


@router.post("/{batch_id}/commit")
async def commit_csv(
    batch_id: uuid.UUID,
    admin_and_session: Annotated[
        tuple[AdminUser, AdminSession],
        Depends(require_admin_roles({AdminRole.OWNER.value, AdminRole.OPERATOR.value})),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session_commit)],
):
    admin, _ = admin_and_session
    batch = await session.scalar(
        select(ImportBatch).where(ImportBatch.id == batch_id).with_for_update()
    )
    if not batch or batch.status != "preview" or batch.error_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="لا يمكن تأكيد هذه الدفعة؛ تحقق من وجود أخطاء أو أنها اعتُمدت مسبقًا",
        )

    rows = (
        await session.scalars(
            select(ImportRow).where(ImportRow.batch_id == batch.id).with_for_update()
        )
    ).all()
    platforms = {p.code: p.id for p in (await session.scalars(select(Platform))).all()}
    mailboxes = {m.label: m.id for m in (await session.scalars(select(Mailbox))).all()}

    count = 0
    for row in rows:
        data = row.data
        account = InventoryAccount(
            platform_id=platforms[data["platform"]],
            mailbox_id=mailboxes[data["mailbox_reference"]],
            identifier=data["account_identifier"],
            normalized_identifier=normalize_identifier(data["account_identifier"]),
            status=data["status"],
            notes=data["notes"] or None,
        )
        session.add(account)
        await session.flush()
        count += 1
        await record(
            session,
            "inventory.account_created",
            "inventory_account",
            str(account.id),
            actor_admin_id=admin.id,
            metadata={"platform_code": data["platform"], "source": "csv_import"},
        )

    batch.status = "committed"
    await record(
        session,
        "import.committed",
        "import_batch",
        str(batch.id),
        actor_admin_id=admin.id,
        metadata={"row_count": len(rows)},
    )

    return {
        "status": "success",
        "message": f"تم استيراد {count} حساب بنجاح",
        "imported_count": count,
    }
