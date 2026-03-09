import hashlib
import json
import mimetypes
import os
import tempfile
import zipfile
from uuid import UUID, uuid4

from app.evidence.adapters.base import BaseAdapter
from app.evidence.adapters.jsonl_adapter import parse_jsonl_lines
from app.evidence.models import Artifact, Record
from app.storage import StorageBackend

# Plain text extensions that become a single Record (whole file as text)
PLAIN_TEXT_EXTENSIONS = {".txt", ".csv", ".md"}

# JSON / JSONL get special handling
JSON_EXTENSION = ".json"
JSONL_EXTENSION = ".jsonl"


class GenericZipAdapter(BaseAdapter):
    """Unpack ZIP, store each file as an Artifact.

    Special handling per file type:
      .jsonl  -> one Record per line (via parse_jsonl_lines)
      .json   -> one Record for the whole object
      .txt/.csv/.md -> one Record with full text
      image/pdf/audio/video -> Artifact with status="processing" for extraction
      everything else -> Artifact with status="needs_review"
    """

    def can_handle(self, filename: str, mime_type: str) -> bool:
        return mime_type == "application/zip" or filename.endswith(".zip")

    async def parse(
        self,
        file_bytes: bytes,
        matter_id: UUID,
        owner_id: UUID,
        storage: StorageBackend,
        **kwargs,
    ) -> tuple[list[Record], list[Artifact]]:
        records: list[Record] = []
        artifacts: list[Artifact] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "upload.zip")
            with open(zip_path, "wb") as f:
                f.write(file_bytes)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmpdir)
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    extracted_path = os.path.join(tmpdir, info.filename)
                    if not os.path.exists(extracted_path):
                        continue

                    with open(extracted_path, "rb") as ef:
                        data = ef.read()

                    filename = os.path.basename(info.filename)
                    mime, _ = mimetypes.guess_type(filename)
                    mime = mime or "application/octet-stream"
                    sha = hashlib.sha256(data).hexdigest()
                    artifact_id = uuid4()
                    key = f"{matter_id}/{artifact_id}/{filename}"
                    uri = await storage.upload(key, data)

                    _, ext = os.path.splitext(filename)
                    ext_lower = ext.lower()

                    is_extractable = (
                        mime.startswith(("image/", "audio/", "video/"))
                        or mime == "application/pdf"
                    )

                    # Pick the right MIME and status for JSONL files
                    artifact_mime = "application/jsonl" if ext_lower == JSONL_EXTENSION else mime
                    artifact_status = (
                        "processing" if is_extractable
                        else "ready" if ext_lower == JSONL_EXTENSION
                        else "needs_review"
                    )

                    artifact = Artifact(
                        id=artifact_id,
                        matter_id=matter_id,
                        owner_user_id=owner_id,
                        mime_type=artifact_mime,
                        original_filename=filename,
                        file_size_bytes=len(data),
                        sha256=sha,
                        storage_uri=uri,
                        source_system="export_zip",
                        source_id=info.filename,
                        status=artifact_status,
                    )
                    artifacts.append(artifact)

                    # --- Per-type Record creation ---

                    if ext_lower == JSONL_EXTENSION:
                        # JSONL: one Record per line
                        line_records = parse_jsonl_lines(
                            data, matter_id, owner_id, filename
                        )
                        records.extend(line_records)

                    elif ext_lower == JSON_EXTENSION:
                        # Single JSON object: one Record
                        record = _json_to_record(
                            data, matter_id, owner_id, info.filename
                        )
                        if record:
                            records.append(record)

                    elif ext_lower in PLAIN_TEXT_EXTENSIONS:
                        # Plain text: one Record with full content
                        try:
                            text_content = data.decode("utf-8", errors="replace")
                        except Exception:
                            text_content = ""
                        record = Record(
                            matter_id=matter_id,
                            owner_user_id=owner_id,
                            source="export",
                            type="unknown",
                            text=text_content,
                            raw_pointer=info.filename,
                        )
                        records.append(record)

        return records, artifacts


def _json_to_record(
    data: bytes, matter_id: UUID, owner_id: UUID, zip_path: str
) -> Record | None:
    """Create a single Record from a .json file."""
    try:
        text_content = data.decode("utf-8", errors="replace")
        obj = json.loads(text_content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    # Use a summary as text if available, otherwise the raw JSON
    text = obj.get("text", text_content[:2000])
    source = obj.get("source", "export")
    record_type = obj.get("type", "json_object")

    return Record(
        matter_id=matter_id,
        owner_user_id=owner_id,
        source=source,
        type=record_type,
        text=text,
        metadata_=obj,
        raw_pointer=zip_path,
    )
