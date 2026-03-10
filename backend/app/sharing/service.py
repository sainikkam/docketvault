from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.evidence.models import Artifact, Record
from app.extraction.models import Extraction
from app.matters.models import MatterMember
from app.matters.service import log_action
from app.sharing.models import RecordShareState, SharePolicy

# Records with relevance at or above this threshold default to "included"
RELEVANCE_THRESHOLD = 0.4
# Max characters of record text to include in share preview
RECORD_PREVIEW_LEN = 200


async def _get_records_for_artifact(
    db: AsyncSession, artifact: Artifact
) -> list[Record]:
    """Fetch all records that belong to a multi-item artifact.

    Records are linked to their source artifact via metadata_.source_file
    matching the artifact's original_filename.
    """
    result = await db.execute(
        select(Record)
        .where(
            Record.matter_id == artifact.matter_id,
            Record.owner_user_id == artifact.owner_user_id,
        )
        .order_by(Record.relevance_score.desc())
    )
    all_records = list(result.scalars().all())
    # Filter to records from this artifact's source file
    return [
        r for r in all_records
        if r.metadata_
        and isinstance(r.metadata_, dict)
        and r.metadata_.get("source_file") == artifact.original_filename
    ]


async def auto_create_record_share_states(
    db: AsyncSession, policy: SharePolicy, artifact: Artifact
) -> list[RecordShareState]:
    """Create RecordShareState rows for each record in a multi-item artifact.

    Uses relevance-based pre-selection: records scored at or above the
    threshold default to "included", lower-scored records to "excluded".
    Existing states are never overwritten — this avoids conflicts with
    Streamlit widget session state and respects user manual overrides.
    Returns the created states (empty list if no child records exist).
    """
    records = await _get_records_for_artifact(db, artifact)
    if not records:
        return []

    # Check if states already exist for this policy
    existing = await db.execute(
        select(RecordShareState.record_id).where(
            RecordShareState.share_policy_id == policy.id
        )
    )
    existing_ids = set(existing.scalars().all())

    created = []
    for rec in records:
        if rec.id in existing_ids:
            continue
        state = (
            "included" if rec.relevance_score >= RELEVANCE_THRESHOLD else "excluded"
        )
        rss = RecordShareState(
            share_policy_id=policy.id,
            record_id=rec.id,
            state=state,
        )
        db.add(rss)
        created.append(rss)

    if created:
        await db.flush()
    return created


