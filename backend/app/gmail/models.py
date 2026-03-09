"""Gmail integration schemas.

Defines request/response models for Gmail search and import endpoints.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import SQLModel


class GmailSearchRequest(SQLModel):
    """Search Gmail using either a raw query or an evidence request ID.

    If request_id is provided, the LLM generates a Gmail query from
    the evidence request's title, description, keywords, and date range.
    If raw_query is provided, it's used directly as the Gmail search.
    At least one must be set.
    """

    request_id: Optional[UUID] = None
    raw_query: Optional[str] = None
    max_results: int = 25


class GmailMessagePreview(SQLModel):
    """Lightweight preview of a Gmail message for the client to review."""

    message_id: str
    subject: str
    sender: str
    date: Optional[str] = None
    snippet: str
    has_attachments: bool = False
    attachment_count: int = 0


class GmailSearchResponse(SQLModel):
    """Response from Gmail search — previews + the query that was used."""

    query: str
    total_results: int
    messages: list[GmailMessagePreview]


class GmailImportRequest(SQLModel):
    """Import selected Gmail messages into a matter as evidence."""

    message_ids: list[str]
    include_attachments: bool = True
