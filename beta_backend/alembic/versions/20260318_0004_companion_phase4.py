"""companion phase4

Revision ID: 20260318_0004
Revises: 20260317_0003
Create Date: 2026-03-18 00:15:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260318_0004"
down_revision = "20260317_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companion_state",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("xp", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mood", sa.String(length=40), nullable=False, server_default="curious"),
        sa.Column(
            "last_message",
            sa.Text(),
            nullable=False,
            server_default="I'm here for safer, better meetups. Start with radar and I'll track your progress.",
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "companion_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("meta_json", sa.JSON(), nullable=False),
        sa.Column("xp_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_companion_events_user_id", "companion_events", ["user_id"], unique=False)
    op.create_index("ix_companion_events_event_type", "companion_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_companion_events_event_type", table_name="companion_events")
    op.drop_index("ix_companion_events_user_id", table_name="companion_events")
    op.drop_table("companion_events")
    op.drop_table("companion_state")
