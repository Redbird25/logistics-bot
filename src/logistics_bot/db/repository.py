from __future__ import annotations

import datetime as dt
import uuid
from typing import Iterable, Sequence

from sqlalchemy import Select, delete, func, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from logistics_bot.db import models


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_hash(self, hash_digest: str) -> models.Message | None:
        stmt = select(models.Message).where(models.Message.hash_digest == hash_digest)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def recent_messages(self, limit: int = 50) -> Sequence[models.Message]:
        stmt = (
            select(models.Message)
            .where(models.Message.duplicate_of_id.is_(None))
            .order_by(models.Message.posted_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def insert_message(self, message: models.Message) -> models.Message:
        self.session.add(message)
        await self.session.flush()
        return message

    async def mark_duplicate(self, message_id: uuid.UUID, original_id: uuid.UUID) -> None:
        stmt = select(models.Message).where(models.Message.id == message_id)
        result = await self.session.execute(stmt)
        entity = result.scalar_one()
        entity.mark_duplicate(original_id)
        await self.session.flush()

    async def search_messages(
        self,
        *,
        origin: str | None = None,
        destination: str | None = None,
        origin_city_id: str | None = None,
        destination_city_id: str | None = None,
        vehicle_type: str | None = None,
        limit: int = 20,
    ) -> Sequence[models.Message]:
        stmt: Select[tuple[models.Message]] = select(models.Message).where(
            models.Message.duplicate_of_id.is_(None)
        )
        if origin_city_id:
            stmt = stmt.where(models.Message.route_from_city_id == origin_city_id)
        if destination_city_id:
            stmt = stmt.where(models.Message.route_to_city_id == destination_city_id)
        if origin:
            stmt = stmt.where(models.Message.route_from.ilike(f"%{origin}%"))
        if destination:
            stmt = stmt.where(models.Message.route_to.ilike(f"%{destination}%"))
        if vehicle_type:
            stmt = stmt.where(models.Message.vehicle_type.ilike(f"%{vehicle_type}%"))
        stmt = stmt.order_by(models.Message.posted_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def stats_by_route(self, limit: int = 10) -> Sequence[tuple[str | None, str | None, int]]:
        stmt = (
            select(
                models.Message.route_from,
                models.Message.route_to,
                func.count(models.Message.id).label("total"),
            )
            .where(models.Message.duplicate_of_id.is_(None))
            .group_by(models.Message.route_from, models.Message.route_to)
            .order_by(func.count(models.Message.id).desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.all()

    async def delete_older_than(self, *, days: int) -> int:
        cutoff = dt.datetime.utcnow() - dt.timedelta(days=days)
        stmt = delete(models.Message).where(models.Message.posted_at < cutoff)
        result = await self.session.execute(stmt)
        return result.rowcount or 0


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_chat(self, telegram_id: int, title: str) -> models.Chat:
        stmt = select(models.Chat).where(models.Chat.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        chat = result.scalar_one_or_none()
        if chat:
            chat.title = title
        else:
            chat = models.Chat(telegram_id=telegram_id, title=title)
            self.session.add(chat)
        await self.session.flush()
        return chat

    async def list_active(self) -> Iterable[models.Chat]:
        stmt = (
            select(models.Chat)
            .where(models.Chat.is_active.is_(True))
            .order_by(models.Chat.added_at)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def set_active(self, telegram_id: int, is_active: bool) -> None:
        stmt = select(models.Chat).where(models.Chat.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        chat = result.scalar_one_or_none()
        if not chat:
            raise NoResultFound(f"Chat {telegram_id} not found")
        chat.is_active = is_active
        await self.session.flush()
