from core.config import settings


def test_register_user(register_user):
    response = register_user(email="Test@Example.com")
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["role"] == "patient"
    assert "id" in data


def test_register_duplicate_user(register_user):
    register_user(email="test2@example.com")
    response = register_user(email="TEST2@example.com")
    assert response.status_code == 400


def test_register_rejects_invalid_role(client):
    response = client.post(
        "/auth/register",
        json={"email": "bad-role@example.com", "password": "password123", "role": "superadmin"},
    )
    assert response.status_code == 422


def test_register_rejects_clinician_role(client):
    response = client.post(
        "/auth/register",
        json={"email": "clinician-public@example.com", "password": "password123", "role": "clinician"},
    )
    assert response.status_code == 403
    assert "administrator" in response.json()["detail"]


def test_register_rejects_weak_password(client):
    response = client.post(
        "/auth/register",
        json={"email": "weak@example.com", "password": "short", "role": "patient"},
    )
    assert response.status_code == 422


def test_login_user(register_user, login_user):
    register_user(email="login@example.com")
    response = login_user(email="login@example.com")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    assert data["token_type"] == "bearer"


def test_login_is_case_insensitive(register_user, login_user):
    register_user(email="mixed-login@example.com")
    response = login_user(email="MIXED-LOGIN@example.com")
    assert response.status_code == 200


def test_login_rejects_wrong_password(register_user, login_user):
    register_user(email="wrong-password@example.com")
    response = login_user(email="wrong-password@example.com", password="bad-password")
    assert response.status_code == 401


def test_login_rate_limits_repeated_failed_attempts(register_user, login_user):
    register_user(email="limited-login@example.com")

    for _ in range(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS):
        response = login_user(email="limited-login@example.com", password="bad-password")
        assert response.status_code == 401

    blocked_response = login_user(email="limited-login@example.com", password="password123")

    assert blocked_response.status_code == 429
    assert "Retry-After" in blocked_response.headers


def test_successful_login_clears_failed_attempt_counter(register_user, login_user):
    register_user(email="counter-reset@example.com")

    for _ in range(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS - 1):
        response = login_user(email="counter-reset@example.com", password="bad-password")
        assert response.status_code == 401

    success_response = login_user(email="counter-reset@example.com", password="password123")
    assert success_response.status_code == 200

    for _ in range(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS - 1):
        response = login_user(email="counter-reset@example.com", password="bad-password")
        assert response.status_code == 401

    still_allowed_response = login_user(email="counter-reset@example.com", password="password123")
    assert still_allowed_response.status_code == 200


def test_refresh_token_rotates_session(client, register_user, login_user):
    register_user(email="refresh@example.com")
    login_response = login_user(email="refresh@example.com")
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["access_token"]
    assert refreshed["refresh_token"]
    assert refreshed["refresh_token"] != refresh_token
    assert refreshed["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    reused_response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert reused_response.status_code == 401

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
    )
    assert me_response.status_code == 200


def test_logout_revokes_refresh_token(client, register_user, login_user):
    register_user(email="logout-refresh@example.com")
    login_response = login_user(email="logout-refresh@example.com")
    refresh_token = login_response.json()["refresh_token"]

    logout_response = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout_response.status_code == 200

    refresh_response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_response.status_code == 401


def test_refresh_rejects_inactive_user(client, create_user, login_user, db_session):
    user = create_user(email="inactive-refresh@example.com", password="password123", role="clinician")
    login_response = login_user(email="inactive-refresh@example.com", password="password123")
    refresh_token = login_response.json()["refresh_token"]

    user.is_active = False
    db_session.add(user)
    db_session.commit()

    refresh_response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_response.status_code == 403


def test_protected_endpoint_rejects_missing_token(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_protected_endpoint_accepts_valid_token(client, create_user, login_user):
    create_user(email="me@example.com", role="clinician")
    login_response = login_user(email="me@example.com")
    token = login_response.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "me@example.com"
    assert data["role"] == "clinician"
    assert data["must_reset_password"] is False


def test_token_contains_subject_and_role_claims(create_user, login_user):
    create_user(email="claims@example.com", role="clinician")
    login_response = login_user(email="claims@example.com")
    token = login_response.json()["access_token"]

    from jose import jwt

    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.ALGORITHM])
    assert payload["role"] == "clinician"
    assert payload["type"] == "access"
    assert payload["sub"]


def test_change_password_clears_required_reset_flag(client, create_user, login_user):
    create_user(
        email="reset-required@example.com",
        password="password123",
        role="clinician",
        must_reset_password=True,
    )
    login_response = login_user(email="reset-required@example.com", password="password123")
    token = login_response.json()["access_token"]

    response = client.post(
        "/auth/password",
        json={"current_password": "password123", "new_password": "password456"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["must_reset_password"] is False
    assert data["password_changed_at"] is not None

    old_login = login_user(email="reset-required@example.com", password="password123")
    assert old_login.status_code == 401

    new_login = login_user(email="reset-required@example.com", password="password456")
    assert new_login.status_code == 200


def test_change_password_rejects_wrong_current_password(client, create_user, login_user):
    create_user(email="wrong-current@example.com", password="password123", role="clinician")
    login_response = login_user(email="wrong-current@example.com", password="password123")
    token = login_response.json()["access_token"]

    response = client.post(
        "/auth/password",
        json={"current_password": "bad-password", "new_password": "password456"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
