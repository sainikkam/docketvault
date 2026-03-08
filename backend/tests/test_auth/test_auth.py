import pytest


@pytest.mark.asyncio
async def test_register_returns_tokens(client):
    resp = await client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "password": "testpass123",
            "role": "attorney",
            "display_name": "Test User",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {
        "email": "dup@example.com",
        "password": "testpass123",
        "role": "attorney",
        "display_name": "User",
    }
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password(client):
    resp = await client.post(
        "/auth/register",
        json={
            "email": "short@example.com",
            "password": "short",
            "role": "attorney",
            "display_name": "User",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_login_correct_password(client):
    await client.post(
        "/auth/register",
        json={
            "email": "login@example.com",
            "password": "testpass123",
            "role": "attorney",
            "display_name": "Login User",
        },
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "testpass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/auth/register",
        json={
            "email": "wrong@example.com",
            "password": "testpass123",
            "role": "attorney",
            "display_name": "User",
        },
    )
    resp = await client.post(
        "/auth/login",
        json={"email": "wrong@example.com", "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_valid_token(client):
    reg = await client.post(
        "/auth/register",
        json={
            "email": "refresh@example.com",
            "password": "testpass123",
            "role": "attorney",
            "display_name": "User",
        },
    )
    refresh_token = reg.json()["refresh_token"]
    resp = await client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_refresh_invalid_token(client):
    resp = await client.post(
        "/auth/refresh",
        json={"refresh_token": "invalid-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_valid_token(client):
    reg = await client.post(
        "/auth/register",
        json={
            "email": "me@example.com",
            "password": "testpass123",
            "role": "attorney",
            "display_name": "Me User",
        },
    )
    token = reg.json()["access_token"]
    resp = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "me@example.com"
    assert data["role"] == "attorney"
    assert data["display_name"] == "Me User"
    assert data["email_verified"] is True


@pytest.mark.asyncio
async def test_get_me_with_invalid_token(client):
    resp = await client.get(
        "/users/me",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_me(client):
    reg = await client.post(
        "/auth/register",
        json={
            "email": "update@example.com",
            "password": "testpass123",
            "role": "attorney",
            "display_name": "Old Name",
        },
    )
    token = reg.json()["access_token"]
    resp = await client.patch(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "New Name"},
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "New Name"
