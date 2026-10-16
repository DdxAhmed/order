"""Add browser sessions and browser-bound verification requests.

Revision ID: 20260911_0002
Revises: 20260908_0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260911_0002"
down_revision = "20260908_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "customer_sessions" not in tables:
        op.create_table(
            "customer_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("csrf_token", sa.String(length=96), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("token_hash"),
        )
    existing_indexes = {item["name"] for item in inspector.get_indexes("customer_sessions")}
    for name, column in (
        ("ix_customer_sessions_customer_id", "customer_id"),
        ("ix_customer_sessions_token_hash", "token_hash"),
        ("ix_customer_sessions_expires_at", "expires_at"),
    ):
        if name not in existing_indexes:
            op.create_index(name, "customer_sessions", [column])

    verification_columns = {item["name"] for item in inspector.get_columns("verification_requests")}
    if "requested_by_web_session_id" not in verification_columns:
        op.add_column(
            "verification_requests",
            sa.Column("requested_by_web_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
    existing_foreign_keys = {item["name"] for item in inspector.get_foreign_keys("verification_requests")}
    if "fk_verification_requests_web_session" not in existing_foreign_keys:
        op.create_foreign_key(
            "fk_verification_requests_web_session",
            "verification_requests",
            "customer_sessions",
            ["requested_by_web_session_id"],
            ["id"],
            ondelete="SET NULL",
        )
    existing_verification_indexes = {item["name"] for item in inspector.get_indexes("verification_requests")}
    if "ix_verification_requests_requested_by_web_session_id" not in existing_verification_indexes:
        op.create_index(
            "ix_verification_requests_requested_by_web_session_id",
            "verification_requests",
            ["requested_by_web_session_id"],
        )
    telegram_column = next(
        item for item in inspector.get_columns("verification_requests") if item["name"] == "requested_by_telegram_id"
    )
    if not telegram_column["nullable"]:
        op.alter_column("verification_requests", "requested_by_telegram_id", nullable=True)
    existing_checks = {item["name"] for item in inspector.get_check_constraints("verification_requests")}
    if "ck_verification_actor" not in existing_checks:
        op.create_check_constraint(
            "ck_verification_actor",
            "verification_requests",
            "((requested_by_telegram_id IS NOT NULL) <> (requested_by_web_session_id IS NOT NULL))",
        )


def downgrade() -> None:
    op.drop_constraint("ck_verification_actor", "verification_requests", type_="check")
    op.alter_column("verification_requests", "requested_by_telegram_id", nullable=False)
    op.drop_index("ix_verification_requests_requested_by_web_session_id", table_name="verification_requests")
    op.drop_constraint("fk_verification_requests_web_session", "verification_requests", type_="foreignkey")
    op.drop_column("verification_requests", "requested_by_web_session_id")
    op.drop_index("ix_customer_sessions_expires_at", table_name="customer_sessions")
    op.drop_index("ix_customer_sessions_token_hash", table_name="customer_sessions")
    op.drop_index("ix_customer_sessions_customer_id", table_name="customer_sessions")
    op.drop_table("customer_sessions")
