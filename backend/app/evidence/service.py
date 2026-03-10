import hashlib
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.evidence.adapters.generic_zip import GenericZipAdapter
from app.evidence.adapters.jsonl_adapter import JsonlAdapter
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
        # Order matters: more specific adapters first, generic ZIP last
        self.adapters = [JsonlAdapter(), GenericZipAdapter()]

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
                    file_bytes, matter_id, owner_id, self.storage,
                    filename=filename,
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
    matter_id: UUID,
    db: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "relevance",
) -> list[Artifact]:
    """List artifacts. sort_by can be 'relevance' (highest first) or 'timestamp'."""
    query = select(Artifact).where(Artifact.matter_id == matter_id)
    if sort_by == "relevance":
        query = query.order_by(Artifact.relevance_score.desc(), Artifact.import_timestamp.desc())
    else:
        query = query.order_by(Artifact.import_timestamp.desc())
    result = await db.execute(query.limit(limit).offset(offset))
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


async def list_records_for_artifact(
    artifact: Artifact, db: AsyncSession
) -> list[Record]:
    """Return all records that belong to a specific artifact.

    Records are linked via metadata_.source_file matching the artifact filename.
    Sorted by relevance (highest first).
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
    return [
        r for r in all_records
        if r.metadata_
        and isinstance(r.metadata_, dict)
        and r.metadata_.get("source_file") == artifact.original_filename
    ]


async def get_record(record_id: UUID, db: AsyncSession) -> Record:
    from fastapi import HTTPException

    result = await db.execute(select(Record).where(Record.id == record_id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    return record


# Relevance threshold: items below this are "potentially not relevant"
RELEVANCE_THRESHOLD = 0.4


async def build_evidence_preview(
    matter_id: UUID, user_id: UUID, db: AsyncSession
) -> dict:
    """Build an organized evidence preview for the client.

    Returns artifacts grouped into three sections:
    1. relevant — items scored above the threshold, sorted by relevance
    2. sensitive — items with any sensitivity flag, regardless of relevance
    3. low_relevance — items scored below the threshold
    Each item includes extraction summary and sensitivity flags.
    """
    from app.extraction.models import Extraction

    # Fetch all artifacts owned by this user in this matter
    result = await db.execute(
        select(Artifact)
        .where(Artifact.matter_id == matter_id, Artifact.owner_user_id == user_id)
        .order_by(Artifact.relevance_score.desc())
    )
    artifacts = list(result.scalars().all())

    # Batch-fetch all extractions for these artifacts
    art_ids = [a.id for a in artifacts]
    ext_result = await db.execute(
        select(Extraction).where(Extraction.artifact_id.in_(art_ids))
    )
    ext_map = {e.artifact_id: e for e in ext_result.scalars().all()}

    relevant = []
    sensitive = []
    low_relevance = []

    for art in artifacts:
        ext = ext_map.get(art.id)
        is_sensitive = False
        sensitivity_flags = {}
        if ext and ext.sensitivity_flags:
            sensitivity_flags = ext.sensitivity_flags
            is_sensitive = any(sensitivity_flags.values())

        item = {
            "artifact_id": str(art.id),
            "filename": art.original_filename,
            "mime_type": art.mime_type,
            "status": art.status,
            "category": art.category,
            "relevance_score": art.relevance_score,
            "relevance_rationale": art.relevance_rationale or "",
            "tags": art.tags,
            "is_sensitive": is_sensitive,
            "sensitivity_flags": sensitivity_flags,
            "summary": (ext.summary or ext.overall_summary or "") if ext else "",
            "doc_type": ext.doc_type_guess if ext else "unknown",
            "uploaded_at": str(art.import_timestamp),
        }

        # Sensitive items always appear in the sensitive section
        if is_sensitive:
            sensitive.append(item)

        if art.relevance_score >= RELEVANCE_THRESHOLD:
            relevant.append(item)
        else:
            low_relevance.append(item)

    # Group relevant items by category for display
    relevant_by_category: dict[str, list] = {}
    for item in relevant:
        cat = item["category"]
        relevant_by_category.setdefault(cat, []).append(item)

    return {
        "matter_id": str(matter_id),
        "total": len(artifacts),
        "relevant_count": len(relevant),
        "sensitive_count": len(sensitive),
        "low_relevance_count": len(low_relevance),
        "relevant_by_category": relevant_by_category,
        "sensitive_items": sensitive,
        "low_relevance_items": low_relevance,
    }
