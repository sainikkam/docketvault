from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.models import User
from app.auth.service import get_current_user
from app.database import get_db
from app.notifications.models import Notification, NotificationResponse

router = APIRouter()


@router.get("/notifications", response_model=dict)
async def list_notifications(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's notifications, newest first."""
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at == None)  # noqa: E711
    stmt = stmt.order_by(Notification.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    notifications = list(result.scalars().all())

    # Unread count
    count_result = await db.execute(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.read_at == None,  # noqa: E711
        )
    )
    unread_count = len(list(count_result.scalars().all()))

    return {
        "notifications": [
            {
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "matter_id": str(n.matter_id) if n.matter_id else None,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
        "unread_count": unread_count,
        "total_returned": len(notifications),
    }


@router.patch("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    notif = result.scalars().first()
    if not notif:
        raise HTTPException(404, "Notification not found")
    notif.read_at = datetime.utcnow()
    db.add(notif)
    await db.commit()
    return {"status": "read"}


@router.post("/notifications/read-all")
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.read_at == None,  # noqa: E711
        )
    )
    unread = list(result.scalars().all())
    now = datetime.utcnow()
    for notif in unread:
        notif.read_at = now
        db.add(notif)
    await db.commit()
    return {"marked_read": len(unread)}
