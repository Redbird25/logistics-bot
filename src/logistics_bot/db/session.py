from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from logistics_bot.config.settings import get_settings
from logistics_bot.db.migrations import run_all_migrations

_settings = get_settings()

engine = create_async_engine(_settings.postgres_dsn, echo=False, future=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_session() -> AsyncSession:
    session = async_session_factory()
    try:
        yield session
    finally:
        await session.close()


async def init_db() -> None:
    await run_all_migrations(engine=engine)
