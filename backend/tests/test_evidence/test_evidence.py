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
    """Create firm/template/matter as attorney, invite+accept as client. Returns (att_token, cli_token, matter_id)."""
    att_token = await register_user(client, "att@ev.com", "attorney")

    firm = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"name": "Ev Firm"},
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
            "title": "Evidence Test",
        },
    )
    matter_id = matter.json()["id"]

    invite = await client.post(
        f"/matters/{matter_id}/invitations",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"role": "primary_client"},
    )
    invite_token = invite.json()["token"]

    cli_token = await register_user(client, "cli@ev.com", "primary_client")
    await client.post(
        f"/invitations/{invite_token}/accept",
        headers={"Authorization": f"Bearer {cli_token}"},
    )

    return att_token, cli_token, matter_id


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_upload_single_pdf(client):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    resp = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("lease.pdf", pdf_bytes, "application/pdf"))],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["uploaded"] == 1
    assert len(data["artifacts"]) == 1


@pytest.mark.asyncio
async def test_upload_zip_with_files(client):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    zip_bytes = make_zip(
        {
            "doc1.txt": b"Some text content",
            "photo.jpg": b"\xff\xd8\xff fake jpeg",
            "receipt.pdf": b"%PDF-1.4 receipt",
        }
    )
    resp = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("bundle.zip", zip_bytes, "application/zip"))],
    )
    assert resp.status_code == 201
    assert resp.json()["uploaded"] == 3


@pytest.mark.asyncio
async def test_upload_unknown_format(client):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    resp = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("data.xyz", b"unknown data", "application/octet-stream"))],
    )
    assert resp.status_code == 201
    artifact_id = resp.json()["artifacts"][0]

    detail = await client.get(
        f"/artifacts/{artifact_id}",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert detail.json()["status"] == "needs_review"


@pytest.mark.asyncio
async def test_attorney_cannot_upload(client):
    att_token, _, matter_id = await setup_matter_with_client(client)
    resp = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {att_token}"},
        files=[("files", ("test.pdf", b"content", "application/pdf"))],
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_artifacts(client):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("a.pdf", b"pdf1", "application/pdf"))],
    )
    await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("b.png", b"png1", "image/png"))],
    )
    resp = await client.get(
        f"/matters/{matter_id}/artifacts",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_artifact_detail(client):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    upload = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("doc.pdf", b"%PDF-1.4 content", "application/pdf"))],
    )
    artifact_id = upload.json()["artifacts"][0]
    resp = await client.get(
        f"/artifacts/{artifact_id}",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mime_type"] == "application/pdf"
    assert data["original_filename"] == "doc.pdf"
    assert data["sha256"] is not None


@pytest.mark.asyncio
async def test_download_artifact(client):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    upload = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("dl.pdf", b"download me", "application/pdf"))],
    )
    artifact_id = upload.json()["artifacts"][0]
    resp = await client.get(
        f"/artifacts/{artifact_id}/download",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 200
    assert "url" in resp.json()
