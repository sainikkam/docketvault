"""Adapter for JSONL (JSON Lines) files.

Parses each line of a .jsonl file into an individual Record, mapping common
fields from portable data exports (like competition persona datasets) to
the Record model. Also stores the raw file as a single Artifact for
provenance and download.

Supported JSONL field mapping:
  id   -> stored in metadata_.original_id
  ts   -> Record.ts (parsed as ISO datetime)
  source -> Record.source (e.g. "bank", "email", "ai_chat")
  type -> Record.type (e.g. "transaction", "sent", "chat_turn")
  text -> Record.text
  tags -> Record.tags
  refs -> stored in metadata_.refs
  pii_level -> stored in metadata_.pii_level
"""

import hashlib
import json
from datetime import datetime
from uuid import UUID, uuid4

from app.evidence.adapters.base import BaseAdapter
from app.evidence.models import Artifact, Record
from app.storage import StorageBackend


class JsonlAdapter(BaseAdapter):
    """Parse JSONL files into individual Records, one per line."""

    def can_handle(self, filename: str, mime_type: str) -> bool:
        return filename.lower().endswith(".jsonl")

    async def parse(
        self,
        file_bytes: bytes,
        matter_id: UUID,
        owner_id: UUID,
        storage: StorageBackend,
        *,
        filename: str = "data.jsonl",
        source_id: str | None = None,
    ) -> tuple[list[Record], list[Artifact]]:
        records: list[Record] = []
        artifacts: list[Artifact] = []

        # Store the raw .jsonl file as an Artifact for provenance
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        artifact_id = uuid4()
        key = f"{matter_id}/{artifact_id}/{filename}"
        uri = await storage.upload(key, file_bytes)

        artifact = Artifact(
            id=artifact_id,
            matter_id=matter_id,
            owner_user_id=owner_id,
            mime_type="application/jsonl",
            original_filename=filename,
            file_size_bytes=len(file_bytes),
            sha256=sha256,
            storage_uri=uri,
            source_system="export_zip" if source_id else "upload",
            source_id=source_id,
            status="ready",
        )
        artifacts.append(artifact)

        # Parse each line into a Record
        text_content = file_bytes.decode("utf-8", errors="replace")
        for line_num, line in enumerate(text_content.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            record = _entry_to_record(
                entry=entry,
                matter_id=matter_id,
                owner_id=owner_id,
                filename=filename,
                line_num=line_num,
            )
            records.append(record)

        return records, artifacts


def parse_jsonl_lines(
    file_bytes: bytes,
    matter_id: UUID,
    owner_id: UUID,
    filename: str = "data.jsonl",
) -> list[Record]:
    """Parse JSONL bytes into Records without creating an Artifact.

    Used by GenericZipAdapter when it handles artifact storage itself.
    """
    records: list[Record] = []
    text_content = file_bytes.decode("utf-8", errors="replace")

    for line_num, line in enumerate(text_content.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        record = _entry_to_record(
            entry=entry,
            matter_id=matter_id,
            owner_id=owner_id,
            filename=filename,
            line_num=line_num,
        )
        records.append(record)

    return records


def _entry_to_record(
    entry: dict,
    matter_id: UUID,
    owner_id: UUID,
    filename: str,
    line_num: int,
) -> Record:
    """Convert a single JSONL entry dict into a Record.

    Maps common portable-export fields to the Record model. Unknown fields
    are preserved in metadata_ so nothing is lost.
    """
    # Parse timestamp if present
    ts = None
    if entry.get("ts"):
        try:
            ts = datetime.fromisoformat(entry["ts"])
        except (ValueError, TypeError):
            pass

    # Determine source — use entry's source field, fall back to filename
    source = entry.get("source", _source_from_filename(filename))
    record_type = entry.get("type", "unknown")
    text = entry.get("text", json.dumps(entry))
    tags = entry.get("tags", [])

    # Preserve extra fields in metadata
    metadata = {
        "original_id": entry.get("id"),
        "source_file": filename,
        "line_number": line_num,
    }
    if entry.get("refs"):
        metadata["refs"] = entry["refs"]
    if entry.get("pii_level"):
        metadata["pii_level"] = entry["pii_level"]

    # Carry forward any non-standard fields the export might contain
    standard_keys = {"id", "ts", "source", "type", "text", "tags", "refs", "pii_level"}
    extras = {k: v for k, v in entry.items() if k not in standard_keys}
    if extras:
        metadata["extra_fields"] = extras

    return Record(
        matter_id=matter_id,
        owner_user_id=owner_id,
        ts=ts,
        source=source,
        type=record_type,
        text=text,
        tags=tags,
        metadata_=metadata,
        raw_pointer=f"{filename}:{line_num}",
    )


def _source_from_filename(filename: str) -> str:
    """Infer a source label from the filename when the entry has no source."""
    name = filename.lower().rsplit(".", 1)[0]
    known = {
        "transactions": "bank",
        "emails": "email",
        "calendar": "calendar",
        "conversations": "ai_chat",
        "lifelog": "lifelog",
        "social_posts": "social",
        "files_index": "files",
    }
    return known.get(name, "export")
