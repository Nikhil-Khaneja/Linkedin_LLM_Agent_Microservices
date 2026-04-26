from jose import jwt

from app.core.config import settings
from app.core.security import PUBLIC_KEY_PEM


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_success(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "ava@example.com",
            "password": "StrongPass#1",
            "user_type": "member",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user_id"].startswith("usr_")


def test_duplicate_email_returns_409(client):
    payload = {
        "email": "duplicate@example.com",
        "password": "StrongPass#1",
        "user_type": "member",
    }
    r1 = client.post("/auth/register", json=payload)
    assert r1.status_code == 200

    r2 = client.post("/auth/register", json=payload)
    assert r2.status_code == 409


def test_login_success(client):
    client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "StrongPass#1",
            "user_type": "member",
        },
    )

    response = client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "StrongPass#1"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_invalid_password(client):
    client.post(
        "/auth/register",
        json={
            "email": "badpass@example.com",
            "password": "StrongPass#1",
            "user_type": "member",
        },
    )

    response = client.post(
        "/auth/login",
        json={"email": "badpass@example.com", "password": "WrongPass#1"},
    )
    assert response.status_code == 401


def test_refresh_success(client):
    reg = client.post(
        "/auth/register",
        json={
            "email": "refresh@example.com",
            "password": "StrongPass#1",
            "user_type": "member",
        },
    )
    refresh_token = reg.json()["refresh_token"]

    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


def test_logout_success(client):
    reg = client.post(
        "/auth/register",
        json={
            "email": "logout@example.com",
            "password": "StrongPass#1",
            "user_type": "member",
        },
    )
    refresh_token = reg.json()["refresh_token"]

    response = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"


def test_jwks_exists(client):
    response = client.get("/.well-known/jwks.json")
    assert response.status_code == 200
    assert "keys" in response.json()
    assert len(response.json()["keys"]) >= 1


def test_protected_me(client):
    reg = client.post(
        "/auth/register",
        json={
            "email": "protected@example.com",
            "password": "StrongPass#1",
            "user_type": "member",
        },
    )
    access_token = reg.json()["access_token"]

    response = client.get(
        "/protected/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "protected@example.com"


def test_request_id_header_present(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert "x-request-id" in response.headers


def test_idempotency_replay(client):
    headers = {"Idempotency-Key": "same-register-1"}
    payload = {
        "email": "idem@example.com",
        "password": "StrongPass#1",
        "user_type": "member",
    }

    r1 = client.post("/auth/register", json=payload, headers=headers)
    assert r1.status_code == 200

    r2 = client.post("/auth/register", json=payload, headers=headers)
    assert r2.status_code == 200
    assert r2.headers.get("x-idempotent-replay") == "true"