async def build_share_preview(
    db: AsyncSession, matter_id: UUID, user_id: UUID
) -> dict:
    """Build share preview grouped by category with sensitivity flags and relevance data.

    Uses artifact-level category and relevance_score (set by enrichment pipeline).
    Includes extraction summaries so the client can see what the lawyer would receive.
    For multi-item artifacts (those with child records), includes per-record data
    so the client can approve/exclude individual items.
    """
    result = await db.execute(
        select(Artifact)
        .where(
            Artifact.matter_id == matter_id,
            Artifact.owner_user_id == user_id,
        )
        .order_by(Artifact.relevance_score.desc())
    )
    artifacts = list(result.scalars().all())

    # Batch-fetch extractions and share policies for efficiency
    art_ids = [a.id for a in artifacts]

    ext_result = await db.execute(
        select(Extraction).where(Extraction.artifact_id.in_(art_ids))
    )
    ext_map = {e.artifact_id: e for e in ext_result.scalars().all()}

    pol_result = await db.execute(
        select(SharePolicy).where(
            SharePolicy.matter_id == matter_id,
            SharePolicy.artifact_id.in_(art_ids),
        )
    )
    pol_map = {p.artifact_id: p for p in pol_result.scalars().all()}

    categories: dict[str, list] = {}
    sensitive_items: list[dict] = []

    for art in artifacts:
        extraction = ext_map.get(art.id)
        is_sensitive = False
        sensitivity_flags = {}
        if extraction and extraction.sensitivity_flags:
            sensitivity_flags = extraction.sensitivity_flags
            is_sensitive = any(sensitivity_flags.values())

        # Use artifact-level category (set by enrichment pipeline)
        category = art.category or "uncategorized"

        # Get or create share policy
        policy = pol_map.get(art.id)
        if not policy:
            policy = SharePolicy(
                matter_id=matter_id,
                artifact_id=art.id,
                owner_user_id=user_id,
                is_sensitive=is_sensitive,
            )
            db.add(policy)
            await db.flush()

        summary = ""
        if extraction:
            summary = extraction.summary or extraction.overall_summary or ""

        # Fetch child records for multi-item artifacts
        child_records = await _get_records_for_artifact(db, art)
        has_records = len(child_records) > 1

        records_data = []
        if has_records:
            # Auto-create record share states if they don't exist yet
            await auto_create_record_share_states(db, policy, art)

            # Fetch record share states for this policy
            rss_result = await db.execute(
                select(RecordShareState).where(
                    RecordShareState.share_policy_id == policy.id
                )
            )
            rss_map = {
                rs.record_id: rs.state
                for rs in rss_result.scalars().all()
            }

            for rec in child_records:
                rec_state = rss_map.get(rec.id, "included")
                records_data.append({
                    "record_id": str(rec.id),
                    "text": rec.text[:RECORD_PREVIEW_LEN] if rec.text else "",
                    "ts": str(rec.ts) if rec.ts else None,
                    "source": rec.source,
                    "type": rec.type,
                    "relevance_score": rec.relevance_score,
                    "state": rec_state,
                })

        item = {
            "artifact_id": str(art.id),
            "filename": art.original_filename,
            "mime_type": art.mime_type,
            "state": policy.state,
            "is_sensitive": is_sensitive,
            "sensitivity_flags": sensitivity_flags,
            "sensitivity_acknowledged": policy.sensitivity_acknowledged,
            "category": category,
            "relevance_score": art.relevance_score,
            "relevance_rationale": art.relevance_rationale or "",
            "summary": summary,
            "tags": art.tags,
            "has_records": has_records,
            "record_count": len(child_records) if has_records else 0,
            "records": records_data,
        }
        categories.setdefault(category, []).append(item)

        if is_sensitive:
            sensitive_items.append(item)

    await db.commit()
    return {
        "matter_id": str(matter_id),
        "categories": categories,
        "sensitive_items": sensitive_items,
        "total": len(artifacts),
        "sensitive_count": len(sensitive_items),
    }


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


async def batch_update_record_share_states(
    db: AsyncSession,
    matter_id: UUID,
    user_id: UUID,
    artifact_id: UUID,
    updates: list[dict],
) -> list[dict]:
    """Batch update per-record share states within an artifact.

    Finds the SharePolicy for the artifact, then creates or updates
    RecordShareState rows for each record specified.
    """
    pol_result = await db.execute(
        select(SharePolicy).where(
            SharePolicy.matter_id == matter_id,
            SharePolicy.artifact_id == artifact_id,
            SharePolicy.owner_user_id == user_id,
        )
    )
    policy = pol_result.scalars().first()
    if not policy:
        return [{"error": "share policy not found for this artifact"}]

    results = []
    for upd in updates:
        record_id = UUID(upd["record_id"])
        new_state = upd["state"]

        # Find or create RecordShareState
        rss_result = await db.execute(
            select(RecordShareState).where(
                RecordShareState.share_policy_id == policy.id,
                RecordShareState.record_id == record_id,
            )
        )
        rss = rss_result.scalars().first()

        if rss:
            rss.state = new_state
        else:
            rss = RecordShareState(
                share_policy_id=policy.id,
                record_id=record_id,
                state=new_state,
            )
        db.add(rss)

        await log_action(
            db,
            user_id=user_id,
            action=f"record_share_{new_state}",
            matter_id=matter_id,
            target_type="record",
            target_id=record_id,
        )
        results.append({"record_id": str(record_id), "state": new_state})

    await db.commit()
    return results


async def get_included_record_ids(
    db: AsyncSession, policy_id: UUID
) -> set[UUID]:
    """Return the set of record IDs marked as 'included' for a share policy."""
    result = await db.execute(
        select(RecordShareState.record_id).where(
            RecordShareState.share_policy_id == policy_id,
            RecordShareState.state == "included",
        )
    )
    return set(result.scalars().all())


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
