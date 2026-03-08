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
    template = MatterTemplate(firm_id=firm_id, name=req.name, checklist=req.checklist)
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


async def list_templates(firm_id: UUID, db: AsyncSession) -> list[MatterTemplate]:
    result = await db.execute(
        select(MatterTemplate).where(MatterTemplate.firm_id == firm_id)
    )
    return list(result.scalars().all())
