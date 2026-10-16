"""Add isolated Salla order verification and generic usage tables.

Revision ID: 20260918_0005
Revises: 20260914_0004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260918_0005"
down_revision = "20260914_0004"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()


def upgrade() -> None:
    # The initial legacy migration calls Base.metadata.create_all(). Since
    # the Salla models are now part of that metadata, a fresh database may
    # already contain these tables before this revision is reached. The
    # production database at 20260914_0004 does not contain them. Treat the
    # fresh-database case as already applied instead of raising DuplicateTable.
    if sa.inspect(op.get_bind()).has_table("salla_merchant_authorizations"):
        return
    op.create_table("salla_merchant_authorizations",
        sa.Column("id", UUID, primary_key=True), sa.Column("merchant_id", sa.BigInteger(), nullable=False),
        sa.Column("access_token_ciphertext", sa.LargeBinary(), nullable=False), sa.Column("refresh_token_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("scopes", sa.String(500), nullable=False, server_default=""),
        sa.Column("revoked_at", sa.DateTime(timezone=True)), sa.Column("last_error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("merchant_id", name="uq_salla_merchant"))
    op.create_index("ix_salla_auth_merchant", "salla_merchant_authorizations", ["merchant_id"])
    op.create_index("ix_salla_auth_expiry", "salla_merchant_authorizations", ["token_expires_at"])
    op.create_table("salla_webhook_events",
        sa.Column("id", UUID, primary_key=True), sa.Column("event_key", sa.String(64), nullable=False), sa.Column("event_name", sa.String(120), nullable=False),
        sa.Column("merchant_id", sa.BigInteger()), sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("event_key", name="uq_salla_webhook_event_key"))
    op.create_index("ix_salla_webhook_name", "salla_webhook_events", ["event_name"])
    op.create_index("ix_salla_webhook_merchant", "salla_webhook_events", ["merchant_id"])
    op.create_table("salla_product_mappings",
        sa.Column("id", UUID, primary_key=True), sa.Column("merchant_id", sa.BigInteger(), nullable=False), sa.Column("product_id", sa.BigInteger()),
        sa.Column("sku", sa.String(160)), sa.Column("service_key", sa.String(100), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("merchant_id", "product_id", "sku", "service_key", name="uq_salla_product_mapping"))
    op.create_index("ix_salla_mapping_merchant_product", "salla_product_mappings", ["merchant_id", "product_id"])
    op.create_index("ix_salla_mapping_service", "salla_product_mappings", ["service_key"])
    op.create_table("usage_policies",
        sa.Column("id", UUID, primary_key=True), sa.Column("service_key", sa.String(100), nullable=False), sa.Column("max_uses", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("period_seconds", sa.Integer(), nullable=False, server_default="86400"), sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="30"), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("service_key"))
    op.create_index("ix_usage_policy_service", "usage_policies", ["service_key"])
    op.create_table("salla_order_verifications",
        sa.Column("id", UUID, primary_key=True), sa.Column("merchant_id", sa.BigInteger(), nullable=False), sa.Column("salla_order_id", sa.BigInteger(), nullable=False),
        sa.Column("reference_id", sa.String(120), nullable=False), sa.Column("purchaser_email_hash", sa.String(64), nullable=False), sa.Column("service_keys", JSONB, nullable=False, server_default="[]"), sa.Column("status_slug", sa.String(60), nullable=False),
        sa.Column("payment_eligible", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("verified_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("merchant_id", "reference_id", name="uq_salla_order_reference"))
    op.create_index("ix_salla_order_verification_reference", "salla_order_verifications", ["reference_id"])
    op.create_index("ix_salla_order_verification_expiry", "salla_order_verifications", ["expires_at"])
    op.create_table("salla_access_sessions",
        sa.Column("id", UUID, primary_key=True), sa.Column("verification_id", UUID, sa.ForeignKey("salla_order_verifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False), sa.Column("csrf_token", sa.String(96), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("token_hash"))
    op.create_index("ix_salla_access_token", "salla_access_sessions", ["token_hash"])
    op.create_table("usage_counters",
        sa.Column("id", UUID, primary_key=True), sa.Column("verification_id", UUID, sa.ForeignKey("salla_order_verifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_key", sa.String(100), nullable=False), sa.Column("period_start", sa.DateTime(timezone=True), nullable=False), sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("verification_id", "service_key", "period_start", name="uq_usage_counter_period"))
    op.create_index("ix_usage_counter_verification", "usage_counters", ["verification_id"])
    op.create_table("usage_records",
        sa.Column("id", UUID, primary_key=True), sa.Column("verification_id", UUID, sa.ForeignKey("salla_order_verifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_key", sa.String(100), nullable=False), sa.Column("idempotency_key", sa.String(160), nullable=False), sa.Column("period_start", sa.DateTime(timezone=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("verification_id", "service_key", "idempotency_key", name="uq_usage_replay"))
    op.create_index("ix_usage_record_verification", "usage_records", ["verification_id"])


def downgrade() -> None:
    for table in ("usage_records", "usage_counters", "salla_access_sessions", "salla_order_verifications", "usage_policies", "salla_product_mappings", "salla_webhook_events", "salla_merchant_authorizations"):
        op.drop_table(table)
