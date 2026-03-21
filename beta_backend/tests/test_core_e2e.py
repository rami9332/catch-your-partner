def start_radar(client, headers, lat=52.52, lng=13.405, zone_tag="alpha"):
    return client.post("/core/radar/start", json={"lat": lat, "lng": lng, "zone_tag": zone_tag, "safe_zones": []}, headers=headers)


def create_meeting(client, headers, target_user_id, spot_lat=52.5202, spot_lng=13.4053):
    return client.post(
        "/core/meeting/start",
        json={"target_user_id": target_user_id, "spot_name": "Cafe Orbit", "spot_lat": spot_lat, "spot_lng": spot_lng},
        headers=headers,
    )


def login(client, email, password="secret123"):
    return client.post("/auth/login", json={"email": email, "password": password})


def sync_matching_profile(
    client,
    headers,
    *,
    verification_status="ready",
    face_scan_available=True,
    location_available=True,
    radar_active=True,
    matching_allowed=True,
    interests=None,
    lat=52.52,
    lng=13.405,
    max_distance=300,
):
    return client.put(
        "/core/matching/profile",
        json={
            "verification_status": verification_status,
            "face_scan_available": face_scan_available,
            "location_available": location_available,
            "radar_active": radar_active,
            "matching_allowed": matching_allowed,
            "interests": interests or ["music", "coffee"],
            "preferences": {"maxDistanceMeters": max_distance},
            "location": {"lat": lat, "lng": lng},
            "timestamps": {},
            "scan": {"detector_mode": "local", "face_count": 1, "capture_available": True},
        },
        headers=headers,
    )


