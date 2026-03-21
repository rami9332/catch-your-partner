from datetime import datetime
import uuid
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user")
    mode: Mapped[str] = mapped_column(String(20), default="free")
    premium_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    astro_sign: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    interests: Mapped[list] = mapped_column(JSON, default=list)
    phone_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    phone_verification_status: Mapped[str] = mapped_column(String(30), default="not_started", index=True)
    phone_verification_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    phone_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    phone_verification_locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    id_verification_status: Mapped[str] = mapped_column(String(30), default="not_started", index=True)
    id_verification_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    id_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    profile_photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    profile_photo_status: Mapped[str] = mapped_column(String(30), default="not_started")
    profile_photo_uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RadarSession(Base):
    __tablename__ = "radar_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    zone_tag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    safe_zones: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped[User] = relationship()


class MatchingProfile(Base):
    __tablename__ = "matching_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
    verification_status: Mapped[str] = mapped_column(String(40), default="not_ready", index=True)
    face_scan_available: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    location_available: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    radar_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    matching_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    matching_eligible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    interests: Mapped[list] = mapped_column(JSON, default=list)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    scan_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    location_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_radar_activation_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_face_scan_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship()


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    initiator_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    participant_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    spot_name: Mapped[str] = mapped_column(String(255), nullable=False)
    spot_lat: Mapped[float] = mapped_column(Float, nullable=False)
    spot_lng: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="planned", index=True)
    accepted_by: Mapped[list] = mapped_column(JSON, default=list)
    arrived_by: Mapped[list] = mapped_column(JSON, default=list)
    ok_by: Mapped[list] = mapped_column(JSON, default=list)
    navigation_started_by: Mapped[list] = mapped_column(JSON, default=list)
    checkins: Mapped[dict] = mapped_column(JSON, default=dict)
    ok_signals: Mapped[dict] = mapped_column(JSON, default=dict)
    chat_unlocked: Mapped[bool] = mapped_column(Boolean, default=False)
    chat_locked_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    chat_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), nullable=False, index=True)
    sender_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SafetyEvent(Base):
    __tablename__ = "safety_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    meeting_id: Mapped[Optional[str]] = mapped_column(ForeignKey("meetings.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SafetyCircleContact(Base):
    __tablename__ = "safety_circle_contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    relation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_channel: Mapped[str] = mapped_column(String(30), default="phone")
    phone_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SafetyAlarm(Base):
    __tablename__ = "safety_alarms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    primary_contact_id: Mapped[str] = mapped_column(ForeignKey("safety_circle_contacts.id"), nullable=False, index=True)
    meeting_id: Mapped[Optional[str]] = mapped_column(ForeignKey("meetings.id"), nullable=True, index=True)
    location_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_recorded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="created", index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AuthRateCounter(Base):
    __tablename__ = "auth_rate_counters"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PhoneVerificationChallenge(Base):
    __tablename__ = "phone_verification_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(30), default="provider_missing")
    attempts_remaining: Mapped[int] = mapped_column(Integer, default=5)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IdentityProfile(Base):
    __tablename__ = "identity_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
    face_embedding: Mapped[list] = mapped_column(JSON, default=list)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    image_width: Mapped[int] = mapped_column(Integer, default=0)
    image_height: Mapped[int] = mapped_column(Integer, default=0)
    face_count: Mapped[int] = mapped_column(Integer, default=0)
    anti_fake_status: Mapped[str] = mapped_column(String(40), default="pending")
    anti_fake_reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    provider: Mapped[str] = mapped_column(String(50), default="local")
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class IdentityVerificationAttempt(Base):
    __tablename__ = "identity_verification_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Entitlement(Base):
    __tablename__ = "entitlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class CompanionState(Base):
    __tablename__ = "companion_state"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    mood: Mapped[str] = mapped_column(String(40), default="curious")
    last_message: Mapped[str] = mapped_column(
        Text,
        default="I'm here for safer, better meetups. Start with radar and I'll track your progress.",
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class CompanionEvent(Base):
    __tablename__ = "companion_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    xp_delta: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
