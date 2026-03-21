from datetime import timedelta
import hashlib
from io import BytesIO
from pathlib import Path
import re
import secrets
from typing import Optional, Tuple
import uuid

from fastapi import HTTPException, UploadFile
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password, verify_password
from app.config import Settings
from app.models.db import PhoneVerificationChallenge, SafetyCircleContact, User, utcnow
from app.models.schemas import RegisterRequest
from app.services.sms_service import SmsService


class AuthService:
    def __init__(self) -> None:
        self.sms_service = SmsService()

    def register(self, db: Session, payload: RegisterRequest, settings: Settings) -> tuple[User, str]:
        existing = db.scalar(select(User).where(User.email == payload.email))
        if existing:
            raise ValueError("Email already registered")

        role = "admin" if payload.email == settings.default_admin_email else "user"
        user = User(
            email=str(payload.email),
            password_hash=hash_password(payload.password),
            name=payload.name,
            role=role,
            mode=payload.mode,
            premium_enabled=payload.mode == "premium",
            astro_sign=payload.astro_sign,
            interests=payload.interests,
            phone_verification_status="not_started",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.id, user.role, settings)
        return user, token

    def login(self, db: Session, email: str, password: str, settings: Settings) -> Optional[Tuple[User, str]]:
        user = db.scalar(select(User).where(User.email == str(email)))
        if not user or not verify_password(password, user.password_hash):
            return None
        token = create_access_token(user.id, user.role, settings)
        return user, token

    def start_phone_verification(
        self,
        db: Session,
        user: User,
        phone_number: str,
        settings: Settings,
    ) -> tuple[User, PhoneVerificationChallenge, Optional[str]]:
        normalized_phone = self._normalize_phone_number(phone_number)
        now = utcnow()
        if user.phone_verification_locked_until and user.phone_verification_locked_until > now:
            raise ValueError("Phone verification temporarily locked")

        existing_owner = db.scalar(
            select(User).where(
                User.phone_number == normalized_phone,
                User.id != user.id,
                User.phone_verification_status == "verified",
            )
        )
        if existing_owner:
            raise ValueError("Phone number already verified by another account")

        window_started_at = now - timedelta(minutes=settings.phone_verification_request_window_minutes)
        recent_request_count = len(
            db.scalars(
                select(PhoneVerificationChallenge.id).where(
                    PhoneVerificationChallenge.user_id == user.id,
                    PhoneVerificationChallenge.created_at >= window_started_at,
                )
            ).all()
        )
        if recent_request_count >= settings.phone_verification_request_limit:
            raise ValueError("Phone verification request rate limit exceeded")

        active_challenges = db.scalars(
            select(PhoneVerificationChallenge).where(
                PhoneVerificationChallenge.user_id == user.id,
                PhoneVerificationChallenge.consumed_at.is_(None),
            )
        ).all()
        for active in active_challenges:
            active.consumed_at = now
            db.add(active)

        verification_code = self._generate_phone_code()
        challenge = PhoneVerificationChallenge(
            user_id=user.id,
            phone_number=normalized_phone,
            code_hash=self._hash_phone_code(user.id, normalized_phone, verification_code, settings),
            delivery_status="pending",
            attempts_remaining=5,
            expires_at=now + timedelta(minutes=10),
        )

        user.phone_number = normalized_phone
        user.phone_verification_status = "pending"
        user.phone_verification_requested_at = now
        user.phone_verified_at = None

        send_result = self.sms_service.send_verification_code(normalized_phone, verification_code, settings)
        challenge.delivery_status = send_result.delivery_status

        if send_result.delivery_status == "failed":
            db.add(challenge)
            db.commit()
            db.refresh(challenge)
            raise ValueError("Phone verification SMS could not be sent")

        db.add(challenge)
        db.commit()
        db.refresh(user)
        db.refresh(challenge)
        return user, challenge, verification_code if send_result.delivery_status == "provider_missing" else None

    def verify_phone_code(
        self,
        db: Session,
        user: User,
        code: str,
        settings: Settings,
    ) -> tuple[User, PhoneVerificationChallenge]:
        challenge = db.scalar(
            select(PhoneVerificationChallenge)
            .where(
                PhoneVerificationChallenge.user_id == user.id,
                PhoneVerificationChallenge.consumed_at.is_(None),
            )
            .order_by(PhoneVerificationChallenge.created_at.desc())
        )
        if user.phone_verification_locked_until and user.phone_verification_locked_until > utcnow():
            raise ValueError("Phone verification temporarily locked")
        if not challenge:
            raise ValueError("No active phone verification challenge")

        now = utcnow()
        if challenge.expires_at <= now:
            raise ValueError("Phone verification code expired")
        if challenge.attempts_remaining <= 0:
            raise ValueError("Phone verification attempts exhausted")

        normalized_code = re.sub(r"\s+", "", code)
        expected_hash = self._hash_phone_code(user.id, challenge.phone_number, normalized_code, settings)
        if not secrets.compare_digest(expected_hash, challenge.code_hash):
            challenge.attempts_remaining = max(0, challenge.attempts_remaining - 1)
            if challenge.attempts_remaining == 0:
                challenge.consumed_at = now
                user.phone_verification_locked_until = now + timedelta(minutes=settings.phone_verification_lock_minutes)
                db.add(user)
            db.add(challenge)
            db.commit()
            db.refresh(user)
            db.refresh(challenge)
            raise ValueError("Invalid phone verification code")

        challenge.consumed_at = now
        user.phone_number = challenge.phone_number
        user.phone_verification_status = "verified"
        user.phone_verified_at = now
        user.phone_verification_locked_until = None
        if not user.phone_verification_requested_at:
            user.phone_verification_requested_at = challenge.created_at

        db.add(challenge)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.refresh(challenge)
        return user, challenge

    async def upload_profile_photo(
        self,
        db: Session,
        user: User,
        upload: UploadFile,
        settings: Settings,
    ) -> User:
        if not upload.content_type or not upload.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="Only image uploads are supported")

        file_bytes = await upload.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded image is empty")
        if len(file_bytes) > settings.profile_photo_max_bytes:
            raise HTTPException(status_code=413, detail="Profile photo is too large")

        try:
            image = Image.open(BytesIO(file_bytes))
            image_format = (image.format or "").upper()
            width, height = image.size
            image.verify()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Uploaded image is invalid") from exc

        if image_format not in {"JPEG", "PNG", "WEBP"}:
            raise HTTPException(status_code=415, detail="Unsupported image format")
        if width < 120 or height < 120:
            raise HTTPException(status_code=400, detail="Profile photo is too small")

        extension = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[image_format]
        filename = f"{user.id}-{uuid.uuid4().hex}.{extension}"
        upload_dir = settings.profile_photo_upload_path
        file_path = upload_dir / filename
        file_path.write_bytes(file_bytes)

        previous_url = user.profile_photo_url or ""
        user.profile_photo_url = f"/media/profile-photos/{filename}"
        user.profile_photo_status = "pending_review"
        user.profile_photo_uploaded_at = utcnow()
        db.add(user)
        db.commit()
        db.refresh(user)

        if previous_url.startswith("/media/profile-photos/"):
            previous_path = upload_dir / Path(previous_url).name
            if previous_path.exists() and previous_path.name != filename:
                try:
                    previous_path.unlink()
                except OSError:
                    pass

        return user

    def remove_profile_photo(
        self,
        db: Session,
        user: User,
        settings: Settings,
    ) -> User:
        previous_url = user.profile_photo_url or ""
        user.profile_photo_url = None
        user.profile_photo_status = "not_started"
        user.profile_photo_uploaded_at = None
        db.add(user)
        db.commit()
        db.refresh(user)

        if previous_url.startswith("/media/profile-photos/"):
            previous_path = settings.profile_photo_upload_path / Path(previous_url).name
            if previous_path.exists():
                try:
                    previous_path.unlink()
                except OSError:
                    pass

        return user

    def list_safety_circle_contacts(self, db: Session, user: User) -> list[SafetyCircleContact]:
        contacts = db.scalars(
            select(SafetyCircleContact)
            .where(SafetyCircleContact.user_id == user.id)
            .order_by(SafetyCircleContact.is_primary.desc(), SafetyCircleContact.created_at.asc())
        ).all()
        return list(contacts)

    def create_safety_circle_contact(
        self,
        db: Session,
        user: User,
        name: str,
        relation: Optional[str],
        contact_channel: str,
        phone_number: Optional[str],
        is_primary: bool,
    ) -> SafetyCircleContact:
        normalized_channel = (contact_channel or "phone").strip().lower()
        if normalized_channel != "phone":
            raise ValueError("Unsupported contact channel")
        if not phone_number:
            raise ValueError("Safety contact phone number required")

        normalized_phone = self._normalize_phone_number(phone_number)
        existing_contacts = self.list_safety_circle_contacts(db, user)
        make_primary = is_primary or not existing_contacts
        if make_primary:
            self._clear_primary_safety_contact(db, user.id)

        contact = SafetyCircleContact(
            user_id=user.id,
            name=name.strip(),
            relation=relation.strip() if relation else None,
            contact_channel=normalized_channel,
            phone_number=normalized_phone,
            is_primary=make_primary,
            status="active",
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact

    def update_safety_circle_contact(
        self,
        db: Session,
        user: User,
        contact_id: str,
        name: Optional[str],
        relation: Optional[str],
        contact_channel: Optional[str],
        phone_number: Optional[str],
        is_primary: Optional[bool],
    ) -> SafetyCircleContact:
        contact = self._get_owned_safety_contact(db, user.id, contact_id)

        if name is not None:
            contact.name = name.strip()
        if relation is not None:
            contact.relation = relation.strip() or None
        if contact_channel is not None:
            normalized_channel = contact_channel.strip().lower()
            if normalized_channel != "phone":
                raise ValueError("Unsupported contact channel")
            contact.contact_channel = normalized_channel
        if phone_number is not None:
            contact.phone_number = self._normalize_phone_number(phone_number)
        if not contact.phone_number:
            raise ValueError("Safety contact phone number required")

        if is_primary is True:
            self._clear_primary_safety_contact(db, user.id, keep_contact_id=contact.id)
            contact.is_primary = True
        elif is_primary is False:
            other_primary = db.scalar(
                select(SafetyCircleContact).where(
                    SafetyCircleContact.user_id == user.id,
                    SafetyCircleContact.id != contact.id,
                    SafetyCircleContact.is_primary.is_(True),
                    SafetyCircleContact.status == "active",
                )
            )
            contact.is_primary = False
            if not other_primary:
                replacement = db.scalar(
                    select(SafetyCircleContact).where(
                        SafetyCircleContact.user_id == user.id,
                        SafetyCircleContact.id != contact.id,
                        SafetyCircleContact.status == "active",
                    )
                )
                if replacement:
                    replacement.is_primary = True
                    db.add(replacement)
                else:
                    contact.is_primary = True

        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact

    def delete_safety_circle_contact(self, db: Session, user: User, contact_id: str) -> None:
        contact = self._get_owned_safety_contact(db, user.id, contact_id)
        was_primary = bool(contact.is_primary)
        db.delete(contact)
        db.commit()

        if was_primary:
            replacement = db.scalar(
                select(SafetyCircleContact).where(
                    SafetyCircleContact.user_id == user.id,
                    SafetyCircleContact.status == "active",
                )
            )
            if replacement:
                replacement.is_primary = True
                db.add(replacement)
                db.commit()

    def _get_owned_safety_contact(self, db: Session, user_id: str, contact_id: str) -> SafetyCircleContact:
        contact = db.scalar(
            select(SafetyCircleContact).where(
                SafetyCircleContact.id == contact_id,
                SafetyCircleContact.user_id == user_id,
            )
        )
        if not contact:
            raise ValueError("Safety contact not found")
        return contact

    def _clear_primary_safety_contact(self, db: Session, user_id: str, keep_contact_id: Optional[str] = None) -> None:
        contacts = db.scalars(
            select(SafetyCircleContact).where(
                SafetyCircleContact.user_id == user_id,
                SafetyCircleContact.is_primary.is_(True),
            )
        ).all()
        for contact in contacts:
            if keep_contact_id and contact.id == keep_contact_id:
                continue
            contact.is_primary = False
            db.add(contact)

    def _normalize_phone_number(self, phone_number: str) -> str:
        cleaned = phone_number.strip()
        cleaned = re.sub(r"[^\d+]", "", cleaned)
        if cleaned.startswith("00"):
            cleaned = f"+{cleaned[2:]}"
        if cleaned.startswith("+"):
            digits_only = re.sub(r"\D", "", cleaned[1:])
            digits = f"+{digits_only}"
        else:
            digits = re.sub(r"\D", "", cleaned)

        digit_count = len(re.sub(r"\D", "", digits))
        if digit_count < 7 or digit_count > 15:
            raise ValueError("Invalid phone number")
        return digits

    def _generate_phone_code(self) -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    def _hash_phone_code(self, user_id: str, phone_number: str, code: str, settings: Settings) -> str:
        raw = f"{user_id}:{phone_number}:{code}:{settings.jwt_secret}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
