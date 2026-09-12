"""add revoked tokens table

Revision ID: 20260417_03
Revises: 20260417_02
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260417_03"
down_revision = "20260417_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jti", sa.String(length=64), nullable=False, unique=True),
        sa.Column("token_type", sa.String(length=20), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_revoked_tokens_jti", "revoked_tokens", ["jti"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_revoked_tokens_jti", table_name="revoked_tokens")
    op.drop_table("revoked_tokens")
