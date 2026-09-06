"""
Auth flow tests.

Covers: register, login, /me, duplicate username, wrong password,
missing token, role encoding in JWT.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "newuser",
        "password": "password99",
        "role": "field_officer",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "newuser"
    assert body["role"] == "field_officer"
    assert "password_hash" not in body
    assert "id" in body


@pytest.mark.asyncio
async def test_register_default_role(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "defaultrole",
        "password": "password99",
    })
    assert resp.status_code == 201
    assert resp.json()["role"] == "field_officer"


@pytest.mark.asyncio
async def test_register_admin_role(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "myadmin",
        "password": "adminpass1",
        "role": "admin",
    })
    assert resp.status_code == 201
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    payload = {"username": "dupuser", "password": "password99", "role": "verifier"}
    r1 = await client.post("/auth/register", json=payload)
    r2 = await client.post("/auth/register", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 409
    assert "taken" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "shortpw",
        "password": "abc",       # less than 8 chars
        "role": "field_officer",
    })
    assert resp.status_code == 422   # Pydantic validation error


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    await client.post("/auth/register", json={
        "username": "logintest",
        "password": "loginpass1",
        "role": "verifier",
    })
    resp = await client.post("/auth/login", json={
        "username": "logintest",
        "password": "loginpass1",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/auth/register", json={
        "username": "wrongpw",
        "password": "correct99",
        "role": "field_officer",
    })
    resp = await client.post("/auth/login", json={
        "username": "wrongpw",
        "password": "badpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client: AsyncClient):
    resp = await client.post("/auth/login", json={
        "username": "ghost",
        "password": "doesnotmatter",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client: AsyncClient, admin_token: str):
    resp = await client.get("/auth/me",
                            headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "alice_admin"
    assert body["role"] == "admin"


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_invalid_token(client: AsyncClient):
    resp = await client.get("/auth/me",
                            headers={"Authorization": "Bearer this.is.not.valid"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_jwt_contains_role(client: AsyncClient):
    """Decode JWT without verifying signature and check role claim is present."""
    import base64, json as _json

    await client.post("/auth/register", json={
        "username": "rolecheck",
        "password": "rolecheck9",
        "role": "verifier",
    })
    resp = await client.post("/auth/login", json={
        "username": "rolecheck",
        "password": "rolecheck9",
    })
    token = resp.json()["access_token"]

    # Decode the payload section (middle part) without verifying signature
    payload_b64 = token.split(".")[1]
    # Pad to multiple of 4
    payload_b64 += "=" * (-len(payload_b64) % 4)
    payload = _json.loads(base64.urlsafe_b64decode(payload_b64))

    assert payload.get("role") == "verifier"
    assert "sub" in payload
    assert "exp" in payload
