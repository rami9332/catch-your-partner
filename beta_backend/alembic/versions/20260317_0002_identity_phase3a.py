"""identity phase3a

Revision ID: 20260317_0002
Revises: 20260317_0001
Create Date: 2026-03-17 00:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260317_0002"
down_revision = "20260317_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("premium_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "identity_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("face_embedding", sa.JSON(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("image_width", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("image_height", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("face_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("anti_fake_status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("anti_fake_reason_codes", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="local"),
        sa.Column("enrolled_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_identity_profiles_user_id", "identity_profiles", ["user_id"], unique=True)

    op.create_table(
        "identity_verification_attempts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_identity_verification_attempts_user_id", "identity_verification_attempts", ["user_id"], unique=False)
    op.create_index("ix_identity_verification_attempts_status", "identity_verification_attempts", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_identity_verification_attempts_status", table_name="identity_verification_attempts")
    op.drop_index("ix_identity_verification_attempts_user_id", table_name="identity_verification_attempts")
    op.drop_table("identity_verification_attempts")
    op.drop_index("ix_identity_profiles_user_id", table_name="identity_profiles")
    op.drop_table("identity_profiles")
    op.drop_column("users", "premium_enabled")
