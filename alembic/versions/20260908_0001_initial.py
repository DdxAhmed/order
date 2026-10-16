"""Initial secure inventory and delivery schema.

Revision ID: 20260908_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

from app.models import Base

revision = "20260908_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    bind.execute(sa.text(
        """
        INSERT INTO platforms (id, code, name, is_enabled, mail_profile)
        VALUES ('00000000-0000-0000-0000-000000000001'::uuid, 'steam', 'Steam', false, '{}'::jsonb),
               ('00000000-0000-0000-0000-000000000002'::uuid, 'playstation', 'PlayStation', false, '{}'::jsonb),
               ('00000000-0000-0000-0000-000000000003'::uuid, 'rockstar', 'Rockstar', false, '{}'::jsonb),
               ('00000000-0000-0000-0000-000000000004'::uuid, 'ubisoft', 'Ubisoft', false, '{}'::jsonb)
        ON CONFLICT (code) DO NOTHING
        """
    ))


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
