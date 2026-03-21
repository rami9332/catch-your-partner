"""
Run a minimal core flow against a running local server.
Start services first:
  docker compose up --build
Then:
  python beta_backend/demo_flow.py
"""

import httpx
from typing import Dict, Optional, Tuple

BASE = "http://127.0.0.1:8000"


def post(path: str, json: Optional[Dict] = None, token: Optional[str] = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = httpx.post(f"{BASE}{path}", json=json, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def get(path: str, params: Optional[Dict] = None, token: Optional[str] = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = httpx.get(f"{BASE}{path}", params=params, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def register_and_login(email: str, password: str, name: str) -> Tuple[str, str]:
    register = post(
        "/auth/register",
        {
            "email": email,
            "password": password,
            "name": name,
            "mode": "free",
            "interests": ["music", "coffee"],
            "astro_sign": "Leo",
        },
    )
    login = post("/auth/login", {"email": email, "password": password})
    return register["user"]["id"], login["access_token"]


def main() -> None:
    print(get("/health"))
    print(get("/capabilities"))

    alice_id, alice_token = register_and_login("alice@example.com", "secret123", "Alice")
    bob_id, bob_token = register_and_login("bob@example.com", "secret123", "Bob")

    print(post("/core/radar/start", {"lat": 52.52, "lng": 13.405, "zone_tag": "square-a"}, alice_token))
    print(post("/core/radar/start", {"lat": 52.5205, "lng": 13.4055, "zone_tag": "square-b"}, bob_token))

    radar = get("/core/radar", token=alice_token)
    print(radar)

    meeting = post(
        "/core/meeting/start",
        {
            "target_user_id": bob_id,
            "spot_name": "Cafe Orbit",
            "spot_lat": 52.5202,
            "spot_lng": 13.4053,
        },
        alice_token,
    )
    meeting_id = meeting["meeting"]["id"]
    print(meeting)

    print(post("/core/navigation/start", {"meeting_id": meeting_id}, alice_token))
    print(post("/core/navigation/start", {"meeting_id": meeting_id}, bob_token))
    print(post("/core/check-in", {"meeting_id": meeting_id, "lat": 52.5202, "lng": 13.4053}, alice_token))
    print(post("/core/check-in", {"meeting_id": meeting_id, "lat": 52.5202, "lng": 13.4053}, bob_token))
    print(post("/core/ok", {"meeting_id": meeting_id, "signal": "ok"}, alice_token))
    print(post("/core/ok", {"meeting_id": meeting_id, "signal": "ok"}, bob_token))
    print(post("/core/chat/unlock", {"meeting_id": meeting_id}, alice_token))
    print(post("/core/chat/send", {"meeting_id": meeting_id, "text": "Hey Bob"}, alice_token))
    print(get(f"/core/chat/history/{meeting_id}", token=bob_token))
    print(post("/core/safety/panic", {"meeting_id": meeting_id, "reason": "manual"}, bob_token))


if __name__ == "__main__":
    main()
