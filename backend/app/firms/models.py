from typing import Optional
from uuid import UUID

from sqlalchemy import JSON
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
