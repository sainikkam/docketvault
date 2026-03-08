from datetime import datetime
from uuid import UUID

from sqlalchemy import Text
from sqlmodel import Column, Field, SQLModel

from app.base_model import BaseID


class ConnectedAccount(BaseID, table=True):
    __tablename__ = "connected_accounts"
    user_id: UUID = Field(foreign_key="users.id", index=True)
    provider: str = Field(default="google", max_length=50)
    access_token: str = Field(sa_column=Column(Text))  # TODO: encrypt at rest
    refresh_token: str = Field(sa_column=Column(Text))  # TODO: encrypt at rest
    token_expires_at: datetime
    connected_at: datetime = Field(default_factory=datetime.utcnow)


# --- Request/response schemas ---


class DriveImportRequest(SQLModel):
    file_ids: list[str]


class DriveFileResponse(SQLModel):
    id: str
    name: str
    mimeType: str
    modifiedTime: str | None = None
    size: str | None = None
