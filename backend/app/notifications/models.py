from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, Text
from sqlmodel import Column, Field, SQLModel

from app.base_model import BaseID


class Notification(BaseID, table=True):
    __tablename__ = "notifications"
    user_id: UUID = Field(foreign_key="users.id", index=True)
    matter_id: Optional[UUID] = Field(default=None, foreign_key="matters.id")
    type: str = Field(max_length=50)
    title: str = Field(max_length=255)
    body: str = Field(default="", sa_column=Column(Text))
    metadata_: dict = Field(default={}, sa_column=Column("metadata", JSON))
    read_at: Optional[datetime] = Field(default=None)


# --- Response schemas ---


class NotificationResponse(SQLModel):
    id: UUID
    user_id: UUID
    matter_id: Optional[UUID]
    type: str
    title: str
    body: str
    read_at: Optional[datetime]
    created_at: datetime
