import secrets
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.models import User
from app.matters.models import (
    AuditLog,
    Invitation,
    InvitationCreateRequest,
    Matter,
    MatterCreateRequest,
    MatterMember,
)


async def log_action(
    db: AsyncSession,
    user_id: UUID,
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[UUID] = None,
    matter_id: Optional[UUID] = None,
    metadata: Optional[dict] = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        matter_id=matter_id,
        metadata_=metadata or {},
    )
    db.add(entry)
    await db.flush()


async def require_matter_member(
    matter_id: UUID, user: User, db: AsyncSession
) -> MatterMember:
    result = await db.execute(
        select(MatterMember).where(
            MatterMember.matter_id == matter_id,
            MatterMember.user_id == user.id,
        )
    )
    member = result.scalars().first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this matter",
        )
    return member


async def require_matter_role(
    matter_id: UUID,
    allowed_roles: list[str],
    user: User,
    db: AsyncSession,
) -> MatterMember:
    member = await require_matter_member(matter_id, user, db)
    if member.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{member.role}' not authorized for this action",
        )
    return member


async def create_matter(
    req: MatterCreateRequest, user: User, db: AsyncSession
) -> Matter:
    if user.role not in ("attorney", "paralegal"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only attorneys and paralegals can create matters",
        )
    matter = Matter(
        firm_id=req.firm_id,
        template_id=req.template_id,
        title=req.title,
        created_by=user.id,
    )
    db.add(matter)
    await db.flush()
    # Creator becomes a member
    member = MatterMember(matter_id=matter.id, user_id=user.id, role=user.role)
    db.add(member)
    await log_action(db, user.id, "matter.created", "matter", matter.id, matter.id)
    await db.commit()
    await db.refresh(matter)
    return matter


async def list_user_matters(user: User, db: AsyncSession) -> list[Matter]:
    result = await db.execute(
        select(Matter)
        .join(MatterMember, MatterMember.matter_id == Matter.id)
        .where(MatterMember.user_id == user.id)
    )
    return list(result.scalars().all())


async def get_matter(matter_id: UUID, db: AsyncSession) -> Matter:
    result = await db.execute(select(Matter).where(Matter.id == matter_id))
    matter = result.scalars().first()
    if not matter:
        raise HTTPException(status_code=404, detail="Matter not found")
    return matter


async def create_invitation(
    matter_id: UUID,
    req: InvitationCreateRequest,
    user: User,
    db: AsyncSession,
) -> Invitation:
    await require_matter_role(matter_id, ["attorney", "paralegal"], user, db)
    token = secrets.token_urlsafe(32)
    invite = Invitation(
        matter_id=matter_id,
        token=token,
        role=req.role,
        created_by=user.id,
    )
    db.add(invite)
    await log_action(
        db, user.id, "invitation.created", "invitation", invite.id, matter_id
    )
    await db.commit()
    await db.refresh(invite)
    return invite


async def accept_invitation(token: str, user: User, db: AsyncSession) -> MatterMember:
    result = await db.execute(select(Invitation).where(Invitation.token == token))
    invite = result.scalars().first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invite.accepted_at is not None:
        raise HTTPException(status_code=400, detail="Invitation already used")
    # Check if user is already a member
    existing = await db.execute(
        select(MatterMember).where(
            MatterMember.matter_id == invite.matter_id,
            MatterMember.user_id == user.id,
        )
    )
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Already a member of this matter")
    invite.accepted_at = datetime.utcnow()
    member = MatterMember(matter_id=invite.matter_id, user_id=user.id, role=invite.role)
    db.add(invite)
    db.add(member)
    await log_action(
        db,
        user.id,
        "invitation.accepted",
        "invitation",
        invite.id,
        invite.matter_id,
    )
    await db.commit()
    await db.refresh(member)
    return member


async def list_members(matter_id: UUID, db: AsyncSession) -> list[MatterMember]:
    result = await db.execute(
        select(MatterMember).where(MatterMember.matter_id == matter_id)
    )
    return list(result.scalars().all())


async def list_audit_log(
    matter_id: UUID, db: AsyncSession, limit: int = 50, offset: int = 0
) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.matter_id == matter_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
