"""Add delegated Microsoft Graph OAuth2 mailboxes.

Revision ID: 20260914_0003
Revises: 20260911_0002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260914_0003"
down_revision = "20260911_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    mailbox_columns = {item["name"] for item in inspector.get_columns("mailboxes")}
    if "auth_mode" not in mailbox_columns:
        op.add_column("mailboxes", sa.Column("auth_mode", sa.String(length=32), nullable=False, server_default="imap_password"))
    if "oauth_refresh_token" not in mailbox_columns:
        op.add_column("mailboxes", sa.Column("oauth_refresh_token", sa.LargeBinary(), nullable=True))
    encrypted_password = next(item for item in inspector.get_columns("mailboxes") if item["name"] == "encrypted_password")
    if not encrypted_password["nullable"]:
        op.alter_column("mailboxes", "encrypted_password", nullable=True)

    tables = set(inspector.get_table_names())
    if "mailbox_oauth_states" not in tables:
        op.create_table(
            "mailbox_oauth_states",
            sa.Column("state_hash", sa.String(length=64), primary_key=True),
            sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("label", sa.String(length=100), nullable=False),
            sa.Column("username", sa.String(length=320), nullable=False),
            sa.Column("code_verifier_encrypted", sa.LargeBinary(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["admin_id"], ["admin_users.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_mailbox_oauth_states_admin_id", "mailbox_oauth_states", ["admin_id"])
        op.create_index("ix_mailbox_oauth_states_expires_at", "mailbox_oauth_states", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_mailbox_oauth_states_expires_at", table_name="mailbox_oauth_states")
    op.drop_index("ix_mailbox_oauth_states_admin_id", table_name="mailbox_oauth_states")
    op.drop_table("mailbox_oauth_states")
    op.alter_column("mailboxes", "encrypted_password", nullable=False)
    op.drop_column("mailboxes", "oauth_refresh_token")
    op.drop_column("mailboxes", "auth_mode")
