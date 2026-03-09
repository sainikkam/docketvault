from uuid import UUID

from app.evidence.models import Artifact, Record
from app.storage import StorageBackend


class BaseAdapter:
    """Interface for export parsers. New adapters can be added by implementing
    this interface and registering in IngestionService."""

    def can_handle(self, filename: str, mime_type: str) -> bool:
        raise NotImplementedError

    async def parse(
        self,
        file_bytes: bytes,
        matter_id: UUID,
        owner_id: UUID,
        storage: StorageBackend,
        **kwargs,
    ) -> tuple[list[Record], list[Artifact]]:
        raise NotImplementedError
