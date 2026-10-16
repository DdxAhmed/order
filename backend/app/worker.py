from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import timedelta

from sqlalchemy import or_, select, update

from app.config import get_settings
from app.db import SessionLocal
from app.models import Mailbox, VerificationRequest, WorkerJob
from app.security import utcnow
from app.services.salla_notifications import ingest_salla_notification_mailbox
from app.services.verification import fetch_code

logger = logging.getLogger(__name__)


async def claim_next_job() -> WorkerJob | None:
    async with SessionLocal.begin() as session:
        job = await session.scalar(
            select(WorkerJob)
            .where(
                WorkerJob.completed_at.is_(None),
                WorkerJob.available_at <= utcnow(),
                or_(WorkerJob.leased_until.is_(None), WorkerJob.leased_until < utcnow()),
            )
            .order_by(WorkerJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job:
            job.leased_until = utcnow() + timedelta(seconds=45)
            job.attempts += 1
        return job


async def process_job(job_id: uuid.UUID) -> None:
    async with SessionLocal.begin() as session:
        job = await session.get(WorkerJob, job_id, with_for_update=True)
        if not job or job.completed_at is not None:
            return
        if job.kind == "send_verification_result":
            from app.bot import send_result_if_ready

            delivered = await send_result_if_ready(uuid.UUID(job.payload["verification_request_id"]))
            if delivered or job.attempts >= 2:
                job.completed_at = utcnow()
                job.leased_until = None
            else:
                job.available_at = utcnow() + timedelta(seconds=2 ** job.attempts)
                job.leased_until = None
            return
        if job.kind != "fetch_verification_code":
            job.completed_at = utcnow()
            job.last_error_code = "unknown_job_kind"
            return
        outcome = await fetch_code(session, uuid.UUID(job.payload["verification_request_id"]))
        if outcome in {"done", "matched"}:
            job.completed_at = utcnow()
            job.leased_until = None
        else:
            request = await session.get(VerificationRequest, uuid.UUID(job.payload["verification_request_id"]))
            if not request or request.expires_at <= utcnow() or job.attempts >= 14:
                if request and request.status not in {"succeeded", "cancelled"}:
                    request.status = "expired" if request.expires_at <= utcnow() else "failed"
                    request.failure_code = "mail_timeout" if request.status == "expired" else "mail_retry_exhausted"
                job.completed_at = utcnow()
            else:
                job.available_at = utcnow() + timedelta(seconds=min(60, 2 ** job.attempts))
                job.leased_until = None


async def cleanup_expired_sensitive_results() -> None:
    async with SessionLocal.begin() as session:
        await session.execute(
            update(VerificationRequest)
            .where(
                VerificationRequest.result_ciphertext.is_not(None),
                VerificationRequest.result_expires_at < utcnow(),
            )
            .values(result_ciphertext=None)
        )


async def scan_salla_notification_mailboxes() -> None:
    """Run the separate, non-sensitive Salla-email import path.

    This does not enqueue, fetch, display, or change any authentication-code
    workflow. Each mailbox is a distinct transaction so one failed connection
    cannot block the rest of the worker.
    """
    async with SessionLocal() as session:
        mailbox_ids = list(
            (await session.scalars(
                select(Mailbox.id).where(
                    Mailbox.is_active.is_(True),
                    Mailbox.purpose == "salla_notifications",
                )
            )).all()
        )
    for mailbox_id in mailbox_ids:
        try:
            async with SessionLocal.begin() as session:
                mailbox = await session.scalar(select(Mailbox).where(Mailbox.id == mailbox_id).with_for_update())
                if mailbox:
                    await ingest_salla_notification_mailbox(session, mailbox)
        except Exception:
            logger.exception("salla notification mailbox scan failed without message content")


async def run() -> None:
    logging.basicConfig(level=get_settings().log_level)
    last_cleanup = utcnow() - timedelta(minutes=5)
    last_salla_notification_scan = utcnow() - timedelta(hours=1)
    while True:
        try:
            if (utcnow() - last_cleanup).total_seconds() >= 60:
                await cleanup_expired_sensitive_results()
                last_cleanup = utcnow()
            if (utcnow() - last_salla_notification_scan).total_seconds() >= get_settings().salla_notification_poll_seconds:
                await scan_salla_notification_mailboxes()
                last_salla_notification_scan = utcnow()
            job = await claim_next_job()
            if job:
                await process_job(job.id)
                continue
        except Exception:
            logger.exception("worker job failed without sensitive payload")
        await asyncio.sleep(get_settings().worker_poll_seconds)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
