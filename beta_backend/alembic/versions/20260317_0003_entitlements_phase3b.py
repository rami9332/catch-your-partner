"""entitlements phase3b

Revision ID: 20260317_0003
Revises: 20260317_0002
Create Date: 2026-03-17 00:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260317_0003"
down_revision = "20260317_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entitlements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_premium", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("plan", sa.String(length=50), nullable=False, server_default="free"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_entitlements_user_id", "entitlements", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_entitlements_user_id", table_name="entitlements")
    op.drop_table("entitlements")
