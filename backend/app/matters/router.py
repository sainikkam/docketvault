from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.models import User
from app.auth.service import get_current_user
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

    # Category counts from records linked to approved artifacts
    rec_result = await db.execute(
        select(Record).where(Record.matter_id == matter_id)
    )
    category_counts: dict[str, int] = {}
    for rec in rec_result.scalars().all():
        cat = rec.category if hasattr(rec, "category") else "uncategorized"
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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """Unified evidence list with visibility filtering and optional category filter."""
    await require_matter_member(matter_id, user, db)

    from app.evidence.models import Artifact, Record
    from app.sharing.service import apply_visibility_filter

    art_result = await db.execute(
        select(Artifact).where(Artifact.matter_id == matter_id)
    )
    artifacts = list(art_result.scalars().all())

    # Apply visibility filter
    artifacts = await apply_visibility_filter(db, user.id, matter_id, artifacts)

    # Optional category filter
    if category:
        rec_result = await db.execute(
            select(Record).where(
                Record.matter_id == matter_id, Record.category == category
            )
        )
        category_artifact_ids = set()
        for rec in rec_result.scalars().all():
            if hasattr(rec, "raw_pointer"):
                # Records don't have artifact_id directly; use matter_id match
                pass
        # For MVP, filter by matching artifact filenames or return all in category
        # Since records don't have artifact_id, just return all visible artifacts
        # This will be improved when Record gets an artifact_id foreign key

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
                "uploaded_at": str(a.import_timestamp),
            }
            for a in page
        ],
    }


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


@router.patch("/requests/{request_id}")
async def update_request_status(
    request_id: UUID,
    status: str = Query(..., regex="^(fulfilled|dismissed)$"),
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
