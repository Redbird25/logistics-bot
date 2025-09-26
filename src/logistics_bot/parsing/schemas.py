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
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

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
        }
