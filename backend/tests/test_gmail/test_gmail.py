"""Tests for Gmail search and import endpoints.

Mocks the Gmail API and LLM calls to test the full flow:
search → preview → import → artifacts created.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

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
    """Create a firm, matter, and invite a client. Returns tokens + IDs."""
    att_token = await register_user(client, "att@gmail-test.com", "attorney")
    firm = await client.post(
        "/firms",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"name": "Gmail Test Firm"},
    )
    firm_id = firm.json()["id"]
    matter = await client.post(
        "/matters",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"firm_id": firm_id, "title": "Gmail Test Matter"},
    )
    matter_id = matter.json()["id"]

    invite = await client.post(
        f"/matters/{matter_id}/invitations",
        headers={"Authorization": f"Bearer {att_token}"},
        json={"role": "primary_client"},
    )
    cli_token = await register_user(client, "cli@gmail-test.com", "primary_client")
    await client.post(
        f"/invitations/{invite.json()['token']}/accept",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    return att_token, cli_token, matter_id


async def connect_google(client, cli_token):
    """Simulate connecting a Google account via OAuth callback."""
    me = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {cli_token}"}
    )
    user_id = me.json()["id"]

    with patch("app.oauth.router.GoogleOAuthService") as MockSvc:
        mock_instance = MockSvc.return_value
        mock_instance.exchange_code.return_value = {
            "access_token": "mock_gmail_access",
            "refresh_token": "mock_gmail_refresh",
            "expires_at": datetime.utcnow() + timedelta(hours=1),
        }
        await client.get(
            f"/oauth/google/callback?code=mock_code&state={user_id}"
        )
    return user_id


# ── Mock data ─────────────────────────────────────────────────

MOCK_SEARCH_RESULTS = {
    "messages": [
        {"id": "msg_001"},
        {"id": "msg_002"},
    ]
}

MOCK_MSG_METADATA_1 = {
    "id": "msg_001",
    "snippet": "Your rent payment of $1,200 has been received",
    "payload": {
        "headers": [
            {"name": "Subject", "value": "Rent Payment Confirmation"},
            {"name": "From", "value": "landlord@example.com"},
            {"name": "Date", "value": "Mon, 15 Jan 2024 10:00:00 -0600"},
        ],
        "mimeType": "text/plain",
        "body": {"size": 200},
        "parts": [],
    },
}

MOCK_MSG_METADATA_2 = {
    "id": "msg_002",
    "snippet": "Please find attached your lease agreement",
    "payload": {
        "headers": [
            {"name": "Subject", "value": "Lease Agreement - Unit 4B"},
            {"name": "From", "value": "property@mgmt.com"},
            {"name": "Date", "value": "Fri, 01 Dec 2023 14:30:00 -0600"},
        ],
        "mimeType": "multipart/mixed",
        "body": {"size": 0},
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"size": 150},
                "parts": [],
            },
            {
                "filename": "lease.pdf",
                "mimeType": "application/pdf",
                "body": {
                    "attachmentId": "att_001",
                    "size": 50000,
                },
            },
        ],
    },
}

# Full message data (for import)
import base64

MOCK_FULL_MSG_1 = {
    **MOCK_MSG_METADATA_1,
    "internalDate": "1705330800000",
    "labelIds": ["INBOX"],
    "payload": {
        **MOCK_MSG_METADATA_1["payload"],
        "body": {
            "size": 200,
            "data": base64.urlsafe_b64encode(
                b"Your rent payment of $1,200 has been received. Thank you."
            ).decode(),
        },
    },
}


def _build_mock_gmail_service(search_results, metadata_map, full_msg_map=None):
    """Build a mock Gmail API service that returns canned responses."""
    mock_service = MagicMock()

    # users().messages().list()
    mock_list = MagicMock()
    mock_list.execute.return_value = search_results
    mock_service.users.return_value.messages.return_value.list.return_value = mock_list

    # users().messages().get() — returns different data per message ID
    def mock_get(userId, id, format="metadata", **kwargs):
        mock_resp = MagicMock()
        if format == "full" and full_msg_map:
            mock_resp.execute.return_value = full_msg_map.get(id, {})
        else:
            mock_resp.execute.return_value = metadata_map.get(id, {})
        return mock_resp

    mock_service.users.return_value.messages.return_value.get.side_effect = mock_get

    return mock_service


# ── Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gmail_search_with_raw_query(client, db_session):
    """Search Gmail with a raw query string and get previews back."""
    _, cli_token, matter_id = await setup_matter_with_client(client)
    await connect_google(client, cli_token)

    mock_service = _build_mock_gmail_service(
        MOCK_SEARCH_RESULTS,
        {"msg_001": MOCK_MSG_METADATA_1, "msg_002": MOCK_MSG_METADATA_2},
    )

    with (
        patch("app.gmail.router.GoogleOAuthService") as MockOAuth,
        patch("app.gmail.service.build", return_value=mock_service),
    ):
        MockOAuth.return_value.ensure_fresh_token = AsyncMock()

        resp = await client.post(
            f"/matters/{matter_id}/gmail/search",
            headers={"Authorization": f"Bearer {cli_token}"},
            json={"raw_query": "rent payment receipt", "max_results": 10},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "rent payment receipt"
    assert data["total_results"] == 2
    assert len(data["messages"]) == 2

    # First message: no attachments
    assert data["messages"][0]["subject"] == "Rent Payment Confirmation"
    assert data["messages"][0]["sender"] == "landlord@example.com"
    assert data["messages"][0]["has_attachments"] is False

    # Second message: has a PDF attachment
    assert data["messages"][1]["subject"] == "Lease Agreement - Unit 4B"
    assert data["messages"][1]["has_attachments"] is True
    assert data["messages"][1]["attachment_count"] == 1


@pytest.mark.asyncio
async def test_gmail_search_with_evidence_request(client, db_session):
    """Search Gmail using an evidence request ID — LLM generates the query."""
    att_token, cli_token, matter_id = await setup_matter_with_client(client)
    await connect_google(client, cli_token)

    # Create an evidence request
    req_resp = await client.post(
        f"/matters/{matter_id}/requests",
        headers={"Authorization": f"Bearer {att_token}"},
        json={
            "title": "Rent payment receipts Jan-Jun 2024",
            "description": "All receipts or confirmations of rent payments",
            "category": "financial",
            "keywords": ["rent", "payment", "receipt"],
            "date_range_start": "2024-01-01",
            "date_range_end": "2024-06-30",
        },
    )
    request_id = req_resp.json()["id"]

    mock_service = _build_mock_gmail_service(
        MOCK_SEARCH_RESULTS,
        {"msg_001": MOCK_MSG_METADATA_1, "msg_002": MOCK_MSG_METADATA_2},
    )

    with (
        patch("app.gmail.router.GoogleOAuthService") as MockOAuth,
        patch("app.gmail.service.build", return_value=mock_service),
        patch("app.gmail.service.anthropic") as MockAnthropic,
    ):
        MockOAuth.return_value.ensure_fresh_token = AsyncMock()

        # Mock LLM response: the generated Gmail query
        mock_llm = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="rent payment receipt after:2024/01/01 before:2024/07/01")]
        mock_llm.messages.create.return_value = mock_msg
        MockAnthropic.Anthropic.return_value = mock_llm

        resp = await client.post(
            f"/matters/{matter_id}/gmail/search",
            headers={"Authorization": f"Bearer {cli_token}"},
            json={"request_id": request_id},
        )

    assert resp.status_code == 200
    data = resp.json()
    # The query should be what the LLM generated
    assert "rent" in data["query"]
    assert data["total_results"] == 2


@pytest.mark.asyncio
async def test_gmail_import_creates_records(client, db_session):
    """Importing Gmail messages creates Records and Artifacts."""
    _, cli_token, matter_id = await setup_matter_with_client(client)
    await connect_google(client, cli_token)

    mock_service = _build_mock_gmail_service(
        MOCK_SEARCH_RESULTS,
        {"msg_001": MOCK_MSG_METADATA_1},
        full_msg_map={"msg_001": MOCK_FULL_MSG_1},
    )

    with (
        patch("app.gmail.router.GoogleOAuthService") as MockOAuth,
        patch("app.gmail.service.build", return_value=mock_service),
    ):
        MockOAuth.return_value.ensure_fresh_token = AsyncMock()

        resp = await client.post(
            f"/matters/{matter_id}/gmail/import",
            headers={"Authorization": f"Bearer {cli_token}"},
            json={"message_ids": ["msg_001"], "include_attachments": True},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["imported_emails"] == 1
    assert len(data["record_ids"]) == 1

    # Verify the record was created with Gmail metadata
    records = await client.get(
        f"/matters/{matter_id}/records",
        headers={"Authorization": f"Bearer {cli_token}"},
    )
    gmail_records = [
        r for r in records.json() if r.get("source") == "gmail"
    ]
    assert len(gmail_records) == 1
    assert "Rent Payment Confirmation" in gmail_records[0]["text"]


@pytest.mark.asyncio
async def test_gmail_search_requires_connection(client, db_session):
    """Gmail search fails with 404 if no Google account is connected."""
    _, cli_token, matter_id = await setup_matter_with_client(client)

    resp = await client.post(
        f"/matters/{matter_id}/gmail/search",
        headers={"Authorization": f"Bearer {cli_token}"},
        json={"raw_query": "test"},
    )
    assert resp.status_code == 404
    assert "No Google account" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_gmail_search_requires_query_or_request(client, db_session):
    """Gmail search fails if neither raw_query nor request_id is provided."""
    _, cli_token, matter_id = await setup_matter_with_client(client)
    await connect_google(client, cli_token)

    with patch("app.gmail.router.GoogleOAuthService") as MockOAuth:
        MockOAuth.return_value.ensure_fresh_token = AsyncMock()

        resp = await client.post(
            f"/matters/{matter_id}/gmail/search",
            headers={"Authorization": f"Bearer {cli_token}"},
            json={},
        )

    assert resp.status_code == 400
