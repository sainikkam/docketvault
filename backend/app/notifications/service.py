from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.matters.models import MatterMember
from app.notifications.models import Notification


async def notify(
    db: AsyncSession,
    user_id: UUID,
    type: str,
    title: str,
    body: str = "",
    matter_id: Optional[UUID] = None,
    metadata: Optional[dict] = None,
):
    """Create an in-app notification."""
    notif = Notification(
        user_id=user_id,
        matter_id=matter_id,
        type=type,
        title=title,
        body=body,
        metadata_=metadata or {},
    )
    db.add(notif)
    await db.flush()


async def get_matter_attorneys(db: AsyncSession, matter_id: UUID) -> list[UUID]:
    """Get user IDs for attorneys/paralegals on a matter."""
    result = await db.execute(
        select(MatterMember).where(
            MatterMember.matter_id == matter_id,
            MatterMember.role.in_(["attorney", "paralegal"]),
        )
    )
    return [m.user_id for m in result.scalars().all()]


async def get_matter_clients(db: AsyncSession, matter_id: UUID) -> list[UUID]:
    """Get user IDs for clients on a matter."""
    result = await db.execute(
        select(MatterMember).where(
            MatterMember.matter_id == matter_id,
            MatterMember.role.in_(["primary_client", "contributor_client"]),
        )
    )
    return [m.user_id for m in result.scalars().all()]
