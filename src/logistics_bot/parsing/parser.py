from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from logistics_bot.parsing.cities import CityDirectory
from logistics_bot.parsing.schemas import ParsedMessage

_MODULE_PATH = Path(__file__).resolve()
DEFAULT_RULES_PATHS = [
    _MODULE_PATH.parents[3] / "rules" / "messages.yaml",
    _MODULE_PATH.parents[2] / "rules" / "messages.yaml",
]


@dataclass(slots=True)
class ParseSegment:
    text: str
    start_line: int
    end_line: int
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def length(self) -> int:
        return max(0, self.end_line - self.start_line + 1)


@dataclass(slots=True)
class ParseContext:
    normalized_text: str
    lines: list[str]
    segments: list[ParseSegment]

    @property
    def is_multi_listing(self) -> bool:
        return len(self.segments) > 1


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
    "usd",
    "eur",
    "rub",
    "uzs",
    "byn",
    "som",
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
BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-\u2022*]|(?:\d{1,2}|[A-Za-z])[).:-])\s*")
ENUMERATION_BREAK_RE = re.compile(r"^\s*\d{1,2}[).:-]\s*")


class MessageParser:
    VEHICLE_CANONICAL: dict[str, str] = {
        'tent': 'Тент',
        'тент': 'Тент',
        'тентованный': 'Тент',
        'tент': 'Тент',
        'ref': 'Реф',
        'реф': 'Реф',
        'реф.': 'Реф',
        'рефрижератор': 'Реф',
        'refrigerated': 'Реф',
        'reef': 'Реф',
        'container': 'Контейнер',
        'контейнер': 'Контейнер',
        'контейнеровоз': 'Контейнер',
        'flatbed': 'Площадка',
        'площадка': 'Площадка',
        'платформа': 'Площадка',
        'platform': 'Площадка',
        'truck': 'Фура',
        'фура': 'Фура',
        'фура-р': 'Фура',
        'бортовой': 'Бортовой',
        'bort': 'Бортовой',
    }

    def __init__(
        self,
        rules_path: Path | None = None,
        *,
        cities_path: Path | None = None,
    ) -> None:
        rules_file = self._resolve_rules_path(rules_path)
        self.rules_path = rules_file
        self.raw_rules = self._load_rules(rules_file)
        self.route_patterns = [
            re.compile(item["pattern"], re.IGNORECASE)
            for item in self.raw_rules.get("routes", [])
        ]
        self.vehicle_patterns = [
            (re.compile(item["pattern"], re.IGNORECASE), item.get("value"))
            for item in self.raw_rules.get("vehicles", [])
        ]
        self.tonnage_patterns = [
            re.compile(item["pattern"], re.IGNORECASE)
            for item in self.raw_rules.get("tonnage", [])
        ]
        self.price_patterns = [
            re.compile(item["pattern"], re.IGNORECASE)
            for item in self.raw_rules.get("prices", [])
        ]
        self.cargo_patterns = [
            (re.compile(item["pattern"], re.IGNORECASE), item.get("value"))
            for item in self.raw_rules.get("cargo", [])
        ]
        self.urgency_patterns = [
            (re.compile(item["pattern"], re.IGNORECASE), item.get("value", "urgent"))
            for item in self.raw_rules.get("urgency", [])
        ]
        self.city_directory = CityDirectory(cities_path)

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

    def reload_cities(self, cities_path: Path | None = None) -> None:
        if cities_path:
            self.city_directory = CityDirectory(cities_path)
        else:
            self.city_directory.reload()

    def _build_context(self, text: str) -> ParseContext:
        normalized = self._normalize_text(text)
        lines = normalized.splitlines()
        if not lines:
            lines = [normalized]
        segments = self._segment_text(normalized, lines)
        return ParseContext(normalized_text=normalized, lines=lines, segments=segments)

    def _run_pipeline(self, text: str, parsed: ParsedMessage) -> None:
        parsed.metadata.setdefault("stage_text", text)
        self._apply_route(text, parsed)
        self._apply_price(text, parsed)
        self._apply_vehicle(text, parsed)
        self._apply_contact(text, parsed)
        self._apply_tonnage(text, parsed)
        self._apply_cargo(text, parsed)
        self._apply_urgency(text, parsed)
        self._apply_city_matches(parsed)

    def _segment_text(self, normalized: str, lines: list[str]) -> list[ParseSegment]:
        stripped = normalized.strip()
        if not stripped:
            return []
        segments: list[ParseSegment] = []
        buffer: list[str] = []
        start_line = 0
        for idx, raw_line in enumerate(lines):
            content = raw_line.strip()
            if not content:
                if buffer:
                    segment_text = "\n".join(buffer).strip()
                    if segment_text:
                        segments.append(ParseSegment(text=segment_text, start_line=start_line, end_line=idx - 1))
                    buffer = []
                continue
            if buffer and (BULLET_PREFIX_RE.match(raw_line) or ENUMERATION_BREAK_RE.match(raw_line)):
                segment_text = "\n".join(buffer).strip()
                if segment_text:
                    segments.append(ParseSegment(text=segment_text, start_line=start_line, end_line=idx - 1))
                buffer = []
            if not buffer:
                start_line = idx
            buffer.append(self._strip_bullet_prefix(raw_line))
        if buffer:
            segment_text = "\n".join(buffer).strip()
            if segment_text:
                segments.append(ParseSegment(text=segment_text, start_line=start_line, end_line=len(lines) - 1))
        if not segments:
            return [ParseSegment(text=stripped, start_line=0, end_line=len(lines) - 1)]
        if len(segments) == 1:
            return segments
        meaningful: list[ParseSegment] = []
        for segment in segments:
            route_hits = self._count_route_hits(segment.text)
            segment.metadata["route_hits"] = route_hits
            if route_hits:
                meaningful.append(segment)
        return meaningful if meaningful else segments[:1]

    @staticmethod
    def _strip_bullet_prefix(line: str) -> str:
        if not line:
            return ""
        if BULLET_PREFIX_RE.match(line):
            return BULLET_PREFIX_RE.sub("", line, count=1).lstrip()
        return line.lstrip()

    def _count_route_hits(self, text: str) -> int:
        hits = 0
        for pattern in self.route_patterns:
            if pattern.search(text):
                hits += 1
        origin, destination = self._guess_route_from_lines(text)
        if origin and destination:
            hits += 1
        return hits

    def _score_segment(self, parsed: ParsedMessage) -> float:
        score = 0.0
        if parsed.route_from and parsed.route_to:
            score += 3.0
        if parsed.contact:
            score += 2.0
        if parsed.vehicle_type:
            score += 1.5
        if parsed.price_amount:
            score += 0.75
        if parsed.tonnage_tons:
            score += 0.5
        if parsed.cargo:
            score += 0.25
        if parsed.urgency:
            score += 0.1
        return score

    def _segment_payload(
        self,
        segment: ParseSegment,
        parsed: ParsedMessage,
        *,
        include_metadata: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "text": segment.text,
            "start_line": segment.start_line,
            "end_line": segment.end_line,
            "confidence": segment.confidence,
            "route_from": parsed.route_from,
            "route_to": parsed.route_to,
            "vehicle_type": parsed.vehicle_type,
            "tonnage_tons": parsed.tonnage_tons,
            "price_amount": parsed.price_amount,
            "price_currency": parsed.price_currency,
            "contact": parsed.contact,
            "cargo": parsed.cargo,
            "urgency": parsed.urgency,
            "valid_until": parsed.valid_until.isoformat() if parsed.valid_until else None,
        }
        if include_metadata:
            metadata_copy = {
                key: value
                for key, value in parsed.metadata.items()
                if key not in {"segments", "normalized_text", "stage_text"}
            }
            if metadata_copy:
                payload["metadata"] = metadata_copy
        return payload

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
        context = self._build_context(text)
        parsed.metadata["normalized_text"] = context.normalized_text
        parsed.metadata["segment_count"] = len(context.segments)
        parsed.metadata["multi_listing"] = context.is_multi_listing
        segments_payload: list[dict[str, Any]] = []

        if not context.segments:
            context.segments = [
                ParseSegment(
                    text=context.normalized_text,
                    start_line=0,
                    end_line=len(context.lines) - 1,
                )
            ]

        if not context.is_multi_listing:
            segment_text = context.segments[0].text
            self._run_pipeline(segment_text, parsed)
            context.segments[0].confidence = self._score_segment(parsed)
            segments_payload.append(
                self._segment_payload(context.segments[0], parsed, include_metadata=True)
            )
        else:
            best_choice: tuple[float, ParseSegment] | None = None
            best_segment_text: str | None = None
            for segment in context.segments:
                segment_result = ParsedMessage(
                    chat_id=chat_id,
                    message_id=message_id,
                    posted_at=posted_at,
                    raw_text=segment.text,
                )
                self._run_pipeline(segment.text, segment_result)
                score = self._score_segment(segment_result)
                segment.confidence = score
                segments_payload.append(
                    self._segment_payload(segment, segment_result, include_metadata=True)
                )
                if best_choice is None or score > best_choice[0]:
                    best_choice = (score, segment)
                    best_segment_text = segment.text

            if best_choice and best_choice[0] > 0 and best_segment_text:
                self._run_pipeline(best_segment_text, parsed)
            else:
                self._run_pipeline(context.normalized_text, parsed)

        parsed.metadata["segments"] = segments_payload
        parsed.metadata["segmentation_strategy"] = (
            "multi" if context.is_multi_listing else "single"
        )
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
            vehicle_value = value or match.group("vehicle").strip()
            canonical_vehicle = self._normalize_vehicle_value(vehicle_value)
            parsed.vehicle_type = canonical_vehicle
            if canonical_vehicle and canonical_vehicle not in parsed.tags:
                parsed.tags.append(canonical_vehicle)
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

    def _apply_cargo(self, text: str, parsed: ParsedMessage) -> None:
        if not getattr(self, "cargo_patterns", None):
            return
        matches: list[str] = []
        for pattern, value in self.cargo_patterns:
            match = pattern.search(text)
            if not match:
                continue
            label = value or match.groupdict().get("cargo") or match.group(0)
            label = label.strip()
            if not label:
                continue
            matches.append(label)
        if matches:
            if not parsed.cargo:
                parsed.cargo = matches[0]
            parsed.metadata.setdefault("cargo_matches", matches)
            for label in matches:
                if label not in parsed.tags:
                    parsed.tags.append(label)

    def _apply_urgency(self, text: str, parsed: ParsedMessage) -> None:
        matches: list[str] = []
        for pattern, value in getattr(self, "urgency_patterns", []):
            if pattern.search(text):
                matches.append(value or "urgent")
        if matches:
            if not parsed.urgency:
                parsed.urgency = matches[0]
            parsed.metadata.setdefault("urgency_matches", matches)
        validity = self._extract_valid_until(text, parsed.posted_at)
        if validity:
            parsed.valid_until = validity
            parsed.metadata["valid_until_source"] = "time_hint"

    def _extract_valid_until(self, text: str, posted_at: dt.datetime) -> dt.datetime | None:
        time_match = re.search(r"\b\u0434\u043e\s*(\d{1,2})[:.](\d{2})", text, re.IGNORECASE)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            tzinfo = posted_at.tzinfo or dt.timezone.utc
            time_value = dt.time(hour=hour, minute=minute, tzinfo=tzinfo)
            candidate = dt.datetime.combine(posted_at.date(), time_value)
            if candidate <= posted_at:
                candidate += dt.timedelta(days=1)
            return candidate

        relative_markers = [
            (r"\b\u0441\u0435\u0433\u043e\u0434\u043d\u044f\b", 0),
            (r"\b\u0437\u0430\u0432\u0442\u0440\u0430\b", 1),
            (r"\b\u043f\u043e\u0441\u043b\u0435\u0437\u0430\u0432\u0442\u0440\u0430\b", 2),
        ]
        for marker, offset in relative_markers:
            if re.search(marker, text, re.IGNORECASE):
                tzinfo = posted_at.tzinfo or dt.timezone.utc
                candidate_date = posted_at.date() + dt.timedelta(days=offset)
                return dt.datetime.combine(candidate_date, dt.time(23, 59, tzinfo=tzinfo))

        if re.search(r"\b\u0434\u043e \u043a\u043e\u043d\u0446\u0430 \u0434\u043d\u044f\b", text, re.IGNORECASE):
            tzinfo = posted_at.tzinfo or dt.timezone.utc
            return dt.datetime.combine(posted_at.date(), dt.time(23, 59, tzinfo=tzinfo))

        english_markers = [
            (r"\burgent\b", 0),
            (r"\btoday\b", 0),
            (r"\btomorrow\b", 1),
        ]
        for marker, offset in english_markers:
            if re.search(marker, text, re.IGNORECASE):
                tzinfo = posted_at.tzinfo or dt.timezone.utc
                candidate_date = posted_at.date() + dt.timedelta(days=offset)
                return dt.datetime.combine(candidate_date, dt.time(23, 59, tzinfo=tzinfo))
        return None

    def _apply_city_matches(self, parsed: ParsedMessage) -> None:
        for field in ("route_from", "route_to"):
            value = getattr(parsed, field)
            if not value:
                continue
            record = self.city_directory.find(value)
            if not record:
                continue
            metadata_key = f"{field}_city"
            payload = record.to_metadata()
            payload['raw'] = value
            parsed.metadata[metadata_key] = payload
            setattr(parsed, f"{field}_city_id", record.city_id)
            setattr(parsed, f"{field}_city_name", record.name)
            setattr(parsed, f"{field}_country", record.country)
            setattr(parsed, f"{field}_region", record.region)
            canonical_value = record.name
            setattr(parsed, field, canonical_value)
            raw_tag = value.strip()
            if raw_tag and raw_tag not in parsed.metadata.setdefault('route_raw', []):
                parsed.metadata.setdefault('route_raw', []).append(raw_tag)
            if canonical_value not in parsed.tags:
                parsed.tags.append(canonical_value)

    def _normalize_vehicle_value(self, value: str | None) -> str | None:
        if not value:
            return None
        candidate = value.strip()
        if not candidate:
            return None
        key = candidate.lower()
        canonical = self.VEHICLE_CANONICAL.get(key)
        if canonical:
            return canonical
        cleaned = re.sub(r'[^\w\s]', '', key)
        canonical = self.VEHICLE_CANONICAL.get(cleaned)
        if canonical:
            return canonical
        return candidate

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












