import hashlib
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
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

logger = logging.getLogger(__name__)

router = APIRouter()
settings = Settings()

EXTRACTABLE_MIMES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
AUDIO_MIMES = {"audio/mpeg", "audio/mp4", "audio/wav", "audio/webm", "audio/ogg"}


def _dispatch_extraction_tasks(artifacts):
    try:
        from app.extraction.tasks import extract_audio, extract_image_pdf

        for a in artifacts:
            if a.status != "processing":
                continue
            if a.mime_type in EXTRACTABLE_MIMES:
                extract_image_pdf.delay(str(a.id))
            elif a.mime_type in AUDIO_MIMES:
                extract_audio.delay(str(a.id))
    except Exception:
        pass


SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
]


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


@router.get("/oauth/google/status")
async def google_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lightweight check: is a Google account linked for this user?"""
    result = await db.execute(
        select(ConnectedAccount).where(
            ConnectedAccount.user_id == user.id,
            ConnectedAccount.provider == "google",
        )
    )
    account = result.scalars().first()
    return {"connected": account is not None}


@router.get("/oauth/google/authorize")
async def authorize(user: User = Depends(get_current_user)):
    svc = GoogleOAuthService()
    url = svc.get_authorize_url(scopes=SCOPES, state=str(user.id))
    return {"authorize_url": url}


@router.get("/oauth/google/callback", response_class=HTMLResponse)
async def callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Google redirects here after the user grants consent.

    Returns a friendly HTML page telling the user to go back to DocketVault.
    """
    try:
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

        return _success_page()

    except Exception as exc:
        logger.exception("Google OAuth callback failed")
        return _error_page(str(exc))


def _success_page() -> str:
    """HTML shown after successful Google account connection."""
    return """<!DOCTYPE html>
<html><head><title>Connected – DocketVault</title>
<style>
  body { font-family: system-ui, sans-serif; display: flex;
         justify-content: center; align-items: center;
         min-height: 100vh; margin: 0; background: #F8FAFC; }
  .card { background: #fff; border-radius: 12px; padding: 2.5rem;
          box-shadow: 0 2px 12px rgba(0,0,0,0.08); text-align: center;
          max-width: 420px; }
  .icon { font-size: 3rem; margin-bottom: 0.5rem; }
  h1 { color: #1E3A5F; font-size: 1.4rem; margin: 0.5rem 0; }
  p  { color: #475569; font-size: 0.95rem; line-height: 1.5; }
  a  { display: inline-block; margin-top: 1rem; padding: 0.6rem 1.5rem;
       background: #2563EB; color: #fff; border-radius: 8px;
       text-decoration: none; font-weight: 600; }
  a:hover { background: #1D4ED8; }
</style></head>
<body><div class="card">
  <div class="icon">✅</div>
  <h1>Google Account Connected</h1>
  <p>Your Google Drive and Gmail are now linked to DocketVault.
     You can close this tab and return to the app.</p>
  <a href="http://localhost:8501">Back to DocketVault</a>
</div></body></html>"""


def _error_page(detail: str) -> str:
    """HTML shown when the OAuth callback fails."""
    return f"""<!DOCTYPE html>
<html><head><title>Error – DocketVault</title>
<style>
  body {{ font-family: system-ui, sans-serif; display: flex;
         justify-content: center; align-items: center;
         min-height: 100vh; margin: 0; background: #F8FAFC; }}
  .card {{ background: #fff; border-radius: 12px; padding: 2.5rem;
          box-shadow: 0 2px 12px rgba(0,0,0,0.08); text-align: center;
          max-width: 480px; }}
  .icon {{ font-size: 3rem; margin-bottom: 0.5rem; }}
  h1 {{ color: #991B1B; font-size: 1.4rem; margin: 0.5rem 0; }}
  p  {{ color: #475569; font-size: 0.95rem; line-height: 1.5; }}
  .detail {{ background: #FEF2F2; color: #991B1B; padding: 0.6rem 1rem;
             border-radius: 6px; font-size: 0.8rem; margin-top: 0.8rem;
             word-break: break-word; }}
  a  {{ display: inline-block; margin-top: 1rem; padding: 0.6rem 1.5rem;
       background: #2563EB; color: #fff; border-radius: 8px;
       text-decoration: none; font-weight: 600; }}
</style></head>
<body><div class="card">
  <div class="icon">❌</div>
  <h1>Connection Failed</h1>
  <p>Something went wrong linking your Google account. Please try again
     from the Upload Evidence page.</p>
  <div class="detail">{detail}</div>
  <a href="http://localhost:8501">Back to DocketVault</a>
</div></body></html>"""


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
