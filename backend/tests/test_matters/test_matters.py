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


async def setup_firm(client, token):
    """Create a firm and return its ID. Template creation removed; template_id is optional on matters."""
    firm = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test Firm"},
    )
    return firm.json()["id"]


@pytest.mark.asyncio
async def test_attorney_creates_matter(client):
    token = await register_user(client, "att@m.com", "attorney")
    firm_id = await setup_firm(client, token)

    resp = await client.post(
        "/matters",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "firm_id": firm_id,
            "title": "Smith v. Landlord",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Smith v. Landlord"
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_client_cannot_create_matter(client):
    att_token = await register_user(client, "att2@m.com", "attorney")
    firm_id = await setup_firm(client, att_token)

    cli_token = await register_user(client, "cli@m.com", "primary_client")
    resp = await client.post(
        "/matters",
        headers={"Authorization": f"Bearer {cli_token}"},
        json={
            "firm_id": firm_id,
            "title": "Should Fail",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_invite_accept_flow(client):
    att_token = await register_user(client, "att3@m.com", "attorney")
    firm_id = await setup_firm(client, att_token)

    matter = await client.post(
        "/matters",
        headers={"Authorization": f"Bearer {att_token}"},
        json={
            "firm_id": firm_id,
            "title": "Invite Test",
        },
    )
    matter_id = matter.json()["id"]

    # Generate invite
    invite_resp = await client.post(
        f"/matters/{matter_id}/invitations",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"role": "primary_client"},
    )
    assert invite_resp.status_code == 201
    invite_token = invite_resp.json()["token"]

    # Client accepts invite
    cli_token = await register_user(client, "cli2@m.com", "primary_client")
    accept_resp = await client.post(
        f"/invitations/{invite_token}/accept",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert accept_resp.status_code == 200
    assert accept_resp.json()["role"] == "primary_client"


@pytest.mark.asyncio
async def test_invite_already_used(client):
    att_token = await register_user(client, "att4@m.com", "attorney")
    firm_id = await setup_firm(client, att_token)

    matter = await client.post(
        "/matters",
        headers={"Authorization": f"Bearer {att_token}"},
        json={
            "firm_id": firm_id,
            "title": "Reuse Test",
        },
    )
    matter_id = matter.json()["id"]

    invite = await client.post(
        f"/matters/{matter_id}/invitations",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"role": "primary_client"},
    )
    invite_token = invite.json()["token"]

    # First accept
    cli1 = await register_user(client, "cli3@m.com", "primary_client")
    await client.post(
        f"/invitations/{invite_token}/accept",
        headers={"Authorization": f"Bearer {cli1}"},
    )

    # Second accept → 400
    cli2 = await register_user(client, "cli4@m.com", "primary_client")
    resp = await client.post(
        f"/invitations/{invite_token}/accept",
        headers={"Authorization": f"Bearer {cli2}"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_audit_log(client):
    att_token = await register_user(client, "att5@m.com", "attorney")
    firm_id = await setup_firm(client, att_token)

    matter = await client.post(
        "/matters",
        headers={"Authorization": f"Bearer {att_token}"},
        json={
            "firm_id": firm_id,
            "title": "Audit Test",
        },
    )
    matter_id = matter.json()["id"]

    # Generate an invite to create more audit entries
    await client.post(
        f"/matters/{matter_id}/invitations",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"role": "primary_client"},
    )

    resp = await client.get(
        f"/matters/{matter_id}/audit-log",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    assert resp.status_code == 200
    actions = [e["action"] for e in resp.json()]
    assert "matter.created" in actions
    assert "invitation.created" in actions
