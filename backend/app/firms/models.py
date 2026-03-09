from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, Text
from sqlmodel import Column, Field, SQLModel

from app.base_model import BaseID


class Firm(BaseID, table=True):
    __tablename__ = "firms"
    name: str = Field(max_length=255)
    retention_days: int = Field(default=365)
    paralegal_can_export: bool = Field(default=False)
    created_by: UUID = Field(foreign_key="users.id")


class MatterTemplate(BaseID, table=True):
    __tablename__ = "matter_templates"
    firm_id: UUID = Field(foreign_key="firms.id")
    name: str = Field(max_length=255)
    checklist: list = Field(default=[], sa_column=Column(JSON))


class RequestTemplate(BaseID, table=True):
    """Reusable document request template for a firm.

    Lawyers pick a template to pre-fill the structured request form
    with category, description, format, and preservation language.
    """

    __tablename__ = "request_templates"
    firm_id: UUID = Field(foreign_key="firms.id", index=True)
    name: str = Field(max_length=255)
    # Pre-set category (email, chat_logs, social_media, etc.)
    category: str = Field(max_length=50)
    default_description: str = Field(
        default="", sa_column=Column("default_description", Text)
    )
    default_format_instructions: str = Field(
        default="", sa_column=Column("default_format_instructions", Text)
    )
    default_preservation_note: str = Field(
        default="", sa_column=Column("default_preservation_note", Text)
    )
    default_source_system: Optional[str] = Field(default=None, max_length=100)


# --- Request/response schemas ---


class FirmCreateRequest(SQLModel):
    name: str


class FirmUpdateRequest(SQLModel):
    name: Optional[str] = None
    retention_days: Optional[int] = None
    paralegal_can_export: Optional[bool] = None


class FirmResponse(SQLModel):
    id: UUID
    name: str
    retention_days: int
    paralegal_can_export: bool
    created_by: UUID


class TemplateCreateRequest(SQLModel):
    name: str
    checklist: list = []


class TemplateResponse(SQLModel):
    id: UUID
    firm_id: UUID
    name: str
    checklist: list


class RequestTemplateCreateRequest(SQLModel):
    name: str
    category: str
    default_description: str = ""
    default_format_instructions: str = ""
    default_preservation_note: str = ""
    default_source_system: Optional[str] = None


class RequestTemplateResponse(SQLModel):
    id: UUID
    firm_id: UUID
    name: str
    category: str
    default_description: str
    default_format_instructions: str
    default_preservation_note: str
    default_source_system: Optional[str] = None
