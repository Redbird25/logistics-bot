from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Index, Integer, BigInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_chat_posted", "chat_id", "posted_at"),
        Index("ix_messages_hash_digest", "hash_digest", unique=True),
        Index("ix_messages_route_city", "route_from_city_id", "route_to_city_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id: Mapped[str] = mapped_column(String(128), index=True)
    message_id: Mapped[int] = mapped_column(Integer)
    posted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    raw_text: Mapped[str] = mapped_column(Text)
    route_from: Mapped[str | None] = mapped_column(String(128))
    route_to: Mapped[str | None] = mapped_column(String(128))
    route_from_city_id: Mapped[str | None] = mapped_column(String(64))
    route_from_city_name: Mapped[str | None] = mapped_column(String(128))
    route_from_country: Mapped[str | None] = mapped_column(String(4))
    route_from_region: Mapped[str | None] = mapped_column(String(128))
    route_to_city_id: Mapped[str | None] = mapped_column(String(64))
    route_to_city_name: Mapped[str | None] = mapped_column(String(128))
    route_to_country: Mapped[str | None] = mapped_column(String(4))
    route_to_region: Mapped[str | None] = mapped_column(String(128))
    vehicle_type: Mapped[str | None] = mapped_column(String(64))
    tonnage_tons: Mapped[float | None] = mapped_column(Float)
    price_amount: Mapped[float | None] = mapped_column(Float)
    price_currency: Mapped[str | None] = mapped_column(String(16))
    contact: Mapped[str | None] = mapped_column(String(256))
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hash_digest: Mapped[str] = mapped_column(String(64))
    duplicate_of_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
    )

    def mark_duplicate(self, duplicate_of_id: uuid.UUID) -> None:
        self.duplicate_of_id = duplicate_of_id


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(default=True)
    added_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
