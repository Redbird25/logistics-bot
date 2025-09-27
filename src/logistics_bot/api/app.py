from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import re
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from logistics_bot.api.schemas import ChatCreate, ChatOut, ChatStatus, MessageOut, RouteStat
from logistics_bot.db.repository import ChatRepository, MessageRepository
from logistics_bot.db.session import get_session, init_db
from logistics_bot.parsing.cities import CityDirectory
from logistics_bot.parsing.parser import MessageParser

app = FastAPI(title="Logistics Aggregator API")

WEB_DIR = Path(__file__).resolve().parents[3] / "web"
if WEB_DIR.exists():
    app.mount("/web", StaticFiles(directory=WEB_DIR, html=True), name="web")


@app.get("/", include_in_schema=False, response_model=None)
async def root():
    if WEB_DIR.exists():
        return RedirectResponse(url="/web/")
    return {"status": "ok"}

CITY_DIRECTORY = CityDirectory()
VEHICLE_ALIASES = MessageParser.VEHICLE_CANONICAL


def _normalize_vehicle_query(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    key = candidate.lower()
    canonical = VEHICLE_ALIASES.get(key)
    if canonical:
        return canonical
    cleaned = re.sub(r'[^\w\s]', '', key)
    canonical = VEHICLE_ALIASES.get(cleaned)
    if canonical:
        return canonical
    return candidate


    if WEB_DIR.exists():
        return RedirectResponse(url="/web/")
    return {"status": "ok"}


async def db_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    async with get_session() as session:
        yield session


@app.on_event("startup")
async def ensure_database() -> None:
    await init_db()


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search", response_model=list[MessageOut])
async def search_messages(
    origin: str | None = Query(None, max_length=120),
    destination: str | None = Query(None, max_length=120),
    origin_city_id: str | None = Query(None, max_length=64),
    destination_city_id: str | None = Query(None, max_length=64),
    vehicle_type: str | None = Query(None, max_length=80),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_session_dependency),
) -> list[MessageOut]:
    repo = MessageRepository(session)

    resolved_origin = origin.strip() if origin else None
    resolved_origin_city_id = origin_city_id
    if origin:
        origin_record = CITY_DIRECTORY.find(origin)
        if origin_record:
            resolved_origin = origin_record.name
            resolved_origin_city_id = resolved_origin_city_id or origin_record.city_id

    resolved_destination = destination.strip() if destination else None
    resolved_destination_city_id = destination_city_id
    if destination:
        destination_record = CITY_DIRECTORY.find(destination)
        if destination_record:
            resolved_destination = destination_record.name
            resolved_destination_city_id = resolved_destination_city_id or destination_record.city_id

    resolved_vehicle = _normalize_vehicle_query(vehicle_type)

    results = await repo.search_messages(
        origin=resolved_origin,
        destination=resolved_destination,
        origin_city_id=resolved_origin_city_id,
        destination_city_id=resolved_destination_city_id,
        vehicle_type=resolved_vehicle,
        limit=limit,
    )
    return [
        MessageOut(
            id=str(item.id),
            chat_id=item.chat_id,
            message_id=item.message_id,
            posted_at=item.posted_at,
            route_from=item.route_from,
            route_to=item.route_to,
            route_from_city_id=item.route_from_city_id,
            route_from_city_name=item.route_from_city_name,
            route_from_country=item.route_from_country,
            route_from_region=item.route_from_region,
            route_to_city_id=item.route_to_city_id,
            route_to_city_name=item.route_to_city_name,
            route_to_country=item.route_to_country,
            route_to_region=item.route_to_region,
            vehicle_type=item.vehicle_type,
            tonnage_tons=item.tonnage_tons,
            price_amount=item.price_amount,
            price_currency=item.price_currency,
            contact=item.contact,
            tags=item.tags or [],
            metadata=item.extra_metadata or {},
            raw_text=item.raw_text,
        )
        for item in results
    ]


@app.get("/stats", response_model=list[RouteStat])
async def route_stats(
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(db_session_dependency),
) -> list[RouteStat]:
    repo = MessageRepository(session)
    stats = await repo.stats_by_route(limit=limit)
    return [
        RouteStat(origin=row[0], destination=row[1], total=row[2])
        for row in stats
    ]


@app.get("/admin/chats", response_model=list[ChatOut])
async def list_chats(session: AsyncSession = Depends(db_session_dependency)) -> list[ChatOut]:
    repo = ChatRepository(session)
    chats = await repo.list_active()
    return [
        ChatOut(
            telegram_id=chat.telegram_id,
            title=chat.title,
            is_active=chat.is_active,
            added_at=chat.added_at,
        )
        for chat in chats
    ]


@app.post("/admin/chats", response_model=ChatOut)
async def upsert_chat(
    payload: ChatCreate,
    session: AsyncSession = Depends(db_session_dependency),
) -> ChatOut:
    repo = ChatRepository(session)
    chat = await repo.upsert_chat(payload.telegram_id, payload.title)
    await session.commit()
    return ChatOut(
        telegram_id=chat.telegram_id,
        title=chat.title,
        is_active=chat.is_active,
        added_at=chat.added_at,
    )


@app.post("/admin/chats/{telegram_id}/status")
async def update_chat_status(
    telegram_id: int,
    payload: ChatStatus,
    session: AsyncSession = Depends(db_session_dependency),
) -> dict[str, bool]:
    repo = ChatRepository(session)
    try:
        await repo.set_active(telegram_id, payload.is_active)
    except NoResultFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return {"is_active": payload.is_active}


