"""trust, matching, safety, and meeting follow-up

Revision ID: 20260321_0005
Revises: 20260318_0004
Create Date: 2026-03-21 06:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260321_0005"
down_revision = "20260318_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_number", sa.String(length=32), nullable=True))
    op.add_column(
        "users",
        sa.Column("phone_verification_status", sa.String(length=30), nullable=False, server_default="not_started"),
    )
    op.add_column("users", sa.Column("phone_verification_requested_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("phone_verified_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("phone_verification_locked_until", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("profile_photo_url", sa.String(length=500), nullable=True))
    op.add_column(
        "users",
        sa.Column("profile_photo_status", sa.String(length=30), nullable=False, server_default="not_started"),
    )
    op.add_column("users", sa.Column("profile_photo_uploaded_at", sa.DateTime(), nullable=True))
    op.create_index("ix_users_phone_verification_status", "users", ["phone_verification_status"], unique=False)

    op.create_table(
        "matching_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("verification_status", sa.String(length=40), nullable=False, server_default="not_ready"),
        sa.Column("face_scan_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("location_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("radar_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("matching_allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("matching_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("interests", sa.JSON(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("scan_meta", sa.JSON(), nullable=False),
        sa.Column("location_lat", sa.Float(), nullable=True),
        sa.Column("location_lng", sa.Float(), nullable=True),
        sa.Column("location_updated_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_radar_activation_at", sa.DateTime(), nullable=True),
        sa.Column("last_face_scan_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_matching_profiles_user_id", "matching_profiles", ["user_id"], unique=True)
    op.create_index("ix_matching_profiles_verification_status", "matching_profiles", ["verification_status"], unique=False)
    op.create_index("ix_matching_profiles_face_scan_available", "matching_profiles", ["face_scan_available"], unique=False)
    op.create_index("ix_matching_profiles_location_available", "matching_profiles", ["location_available"], unique=False)
    op.create_index("ix_matching_profiles_radar_active", "matching_profiles", ["radar_active"], unique=False)
    op.create_index("ix_matching_profiles_matching_eligible", "matching_profiles", ["matching_eligible"], unique=False)

    op.add_column("meetings", sa.Column("accepted_by", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("meetings", sa.Column("arrived_by", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("meetings", sa.Column("ok_by", sa.JSON(), nullable=False, server_default="[]"))

    op.create_table(
        "safety_circle_contacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("relation", sa.String(length=100), nullable=True),
        sa.Column("contact_channel", sa.String(length=30), nullable=False, server_default="phone"),
        sa.Column("phone_number", sa.String(length=32), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_safety_circle_contacts_user_id", "safety_circle_contacts", ["user_id"], unique=False)
    op.create_index("ix_safety_circle_contacts_is_primary", "safety_circle_contacts", ["is_primary"], unique=False)

    op.create_table(
        "safety_alarms",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("primary_contact_id", sa.String(length=36), sa.ForeignKey("safety_circle_contacts.id"), nullable=False),
        sa.Column("meeting_id", sa.String(length=36), sa.ForeignKey("meetings.id"), nullable=True),
        sa.Column("location_lat", sa.Float(), nullable=True),
        sa.Column("location_lng", sa.Float(), nullable=True),
        sa.Column("location_recorded_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="created"),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_safety_alarms_user_id", "safety_alarms", ["user_id"], unique=False)
    op.create_index("ix_safety_alarms_primary_contact_id", "safety_alarms", ["primary_contact_id"], unique=False)
    op.create_index("ix_safety_alarms_meeting_id", "safety_alarms", ["meeting_id"], unique=False)
    op.create_index("ix_safety_alarms_status", "safety_alarms", ["status"], unique=False)

    op.create_table(
        "phone_verification_challenges",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("delivery_status", sa.String(length=30), nullable=False, server_default="provider_missing"),
        sa.Column("attempts_remaining", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_phone_verification_challenges_user_id", "phone_verification_challenges", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_phone_verification_challenges_user_id", table_name="phone_verification_challenges")
    op.drop_table("phone_verification_challenges")

    op.drop_index("ix_safety_alarms_status", table_name="safety_alarms")
    op.drop_index("ix_safety_alarms_meeting_id", table_name="safety_alarms")
    op.drop_index("ix_safety_alarms_primary_contact_id", table_name="safety_alarms")
    op.drop_index("ix_safety_alarms_user_id", table_name="safety_alarms")
    op.drop_table("safety_alarms")

    op.drop_index("ix_safety_circle_contacts_is_primary", table_name="safety_circle_contacts")
    op.drop_index("ix_safety_circle_contacts_user_id", table_name="safety_circle_contacts")
    op.drop_table("safety_circle_contacts")

    op.drop_column("meetings", "ok_by")
    op.drop_column("meetings", "arrived_by")
    op.drop_column("meetings", "accepted_by")

    op.drop_index("ix_matching_profiles_matching_eligible", table_name="matching_profiles")
    op.drop_index("ix_matching_profiles_radar_active", table_name="matching_profiles")
    op.drop_index("ix_matching_profiles_location_available", table_name="matching_profiles")
    op.drop_index("ix_matching_profiles_face_scan_available", table_name="matching_profiles")
    op.drop_index("ix_matching_profiles_verification_status", table_name="matching_profiles")
    op.drop_index("ix_matching_profiles_user_id", table_name="matching_profiles")
    op.drop_table("matching_profiles")

    op.drop_index("ix_users_phone_verification_status", table_name="users")
    op.drop_column("users", "profile_photo_uploaded_at")
    op.drop_column("users", "profile_photo_status")
    op.drop_column("users", "profile_photo_url")
    op.drop_column("users", "phone_verification_locked_until")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "phone_verification_requested_at")
    op.drop_column("users", "phone_verification_status")
    op.drop_column("users", "phone_number")
