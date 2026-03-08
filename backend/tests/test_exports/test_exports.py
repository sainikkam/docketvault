import io
import zipfile

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
    att_token = await register_user(client, "att_export@ext.com", "attorney")
    firm = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"name": "Export Firm"},
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
            "title": "Export Test",
        },
    )
    matter_id = matter.json()["id"]
    invite = await client.post(
        f"/matters/{matter_id}/invitations",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"role": "primary_client"},
    )
    cli_token = await register_user(client, "cli_export@ext.com", "primary_client")
    await client.post(
        f"/invitations/{invite.json()['token']}/accept",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    return att_token, cli_token, matter_id


@pytest.mark.asyncio
async def test_export_evidence_pack(client, db_session):
    att_token, cli_token, matter_id = await setup_matter_with_client(client)

    # Upload an artifact
    await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("receipt.jpg", b"\xff\xd8\xff fake jpeg", "image/jpeg"))],
    )

    # Client approves sharing (get preview first to create policies)
    await client.get(
        f"/matters/{matter_id}/share-preview",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    await client.post(
        f"/matters/{matter_id}/share-preview/approve-all",
        headers={"Authorization": f"Bearer {cli_token}"},
    )

    # Lawyer exports evidence pack
    resp = await client.post(
        f"/matters/{matter_id}/export",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    # Verify ZIP contents
    zip_data = io.BytesIO(resp.content)
    with zipfile.ZipFile(zip_data, "r") as zf:
        names = zf.namelist()
        assert "evidence_index.csv" in names
        assert "hash_manifest.csv" in names
        assert "approved_records.jsonl" in names
        assert "audit_excerpt.jsonl" in names


@pytest.mark.asyncio
async def test_client_cannot_export(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)

    resp = await client.post(
        f"/matters/{matter_id}/export",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_empty_matter(client, db_session):
    att_token, _, matter_id = await setup_matter_with_client(client)

    # Export with no approved artifacts — should still produce a valid ZIP
    resp = await client.post(
        f"/matters/{matter_id}/export",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    assert resp.status_code == 200

    zip_data = io.BytesIO(resp.content)
    with zipfile.ZipFile(zip_data, "r") as zf:
        assert "evidence_index.csv" in zf.namelist()
