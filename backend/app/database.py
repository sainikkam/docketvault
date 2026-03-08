from sqlmodel import SQLModel
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config import Settings

settings = Settings()
engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine for Celery workers (replace asyncpg with psycopg2)
_sync_url = (
    settings.DATABASE_URL.replace("+asyncpg", "").replace(
        "postgresql://", "postgresql+psycopg2://"
    )
    if "+asyncpg" in settings.DATABASE_URL
    else settings.DATABASE_URL
)
sync_engine = create_sync_engine(_sync_url, echo=False)


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
