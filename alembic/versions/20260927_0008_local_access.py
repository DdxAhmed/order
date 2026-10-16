"""Add local access identities and isolated generic usage counters.

Revision ID: 20260927_0008
Revises: 20260926_0007
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260927_0008"
down_revision = "20260926_0007"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "local_usage_identities" not in tables:
        op.create_table(
            "local_usage_identities",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("reference_key", sa.String(length=120), nullable=False),
            sa.Column("account_alias", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("reference_key", name="uq_local_usage_reference"),
        )
        op.create_index("ix_local_usage_identity_reference", "local_usage_identities", ["reference_key"])
    if "local_access_sessions" not in tables:
        op.create_table(
            "local_access_sessions",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("identity_id", UUID, sa.ForeignKey("local_usage_identities.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("csrf_token", sa.String(length=96), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("token_hash", name="uq_local_access_token"),
        )
        op.create_index("ix_local_access_session_identity", "local_access_sessions", ["identity_id"])
        op.create_index("ix_local_access_session_token", "local_access_sessions", ["token_hash"])
    if "local_usage_counters" not in tables:
        op.create_table(
            "local_usage_counters",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("identity_id", UUID, sa.ForeignKey("local_usage_identities.id", ondelete="CASCADE"), nullable=False),
            sa.Column("service_key", sa.String(length=100), nullable=False),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_used_at", sa.DateTime(timezone=True)),
            sa.UniqueConstraint("identity_id", "service_key", "period_start", name="uq_local_usage_counter_period"),
        )
        op.create_index("ix_local_usage_counter_identity", "local_usage_counters", ["identity_id"])
        op.create_index("ix_local_usage_counter_service", "local_usage_counters", ["service_key"])
    if "local_usage_records" not in tables:
        op.create_table(
            "local_usage_records",
            sa.Column("id", UUID, primary_key=True),
            sa.Column("identity_id", UUID, sa.ForeignKey("local_usage_identities.id", ondelete="CASCADE"), nullable=False),
            sa.Column("service_key", sa.String(length=100), nullable=False),
            sa.Column("idempotency_key", sa.String(length=160), nullable=False),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("identity_id", "service_key", "idempotency_key", name="uq_local_usage_replay"),
        )
        op.create_index("ix_local_usage_record_identity", "local_usage_records", ["identity_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table in ("local_usage_records", "local_usage_counters", "local_access_sessions", "local_usage_identities"):
        if table in tables:
            op.drop_table(table)
