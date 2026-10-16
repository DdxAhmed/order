"""Store parsed Salla line-item quantity on email entitlements.

Revision ID: 20260926_0007
Revises: 20260923_0006
"""

from alembic import op
import sqlalchemy as sa


revision = "20260926_0007"
down_revision = "20260923_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("salla_order_verifications")}
    if "quantity" not in columns:
        op.add_column("salla_order_verifications", sa.Column("quantity", sa.Integer(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("salla_order_verifications")}
    if "quantity" in columns:
        op.drop_column("salla_order_verifications", "quantity")
