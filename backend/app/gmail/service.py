"""Gmail API integration service.

Handles searching, reading, and downloading Gmail messages and attachments.
Uses the same Google OAuth tokens stored in ConnectedAccount.
"""

import base64

import anthropic
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import Settings
from app.gmail.models import GmailMessagePreview

settings = Settings()


# ── LLM prompt for converting evidence requests to Gmail queries ──

QUERY_GEN_SYSTEM = (
    "You are a Gmail search query generator for legal evidence gathering. "
    "Given an attorney's evidence request, produce the best Gmail search query "
    "to find matching emails in the client's inbox.\n\n"
    "Use Gmail search operators:\n"
    "- from: / to: for sender/recipient\n"
    "- subject: for subject line\n"
    "- after:YYYY/MM/DD before:YYYY/MM/DD for date ranges\n"
    "- has:attachment for emails with files\n"
    "- filename:pdf/xlsx etc. for attachment types\n"
    "- OR for alternatives, quotes for exact phrases\n\n"
    "Return ONLY the Gmail query string. No explanation, no quotes around it."
)

QUERY_GEN_USER = """Evidence request:
Title: {title}
Description: {description}
Category: {category}
Keywords: {keywords}
Date range: {date_start} to {date_end}
Source system: {source_system}

Generate the best Gmail search query to find emails matching this request."""


def generate_gmail_query(
    title: str,
    description: str = "",
    category: str = "",
    keywords: list[str] | None = None,
    date_start: str = "",
    date_end: str = "",
    source_system: str = "",
) -> str:
    """Use the LLM to convert an evidence request into a Gmail search query.

    Takes the structured fields from an EvidenceRequest and produces
    a Gmail-compatible search string using Gmail operators.
    """
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=settings.LLM_MODEL,
        system=QUERY_GEN_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": QUERY_GEN_USER.format(
                    title=title,
                    description=description,
                    category=category or "any",
                    keywords=", ".join(keywords) if keywords else "none specified",
                    date_start=date_start or "any",
                    date_end=date_end or "present",
                    source_system=source_system or "any",
                ),
            }
        ],
        max_tokens=200,
    )

    return response.content[0].text.strip().strip('"').strip("'")


def _build_gmail_service(access_token: str):
    """Build an authenticated Gmail API service client."""
    creds = Credentials(token=access_token)
    return build("gmail", "v1", credentials=creds)


def search_emails(
    access_token: str,
    query: str,
    max_results: int = 25,
) -> list[GmailMessagePreview]:
    """Search Gmail and return message previews.

    Uses server-side search (same syntax as Gmail search bar),
    then fetches headers for each result to build previews.
    Only downloads metadata — no full bodies or attachments.
    """
    service = _build_gmail_service(access_token)

    # Search for matching message IDs
    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )

    message_ids = result.get("messages", [])
    if not message_ids:
        return []

    # Fetch metadata for each message (headers + snippet)
    previews = []
    for msg_stub in message_ids:
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=msg_stub["id"],
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            )
            .execute()
        )

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}

        # Count attachments by checking parts
        attachment_count = _count_attachments(msg.get("payload", {}))

        previews.append(
            GmailMessagePreview(
                message_id=msg["id"],
                subject=headers.get("Subject", "(no subject)"),
                sender=headers.get("From", "Unknown"),
                date=headers.get("Date"),
                snippet=msg.get("snippet", ""),
                has_attachments=attachment_count > 0,
                attachment_count=attachment_count,
            )
        )

    return previews


def _count_attachments(payload: dict) -> int:
    """Recursively count attachments in a Gmail message payload."""
    count = 0
    if payload.get("filename") and payload.get("body", {}).get("attachmentId"):
        count += 1
    for part in payload.get("parts", []):
        count += _count_attachments(part)
    return count


def get_full_message(access_token: str, message_id: str) -> dict:
    """Fetch the full Gmail message including body text and attachment metadata.

    Returns a dict with: subject, sender, date, body_text, attachments list.
    """
    service = _build_gmail_service(access_token)

    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )

    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body_text = _extract_body_text(msg.get("payload", {}))
    attachments = _extract_attachment_info(msg.get("payload", {}))

    return {
        "message_id": message_id,
        "subject": headers.get("Subject", "(no subject)"),
        "sender": headers.get("From", "Unknown"),
        "to": headers.get("To", ""),
        "date": headers.get("Date", ""),
        "body_text": body_text,
        "attachments": attachments,
        "label_ids": msg.get("labelIds", []),
        "internal_date_ms": msg.get("internalDate"),
    }


def _extract_body_text(payload: dict) -> str:
    """Extract plain text body from a Gmail message payload.

    Prefers text/plain, falls back to text/html with basic cleanup.
    Handles both single-part and multipart messages.
    """
    # Single-part message
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime == "text/plain" and body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    # Multipart: search parts recursively, prefer text/plain
    parts = payload.get("parts", [])
    plain_text = ""
    html_text = ""

    for part in parts:
        part_mime = part.get("mimeType", "")
        part_data = part.get("body", {}).get("data")

        if part_mime == "text/plain" and part_data:
            plain_text += base64.urlsafe_b64decode(part_data).decode(
                "utf-8", errors="replace"
            )
        elif part_mime == "text/html" and part_data:
            html_text += base64.urlsafe_b64decode(part_data).decode(
                "utf-8", errors="replace"
            )
        elif part.get("parts"):
            # Nested multipart (e.g. multipart/alternative inside multipart/mixed)
            nested = _extract_body_text(part)
            if nested:
                plain_text += nested

    return plain_text or html_text


def _extract_attachment_info(payload: dict) -> list[dict]:
    """Get metadata for all attachments in a message (no download yet)."""
    attachments = []

    if payload.get("filename") and payload.get("body", {}).get("attachmentId"):
        attachments.append(
            {
                "attachment_id": payload["body"]["attachmentId"],
                "filename": payload["filename"],
                "mime_type": payload.get("mimeType", "application/octet-stream"),
                "size": payload.get("body", {}).get("size", 0),
            }
        )

    for part in payload.get("parts", []):
        attachments.extend(_extract_attachment_info(part))

    return attachments


def download_attachment(
    access_token: str, message_id: str, attachment_id: str
) -> bytes:
    """Download a specific attachment's raw bytes from a Gmail message."""
    service = _build_gmail_service(access_token)

    att = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )

    data = att.get("data", "")
    return base64.urlsafe_b64decode(data)
