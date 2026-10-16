from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InventoryStatus(str, enum.Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    ASSIGNED = "assigned"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class OrderStatus(str, enum.Enum):
    DRAFT = "draft"
    ASSIGNED = "assigned"
    ACTIVATED = "activated"
    CANCELLED = "cancelled"


class VerificationStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    WAITING_MAIL = "waiting_mail"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    DELIVERY_UNCERTAIN = "delivery_uncertain"


class AdminRole(str, enum.Enum):
    OWNER = "owner"
    OPERATOR = "operator"
    AUDITOR = "auditor"
    SUPPORT = "support"


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AdminUser(Base, Timestamped):
    __tablename__ = "admin_users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(20), default=AdminRole.OWNER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AdminSession(Base, Timestamped):
    __tablename__ = "admin_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(96))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Platform(Base, Timestamped):
    __tablename__ = "platforms"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mail_profile: Mapped[dict] = mapped_column(JSONB, default=dict)


class Mailbox(Base, Timestamped):
    __tablename__ = "mailboxes"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(100), unique=True)
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=993)
    username: Mapped[str] = mapped_column(String(320))
    encrypted_password: Mapped[bytes | None] = mapped_column(LargeBinary)
    auth_mode: Mapped[str] = mapped_column(String(32), default="imap_password")
    oauth_refresh_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    # Inventory is the legacy/default purpose. A notification mailbox is
    # explicit so ordinary customer inboxes are never scanned as orders.
    purpose: Mapped[str] = mapped_column(String(32), default="inventory", index=True)
    mail_folder: Mapped[str] = mapped_column(String(255), default="INBOX")
    notification_sender_domains: Mapped[list[str]] = mapped_column(JSONB, default=list)
    notification_subject_patterns: Mapped[list[str]] = mapped_column(JSONB, default=list)
    notification_last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notification_last_error_code: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(64))


