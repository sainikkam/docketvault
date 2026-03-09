import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.extraction.models import Extraction
from app.extraction.tasks import _audio_ext


# --- Helper: reuse from test_extraction.py ---


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
    att_token = await register_user(client, "att_audio@ext.com", "attorney")
    firm = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"name": "Audio Firm"},
    )
    firm_id = firm.json()["id"]
    matter = await client.post(
        "/matters",
        headers={"Authorization": f"Bearer {att_token}"},
        json={
            "firm_id": firm_id,
            "title": "Audio Extraction Test",
        },
    )
    matter_id = matter.json()["id"]
    invite = await client.post(
        f"/matters/{matter_id}/invitations",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"role": "primary_client"},
    )
    cli_token = await register_user(client, "cli_audio@ext.com", "primary_client")
    await client.post(
        f"/invitations/{invite.json()['token']}/accept",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    return att_token, cli_token, matter_id


@pytest.mark.asyncio
async def test_audio_extraction_stored_with_transcript(client, db_session):
    """Upload audio → manually create extraction with transcript + key_moments → verify via API."""
    _, cli_token, matter_id = await setup_matter_with_client(client)

    # Upload an audio file
    upload = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("voicemail.mp3", b"\xff\xfb\x90\x00 fake mp3", "audio/mpeg"))],
    )
    assert upload.status_code == 201
    artifact_id = upload.json()["artifacts"][0]

    # Simulate what the extract_audio Celery task would produce
    transcript_segments = [
        {"start_ms": 0, "end_ms": 3200, "text": "Hi, this is your landlord calling about the deposit."},
        {"start_ms": 3200, "end_ms": 8500, "text": "I will not be returning your security deposit."},
        {"start_ms": 8500, "end_ms": 12000, "text": "You have until Friday to dispute this."},
    ]
    key_moments = [
        {
            "title": "Deposit withholding threat",
            "summary": "Landlord states they will not return the security deposit.",
            "start_ms": 3200,
            "end_ms": 8500,
            "confidence": 0.92,
        },
        {
            "title": "Deadline given",
            "summary": "Tenant given until Friday to dispute.",
            "start_ms": 8500,
            "end_ms": 12000,
            "confidence": 0.88,
        },
    ]

    extraction = Extraction(
        artifact_id=artifact_id,
        extracted_text="\n".join(s["text"] for s in transcript_segments),
        transcript=transcript_segments,
        key_moments=key_moments,
        overall_summary="Voicemail from landlord threatening to withhold security deposit, with a Friday deadline to dispute.",
        structured_claims={
            "threats": [
                {
                    "value": "will not return security deposit",
                    "citation": {"start_ms": 3200, "end_ms": 8500},
                }
            ],
            "deadlines": [
                {
                    "value": "Friday",
                    "citation": {"start_ms": 8500, "end_ms": 12000},
                }
            ],
        },
        sensitivity_flags={
            "contains_ssn": False,
            "contains_account_number": False,
            "contains_medical": False,
            "contains_minor_info": False,
            "contains_threat": True,
        },
        confidence=0.90,
        verification_state="high_confidence",
    )
    db_session.add(extraction)
    await db_session.commit()

    # Verify via GET extraction endpoint
    resp = await client.get(
        f"/artifacts/{artifact_id}/extraction",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["artifact_id"] == artifact_id
    assert data["confidence"] == 0.90
    assert data["verification_state"] == "high_confidence"

    # Verify transcript
    assert data["transcript"] is not None
    assert len(data["transcript"]) == 3
    assert data["transcript"][0]["start_ms"] == 0
    assert "landlord" in data["transcript"][0]["text"]

    # Verify key moments
    assert data["key_moments"] is not None
    assert len(data["key_moments"]) == 2
    assert data["key_moments"][0]["title"] == "Deposit withholding threat"

    # Verify overall summary
    assert data["overall_summary"] is not None
    assert "deposit" in data["overall_summary"].lower()

    # Verify structured claims have time-based citations
    claims = data["structured_claims"]
    assert "threats" in claims
    assert claims["threats"][0]["citation"]["start_ms"] == 3200


@pytest.mark.asyncio
async def test_audio_extraction_needs_review_for_low_confidence(client, db_session):
    """Audio extraction with low confidence should have needs_review state."""
    _, cli_token, matter_id = await setup_matter_with_client(client)

    upload = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("noisy.wav", b"RIFF\x00\x00 fake wav", "audio/wav"))],
    )
    artifact_id = upload.json()["artifacts"][0]

    extraction = Extraction(
        artifact_id=artifact_id,
        extracted_text="[inaudible] ... something about rent ...",
        transcript=[
            {"start_ms": 0, "end_ms": 5000, "text": "[inaudible] ... something about rent ..."},
        ],
        key_moments=[],
        overall_summary="Mostly inaudible recording, possibly about rent.",
        structured_claims={},
        sensitivity_flags={
            "contains_ssn": False,
            "contains_account_number": False,
            "contains_medical": False,
            "contains_minor_info": False,
            "contains_threat": False,
        },
        confidence=0.35,
        verification_state="needs_review",
    )
    db_session.add(extraction)
    await db_session.commit()

    resp = await client.get(
        f"/artifacts/{artifact_id}/extraction",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    data = resp.json()
    assert data["confidence"] == 0.35
    assert data["verification_state"] == "needs_review"
    assert data["transcript"] is not None
    assert len(data["transcript"]) == 1


def test_audio_ext_mapping():
    """Verify MIME type to extension mapping."""
    assert _audio_ext("audio/mpeg") == ".mp3"
    assert _audio_ext("audio/mp4") == ".m4a"
    assert _audio_ext("audio/wav") == ".wav"
    assert _audio_ext("audio/webm") == ".webm"
    assert _audio_ext("audio/ogg") == ".ogg"
    assert _audio_ext("audio/unknown") == ".mp3"  # fallback


@pytest.mark.asyncio
async def test_audio_upload_dispatches_correctly(client, db_session):
    """Verify that uploading an audio file goes through the upload flow."""
    _, cli_token, matter_id = await setup_matter_with_client(client)

    # Upload audio — the Celery dispatch will fail silently (no Redis in test),
    # but the artifact should still be created
    upload = await client.post(
        f"/matters/{matter_id}/evidence/upload",
        headers={"Authorization": f"Bearer {cli_token}"},
        files=[("files", ("recording.m4a", b"\x00\x00\x00 fake m4a", "audio/mp4"))],
    )
    assert upload.status_code == 201
    assert len(upload.json()["artifacts"]) == 1

    # Verify artifact is listed
    artifacts = await client.get(
        f"/matters/{matter_id}/artifacts",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert artifacts.status_code == 200
    found = [a for a in artifacts.json() if a["mime_type"] == "audio/mp4"]
    assert len(found) == 1
    assert found[0]["original_filename"] == "recording.m4a"
