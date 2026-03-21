from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=2, max_length=255)
    mode: Literal["free", "premium"] = "free"
    astro_sign: Optional[str] = None
    interests: List[str] = Field(default_factory=list)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    name: str
    role: str
    mode: str
    premium_enabled: bool
    astro_sign: Optional[str]
    interests: List[str]
    phone_number: Optional[str] = None
    phone_verification_status: str
    phone_verification_requested_at: Optional[datetime] = None
    phone_verified_at: Optional[datetime] = None
    phone_verification_locked_until: Optional[datetime] = None
    id_verification_status: str = "not_started"
    id_verification_requested_at: Optional[datetime] = None
    id_verified_at: Optional[datetime] = None
    profile_photo_url: Optional[str] = None
    profile_photo_status: str = "not_started"
    profile_photo_uploaded_at: Optional[datetime] = None
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class PhoneVerificationStartRequest(BaseModel):
    phone_number: str = Field(min_length=7, max_length=32)


class PhoneVerificationVerifyRequest(BaseModel):
    code: str = Field(min_length=4, max_length=8)


class PhoneVerificationResponse(BaseModel):
    phone_number: Optional[str] = None
    phone_verification_status: str
    phone_verification_requested_at: Optional[datetime] = None
    phone_verified_at: Optional[datetime] = None
    phone_verification_locked_until: Optional[datetime] = None
    challenge_expires_at: Optional[datetime] = None
    delivery_status: Optional[str] = None
    attempts_remaining: Optional[int] = None
    code_preview: Optional[str] = None
    user: UserResponse


class SafetyCircleContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    relation: Optional[str] = None
    contact_channel: str
    phone_number: Optional[str] = None
    is_primary: bool
    status: str
    created_at: datetime
    updated_at: datetime


class SafetyCircleContactCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    relation: Optional[str] = Field(default=None, max_length=100)
    contact_channel: str = Field(default="phone", max_length=30)
    phone_number: Optional[str] = Field(default=None, min_length=7, max_length=32)
    is_primary: bool = False


class SafetyCircleContactUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    relation: Optional[str] = Field(default=None, max_length=100)
    contact_channel: Optional[str] = Field(default=None, max_length=30)
    phone_number: Optional[str] = Field(default=None, min_length=7, max_length=32)
    is_primary: Optional[bool] = None


class RuntimeFlagRequest(BaseModel):
    module_key: str
    enabled: bool


class RadarStartRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    zone_tag: Optional[str] = Field(default=None, max_length=100)
    safe_zones: List[str] = Field(default_factory=list)


class MatchingLocationPayload(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    updated_at: Optional[datetime] = None


class MatchingTimestampsPayload(BaseModel):
    updated_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    last_radar_activation_at: Optional[datetime] = None
    last_face_scan_at: Optional[datetime] = None


class MatchingScanPayload(BaseModel):
    detector_mode: Optional[str] = None
    face_count: int = Field(default=0, ge=0)
    capture_available: bool = False


class MatchingProfileUpsertRequest(BaseModel):
    verification_status: str = Field(default="not_ready", max_length=40)
    face_scan_available: bool = False
    location_available: bool = False
    radar_active: bool = False
    matching_allowed: bool = True
    interests: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    location: Optional[MatchingLocationPayload] = None
    timestamps: MatchingTimestampsPayload = Field(default_factory=MatchingTimestampsPayload)
    scan: MatchingScanPayload = Field(default_factory=MatchingScanPayload)


class MatchingProfileResponse(BaseModel):
    user_id: str
    verification_status: str
    face_scan_available: bool
    location_available: bool
    radar_active: bool
    matching_allowed: bool
    matching_eligible: bool
    interests: List[str]
    preferences: Dict[str, Any]
    location: Optional[Dict[str, Any]]
    timestamps: Dict[str, Optional[datetime]]
    scan: Dict[str, Any]


class NearbyCandidateResponse(BaseModel):
    user_id: str
    name: str
    distance_meters: int
    within_radius: bool
    shared_interests: List[str]
    verification_status: str
    radar_active: bool
    location: Optional[Dict[str, Any]] = None


class NearbyCandidatesEnvelope(BaseModel):
    source_profile: MatchingProfileResponse
    candidates: List[NearbyCandidateResponse]


class MeetingStartRequest(BaseModel):
    target_user_id: str
    spot_name: str = Field(min_length=2, max_length=255)
    spot_lat: float = Field(ge=-90, le=90)
    spot_lng: float = Field(ge=-180, le=180)


class MeetingAcceptRequest(BaseModel):
    meeting_id: str


class NavigationStartRequest(BaseModel):
    meeting_id: str


class CheckInRequest(BaseModel):
    meeting_id: str
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class OkSignalRequest(BaseModel):
    meeting_id: str
    signal: Literal["ok", "not_ok"] = "ok"


class ChatUnlockRequest(BaseModel):
    meeting_id: str


class ChatSendRequest(BaseModel):
    meeting_id: str
    text: str = Field(min_length=1, max_length=500)


class SafetyRequest(BaseModel):
    meeting_id: Optional[str] = None
    reason: Optional[str] = Field(default=None, max_length=255)


class SafetyAlarmRequest(BaseModel):
    meeting_id: Optional[str] = None
    reason: Optional[str] = Field(default=None, max_length=255)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    location_recorded_at: Optional[datetime] = None


class SafetyAlarmResponse(BaseModel):
    id: str
    user_id: str
    primary_contact_id: str
    meeting_id: Optional[str] = None
    status: str
    location: Optional[Dict[str, Any]] = None
    details: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CapabilityResponse(BaseModel):
    modules: List[Dict]
    runtime_overrides: Dict[str, bool]
    core_flow: Dict


class IdentityProfileResponse(BaseModel):
    id: str
    user_id: str
    enrolled: bool
    anti_fake_status: str
    reason_codes: List[str]
    quality_score: float
    face_count: int
    enrolled_at: datetime


class IdentityVerificationResponse(BaseModel):
    verified: bool
    status: str
    confidence: float
    reason_codes: List[str]
    anti_fake_status: str


class EntitlementRequest(BaseModel):
    user_id: str
    is_premium: bool
    plan: str = Field(default="premium", max_length=50)
    expires_at: Optional[datetime] = None


class LookalikeSearchRequest(BaseModel):
    mode: Literal["lookalike"] = "lookalike"
    limit: int = Field(default=10, ge=1, le=50)


class LookalikeStatusResponse(BaseModel):
    available: bool
    premium_required: bool
    plan: str


class LookalikeMatchResponse(BaseModel):
    user_id: str
    similarity: float
    preview_fields: Dict


CompanionEventType = Literal[
    "radar_started",
    "radar_stopped",
    "meeting_created",
    "navigation_started",
    "checkin",
    "ok",
    "chat_unlocked",
    "share_location",
    "abort_meeting",
    "panic",
]


class CompanionStateResponse(BaseModel):
    user_id: str
    level: int
    xp: int
    streak: int
    mood: str
    last_message: str
    next_level_xp: int
    updated_at: datetime


class CompanionEventRequest(BaseModel):
    event_type: CompanionEventType
    meta: Dict[str, Any] = Field(default_factory=dict)


class CompanionEventResponse(BaseModel):
    state: CompanionStateResponse
    reward_delta: int
    leveled_up: bool
    message: str


class CompanionSayRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class CompanionSayResponse(BaseModel):
    reply: str
    mood: str
    suggested_action: Optional[str] = None
