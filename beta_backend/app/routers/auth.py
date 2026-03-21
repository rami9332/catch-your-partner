from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.schemas import (
    AuthResponse,
    LoginRequest,
    PhoneVerificationResponse,
    PhoneVerificationStartRequest,
    PhoneVerificationVerifyRequest,
    RegisterRequest,
    SafetyCircleContactCreateRequest,
    SafetyCircleContactResponse,
    SafetyCircleContactUpdateRequest,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService()


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    try:
        user, token = auth_service.register(db, payload, request.app.state.settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"access_token": token, "user": user}


@router.post("/signup", response_model=AuthResponse, status_code=201)
def signup_alias(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    return register(payload, request, db)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    auth_result = auth_service.login(db, payload.email, payload.password, request.app.state.settings)
    if not auth_result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user, token = auth_result
    return {"access_token": token, "user": user}


@router.get("/me", response_model=UserResponse)
def me(current_user=Depends(get_current_user)):
    return current_user


@router.post("/phone/request", response_model=PhoneVerificationResponse)
def request_phone_verification(
    payload: PhoneVerificationStartRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        user, challenge, verification_code = auth_service.start_phone_verification(
            db,
            current_user,
            payload.phone_number,
            request.app.state.settings,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_400_BAD_REQUEST
        if detail == "Phone verification SMS could not be sent":
            status_code = status.HTTP_502_BAD_GATEWAY
        elif detail == "Phone verification request rate limit exceeded":
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
        elif detail == "Phone verification temporarily locked":
            status_code = status.HTTP_423_LOCKED
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return {
        "phone_number": user.phone_number,
        "phone_verification_status": user.phone_verification_status,
        "phone_verification_requested_at": user.phone_verification_requested_at,
        "phone_verified_at": user.phone_verified_at,
        "phone_verification_locked_until": user.phone_verification_locked_until,
        "challenge_expires_at": challenge.expires_at,
        "delivery_status": challenge.delivery_status,
        "attempts_remaining": challenge.attempts_remaining,
        "code_preview": verification_code if challenge.delivery_status == "provider_missing" else None,
        "user": user,
    }


@router.post("/phone/verify", response_model=PhoneVerificationResponse)
def verify_phone_code(
    payload: PhoneVerificationVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        user, challenge = auth_service.verify_phone_code(
            db,
            current_user,
            payload.code,
            request.app.state.settings,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_400_BAD_REQUEST
        if detail == "Invalid phone verification code":
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        elif detail == "Phone verification temporarily locked":
            status_code = status.HTTP_423_LOCKED
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return {
        "phone_number": user.phone_number,
        "phone_verification_status": user.phone_verification_status,
        "phone_verification_requested_at": user.phone_verification_requested_at,
        "phone_verified_at": user.phone_verified_at,
        "phone_verification_locked_until": user.phone_verification_locked_until,
        "challenge_expires_at": challenge.expires_at,
        "delivery_status": challenge.delivery_status,
        "attempts_remaining": challenge.attempts_remaining,
        "code_preview": None,
        "user": user,
    }


@router.post("/profile-photo", response_model=UserResponse)
async def upload_profile_photo(
    request: Request,
    upload: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await auth_service.upload_profile_photo(db, current_user, upload, request.app.state.settings)


@router.delete("/profile-photo", response_model=UserResponse)
def remove_profile_photo(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return auth_service.remove_profile_photo(db, current_user, request.app.state.settings)


@router.get("/safety-circle", response_model=list[SafetyCircleContactResponse])
def list_safety_circle_contacts(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return auth_service.list_safety_circle_contacts(db, current_user)


@router.post("/safety-circle", response_model=SafetyCircleContactResponse, status_code=status.HTTP_201_CREATED)
def create_safety_circle_contact(
    payload: SafetyCircleContactCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return auth_service.create_safety_circle_contact(
            db,
            current_user,
            payload.name,
            payload.relation,
            payload.contact_channel,
            payload.phone_number,
            payload.is_primary,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/safety-circle/{contact_id}", response_model=SafetyCircleContactResponse)
def update_safety_circle_contact(
    contact_id: str,
    payload: SafetyCircleContactUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        return auth_service.update_safety_circle_contact(
            db,
            current_user,
            contact_id,
            payload.name,
            payload.relation,
            payload.contact_channel,
            payload.phone_number,
            payload.is_primary,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail == "Safety contact not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.delete("/safety-circle/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_safety_circle_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        auth_service.delete_safety_circle_contact(db, current_user, contact_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if detail == "Safety contact not found" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=detail) from exc