def accept_meeting(client, headers, meeting_id):
    return client.post("/core/meeting/accept", json={"meeting_id": meeting_id}, headers=headers)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_capabilities_returns_flags(client):
    response = client.get("/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert any(module["key"] == "core" and module["enabled"] for module in payload["modules"])
    assert "non_blocking_modules" in payload["core_flow"]


def test_register_login_and_me(client, user_factory, auth_headers):
    registered = user_factory("alice@example.com", "Alice")
    token = registered["access_token"]
    me = client.get("/auth/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


def test_core_happy_path_e2e(client, user_factory, auth_headers):
    alice = user_factory("alice2@example.com", "Alice")
    bob = user_factory("bob2@example.com", "Bob")
    alice_headers = auth_headers(alice["access_token"])
    bob_headers = auth_headers(bob["access_token"])

    assert start_radar(client, alice_headers, zone_tag="a").status_code == 201
    assert start_radar(client, bob_headers, lat=52.5205, lng=13.4054, zone_tag="b").status_code == 201

    radar = client.get("/core/radar", headers=alice_headers)
    assert radar.status_code == 200
    assert radar.json()["results"][0]["user_id"] == bob["user"]["id"]

    meeting = create_meeting(client, alice_headers, bob["user"]["id"])
    assert meeting.status_code == 201
    meeting_id = meeting.json()["meeting"]["id"]

    assert accept_meeting(client, alice_headers, meeting_id).status_code == 200
    assert accept_meeting(client, bob_headers, meeting_id).status_code == 200
    assert client.post("/core/navigation/start", json={"meeting_id": meeting_id}, headers=alice_headers).status_code == 200
    assert client.post("/core/navigation/start", json={"meeting_id": meeting_id}, headers=bob_headers).status_code == 200
    assert client.post("/core/check-in", json={"meeting_id": meeting_id, "lat": 52.5202, "lng": 13.4053}, headers=alice_headers).status_code == 200
    assert client.post("/core/check-in", json={"meeting_id": meeting_id, "lat": 52.5202, "lng": 13.4053}, headers=bob_headers).status_code == 200
    assert client.post("/core/ok", json={"meeting_id": meeting_id, "signal": "ok"}, headers=alice_headers).status_code == 200
    assert client.post("/core/ok", json={"meeting_id": meeting_id, "signal": "ok"}, headers=bob_headers).status_code == 200
    assert client.post("/core/chat/unlock", json={"meeting_id": meeting_id}, headers=alice_headers).status_code == 200
    send = client.post("/core/chat/send", json={"meeting_id": meeting_id, "text": "Hey Bob"}, headers=alice_headers)
    assert send.status_code == 201
    history = client.get(f"/core/chat/history/{meeting_id}", headers=bob_headers)
    assert history.status_code == 200
    assert history.json()["messages"][0]["text"] == "Hey Bob"
    panic = client.post("/core/safety/panic", json={"meeting_id": meeting_id, "reason": "manual"}, headers=bob_headers)
    assert panic.status_code == 200


def test_chat_locked_returns_403(client, user_factory, auth_headers):
    alice = user_factory("alice3@example.com", "Alice")
    bob = user_factory("bob3@example.com", "Bob")
    alice_headers = auth_headers(alice["access_token"])
    meeting = create_meeting(client, alice_headers, bob["user"]["id"]).json()["meeting"]["id"]
    response = client.post("/core/chat/send", json={"meeting_id": meeting, "text": "Too early"}, headers=alice_headers)
    assert response.status_code == 403


def test_too_far_checkin_returns_422(client, user_factory, auth_headers):
    alice = user_factory("alice4@example.com", "Alice")
    bob = user_factory("bob4@example.com", "Bob")
    alice_headers = auth_headers(alice["access_token"])
    bob_headers = auth_headers(bob["access_token"])
    meeting = create_meeting(client, alice_headers, bob["user"]["id"]).json()["meeting"]["id"]
    assert accept_meeting(client, alice_headers, meeting).status_code == 200
    assert accept_meeting(client, bob_headers, meeting).status_code == 200
    response = client.post("/core/check-in", json={"meeting_id": meeting, "lat": 40.0, "lng": 10.0}, headers=alice_headers)
    assert response.status_code == 422


def test_abort_locks_chat(client, user_factory, auth_headers):
    alice = user_factory("alice5@example.com", "Alice")
    bob = user_factory("bob5@example.com", "Bob")
    alice_headers = auth_headers(alice["access_token"])
    bob_headers = auth_headers(bob["access_token"])
    meeting = create_meeting(client, alice_headers, bob["user"]["id"]).json()["meeting"]["id"]

    client.post("/core/ok", json={"meeting_id": meeting, "signal": "ok"}, headers=alice_headers)
    client.post("/core/ok", json={"meeting_id": meeting, "signal": "ok"}, headers=bob_headers)
    client.post("/core/chat/unlock", json={"meeting_id": meeting}, headers=alice_headers)

    abort = client.post("/core/safety/abort", json={"meeting_id": meeting, "reason": "unsafe"}, headers=bob_headers)
    assert abort.status_code == 200

    send = client.post("/core/chat/send", json={"meeting_id": meeting, "text": "Nope"}, headers=alice_headers)
    assert send.status_code == 403


def test_auth_required_for_core(client):
    response = client.get("/core/radar")
    assert response.status_code == 401


def test_invalid_login_returns_401(client, user_factory):
    user_factory("alice6@example.com", "Alice")
    response = login(client, "alice6@example.com", "wrongpass")
    assert response.status_code == 401


def test_runtime_flags_admin_only(client, user_factory, auth_headers):
    admin = client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "secret123", "name": "Admin", "mode": "free", "interests": []},
    ).json()
    user = user_factory("alice7@example.com", "Alice")

    forbidden = client.post(
        "/admin/runtime-flags",
        json={"module_key": "identity", "enabled": True},
        headers=auth_headers(user["access_token"]),
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        "/admin/runtime-flags",
        json={"module_key": "identity", "enabled": True},
        headers=auth_headers(admin["access_token"]),
    )
    assert allowed.status_code == 200
    assert allowed.json()["flags"]["identity"] is True


def test_panic_stops_radar_and_logs_event(client, user_factory, auth_headers):
    alice = user_factory("alice8@example.com", "Alice")
    alice_headers = auth_headers(alice["access_token"])
    start_radar(client, alice_headers)
    panic = client.post("/core/safety/panic", json={"reason": "manual"}, headers=alice_headers)
    assert panic.status_code == 200
    insights = client.get("/core/insights", headers=alice_headers)
    assert insights.status_code == 200
    assert insights.json()["safety_events"] >= 1


