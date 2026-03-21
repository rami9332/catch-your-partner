def register_user(client, email="identity@example.com", name="Identity User", mode="free"):
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "secret123", "name": name, "mode": mode, "interests": ["music"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_identity_enroll_and_verify_success(identity_enabled_client):
    user = register_user(identity_enabled_client)
    headers = auth_headers(user["access_token"])

    enroll = identity_enabled_client.post(
        "/identity/enroll",
        headers=headers,
        data={"consent": "true"},
        files={"selfie": ("selfie.txt", b"MATCH_A_SELFIE", "image/jpeg")},
    )
    assert enroll.status_code == 201, enroll.text
    assert enroll.json()["enrolled"] is True

    verify = identity_enabled_client.post(
        "/identity/verify",
        headers=headers,
        data={"consent": "true"},
        files={"selfie": ("verify.txt", b"MATCH_A_VERIFY", "image/jpeg")},
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["verified"] is True


def test_identity_enroll_fails_no_face(identity_enabled_client):
    user = register_user(identity_enabled_client, email="noface@example.com")
    headers = auth_headers(user["access_token"])
    response = identity_enabled_client.post(
        "/identity/enroll",
        headers=headers,
        data={"consent": "true"},
        files={"selfie": ("noface.txt", b"NO_FACE", "image/jpeg")},
    )
    assert response.status_code == 422
    assert "no_face" in response.text


def test_identity_enroll_fails_multiple_faces(identity_enabled_client):
    user = register_user(identity_enabled_client, email="multiple@example.com")
    headers = auth_headers(user["access_token"])
    response = identity_enabled_client.post(
        "/identity/enroll",
        headers=headers,
        data={"consent": "true"},
        files={"selfie": ("multi.txt", b"MULTIPLE_FACES", "image/jpeg")},
    )
    assert response.status_code == 422
    assert "multiple_faces" in response.text


def test_identity_profile_and_capabilities(identity_enabled_client):
    capabilities = identity_enabled_client.get("/capabilities")
    assert capabilities.status_code == 200
    identity = next(module for module in capabilities.json()["modules"] if module["key"] == "identity")
    assert identity["enabled"] is True


def test_identity_requires_auth(identity_enabled_client):
    response = identity_enabled_client.get("/identity/profile")
    assert response.status_code == 401


def test_lookalike_blocked_when_not_premium(identity_enabled_client):
    user = register_user(identity_enabled_client, email="blocked@example.com")
    headers = auth_headers(user["access_token"])
    identity_enabled_client.post(
        "/identity/enroll",
        headers=headers,
        data={"consent": "true"},
        files={"selfie": ("selfie.txt", b"MATCH_A_SELFIE", "image/jpeg")},
    )
    response = identity_enabled_client.post("/identity/lookalike/search", json={"limit": 10}, headers=headers)
    assert response.status_code == 402
    assert "premium_required" in response.text


def test_lookalike_works_when_premium_and_excludes_self(identity_enabled_client):
    admin = register_user(identity_enabled_client, email="admin@example.com", name="Admin", mode="free")
    user = register_user(identity_enabled_client, email="premium@example.com", name="Premium User")
    other_a = register_user(identity_enabled_client, email="other-a@example.com", name="Other A")
    other_b = register_user(identity_enabled_client, email="other-b@example.com", name="Other B")
    headers = auth_headers(user["access_token"])
    admin_headers = auth_headers(admin["access_token"])

    for token, payload in [
        (headers, b"MATCH_A_SELFIE"),
        (auth_headers(other_a["access_token"]), b"MATCH_B_SELFIE"),
        (auth_headers(other_b["access_token"]), b"MATCH_C_SELFIE"),
    ]:
        response = identity_enabled_client.post(
            "/identity/enroll",
            headers=token,
            data={"consent": "true"},
            files={"selfie": ("selfie.txt", payload, "image/jpeg")},
        )
        assert response.status_code == 201, response.text

    entitlement = identity_enabled_client.post(
        "/identity/admin/entitlements/set",
        json={"user_id": user["user"]["id"], "is_premium": True, "plan": "premium"},
        headers=admin_headers,
    )
    assert entitlement.status_code == 200, entitlement.text

    response = identity_enabled_client.post("/identity/lookalike/search", json={"limit": 10}, headers=headers)
    assert response.status_code == 200, response.text
    matches = response.json()["matches"]
    assert matches
    assert all(item["user_id"] != user["user"]["id"] for item in matches)
    assert matches == sorted(matches, key=lambda item: item["similarity"], reverse=True)
    assert "display_name" in matches[0]["preview_fields"]
    assert "verified" in matches[0]["preview_fields"]
    assert "face_embedding" not in str(matches[0])


def test_lookalike_respects_quality_filters(identity_enabled_client):
    admin = register_user(identity_enabled_client, email="admin@example.com", name="Admin Two")
    source = register_user(identity_enabled_client, email="source@example.com", name="Source")
    low_quality = register_user(identity_enabled_client, email="lowq@example.com", name="Low Quality")
    good = register_user(identity_enabled_client, email="good@example.com", name="Good Candidate")
    source_headers = auth_headers(source["access_token"])
    admin_headers = auth_headers(admin["access_token"])

    identity_enabled_client.post(
        "/identity/enroll",
        headers=source_headers,
        data={"consent": "true"},
        files={"selfie": ("source.txt", b"MATCH_A_SOURCE", "image/jpeg")},
    )
    low_quality_response = identity_enabled_client.post(
        "/identity/enroll",
        headers=auth_headers(low_quality["access_token"]),
        data={"consent": "true"},
        files={"selfie": ("lowq.txt", b"LOW_QUALITY", "image/jpeg")},
    )
    assert low_quality_response.status_code == 422
    good_response = identity_enabled_client.post(
        "/identity/enroll",
        headers=auth_headers(good["access_token"]),
        data={"consent": "true"},
        files={"selfie": ("good.txt", b"MATCH_B_GOOD", "image/jpeg")},
    )
    assert good_response.status_code == 201

    identity_enabled_client.post(
        "/identity/admin/entitlements/set",
        json={"user_id": source["user"]["id"], "is_premium": True, "plan": "premium"},
        headers=admin_headers,
    )
    response = identity_enabled_client.post("/identity/lookalike/search", json={"limit": 10}, headers=source_headers)
    assert response.status_code == 200
    match_ids = [item["user_id"] for item in response.json()["matches"]]
    assert good["user"]["id"] in match_ids
    assert low_quality["user"]["id"] not in match_ids
