from __future__ import annotations

from pathlib import Path
from typing import Iterable

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncEngine

from logistics_bot.config.settings import BASE_DIR


def _load_statements(sql_path: Path) -> Iterable[str]:
    raw = sql_path.read_text(encoding="utf-8")
    for chunk in raw.split(";"):
        statement = chunk.strip()
        if statement:
            yield statement


async def run_sql_file(sql_path: Path, *, engine: AsyncEngine) -> None:
    if not sql_path.exists():
        logger.warning(f'SQL file not found: {sql_path}')
        return
    logger.info(f'Applying SQL file {sql_path}')
    async with engine.begin() as connection:
        for statement in _load_statements(sql_path):
            await connection.exec_driver_sql(statement)


async def run_all_migrations(*, engine: AsyncEngine) -> None:
    assets_dir = BASE_DIR / 'assets'
    if not assets_dir.exists():
        assets_dir = BASE_DIR.parent / 'assets'

    base_schema = assets_dir / 'schema.sql'
    await run_sql_file(base_schema, engine=engine)

    migrations_dir = assets_dir / 'migrations'
    if not migrations_dir.exists():
        logger.info(f'Migrations directory {migrations_dir} is missing; skipping')
        return

    for sql_file in sorted(migrations_dir.glob('*.sql')):
        await run_sql_file(sql_file, engine=engine)
