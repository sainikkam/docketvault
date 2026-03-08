from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import get_current_user
from app.database import get_db
from app.exports.service import generate_evidence_pack
from app.matters.service import log_action, require_matter_role

router = APIRouter()


@router.post("/matters/{matter_id}/export")
async def export_evidence_pack(
    matter_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate and download Evidence Pack ZIP (approved artifacts only)."""
    await require_matter_role(matter_id, ["attorney", "paralegal"], user, db)

    zip_bytes = await generate_evidence_pack(db, matter_id, user.id)

    await log_action(
        db,
        user_id=user.id,
        action="evidence_pack_exported",
        matter_id=matter_id,
    )

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"evidence_pack_{matter_id}_{timestamp}.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
