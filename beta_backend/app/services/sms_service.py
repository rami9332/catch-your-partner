from __future__ import annotations

from dataclasses import dataclass
from base64 import b64encode
from urllib import parse, request
from urllib.error import HTTPError, URLError

from app.config import Settings


@dataclass
class SmsSendResult:
    delivery_status: str
    provider_message_id: str | None = None
    error_detail: str | None = None


class SmsProvider:
    def send_verification_code(self, phone_number: str, code: str, settings: Settings) -> SmsSendResult:
        raise NotImplementedError

    def send_message(self, phone_number: str, body: str, settings: Settings) -> SmsSendResult:
        raise NotImplementedError


class NoopSmsProvider(SmsProvider):
    def send_verification_code(self, phone_number: str, code: str, settings: Settings) -> SmsSendResult:
        return SmsSendResult(delivery_status="provider_missing")

    def send_message(self, phone_number: str, body: str, settings: Settings) -> SmsSendResult:
        return SmsSendResult(delivery_status="provider_missing")


class TwilioSmsProvider(SmsProvider):
    def send_verification_code(self, phone_number: str, code: str, settings: Settings) -> SmsSendResult:
        return self.send_message(phone_number, f"Dein Catch Your Partner Code lautet: {code}", settings)

    def send_message(self, phone_number: str, body: str, settings: Settings) -> SmsSendResult:
        if not settings.twilio_account_sid or not settings.twilio_auth_token or not settings.sms_from_number:
            return SmsSendResult(delivery_status="provider_missing")

        body = parse.urlencode(
            {
                "To": phone_number,
                "From": settings.sms_from_number,
                "Body": body,
            }
        ).encode("utf-8")

        req = request.Request(
            url=f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": "Basic "
                + b64encode(f"{settings.twilio_account_sid}:{settings.twilio_auth_token}".encode("utf-8")).decode("utf-8"),
            },
        )

        try:
            with request.urlopen(req, timeout=10) as response:
                payload = response.read().decode("utf-8", errors="ignore")
                provider_message_id = None
                marker = '"sid":'
                if marker in payload:
                    sid_fragment = payload.split(marker, 1)[1]
                    provider_message_id = sid_fragment.split('"', 2)[1]
                return SmsSendResult(delivery_status="sent", provider_message_id=provider_message_id)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            return SmsSendResult(delivery_status="failed", error_detail=detail or f"http_{exc.code}")
        except URLError as exc:
            return SmsSendResult(delivery_status="failed", error_detail=str(exc.reason))


class SmsService:
    def __init__(self) -> None:
        self.providers = {
            "none": NoopSmsProvider(),
            "twilio": TwilioSmsProvider(),
        }

    def send_verification_code(self, phone_number: str, code: str, settings: Settings) -> SmsSendResult:
        provider_key = (settings.sms_provider or "none").strip().lower()
        provider = self.providers.get(provider_key, self.providers["none"])
        return provider.send_verification_code(phone_number, code, settings)

    def send_message(self, phone_number: str, body: str, settings: Settings) -> SmsSendResult:
        provider_key = (settings.sms_provider or "none").strip().lower()
        provider = self.providers.get(provider_key, self.providers["none"])
        return provider.send_message(phone_number, body, settings)
