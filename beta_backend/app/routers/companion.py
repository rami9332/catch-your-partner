from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.schemas import (
    CompanionEventRequest,
    CompanionEventResponse,
    CompanionSayRequest,
    CompanionSayResponse,
    CompanionStateResponse,
)

router = APIRouter(prefix="/companion", tags=["companion"])


@router.get("/state", response_model=CompanionStateResponse)
def companion_state(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    request.app.state.module_service.require_enabled("companion")
    state = request.app.state.companion_service.get_or_create_state(db, current_user)
    return request.app.state.companion_service.state_response(state)


@router.post("/event", response_model=CompanionEventResponse)
def companion_event(
    payload: CompanionEventRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    request.app.state.module_service.require_enabled("companion")
    return request.app.state.companion_service.apply_event(db, current_user, payload.event_type, payload.meta)


@router.post("/say", response_model=CompanionSayResponse)
def companion_say(
    payload: CompanionSayRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    request.app.state.module_service.require_enabled("companion")
    return request.app.state.companion_service.say(db, current_user, payload.text)


@router.get("/tamagotchi")
def companion_tamagotchi(request: Request):
    request.app.state.module_service.require_enabled("companion")
    return {
        "module": "companion",
        "status": "placeholder",
        "message": "2D companion active. 3D avatar comes later.",
        "features": ["rewards", "levels", "coach"],
    }


@router.post("/debug/reset", response_model=CompanionStateResponse)
def companion_debug_reset(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    request.app.state.module_service.require_enabled("companion")
    if not request.app.state.settings.debug:
        return request.app.state.companion_service.state_response(
            request.app.state.companion_service.get_or_create_state(db, current_user)
        )
    return request.app.state.companion_service.reset(db, current_user)
