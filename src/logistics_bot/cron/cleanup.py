from __future__ import annotations

import asyncio
from loguru import logger
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

try:
    from asyncpg import UndefinedTableError
except ImportError:  # pragma: no cover - asyncpg always available in runtime image
    UndefinedTableError = type("UndefinedTableError", (), {})

from logistics_bot.config.settings import get_settings
from logistics_bot.db.repository import MessageRepository
from logistics_bot.db.session import engine, get_session

CLEAN_INTERVAL_SECONDS = 900


async def cleanup_once() -> None:
    settings = get_settings()
    async with get_session() as session:
        repo = MessageRepository(session)
        try:
            deleted = await repo.delete_older_than(days=settings.retention_days)
            await session.commit()
        except ProgrammingError as exc:
            if isinstance(exc.orig, UndefinedTableError):
                logger.warning("Cleanup skipped: messages table missing (yet)")
                await session.rollback()
                return
            raise

    async with engine.connect() as conn:
        try:
            await conn.run_sync(
                lambda sync_conn: sync_conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                    text("VACUUM ANALYZE messages")
                )
            )
        except ProgrammingError as exc:
            if isinstance(exc.orig, UndefinedTableError):
                logger.warning("VACUUM skipped: messages table missing (yet)")
            else:
                raise
    logger.info("Cleanup complete. Deleted %s records", deleted)


async def run_cleanup_loop() -> None:
    logger.info("Cron cleanup loop started")
    while True:
        await cleanup_once()
        await asyncio.sleep(CLEAN_INTERVAL_SECONDS)
