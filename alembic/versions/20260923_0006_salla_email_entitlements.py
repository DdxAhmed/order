"""Add trusted Salla email entitlements and dedicated mailbox settings.

Revision ID: 20260923_0006
Revises: 20260918_0005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260923_0006"
down_revision = "20260918_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    mailbox_columns = {item["name"] for item in inspector.get_columns("mailboxes")}
    mailbox_additions = (
        ("purpose", sa.Column("purpose", sa.String(length=32), nullable=False, server_default="inventory")),
        ("mail_folder", sa.Column("mail_folder", sa.String(length=255), nullable=False, server_default="INBOX")),
        ("notification_sender_domains", sa.Column("notification_sender_domains", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb"))),
        ("notification_subject_patterns", sa.Column("notification_subject_patterns", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb"))),
        ("notification_last_scanned_at", sa.Column("notification_last_scanned_at", sa.DateTime(timezone=True), nullable=True)),
        ("notification_last_error_code", sa.Column("notification_last_error_code", sa.String(length=80), nullable=True)),
    )
    for name, column in mailbox_additions:
        if name not in mailbox_columns:
            op.add_column("mailboxes", column)
    mailbox_indexes = {item["name"] for item in inspector.get_indexes("mailboxes")}
    if "ix_mailboxes_purpose" not in mailbox_indexes:
        op.create_index("ix_mailboxes_purpose", "mailboxes", ["purpose"])

    entitlement_columns = {item["name"] for item in inspector.get_columns("salla_order_verifications")}
    additions = (
        ("source", sa.Column("source", sa.String(length=32), nullable=False, server_default="salla_api")),
        ("notification_mailbox_id", sa.Column("notification_mailbox_id", postgresql.UUID(as_uuid=True), nullable=True)),
        ("external_message_id", sa.Column("external_message_id", sa.String(length=320), nullable=True)),
        ("product_id", sa.Column("product_id", sa.String(length=120), nullable=True)),
        ("sku", sa.Column("sku", sa.String(length=160), nullable=True)),
        ("product_name", sa.Column("product_name", sa.String(length=255), nullable=True)),
        ("customer_identifier_hash", sa.Column("customer_identifier_hash", sa.String(length=64), nullable=True)),
        ("requested_username_hash", sa.Column("requested_username_hash", sa.String(length=64), nullable=True)),
        ("ownership_method", sa.Column("ownership_method", sa.String(length=32), nullable=False, server_default="buyer_email")),
    )
    added_mailbox_fk = False
    for name, column in additions:
        if name not in entitlement_columns:
            op.add_column("salla_order_verifications", column)
            added_mailbox_fk = added_mailbox_fk or name == "notification_mailbox_id"
    if added_mailbox_fk:
        op.create_foreign_key(
            "fk_salla_entitlement_notification_mailbox",
            "salla_order_verifications",
            "mailboxes",
            ["notification_mailbox_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "salla_order_id" in entitlement_columns:
        op.alter_column("salla_order_verifications", "salla_order_id", existing_type=sa.BigInteger(), nullable=True)
    if "purchaser_email_hash" in entitlement_columns:
        op.alter_column("salla_order_verifications", "purchaser_email_hash", existing_type=sa.String(length=64), nullable=True)
    entitlement_indexes = {item["name"] for item in inspector.get_indexes("salla_order_verifications")}
    for name, columns in (
        ("ix_salla_entitlement_source", ["source"]),
        ("ix_salla_entitlement_notification_mailbox", ["notification_mailbox_id"]),
        ("ix_salla_entitlement_message", ["external_message_id"]),
        ("ix_salla_entitlement_product", ["product_id"]),
        ("ix_salla_entitlement_sku", ["sku"]),
        ("ix_salla_entitlement_username", ["requested_username_hash"]),
    ):
        if name not in entitlement_indexes:
            op.create_index(name, "salla_order_verifications", columns)

    if "salla_notification_claims" not in set(inspector.get_table_names()):
        op.create_table(
            "salla_notification_claims",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("mailbox_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("external_message_id", sa.String(length=320), nullable=False),
            sa.Column("order_reference", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=60), nullable=False),
            sa.Column("event_key", sa.String(length=64), nullable=False),
            sa.Column("message_date", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["mailbox_id"], ["mailboxes.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("mailbox_id", "external_message_id", name="uq_salla_notification_message"),
            sa.UniqueConstraint("mailbox_id", "event_key", name="uq_salla_notification_event"),
        )
        op.create_index("ix_salla_notification_claim_mailbox", "salla_notification_claims", ["mailbox_id"])
        op.create_index("ix_salla_notification_claim_reference", "salla_notification_claims", ["order_reference"])
        op.create_index("ix_salla_notification_claim_status", "salla_notification_claims", ["status"])


def downgrade() -> None:
    op.drop_table("salla_notification_claims")
    for name in (
        "ix_salla_entitlement_username",
        "ix_salla_entitlement_sku",
        "ix_salla_entitlement_product",
        "ix_salla_entitlement_message",
        "ix_salla_entitlement_notification_mailbox",
        "ix_salla_entitlement_source",
    ):
        op.drop_index(name, table_name="salla_order_verifications")
    op.drop_constraint("fk_salla_entitlement_notification_mailbox", "salla_order_verifications", type_="foreignkey")
    for name in (
        "ownership_method",
        "requested_username_hash",
        "customer_identifier_hash",
        "product_name",
        "sku",
        "product_id",
        "external_message_id",
        "notification_mailbox_id",
        "source",
    ):
        op.drop_column("salla_order_verifications", name)
    op.drop_index("ix_mailboxes_purpose", table_name="mailboxes")
    for name in (
        "notification_last_error_code",
        "notification_last_scanned_at",
        "notification_subject_patterns",
        "notification_sender_domains",
        "mail_folder",
        "purpose",
    ):
        op.drop_column("mailboxes", name)
