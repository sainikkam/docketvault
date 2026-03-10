import io
import os
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.oauth.models import ConnectedAccount

settings = Settings()

# Allow HTTP redirect URIs for local development (Google's oauthlib
# rejects non-HTTPS redirect URIs without this flag).
if settings.GOOGLE_REDIRECT_URI.startswith("http://localhost"):
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


class GoogleOAuthService:
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI

    # Google OAuth endpoints
    _AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
    _TOKEN_URL = "https://oauth2.googleapis.com/token"

    def get_authorize_url(self, scopes: list[str], state: str) -> str:
        """Build the Google OAuth consent URL directly (no PKCE).

        We avoid google_auth_oauthlib.Flow here because it
        auto-generates a PKCE code_verifier that we'd need to
        persist across requests. Since we're a confidential client
        (we have a client_secret), PKCE is optional.
        """
        from urllib.parse import urlencode

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "state": state,
            "prompt": "consent",
        }
        return f"{self._AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> dict:
        """Exchange the authorization code for tokens via direct HTTP POST.

        This avoids the Flow class's PKCE requirement entirely.
        """
        import httpx

        resp = httpx.post(
            self._TOKEN_URL,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        expires_in = data.get("expires_in", 3600)
        return {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "expires_at": datetime.utcnow() + timedelta(seconds=expires_in),
        }

    async def ensure_fresh_token(self, account: ConnectedAccount, db: AsyncSession):
        if account.token_expires_at > datetime.utcnow():
            return
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=account.access_token,
            refresh_token=account.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        from google.auth.transport.requests import Request

        creds.refresh(Request())
        account.access_token = creds.token
        account.token_expires_at = datetime.utcnow() + timedelta(hours=1)
        db.add(account)
        await db.commit()

    def list_drive_files(self, access_token: str, max_results: int = 50) -> list[dict]:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(token=access_token)
        service = build("drive", "v3", credentials=creds)
        results = (
            service.files()
            .list(
                pageSize=max_results,
                fields="files(id,name,mimeType,modifiedTime,size)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        return results.get("files", [])

    def download_file(self, access_token: str, file_id: str) -> tuple[bytes, dict]:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload

        creds = Credentials(token=access_token)
        service = build("drive", "v3", credentials=creds)
        meta = (
            service.files()
            .get(fileId=file_id, fields="id,name,mimeType,modifiedTime,size")
            .execute()
        )
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue(), meta

    def revoke_token(self, access_token: str):
        import httpx

        try:
            httpx.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": access_token},
                timeout=5,
            )
        except Exception:
            pass  # best-effort
