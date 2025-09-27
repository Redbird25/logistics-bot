from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel


class MessageOut(BaseModel):
    id: str
    chat_id: str
    message_id: int
    posted_at: dt.datetime
    route_from: str | None
    route_to: str | None
    route_from_city_id: str | None
    route_from_city_name: str | None
    route_from_country: str | None
    route_from_region: str | None
    route_to_city_id: str | None
    route_to_city_name: str | None
    route_to_country: str | None
    route_to_region: str | None
    vehicle_type: str | None
    tonnage_tons: float | None
    price_amount: float | None
    price_currency: str | None
    contact: str | None
    tags: list[str]
    metadata: dict[str, Any]
    raw_text: str


class RouteStat(BaseModel):
    origin: str | None
    destination: str | None
    total: int


class ChatOut(BaseModel):
    telegram_id: int
    title: str
    is_active: bool
    added_at: dt.datetime


class ChatCreate(BaseModel):
    telegram_id: int
    title: str


class ChatStatus(BaseModel):
    is_active: bool
