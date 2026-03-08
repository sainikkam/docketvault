import hashlib
import mimetypes
import os
import tempfile
import zipfile
from uuid import UUID, uuid4

from app.evidence.adapters.base import BaseAdapter
from app.evidence.models import Artifact, Record
from app.storage import StorageBackend

TEXT_EXTENSIONS = {".txt", ".csv", ".json", ".jsonl"}


class GenericZipAdapter(BaseAdapter):
    """Unpack ZIP, store each file as an Artifact. Text files also get a Record."""

    def can_handle(self, filename: str, mime_type: str) -> bool:
        return mime_type == "application/zip" or filename.endswith(".zip")

    async def parse(
        self,
        file_bytes: bytes,
        matter_id: UUID,
        owner_id: UUID,
        storage: StorageBackend,
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
                    is_extractable = (
                        mime.startswith(("image/", "audio/", "video/"))
                        or mime == "application/pdf"
                    )

                    artifact = Artifact(
                        id=artifact_id,
                        matter_id=matter_id,
                        owner_user_id=owner_id,
                        mime_type=mime,
                        original_filename=filename,
                        file_size_bytes=len(data),
                        sha256=sha,
                        storage_uri=uri,
                        source_system="export_zip",
                        source_id=info.filename,
                        status="processing" if is_extractable else "needs_review",
                    )
                    artifacts.append(artifact)

                    # Text files also get a Record
                    if ext.lower() in TEXT_EXTENSIONS:
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
