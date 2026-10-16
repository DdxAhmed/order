"""Ensure the safe inventory platform catalog exists."""

from alembic import op
import sqlalchemy as sa


revision = "20261004_0009"
down_revision = "20260927_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing deployments already have the generic ``platforms`` table.  The
    # upsert is deliberately non-destructive: it only adds the supported
    # inventory records when missing and refreshes their user-facing labels.
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO platforms (id, code, name, is_enabled, mail_profile)
            VALUES
                ('00000000-0000-0000-0000-000000000001'::uuid, 'steam', 'Steam', false, '{}'::jsonb),
                ('00000000-0000-0000-0000-000000000003'::uuid, 'rockstar', 'Rockstar Games', false, '{}'::jsonb),
                ('00000000-0000-0000-0000-000000000004'::uuid, 'ubisoft', 'Ubisoft', false, '{}'::jsonb)
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name
            """
        )
    )


def downgrade() -> None:
    # Never remove platform rows because existing inventory may reference them.
    pass

