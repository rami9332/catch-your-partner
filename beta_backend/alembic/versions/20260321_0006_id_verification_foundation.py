"""id verification foundation

Revision ID: 20260321_0006
Revises: 20260321_0005
Create Date: 2026-03-21 09:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260321_0006"
down_revision = "20260321_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("id_verification_status", sa.String(length=30), nullable=False, server_default="not_started"),
    )
    op.add_column("users", sa.Column("id_verification_requested_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("id_verified_at", sa.DateTime(), nullable=True))
    op.create_index("ix_users_id_verification_status", "users", ["id_verification_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_id_verification_status", table_name="users")
    op.drop_column("users", "id_verified_at")
    op.drop_column("users", "id_verification_requested_at")
    op.drop_column("users", "id_verification_status")