class MailboxOAuthState(Base, Timestamped):
    __tablename__ = "mailbox_oauth_states"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    username: Mapped[str] = mapped_column(String(320))
    code_verifier_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Customer(Base, Timestamped):
    __tablename__ = "customers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(160))
    telegram_user_id: Mapped[int | None] = mapped_column(unique=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class CustomerSession(Base, Timestamped):
    __tablename__ = "customer_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(96))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InventoryAccount(Base, Timestamped):
    __tablename__ = "inventory_accounts"
    __table_args__ = (
        UniqueConstraint("platform_id", "normalized_identifier", name="uq_account_platform_identifier"),
        CheckConstraint(
            "status IN ('available','reserved','assigned','disabled','archived')", name="ck_inventory_status"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platforms.id"), index=True)
    mailbox_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mailboxes.id"), index=True)
    identifier: Mapped[str] = mapped_column(String(255))
    normalized_identifier: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default=InventoryStatus.AVAILABLE.value, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class Order(Base, Timestamped):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("external_reference", name="uq_order_reference"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.DRAFT.value, index=True)
    notes: Mapped[str | None] = mapped_column(Text)


class AccountAssignment(Base, Timestamped):
    __tablename__ = "account_assignments"
    __table_args__ = (
        Index("uq_current_assignment_account", "account_id", unique=True, postgresql_where="revoked_at IS NULL"),
        Index("uq_current_assignment_order", "order_id", unique=True, postgresql_where="revoked_at IS NULL"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventory_accounts.id"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    assigned_by_admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(250))


class ActivationToken(Base, Timestamped):
    __tablename__ = "activation_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VerificationRequest(Base, Timestamped):
    __tablename__ = "verification_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','processing','waiting_mail','succeeded','failed','expired','cancelled','delivery_uncertain')",
            name="ck_verification_status",
        ),
        Index(
            "uq_active_verification_assignment",
            "assignment_id",
            unique=True,
            postgresql_where="status IN ('queued','processing','waiting_mail','delivery_uncertain')",
        ),
        CheckConstraint(
            "((requested_by_telegram_id IS NOT NULL) <> (requested_by_web_session_id IS NOT NULL))",
            name="ck_verification_actor",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("account_assignments.id"), index=True)
    requested_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    requested_by_web_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customer_sessions.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default=VerificationStatus.QUEUED.value, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    result_hash: Mapped[str | None] = mapped_column(String(64))
    result_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(80))


class MailMessageClaim(Base, Timestamped):
    __tablename__ = "mail_message_claims"
    __table_args__ = (UniqueConstraint("mailbox_id", "uidvalidity", "uid", name="uq_mail_message_claim"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mailbox_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mailboxes.id"), index=True)
    uidvalidity: Mapped[str] = mapped_column(String(64))
    uid: Mapped[str] = mapped_column(String(64))
    verification_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("verification_requests.id"), unique=True, index=True
    )
    message_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkerJob(Base, Timestamped):
    __tablename__ = "worker_jobs"
    __table_args__ = (UniqueConstraint("kind", "idempotency_key", name="uq_job_idempotency"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))


class TelegramUpdate(Base, Timestamped):
    __tablename__ = "telegram_updates"
    update_id: Mapped[int] = mapped_column(primary_key=True)


class RateLimitWindow(Base):
    __tablename__ = "rate_limit_windows"
    __table_args__ = (UniqueConstraint("scope", "subject_hash", "window_start", name="uq_rate_limit_window"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(64), index=True)
    subject_hash: Mapped[str] = mapped_column(String(64), index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class SallaMerchantAuthorization(Base, Timestamped):
    __tablename__ = "salla_merchant_authorizations"
    __table_args__ = (UniqueConstraint("merchant_id", name="uq_salla_merchant"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[int] = mapped_column(BigInteger, index=True)
    access_token_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    refresh_token_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    scopes: Mapped[str] = mapped_column(String(500), default="")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error_code: Mapped[str | None] = mapped_column(String(80))


class SallaWebhookEvent(Base):
    __tablename__ = "salla_webhook_events"
    __table_args__ = (UniqueConstraint("event_key", name="uq_salla_webhook_event_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_key: Mapped[str] = mapped_column(String(64))
    event_name: Mapped[str] = mapped_column(String(120), index=True)
    merchant_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SallaProductMapping(Base, Timestamped):
    __tablename__ = "salla_product_mappings"
    __table_args__ = (
        UniqueConstraint("merchant_id", "product_id", "sku", "service_key", name="uq_salla_product_mapping"),
        Index("ix_salla_mapping_product", "merchant_id", "product_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[int] = mapped_column(BigInteger, index=True)
    product_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    sku: Mapped[str | None] = mapped_column(String(160), index=True)
    service_key: Mapped[str] = mapped_column(String(100), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UsagePolicy(Base, Timestamped):
    __tablename__ = "usage_policies"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=5)
    period_seconds: Mapped[int] = mapped_column(Integer, default=86400)
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LocalUsageIdentity(Base, Timestamped):
    """Local usage identity keyed by an unverified external reference.

    ``reference_key`` is deliberately not a Salla order verification.  It is
    only a merchant-approved local usage key supplied by the customer.
    """

    __tablename__ = "local_usage_identities"
    __table_args__ = (UniqueConstraint("reference_key", name="uq_local_usage_reference"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference_key: Mapped[str] = mapped_column(String(120), index=True)
    # Ordinary metadata for the local, non-sensitive usage flow. It does not
    # verify an external order or grant access to authentication material.
    platform_code: Mapped[str] = mapped_column(String(32), default="steam", index=True)
    account_alias: Mapped[str] = mapped_column(String(255))


class LocalAccessSession(Base):
    __tablename__ = "local_access_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("local_usage_identities.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(96))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LocalUsageCounter(Base):
    __tablename__ = "local_usage_counters"
    __table_args__ = (UniqueConstraint("identity_id", "service_key", "period_start", name="uq_local_usage_counter_period"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("local_usage_identities.id", ondelete="CASCADE"), index=True)
    service_key: Mapped[str] = mapped_column(String(100), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LocalUsageRecord(Base):
    __tablename__ = "local_usage_records"
    __table_args__ = (UniqueConstraint("identity_id", "service_key", "idempotency_key", name="uq_local_usage_replay"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("local_usage_identities.id", ondelete="CASCADE"), index=True)
    service_key: Mapped[str] = mapped_column(String(100), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SallaOrderVerification(Base, Timestamped):
    __tablename__ = "salla_order_verifications"
    __table_args__ = (UniqueConstraint("merchant_id", "reference_id", name="uq_salla_order_reference"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Shared non-sensitive entitlement record: API verification uses
    # source=salla_api and mailbox notification ingestion uses source=salla_email.
    source: Mapped[str] = mapped_column(String(32), default="salla_api", index=True)
    notification_mailbox_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mailboxes.id", ondelete="SET NULL"), index=True)
    merchant_id: Mapped[int] = mapped_column(BigInteger, index=True)
    salla_order_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    reference_id: Mapped[str] = mapped_column(String(120), index=True)
    purchaser_email_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    external_message_id: Mapped[str | None] = mapped_column(String(320), index=True)
    product_id: Mapped[str | None] = mapped_column(String(120), index=True)
    sku: Mapped[str | None] = mapped_column(String(160), index=True)
    product_name: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int | None] = mapped_column(Integer)
    customer_identifier_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    requested_username_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    ownership_method: Mapped[str] = mapped_column(String(32), default="buyer_email")
    # The exact services authorized by the purchased order.  This prevents an
    # authenticated buyer from selecting another service configured for the
    # same merchant.
    service_keys: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status_slug: Mapped[str] = mapped_column(String(60))
    payment_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class SallaNotificationClaim(Base, Timestamped):
    """Idempotency evidence for a trusted, read-only Salla notification."""

    __tablename__ = "salla_notification_claims"
    __table_args__ = (
        UniqueConstraint("mailbox_id", "external_message_id", name="uq_salla_notification_message"),
        UniqueConstraint("mailbox_id", "event_key", name="uq_salla_notification_event"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mailbox_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mailboxes.id", ondelete="CASCADE"), index=True)
    external_message_id: Mapped[str] = mapped_column(String(320))
    order_reference: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(60), index=True)
    event_key: Mapped[str] = mapped_column(String(64))
    message_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SallaAccessSession(Base):
    __tablename__ = "salla_access_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("salla_order_verifications.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(96))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageCounter(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("verification_id", "service_key", "period_start", name="uq_usage_counter_period"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("salla_order_verifications.id", ondelete="CASCADE"), index=True)
    service_key: Mapped[str] = mapped_column(String(100), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageRecord(Base):
    __tablename__ = "usage_records"
    __table_args__ = (UniqueConstraint("verification_id", "service_key", "idempotency_key", name="uq_usage_replay"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("salla_order_verifications.id", ondelete="CASCADE"), index=True)
    service_key: Mapped[str] = mapped_column(String(100), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ImportBatch(Base, Timestamped):
    __tablename__ = "import_batches"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_by_admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("admin_users.id"))
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="preview")
    error_count: Mapped[int] = mapped_column(Integer, default=0)


class ImportRow(Base, Timestamped):
    __tablename__ = "import_rows"
    __table_args__ = (UniqueConstraint("batch_id", "row_number", name="uq_import_batch_row"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_admin_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("admin_users.id"), index=True)
    actor_telegram_id: Mapped[int | None] = mapped_column(index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
