def register_user(client, email="companion@example.com", name="Companion User"):
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "secret123", "name": name, "mode": "free", "interests": ["music"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_companion_state_default(companion_enabled_client):
    user = register_user(companion_enabled_client)
    response = companion_enabled_client.get("/companion/state", headers=auth_headers(user["access_token"]))
    assert response.status_code == 200
    payload = response.json()
    assert payload["level"] == 1
    assert payload["xp"] == 0
    assert payload["streak"] == 0
    assert payload["mood"] == "curious"
    assert payload["next_level_xp"] == 100


def test_companion_event_updates_xp_and_level(companion_enabled_client):
    user = register_user(companion_enabled_client, email="xp@example.com")
    headers = auth_headers(user["access_token"])

    for event_type in ["chat_unlocked", "chat_unlocked"]:
        response = companion_enabled_client.post("/companion/event", json={"event_type": event_type}, headers=headers)
        assert response.status_code == 200, response.text

    payload = companion_enabled_client.get("/companion/state", headers=headers).json()
    assert payload["xp"] == 100
    assert payload["level"] == 2
    assert payload["next_level_xp"] == 400


def test_companion_panic_produces_serious_message(companion_enabled_client):
    user = register_user(companion_enabled_client, email="panic@example.com")
    headers = auth_headers(user["access_token"])

    response = companion_enabled_client.post("/companion/event", json={"event_type": "panic"}, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["reward_delta"] == 0
    assert payload["state"]["mood"] == "serious"
    assert "Serious mode" in payload["message"]


def test_companion_auth_guard(companion_enabled_client):
    response = companion_enabled_client.get("/companion/state")
    assert response.status_code == 401


def test_companion_say_returns_reply(companion_enabled_client):
    user = register_user(companion_enabled_client, email="say@example.com")
    headers = auth_headers(user["access_token"])

    response = companion_enabled_client.post("/companion/say", json={"text": "How much XP do I have?"}, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert "XP" in payload["reply"]
    assert payload["suggested_action"] == "complete_checkin"
