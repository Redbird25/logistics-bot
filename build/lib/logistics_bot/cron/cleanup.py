from __future__ import annotations

import asyncio
from loguru import logger
from sqlalchemy import text

from logistics_bot.config.settings import get_settings
from logistics_bot.db.repository import MessageRepository
from logistics_bot.db.session import get_session

CLEAN_INTERVAL_SECONDS = 900


async def cleanup_once() -> None:
    settings = get_settings()
    async with get_session() as session:
        repo = MessageRepository(session)
        deleted = await repo.delete_older_than(days=settings.retention_days)
        await session.execute(text("VACUUM ANALYZE messages"))
        await session.commit()
    logger.info("Cleanup complete. Deleted %s records", deleted)


async def run_cleanup_loop() -> None:
    logger.info("Cron cleanup loop started")
    while True:
        await cleanup_once()
        await asyncio.sleep(CLEAN_INTERVAL_SECONDS)