def test_matching_profiles_return_only_eligible_nearby_candidates(client, user_factory, auth_headers):
    alice = user_factory("matching-a@example.com", "Alice")
    bob = user_factory("matching-b@example.com", "Bob")
    far = user_factory("matching-far@example.com", "Far Away")
    blocked = user_factory("matching-blocked@example.com", "Blocked")

    alice_headers = auth_headers(alice["access_token"])
    bob_headers = auth_headers(bob["access_token"])
    far_headers = auth_headers(far["access_token"])
    blocked_headers = auth_headers(blocked["access_token"])

    assert sync_matching_profile(client, alice_headers, lat=52.52, lng=13.405, interests=["music", "coffee"]).status_code == 200
    assert sync_matching_profile(client, bob_headers, lat=52.5206, lng=13.4054, interests=["music", "art"]).status_code == 200
    assert sync_matching_profile(client, far_headers, lat=52.54, lng=13.45, interests=["music"]).status_code == 200
    assert sync_matching_profile(client, blocked_headers, radar_active=False, lat=52.5204, lng=13.4052).status_code == 200

    response = client.get("/core/matching/candidates", headers=alice_headers)
    assert response.status_code == 200
    payload = response.json()

    assert payload["source_profile"]["matching_eligible"] is True
    candidate_ids = [item["user_id"] for item in payload["candidates"]]
    assert bob["user"]["id"] in candidate_ids
    assert far["user"]["id"] not in candidate_ids
    assert blocked["user"]["id"] not in candidate_ids
    bob_candidate = next(item for item in payload["candidates"] if item["user_id"] == bob["user"]["id"])
    assert bob_candidate["location"]["lat"] == 52.5206
    assert bob_candidate["location"]["lng"] == 13.4054


def test_pair_meeting_is_created_once_and_loadable_for_both_users(client, user_factory, auth_headers):
    alice = user_factory("meeting-sync-a@example.com", "Alice")
    bob = user_factory("meeting-sync-b@example.com", "Bob")
    alice_headers = auth_headers(alice["access_token"])
    bob_headers = auth_headers(bob["access_token"])

    assert sync_matching_profile(client, alice_headers, lat=52.52, lng=13.405).status_code == 200
    assert sync_matching_profile(client, bob_headers, lat=52.5206, lng=13.4054).status_code == 200

    created = create_meeting(client, alice_headers, bob["user"]["id"], spot_lat=52.5203, spot_lng=13.4052)
    assert created.status_code == 201
    created_meeting = created.json()["meeting"]
    assert created_meeting["user_a_id"] == alice["user"]["id"]
    assert created_meeting["user_b_id"] == bob["user"]["id"]
    assert created_meeting["created_at"] is not None
    assert created_meeting["fully_accepted"] is False

    repeated = create_meeting(client, alice_headers, bob["user"]["id"], spot_lat=52.5203, spot_lng=13.4052)
    assert repeated.status_code == 201
    assert repeated.json()["meeting"]["id"] == created_meeting["id"]

    alice_loaded = client.get(f"/core/meeting/with/{bob['user']['id']}", headers=alice_headers)
    bob_loaded = client.get(f"/core/meeting/with/{alice['user']['id']}", headers=bob_headers)
    assert alice_loaded.status_code == 200
    assert bob_loaded.status_code == 200
    assert alice_loaded.json()["meeting"]["id"] == created_meeting["id"]
    assert bob_loaded.json()["meeting"]["id"] == created_meeting["id"]


def test_meeting_requires_both_acceptances_before_navigation(client, user_factory, auth_headers):
    alice = user_factory("meeting-accept-a@example.com", "Alice")
    bob = user_factory("meeting-accept-b@example.com", "Bob")
    alice_headers = auth_headers(alice["access_token"])
    bob_headers = auth_headers(bob["access_token"])

    assert sync_matching_profile(client, alice_headers, lat=52.52, lng=13.405).status_code == 200
    assert sync_matching_profile(client, bob_headers, lat=52.5206, lng=13.4054).status_code == 200

    created = create_meeting(client, alice_headers, bob["user"]["id"])
    meeting_id = created.json()["meeting"]["id"]

    blocked = client.post("/core/navigation/start", json={"meeting_id": meeting_id}, headers=alice_headers)
    assert blocked.status_code == 409

    once = accept_meeting(client, alice_headers, meeting_id)
    assert once.status_code == 200
    assert once.json()["meeting"]["fully_accepted"] is False
    assert once.json()["meeting"]["accepted_by_user_a"] is True
    assert once.json()["meeting"]["accepted_by_user_b"] is False

    twice = accept_meeting(client, bob_headers, meeting_id)
    assert twice.status_code == 200
    assert twice.json()["meeting"]["fully_accepted"] is True
    assert twice.json()["meeting"]["status"] == "accepted"


