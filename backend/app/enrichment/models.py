from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from sqlalchemy import JSON, Text
from sqlmodel import Column, Field, SQLModel

from app.base_model import BaseID


class TimelineEvent(BaseID, table=True):
    __tablename__ = "timeline_events"
    matter_id: UUID = Field(foreign_key="matters.id", index=True)
    event_type: str = Field(default="unknown", max_length=50)
    title: str = Field(max_length=500)
    event_ts: Optional[datetime] = Field(default=None)
    actors: list = Field(default=[], sa_column=Column(JSON))
    summary: str = Field(default="", sa_column=Column(Text))
    confidence: float = Field(default=0.0)
    verification_state: str = Field(default="needs_review", max_length=20)
    citations: list = Field(default=[], sa_column=Column(JSON))
    related_record_ids: list = Field(default=[], sa_column=Column(JSON))


class MissingItem(BaseID, table=True):
    __tablename__ = "missing_items"
    matter_id: UUID = Field(foreign_key="matters.id", index=True)
    missing_type: str = Field(max_length=50)
    description: str = Field(default="", sa_column=Column(Text))
    priority: str = Field(default="medium", max_length=10)
    status: str = Field(default="open", max_length=20)


class IntakeSummary(BaseID, table=True):
    __tablename__ = "intake_summaries"
    matter_id: UUID = Field(foreign_key="matters.id", unique=True)
    case_overview: str = Field(default="", sa_column=Column(Text))
    key_timeline: list = Field(default=[], sa_column=Column(JSON))
    open_questions: list = Field(default=[], sa_column=Column(JSON))
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# --- Response schemas ---


class TimelineEventResponse(SQLModel):
    id: UUID
    matter_id: UUID
    event_type: str
    title: str
    event_ts: Optional[datetime]
    actors: list
    summary: str
    confidence: float
    verification_state: str
    citations: list
    related_record_ids: list
    created_at: datetime


class MissingItemResponse(SQLModel):
    id: UUID
    matter_id: UUID
    missing_type: str
    description: str
    priority: str
    status: str
    created_at: datetime


class IntakeSummaryResponse(SQLModel):
    id: UUID
    matter_id: UUID
    case_overview: str
    key_timeline: list
    open_questions: list
    generated_at: datetime
