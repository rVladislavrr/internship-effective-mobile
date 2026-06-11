import asyncio
from typing import AsyncGenerator

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from src.config import settings
from src.db.connection import get_async_session
from src.models import Base
from src.main import app
from src.redis_conn import redis_client
from src.utils.create_bd import seed_scope_groups, seed_admin

test_engine = create_async_engine(
    settings.DATABASE_URL_TEST,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

TestingAsyncSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingAsyncSessionLocal() as session:
        yield session


@pytest.fixture(scope="function", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingAsyncSessionLocal() as session:
        await seed_scope_groups(session)
        await seed_admin(session)

    await redis_client.connect()

    yield

    app.dependency_overrides.clear()

    await redis_client.close()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingAsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


@pytest.fixture(scope="function")
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_async_session] = override_get_async_session

    async with AsyncClient(
        transport=ASGITransport(app),
        base_url="http://test",
        timeout=30.0,
    ) as ac:
        yield ac

    app.dependency_overrides.clear()

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()