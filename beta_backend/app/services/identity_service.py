from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import List, Optional
import hashlib
import math

import numpy as np
from fastapi import HTTPException, UploadFile
from PIL import Image, ImageStat
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.events import EventBus
from app.models.db import Entitlement, IdentityProfile, IdentityVerificationAttempt, User

try:
    import face_recognition  # type: ignore
except Exception:  # pragma: no cover
    face_recognition = None


ANTI_FAKE_REASON_CODES = {"no_face", "multiple_faces", "low_quality", "spoof_suspected"}


@dataclass
class FaceAnalysis:
    embedding: List[float]
    face_count: int
    quality_score: float
    image_width: int
    image_height: int
    reason_codes: List[str]
    anti_fake_status: str
    confidence_hint: float = 0.0


class FaceAnalyzer:
    def available(self) -> bool:
        return face_recognition is not None

    def analyze(self, file_bytes: bytes) -> FaceAnalysis:
        image = Image.open(BytesIO(file_bytes))
        image = image.convert("RGB")
        width, height = image.size
        quality_score = self._quality_score(image)
        reason_codes: List[str] = []

        if width < 160 or height < 160:
            reason_codes.append("low_quality")
        if quality_score < 0.22:
            reason_codes.append("low_quality")
        if self._spoof_hint(image):
            reason_codes.append("spoof_suspected")

        if face_recognition is None:
            # Lightweight fallback for environments without the optional face engine.
            embedding = self._deterministic_embedding(file_bytes)
            anti_fake_status = "passed" if not reason_codes else "review_required"
            return FaceAnalysis(
                embedding=embedding,
                face_count=1,
                quality_score=quality_score,
                image_width=width,
                image_height=height,
                reason_codes=reason_codes,
                anti_fake_status=anti_fake_status,
                confidence_hint=0.72,
            )

        np_image = np.array(image)
        face_locations = face_recognition.face_locations(np_image)
        face_count = len(face_locations)

        if face_count == 0:
            reason_codes.append("no_face")
        elif face_count > 1:
            reason_codes.append("multiple_faces")

        encodings = face_recognition.face_encodings(np_image, face_locations)
        if not encodings:
            if "no_face" not in reason_codes:
                reason_codes.append("no_face")
            embedding: List[float] = []
        else:
            embedding = encodings[0].tolist()

        anti_fake_status = "passed" if not reason_codes else "review_required"
        return FaceAnalysis(
            embedding=embedding,
            face_count=face_count,
            quality_score=quality_score,
            image_width=width,
            image_height=height,
            reason_codes=sorted(set(code for code in reason_codes if code in ANTI_FAKE_REASON_CODES)),
            anti_fake_status=anti_fake_status,
            confidence_hint=0.9 if embedding else 0.0,
        )

    def _quality_score(self, image: Image.Image) -> float:
        grayscale = image.convert("L").resize((64, 64))
        pixels = np.asarray(grayscale, dtype=np.float32)
        contrast = float(np.std(pixels) / 64.0)
        brightness = float(np.mean(pixels) / 255.0)
        return max(0.0, min((contrast * 0.7) + (brightness * 0.3), 1.0))

    def _spoof_hint(self, image: Image.Image) -> bool:
        grayscale = image.convert("L").resize((64, 64))
        stat = ImageStat.Stat(grayscale)
        variance = stat.var[0] if stat.var else 0
        return variance < 40

    def _deterministic_embedding(self, file_bytes: bytes) -> List[float]:
        digest = hashlib.sha256(file_bytes).digest()
        values = []
        for index in range(0, 32, 2):
            chunk = int.from_bytes(digest[index:index + 2], "big")
            values.append((chunk / 65535.0) * 2 - 1)
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [round(value / norm, 6) for value in values]


