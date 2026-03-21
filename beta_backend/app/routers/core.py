from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.db import Meeting, RadarSession, SafetyAlarm, SafetyEvent
from app.models.schemas import (
    ChatSendRequest,
    ChatUnlockRequest,
    CheckInRequest,
    MatchingProfileResponse,
    MatchingProfileUpsertRequest,
    NearbyCandidatesEnvelope,
    MeetingAcceptRequest,
    MeetingStartRequest,
    NavigationStartRequest,
    OkSignalRequest,
    RadarStartRequest,
    SafetyAlarmRequest,
    SafetyAlarmResponse,
    SafetyRequest,
)

router = APIRouter(prefix="/core", tags=["core"])


def meeting_to_dict(meeting: Meeting) -> dict:
    accepted_by = meeting.accepted_by or []
    arrived_by = meeting.arrived_by or []
    ok_by = meeting.ok_by or []
    return {
        "id": meeting.id,
        "initiator_id": meeting.initiator_id,
        "participant_id": meeting.participant_id,
        "user_a_id": meeting.initiator_id,
        "user_b_id": meeting.participant_id,
        "spot_name": meeting.spot_name,
        "spot_lat": meeting.spot_lat,
        "spot_lng": meeting.spot_lng,
        "status": meeting.status,
        "accepted_by": accepted_by,
        "accepted_by_user_a": meeting.initiator_id in accepted_by,
        "accepted_by_user_b": meeting.participant_id in accepted_by,
        "fully_accepted": meeting.initiator_id in accepted_by and meeting.participant_id in accepted_by,
        "arrived_by": arrived_by,
        "arrived_by_user_a": meeting.initiator_id in arrived_by,
        "arrived_by_user_b": meeting.participant_id in arrived_by,
        "both_arrived": meeting.initiator_id in arrived_by and meeting.participant_id in arrived_by,
        "ok_by": ok_by,
        "ok_by_user_a": meeting.initiator_id in ok_by,
        "ok_by_user_b": meeting.participant_id in ok_by,
        "both_ok": meeting.initiator_id in ok_by and meeting.participant_id in ok_by,
        "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
        "updated_at": meeting.updated_at.isoformat() if meeting.updated_at else None,
        "navigation_started_by": meeting.navigation_started_by or [],
        "checkins": meeting.checkins or {},
        "ok_signals": meeting.ok_signals or {},
        "chat_unlocked": meeting.chat_unlocked,
        "chat_locked_reason": meeting.chat_locked_reason,
        "chat_expires_at": meeting.chat_expires_at.isoformat() if meeting.chat_expires_at else None,
    }


def alarm_to_dict(alarm: SafetyAlarm) -> dict:
    return {
        "id": alarm.id,
        "user_id": alarm.user_id,
        "primary_contact_id": alarm.primary_contact_id,
        "meeting_id": alarm.meeting_id,
        "status": alarm.status,
        "location": (
            {
                "lat": alarm.location_lat,
                "lng": alarm.location_lng,
                "recorded_at": alarm.location_recorded_at.isoformat() if alarm.location_recorded_at else None,
            }
            if alarm.location_lat is not None and alarm.location_lng is not None
            else None
        ),
        "details": alarm.details or {},
        "created_at": alarm.created_at,
        "updated_at": alarm.updated_at,
    }


