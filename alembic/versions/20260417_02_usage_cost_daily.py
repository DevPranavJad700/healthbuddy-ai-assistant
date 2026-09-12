"""add usage cost daily table

Revision ID: 20260417_02
Revises: 20260417_01
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260417_02"
down_revision = "20260417_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_cost_daily",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.String(length=10), nullable=False),
        sa.Column("feature", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens_est", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens_est", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_usage_cost_daily_date", "usage_cost_daily", ["date"])
    op.create_index("ix_usage_cost_daily_feature", "usage_cost_daily", ["feature"])
    op.create_index("ix_usage_cost_daily_provider", "usage_cost_daily", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_usage_cost_daily_provider", table_name="usage_cost_daily")
    op.drop_index("ix_usage_cost_daily_feature", table_name="usage_cost_daily")
    op.drop_index("ix_usage_cost_daily_date", table_name="usage_cost_daily")
    op.drop_table("usage_cost_daily")
