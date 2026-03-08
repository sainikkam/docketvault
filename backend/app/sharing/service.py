from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.evidence.models import Artifact, Record
from app.extraction.models import Extraction
from app.matters.models import MatterMember
from app.matters.service import log_action
from app.sharing.models import SharePolicy


async def build_share_preview(
    db: AsyncSession, matter_id: UUID, user_id: UUID
) -> dict:
    """Build share preview grouped by category with sensitivity flags."""
    result = await db.execute(
        select(Artifact).where(
            Artifact.matter_id == matter_id,
            Artifact.owner_user_id == user_id,
        )
    )
    artifacts = list(result.scalars().all())

    categories: dict[str, list] = {}
    for art in artifacts:
        # Get existing share policy
        pol_result = await db.execute(
            select(SharePolicy).where(
                SharePolicy.matter_id == matter_id,
                SharePolicy.artifact_id == art.id,
            )
        )
        policy = pol_result.scalars().first()

        # Check sensitivity from extraction
        ext_result = await db.execute(
            select(Extraction).where(Extraction.artifact_id == art.id)
        )
        extraction = ext_result.scalars().first()
        is_sensitive = False
        if extraction and extraction.sensitivity_flags:
            is_sensitive = any(extraction.sensitivity_flags.values())

        # Get category from record
        rec_result = await db.execute(
            select(Record).where(Record.matter_id == matter_id)
        )
        record = rec_result.scalars().first()
        category = record.category if record and hasattr(record, "category") else "uncategorized"

        # Ensure share policy exists
        if not policy:
            policy = SharePolicy(
                matter_id=matter_id,
                artifact_id=art.id,
                owner_user_id=user_id,
                is_sensitive=is_sensitive,
            )
            db.add(policy)
            await db.flush()

        item = {
            "artifact_id": str(art.id),
            "filename": art.original_filename,
            "mime_type": art.mime_type,
            "state": policy.state,
            "is_sensitive": is_sensitive,
            "sensitivity_acknowledged": policy.sensitivity_acknowledged,
            "category": category,
        }
        categories.setdefault(category, []).append(item)

    await db.commit()
    return {"matter_id": str(matter_id), "categories": categories}


async def batch_update_share_states(
    db: AsyncSession,
    matter_id: UUID,
    user_id: UUID,
    updates: list[dict],
) -> list[dict]:
    """Batch update share policies. Enforces sensitivity acknowledgment."""
    results = []
    for upd in updates:
        pol_result = await db.execute(
            select(SharePolicy).where(
                SharePolicy.matter_id == matter_id,
                SharePolicy.artifact_id == UUID(upd["artifact_id"]),
                SharePolicy.owner_user_id == user_id,
            )
        )
        policy = pol_result.scalars().first()
        if not policy:
            results.append(
                {"artifact_id": upd["artifact_id"], "error": "not found or not owner"}
            )
            continue

        new_state = upd["state"]

        # Enforce: sensitive items must be acknowledged before approving
        if (
            new_state == "approved"
            and policy.is_sensitive
            and not policy.sensitivity_acknowledged
        ):
            if not upd.get("acknowledge_sensitive", False):
                results.append(
                    {
                        "artifact_id": upd["artifact_id"],
                        "error": "sensitive item requires acknowledgment",
                    }
                )
                continue
            policy.sensitivity_acknowledged = True

        policy.state = new_state
        if new_state == "approved":
            policy.approved_at = datetime.utcnow()
        elif new_state == "revoked":
            policy.revoked_at = datetime.utcnow()
        db.add(policy)

        await log_action(
            db,
            user_id=user_id,
            action=f"share_{new_state}",
            matter_id=matter_id,
            target_type="artifact",
            target_id=UUID(upd["artifact_id"]),
        )
        results.append({"artifact_id": upd["artifact_id"], "state": new_state})

    await db.commit()
    return results


async def get_approved_artifact_ids(db: AsyncSession, matter_id: UUID) -> set[UUID]:
    """Get set of approved artifact IDs for a matter."""
    result = await db.execute(
        select(SharePolicy.artifact_id).where(
            SharePolicy.matter_id == matter_id,
            SharePolicy.state == "approved",
        )
    )
    return set(result.scalars().all())


async def apply_visibility_filter(
    db: AsyncSession,
    user_id: UUID,
    matter_id: UUID,
    artifacts: list,
) -> list:
    """Filter artifacts based on user role and share policies.
    - Clients see all their own artifacts (any state)
    - Attorneys/paralegals see only approved artifacts
    """
    result = await db.execute(
        select(MatterMember).where(
            MatterMember.matter_id == matter_id,
            MatterMember.user_id == user_id,
        )
    )
    member = result.scalars().first()
    if not member:
        return []

    if member.role in ("attorney", "paralegal"):
        approved_ids = await get_approved_artifact_ids(db, matter_id)
        return [a for a in artifacts if a.id in approved_ids]

    # Clients see everything they uploaded
    return [a for a in artifacts if a.owner_user_id == user_id]
