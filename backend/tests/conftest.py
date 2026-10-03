import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.session as session_module
import app.models  # noqa: F401,F403  -- registers ORM models on Base.metadata
from app.db.base import Base
from app.deps import get_session
from app.main import app
from app.mock_engine import get_engine


@pytest_asyncio.fixture(autouse=True)
async def _reset_mock_engine():
    get_engine()._routes.clear()
    yield
    get_engine()._routes.clear()


@pytest_asyncio.fixture
async def session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    session_module.engine = test_engine
    session_module.AsyncSessionLocal = TestSession
    async with TestSession() as s:
        yield s
    await test_engine.dispose()


@pytest_asyncio.fixture
async def client(session):
    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()