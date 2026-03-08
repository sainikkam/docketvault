import pytest

from app.notifications.models import Notification


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
    return resp.json()["access_token"], resp.json().get("user_id", resp.json().get("id"))


async def setup_matter_with_client(client):
    att_token, _ = await register_user(client, "att_notif@ext.com", "attorney")
    firm = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"name": "Notif Firm"},
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
            "title": "Notification Test",
        },
    )
    matter_id = matter.json()["id"]
    invite = await client.post(
        f"/matters/{matter_id}/invitations",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"role": "primary_client"},
    )
    cli_token, _ = await register_user(client, "cli_notif@ext.com", "primary_client")
    await client.post(
        f"/invitations/{invite.json()['token']}/accept",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    return att_token, cli_token, matter_id


@pytest.mark.asyncio
async def test_list_notifications_empty(client, db_session):
    att_token, _, _ = await setup_matter_with_client(client)

    resp = await client.get(
        "/notifications",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["unread_count"] == 0
    assert resp.json()["total_returned"] == 0


@pytest.mark.asyncio
async def test_notification_on_request_created(client, db_session):
    att_token, cli_token, matter_id = await setup_matter_with_client(client)

    # Lawyer creates a request → client should get notification
    await client.post(
        f"/matters/{matter_id}/requests",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"title": "Upload your lease", "priority": "high"},
    )

    resp = await client.get(
        "/notifications",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 200
    notifs = resp.json()["notifications"]
    assert len(notifs) >= 1
    assert notifs[0]["type"] == "request.received"
    assert "lease" in notifs[0]["title"].lower()


@pytest.mark.asyncio
async def test_mark_read(client, db_session):
    att_token, cli_token, matter_id = await setup_matter_with_client(client)

    # Create a notification
    await client.post(
        f"/matters/{matter_id}/requests",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"title": "Upload lease"},
    )

    # Get notifications
    resp = await client.get(
        "/notifications",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    notif_id = resp.json()["notifications"][0]["id"]

    # Mark as read
    resp2 = await client.patch(
        f"/notifications/{notif_id}/read",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "read"

    # Verify unread count decreased
    resp3 = await client.get(
        "/notifications",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp3.json()["unread_count"] == 0


@pytest.mark.asyncio
async def test_mark_all_read(client, db_session):
    att_token, cli_token, matter_id = await setup_matter_with_client(client)

    # Create multiple notifications
    await client.post(
        f"/matters/{matter_id}/requests",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"title": "Upload lease"},
    )
    await client.post(
        f"/matters/{matter_id}/requests",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"title": "Upload receipts"},
    )

    resp = await client.post(
        "/notifications/read-all",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["marked_read"] >= 2

    # Verify
    resp2 = await client.get(
        "/notifications",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp2.json()["unread_count"] == 0
