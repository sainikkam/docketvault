from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import JSON, Text
from sqlmodel import Column, Field, SQLModel

from app.base_model import BaseID


class Extraction(BaseID, table=True):
    __tablename__ = "extractions"
    artifact_id: UUID = Field(foreign_key="artifacts.id", index=True)
    extracted_text: str = Field(default="", sa_column=Column(Text))
    summary: str = Field(default="", sa_column=Column(Text))
    doc_type_guess: str = Field(default="unknown", max_length=50)
    structured_claims: dict = Field(default={}, sa_column=Column(JSON))
    sensitivity_flags: dict = Field(default={}, sa_column=Column(JSON))
    confidence: float = Field(default=0.0)
    verification_state: str = Field(default="needs_review", max_length=20)
    # Audio/video fields (populated in Chunk 7):
    transcript: Optional[list] = Field(default=None, sa_column=Column(JSON))
    key_moments: Optional[list] = Field(default=None, sa_column=Column(JSON))
    overall_summary: Optional[str] = Field(default=None, sa_column=Column(Text))


# --- Response schemas ---


class ExtractionResponse(SQLModel):
    id: UUID
    artifact_id: UUID
    extracted_text: str
    summary: str
    doc_type_guess: str
    structured_claims: dict
    sensitivity_flags: dict
    confidence: float
    verification_state: str
    transcript: Optional[list] = None
    key_moments: Optional[list] = None
    overall_summary: Optional[str] = None
    created_at: datetime
