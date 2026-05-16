import pytest


@pytest.mark.asyncio
async def test_status_uninitialized_competition(client):
    r = await client.get("/api/system/status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "competition"
    assert body["initialized"] is False
    assert body["practice_problem_count"] == 0


@pytest.mark.asyncio
async def test_setup_creates_first_admin(client):
    payload = {
        "email": "root@codefy.dev",
        "password": "supersecret123",
        "display_name": "Root",
    }
    r = await client.post("/api/system/setup", json=payload)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["email"] == "root@codefy.dev"
    assert created["role"] == "admin"
    assert created["is_superuser"] is True

    r = await client.get("/api/system/status")
    assert r.status_code == 200
    assert r.json()["initialized"] is True


@pytest.mark.asyncio
async def test_setup_rejected_when_admin_exists(client):
    payload = {
        "email": "first@codefy.dev",
        "password": "supersecret123",
        "display_name": "First",
    }
    r = await client.post("/api/system/setup", json=payload)
    assert r.status_code == 201

    payload2 = {
        "email": "second@codefy.dev",
        "password": "supersecret123",
        "display_name": "Second",
    }
    r = await client.post("/api/system/setup", json=payload2)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_setup_login_works(client):
    payload = {
        "email": "login-test@codefy.dev",
        "password": "supersecret123",
        "display_name": "LoginTest",
    }
    r = await client.post("/api/system/setup", json=payload)
    assert r.status_code == 201

    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": payload["email"], "password": payload["password"]},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    r = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    me = r.json()
    assert me["role"] == "admin"
    assert me["is_superuser"] is True


@pytest.mark.asyncio
async def test_setup_validates_password_length(client):
    r = await client.post(
        "/api/system/setup",
        json={"email": "x@y.com", "password": "short", "display_name": "X"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_setup_validates_email(client):
    r = await client.post(
        "/api/system/setup",
        json={"email": "not-an-email", "password": "supersecret123", "display_name": "X"},
    )
    assert r.status_code == 422
