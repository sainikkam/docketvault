from datetime import date, datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, Text, UniqueConstraint
from sqlmodel import Column, Field, SQLModel

from app.base_model import BaseID


class Matter(BaseID, table=True):
    __tablename__ = "matters"
    firm_id: UUID = Field(foreign_key="firms.id")
    template_id: Optional[UUID] = Field(default=None, foreign_key="matter_templates.id")
    title: str = Field(max_length=255)
    status: str = Field(default="active", max_length=50)
    created_by: UUID = Field(foreign_key="users.id")


class MatterMember(BaseID, table=True):
    __tablename__ = "matter_members"
    __table_args__ = (UniqueConstraint("matter_id", "user_id"),)
    matter_id: UUID = Field(foreign_key="matters.id")
    user_id: UUID = Field(foreign_key="users.id")
    role: str = Field(max_length=50)
    joined_at: datetime = Field(default_factory=datetime.utcnow)


class Invitation(BaseID, table=True):
    __tablename__ = "invitations"
    matter_id: UUID = Field(foreign_key="matters.id")
    token: str = Field(unique=True, max_length=255)
    role: str = Field(max_length=50)
    accepted_at: Optional[datetime] = Field(default=None)
    created_by: UUID = Field(foreign_key="users.id")


class AuditLog(BaseID, table=True):
    """Append-only. No UPDATE or DELETE operations allowed on this table."""

    __tablename__ = "audit_logs"
    matter_id: Optional[UUID] = Field(default=None, foreign_key="matters.id")
    user_id: UUID = Field(foreign_key="users.id")
    action: str = Field(max_length=100)
    target_type: Optional[str] = Field(default=None, max_length=50)
    target_id: Optional[UUID] = Field(default=None)
    metadata_: dict = Field(default={}, sa_column=Column("metadata", JSON))


class EvidenceRequest(BaseID, table=True):
    """Lawyer → Client structured document request (RFP).

    Supports both free-text and structured fields so lawyers can issue
    precise, legally-defensible requests with categories, date ranges,
    keywords, format instructions, and preservation notes.
    """

    __tablename__ = "requests"
    matter_id: UUID = Field(foreign_key="matters.id", index=True)
    created_by: UUID = Field(foreign_key="users.id")
    title: str = Field(max_length=500)
    description: str = Field(default="", sa_column=Column(Text))
    priority: str = Field(default="medium", max_length=10)
    status: str = Field(default="open", max_length=20)

    # -- Structured RFP fields --
    # Category of data sought (email, browser_history, social_media, etc.)
    category: Optional[str] = Field(default=None, max_length=50)
    # Date range bounding the request (e.g. "all emails from Jan 1 to Mar 1")
    date_range_start: Optional[date] = Field(default=None)
    date_range_end: Optional[date] = Field(default=None)
    # Search terms the client should use when finding data
    keywords: list = Field(default=[], sa_column=Column(JSON))
    # Where the client should look (Gmail, WhatsApp, Company laptop, etc.)
    source_system: Optional[str] = Field(
        default=None, sa_column=Column("source_system", Text)
    )
    # How to deliver the data (native format, PDF, etc.)
    format_instructions: Optional[str] = Field(
        default=None, sa_column=Column("format_instructions", Text)
    )
    # Legal hold / preservation language
    preservation_note: Optional[str] = Field(
        default=None, sa_column=Column("preservation_note", Text)
    )
    # AI-generated checklist, reviewed/edited by lawyer before sending.
    # Each item: {"item": str, "completed": bool}
    checklist: list = Field(default=[], sa_column=Column("checklist", JSON))


# --- Request/response schemas ---


class MatterCreateRequest(SQLModel):
    firm_id: UUID
    template_id: Optional[UUID] = None
    title: str


class MatterResponse(SQLModel):
    id: UUID
    firm_id: UUID
    template_id: Optional[UUID] = None
    title: str
    status: str
    created_by: UUID


class InvitationCreateRequest(SQLModel):
    role: str


class InvitationResponse(SQLModel):
    id: UUID
    matter_id: UUID
    token: str
    role: str
    accepted_at: Optional[datetime] = None
    created_by: UUID


class MemberResponse(SQLModel):
    id: UUID
    matter_id: UUID
    user_id: UUID
    role: str
    joined_at: datetime


class AuditLogResponse(SQLModel):
    id: UUID
    matter_id: Optional[UUID]
    user_id: UUID
    action: str
    target_type: Optional[str]
    target_id: Optional[UUID]
    created_at: datetime


class CreateEvidenceRequestBody(SQLModel):
    title: str
    description: str = ""
    priority: str = "medium"
    # Structured RFP fields (all optional for backwards compatibility)
    category: Optional[str] = None
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    keywords: list = []
    source_system: Optional[str] = None
    format_instructions: Optional[str] = None
    preservation_note: Optional[str] = None
    # AI-generated checklist, reviewed by the lawyer before sending
    checklist: list = []


class EvidenceRequestResponse(SQLModel):
    id: UUID
    matter_id: UUID
    created_by: UUID
    title: str
    description: str
    priority: str
    status: str
    category: Optional[str] = None
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    keywords: list = []
    source_system: Optional[str] = None
    format_instructions: Optional[str] = None
    preservation_note: Optional[str] = None
    checklist: list = []
    created_at: datetime
