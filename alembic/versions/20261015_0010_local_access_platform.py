"""Store the selected safe platform on local usage identities."""

from alembic import op
import sqlalchemy as sa


revision = "20261015_0010"
down_revision = "20261004_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Historic local references were Steam-only; preserve them unchanged.
    inspector = sa.inspect(op.get_bind())
    cols = {c["name"] for c in inspector.get_columns("local_usage_identities")}
    if "platform_code" not in cols:
        op.add_column(
            "local_usage_identities",
            sa.Column("platform_code", sa.String(length=32), nullable=False, server_default="steam"),
        )
        op.alter_column("local_usage_identities", "platform_code", server_default=None)
    indexes = {i["name"] for i in inspector.get_indexes("local_usage_identities")}
    if "ix_local_usage_identities_platform_code" not in indexes:
        op.create_index("ix_local_usage_identities_platform_code", "local_usage_identities", ["platform_code"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {i["name"] for i in inspector.get_indexes("local_usage_identities")}
    if "ix_local_usage_identities_platform_code" in indexes:
        op.drop_index("ix_local_usage_identities_platform_code", table_name="local_usage_identities")
    cols = {c["name"] for c in inspector.get_columns("local_usage_identities")}
    if "platform_code" in cols:
        op.drop_column("local_usage_identities", "platform_code")
