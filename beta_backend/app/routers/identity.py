from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_admin
from app.models.db import IdentityProfile
from app.models.schemas import (
    EntitlementRequest,
    IdentityProfileResponse,
    IdentityVerificationResponse,
    LookalikeSearchRequest,
    LookalikeStatusResponse,
)

router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("/status")
def identity_status(request: Request):
    request.app.state.module_service.require_enabled("identity")
    capabilities = request.app.state.module_service.capabilities()
    identity_module = next(module for module in capabilities["modules"] if module["key"] == "identity")
    return {
        "module": "identity",
        "status": "active",
        "engine_available": request.app.state.identity_service.analyzer.available(),
        "lookalike": identity_module.get("lookalike", False),
        "message": "Identity module active. Raw images are not persisted.",
    }


@router.post("/enroll", response_model=IdentityProfileResponse, status_code=status.HTTP_201_CREATED)
async def enroll(
    request: Request,
    consent: bool = Form(...),
    selfie: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    request.app.state.module_service.require_enabled("identity")
    profile = await request.app.state.identity_service.enroll(db, current_user, selfie, consent)
    return request.app.state.identity_service.profile_response(profile)


@router.post("/verify", response_model=IdentityVerificationResponse)
async def verify(
    request: Request,
    consent: bool = Form(...),
    selfie: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    request.app.state.module_service.require_enabled("identity")
    attempt = await request.app.state.identity_service.verify(db, current_user, selfie, consent)
    return request.app.state.identity_service.verification_response(attempt)


@router.get("/profile", response_model=IdentityProfileResponse)
def profile(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    request.app.state.module_service.require_enabled("identity")
    profile = db.query(IdentityProfile).filter(IdentityProfile.user_id == current_user.id).first()
    if not profile:
        return {
            "id": "",
            "user_id": current_user.id,
            "enrolled": False,
            "anti_fake_status": "missing",
            "reason_codes": [],
            "quality_score": 0.0,
            "face_count": 0,
            "enrolled_at": current_user.created_at,
        }
    return request.app.state.identity_service.profile_response(profile)


@router.get("/lookalike/status", response_model=LookalikeStatusResponse)
def lookalike_status(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    request.app.state.module_service.require_enabled("identity")
    return request.app.state.identity_service.entitlement_status(db, current_user)


@router.post("/lookalike/search")
def lookalike_search(
    payload: LookalikeSearchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    request.app.state.module_service.require_enabled("identity")
    matches = request.app.state.identity_service.search_lookalikes(db, current_user, payload.limit)
    request.app.state.events.publish("identity.lookalike.searched", {"user_id": current_user.id, "limit": payload.limit, "count": len(matches)})
    return {"matches": matches}


@router.post("/admin/entitlements/set")
def set_entitlement(
    payload: EntitlementRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    entitlement = request.app.state.identity_service.set_entitlement(
        db=db,
        user_id=payload.user_id,
        is_premium=payload.is_premium,
        plan=payload.plan,
        expires_at=payload.expires_at,
    )
    return request.app.state.identity_service.entitlement_response(entitlement)
