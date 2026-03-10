from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.models import User
from app.auth.service import get_current_user
from app.database import get_db
from app.enrichment.models import (
    IntakeSummary,
    IntakeSummaryResponse,
    MissingItem,
    MissingItemResponse,
    TimelineEvent,
    TimelineEventResponse,
)
from app.matters.service import require_matter_member, require_matter_role

router = APIRouter()


@router.get(
    "/matters/{matter_id}/timeline",
    response_model=list[TimelineEventResponse],
)
async def get_timeline(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get timeline events sorted chronologically."""
    await require_matter_member(matter_id, user, db)
    result = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.matter_id == matter_id)
        .order_by(TimelineEvent.event_ts)
    )
    return list(result.scalars().all())


@router.patch("/timeline-events/{event_id}/verify")
async def verify_timeline_event(
    event_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Client confirms a timeline event is correct."""
    result = await db.execute(
        select(TimelineEvent).where(TimelineEvent.id == event_id)
    )
    event = result.scalars().first()
    if not event:
        raise HTTPException(404, "Timeline event not found")
    await require_matter_role(
        event.matter_id, ["primary_client", "contributor_client"], user, db
    )
    event.verification_state = "verified"
    db.add(event)
    await db.commit()
    return {"status": "verified"}


@router.get(
    "/matters/{matter_id}/missing-items",
    response_model=list[MissingItemResponse],
)
async def get_missing_items(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List missing evidence items."""
    await require_matter_member(matter_id, user, db)
    result = await db.execute(
        select(MissingItem).where(MissingItem.matter_id == matter_id)
    )
    return list(result.scalars().all())


@router.patch("/missing-items/{item_id}")
async def update_missing_item(
    item_id: UUID,
    status: str = Query(..., pattern="^(fulfilled|dismissed)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a missing item as fulfilled or dismissed."""
    result = await db.execute(
        select(MissingItem).where(MissingItem.id == item_id)
    )
    item = result.scalars().first()
    if not item:
        raise HTTPException(404, "Missing item not found")
    await require_matter_member(item.matter_id, user, db)
    item.status = status
    db.add(item)
    await db.commit()
    return {"status": status}


@router.get(
    "/matters/{matter_id}/intake-summary",
    response_model=IntakeSummaryResponse,
)
async def get_intake_summary(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the AI-drafted intake summary."""
    await require_matter_member(matter_id, user, db)
    result = await db.execute(
        select(IntakeSummary).where(IntakeSummary.matter_id == matter_id)
    )
    summary = result.scalars().first()
    if not summary:
        raise HTTPException(404, "Intake summary not yet generated")
    return summary


@router.post("/matters/{matter_id}/enrich")
async def trigger_enrichment(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger the AI enrichment pipeline for a matter.

    Kicks off categorization, relevance scoring, timeline extraction,
    missing-item detection, and intake summary generation. Safe to call
    multiple times — results are upserted.
    """
    await require_matter_member(matter_id, user, db)

    from app.enrichment.tasks import enrich_matter

    try:
        enrich_matter.delay(str(matter_id))
        return {"status": "processing", "message": "Enrichment started. Refresh in a few seconds."}
    except Exception as e:
        raise HTTPException(
            503, f"Could not start enrichment. Is the worker running? {e}"
        )
