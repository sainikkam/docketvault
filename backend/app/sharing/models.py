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


class RecordShareState(BaseID, table=True):
    """Per-record inclusion/exclusion within an approved artifact.

    Lets clients approve a multi-item file (e.g. JSONL of emails) while
    choosing exactly which individual records to share with the attorney.
    Default state is "included"; records below the relevance threshold
    are auto-set to "excluded" when the SharePolicy is first created.
    """
    __tablename__ = "record_share_states"
    __table_args__ = (UniqueConstraint("share_policy_id", "record_id"),)
    share_policy_id: UUID = Field(foreign_key="share_policies.id", index=True)
    record_id: UUID = Field(foreign_key="records.id", index=True)
    state: str = Field(default="included", max_length=20)  # included | excluded


# --- Request/response schemas ---


class ShareUpdate(SQLModel):
    artifact_id: str
    state: str  # "approved" | "excluded"
    acknowledge_sensitive: bool = False


class BatchShareUpdateRequest(SQLModel):
    updates: list[ShareUpdate]


class RecordShareUpdate(SQLModel):
    record_id: str
    state: str  # "included" | "excluded"


class BatchRecordShareUpdateRequest(SQLModel):
    artifact_id: str
    updates: list[RecordShareUpdate]
