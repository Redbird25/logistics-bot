# AGENTS.md — Telegram Logistics Aggregator (MVP)

**Goal:** Build an MVP Telegram system that reads messages from selected groups (100–150 to start, scalable to 300), stores 3 days of data, removes duplicates, parses key fields (route, vehicle type, tonnage, price, contacts), and lets users query via a bot and receive results with a button linking to the original post.

> Budget/time guardrails: $500, 1 month, no paid AI. Use rules/regex + similarity search. Single VPS, Docker Compose.

---

## 1) Agent Responsibilities

### Collector Agent

* Connect to Telegram groups (via bot or user-client).
* Stream new messages, normalize text, filter duplicates.
* Forward to Parser Agent.

### Parser Agent

* Apply regex/rule-based extraction for key fields.
* Support RU/UZ mixed messages.
* Normalize and enrich data before DB insert.

### Dedup Agent

* Maintain Redis cache for exact duplicates (TTL = 3 days).
* Query Postgres (pg_trgm) for near-duplicates.
* Tag messages with `is_duplicate_of` if needed.

### DB Agent

* Store normalized and parsed messages.
* Apply retention (delete >3 days old).
* Expose structured data for queries.

### API Agent

* Handle `/search`, `/stats`, `/admin` endpoints.
* Orchestrate DB queries + filters.
* Provide JSON for Bot Agent.

### Bot Agent

* Handle Telegram commands (`/start`, `/find`, `/add_chat`, etc.).
* Send search results to users with inline button linking to original.
* Rate limit users.

### Cron Agent

* Run cleanup job every 15 minutes.
* Delete old data (older than 3 days).
* Run `VACUUM ANALYZE`.

---

## 2) Agent-to-Agent Interactions

* **Collector → Parser → DB**: main ingestion flow.
* **Parser ↔ Dedup**: consult Redis and Postgres before insert.
* **Bot → API → DB**: query flow.
* **Admin → Bot → API**: manage chats, retention, stats.
* **Cron → DB**: enforce rolling retention.

---

## 3) Agent Configurations

All agents share a single `.env` file:

```
TG_BOT_TOKEN=...
TG_API_ID=...
TG_API_HASH=...
TG_SESSION_STRING=...  # only if using Telethon

POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=logi
POSTGRES_USER=logi
POSTGRES_PASSWORD=logi

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

RETENTION_DAYS=3
MAX_RESULTS_PER_QUERY=20
SIMILARITY_THRESHOLD=0.85
```

---

## 4) Agent Implementation Notes

* **Collector Agent:** resilient to Telegram rate limits, reconnects on error.
* **Parser Agent:** rule sets stored in `rules/*.yaml` for hot reload.
* **Dedup Agent:** exact dedup via SHA1 + Redis; near-dedup via `pg_trgm` similarity.
* **DB Agent:** indexes on parsed fields; JSONB for flexible structure.
* **API Agent:** must sanitize user input, prevent SQL injection.
* **Bot Agent:** polite error messages, respect Telegram limits.
* **Cron Agent:** simple loop + SQL DELETE + sleep.

---

## 5) Agent Lifecycle & Scaling

* Start all agents via Docker Compose.
* Collector can be scaled to multiple workers if groups >150.
* Parser and Dedup are lightweight; can run within collector worker.
* API and Bot scale separately if traffic grows.
* DB scales vertically (2–4 GB RAM enough for MVP).
* Redis single instance (no clustering for MVP).

---

## 6) Acceptance for Agents

* Collector inserts real messages into DB.
* Parser fills JSON fields correctly on 10–20 examples.
* Dedup filters exact and near-duplicates.
* API returns valid JSON results.
* Bot responds to `/find` and inline button works.
* Cron deletes expired messages on schedule.

---

## 7) Future Agents (Beyond MVP)

* **Analytics Agent:** statistics, trends, dashboards.
* **AI Agent:** NLP-based classification once paid AI allowed.
* **Web UI Agent:** web interface for admins instead of commands.
* **Alert Agent:** push notifications when matching new cargo.

---

## 8) Deployment & Operations

* Deploy agents as containers on single VPS.
* Monitor `/healthz` endpoints for API, Collector.
* Backup Postgres daily (keep 3 copies).
* Logs centralized (stdout → Docker logs).
* Security: store tokens only in `.env`, restrict DB user.

---

This AGENTS.md defines clear roles for each agent in the system so Codex CLI (or any orchestrator) can run them with minimal bugs and clear boundaries.
