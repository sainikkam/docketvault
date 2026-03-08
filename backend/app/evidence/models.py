from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, BigInteger, Text
from sqlmodel import Column, Field, SQLModel

from app.base_model import BaseID


class Record(BaseID, table=True):
    __tablename__ = "records"
    matter_id: UUID = Field(foreign_key="matters.id", index=True)
    owner_user_id: UUID = Field(foreign_key="users.id")
    ts: Optional[datetime] = Field(default=None)
    source: str = Field(max_length=50)
    type: str = Field(max_length=50)
    text: str = Field(default="", sa_column=Column(Text))
    metadata_: dict = Field(default={}, sa_column=Column("metadata", JSON))
    tags: list = Field(default=[], sa_column=Column(JSON))
    raw_pointer: Optional[str] = Field(default=None, max_length=500)


class Artifact(BaseID, table=True):
    __tablename__ = "artifacts"
    matter_id: UUID = Field(foreign_key="matters.id", index=True)
    owner_user_id: UUID = Field(foreign_key="users.id")
    mime_type: str = Field(max_length=100)
    original_filename: str = Field(max_length=500)
    file_size_bytes: int = Field(sa_column=Column(BigInteger))
    sha256: Optional[str] = Field(default=None, max_length=64)
    storage_uri: str = Field(max_length=500)
    source_system: str = Field(max_length=50)
    source_id: Optional[str] = Field(default=None, max_length=255)
    original_timestamps: dict = Field(default={}, sa_column=Column(JSON))
    import_timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="uploading", max_length=50)
    is_duplicate: bool = Field(default=False)
    duplicate_of: Optional[UUID] = Field(default=None, foreign_key="artifacts.id")


# --- Request/response schemas ---


class ArtifactResponse(SQLModel):
    id: UUID
    matter_id: UUID
    owner_user_id: UUID
    mime_type: str
    original_filename: str
    file_size_bytes: int
    sha256: Optional[str]
    storage_uri: str
    source_system: str
    status: str
    import_timestamp: datetime
    is_duplicate: bool = False
    duplicate_of: Optional[UUID] = None


class RecordResponse(SQLModel):
    id: UUID
    matter_id: UUID
    owner_user_id: UUID
    ts: Optional[datetime]
    source: str
    type: str
    text: str
    tags: list


class UploadResponse(SQLModel):
    uploaded: int
    artifacts: list[UUID]


class ManifestEntry(SQLModel):
    artifact_id: UUID
    sha256: str
    original_filename: str
    mime_type: str
    size_bytes: int
    source_system: str
    source_id: Optional[str] = None
    original_timestamps: dict = {}
    uploaded_at: datetime
    uploaded_by: UUID
    is_duplicate: bool
    duplicate_of: Optional[UUID] = None
    status: str


class MatterManifest(SQLModel):
    matter_id: UUID
    total_artifacts: int
    total_duplicates: int
    entries: list[ManifestEntry]
