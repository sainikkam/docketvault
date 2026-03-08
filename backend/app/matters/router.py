from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import get_current_user
from app.database import get_db
from app.matters.models import (
    AuditLogResponse,
    InvitationCreateRequest,
    InvitationResponse,
    MatterCreateRequest,
    MatterResponse,
    MemberResponse,
)
from app.matters.service import (
    accept_invitation,
    create_invitation,
    create_matter,
    get_matter,
    list_audit_log,
    list_members,
    list_user_matters,
    require_matter_member,
)

router = APIRouter()


@router.post("/matters", response_model=MatterResponse, status_code=201)
async def create_matter_endpoint(
    req: MatterCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_matter(req, user, db)


@router.get("/matters", response_model=list[MatterResponse])
async def list_matters_endpoint(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_user_matters(user, db)


@router.get("/matters/{matter_id}", response_model=MatterResponse)
async def get_matter_endpoint(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_member(matter_id, user, db)
    return await get_matter(matter_id, db)


@router.post(
    "/matters/{matter_id}/invitations",
    response_model=InvitationResponse,
    status_code=201,
)
async def create_invitation_endpoint(
    matter_id: UUID,
    req: InvitationCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_invitation(matter_id, req, user, db)


@router.post(
    "/invitations/{token}/accept",
    response_model=MemberResponse,
)
async def accept_invitation_endpoint(
    token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await accept_invitation(token, user, db)


@router.get("/matters/{matter_id}/members", response_model=list[MemberResponse])
async def list_members_endpoint(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_member(matter_id, user, db)
    return await list_members(matter_id, db)


@router.get("/matters/{matter_id}/audit-log", response_model=list[AuditLogResponse])
async def list_audit_log_endpoint(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    await require_matter_member(matter_id, user, db)
    return await list_audit_log(matter_id, db, limit, offset)
