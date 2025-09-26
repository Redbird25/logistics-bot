from __future__ import annotations

import datetime as dt
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

import yaml

from logistics_bot.parsing.schemas import ParsedMessage

_MODULE_PATH = Path(__file__).resolve()
DEFAULT_RULES_PATHS = [
    _MODULE_PATH.parents[3] / "rules" / "messages.yaml",
    _MODULE_PATH.parents[2] / "rules" / "messages.yaml",
]

FLAG_RE = re.compile(r"[\U0001F1E6-\U0001F1FF]{2}")
EMOJI_RE = re.compile(r"[\U00010000-\U0010FFFF]")
ROUTE_EXCLUDE_KEYWORDS: tuple[str, ...] = (
    "груз",
    "дсп",
    "мдф",
    "мешк",
    "цемент",
    "бетон",
    "шпак",
    "шалак",
    "шланк",
    "биг",
    "бег",
    "контейнер",
    "container",
    "куб",
    "вес",
    "тонн",
    "тонна",
    "паддон",
    "палл",
    "мешках",
    "chips",
    "чипс",
    "напит",
    "мясо",
    "зерн",
    "пшени",
    "нагруз",
    "машин",
    "машина",
    "нужен",
    "нужны",
    "kerak",
    "керек",
    "emas",
    "emas",
    "kk",
    "gas",
    "газ",
    "tel",
    "тел",
    "контакт",
    "логист",
    "дисп",
    "disp",
    "dispech",
    "реклама",
    "reklam",
    "оплата",
    "аван",
    "погруз",
    "razgr",
    "документ",
    "spravo",
    "narx",
    "narxi",
    "kelish",
    "price",
    "tent",
    "тент",
    "реф",
    "fura",
    "фура",
    "platform",
    "площад",
    "аптека",
    "товар",
    "ready",
    "global",
    "gruz",
)

LOCATION_STOPWORDS: set[str] = {
    "kk",
    "kerak",
    "emas",
    "bor",
    "bar",
    "yuk",
    "yuklanadi",
    "yuklanmagan",
    "yuklan",
    "yuklab",
    "yuk",
    "машина",
    "машини",
    "машин",
    "товар",
    "реф",
    "тент",
    "tent",
    "ref",
    "fura",
    "фура",
    "kont",
    "container",
    "kontener",
    "konteyner",
    "контейнер",
    "kub",
    "куб",
    "тонн",
    "тонна",
    "тонны",
    "тон",
    "tonna",
    "ton",
    "poddon",
    "поддон",
    "mixed",
    "цемент",
    "бетон",
    "дсп",
    "мдф",
    "чипс",
    "chips",
    "бетон",
    "кирпич",
    "песок",
    "зерно",
    "расп",
    "оплата",
    "нал",
    "налич",
    "налом",
    "puli",
    "pul",
    "naxt",
    "cash",
    "аванс",
    "dispecher",
    "dispechir",
    "dispatcher",
    "готов",
    "готова",
    "готовы",
    "готовый",
    "логист",
    "дисп",
    "reklama",
    "narxi",
    "narx",
    "kelishiladi",
    "srch",
    "srchno",
    "срочно",
    "договор",
    "дог",
    "doc",
    "документ",
    "glonass",
    "глонасс",
    "uzidan",
    "uziga",
    "узидан",
    "узига",
    "ташка",
}

DIGIT_ONLY_RE = re.compile(r"\d+")


