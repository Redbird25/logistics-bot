from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from logistics_bot.api.schemas import ChatCreate, ChatOut, ChatStatus, MessageOut, RouteStat
from logistics_bot.db.repository import ChatRepository, MessageRepository
from logistics_bot.db.session import get_session

app = FastAPI(title="Logistics Aggregator API")


async def db_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    async with get_session() as session:
        yield session


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search", response_model=list[MessageOut])
async def search_messages(
    origin: str | None = Query(None, max_length=120),
    destination: str | None = Query(None, max_length=120),
    vehicle_type: str | None = Query(None, max_length=80),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(db_session_dependency),
) -> list[MessageOut]:
    repo = MessageRepository(session)
    results = await repo.search_messages(
        origin=origin,
        destination=destination,
        vehicle_type=vehicle_type,
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
            vehicle_type=item.vehicle_type,
            tonnage_tons=item.tonnage_tons,
            price_amount=item.price_amount,
            price_currency=item.price_currency,
            contact=item.contact,
            tags=item.tags or [],
            metadata=item.metadata or {},
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
