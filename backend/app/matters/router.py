import base64
import io
import json
from typing import Optional
from uuid import UUID

import anthropic
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

from app.auth.models import User
from app.auth.service import get_current_user
from app.config import Settings
from app.database import get_db
from app.notifications.service import get_matter_attorneys, get_matter_clients, notify
from app.matters.models import (
    AuditLog,
    AuditLogResponse,
    CreateEvidenceRequestBody,
    EvidenceRequest,
    EvidenceRequestResponse,
    InvitationCreateRequest,
    InvitationResponse,
    MatterCreateRequest,
    MatterResponse,
    MemberResponse,
)
from app.matters.service import (
    accept_invitation,
    create_invitation,
    create_matter,
    get_matter,
    list_audit_log,
    list_members,
    list_user_matters,
    log_action,
    require_matter_member,
    require_matter_role,
)

router = APIRouter()


@router.post("/matters", response_model=MatterResponse, status_code=201)
async def create_matter_endpoint(
    req: MatterCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_matter(req, user, db)


@router.get("/matters", response_model=list[MatterResponse])
async def list_matters_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_user_matters(user, db)


@router.get("/matters/{matter_id}", response_model=MatterResponse)
async def get_matter_endpoint(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_member(matter_id, user, db)
    return await get_matter(matter_id, db)


@router.post(
    "/matters/{matter_id}/invitations",
    response_model=InvitationResponse,
    status_code=201,
)
async def create_invitation_endpoint(
    matter_id: UUID,
    req: InvitationCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_invitation(matter_id, req, user, db)


@router.post(
    "/invitations/{token}/accept",
    response_model=MemberResponse,
)
async def accept_invitation_endpoint(
    token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await accept_invitation(token, user, db)


@router.get("/matters/{matter_id}/members", response_model=list[MemberResponse])
async def list_members_endpoint(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_member(matter_id, user, db)
    return await list_members(matter_id, db)


@router.get("/matters/{matter_id}/audit-log", response_model=list[AuditLogResponse])
async def list_audit_log_endpoint(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    await require_matter_member(matter_id, user, db)
    return await list_audit_log(matter_id, db, limit, offset)


# --- Chunk 11: Dashboard, Evidence, Requests ---


@router.get("/matters/{matter_id}/dashboard")
async def get_dashboard(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated lawyer dashboard: timeline, categories, missing items, activity."""
    await require_matter_role(matter_id, ["attorney", "paralegal"], user, db)

    from app.enrichment.models import MissingItem, TimelineEvent
    from app.evidence.models import Artifact, Record
    from app.sharing.service import get_approved_artifact_ids

    matter = await get_matter(matter_id, db)

    # Timeline events
    te_result = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.matter_id == matter_id)
        .order_by(TimelineEvent.event_ts)
    )
    timeline_events = [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "title": e.title,
            "event_ts": str(e.event_ts) if e.event_ts else None,
            "actors": e.actors,
            "summary": e.summary,
            "confidence": e.confidence,
            "verification_state": e.verification_state,
        }
        for e in te_result.scalars().all()
    ]

    # Approved artifact IDs
    approved_ids = await get_approved_artifact_ids(db, matter_id)

    # Category counts from approved artifacts (uses artifact-level category)
    art_result = await db.execute(
        select(Artifact).where(Artifact.matter_id == matter_id)
    )
    category_counts: dict[str, int] = {}
    for art in art_result.scalars().all():
        if art.id in approved_ids:
            cat = art.category or "uncategorized"
            category_counts[cat] = category_counts.get(cat, 0) + 1

    # Open missing items
    mi_result = await db.execute(
        select(MissingItem).where(
            MissingItem.matter_id == matter_id, MissingItem.status == "open"
        )
    )
    missing_items = [
        {
            "id": str(m.id),
            "missing_type": m.missing_type,
            "description": m.description,
            "priority": m.priority,
        }
        for m in mi_result.scalars().all()
    ]

    # Recent activity
    audit_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.matter_id == matter_id)
        .order_by(AuditLog.created_at.desc())
        .limit(20)
    )
    recent_activity = [
        {
            "id": str(a.id),
            "action": a.action,
            "user_id": str(a.user_id),
            "created_at": str(a.created_at),
        }
        for a in audit_result.scalars().all()
    ]

    return {
        "matter_id": str(matter_id),
        "firm_id": str(matter.firm_id),
        "matter_title": matter.title,
        "status": matter.status,
        "timeline_events": timeline_events,
        "category_counts": category_counts,
        "missing_items": missing_items,
        "recent_activity": recent_activity,
    }


@router.get("/matters/{matter_id}/evidence")
async def get_evidence(
    matter_id: UUID,
    category: Optional[str] = None,
    sort_by: str = Query("relevance", pattern="^(relevance|timestamp)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """Unified evidence list with visibility filtering, sorting, and optional category filter."""
    await require_matter_member(matter_id, user, db)

    from app.evidence.models import Artifact
    from app.sharing.service import apply_visibility_filter

    order = (
        Artifact.relevance_score.desc()
        if sort_by == "relevance"
        else Artifact.import_timestamp.desc()
    )
    art_result = await db.execute(
        select(Artifact).where(Artifact.matter_id == matter_id).order_by(order)
    )
    artifacts = list(art_result.scalars().all())

    # Apply visibility filter (lawyers see only approved; clients see their own)
    artifacts = await apply_visibility_filter(db, user.id, matter_id, artifacts)

    # Filter by category if requested (uses artifact-level category now)
    if category:
        artifacts = [a for a in artifacts if a.category == category]

    total = len(artifacts)
    page = artifacts[offset : offset + limit]

    return {
        "total": total,
        "artifacts": [
            {
                "id": str(a.id),
                "filename": a.original_filename,
                "mime_type": a.mime_type,
                "status": a.status,
                "category": a.category,
                "relevance_score": a.relevance_score,
                "relevance_rationale": a.relevance_rationale or "",
                "tags": a.tags,
                "uploaded_at": str(a.import_timestamp),
            }
            for a in page
        ],
    }


@router.get("/matters/{matter_id}/evidence-preview")
async def get_evidence_preview(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Client-facing organized evidence preview.

    Returns artifacts grouped by relevance (relevant by category, sensitive,
    and low relevance), each with extraction summaries and sensitivity flags.
    """
    await require_matter_role(
        matter_id, ["primary_client", "contributor_client"], user, db
    )
    from app.evidence.service import build_evidence_preview

    return await build_evidence_preview(matter_id, user.id, db)


@router.post(
    "/matters/{matter_id}/requests",
    response_model=EvidenceRequestResponse,
    status_code=201,
)
async def create_request(
    matter_id: UUID,
    body: CreateEvidenceRequestBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lawyer creates an evidence request for the client."""
    await require_matter_role(matter_id, ["attorney", "paralegal"], user, db)

    req = EvidenceRequest(
        matter_id=matter_id,
        created_by=user.id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        category=body.category,
        date_range_start=body.date_range_start,
        date_range_end=body.date_range_end,
        keywords=body.keywords,
        source_system=body.source_system,
        format_instructions=body.format_instructions,
        preservation_note=body.preservation_note,
        checklist=body.checklist,
    )
    db.add(req)
    await db.commit()
    await db.refresh(req)

    await log_action(
        db,
        user_id=user.id,
        action="request_created",
        matter_id=matter_id,
        target_type="request",
        target_id=req.id,
    )

    # Notify clients about the new request
    for client_id in await get_matter_clients(db, matter_id):
        await notify(
            db, client_id, "request.received",
            body.title, matter_id=matter_id,
            metadata={"request_id": str(req.id)},
        )
    await db.commit()

    return req


@router.get(
    "/matters/{matter_id}/requests",
    response_model=list[EvidenceRequestResponse],
)
async def list_requests(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all evidence requests for a matter."""
    await require_matter_member(matter_id, user, db)
    result = await db.execute(
        select(EvidenceRequest).where(EvidenceRequest.matter_id == matter_id)
    )
    return list(result.scalars().all())


GENERATE_CHECKLIST_SYSTEM = (
    "You are a legal assistant helping a lawyer specify what evidence they need "
    "from a client. Generate a checklist of specific documents, records, or "
    "materials the lawyer is requesting. Each item describes a piece of evidence, "
    "NOT how to export it or what format to use — those details are handled "
    "separately. Write in plain language a non-lawyer can understand."
)

GENERATE_CHECKLIST_USER = """Generate an evidence checklist for this document request.

Each checklist item should describe a SPECIFIC document, record, or piece of
evidence the lawyer needs. Focus on WHAT the lawyer is looking for, not HOW
to export or deliver it.

DO NOT include items about:
- Export formats or technical steps (handled by "Format instructions" field)
- Preservation warnings (handled by "Preservation notice" field)
- Where to find data (handled by "Source system" field)
- How to upload or deliver files

DO include items like:
- Specific emails, messages, or conversations to locate
- Specific documents, receipts, or records to gather
- Specific date ranges or people involved
- Specific types of evidence relevant to the case

Request details:
Title: {title}
Category: {category}
Date range: {date_range_start} to {date_range_end}
Keywords: {keywords}
Source system: {source_system}
Description: {description}

Return a JSON array of strings. Each string is one checklist item.
Keep items short and specific. Include 4-8 items.

Example: ["All emails between you and John Smith from Jan-Mar 2025 regarding the lease agreement", "Any text messages mentioning the security deposit or move-out date", "Photos of the apartment taken at move-in and move-out", "The signed lease agreement and any amendments"]
"""


class GenerateChecklistBody(SQLModel):
    """Input fields for AI checklist generation."""

    title: str = ""
    category: str = ""
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    keywords: list = []
    source_system: str = ""
    description: str = ""
    format_instructions: str = ""
    preservation_note: str = ""


@router.post("/requests/generate-checklist")
async def generate_checklist(
    body: GenerateChecklistBody,
    user: User = Depends(get_current_user),
):
    """AI generates an actionable checklist from structured request fields.

    The lawyer reviews and edits the checklist before attaching it to the
    evidence request and sending to the client.
    """
    if user.role not in ("attorney", "paralegal"):
        raise HTTPException(403, "Only attorneys can generate checklists")

    settings = Settings()
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Only pass content-related fields to the AI. Format instructions,
    # preservation notes, and source system have their own form fields
    # and should NOT appear as checklist items.
    prompt = GENERATE_CHECKLIST_USER.format(
        title=body.title or "(not specified)",
        category=body.category or "(not specified)",
        date_range_start=body.date_range_start or "(open)",
        date_range_end=body.date_range_end or "present",
        keywords=", ".join(body.keywords) if body.keywords else "(none)",
        source_system=body.source_system or "(not specified)",
        description=body.description or "(none)",
    )

    response = client.messages.create(
        model=settings.LLM_MODEL,
        system=GENERATE_CHECKLIST_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )

    raw_text = response.content[0].text
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0]
    items = json.loads(raw_text)

    # Ensure it's a list of strings
    if not isinstance(items, list):
        items = []

    # Return as checklist objects with completed=False
    checklist = [{"item": str(item), "completed": False} for item in items]
    return {"checklist": checklist}


@router.patch("/requests/{request_id}/checklist")
async def update_checklist_item(
    request_id: UUID,
    item_index: int = Query(..., ge=0),
    completed: bool = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Client toggles a checklist item's completed status."""
    result = await db.execute(
        select(EvidenceRequest).where(EvidenceRequest.id == request_id)
    )
    req = result.scalars().first()
    if not req:
        raise HTTPException(404, "Request not found")
    await require_matter_member(req.matter_id, user, db)

    checklist = list(req.checklist) if req.checklist else []
    if item_index >= len(checklist):
        raise HTTPException(400, "Checklist item index out of range")

    checklist[item_index]["completed"] = completed
    req.checklist = checklist
    db.add(req)
    await db.commit()

    return {"checklist": checklist}


PARSE_LETTER_SYSTEM = (
    "You are a legal document parser. You are given a formal letter or memorandum "
    "from a lawyer to a client requesting production of documents or ESI. "
    "Extract the structured fields from this letter. Be precise and thorough. "
    "Only extract what is explicitly stated in the letter. Respond with strict JSON."
)

PARSE_LETTER_USER = """Parse this formal document request letter and extract:

- title: a short descriptive title for this request (e.g. "Email Production Request")
- description: the main body of instructions for the client
- category: one of [email, browser_history, social_media, chat_logs, files, photos, financial, medical, other]
- date_range_start: ISO date string (YYYY-MM-DD) or null if not specified
- date_range_end: ISO date string (YYYY-MM-DD) or null if not specified
- keywords: list of search terms or key phrases mentioned
- source_system: where the client should look (e.g. "Gmail", "WhatsApp", "Company laptop") or null
- format_instructions: any instructions about file format, metadata preservation, etc. or null
- preservation_note: any preservation / legal hold language (do not delete, etc.) or null
- priority: "low", "medium", or "high" based on urgency language in the letter

Return a single JSON object with these fields. Use null for fields not found in the letter.
"""

# Supported MIME types for letter upload
LETTER_MIME_MAP = {
    "application/pdf": "application/pdf",
    "image/png": "image/png",
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "text",
}


def _extract_docx_text(file_bytes: bytes) -> str:
    """Extract plain text from a DOCX file."""
    import docx

    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text)


@router.post("/requests/parse-letter")
async def parse_letter(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Parse a formal document request letter into structured RFP fields.

    Accepts PDF, images (PNG/JPG), DOCX, or plain text files. Uses the LLM
    to extract category, date ranges, keywords, format instructions, etc.
    """
    if user.role not in ("attorney", "paralegal"):
        raise HTTPException(403, "Only attorneys can parse request letters")

    content_type = file.content_type or ""
    if content_type not in LETTER_MIME_MAP:
        raise HTTPException(
            400,
            f"Unsupported file type: {content_type}. "
            "Upload a PDF, image (PNG/JPG), DOCX, or TXT file.",
        )

    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large. Maximum 10 MB.")

    settings = Settings()
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    mapped_type = LETTER_MIME_MAP[content_type]

    # Build the message content based on file type
    if mapped_type == "docx":
        # Extract text from DOCX, then send as text prompt
        text_content = _extract_docx_text(file_bytes)
        if not text_content.strip():
            raise HTTPException(400, "Could not extract text from DOCX file.")
        messages = [
            {
                "role": "user",
                "content": (
                    PARSE_LETTER_USER
                    + f"\n\n--- LETTER TEXT ---\n{text_content}\n--- END ---"
                ),
            }
        ]
    elif mapped_type == "text":
        # Plain text — send directly
        text_content = file_bytes.decode("utf-8", errors="replace")
        messages = [
            {
                "role": "user",
                "content": (
                    PARSE_LETTER_USER
                    + f"\n\n--- LETTER TEXT ---\n{text_content}\n--- END ---"
                ),
            }
        ]
    else:
        # PDF or image — send via vision as base64
        b64_data = base64.b64encode(file_bytes).decode()
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mapped_type,
                            "data": b64_data,
                        },
                    },
                    {"type": "text", "text": PARSE_LETTER_USER},
                ],
            }
        ]

    response = client.messages.create(
        model=settings.LLM_MODEL,
        system=PARSE_LETTER_SYSTEM,
        messages=messages,
        max_tokens=2048,
    )

    # Parse JSON from response
    raw_text = response.content[0].text
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1].rsplit("```", 1)[0]
    parsed = json.loads(raw_text)

    # Ensure keywords is always a list
    if not isinstance(parsed.get("keywords"), list):
        parsed["keywords"] = []

    return parsed


@router.patch("/requests/{request_id}")
async def update_request_status(
    request_id: UUID,
    status: str = Query(..., pattern="^(fulfilled|dismissed)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update request status (fulfilled or dismissed)."""
    result = await db.execute(
        select(EvidenceRequest).where(EvidenceRequest.id == request_id)
    )
    req = result.scalars().first()
    if not req:
        raise HTTPException(404, "Request not found")
    await require_matter_member(req.matter_id, user, db)

    req.status = status
    db.add(req)
    await db.commit()

    await log_action(
        db,
        user_id=user.id,
        action=f"request_{status}",
        matter_id=req.matter_id,
        target_type="request",
        target_id=request_id,
    )

    # Notify attorneys when a request is fulfilled
    if status == "fulfilled":
        for attorney_id in await get_matter_attorneys(db, req.matter_id):
            await notify(
                db, attorney_id, "request.fulfilled",
                f"Client fulfilled request: {req.title}",
                matter_id=req.matter_id,
            )
        await db.commit()

    return {"status": status}
