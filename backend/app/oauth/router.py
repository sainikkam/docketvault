import hashlib
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.auth.models import User
from app.auth.service import get_current_user
from app.config import Settings
from app.database import get_db
from app.evidence.models import Artifact
from app.evidence.service import enforce_hash_and_check_dedup
from app.matters.service import log_action, require_matter_role
from app.oauth.models import ConnectedAccount, DriveImportRequest
from app.oauth.service import GoogleOAuthService
from app.storage import get_storage

router = APIRouter()
settings = Settings()

EXTRACTABLE_MIMES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


def _dispatch_extraction_tasks(artifacts):
    try:
        from app.extraction.tasks import extract_image_pdf

        for a in artifacts:
            if a.mime_type in EXTRACTABLE_MIMES and a.status == "processing":
                extract_image_pdf.delay(str(a.id))
    except Exception:
        pass


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


async def _get_account(user_id: UUID, db: AsyncSession) -> ConnectedAccount:
    result = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.provider == "google",
        )
    )
    account = result.scalars().first()
    if not account:
        raise HTTPException(
            404, "No Google account connected. Use /oauth/google/authorize first."
        )
    return account


@router.get("/oauth/google/authorize")
async def authorize(user: User = Depends(get_current_user)):
    svc = GoogleOAuthService()
    url = svc.get_authorize_url(scopes=SCOPES, state=str(user.id))
    return {"authorize_url": url}


@router.get("/oauth/google/callback")
async def callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    svc = GoogleOAuthService()
    tokens = svc.exchange_code(code)
    user_id = UUID(state)

    # Upsert: delete old connection if exists
    result = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == user_id,
            ConnectedAccount.provider == "google",
        )
    )
    old = result.scalars().first()
    if old:
        await db.delete(old)

    account = ConnectedAccount(
        user_id=user_id,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_expires_at=tokens["expires_at"],
    )
    db.add(account)
    await log_action(db, user_id, "google.connected")
    await db.commit()
    return {"status": "connected"}


@router.delete("/oauth/google/disconnect")
async def disconnect(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_account(user.id, db)
    svc = GoogleOAuthService()
    svc.revoke_token(account.access_token)
    await db.delete(account)
    await log_action(db, user.id, "google.disconnected")
    await db.commit()
    return {"status": "disconnected"}


@router.get("/oauth/google/drive/files")
async def list_drive_files(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    account = await _get_account(user.id, db)
    svc = GoogleOAuthService()
    await svc.ensure_fresh_token(account, db)
    files = svc.list_drive_files(account.access_token)
    return {"files": files}


@router.post("/matters/{matter_id}/import/drive")
async def import_from_drive(
    matter_id: UUID,
    body: DriveImportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await require_matter_role(
        matter_id, ["primary_client", "contributor_client"], user, db
    )
    account = await _get_account(user.id, db)
    svc = GoogleOAuthService()
    await svc.ensure_fresh_token(account, db)
    storage = get_storage(settings)
    created = []

    for file_id in body.file_ids:
        file_bytes, meta = svc.download_file(account.access_token, file_id)
        artifact_id = uuid4()
        filename = meta.get("name", "unknown")
        key = f"{matter_id}/{artifact_id}/{filename}"
        storage_uri = await storage.upload(key, file_bytes)

        artifact = Artifact(
            id=artifact_id,
            matter_id=matter_id,
            owner_user_id=user.id,
            original_filename=filename,
            mime_type=meta.get("mimeType", "application/octet-stream"),
            file_size_bytes=len(file_bytes),
            storage_uri=storage_uri,
            source_system="drive",
            source_id=meta.get("id"),
            sha256=hashlib.sha256(file_bytes).hexdigest(),
            original_timestamps={"modifiedTime": meta.get("modifiedTime")},
            status="processing",
        )
        db.add(artifact)

        dedup = await enforce_hash_and_check_dedup(db, artifact, file_bytes, matter_id)
        if dedup["is_duplicate"]:
            await log_action(
                db,
                user.id,
                "duplicate_detected",
                target_type="artifact",
                target_id=artifact.id,
                matter_id=matter_id,
                metadata={
                    "artifact_id": str(artifact.id),
                    "duplicate_of": str(dedup["duplicate_of"]),
                },
            )

        created.append(artifact)

    await db.commit()

    # Dispatch extraction tasks for extractable artifacts
    _dispatch_extraction_tasks(created)

    await log_action(
        db,
        user.id,
        "drive.import",
        matter_id=matter_id,
        metadata={
            "file_ids": body.file_ids,
            "artifacts_created": [str(a.id) for a in created],
        },
    )
    return {"imported": len(created), "artifact_ids": [str(a.id) for a in created]}
