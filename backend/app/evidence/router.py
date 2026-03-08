from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import get_current_user
from app.config import Settings
from app.database import get_db
from app.evidence.models import (
    ArtifactResponse,
    ManifestEntry,
    MatterManifest,
    RecordResponse,
    UploadResponse,
)
from app.evidence.service import (
    IngestionService,
    enforce_hash_and_check_dedup,
    get_artifact,
    get_record,
    list_artifacts,
    list_records,
)
from app.matters.service import log_action, require_matter_member, require_matter_role
from app.storage import get_storage

router = APIRouter()
settings = Settings()


def get_storage_dep():
    return get_storage(settings)


@router.post(
    "/matters/{matter_id}/evidence/upload",
    response_model=UploadResponse,
    status_code=201,
)
async def upload_evidence(
    matter_id: UUID,
    files: list[UploadFile],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage=Depends(get_storage_dep),
):
    member = await require_matter_role(
        matter_id, ["primary_client", "contributor_client"], user, db
    )
    service = IngestionService(storage, db)
    all_artifacts = []
    for file in files:
        file_bytes = await file.read()
        artifacts = await service.ingest(
            file_bytes,
            file.filename or "unknown",
            file.content_type or "application/octet-stream",
            matter_id,
            member.user_id,
        )
        all_artifacts.extend(artifacts)

    # Run dedup check on all artifacts
    for artifact in all_artifacts:
        dedup = await enforce_hash_and_check_dedup(db, artifact, b"", matter_id)
        if dedup["is_duplicate"]:
            await log_action(
                db,
                member.user_id,
                "duplicate_detected",
                target_type="artifact",
                target_id=artifact.id,
                matter_id=matter_id,
                metadata={
                    "artifact_id": str(artifact.id),
                    "duplicate_of": str(dedup["duplicate_of"]),
                },
            )

    await db.commit()

    for artifact in all_artifacts:
        await log_action(
            db,
            member.user_id,
            "evidence.uploaded",
            target_type="artifact",
            target_id=artifact.id,
            matter_id=matter_id,
        )

    return UploadResponse(
        uploaded=len(all_artifacts),
        artifacts=[a.id for a in all_artifacts],
    )


@router.get("/matters/{matter_id}/artifacts", response_model=list[ArtifactResponse])
async def list_artifacts_endpoint(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    await require_matter_member(matter_id, user, db)
    return await list_artifacts(matter_id, db, limit, offset)


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact_endpoint(
    artifact_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    artifact = await get_artifact(artifact_id, db)
    await require_matter_member(artifact.matter_id, user, db)
    return artifact


@router.get("/artifacts/{artifact_id}/download")
async def download_artifact(
    artifact_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage=Depends(get_storage_dep),
):
    artifact = await get_artifact(artifact_id, db)
    await require_matter_member(artifact.matter_id, user, db)
    # Extract key from storage_uri (strip local:// or s3:// prefix)
    uri = artifact.storage_uri
    if uri.startswith("local://"):
        key = uri[len("local://") :]
    elif uri.startswith("s3://"):
        # s3://bucket/key -> key part after bucket/
        parts = uri[len("s3://") :].split("/", 1)
        key = parts[1] if len(parts) > 1 else parts[0]
    else:
        key = uri
    url = await storage.signed_url(key)
    return {"url": url}


@router.get("/matters/{matter_id}/records", response_model=list[RecordResponse])
async def list_records_endpoint(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    await require_matter_member(matter_id, user, db)
    return await list_records(matter_id, db, limit, offset)


@router.get("/records/{record_id}", response_model=RecordResponse)
async def get_record_endpoint(
    record_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    record = await get_record(record_id, db)
    await require_matter_member(record.matter_id, user, db)
    return record


@router.get("/matters/{matter_id}/manifest", response_model=MatterManifest)
async def get_manifest(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_member(matter_id, user, db)
    artifacts = await list_artifacts(matter_id, db, limit=10000, offset=0)

    entries = [
        ManifestEntry(
            artifact_id=a.id,
            sha256=a.sha256 or "",
            original_filename=a.original_filename,
            mime_type=a.mime_type,
            size_bytes=a.file_size_bytes,
            source_system=a.source_system,
            source_id=getattr(a, "source_id", None),
            original_timestamps=getattr(a, "original_timestamps", {}),
            uploaded_at=a.created_at,
            uploaded_by=a.owner_user_id,
            is_duplicate=a.is_duplicate,
            duplicate_of=a.duplicate_of,
            status=a.status,
        )
        for a in artifacts
    ]

    return MatterManifest(
        matter_id=matter_id,
        total_artifacts=len(entries),
        total_duplicates=sum(1 for e in entries if e.is_duplicate),
        entries=entries,
    )
