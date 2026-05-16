import pytest


@pytest.mark.asyncio
async def test_register_login_and_me(client):
    register_payload = {
        "email": "alice@codefy.dev",
        "password": "supersecret123",
        "display_name": "Alice",
    }
    r = await client.post("/api/auth/register", json=register_payload)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["email"] == "alice@codefy.dev"
    assert created["display_name"] == "Alice"
    assert created["role"] == "student"

    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": "alice@codefy.dev", "password": "supersecret123"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    token = body["access_token"]

    r = await client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["email"] == "alice@codefy.dev"
    assert me["role"] == "student"


@pytest.mark.asyncio
async def test_me_requires_token(client):
    r = await client.get("/api/users/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_register_rejected(client):
    payload = {
        "email": "dup@codefy.dev",
        "password": "password123",
        "display_name": "Dup",
    }
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 201
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client):
    r = await client.post(
        "/api/auth/register",
        json={"email": "bob@codefy.dev", "password": "rightpass1", "display_name": "Bob"},
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/auth/jwt/login",
        data={"username": "bob@codefy.dev", "password": "wrongpass"},
    )
    assert r.status_code == 400
