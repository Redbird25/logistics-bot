from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ParsedMessage:
    chat_id: int
    message_id: int
    posted_at: dt.datetime
    raw_text: str
    route_from: str | None = None
    route_to: str | None = None
    vehicle_type: str | None = None
    tonnage_tons: float | None = None
    price_amount: float | None = None
    price_currency: str | None = None
    contact: str | None = None
    cargo: str | None = None
    urgency: str | None = None
    valid_until: dt.datetime | None = None
    tags: list[str] = field(default_factory=list)
    segments: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    route_from_city_id: str | None = None
    route_from_city_name: str | None = None
    route_from_country: str | None = None
    route_from_region: str | None = None
    route_to_city_id: str | None = None
    route_to_city_name: str | None = None
    route_to_country: str | None = None
    route_to_region: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "chat_id": self.chat_id,
            "message_id": self.message_id,
            "posted_at": self.posted_at,
            "raw_text": self.raw_text,
            "route_from": self.route_from,
            "route_to": self.route_to,
            "vehicle_type": self.vehicle_type,
            "tonnage_tons": self.tonnage_tons,
            "price_amount": self.price_amount,
            "price_currency": self.price_currency,
            "contact": self.contact,
            "tags": self.tags,
            "metadata": self.metadata,
            "route_from_city_id": self.route_from_city_id,
            "route_from_city_name": self.route_from_city_name,
            "route_from_country": self.route_from_country,
            "route_from_region": self.route_from_region,
            "route_to_city_id": self.route_to_city_id,
            "route_to_city_name": self.route_to_city_name,
            "route_to_country": self.route_to_country,
            "route_to_region": self.route_to_region,
        }


