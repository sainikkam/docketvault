import hashlib
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.evidence.adapters.generic_zip import GenericZipAdapter
from app.evidence.models import Artifact, Record
from app.storage import StorageBackend


async def enforce_hash_and_check_dedup(
    db: AsyncSession,
    artifact: Artifact,
    file_bytes: bytes,
    matter_id: UUID,
) -> dict:
    """Compute SHA-256 if missing, check for duplicates within the matter."""
    if not artifact.sha256:
        artifact.sha256 = hashlib.sha256(file_bytes).hexdigest()

    result = await db.execute(
        select(Artifact).where(
            Artifact.matter_id == matter_id,
            Artifact.sha256 == artifact.sha256,
            Artifact.id != artifact.id,
        )
    )
    existing = result.scalars().first()

    if existing:
        artifact.is_duplicate = True
        artifact.duplicate_of = existing.id
        return {"is_duplicate": True, "duplicate_of": existing.id}

    return {"is_duplicate": False, "duplicate_of": None}


class IngestionService:
    """Handles file uploads — both direct files and ZIPs."""

    def __init__(self, storage: StorageBackend, db: AsyncSession):
        self.storage = storage
        self.db = db
        self.adapters = [GenericZipAdapter()]

    async def ingest(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        matter_id: UUID,
        owner_id: UUID,
    ) -> list[Artifact]:
        sha256 = hashlib.sha256(file_bytes).hexdigest()

        for adapter in self.adapters:
            if adapter.can_handle(filename, mime_type):
                records, artifacts = await adapter.parse(
                    file_bytes, matter_id, owner_id, self.storage
                )
                for r in records:
                    self.db.add(r)
                for a in artifacts:
                    self.db.add(a)
                return artifacts

        # No adapter matched — store as single Artifact
        artifact_id = uuid4()
        key = f"{matter_id}/{artifact_id}/{filename}"
        storage_uri = await self.storage.upload(key, file_bytes)

        is_extractable = (
            mime_type.startswith(("image/", "audio/", "video/"))
            or mime_type == "application/pdf"
        )

        artifact = Artifact(
            id=artifact_id,
            matter_id=matter_id,
            owner_user_id=owner_id,
            mime_type=mime_type,
            original_filename=filename,
            file_size_bytes=len(file_bytes),
            sha256=sha256,
            storage_uri=storage_uri,
            source_system="upload",
            status="processing" if is_extractable else "needs_review",
        )
        self.db.add(artifact)
        return [artifact]


async def list_artifacts(
    matter_id: UUID, db: AsyncSession, limit: int = 50, offset: int = 0
) -> list[Artifact]:
    result = await db.execute(
        select(Artifact)
        .where(Artifact.matter_id == matter_id)
        .order_by(Artifact.import_timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_artifact(artifact_id: UUID, db: AsyncSession) -> Artifact:
    from fastapi import HTTPException

    result = await db.execute(select(Artifact).where(Artifact.id == artifact_id))
    artifact = result.scalars().first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


async def list_records(
    matter_id: UUID, db: AsyncSession, limit: int = 50, offset: int = 0
) -> list[Record]:
    result = await db.execute(
        select(Record)
        .where(Record.matter_id == matter_id)
        .order_by(Record.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_record(record_id: UUID, db: AsyncSession) -> Record:
    from fastapi import HTTPException

    result = await db.execute(select(Record).where(Record.id == record_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record
