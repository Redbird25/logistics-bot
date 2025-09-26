from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

import yaml

from logistics_bot.parsing.schemas import ParsedMessage

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "rules" / "messages.yaml"


class MessageParser:
    def __init__(self, rules_path: Path | None = None) -> None:
        path = rules_path or DEFAULT_RULES_PATH
        self.raw_rules = self._load_rules(path)
        self.route_patterns = [re.compile(item["pattern"], re.IGNORECASE) for item in self.raw_rules["routes"]]
        self.vehicle_patterns = [
            (re.compile(item["pattern"], re.IGNORECASE), item.get("value"))
            for item in self.raw_rules["vehicles"]
        ]
        self.tonnage_patterns = [re.compile(item["pattern"], re.IGNORECASE) for item in self.raw_rules["tonnage"]]
        self.price_patterns = [re.compile(item["pattern"], re.IGNORECASE) for item in self.raw_rules["prices"]]

    @staticmethod
    def _load_rules(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Parsing rules file is missing: {path}")
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def parse(
        self,
        *,
        chat_id: int,
        message_id: int,
        posted_at: dt.datetime,
        text: str,
    ) -> ParsedMessage:
        parsed = ParsedMessage(
            chat_id=chat_id,
            message_id=message_id,
            posted_at=posted_at,
            raw_text=text,
        )
        cleaned = self._normalize_text(text)
        self._apply_route(cleaned, parsed)
        self._apply_vehicle(cleaned, parsed)
        self._apply_tonnage(cleaned, parsed)
        self._apply_price(cleaned, parsed)
        self._apply_contact(cleaned, parsed)
        parsed.metadata["normalized_text"] = cleaned
        return parsed

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\n", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _apply_route(self, text: str, parsed: ParsedMessage) -> None:
        for pattern in self.route_patterns:
            match = pattern.search(text)
            if not match:
                continue
            parsed.route_from = (match.group("origin") or "").strip()
            parsed.route_to = (match.group("destination") or "").strip()
            parsed.tags.extend([parsed.route_from, parsed.route_to])
            break

    def _apply_vehicle(self, text: str, parsed: ParsedMessage) -> None:
        for pattern, value in self.vehicle_patterns:
            match = pattern.search(text)
            if not match:
                continue
            parsed.vehicle_type = value or match.group("vehicle").strip()
            parsed.tags.append(parsed.vehicle_type)
            break

    def _apply_tonnage(self, text: str, parsed: ParsedMessage) -> None:
        for pattern in self.tonnage_patterns:
            match = pattern.search(text)
            if not match:
                continue
            try:
                parsed.tonnage_tons = float(match.group("tons"))
            except (ValueError, TypeError):
                continue
            break

    def _apply_price(self, text: str, parsed: ParsedMessage) -> None:
        for pattern in self.price_patterns:
            match = pattern.search(text)
            if not match:
                continue
            try:
                parsed.price_amount = float(match.group("amount"))
            except (ValueError, TypeError):
                continue
            currency = match.groupdict().get("currency")
            parsed.price_currency = currency.upper() if currency else None
            break

    def _apply_contact(self, text: str, parsed: ParsedMessage) -> None:
        phone_match = re.search(r"(\+?\d{10,15})", text)
        if phone_match:
            parsed.contact = phone_match.group(1)
            parsed.metadata.setdefault("contacts", []).append(parsed.contact)
        else:
            tg_match = re.search(r"@(?P<username>[A-Za-z0-9_]{5,})", text)
            if tg_match:
                username = tg_match.group("username")
                parsed.contact = f"@{username}"
                parsed.metadata.setdefault("contacts", []).append(parsed.contact)