class IdentityService:
    def __init__(self, events: EventBus, analyzer: Optional[FaceAnalyzer] = None) -> None:
        self.events = events
        self.analyzer = analyzer or FaceAnalyzer()

    async def read_upload(self, upload: UploadFile) -> bytes:
        if not upload.content_type or not upload.content_type.startswith("image/"):
            raise HTTPException(status_code=415, detail="Only image uploads are supported")
        file_bytes = await upload.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded image is empty")
        return file_bytes

    async def enroll(self, db: Session, user: User, upload: UploadFile, consent: bool) -> IdentityProfile:
        if not consent:
            raise HTTPException(status_code=400, detail="Consent required for identity enrollment")

        file_bytes = await self.read_upload(upload)
        analysis = self.analyzer.analyze(file_bytes)
        self._raise_if_invalid_analysis(analysis)

        profile = db.scalar(select(IdentityProfile).where(IdentityProfile.user_id == user.id))
        if profile is None:
            profile = IdentityProfile(user_id=user.id)
            db.add(profile)

        profile.face_embedding = analysis.embedding
        profile.quality_score = analysis.quality_score
        profile.image_width = analysis.image_width
        profile.image_height = analysis.image_height
        profile.face_count = analysis.face_count
        profile.anti_fake_status = analysis.anti_fake_status
        profile.anti_fake_reason_codes = analysis.reason_codes
        profile.provider = "face_recognition" if self.analyzer.available() else "lightweight_fallback"
        profile.last_verified_at = None
        db.commit()
        db.refresh(profile)
        self.events.publish("identity.enrolled", {"user_id": user.id})
        return profile

    async def verify(self, db: Session, user: User, upload: UploadFile, consent: bool) -> IdentityVerificationAttempt:
        if not consent:
            raise HTTPException(status_code=400, detail="Consent required for identity verification")

        profile = db.scalar(select(IdentityProfile).where(IdentityProfile.user_id == user.id))
        if profile is None or not profile.face_embedding:
            raise HTTPException(status_code=404, detail="Identity enrollment not found")

        file_bytes = await self.read_upload(upload)
        analysis = self.analyzer.analyze(file_bytes)

        if analysis.reason_codes:
            attempt = IdentityVerificationAttempt(
                user_id=user.id,
                status="rejected",
                reason_codes=analysis.reason_codes,
                confidence=0.0,
                quality_score=analysis.quality_score,
            )
            db.add(attempt)
            db.commit()
            db.refresh(attempt)
            return attempt

        confidence = self._compare_embeddings(profile.face_embedding, analysis.embedding)
        verified = confidence >= 0.84
        attempt = IdentityVerificationAttempt(
            user_id=user.id,
            status="verified" if verified else "mismatch",
            reason_codes=[] if verified else ["face_mismatch"],
            confidence=confidence,
            quality_score=analysis.quality_score,
        )
        db.add(attempt)
        if verified:
            profile.last_verified_at = datetime.utcnow()
        db.commit()
        db.refresh(attempt)
        self.events.publish("identity.verified", {"user_id": user.id, "verified": verified})
        return attempt

    def entitlement_status(self, db: Session, user: User) -> dict:
        entitlement = db.scalar(select(Entitlement).where(Entitlement.user_id == user.id))
        is_premium = self._is_premium(entitlement, user)
        return {
            "available": is_premium,
            "premium_required": not is_premium,
            "plan": entitlement.plan if entitlement else ("premium" if user.premium_enabled else "free"),
        }

    def set_entitlement(self, db: Session, user_id: str, is_premium: bool, plan: str, expires_at: Optional[datetime]) -> Entitlement:
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        entitlement = db.scalar(select(Entitlement).where(Entitlement.user_id == user_id))
        if entitlement is None:
            entitlement = Entitlement(user_id=user_id)
            db.add(entitlement)

        entitlement.is_premium = is_premium
        entitlement.plan = plan
        entitlement.expires_at = expires_at
        user.premium_enabled = is_premium
        user.mode = "premium" if is_premium else "free"
        db.commit()
        db.refresh(entitlement)
        return entitlement

    def require_premium(self, db: Session, user: User) -> Entitlement:
        entitlement = db.scalar(select(Entitlement).where(Entitlement.user_id == user.id))
        if not self._is_premium(entitlement, user):
            raise HTTPException(status_code=402, detail={"error": "premium_required", "message": "Premium entitlement required"})
        return entitlement if entitlement else Entitlement(user_id=user.id, is_premium=True, plan="premium")

    def search_lookalikes(self, db: Session, user: User, limit: int) -> List[dict]:
        self.require_premium(db, user)

        source_profile = db.scalar(select(IdentityProfile).where(IdentityProfile.user_id == user.id))
        if source_profile is None or not source_profile.face_embedding:
            raise HTTPException(status_code=404, detail="Identity enrollment not found")

        candidates = db.scalars(select(IdentityProfile).where(IdentityProfile.user_id != user.id)).all()
        results = []
        for profile in candidates:
            if not profile.face_embedding:
                continue
            if not self._eligible_for_lookalike(profile):
                continue

            candidate_user = db.get(User, profile.user_id)
            if candidate_user is None:
                continue

            similarity = self._cosine_similarity(source_profile.face_embedding, profile.face_embedding)
            results.append(
                {
                    "user_id": candidate_user.id,
                    "similarity": round(similarity, 4),
                    "preview_fields": {
                        "display_name": candidate_user.name,
                        "age_bucket": None,
                        "location_coarse": None,
                        "verified": profile.anti_fake_status == "passed",
                    },
                }
            )

        results.sort(key=lambda item: item["similarity"], reverse=True)
        return results[:limit]

    def profile_response(self, profile: IdentityProfile) -> dict:
        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "enrolled": True,
            "anti_fake_status": profile.anti_fake_status,
            "reason_codes": profile.anti_fake_reason_codes or [],
            "quality_score": profile.quality_score,
            "face_count": profile.face_count,
            "enrolled_at": profile.enrolled_at,
        }

    def verification_response(self, attempt: IdentityVerificationAttempt) -> dict:
        return {
            "verified": attempt.status == "verified",
            "status": attempt.status,
            "confidence": attempt.confidence,
            "reason_codes": attempt.reason_codes or [],
            "anti_fake_status": "passed" if attempt.status == "verified" else "review_required",
        }

    def entitlement_response(self, entitlement: Entitlement) -> dict:
        return {
            "user_id": entitlement.user_id,
            "is_premium": entitlement.is_premium,
            "plan": entitlement.plan,
            "expires_at": entitlement.expires_at.isoformat() if entitlement.expires_at else None,
        }

    def _compare_embeddings(self, enrolled: List[float], candidate: List[float]) -> float:
        if not enrolled or not candidate:
            return 0.0
        length = min(len(enrolled), len(candidate))
        distance = math.sqrt(sum((enrolled[i] - candidate[i]) ** 2 for i in range(length)))
        confidence = max(0.0, 1.0 - (distance / 2.0))
        return round(confidence, 4)

    def _cosine_similarity(self, left: List[float], right: List[float]) -> float:
        length = min(len(left), len(right))
        if length == 0:
            return 0.0
        numerator = sum(left[index] * right[index] for index in range(length))
        left_norm = math.sqrt(sum(value * value for value in left[:length]))
        right_norm = math.sqrt(sum(value * value for value in right[:length]))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return max(0.0, min(numerator / (left_norm * right_norm), 1.0))

    def _eligible_for_lookalike(self, profile: IdentityProfile) -> bool:
        return profile.anti_fake_status == "passed" or profile.quality_score >= 0.8

    def _is_premium(self, entitlement: Optional[Entitlement], user: User) -> bool:
        if entitlement:
            if not entitlement.is_premium:
                return False
            if entitlement.expires_at and entitlement.expires_at < datetime.utcnow():
                return False
            return True
        return bool(user.premium_enabled)

    def _raise_if_invalid_analysis(self, analysis: FaceAnalysis) -> None:
        if analysis.reason_codes:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Identity enrollment rejected",
                    "reason_codes": analysis.reason_codes,
                    "anti_fake_status": analysis.anti_fake_status,
                },
            )
