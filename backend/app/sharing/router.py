from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.models import User
from app.auth.service import get_current_user
from app.database import get_db
from app.matters.service import log_action, require_matter_role
from app.notifications.service import get_matter_attorneys, notify
from app.sharing.models import BatchShareUpdateRequest, SharePolicy
from app.sharing.service import batch_update_share_states, build_share_preview

router = APIRouter()


@router.get("/matters/{matter_id}/share-preview")
async def get_share_preview(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all artifacts grouped by category with share states + sensitivity flags."""
    await require_matter_role(
        matter_id, ["primary_client", "contributor_client"], user, db
    )
    return await build_share_preview(db, matter_id, user.id)


@router.post("/matters/{matter_id}/share-preview/update")
async def update_share_states(
    matter_id: UUID,
    body: BatchShareUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch update share states. Sensitive items require acknowledge_sensitive=true."""
    await require_matter_role(
        matter_id, ["primary_client", "contributor_client"], user, db
    )
    results = await batch_update_share_states(
        db, matter_id, user.id, [u.model_dump() for u in body.updates]
    )
    return {"results": results}


@router.post("/matters/{matter_id}/share-preview/approve-all")
async def approve_all(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve all pending (non-excluded) artifacts. Sensitive items auto-acknowledged."""
    await require_matter_role(
        matter_id, ["primary_client", "contributor_client"], user, db
    )

    result = await db.execute(
        select(SharePolicy).where(
            SharePolicy.matter_id == matter_id,
            SharePolicy.owner_user_id == user.id,
            SharePolicy.state == "pending",
        )
    )
    policies = list(result.scalars().all())

    approved_count = 0
    now = datetime.utcnow()
    for policy in policies:
        policy.state = "approved"
        policy.approved_at = now
        if policy.is_sensitive:
            policy.sensitivity_acknowledged = True
        db.add(policy)
        approved_count += 1

    await db.commit()
    await log_action(
        db,
        user_id=user.id,
        action="share_approve_all",
        matter_id=matter_id,
        metadata={"count": approved_count},
    )

    # Notify attorneys
    for attorney_id in await get_matter_attorneys(db, matter_id):
        await notify(
            db, attorney_id, "sharing.approved",
            f"Client approved {approved_count} items",
            matter_id=matter_id,
            metadata={"count": approved_count},
        )
    await db.commit()

    return {"approved": approved_count}


@router.post("/matters/{matter_id}/revoke")
async def revoke_all(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all sharing for this matter. Lawyer immediately loses access."""
    await require_matter_role(
        matter_id, ["primary_client", "contributor_client"], user, db
    )

    result = await db.execute(
        select(SharePolicy).where(
            SharePolicy.matter_id == matter_id,
            SharePolicy.owner_user_id == user.id,
            SharePolicy.state == "approved",
        )
    )
    policies = list(result.scalars().all())

    revoked_count = 0
    now = datetime.utcnow()
    for policy in policies:
        policy.state = "revoked"
        policy.revoked_at = now
        db.add(policy)
        revoked_count += 1

    await db.commit()
    await log_action(
        db,
        user_id=user.id,
        action="share_revoke_all",
        matter_id=matter_id,
        metadata={"count": revoked_count},
    )

    # Notify attorneys
    for attorney_id in await get_matter_attorneys(db, matter_id):
        await notify(
            db, attorney_id, "sharing.revoked",
            f"Client revoked access to {revoked_count} items",
            matter_id=matter_id,
        )
    await db.commit()

    return {"revoked": revoked_count}
