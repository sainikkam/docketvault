import io
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.oauth.models import ConnectedAccount

settings = Settings()


class GoogleOAuthService:
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI

    def _client_config(self):
        return {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

    def get_authorize_url(self, scopes: list[str], state: str) -> str:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            self._client_config(),
            scopes=scopes,
            redirect_uri=self.redirect_uri,
        )
        url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=state,
            prompt="consent",
        )
        return url

    def exchange_code(self, code: str) -> dict:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            self._client_config(),
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
            redirect_uri=self.redirect_uri,
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        if creds.expiry:
            expires_at = creds.expiry
        else:
            expires_at = datetime.utcnow() + timedelta(hours=1)
        return {
            "access_token": creds.token,
            "refresh_token": creds.refresh_token or "",
            "expires_at": expires_at,
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
