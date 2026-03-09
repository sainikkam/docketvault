import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.auth.models import User  # noqa: F401
from app.firms.models import Firm, MatterTemplate  # noqa: F401
from app.matters.models import Matter, MatterMember, Invitation, AuditLog, EvidenceRequest  # noqa: F401
from app.evidence.models import Record, Artifact  # noqa: F401
from app.oauth.models import ConnectedAccount  # noqa: F401
from app.extraction.models import Extraction  # noqa: F401
from app.enrichment.models import TimelineEvent, MissingItem, IntakeSummary  # noqa: F401
from app.sharing.models import SharePolicy  # noqa: F401
from app.notifications.models import Notification  # noqa: F401
from app.database import get_db
from app.main import app

TEST_DATABASE_URL = "postgresql+asyncpg://phoenix.t@localhost:5432/docketvault_test"


@pytest_asyncio.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
