"""initial core schema

Revision ID: 20260317_0001
Revises:
Create Date: 2026-03-17 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260317_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="free"),
        sa.Column("astro_sign", sa.String(length=50), nullable=True),
        sa.Column("interests", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "radar_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("zone_tag", sa.String(length=100), nullable=True),
        sa.Column("safe_zones", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_radar_sessions_user_id", "radar_sessions", ["user_id"], unique=False)
    op.create_index("ix_radar_sessions_active", "radar_sessions", ["active"], unique=False)

    op.create_table(
        "meetings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("initiator_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("participant_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("spot_name", sa.String(length=255), nullable=False),
        sa.Column("spot_lat", sa.Float(), nullable=False),
        sa.Column("spot_lng", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="planned"),
        sa.Column("navigation_started_by", sa.JSON(), nullable=False),
        sa.Column("checkins", sa.JSON(), nullable=False),
        sa.Column("ok_signals", sa.JSON(), nullable=False),
        sa.Column("chat_unlocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("chat_locked_reason", sa.String(length=100), nullable=True),
        sa.Column("chat_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_meetings_status", "meetings", ["status"], unique=False)

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("meeting_id", sa.String(length=36), sa.ForeignKey("meetings.id"), nullable=False),
        sa.Column("sender_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_chat_messages_meeting_id", "chat_messages", ["meeting_id"], unique=False)

    op.create_table(
        "safety_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("meeting_id", sa.String(length=36), sa.ForeignKey("meetings.id"), nullable=True),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_safety_events_user_id", "safety_events", ["user_id"], unique=False)
    op.create_index("ix_safety_events_meeting_id", "safety_events", ["meeting_id"], unique=False)
    op.create_index("ix_safety_events_event_type", "safety_events", ["event_type"], unique=False)

    op.create_table(
        "auth_rate_counters",
        sa.Column("key", sa.String(length=255), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("auth_rate_counters")
    op.drop_index("ix_safety_events_event_type", table_name="safety_events")
    op.drop_index("ix_safety_events_meeting_id", table_name="safety_events")
    op.drop_index("ix_safety_events_user_id", table_name="safety_events")
    op.drop_table("safety_events")
    op.drop_index("ix_chat_messages_meeting_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_meetings_status", table_name="meetings")
    op.drop_table("meetings")
    op.drop_index("ix_radar_sessions_active", table_name="radar_sessions")
    op.drop_index("ix_radar_sessions_user_id", table_name="radar_sessions")
    op.drop_table("radar_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
