import asyncio
import csv
import io
import json
import zipfile
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.config import Settings
from app.enrichment.models import IntakeSummary
from app.evidence.models import Artifact, Record
from app.matters.models import AuditLog, Matter
from app.sharing.service import get_approved_artifact_ids
from app.storage import get_storage


async def generate_evidence_pack(
    db: AsyncSession, matter_id: UUID, user_id: UUID
) -> bytes:
    """Generate Evidence Pack ZIP (approved artifacts only). Returns ZIP bytes."""
    settings = Settings()
    storage = get_storage(settings)

    matter_result = await db.execute(
        select(Matter).where(Matter.id == matter_id)
    )
    matter = matter_result.scalars().first()

    # 1. Get approved artifact IDs
    approved_ids = await get_approved_artifact_ids(db, matter_id)
    art_result = await db.execute(
        select(Artifact).where(
            Artifact.matter_id == matter_id,
            Artifact.id.in_(approved_ids) if approved_ids else Artifact.id == None,
        )
    )
    artifacts = list(art_result.scalars().all())

    # 2. Get records
    rec_result = await db.execute(
        select(Record).where(Record.matter_id == matter_id)
    )
    records = list(rec_result.scalars().all())

    # 3. Build ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:

        # intake_summary.json
        sum_result = await db.execute(
            select(IntakeSummary).where(IntakeSummary.matter_id == matter_id)
        )
        summary = sum_result.scalars().first()
        if summary:
            summary_data = {
                "matter_title": matter.title if matter else "",
                "generated_at": datetime.utcnow().isoformat(),
                "ai_draft_notice": "AI-assisted draft — verify all claims against source evidence",
                "case_overview": summary.case_overview,
                "key_timeline": summary.key_timeline,
                "open_questions": summary.open_questions,
            }
            zf.writestr(
                "intake_summary.json",
                json.dumps(summary_data, indent=2, default=str),
            )

        # evidence_index.csv
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow([
            "artifact_id", "original_filename", "mime_type",
            "source_system", "sha256", "uploaded_at",
        ])
        for art in artifacts:
            writer.writerow([
                str(art.id), art.original_filename, art.mime_type,
                art.source_system, art.sha256 or "",
                art.created_at.isoformat() if art.created_at else "",
            ])
        zf.writestr("evidence_index.csv", csv_buffer.getvalue())

        # approved_records.jsonl
        records_lines = []
        for rec in records:
            records_lines.append(json.dumps({
                "id": str(rec.id),
                "matter_id": str(rec.matter_id),
                "source": rec.source,
                "type": rec.type,
                "category": rec.category if hasattr(rec, "category") else "uncategorized",
                "tags": rec.tags,
                "text": rec.text,
                "ts": rec.ts.isoformat() if rec.ts else None,
            }, default=str))
        zf.writestr("approved_records.jsonl", "\n".join(records_lines))

        # approved_artifacts/ — download each file
        for art in artifacts:
            try:
                uri = art.storage_uri
                if uri.startswith("local://"):
                    key = uri[len("local://"):]
                elif uri.startswith("s3://"):
                    parts = uri[len("s3://"):].split("/", 1)
                    key = parts[1] if len(parts) > 1 else parts[0]
                else:
                    key = uri
                file_bytes = await storage.download(key)
                zf.writestr(
                    f"approved_artifacts/{art.original_filename}", file_bytes
                )
            except Exception:
                pass  # skip files that can't be downloaded

        # hash_manifest.csv
        manifest_buffer = io.StringIO()
        mwriter = csv.writer(manifest_buffer)
        mwriter.writerow([
            "artifact_id", "sha256", "source_system", "source_id",
            "original_filename", "import_timestamp",
        ])
        for art in artifacts:
            mwriter.writerow([
                str(art.id), art.sha256 or "", art.source_system,
                art.source_id or "", art.original_filename,
                art.created_at.isoformat() if art.created_at else "",
            ])
        zf.writestr("hash_manifest.csv", manifest_buffer.getvalue())

        # audit_excerpt.jsonl
        audit_result = await db.execute(
            select(AuditLog)
            .where(AuditLog.matter_id == matter_id)
            .order_by(AuditLog.created_at)
        )
        audit_lines = []
        for entry in audit_result.scalars().all():
            audit_lines.append(json.dumps({
                "id": str(entry.id),
                "user_id": str(entry.user_id),
                "action": entry.action,
                "created_at": entry.created_at.isoformat() if entry.created_at else None,
            }, default=str))
        zf.writestr("audit_excerpt.jsonl", "\n".join(audit_lines))

    return zip_buffer.getvalue()
