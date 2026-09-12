"""baseline schema migration

Revision ID: 20260417_01
Revises:
Create Date: 2026-04-17
"""

from alembic import op
from app.core.database import Base

# revision identifiers, used by Alembic.
revision = "20260417_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
