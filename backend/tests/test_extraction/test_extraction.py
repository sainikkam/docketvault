import pytest

from app.extraction.models import Extraction


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
    att_token = await register_user(client, "att@ext.com", "attorney")
    firm = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"name": "Ext Firm"},
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
            "title": "Extraction Test",
        },
    )
    matter_id = matter.json()["id"]
    invite = await client.post(
        f"/matters/{matter_id}/invitations",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"role": "primary_client"},
    )
    cli_token = await register_user(client, "cli@ext.com", "primary_client")
    await client.post(
        f"/invitations/{invite.json()['token']}/accept",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    return att_token, cli_token, matter_id


async def upload_and_create_extraction(client, db_session, cli_token, matter_id):
    """Upload a file and manually create an Extraction record for it."""
    upload = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("receipt.jpg", b"\xff\xd8\xff fake jpeg", "image/jpeg"))],
    )
    artifact_id = upload.json()["artifacts"][0]

    # Manually create extraction (simulating what Celery task would do)
    extraction = Extraction(
        artifact_id=artifact_id,
        extracted_text="Rent payment $1200 received",
        summary="A rent payment receipt for $1,200.",
        doc_type_guess="receipt",
        structured_claims={
            "amounts": [
                {
                    "value": "$1,200",
                    "citation": {
                        "page": 1,
                        "region": {"x": 0.1, "y": 0.3, "w": 0.2, "h": 0.05},
                    },
                }
            ],
            "parties": [
                {
                    "value": "John Doe",
                    "citation": {
                        "page": 1,
                        "region": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.05},
                    },
                }
            ],
        },
        sensitivity_flags={
            "contains_ssn": False,
            "contains_account_number": False,
            "contains_medical": False,
            "contains_minor_info": False,
        },
        confidence=0.92,
        verification_state="high_confidence",
    )
    db_session.add(extraction)
    await db_session.commit()
    await db_session.refresh(extraction)
    return artifact_id, extraction


@pytest.mark.asyncio
async def test_get_extraction(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    artifact_id, extraction = await upload_and_create_extraction(
        client, db_session, cli_token, matter_id
    )

    resp = await client.get(
        f"/artifacts/{artifact_id}/extraction",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["artifact_id"] == artifact_id
    assert data["doc_type_guess"] == "receipt"
    assert data["confidence"] == 0.92
    assert data["verification_state"] == "high_confidence"
    assert "amounts" in data["structured_claims"]
    assert data["sensitivity_flags"]["contains_ssn"] is False


@pytest.mark.asyncio
async def test_get_extraction_not_found(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    # Upload file but don't create extraction
    upload = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("doc.pdf", b"%PDF-1.4 content", "application/pdf"))],
    )
    artifact_id = upload.json()["artifacts"][0]

    resp = await client.get(
        f"/artifacts/{artifact_id}/extraction",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_verify_extraction(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    artifact_id, extraction = await upload_and_create_extraction(
        client, db_session, cli_token, matter_id
    )

    resp = await client.patch(
        f"/extractions/{extraction.id}/verify",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "verified"

    # Verify the state persisted
    resp2 = await client.get(
        f"/artifacts/{artifact_id}/extraction",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp2.json()["verification_state"] == "verified"


@pytest.mark.asyncio
async def test_attorney_cannot_verify(client, db_session):
    att_token, cli_token, matter_id = await setup_matter_with_client(client)
    artifact_id, extraction = await upload_and_create_extraction(
        client, db_session, cli_token, matter_id
    )

    # Attorney should not be able to verify
    resp = await client.patch(
        f"/extractions/{extraction.id}/verify",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_extraction_has_citations(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    artifact_id, extraction = await upload_and_create_extraction(
        client, db_session, cli_token, matter_id
    )

    resp = await client.get(
        f"/artifacts/{artifact_id}/extraction",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    data = resp.json()
    claims = data["structured_claims"]
    # Verify every claim has a citation with bounding box
    for field_name, claim_list in claims.items():
        for claim in claim_list:
            assert "citation" in claim
            assert "region" in claim["citation"]
            region = claim["citation"]["region"]
            assert all(k in region for k in ("x", "y", "w", "h"))


@pytest.mark.asyncio
async def test_confidence_threshold_logic(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)

    # Upload and create extraction with low confidence
    upload = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("blurry.jpg", b"\xff\xd8\xff blurry", "image/jpeg"))],
    )
    artifact_id = upload.json()["artifacts"][0]

    extraction = Extraction(
        artifact_id=artifact_id,
        extracted_text="Unclear text",
        summary="A blurry photo.",
        doc_type_guess="photo",
        structured_claims={},
        sensitivity_flags={},
        confidence=0.45,
        verification_state="needs_review",
    )
    db_session.add(extraction)
    await db_session.commit()

    resp = await client.get(
        f"/artifacts/{artifact_id}/extraction",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    data = resp.json()
    assert data["confidence"] == 0.45
    assert data["verification_state"] == "needs_review"
