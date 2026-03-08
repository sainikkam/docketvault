from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest


async def register_user(client, email, role="attorney"):
    resp = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "testpass123",
            "role": role,
            "display_name": f"User {email}",
        },
    )
    return resp.json()["access_token"]


async def setup_matter_with_client(client):
    att_token = await register_user(client, "att@oauth.com", "attorney")
    firm = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"name": "OAuth Firm"},
    )
    firm_id = firm.json()["id"]
    template = await client.post(
        f"/firms/{firm_id}/templates",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"name": "Template", "checklist": []},
    )
    template_id = template.json()["id"]
    matter = await client.post(
        "/matters",
        headers={"Authorization": f"Bearer {att_token}"},
        json={
            "firm_id": firm_id,
            "template_id": template_id,
            "title": "OAuth Test",
        },
    )
    matter_id = matter.json()["id"]

    invite = await client.post(
        f"/matters/{matter_id}/invitations",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"role": "primary_client"},
    )
    cli_token = await register_user(client, "cli@oauth.com", "primary_client")
    await client.post(
        f"/invitations/{invite.json()['token']}/accept",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    return att_token, cli_token, matter_id


@pytest.mark.asyncio
async def test_authorize_returns_url(client):
    token = await register_user(client, "auth@oauth.com", "primary_client")
    with patch("app.oauth.router.GoogleOAuthService") as MockSvc:
        mock_instance = MockSvc.return_value
        mock_instance.get_authorize_url.return_value = (
            "https://accounts.google.com/o/oauth2/auth?client_id=test"
        )
        resp = await client.get(
            "/oauth/google/authorize",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert "authorize_url" in resp.json()
    assert "accounts.google.com" in resp.json()["authorize_url"]


@pytest.mark.asyncio
async def test_callback_stores_account(client, db_session):
    token = await register_user(client, "cb@oauth.com", "primary_client")
    # Get user ID from token
    me = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me.json()["id"]

    with patch("app.oauth.router.GoogleOAuthService") as MockSvc:
        mock_instance = MockSvc.return_value
        mock_instance.exchange_code.return_value = {
            "access_token": "mock_access",
            "refresh_token": "mock_refresh",
            "expires_at": datetime.utcnow() + timedelta(hours=1),
        }
        resp = await client.get(
            f"/oauth/google/callback?code=mock_code&state={user_id}"
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "connected"


@pytest.mark.asyncio
async def test_disconnect(client, db_session):
    token = await register_user(client, "disc@oauth.com", "primary_client")
    me = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me.json()["id"]

    # First connect
    with patch("app.oauth.router.GoogleOAuthService") as MockSvc:
        mock_instance = MockSvc.return_value
        mock_instance.exchange_code.return_value = {
            "access_token": "mock_access",
            "refresh_token": "mock_refresh",
            "expires_at": datetime.utcnow() + timedelta(hours=1),
        }
        await client.get(f"/oauth/google/callback?code=mock_code&state={user_id}")

    # Then disconnect
    with patch("app.oauth.router.GoogleOAuthService") as MockSvc:
        mock_instance = MockSvc.return_value
        mock_instance.revoke_token.return_value = None
        resp = await client.delete(
            "/oauth/google/disconnect",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"


@pytest.mark.asyncio
async def test_drive_import_creates_artifacts(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    me = await client.get("/users/me", headers={"Authorization": f"Bearer {cli_token}"})
    user_id = me.json()["id"]

    # Connect Google account
    with patch("app.oauth.router.GoogleOAuthService") as MockSvc:
        mock_instance = MockSvc.return_value
        mock_instance.exchange_code.return_value = {
            "access_token": "mock_access",
            "refresh_token": "mock_refresh",
            "expires_at": datetime.utcnow() + timedelta(hours=1),
        }
        await client.get(f"/oauth/google/callback?code=mock_code&state={user_id}")

    # Import files
    with patch("app.oauth.router.GoogleOAuthService") as MockSvc:
        mock_instance = MockSvc.return_value
        mock_instance.ensure_fresh_token = AsyncMock()
        mock_instance.download_file.return_value = (
            b"fake file content",
            {
                "id": "drive_file_1",
                "name": "lease.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "2026-01-15T10:00:00Z",
            },
        )
        resp = await client.post(
            f"/matters/{matter_id}/import/drive",
            headers={"Authorization": f"Bearer {cli_token}"},
            json={"file_ids": ["drive_file_1"]},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 1
    assert len(data["artifact_ids"]) == 1

    # Verify artifact was created with Drive metadata
    artifacts = await client.get(
        f"/matters/{matter_id}/artifacts",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert len(artifacts.json()) == 1
    art = artifacts.json()[0]
    assert art["source_system"] == "drive"
    assert art["sha256"] is not None
