from datetime import datetime, timedelta
import math
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.events import EventBus
from app.models.db import ChatMessage, MatchingProfile, Meeting, RadarSession, SafetyAlarm, SafetyCircleContact, SafetyEvent, User
from app.models.schemas import MatchingProfileUpsertRequest
from app.services.sms_service import SmsService


def utcnow() -> datetime:
    return datetime.utcnow()


def distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return radius * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


class CoreService:
    def __init__(self, settings: Settings, events: EventBus) -> None:
        self.settings = settings
        self.events = events
        self.sms_service = SmsService()

    def start_radar(self, db: Session, user: User, lat: float, lng: float, zone_tag: Optional[str], safe_zones: list[str]) -> RadarSession:
        db.query(RadarSession).filter(RadarSession.user_id == user.id, RadarSession.active.is_(True)).update({"active": False})
        session = RadarSession(
            user_id=user.id,
            lat=lat,
            lng=lng,
            zone_tag=zone_tag,
            safe_zones=safe_zones,
            active=True,
            expires_at=utcnow() + timedelta(minutes=self.settings.radar_ttl_minutes),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        self.events.publish("core.radar.started", {"user_id": user.id, "radar_session_id": session.id})
        return session

    def stop_radar(self, db: Session, user: User) -> None:
        db.query(RadarSession).filter(RadarSession.user_id == user.id, RadarSession.active.is_(True)).update({"active": False})
        db.commit()

    def _parse_dt(self, value: Optional[datetime]) -> Optional[datetime]:
        return value

    def _matching_radius(self, profile: MatchingProfile) -> int:
        preferences = profile.preferences or {}
        radius = preferences.get("maxDistanceMeters", 300)
        try:
            return max(50, min(int(radius), 5000))
        except Exception:
            return 300

    def _matching_eligible(self, profile: MatchingProfile) -> bool:
        return bool(
            profile.face_scan_available
            and profile.verification_status in {"ready", "verified"}
            and profile.radar_active
            and profile.location_available
            and profile.matching_allowed
            and profile.location_lat is not None
            and profile.location_lng is not None
        )

    def matching_profile_to_dict(self, profile: MatchingProfile) -> dict:
        return {
            "user_id": profile.user_id,
            "verification_status": profile.verification_status,
            "face_scan_available": profile.face_scan_available,
            "location_available": profile.location_available,
            "radar_active": profile.radar_active,
            "matching_allowed": profile.matching_allowed,
            "matching_eligible": profile.matching_eligible,
            "interests": profile.interests or [],
            "preferences": profile.preferences or {},
            "location": (
                {
                    "lat": profile.location_lat,
                    "lng": profile.location_lng,
                    "updated_at": profile.location_updated_at,
                }
                if profile.location_lat is not None and profile.location_lng is not None
                else None
            ),
            "timestamps": {
                "updated_at": profile.updated_at,
                "last_seen_at": profile.last_seen_at,
                "last_radar_activation_at": profile.last_radar_activation_at,
                "last_face_scan_at": profile.last_face_scan_at,
            },
            "scan": profile.scan_meta or {},
        }

    def upsert_matching_profile(self, db: Session, user: User, payload: MatchingProfileUpsertRequest) -> MatchingProfile:
        profile = db.scalar(select(MatchingProfile).where(MatchingProfile.user_id == user.id))
        if profile is None:
            profile = MatchingProfile(user_id=user.id)
            db.add(profile)

        profile.verification_status = payload.verification_status
        profile.face_scan_available = payload.face_scan_available
        profile.location_available = payload.location_available and payload.location is not None
        profile.radar_active = payload.radar_active
        profile.matching_allowed = payload.matching_allowed
        profile.interests = payload.interests or []
        profile.preferences = payload.preferences or {}
        profile.scan_meta = payload.scan.model_dump(mode="json")
        profile.last_seen_at = payload.timestamps.last_seen_at
        profile.last_radar_activation_at = payload.timestamps.last_radar_activation_at
        profile.last_face_scan_at = payload.timestamps.last_face_scan_at

        if payload.location is not None:
            profile.location_lat = payload.location.lat
            profile.location_lng = payload.location.lng
            profile.location_updated_at = payload.location.updated_at or payload.timestamps.last_seen_at or datetime.utcnow()
        else:
            profile.location_lat = None
            profile.location_lng = None
            profile.location_updated_at = None

        profile.matching_eligible = self._matching_eligible(profile)
        db.commit()
        db.refresh(profile)
        self.events.publish(
            "core.matching.profile_synced",
            {"user_id": user.id, "eligible": profile.matching_eligible, "radar_active": profile.radar_active},
        )
        return profile

    def get_matching_profile(self, db: Session, user: User) -> MatchingProfile:
        profile = db.scalar(select(MatchingProfile).where(MatchingProfile.user_id == user.id))
        if profile is None:
            raise HTTPException(status_code=404, detail="Matching profile not found")
        return profile

    def nearby_matching_candidates(self, db: Session, user: User) -> dict:
        source = self.get_matching_profile(db, user)
        source.matching_eligible = self._matching_eligible(source)
        db.commit()
        db.refresh(source)

        if not source.matching_eligible:
            return {"source_profile": self.matching_profile_to_dict(source), "candidates": []}

        candidates = db.scalars(
            select(MatchingProfile).where(
                MatchingProfile.user_id != user.id,
                MatchingProfile.matching_allowed.is_(True),
                MatchingProfile.radar_active.is_(True),
                MatchingProfile.face_scan_available.is_(True),
                MatchingProfile.location_available.is_(True),
            )
        ).all()

        results = []
        source_radius = self._matching_radius(source)

        for candidate in candidates:
            candidate.matching_eligible = self._matching_eligible(candidate)
            if not candidate.matching_eligible:
                continue
            if candidate.location_lat is None or candidate.location_lng is None or source.location_lat is None or source.location_lng is None:
                continue

            distance = distance_meters(source.location_lat, source.location_lng, candidate.location_lat, candidate.location_lng)
            candidate_radius = self._matching_radius(candidate)
            within_radius = distance <= min(source_radius, candidate_radius)
            if not within_radius:
                continue

            candidate_user = db.get(User, candidate.user_id)
            if candidate_user is None:
                continue

            shared_interests = sorted(set(source.interests or []) & set(candidate.interests or []))
            results.append(
                {
                    "user_id": candidate.user_id,
                    "name": candidate_user.name,
                    "distance_meters": round(distance),
                    "within_radius": within_radius,
                    "shared_interests": shared_interests,
                    "verification_status": candidate.verification_status,
                    "radar_active": candidate.radar_active,
                    "location": {
                        "lat": candidate.location_lat,
                        "lng": candidate.location_lng,
                        "updated_at": candidate.location_updated_at,
                    },
                }
            )

        results.sort(key=lambda item: (item["distance_meters"], -len(item["shared_interests"])))
        self.events.publish("core.matching.candidates_viewed", {"user_id": user.id, "count": len(results)})
        return {"source_profile": self.matching_profile_to_dict(source), "candidates": results}

    def _pair_meeting_query(self, user_a_id: str, user_b_id: str):
        return select(Meeting).where(
            or_(
                and_(Meeting.initiator_id == user_a_id, Meeting.participant_id == user_b_id),
                and_(Meeting.initiator_id == user_b_id, Meeting.participant_id == user_a_id),
            )
        )

    def _validated_pair_matching(self, db: Session, source_user_id: str, target_user_id: str) -> tuple[MatchingProfile, MatchingProfile]:
        source = db.scalar(select(MatchingProfile).where(MatchingProfile.user_id == source_user_id))
        target = db.scalar(select(MatchingProfile).where(MatchingProfile.user_id == target_user_id))
        if source is None or target is None:
            return source, target

        source.matching_eligible = self._matching_eligible(source)
        target.matching_eligible = self._matching_eligible(target)
        db.commit()
        db.refresh(source)
        db.refresh(target)

        if not source.matching_eligible or not target.matching_eligible:
            raise HTTPException(status_code=409, detail="Candidate is no longer eligible for a meeting")
        if source.location_lat is None or source.location_lng is None or target.location_lat is None or target.location_lng is None:
            raise HTTPException(status_code=409, detail="Location data is incomplete for meeting creation")

        distance = distance_meters(source.location_lat, source.location_lng, target.location_lat, target.location_lng)
        if distance > min(self._matching_radius(source), self._matching_radius(target)):
            raise HTTPException(status_code=409, detail="Candidate is no longer within meeting radius")

        return source, target

    def get_pair_meeting(self, db: Session, user: User, other_user_id: str) -> Meeting:
        meeting = db.scalar(
            self._pair_meeting_query(user.id, other_user_id)
            .where(Meeting.status != "aborted")
            .order_by(Meeting.created_at.desc())
        )
        if meeting is None:
            raise HTTPException(status_code=404, detail="Meeting not found")
        self.ensure_member(meeting, user)
        return meeting

    def radar_results(self, db: Session, user: User) -> list[dict]:
        now = utcnow()
        requester_radar = db.scalar(
            select(RadarSession).where(
                RadarSession.user_id == user.id,
                RadarSession.active.is_(True),
                RadarSession.expires_at > now,
            )
        )
        active_sessions = db.scalars(
            select(RadarSession).where(
                RadarSession.active.is_(True),
                RadarSession.expires_at > now,
                RadarSession.user_id != user.id,
            )
        ).all()

        results = []
        for radar in active_sessions:
            other = db.get(User, radar.user_id)
            if not other:
                continue
            overlap = len(set(user.interests or []) & set(other.interests or []))
            score = min(0.5 + overlap * 0.1, 0.9)
            distance = (
                distance_meters(requester_radar.lat, requester_radar.lng, radar.lat, radar.lng)
                if requester_radar
                else 0
            )
            results.append(
                {
                    "radar_session_id": radar.id,
                    "user_id": other.id,
                    "name": other.name,
                    "match_score": round(score, 2),
                    "distance_m": round(distance),
                    "mode": other.mode,
                }
            )
        self.events.publish("core.radar.viewed", {"user_id": user.id, "count": len(results)})
        return results

    def create_meeting(self, db: Session, initiator: User, target_user_id: str, spot_name: str, spot_lat: float, spot_lng: float) -> Meeting:
        target = db.get(User, target_user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Target user not found")

        self._validated_pair_matching(db, initiator.id, target_user_id)

        existing = db.scalar(
            self._pair_meeting_query(initiator.id, target_user_id)
            .where(Meeting.status != "aborted")
            .order_by(Meeting.created_at.desc())
        )
        if existing is not None:
            return existing

        meeting = Meeting(
            initiator_id=initiator.id,
            participant_id=target.id,
            spot_name=spot_name,
            spot_lat=spot_lat,
            spot_lng=spot_lng,
            status="awaiting_acceptance",
            accepted_by=[],
            arrived_by=[],
            ok_by=[],
            navigation_started_by=[],
            checkins={},
            ok_signals={},
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        self.events.publish("core.meeting.created", {"meeting_id": meeting.id, "users": [initiator.id, target.id]})
        return meeting

    def get_meeting(self, db: Session, meeting_id: str) -> Meeting:
        meeting = db.get(Meeting, meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return meeting

    def ensure_member(self, meeting: Meeting, user: User) -> None:
        if user.id not in {meeting.initiator_id, meeting.participant_id}:
            raise HTTPException(status_code=403, detail="Not part of this meeting")

    def _meeting_fully_accepted(self, meeting: Meeting) -> bool:
        accepted_by = set(meeting.accepted_by or [])
        return meeting.initiator_id in accepted_by and meeting.participant_id in accepted_by

    def _meeting_both_arrived(self, meeting: Meeting) -> bool:
        arrived_by = set(meeting.arrived_by or [])
        return meeting.initiator_id in arrived_by and meeting.participant_id in arrived_by

    def _meeting_both_ok(self, meeting: Meeting) -> bool:
        ok_by = set(meeting.ok_by or [])
        return meeting.initiator_id in ok_by and meeting.participant_id in ok_by

    def accept_meeting(self, db: Session, meeting: Meeting, user: User) -> Meeting:
        self.ensure_member(meeting, user)
        if meeting.status in {"aborted", "chat_open"}:
            raise HTTPException(status_code=409, detail="Meeting is no longer available for acceptance")

        accepted_by = set(meeting.accepted_by or [])
        accepted_by.add(user.id)
        meeting.accepted_by = sorted(accepted_by)
        meeting.status = "accepted" if self._meeting_fully_accepted(meeting) else "awaiting_acceptance"
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        self.events.publish("core.meeting.accepted", {"meeting_id": meeting.id, "user_id": user.id, "fully_accepted": self._meeting_fully_accepted(meeting)})
        return meeting

    def start_navigation(self, db: Session, meeting: Meeting, user: User) -> Meeting:
        self.ensure_member(meeting, user)
        if not self._meeting_fully_accepted(meeting):
            raise HTTPException(status_code=409, detail="Meeting must be accepted by both users before navigation starts")
        started_by = set(meeting.navigation_started_by or [])
        started_by.add(user.id)
        meeting.navigation_started_by = sorted(started_by)
        meeting.status = "navigating"
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        self.events.publish("core.navigation.started", {"meeting_id": meeting.id, "user_id": user.id})
        return meeting

    def check_in(self, db: Session, meeting: Meeting, user: User, lat: float, lng: float) -> Meeting:
        self.ensure_member(meeting, user)
        if not self._meeting_fully_accepted(meeting):
            raise HTTPException(status_code=409, detail="Meeting must be accepted by both users before arrival check-in")
        if meeting.status == "aborted":
            raise HTTPException(status_code=409, detail="Meeting aborted")

        if distance_meters(lat, lng, meeting.spot_lat, meeting.spot_lng) > self.settings.checkin_radius_meters:
            raise HTTPException(status_code=422, detail="Check-in is too far from the meeting spot")

        arrived_by = set(meeting.arrived_by or [])
        arrived_by.add(user.id)
        meeting.arrived_by = sorted(arrived_by)
        payload = dict(meeting.checkins or {})
        payload[user.id] = {"lat": lat, "lng": lng, "at": utcnow().isoformat()}
        meeting.checkins = payload
        meeting.status = "checked_in" if self._meeting_both_arrived(meeting) else "awaiting_arrival"
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        self.events.publish("core.checkin.completed", {"meeting_id": meeting.id, "user_id": user.id, "both_arrived": self._meeting_both_arrived(meeting)})
        return meeting

    def signal_ok(self, db: Session, meeting: Meeting, user: User, signal: str) -> Meeting:
        self.ensure_member(meeting, user)
        if not self._meeting_both_arrived(meeting):
            raise HTTPException(status_code=409, detail="Both users must arrive before OK can be confirmed")
        if meeting.status == "aborted":
            raise HTTPException(status_code=409, detail="Meeting aborted")
        payload = dict(meeting.ok_signals or {})
        payload[user.id] = signal
        meeting.ok_signals = payload
        if signal == "ok":
            ok_by = set(meeting.ok_by or [])
            ok_by.add(user.id)
            meeting.ok_by = sorted(ok_by)
        else:
            ok_by = set(meeting.ok_by or [])
            ok_by.discard(user.id)
            meeting.ok_by = sorted(ok_by)
        if self._meeting_both_ok(meeting):
            meeting.chat_unlocked = True
            meeting.status = "ok_confirmed"
        else:
            meeting.chat_unlocked = False
            meeting.status = "awaiting_ok"
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        self.events.publish("core.ok.completed", {"meeting_id": meeting.id, "user_id": user.id, "signal": signal, "both_ok": self._meeting_both_ok(meeting)})
        return meeting

    def unlock_chat(self, db: Session, meeting: Meeting, user: User) -> Meeting:
        self.ensure_member(meeting, user)
        if meeting.status == "aborted":
            raise HTTPException(status_code=403, detail="Meeting aborted")
        if not meeting.chat_unlocked:
            raise HTTPException(status_code=403, detail="Chat remains locked until both users confirm OK")

        meeting.chat_expires_at = utcnow() + timedelta(hours=self.settings.chat_expiry_hours)
        meeting.status = "chat_open"
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        self.events.publish("core.chat.unlocked", {"meeting_id": meeting.id})
        return meeting

    def send_chat(self, db: Session, meeting: Meeting, user: User, text: str) -> ChatMessage:
        self.ensure_member(meeting, user)
        if meeting.status == "aborted":
            raise HTTPException(status_code=403, detail="Meeting aborted")
        if not meeting.chat_unlocked or not meeting.chat_expires_at:
            raise HTTPException(status_code=403, detail="Chat is locked")
        if meeting.chat_expires_at < utcnow():
            raise HTTPException(status_code=410, detail="Chat expired")

        count = db.scalar(select(func.count(ChatMessage.id)).where(ChatMessage.meeting_id == meeting.id)) or 0
        if count >= self.settings.chat_message_limit:
            raise HTTPException(status_code=429, detail="Chat limit reached")

        message = ChatMessage(meeting_id=meeting.id, sender_user_id=user.id, text=text)
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    def list_messages(self, db: Session, meeting: Meeting, user: User) -> list[ChatMessage]:
        self.ensure_member(meeting, user)
        if meeting.status == "aborted":
            raise HTTPException(status_code=403, detail="Meeting aborted")
        return db.scalars(select(ChatMessage).where(ChatMessage.meeting_id == meeting.id).order_by(ChatMessage.created_at.asc())).all()

    def create_safety_event(
        self,
        db: Session,
        user: User,
        event_type: str,
        reason: Optional[str] = None,
        meeting: Optional[Meeting] = None,
        details: Optional[dict] = None,
    ) -> SafetyEvent:
        event = SafetyEvent(
            user_id=user.id,
            meeting_id=meeting.id if meeting else None,
            event_type=event_type,
            reason=reason,
            details=details or {},
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        self.events.publish("core.safety.triggered", {"meeting_id": event.meeting_id, "user_id": user.id, "event_type": event_type})
        return event

    def panic(self, db: Session, user: User, meeting: Optional[Meeting], reason: Optional[str]) -> SafetyEvent:
        self.stop_radar(db, user)
        if meeting:
            self.abort(db, meeting, user, reason or "panic")
        return self.create_safety_event(db, user, "panic", reason, meeting)

    def create_safety_alarm_draft(
        self,
        db: Session,
        user: User,
        meeting: Optional[Meeting],
        reason: Optional[str],
        lat: Optional[float],
        lng: Optional[float],
        location_recorded_at: Optional[datetime],
    ) -> SafetyAlarm:
        primary_contact = db.scalar(
            select(SafetyCircleContact).where(
                SafetyCircleContact.user_id == user.id,
                SafetyCircleContact.is_primary.is_(True),
                SafetyCircleContact.status == "active",
            )
        )
        if primary_contact is None:
            raise HTTPException(status_code=409, detail="Primary safety contact required")
        if primary_contact.contact_channel != "phone" or not primary_contact.phone_number:
            raise HTTPException(status_code=409, detail="Primary safety contact has no supported delivery channel")

        details = {
            "reason": reason or "",
            "contact_channel": primary_contact.contact_channel,
            "contact_phone_number": primary_contact.phone_number,
            "meeting_status": meeting.status if meeting else None,
        }
        alarm = SafetyAlarm(
            user_id=user.id,
            primary_contact_id=primary_contact.id,
            meeting_id=meeting.id if meeting else None,
            location_lat=lat,
            location_lng=lng,
            location_recorded_at=location_recorded_at or utcnow() if lat is not None and lng is not None else None,
            status="draft_countdown",
            details=details,
        )
        db.add(alarm)
        db.commit()
        db.refresh(alarm)
        self.create_safety_event(
            db,
            user,
            "alarm_draft_created",
            reason,
            meeting,
            {
                "alarm_id": alarm.id,
                "primary_contact_id": primary_contact.id,
                "has_location": lat is not None and lng is not None,
            },
        )
        return alarm

    def cancel_safety_alarm(self, db: Session, alarm_id: str, user: User, reason: Optional[str]) -> SafetyAlarm:
        alarm = db.get(SafetyAlarm, alarm_id)
        if alarm is None or alarm.user_id != user.id:
            raise HTTPException(status_code=404, detail="Safety alarm not found")
        if alarm.status not in {"draft_countdown"}:
            raise HTTPException(status_code=409, detail="Safety alarm can no longer be cancelled")

        alarm.status = "cancelled"
        alarm.details = {
            **(alarm.details or {}),
            "cancel_reason": reason or "",
            "cancelled_at": utcnow().isoformat(),
        }
        db.add(alarm)
        db.commit()
        db.refresh(alarm)
        return alarm

    def deliver_safety_alarm(self, db: Session, alarm_id: str, user: User) -> SafetyAlarm:
        alarm = db.get(SafetyAlarm, alarm_id)
        if alarm is None or alarm.user_id != user.id:
            raise HTTPException(status_code=404, detail="Safety alarm not found")
        if alarm.status == "cancelled":
            raise HTTPException(status_code=409, detail="Safety alarm was cancelled")
        if alarm.status in {"delivered", "delivery_failed", "pending_delivery"}:
            raise HTTPException(status_code=409, detail="Safety alarm delivery already started")
        if alarm.status != "draft_countdown":
            raise HTTPException(status_code=409, detail="Safety alarm is not ready for delivery")

        primary_contact = db.get(SafetyCircleContact, alarm.primary_contact_id)
        if primary_contact is None or primary_contact.user_id != user.id or primary_contact.status != "active":
            raise HTTPException(status_code=409, detail="Primary safety contact required")
        if primary_contact.contact_channel != "phone" or not primary_contact.phone_number:
            raise HTTPException(status_code=409, detail="Primary safety contact has no supported delivery channel")

        meeting = db.get(Meeting, alarm.meeting_id) if alarm.meeting_id else None
        lat = alarm.location_lat
        lng = alarm.location_lng

        alarm.status = "pending_delivery"
        alarm.details = {
            **(alarm.details or {}),
            "delivery_started_at": utcnow().isoformat(),
        }
        db.add(alarm)
        db.commit()
        db.refresh(alarm)

        sms_result = self.sms_service.send_message(
            primary_contact.phone_number,
            self._build_safety_alarm_message(user, primary_contact, meeting, lat, lng),
            self.settings,
        )
        alarm.status = "delivered" if sms_result.delivery_status == "sent" else "delivery_failed"
        alarm.details = {
            **(alarm.details or {}),
            "delivery_status": sms_result.delivery_status,
            "provider_message_id": sms_result.provider_message_id,
            "delivery_error": sms_result.error_detail,
        }
        db.add(alarm)
        db.commit()
        db.refresh(alarm)

        self.create_safety_event(
            db,
            user,
            "alarm_created",
            (alarm.details or {}).get("reason"),
            meeting,
            {
                "alarm_id": alarm.id,
                "primary_contact_id": primary_contact.id,
                "has_location": lat is not None and lng is not None,
            },
        )
        return alarm

    def _build_safety_alarm_message(
        self,
        user: User,
        contact: SafetyCircleContact,
        meeting: Optional[Meeting],
        lat: Optional[float],
        lng: Optional[float],
    ) -> str:
        parts = [
            f"Sicherheitsalarm von Catch Your Partner: {user.name} hat einen Safety-Alarm ausgeloest."
        ]
        if meeting:
            parts.append(f"Meeting-Bezug: {meeting.spot_name}.")
        if lat is not None and lng is not None:
            parts.append(f"Letzter Standort: https://maps.apple.com/?ll={lat},{lng}")
        parts.append(f"Kontaktkanal fuer Rueckfrage: {user.phone_number or user.email}")
        return " ".join(parts)

    def abort(self, db: Session, meeting: Meeting, user: User, reason: Optional[str]) -> Meeting:
        self.ensure_member(meeting, user)
        meeting.status = "aborted"
        meeting.chat_unlocked = False
        meeting.chat_locked_reason = reason or "aborted"
        meeting.chat_expires_at = None
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        self.create_safety_event(db, user, "abort", reason, meeting)
        return meeting
