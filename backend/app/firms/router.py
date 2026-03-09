from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import get_current_user
from app.database import get_db
from app.firms.models import (
    FirmCreateRequest,
    FirmResponse,
    FirmUpdateRequest,
    RequestTemplateCreateRequest,
    RequestTemplateResponse,
    TemplateCreateRequest,
    TemplateResponse,
)
from app.firms.service import (
    create_firm,
    create_request_template,
    create_template,
    get_firm,
    list_request_templates,
    list_templates,
    update_firm,
)
from app.matters.service import log_action

router = APIRouter()


@router.get("/firms", response_model=list[FirmResponse])
async def list_firms_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all firms the current user created."""
    from app.firms.models import Firm
    from sqlmodel import select

    result = await db.execute(select(Firm).where(Firm.created_by == user.id))
    return list(result.scalars().all())


@router.post("/firms", response_model=FirmResponse, status_code=201)
async def create_firm_endpoint(
    req: FirmCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    firm = await create_firm(req, user, db)
    await log_action(db, user.id, "firm.created", "firm", firm.id)
    return firm


@router.get("/firms/{firm_id}", response_model=FirmResponse)
async def get_firm_endpoint(
    firm_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_firm(firm_id, db)


@router.patch("/firms/{firm_id}", response_model=FirmResponse)
async def update_firm_endpoint(
    firm_id: UUID,
    req: FirmUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    firm = await update_firm(firm_id, req, user, db)
    await log_action(db, user.id, "firm.updated", "firm", firm.id)
    return firm


@router.post(
    "/firms/{firm_id}/templates",
    response_model=TemplateResponse,
    status_code=201,
)
async def create_template_endpoint(
    firm_id: UUID,
    req: TemplateCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    template = await create_template(firm_id, req, user, db)
    await log_action(db, user.id, "template.created", "template", template.id)
    return template


@router.get("/firms/{firm_id}/templates", response_model=list[TemplateResponse])
async def list_templates_endpoint(
    firm_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_templates(firm_id, db)

# --- Request template endpoints ---


@router.post(
    "/firms/{firm_id}/request-templates",
    response_model=RequestTemplateResponse,
    status_code=201,
)
async def create_request_template_endpoint(
    firm_id: UUID,
    req: RequestTemplateCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a reusable document request template for this firm."""
    template = await create_request_template(firm_id, req, user, db)
    await log_action(
        db, user.id, "request_template.created", "request_template", template.id
    )
    return template


@router.get(
    "/firms/{firm_id}/request-templates",
    response_model=list[RequestTemplateResponse],
)
async def list_request_templates_endpoint(
    firm_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all request templates for this firm."""
    return await list_request_templates(firm_id, db)
