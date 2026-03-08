from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/docketvault"
    )

    # Storage
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_DIR: str = "./storage"
    S3_ENDPOINT: str = ""
    S3_BUCKET: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""

    # Auth
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    TOTP_ISSUER: str = "DocketVault"

    # LLM
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-sonnet-4-6"

    # Google OAuth (needed in Chunk 4)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # Celery/Redis (not needed until Chunk 6)
    REDIS_URL: str = "redis://localhost:6379/0"

    # ClamAV — deferred from MVP (no malware scanning)
    CLAMAV_HOST: str = "localhost"
    CLAMAV_PORT: int = 3310

    model_config = SettingsConfigDict(env_file=".env")