@router.post("/radar/start", status_code=status.HTTP_201_CREATED)
def radar_start(payload: RadarStartRequest, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    radar = request.app.state.core_service.start_radar(db, current_user, payload.lat, payload.lng, payload.zone_tag, payload.safe_zones)
    return {"radar_session": {"id": radar.id, "expires_at": radar.expires_at.isoformat(), "active": radar.active}}


@router.post("/radar/stop")
def radar_stop(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    request.app.state.core_service.stop_radar(db, current_user)
    return {"ok": True}


@router.get("/radar")
def radar_results(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return {"results": request.app.state.core_service.radar_results(db, current_user)}


@router.put("/matching/profile", response_model=MatchingProfileResponse)
def matching_profile_upsert(
    payload: MatchingProfileUpsertRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    profile = request.app.state.core_service.upsert_matching_profile(db, current_user, payload)
    return request.app.state.core_service.matching_profile_to_dict(profile)


@router.get("/matching/profile", response_model=MatchingProfileResponse)
def matching_profile_get(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    profile = request.app.state.core_service.get_matching_profile(db, current_user)
    return request.app.state.core_service.matching_profile_to_dict(profile)


@router.get("/matching/candidates", response_model=NearbyCandidatesEnvelope)
def matching_candidates(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return request.app.state.core_service.nearby_matching_candidates(db, current_user)


@router.post("/meeting/start", status_code=status.HTTP_201_CREATED)
def meeting_start(payload: MeetingStartRequest, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.create_meeting(
        db,
        current_user,
        payload.target_user_id,
        payload.spot_name,
        payload.spot_lat,
        payload.spot_lng,
    )
    return {"meeting": meeting_to_dict(meeting)}


@router.get("/meeting/with/{other_user_id}")
def meeting_with_user(other_user_id: str, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.get_pair_meeting(db, current_user, other_user_id)
    return {"meeting": meeting_to_dict(meeting)}


@router.post("/meeting/accept")
def meeting_accept(payload: MeetingAcceptRequest, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.get_meeting(db, payload.meeting_id)
    meeting = request.app.state.core_service.accept_meeting(db, meeting, current_user)
    return {"meeting": meeting_to_dict(meeting)}


@router.post("/navigation/start")
def navigation_start(payload: NavigationStartRequest, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.get_meeting(db, payload.meeting_id)
    meeting = request.app.state.core_service.start_navigation(db, meeting, current_user)
    return {"meeting": meeting_to_dict(meeting)}


@router.post("/check-in")
def check_in(payload: CheckInRequest, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.get_meeting(db, payload.meeting_id)
    meeting = request.app.state.core_service.check_in(db, meeting, current_user, payload.lat, payload.lng)
    return {"meeting": meeting_to_dict(meeting)}


@router.post("/ok")
def ok_signal(payload: OkSignalRequest, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.get_meeting(db, payload.meeting_id)
    meeting = request.app.state.core_service.signal_ok(db, meeting, current_user, payload.signal)
    return {"meeting": meeting_to_dict(meeting)}


@router.post("/chat/unlock")
def chat_unlock(payload: ChatUnlockRequest, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.get_meeting(db, payload.meeting_id)
    meeting = request.app.state.core_service.unlock_chat(db, meeting, current_user)
    return {"meeting": meeting_to_dict(meeting)}


@router.post("/chat/send", status_code=status.HTTP_201_CREATED)
def chat_send(payload: ChatSendRequest, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.get_meeting(db, payload.meeting_id)
    message = request.app.state.core_service.send_chat(db, meeting, current_user, payload.text)
    return {"message": {"id": message.id, "meeting_id": message.meeting_id, "sender_user_id": message.sender_user_id, "text": message.text}}


@router.get("/chat/history/{meeting_id}")
def chat_history(meeting_id: str, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.get_meeting(db, meeting_id)
    messages = request.app.state.core_service.list_messages(db, meeting, current_user)
    return {
        "messages": [
            {"id": message.id, "sender_user_id": message.sender_user_id, "text": message.text, "created_at": message.created_at.isoformat()}
            for message in messages
        ]
    }


@router.post("/safety/panic")
def panic(payload: SafetyRequest, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.get_meeting(db, payload.meeting_id) if payload.meeting_id else None
    event = request.app.state.core_service.panic(db, current_user, meeting, payload.reason)
    return {"event": {"id": event.id, "event_type": event.event_type, "reason": event.reason}}


@router.post("/safety/alarm", response_model=SafetyAlarmResponse, status_code=status.HTTP_201_CREATED)
def safety_alarm(payload: SafetyAlarmRequest, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.get_meeting(db, payload.meeting_id) if payload.meeting_id else None
    if meeting:
        request.app.state.core_service.ensure_member(meeting, current_user)
    alarm = request.app.state.core_service.create_safety_alarm_draft(
        db,
        current_user,
        meeting,
        payload.reason,
        payload.lat,
        payload.lng,
        payload.location_recorded_at,
    )
    return alarm_to_dict(alarm)


@router.post("/safety/alarm/{alarm_id}/deliver", response_model=SafetyAlarmResponse)
def safety_alarm_deliver(alarm_id: str, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    alarm = request.app.state.core_service.deliver_safety_alarm(db, alarm_id, current_user)
    return alarm_to_dict(alarm)


@router.post("/safety/alarm/{alarm_id}/cancel", response_model=SafetyAlarmResponse)
def safety_alarm_cancel(
    alarm_id: str,
    payload: SafetyRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    alarm = request.app.state.core_service.cancel_safety_alarm(db, alarm_id, current_user, payload.reason)
    return alarm_to_dict(alarm)


@router.post("/safety/abort")
def abort(payload: SafetyRequest, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.get_meeting(db, payload.meeting_id) if payload.meeting_id else None
    if not meeting:
        raise HTTPException(status_code=400, detail="meeting_id is required")
    meeting = request.app.state.core_service.abort(db, meeting, current_user, payload.reason)
    return {"meeting": meeting_to_dict(meeting)}


@router.get("/meetings/{meeting_id}")
def meeting_detail(meeting_id: str, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    meeting = request.app.state.core_service.get_meeting(db, meeting_id)
    request.app.state.core_service.ensure_member(meeting, current_user)
    return {"meeting": meeting_to_dict(meeting)}


@router.get("/insights")
def insights(db: Session = Depends(get_db)):
    return {
        "active_radar_sessions": db.query(RadarSession).filter(RadarSession.active.is_(True)).count(),
        "meetings": db.query(Meeting).count(),
        "safety_events": db.query(SafetyEvent).count(),
    }
