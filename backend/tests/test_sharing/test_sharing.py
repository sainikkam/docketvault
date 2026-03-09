import pytest

from app.extraction.models import Extraction
from app.sharing.models import SharePolicy


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
    att_token = await register_user(client, "att_share@ext.com", "attorney")
    firm = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"name": "Share Firm"},
    )
    firm_id = firm.json()["id"]
    matter = await client.post(
        "/matters",
        headers={"Authorization": f"Bearer {att_token}"},
        json={
            "firm_id": firm_id,
            "title": "Sharing Test",
        },
    )
    matter_id = matter.json()["id"]
    invite = await client.post(
        f"/matters/{matter_id}/invitations",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"role": "primary_client"},
    )
    cli_token = await register_user(client, "cli_share@ext.com", "primary_client")
    await client.post(
        f"/invitations/{invite.json()['token']}/accept",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    return att_token, cli_token, matter_id


async def upload_artifact(client, cli_token, matter_id, filename="doc.jpg", mime="image/jpeg"):
    upload = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", (filename, b"\xff\xd8\xff fake", mime))],
    )
    return upload.json()["artifacts"][0]


@pytest.mark.asyncio
async def test_share_preview_creates_policies(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    artifact_id = await upload_artifact(client, cli_token, matter_id)

    resp = await client.get(
        f"/matters/{matter_id}/share-preview",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["matter_id"] == matter_id
    # Should have at least one category
    all_items = []
    for items in data["categories"].values():
        all_items.extend(items)
    assert len(all_items) >= 1
    assert all_items[0]["state"] == "pending"


@pytest.mark.asyncio
async def test_batch_approve(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    artifact_id = await upload_artifact(client, cli_token, matter_id)

    # First get preview to create policies
    await client.get(
        f"/matters/{matter_id}/share-preview",
        headers={"Authorization": f"Bearer {cli_token}"},
    )

    # Approve the artifact
    resp = await client.post(
        f"/matters/{matter_id}/share-preview/update",
        headers={"Authorization": f"Bearer {cli_token}"},
        json={
            "updates": [{"artifact_id": artifact_id, "state": "approved"}]
        },
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert results[0]["state"] == "approved"


@pytest.mark.asyncio
async def test_sensitive_item_requires_acknowledgment(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    artifact_id = await upload_artifact(client, cli_token, matter_id)

    # Create extraction with sensitivity flag
    extraction = Extraction(
        artifact_id=artifact_id,
        extracted_text="SSN: 123-45-6789",
        summary="Document with SSN",
        doc_type_guess="other",
        structured_claims={},
        sensitivity_flags={"contains_ssn": True, "contains_account_number": False},
        confidence=0.9,
        verification_state="high_confidence",
    )
    db_session.add(extraction)
    await db_session.commit()

    # Get preview to create policies
    await client.get(
        f"/matters/{matter_id}/share-preview",
        headers={"Authorization": f"Bearer {cli_token}"},
    )

    # Try approving without acknowledgment → should fail
    resp = await client.post(
        f"/matters/{matter_id}/share-preview/update",
        headers={"Authorization": f"Bearer {cli_token}"},
        json={
            "updates": [{"artifact_id": artifact_id, "state": "approved"}]
        },
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert "error" in results[0]
    assert "sensitive" in results[0]["error"]

    # Approve with acknowledgment → should succeed
    resp2 = await client.post(
        f"/matters/{matter_id}/share-preview/update",
        headers={"Authorization": f"Bearer {cli_token}"},
        json={
            "updates": [
                {
                    "artifact_id": artifact_id,
                    "state": "approved",
                    "acknowledge_sensitive": True,
                }
            ]
        },
    )
    assert resp2.status_code == 200
    assert resp2.json()["results"][0]["state"] == "approved"


@pytest.mark.asyncio
async def test_approve_all(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    await upload_artifact(client, cli_token, matter_id, "a.jpg")
    await upload_artifact(client, cli_token, matter_id, "b.jpg")

    # Get preview to create policies
    await client.get(
        f"/matters/{matter_id}/share-preview",
        headers={"Authorization": f"Bearer {cli_token}"},
    )

    resp = await client.post(
        f"/matters/{matter_id}/share-preview/approve-all",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["approved"] >= 2


@pytest.mark.asyncio
async def test_revoke_all(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    await upload_artifact(client, cli_token, matter_id)

    # Preview → approve all → revoke all
    await client.get(
        f"/matters/{matter_id}/share-preview",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    await client.post(
        f"/matters/{matter_id}/share-preview/approve-all",
        headers={"Authorization": f"Bearer {cli_token}"},
    )

    resp = await client.post(
        f"/matters/{matter_id}/revoke",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["revoked"] >= 1


@pytest.mark.asyncio
async def test_attorney_cannot_access_share_preview(client, db_session):
    att_token, _, matter_id = await setup_matter_with_client(client)

    resp = await client.get(
        f"/matters/{matter_id}/share-preview",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    assert resp.status_code == 403
