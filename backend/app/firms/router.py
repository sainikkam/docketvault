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
    TemplateCreateRequest,
    TemplateResponse,
)
from app.firms.service import (
    create_firm,
    create_template,
    get_firm,
    list_templates,
    update_firm,
)
from app.matters.service import log_action

router = APIRouter()


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
