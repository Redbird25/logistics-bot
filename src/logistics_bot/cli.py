from __future__ import annotations

import argparse
import asyncio
from loguru import logger

from logistics_bot.api.main import run as run_api
from logistics_bot.bot.runner import run_bot
from logistics_bot.config.settings import get_settings
from logistics_bot.cron.cleanup import cleanup_once, run_cleanup_loop
from logistics_bot.parsing.parser import MessageParser
from logistics_bot.services.dedup_service import build_dedup_service
from logistics_bot.services.message_pipeline import MessagePipeline
from logistics_bot.agents.collector import run_collector
from logistics_bot.db.session import init_db, engine
from logistics_bot.db.migrations import run_all_migrations


async def _run_collector() -> None:
    settings = get_settings()
    await init_db()
    parser = MessageParser()
    dedup = await build_dedup_service(
        settings.redis_url,
        ttl_seconds=settings.retention_days * 24 * 3600,
        similarity_threshold=settings.similarity_threshold,
    )
    pipeline = MessagePipeline(parser, dedup)
    try:
        await run_collector(pipeline)
    finally:
        await dedup.close()


async def _run_bot() -> None:
    await init_db()
    await run_bot()


async def _cleanup_loop() -> None:
    await init_db()
    await run_cleanup_loop()


async def _cleanup_once() -> None:
    await init_db()
    await cleanup_once()


async def _run_migrations() -> None:
    await run_all_migrations(engine=engine)


def main() -> None:
    parser = argparse.ArgumentParser(description="Logistics bot control CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("collector", help="Run the collector agent")
    subparsers.add_parser("bot", help="Run the Telegram bot agent")
    subparsers.add_parser("api", help="Run the FastAPI service")
    subparsers.add_parser("cleanup", help="Run retention cleanup once")
    subparsers.add_parser("cleanup-loop", help="Run retention cleanup loop")
    subparsers.add_parser("migrate", help="Apply database schema and migrations")

    args = parser.parse_args()

    if args.command == "collector":
        asyncio.run(_run_collector())
    elif args.command == "bot":
        asyncio.run(_run_bot())
    elif args.command == "api":
        run_api()
    elif args.command == "cleanup":
        asyncio.run(_cleanup_once())
    elif args.command == "cleanup-loop":
        asyncio.run(_cleanup_loop())
    elif args.command == "migrate":
        asyncio.run(_run_migrations())
    else:
        logger.error("Unsupported command %s", args.command)


if __name__ == "__main__":
    main()
