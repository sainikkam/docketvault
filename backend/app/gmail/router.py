"""Gmail search & import API endpoints.

Lets clients search their Gmail for evidence matching attorney requests,
preview results, then import selected emails + attachments into a matter.
"""

import hashlib
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.models import User
from app.auth.service import get_current_user
from app.config import Settings
from app.database import get_db
from app.evidence.models import Artifact, Record
from app.evidence.service import enforce_hash_and_check_dedup
from app.gmail.models import (
    GmailImportRequest,
    GmailSearchRequest,
    GmailSearchResponse,
)
from app.gmail.service import (
    download_attachment,
    generate_gmail_query,
    get_full_message,
    search_emails,
)
from app.matters.models import EvidenceRequest
from app.matters.service import log_action, require_matter_role
from app.oauth.models import ConnectedAccount
from app.oauth.service import GoogleOAuthService
from app.storage import get_storage

router = APIRouter()
settings = Settings()

EXTRACTABLE_MIMES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
AUDIO_MIMES = {"audio/mpeg", "audio/mp4", "audio/wav", "audio/webm", "audio/ogg"}


async def _get_google_account(user_id: UUID, db: AsyncSession) -> ConnectedAccount:
    """Fetch the user's connected Google account, or raise 404."""
    result = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.provider == "google",
        )
    )
    account = result.scalars().first()
    if not account:
        raise HTTPException(
            404, "No Google account connected. Use /oauth/google/authorize first."
        )
    return account


def _dispatch_extraction(artifacts: list[Artifact]):
    """Kick off extraction tasks for importable file types."""
    try:
        from app.extraction.tasks import extract_audio, extract_image_pdf

        for a in artifacts:
            if a.status != "processing":
                continue
            if a.mime_type in EXTRACTABLE_MIMES:
                extract_image_pdf.delay(str(a.id))
            elif a.mime_type in AUDIO_MIMES:
                extract_audio.delay(str(a.id))
    except Exception:
        pass


@router.post(
    "/matters/{matter_id}/gmail/search",
    response_model=GmailSearchResponse,
)
async def gmail_search(
    matter_id: UUID,
    body: GmailSearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search the client's Gmail for evidence matching a request.

    Accepts either a request_id (uses LLM to generate query from
    the evidence request) or a raw_query (used directly). Returns
    message previews the client can review before importing.
    """
    await require_matter_role(
        matter_id, ["primary_client", "contributor_client"], user, db
    )

    # Get Google account and refresh token if needed
    account = await _get_google_account(user.id, db)
    svc = GoogleOAuthService()
    await svc.ensure_fresh_token(account, db)

    # Build the Gmail query — either from an evidence request or raw
    if body.request_id:
        result = await db.execute(
            select(EvidenceRequest).where(EvidenceRequest.id == body.request_id)
        )
        ev_req = result.scalars().first()
        if not ev_req:
            raise HTTPException(404, "Evidence request not found")

        query = generate_gmail_query(
            title=ev_req.title,
            description=ev_req.description,
            category=ev_req.category or "",
            keywords=ev_req.keywords or [],
            date_start=str(ev_req.date_range_start) if ev_req.date_range_start else "",
            date_end=str(ev_req.date_range_end) if ev_req.date_range_end else "",
            source_system=ev_req.source_system or "",
        )
    elif body.raw_query:
        query = body.raw_query
    else:
        raise HTTPException(400, "Provide either request_id or raw_query")

    # Search Gmail
    previews = search_emails(
        access_token=account.access_token,
        query=query,
        max_results=body.max_results,
    )

    await log_action(
        db,
        user.id,
        "gmail.search",
        matter_id=matter_id,
        metadata={"query": query, "results": len(previews)},
    )
    await db.commit()

    return GmailSearchResponse(
        query=query,
        total_results=len(previews),
        messages=previews,
    )


@router.post("/matters/{matter_id}/gmail/import")
async def gmail_import(
    matter_id: UUID,
    body: GmailImportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import selected Gmail messages into a matter as evidence.

    Each email body becomes a Record (source='gmail'). Attachments
    become Artifacts and get routed through the extraction pipeline.
    """
    await require_matter_role(
        matter_id, ["primary_client", "contributor_client"], user, db
    )

    account = await _get_google_account(user.id, db)
    svc = GoogleOAuthService()
    await svc.ensure_fresh_token(account, db)

    storage = get_storage(settings)
    imported_records = []
    imported_artifacts = []

    for message_id in body.message_ids:
        # Fetch full message content
        msg = get_full_message(account.access_token, message_id)

        # Build a clean text representation of the email
        email_text = (
            f"Subject: {msg['subject']} | "
            f"From: {msg['sender']} | "
            f"To: {msg['to']} | "
            f"Date: {msg['date']} | "
            f"Body summary: {msg['body_text'][:2000]}"
        )

        # Parse the internal date (milliseconds since epoch)
        email_ts = None
        if msg.get("internal_date_ms"):
            try:
                from datetime import datetime as dt, timezone

                email_ts = dt.fromtimestamp(
                    int(msg["internal_date_ms"]) / 1000, tz=timezone.utc
                ).replace(tzinfo=None)
            except (ValueError, TypeError):
                pass

        # Create a Record for the email content
        record = Record(
            matter_id=matter_id,
            owner_user_id=user.id,
            ts=email_ts,
            source="gmail",
            type="email",
            text=email_text,
            metadata_={
                "gmail_message_id": message_id,
                "subject": msg["subject"],
                "sender": msg["sender"],
                "to": msg["to"],
                "label_ids": msg.get("label_ids", []),
            },
        )
        db.add(record)
        imported_records.append(record)

        # Import attachments as Artifacts (if requested)
        if body.include_attachments and msg.get("attachments"):
            for att_info in msg["attachments"]:
                att_bytes = download_attachment(
                    account.access_token,
                    message_id,
                    att_info["attachment_id"],
                )

                artifact_id = uuid4()
                filename = att_info["filename"]
                key = f"{matter_id}/{artifact_id}/{filename}"
                storage_uri = await storage.upload(key, att_bytes)

                artifact = Artifact(
                    id=artifact_id,
                    matter_id=matter_id,
                    owner_user_id=user.id,
                    original_filename=filename,
                    mime_type=att_info.get("mime_type", "application/octet-stream"),
                    file_size_bytes=len(att_bytes),
                    storage_uri=storage_uri,
                    source_system="gmail",
                    source_id=f"{message_id}/{att_info['attachment_id']}",
                    sha256=hashlib.sha256(att_bytes).hexdigest(),
                    original_timestamps={"email_date": msg.get("date", "")},
                    status="processing",
                )
                db.add(artifact)

                # Check for duplicates
                await enforce_hash_and_check_dedup(db, artifact, att_bytes, matter_id)
                imported_artifacts.append(artifact)

    await db.commit()

    # Dispatch extraction for any importable attachments
    _dispatch_extraction(imported_artifacts)

    await log_action(
        db,
        user.id,
        "gmail.import",
        matter_id=matter_id,
        metadata={
            "message_ids": body.message_ids,
            "records_created": len(imported_records),
            "artifacts_created": len(imported_artifacts),
        },
    )
    await db.commit()

    return {
        "imported_emails": len(imported_records),
        "imported_attachments": len(imported_artifacts),
        "record_ids": [str(r.id) for r in imported_records],
        "artifact_ids": [str(a.id) for a in imported_artifacts],
    }
