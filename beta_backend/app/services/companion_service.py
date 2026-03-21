from datetime import datetime
import math
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import EventBus
from app.models.db import CompanionEvent, CompanionState, User


def utcnow() -> datetime:
    return datetime.utcnow()


class CompanionService:
    DEFAULT_MESSAGE = "Good chemistry is nice. Safe follow-through is hotter."

    XP_RULES = {
        "radar_started": 0,
        "radar_stopped": 0,
        "meeting_created": 0,
        "navigation_started": 0,
        "checkin": 20,
        "ok": 30,
        "chat_unlocked": 50,
        "share_location": 10,
        "abort_meeting": -10,
        "panic": 0,
    }

    EVENT_MOOD = {
        "radar_started": "curious",
        "radar_stopped": "calm",
        "meeting_created": "excited",
        "navigation_started": "focused",
        "checkin": "proud",
        "ok": "supportive",
        "chat_unlocked": "celebrating",
        "share_location": "protective",
        "abort_meeting": "careful",
        "panic": "serious",
    }

    EVENT_MESSAGE = {
        "radar_started": "Radar on. Main character energy, but with better safety instincts.",
        "radar_stopped": "Radar off. Rest is a tactic, not a retreat.",
        "meeting_created": "Meeting locked. Intent beats endless texting every time.",
        "navigation_started": "You are in motion now. Calm beats chaotic.",
        "checkin": "Check-in landed. Real-world follow-through always scores.",
        "ok": "Mutual OK. Trust just got louder than hype.",
        "chat_unlocked": "Chat unlocked. Real meetup confirmed. That is premium behavior.",
        "share_location": "Location shared. Smart is attractive.",
        "abort_meeting": "You protected your peace. That still counts as a win.",
        "panic": "Serious mode: stop the flow, get to a safe place, and contact a trusted person now.",
    }

    def __init__(self, events: EventBus) -> None:
        self.events = events

    def level_for_xp(self, xp: int) -> int:
        return math.floor(math.sqrt(max(xp, 0) / 100)) + 1

    def next_level_xp(self, level: int) -> int:
        return (level**2) * 100

    def get_or_create_state(self, db: Session, user: User) -> CompanionState:
        state = db.get(CompanionState, user.id)
        if state:
            return state

        state = CompanionState(user_id=user.id, last_message=self.DEFAULT_MESSAGE)
        db.add(state)
        db.commit()
        db.refresh(state)
        return state

    def state_response(self, state: CompanionState) -> dict:
        return {
            "user_id": state.user_id,
            "level": state.level,
            "xp": state.xp,
            "streak": state.streak,
            "mood": state.mood,
            "last_message": state.last_message,
            "next_level_xp": self.next_level_xp(state.level),
            "updated_at": state.updated_at,
        }

    def event_reward(self, event_type: str) -> int:
        return self.XP_RULES.get(event_type, 0)

    def apply_event(self, db: Session, user: User, event_type: str, meta: Optional[dict] = None) -> dict:
        state = self.get_or_create_state(db, user)
        previous_level = state.level
        xp_delta = self.event_reward(event_type)
        state.xp = max(0, state.xp + xp_delta)
        state.level = self.level_for_xp(state.xp)
        state.mood = self.EVENT_MOOD.get(event_type, state.mood)
        state.last_message = self.EVENT_MESSAGE.get(event_type, state.last_message)

        if event_type == "panic":
            state.streak = 0
        elif xp_delta > 0:
            state.streak += 1
        elif event_type == "abort_meeting":
            state.streak = max(0, state.streak - 1)

        entry = CompanionEvent(user_id=user.id, event_type=event_type, meta_json=meta or {}, xp_delta=xp_delta)
        db.add(entry)
        db.add(state)
        db.commit()
        db.refresh(state)
        db.refresh(entry)
        leveled_up = state.level > previous_level
        self.events.publish(
            "companion.event.recorded",
            {"user_id": user.id, "event_type": event_type, "xp_delta": xp_delta, "level": state.level},
        )
        return {
            "state": self.state_response(state),
            "reward_delta": xp_delta,
            "leveled_up": leveled_up,
            "message": state.last_message,
        }

    def say(self, db: Session, user: User, text: str) -> dict:
        state = self.get_or_create_state(db, user)
        lowered = text.strip().lower()

        if any(word in lowered for word in ["panic", "unsafe", "scared", "help"]):
            reply = "Serious mode: pause the meetup, use the safety tools, and call a trusted contact if you need backup."
            mood = "serious"
            suggested_action = "use_safety_tools"
        elif "xp" in lowered or "level" in lowered or "progress" in lowered:
            reply = f"You are level {state.level} with {state.xp} XP. Your next milestone unlocks at {self.next_level_xp(state.level)} XP."
            mood = "hyped"
            suggested_action = "complete_checkin"
        elif any(word in lowered for word in ["hello", "hi", "hey"]):
            reply = "I track momentum, trust, and smart choices. Start radar and let me cook."
            mood = "curious"
            suggested_action = "start_radar"
        elif state.mood == "celebrating":
            reply = "You turned chemistry into reality. Try not to act too legendary about it."
            mood = "hyped"
            suggested_action = "send_ok"
        else:
            reply = "The hottest flex here is still safe follow-through. Do the next real step."
            mood = state.mood
            suggested_action = "complete_checkin"

        state.mood = mood
        state.last_message = reply
        db.add(state)
        db.commit()
        db.refresh(state)
        return {"reply": reply, "mood": state.mood, "suggested_action": suggested_action}

    def recent_events(self, db: Session, user: User, limit: int = 10) -> list[CompanionEvent]:
        return db.scalars(
            select(CompanionEvent)
            .where(CompanionEvent.user_id == user.id)
            .order_by(CompanionEvent.created_at.desc())
            .limit(limit)
        ).all()

    def reset(self, db: Session, user: User) -> dict:
        state = self.get_or_create_state(db, user)
        db.query(CompanionEvent).filter(CompanionEvent.user_id == user.id).delete()
        state.level = 1
        state.xp = 0
        state.streak = 0
        state.mood = "calm"
        state.last_message = self.DEFAULT_MESSAGE
        db.add(state)
        db.commit()
        db.refresh(state)
        return self.state_response(state)
