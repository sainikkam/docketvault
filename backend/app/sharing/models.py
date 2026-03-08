from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.base_model import BaseID


class SharePolicy(BaseID, table=True):
    __tablename__ = "share_policies"
    __table_args__ = (UniqueConstraint("matter_id", "artifact_id"),)
    matter_id: UUID = Field(foreign_key="matters.id", index=True)
    artifact_id: UUID = Field(foreign_key="artifacts.id", index=True)
    owner_user_id: UUID = Field(foreign_key="users.id")
    state: str = Field(default="pending", max_length=20)  # pending|approved|excluded|revoked
    is_sensitive: bool = Field(default=False)
    sensitivity_acknowledged: bool = Field(default=False)
    approved_at: Optional[datetime] = Field(default=None)
    revoked_at: Optional[datetime] = Field(default=None)


# --- Request/response schemas ---


class ShareUpdate(SQLModel):
    artifact_id: str
    state: str  # "approved" | "excluded"
    acknowledge_sensitive: bool = False


class BatchShareUpdateRequest(SQLModel):
    updates: list[ShareUpdate]
