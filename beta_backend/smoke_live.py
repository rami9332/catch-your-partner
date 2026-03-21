"""
One-minute smoke test for a running docker-compose stack.
Run after:
  docker compose up -d
"""

import httpx
import uuid

BASE = "http://127.0.0.1:8000"


def post(path, json=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = httpx.post(f"{BASE}{path}", json=json, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def get(path, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = httpx.get(f"{BASE}{path}", headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def register(email, name):
    return post(
        "/auth/register",
        {
            "email": email,
            "password": "secret123",
            "name": name,
            "mode": "free",
            "interests": ["music", "coffee"],
        },
    )


def main():
    print("health", get("/health"))
    capabilities = get("/capabilities")
    print("capabilities", capabilities)

    suffix = uuid.uuid4().hex[:8]
    alice = register(f"smoke-alice-{suffix}@example.com", "Smoke Alice")
    bob = register(f"smoke-bob-{suffix}@example.com", "Smoke Bob")

    alice_token = alice["access_token"]
    bob_token = bob["access_token"]
    bob_id = bob["user"]["id"]

    print(post("/core/radar/start", {"lat": 52.52, "lng": 13.405, "zone_tag": "a", "safe_zones": []}, alice_token))
    print(post("/core/radar/start", {"lat": 52.5203, "lng": 13.4052, "zone_tag": "b", "safe_zones": []}, bob_token))
    print(get("/core/radar", alice_token))

    meeting = post(
        "/core/meeting/start",
        {"target_user_id": bob_id, "spot_name": "Cafe Orbit", "spot_lat": 52.5202, "spot_lng": 13.4053},
        alice_token,
    )
    meeting_id = meeting["meeting"]["id"]
    print("meeting", meeting)

    print(post("/core/navigation/start", {"meeting_id": meeting_id}, alice_token))
    print(post("/core/navigation/start", {"meeting_id": meeting_id}, bob_token))
    print(post("/core/check-in", {"meeting_id": meeting_id, "lat": 52.5202, "lng": 13.4053}, alice_token))
    print(post("/core/check-in", {"meeting_id": meeting_id, "lat": 52.5202, "lng": 13.4053}, bob_token))
    print(post("/core/ok", {"meeting_id": meeting_id, "signal": "ok"}, alice_token))
    print(post("/core/ok", {"meeting_id": meeting_id, "signal": "ok"}, bob_token))
    print(post("/core/chat/unlock", {"meeting_id": meeting_id}, alice_token))
    print(post("/core/chat/send", {"meeting_id": meeting_id, "text": "smoke hello"}, alice_token))
    print(get(f"/core/chat/history/{meeting_id}", bob_token))
    print(post("/core/safety/panic", {"meeting_id": meeting_id, "reason": "smoke"}, bob_token))

    identity_enabled = any(module["key"] == "identity" and module["enabled"] for module in capabilities["modules"])
    if identity_enabled:
        print("identity enabled; skipping live binary upload until sample image wiring is configured")
    companion_enabled = any(module["key"] == "companion" and module["enabled"] for module in capabilities["modules"])
    if companion_enabled:
        print(post("/companion/event", {"event_type": "chat_unlocked"}, alice_token))
        print(get("/companion/state", alice_token))
    print("smoke ok")


if __name__ == "__main__":
    main()