class MessageParser:
    def __init__(self, rules_path: Path | None = None) -> None:
        path = self._resolve_rules_path(rules_path)
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

    @classmethod
    def _resolve_rules_path(cls, override: Path | None) -> Path:
        if override:
            return override
        for candidate in DEFAULT_RULES_PATHS:
            if candidate.exists():
                return candidate
        # fall back to the first candidate for error reporting
        return DEFAULT_RULES_PATHS[0]

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
        text = unicodedata.normalize("NFKC", text)
        text = text.replace("\u200c", "")
        text = text.replace("\u200b", "")
        text = text.replace("\xa0", " ")
        text = text.replace("|", "\n")
        text = text.replace("_", " ")
        text = text.replace("→", "->").replace("➡️", "->").replace("➔", "->")
        text = text.replace("–", "-").replace("—", "-")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\s*\n\s*", "\n", text)
        return text.strip()

    def _apply_route(self, text: str, parsed: ParsedMessage) -> None:
        for pattern in self.route_patterns:
            match = pattern.search(text)
            if not match:
                continue
            origin = self._normalize_location(match.group("origin"))
            destination = self._normalize_location(match.group("destination"))
            if "tail" in match.groupdict() and match.group("tail"):
                destination = self._normalize_location(match.group("tail"))
            if destination and any(sep in destination for sep in ("-", "->")):
                parts = re.split(r"[-–>]+", destination)
                destination = self._normalize_location(parts[-1]) if parts else destination
            if origin and any(sep in origin for sep in ("-", "->")):
                parts = re.split(r"[-–>]+", origin)
                origin = self._normalize_location(parts[0]) if parts else origin
            if origin and destination:
                parsed.route_from = origin
                parsed.route_to = destination
                parsed.tags.extend([origin, destination])
                return

        origin, destination = self._guess_route_from_lines(text)
        if origin and destination:
            parsed.route_from = origin
            parsed.route_to = destination
            parsed.tags.extend([origin, destination])

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
            if match.groupdict().get("tons_high"):
                value = match.group("tons_high")
            else:
                value = match.group("tons") or match.group("tons_low")
            if not value:
                continue
            value = value.replace("_", ".").replace(",", ".")
            try:
                parsed.tonnage_tons = float(value)
            except (ValueError, TypeError):
                continue
            break

    def _apply_price(self, text: str, parsed: ParsedMessage) -> None:
        for pattern in self.price_patterns:
            match = pattern.search(text)
            if not match:
                continue
            amount = match.group("amount")
            if not amount:
                continue
            amount = amount.replace(" ", "").replace(",", ".").replace("_", "")
            try:
                value = float(amount)
            except ValueError:
                # remove thousand separators for integers
                amount_compact = re.sub(r"[^0-9.]", "", amount)
                try:
                    value = float(amount_compact)
                except ValueError:
                    continue
            multiplier = match.groupdict().get("multiplier")
            if multiplier:
                multiplier_lower = multiplier.lower()
                if "мл" in multiplier_lower or "mln" in multiplier_lower or "million" in multiplier_lower:
                    value *= 1_000_000
                elif "тыс" in multiplier_lower or "th" in multiplier_lower:
                    value *= 1_000

            currency = match.groupdict().get("currency")
            currency_symbol = match.groupdict().get("currency_symbol")
            if not currency and not currency_symbol and not multiplier:
                continue

            parsed.price_amount = value
            if currency_symbol:
                parsed.price_currency = self._normalize_currency(currency_symbol)
            elif currency:
                parsed.price_currency = self._normalize_currency(currency)
            else:
                parsed.price_currency = None
            break

    def _apply_contact(self, text: str, parsed: ParsedMessage) -> None:
        phone_candidates: list[tuple[int, str]] = []
        for match in re.finditer(r"(\+?\d[\d\s\-()]{5,}\d)", text):
            raw_value = match.group(1)
            digits_only = re.sub(r"\D", "", raw_value)
            if len(digits_only) < 7:
                continue
            starts_with_plus = raw_value.strip().startswith("+")
            if not starts_with_plus and len(digits_only) <= 8 and " " in raw_value:
                # likely a price like "7 000 000"
                continue
            score = len(digits_only)
            if starts_with_plus:
                score += 5
            if len(digits_only) >= 11:
                score += 2
            normalized = "+" + digits_only if starts_with_plus else digits_only
            phone_candidates.append((score, normalized))
        if phone_candidates:
            _, chosen_phone = max(phone_candidates, key=lambda item: item[0])
        else:
            chosen_phone = None
            fallback = re.search(r"\b(\d{9,12})\b", text)
            if fallback:
                chosen_phone = fallback.group(1)
        if chosen_phone:
            parsed.contact = chosen_phone
            parsed.metadata.setdefault("contacts", []).append(parsed.contact)
            return
        tg_match = re.search(r"@(?P<username>[A-Za-z0-9_]{5,})", text)
        if tg_match:
            username = tg_match.group("username")
            parsed.contact = f"@{username}"
            parsed.metadata.setdefault("contacts", []).append(parsed.contact)

    @staticmethod
    def _normalize_currency(value: str) -> str:
        mapping = {
            "$": "USD",
            "€": "EUR",
            "₽": "RUB",
            "usd": "USD",
            "eur": "EUR",
            "rub": "RUB",
            "руб": "RUB",
            "byn": "BYN",
            "som": "UZS",
            "so'm": "UZS",
            "uzs": "UZS",
            "сум": "UZS",
        }
        return mapping.get(value.lower(), value.upper())

    def _normalize_location(self, value: str | None) -> str | None:
        if not value:
            return None
        value = FLAG_RE.sub("", value)
        value = EMOJI_RE.sub("", value)
        value = value.replace("г.", " ")
        value = re.sub(r"[^A-Za-zА-Яа-яЁё0-9\s'`\u02bb\u02bc-]", " ", value)
        value = re.sub(r"\d+", " ", value)
        value = re.sub(r"\s+", " ", value)
        value = value.strip(" .,-")
        if not value:
            return None
        tokens = []
        for raw_token in value.split():
            token = raw_token.strip("- ")
            if not token:
                continue
            lowered = token.lower()
            suffixes = (
                "dan",
                "дан",
                "данга",
                "га",
                "ga",
                "qa",
                "ка",
                "uzidan",
                "узидан",
                "ning",
                "нинг",
            )
            for suffix in suffixes:
                if lowered.endswith(suffix) and len(token) > len(suffix) + 1:
                    token = token[: -len(suffix)]
                    lowered = token.lower()
                    break
            if not token:
                continue
            if lowered in LOCATION_STOPWORDS:
                continue
            if len(token) <= 1:
                continue
            if DIGIT_ONLY_RE.fullmatch(token):
                continue
            tokens.append(token)
        if not tokens:
            return None
        candidate = " ".join(tokens)
        lowered_candidate = candidate.lower()
        if any(keyword in lowered_candidate for keyword in ROUTE_EXCLUDE_KEYWORDS):
            return None
        return candidate

    def _clean_route_candidate(self, line: str) -> str | None:
        if not line:
            return None
        if "," in line and "[" in line and "]" in line:
            # Telegram author header
            return None
        if re.search(r"\[\d{1,2}/\d{1,2}/\d{2,4}", line):
            return None
        if re.search(r"\b(?:AM|PM)\b", line, re.IGNORECASE):
            return None
        line = unicodedata.normalize("NFKC", line)
        line = FLAG_RE.sub("", line)
        line = EMOJI_RE.sub("", line)
        line = line.strip()
        if not line:
            return None
        if re.match(r"^[+\d]", line):
            return None
        lower = line.lower()
        if any(keyword in lower for keyword in ROUTE_EXCLUDE_KEYWORDS):
            return None
        line = re.sub(r"[^A-Za-zА-Яа-яЁё0-9\s'`\u02bb\u02bc-]", " ", line)
        line = re.sub(r"\s+", " ", line)
        return line.strip(" .,-") or None

    def _guess_route_from_lines(self, text: str) -> tuple[str | None, str | None]:
        candidates: list[str] = []
        for raw_line in text.splitlines():
            line = self._clean_route_candidate(raw_line)
            if not line:
                continue
            split_result = self._split_line_into_locations(line)
            if split_result is not None:
                return split_result
            candidates.append(line)

        normalized_candidates = [self._normalize_location(line) for line in candidates]
        normalized_candidates = [line for line in normalized_candidates if line]

        if len(normalized_candidates) >= 2:
            return normalized_candidates[0], normalized_candidates[1]
        return None, None

    def _split_line_into_locations(self, line: str) -> tuple[str | None, str | None] | None:
        if not line:
            return None
        for delim in ("->", "=>", "➡️", "→", "-", "—", "–"):
            if delim in line:
                left, right = line.split(delim, 1)
                origin = self._normalize_location(left)
                destination = self._normalize_location(right)
                if origin and destination:
                    return origin, destination
        if " узидан " in line.lower():
            parts = re.split(r"\bузидан\b", line, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                origin = self._normalize_location(parts[0])
                destination = self._normalize_location(parts[1])
                if origin and destination:
                    return origin, destination
        return None
