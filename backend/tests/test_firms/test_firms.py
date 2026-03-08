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


@pytest.mark.asyncio
async def test_attorney_creates_firm(client):
    token = await register_user(client, "att@test.com", "attorney")
    resp = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Demo Law Firm"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Demo Law Firm"


@pytest.mark.asyncio
async def test_client_cannot_create_firm(client):
    token = await register_user(client, "cli@test.com", "primary_client")
    resp = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Should Fail"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_attorney_creates_template(client):
    token = await register_user(client, "att2@test.com", "attorney")
    firm_resp = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test Firm"},
    )
    firm_id = firm_resp.json()["id"]

    checklist = [
        {"item_type": "lease_copy", "label": "Copy of lease", "required": True}
    ]
    resp = await client.post(
        f"/firms/{firm_id}/templates",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Landlord-Tenant", "checklist": checklist},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Landlord-Tenant"
    assert len(resp.json()["checklist"]) == 1
