from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.models import User
from app.firms.models import (
    Firm,
    FirmCreateRequest,
    FirmUpdateRequest,
    MatterTemplate,
    RequestTemplate,
    RequestTemplateCreateRequest,
    TemplateCreateRequest,
)


def require_attorney(user: User) -> None:
    if user.role != "attorney":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only attorneys can perform this action",
        )


async def create_firm(req: FirmCreateRequest, user: User, db: AsyncSession) -> Firm:
    require_attorney(user)
    firm = Firm(name=req.name, created_by=user.id)
    db.add(firm)
    await db.commit()
    await db.refresh(firm)

    # Seed default request templates so every firm starts with standard RFPs
    await _seed_default_request_templates(firm.id, db)

    return firm


async def get_firm(firm_id: UUID, db: AsyncSession) -> Firm:
    result = await db.execute(select(Firm).where(Firm.id == firm_id))
    firm = result.scalars().first()
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")
    return firm


async def update_firm(
    firm_id: UUID, req: FirmUpdateRequest, user: User, db: AsyncSession
) -> Firm:
    require_attorney(user)
    firm = await get_firm(firm_id, db)
    if req.name is not None:
        firm.name = req.name
    if req.retention_days is not None:
        firm.retention_days = req.retention_days
    if req.paralegal_can_export is not None:
        firm.paralegal_can_export = req.paralegal_can_export
    db.add(firm)
    await db.commit()
    await db.refresh(firm)
    return firm


async def create_template(
    firm_id: UUID, req: TemplateCreateRequest, user: User, db: AsyncSession
) -> MatterTemplate:
    require_attorney(user)
    await get_firm(firm_id, db)
    template = MatterTemplate(
        firm_id=firm_id, name=req.name, checklist=req.checklist)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


async def list_templates(firm_id: UUID, db: AsyncSession) -> list[MatterTemplate]:
    result = await db.execute(
        select(MatterTemplate).where(MatterTemplate.firm_id == firm_id)
    )
    return list(result.scalars().all())

# --- Request template CRUD ---


async def create_request_template(
    firm_id: UUID,
    req: RequestTemplateCreateRequest,
    user: User,
    db: AsyncSession,
) -> RequestTemplate:
    """Create a reusable document request template for a firm."""
    require_attorney(user)
    await get_firm(firm_id, db)
    template = RequestTemplate(
        firm_id=firm_id,
        name=req.name,
        category=req.category,
        default_description=req.default_description,
        default_format_instructions=req.default_format_instructions,
        default_preservation_note=req.default_preservation_note,
        default_source_system=req.default_source_system,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


async def list_request_templates(
    firm_id: UUID, db: AsyncSession
) -> list[RequestTemplate]:
    """List all request templates for a firm."""
    result = await db.execute(
        select(RequestTemplate).where(RequestTemplate.firm_id == firm_id)
    )
    return list(result.scalars().all())


# -- Default request templates seeded for every new firm --

DEFAULT_REQUEST_TEMPLATES = [
    {
        "name": "Email Production",
        "category": "email",
        "default_description": (
            "Please produce all emails from the specified account(s) "
            "involving the key parties or containing the listed keywords."
        ),
        "default_format_instructions": (
            "Export as .mbox or .eml files. Do not convert to PDF. "
            "Preserve all metadata (sender, recipients, timestamps, attachments)."
        ),
        "default_preservation_note": (
            "Do not delete, archive, or modify any emails. "
            "Do not empty your Trash or Spam folders."
        ),
        "default_source_system": "Gmail / Outlook",
    },
    {
        "name": "Text & Chat Messages",
        "category": "chat_logs",
        "default_description": (
            "Please export all text messages and chat conversations "
            "with the specified contacts during the given date range."
        ),
        "default_format_instructions": (
            "Use the platform's built-in export feature. "
            "For iMessage, export via third-party tool (e.g. iMazing). "
            "For WhatsApp, use 'Export Chat' with media."
        ),
        "default_preservation_note": (
            "Do not delete any messages or conversations. "
            "Do not clear chat history."
        ),
        "default_source_system": "iMessage / WhatsApp / Slack",
    },
    {
        "name": "Social Media Export",
        "category": "social_media",
        "default_description": (
            "Please download your data from the specified social media platform(s) "
            "and provide the export files."
        ),
        "default_format_instructions": (
            "Use the platform's official data download tool "
            "(e.g. Facebook: Settings > Your Information > Download Your Information). "
            "Select JSON format if available."
        ),
        "default_preservation_note": (
            "Do not delete any posts, messages, or comments. "
            "Do not deactivate your account."
        ),
        "default_source_system": "Facebook / Instagram / Twitter",
    },
    {
        "name": "Financial Records",
        "category": "financial",
        "default_description": (
            "Please produce bank statements, receipts, invoices, or payment records "
            "for the specified date range."
        ),
        "default_format_instructions": (
            "Provide in native format (Excel/CSV, not PDF). "
            "If only PDF is available, ensure it is text-searchable. "
            "Do not redact any information without prior approval."
        ),
        "default_preservation_note": (
            "Do not delete or modify any financial records. "
            "Preserve all transaction history."
        ),
        "default_source_system": "Bank portal / Accounting software",
    },
    {
        "name": "Photos & Videos",
        "category": "photos",
        "default_description": (
            "Please provide all photos and videos taken during the specified "
            "date range that relate to the matter."
        ),
        "default_format_instructions": (
            "Provide original files — do not crop, edit, filter, or screenshot. "
            "Preserve EXIF metadata (location, timestamp). "
            "Upload as ZIP if there are many files."
        ),
        "default_preservation_note": (
            "Do not delete any photos or videos from your device or cloud storage. "
            "Do not edit or apply filters to any images."
        ),
        "default_source_system": "Phone camera roll / Google Photos / iCloud",
    },
    {
        "name": "Browser History",
        "category": "browser_history",
        "default_description": (
            "Please export your browser history for the specified date range "
            "from all browsers you use."
        ),
        "default_format_instructions": (
            "Export as HTML or JSON from your browser settings. "
            "Chrome: chrome://history, then use a history export extension. "
            "Firefox: Library > History > Show All History > Export."
        ),
        "default_preservation_note": (
            "Do not clear your browsing history, cache, or cookies. "
            "Do not use private/incognito mode for related activities."
        ),
        "default_source_system": "Chrome / Firefox / Safari",
    },
]


async def _seed_default_request_templates(
    firm_id: UUID, db: AsyncSession
) -> None:
    """Create the 6 default request templates for a newly created firm."""
    for tmpl_data in DEFAULT_REQUEST_TEMPLATES:
        template = RequestTemplate(firm_id=firm_id, **tmpl_data)
        db.add(template)
    await db.commit()