def test_meeting_arrival_requires_both_acceptances_and_tracks_both_users(client, user_factory, auth_headers):
    alice = user_factory("meeting-arrival-a@example.com", "Alice")
    bob = user_factory("meeting-arrival-b@example.com", "Bob")
    alice_headers = auth_headers(alice["access_token"])
    bob_headers = auth_headers(bob["access_token"])

    assert sync_matching_profile(client, alice_headers, lat=52.52, lng=13.405).status_code == 200
    assert sync_matching_profile(client, bob_headers, lat=52.5206, lng=13.4054).status_code == 200

    meeting_id = create_meeting(client, alice_headers, bob["user"]["id"]).json()["meeting"]["id"]

    blocked = client.post("/core/check-in", json={"meeting_id": meeting_id, "lat": 52.5202, "lng": 13.4053}, headers=alice_headers)
    assert blocked.status_code == 409

    assert accept_meeting(client, alice_headers, meeting_id).status_code == 200
    assert accept_meeting(client, bob_headers, meeting_id).status_code == 200

    alice_arrival = client.post("/core/check-in", json={"meeting_id": meeting_id, "lat": 52.5202, "lng": 13.4053}, headers=alice_headers)
    assert alice_arrival.status_code == 200
    assert alice_arrival.json()["meeting"]["arrived_by_user_a"] is True
    assert alice_arrival.json()["meeting"]["arrived_by_user_b"] is False
    assert alice_arrival.json()["meeting"]["both_arrived"] is False
    assert alice_arrival.json()["meeting"]["status"] == "awaiting_arrival"

    bob_arrival = client.post("/core/check-in", json={"meeting_id": meeting_id, "lat": 52.5202, "lng": 13.4053}, headers=bob_headers)
    assert bob_arrival.status_code == 200
    assert bob_arrival.json()["meeting"]["arrived_by_user_a"] is True
    assert bob_arrival.json()["meeting"]["arrived_by_user_b"] is True
    assert bob_arrival.json()["meeting"]["both_arrived"] is True
    assert bob_arrival.json()["meeting"]["status"] == "checked_in"


def test_meeting_ok_requires_both_arrivals_and_tracks_both_users(client, user_factory, auth_headers):
    alice = user_factory("meeting-ok-a@example.com", "Alice")
    bob = user_factory("meeting-ok-b@example.com", "Bob")
    alice_headers = auth_headers(alice["access_token"])
    bob_headers = auth_headers(bob["access_token"])

    assert sync_matching_profile(client, alice_headers, lat=52.52, lng=13.405).status_code == 200
    assert sync_matching_profile(client, bob_headers, lat=52.5206, lng=13.4054).status_code == 200

    meeting_id = create_meeting(client, alice_headers, bob["user"]["id"]).json()["meeting"]["id"]
    assert accept_meeting(client, alice_headers, meeting_id).status_code == 200
    assert accept_meeting(client, bob_headers, meeting_id).status_code == 200

    blocked = client.post("/core/ok", json={"meeting_id": meeting_id, "signal": "ok"}, headers=alice_headers)
    assert blocked.status_code == 409

    assert client.post("/core/check-in", json={"meeting_id": meeting_id, "lat": 52.5202, "lng": 13.4053}, headers=alice_headers).status_code == 200
    assert client.post("/core/check-in", json={"meeting_id": meeting_id, "lat": 52.5202, "lng": 13.4053}, headers=bob_headers).status_code == 200

    alice_ok = client.post("/core/ok", json={"meeting_id": meeting_id, "signal": "ok"}, headers=alice_headers)
    assert alice_ok.status_code == 200
    assert alice_ok.json()["meeting"]["ok_by_user_a"] is True
    assert alice_ok.json()["meeting"]["ok_by_user_b"] is False
    assert alice_ok.json()["meeting"]["both_ok"] is False
    assert alice_ok.json()["meeting"]["status"] == "awaiting_ok"
    assert alice_ok.json()["meeting"]["chat_unlocked"] is False

    bob_ok = client.post("/core/ok", json={"meeting_id": meeting_id, "signal": "ok"}, headers=bob_headers)
    assert bob_ok.status_code == 200
    assert bob_ok.json()["meeting"]["ok_by_user_a"] is True
    assert bob_ok.json()["meeting"]["ok_by_user_b"] is True
    assert bob_ok.json()["meeting"]["both_ok"] is True
    assert bob_ok.json()["meeting"]["status"] == "ok_confirmed"
    assert bob_ok.json()["meeting"]["chat_unlocked"] is True


def test_matching_requires_all_conditions_before_candidate_search(client, user_factory, auth_headers):
    alice = user_factory("matching-incomplete@example.com", "Alice")
    alice_headers = auth_headers(alice["access_token"])

    response = sync_matching_profile(
        client,
        alice_headers,
        face_scan_available=False,
        radar_active=False,
        location_available=False,
    )
    assert response.status_code == 200
    assert response.json()["matching_eligible"] is False

    candidates = client.get("/core/matching/candidates", headers=alice_headers)
    assert candidates.status_code == 200
    payload = candidates.json()
    assert payload["source_profile"]["matching_eligible"] is False
    assert payload["candidates"] == []
