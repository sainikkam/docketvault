import pytest

from app.enrichment.models import IntakeSummary, MissingItem, TimelineEvent


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
    att_token = await register_user(client, "att_enrich@ext.com", "attorney")
    firm = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"name": "Enrich Firm"},
    )
    firm_id = firm.json()["id"]
    matter = await client.post(
        "/matters",
        headers={"Authorization": f"Bearer {att_token}"},
        json={
            "firm_id": firm_id,
            "title": "Enrichment Test",
        },
    )
    matter_id = matter.json()["id"]
    invite = await client.post(
        f"/matters/{matter_id}/invitations",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"role": "primary_client"},
    )
    cli_token = await register_user(client, "cli_enrich@ext.com", "primary_client")
    await client.post(
        f"/invitations/{invite.json()['token']}/accept",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    return att_token, cli_token, matter_id


async def seed_enrichment_data(db_session, matter_id):
    """Create timeline events, missing items, and intake summary for a matter."""
    from uuid import UUID

    mid = UUID(matter_id)

    te1 = TimelineEvent(
        matter_id=mid,
        event_type="lease_signed",
        title="Lease agreement signed",
        event_ts="2025-01-15T00:00:00",
        actors=["tenant", "landlord"],
        summary="Original lease signed for 12-month term.",
        confidence=0.92,
        verification_state="high_confidence",
        citations=[{"record_id": "rec_001", "excerpt": "Signed lease"}],
        related_record_ids=["rec_001"],
    )
    te2 = TimelineEvent(
        matter_id=mid,
        event_type="notice_received",
        title="Eviction notice served",
        event_ts="2025-09-01T00:00:00",
        actors=["landlord"],
        summary="30-day eviction notice delivered.",
        confidence=0.88,
        verification_state="needs_review",
        citations=[{"record_id": "rec_002", "excerpt": "Notice to vacate"}],
        related_record_ids=["rec_002"],
    )
    mi1 = MissingItem(
        matter_id=mid,
        missing_type="notice_to_vacate",
        description="Referenced in emails but not uploaded as a document.",
        priority="high",
    )
    summary = IntakeSummary(
        matter_id=mid,
        case_overview="The tenant reports a dispute regarding eviction proceedings [rec_001]. A lease was signed in January 2025 [rec_001], and an eviction notice was served in September [rec_002].",
        key_timeline=[
            {"bullet": "Lease signed Jan 2025", "citations": [{"record_id": "rec_001"}]},
            {"bullet": "Eviction notice Sep 2025", "citations": [{"record_id": "rec_002"}]},
        ],
        open_questions=[
            {"question": "Was proper notice given?", "why": "Notice period may be insufficient."},
        ],
    )
    db_session.add_all([te1, te2, mi1, summary])
    await db_session.commit()


@pytest.mark.asyncio
async def test_get_timeline(client, db_session):
    att_token, cli_token, matter_id = await setup_matter_with_client(client)
    await seed_enrichment_data(db_session, matter_id)

    resp = await client.get(
        f"/matters/{matter_id}/timeline",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 2
    assert events[0]["event_type"] == "lease_signed"
    assert events[1]["event_type"] == "notice_received"
    assert events[0]["confidence"] == 0.92


@pytest.mark.asyncio
async def test_verify_timeline_event(client, db_session):
    _, cli_token, matter_id = await setup_matter_with_client(client)
    await seed_enrichment_data(db_session, matter_id)

    # Get timeline events
    resp = await client.get(
        f"/matters/{matter_id}/timeline",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    event_id = resp.json()[1]["id"]  # needs_review event

    # Client verifies
    resp2 = await client.patch(
        f"/timeline-events/{event_id}/verify",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "verified"


@pytest.mark.asyncio
async def test_attorney_cannot_verify_timeline(client, db_session):
    att_token, _, matter_id = await setup_matter_with_client(client)
    await seed_enrichment_data(db_session, matter_id)

    resp = await client.get(
        f"/matters/{matter_id}/timeline",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    event_id = resp.json()[0]["id"]

    resp2 = await client.patch(
        f"/timeline-events/{event_id}/verify",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    assert resp2.status_code == 403


@pytest.mark.asyncio
async def test_get_missing_items(client, db_session):
    att_token, _, matter_id = await setup_matter_with_client(client)
    await seed_enrichment_data(db_session, matter_id)

    resp = await client.get(
        f"/matters/{matter_id}/missing-items",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["missing_type"] == "notice_to_vacate"
    assert items[0]["priority"] == "high"
    assert items[0]["status"] == "open"


@pytest.mark.asyncio
async def test_dismiss_missing_item(client, db_session):
    att_token, _, matter_id = await setup_matter_with_client(client)
    await seed_enrichment_data(db_session, matter_id)

    items_resp = await client.get(
        f"/matters/{matter_id}/missing-items",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    item_id = items_resp.json()[0]["id"]

    resp = await client.patch(
        f"/missing-items/{item_id}?status=dismissed",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"


@pytest.mark.asyncio
async def test_get_intake_summary(client, db_session):
    att_token, _, matter_id = await setup_matter_with_client(client)
    await seed_enrichment_data(db_session, matter_id)

    resp = await client.get(
        f"/matters/{matter_id}/intake-summary",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "eviction" in data["case_overview"].lower()
    assert len(data["key_timeline"]) == 2
    assert len(data["open_questions"]) == 1


@pytest.mark.asyncio
async def test_intake_summary_not_found(client, db_session):
    att_token, _, matter_id = await setup_matter_with_client(client)
    # No enrichment data seeded

    resp = await client.get(
        f"/matters/{matter_id}/intake-summary",
        headers={"Authorization": f"Bearer {att_token}"},
    )
    assert resp.status_code == 404
