# Telegram Logistics Aggregator

This repository implements the MVP defined in `AGENTS.md`: it listens to cargo groups in Telegram, parses and deduplicates offers, stores structured records in Postgres, and exposes both an HTTP API and a Telegram bot for human queries.

## Stack Overview
- **Collector agent** (Telethon) streams group messages and feeds the message pipeline.
- **Parser & Dedup pipeline** applies rule/regex extraction and Redis-backed duplicate detection before persisting to Postgres.
- **API** (FastAPI) exposes `/search`, `/stats`, and admin chat management endpoints.
- **Bot** (aiogram) wraps the search flow for operators inside Telegram.
- **Cron** job maintains 3-day retention and runs `VACUUM ANALYZE`.

### Parser Breakdown
- Stage 0 – normalize text, strip noise, and segment multi-ad messages; results surface in `metadata.multi_listing` and the `segments` collection.
- Stage 1 – extract route pairs via YAML rules plus city-directory fallbacks.
- Stage 2 – capture price (amount, currency, multipliers) ahead of vehicle/contact.
- Stage 3 – resolve vehicle canonical names and prefer the highest-confidence contact.
- Stage 4 – enrich with tonnage, `cargo`, `urgency`, and `valid_until` hints before geo enrichment.

## Local Development
1. Copy `.env.example` to `.env` and fill Telegram + database secrets.
2. Bootstrap tooling: `pwsh ./scripts/bootstrap.ps1 -InstallDev` (venv + dev dependencies).
3. Apply migrations (`python -m logistics_bot.cli migrate` runs `assets/schema.sql` and every `assets/migrations/*.sql`, or run them manually via `psql`).
4. Launch pieces via CLI:
   - `python -m logistics_bot.cli api`
   - `python -m logistics_bot.cli collector`
   - `python -m logistics_bot.cli bot`
   - `python -m logistics_bot.cli cleanup-loop`

Use `make lint`, `make format`, and `make test` for quality gates.

## Docker Compose
`docker compose up --build` builds a single image for all agents and starts Postgres, Redis, API, collector, bot, and cron services. Ensure `.env` is present before starting the stack.


## Web App
- Откройте `http://localhost:8000/web/` после запуска API/бота — статический интерфейс с современной панелью поиска и карточками рейсов.
- Данные подгружаются по REST из `/search`; фильтры (откуда/куда/тип кузова) обновляют результаты без перезагрузки.
- Сборка Docker включает директорию `web`, поэтому `docker compose up --build` автоматически разворачивает интерфейс.

## Testing
`pytest` covers the parser and deduplication heuristics. Extend tests alongside new modules under `tests/` to guard agent behaviour.

