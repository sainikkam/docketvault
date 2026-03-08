from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, Text, UniqueConstraint
from sqlmodel import Column, Field, SQLModel

from app.base_model import BaseID


class Matter(BaseID, table=True):
    __tablename__ = "matters"
    firm_id: UUID = Field(foreign_key="firms.id")
    template_id: UUID = Field(foreign_key="matter_templates.id")
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
    """Lawyer → Client evidence request."""

    __tablename__ = "requests"
    matter_id: UUID = Field(foreign_key="matters.id", index=True)
    created_by: UUID = Field(foreign_key="users.id")
    title: str = Field(max_length=500)
    description: str = Field(default="", sa_column=Column(Text))
    priority: str = Field(default="medium", max_length=10)
    status: str = Field(default="open", max_length=20)


# --- Request/response schemas ---


class MatterCreateRequest(SQLModel):
    firm_id: UUID
    template_id: UUID
    title: str


class MatterResponse(SQLModel):
    id: UUID
    firm_id: UUID
    template_id: UUID
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


class EvidenceRequestResponse(SQLModel):
    id: UUID
    matter_id: UUID
    created_by: UUID
    title: str
    description: str
    priority: str
    status: str
    created_at: datetime
