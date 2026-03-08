from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.models import User
from app.auth.service import get_current_user
from app.database import get_db
from app.evidence.models import Artifact
from app.extraction.models import Extraction, ExtractionResponse
from app.matters.service import log_action, require_matter_member, require_matter_role

router = APIRouter()


@router.get("/artifacts/{artifact_id}/extraction", response_model=ExtractionResponse)
async def get_extraction(
    artifact_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    artifact = (
        (await db.execute(select(Artifact).where(Artifact.id == artifact_id)))
        .scalars()
        .first()
    )
    if not artifact:
        raise HTTPException(404, "Artifact not found")
    await require_matter_member(artifact.matter_id, user, db)

    extraction = (
        (
            await db.execute(
                select(Extraction).where(Extraction.artifact_id == artifact_id)
            )
        )
        .scalars()
        .first()
    )
    if not extraction:
        raise HTTPException(404, "No extraction found for this artifact")
    return extraction


@router.patch("/extractions/{extraction_id}/verify")
async def verify_extraction(
    extraction_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    extraction = (
        (await db.execute(select(Extraction).where(Extraction.id == extraction_id)))
        .scalars()
        .first()
    )
    if not extraction:
        raise HTTPException(404, "Extraction not found")

    artifact = (
        (
            await db.execute(
                select(Artifact).where(Artifact.id == extraction.artifact_id)
            )
        )
        .scalars()
        .first()
    )
    await require_matter_role(
        artifact.matter_id,
        ["primary_client", "contributor_client"],
        user,
        db,
    )

    extraction.verification_state = "verified"
    db.add(extraction)
    await log_action(
        db,
        user.id,
        "extraction.verified",
        target_type="extraction",
        target_id=extraction.id,
        matter_id=artifact.matter_id,
    )
    await db.commit()
    return {"status": "verified", "extraction_id": str(extraction_id)}
