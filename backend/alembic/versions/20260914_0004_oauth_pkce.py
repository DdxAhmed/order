"""Add PKCE verifier storage to mailbox OAuth state.

Revision ID: 20260914_0004
Revises: 20260914_0003
"""

from alembic import op
import sqlalchemy as sa


revision = "20260914_0004"
down_revision = "20260914_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("mailbox_oauth_states")}
    if "code_verifier_encrypted" not in columns:
        op.add_column(
            "mailbox_oauth_states",
            sa.Column("code_verifier_encrypted", sa.LargeBinary(), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("mailbox_oauth_states")}
    if "code_verifier_encrypted" in columns:
        op.drop_column("mailbox_oauth_states", "code_verifier_encrypted")
