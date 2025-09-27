from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

_MODULE_PATH = Path(__file__).resolve()
DEFAULT_CITIES_PATHS = [
    _MODULE_PATH.parents[3] / "rules" / "cities.yaml",
    _MODULE_PATH.parents[2] / "rules" / "cities.yaml",
]


@dataclass(slots=True, frozen=True)
class CityRecord:
    city_id: str
    name: str
    country: str
    region: str | None
    aliases: tuple[str, ...]

    def to_metadata(self) -> dict[str, Any]:
        return {
            "city_id": self.city_id,
            "name": self.name,
            "country": self.country,
            "region": self.region,
            "aliases": list(self.aliases),
        }


class CityDirectory:
    def __init__(self, path: Path | None = None) -> None:
        self._source_path = self._resolve_path(path)
        self._alias_index: dict[str, CityRecord] = {}
        self._records: dict[str, CityRecord] = {}
        self._collisions: dict[str, set[str]] = {}
        self.reload()

    @property
    def source_path(self) -> Path:
        return self._source_path

    @property
    def collisions(self) -> dict[str, set[str]]:
        return self._collisions

    @property
    def cities(self) -> Iterable[CityRecord]:
        return self._records.values()

    def reload(self) -> None:
        data = self._load_yaml(self._source_path)
        records: dict[str, CityRecord] = {}
        alias_index: dict[str, CityRecord] = {}
        collisions: dict[str, set[str]] = {}

        for item in data.get("cities", []):
            record = self._build_record(item)
            records[record.city_id] = record
            for alias in (*record.aliases, record.name):
                normalized = self._normalize_alias(alias)
                if not normalized:
                    continue
                existing = alias_index.get(normalized)
                if existing and existing.city_id != record.city_id:
                    collision = collisions.setdefault(normalized, {existing.city_id})
                    collision.add(record.city_id)
                    continue
                alias_index[normalized] = record

        self._records = records
        self._alias_index = alias_index
        self._collisions = collisions

    def find(self, value: str | None) -> CityRecord | None:
        if not value:
            return None
        normalized = self._normalize_alias(value)
        if not normalized:
            return None
        record = self._alias_index.get(normalized)
        if record:
            return record
        tokens = normalized.split()
        if len(tokens) <= 1:
            return None
        for length in range(len(tokens), 0, -1):
            for start in range(0, len(tokens) - length + 1):
                key = " ".join(tokens[start : start + length])
                record = self._alias_index.get(key)
                if record:
                    return record
        return None

    @classmethod
    def _load_yaml(cls, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"City dictionary file is missing: {path}")
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
            if not isinstance(data, dict):
                raise ValueError("City dictionary YAML must contain a mapping at the top level")
            return data

    @classmethod
    def _build_record(cls, payload: dict[str, Any]) -> CityRecord:
        try:
            city_id = str(payload["id"])
            name = payload["name"].strip()
            country = payload["country"].strip().upper()
        except KeyError as exc:
            raise ValueError(f"City item is missing required field: {exc}") from exc
        region = payload.get("region")
        if region:
            region = str(region).strip() or None
        raw_aliases = payload.get("aliases", [])
        if not isinstance(raw_aliases, list):
            raise ValueError(f"City aliases must be a list for {city_id}")
        aliases: list[str] = []
        for alias in raw_aliases:
            alias_text = str(alias).strip()
            if alias_text:
                aliases.append(alias_text)
        unique_aliases = tuple(dict.fromkeys(aliases))
        return CityRecord(
            city_id=city_id,
            name=name,
            country=country,
            region=region,
            aliases=unique_aliases,
        )

    @classmethod
    def _normalize_alias(cls, value: str) -> str:
        text = unicodedata.normalize("NFKC", value.lower())
        text = text.replace("'", " ").replace("", " ").replace("’", " ").replace("ʻ", " ")
        text = text.replace("ё", "е").replace("ў", "у")
        text = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
        text = text.replace("-", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @classmethod
    def _resolve_path(cls, override: Path | None) -> Path:
        if override:
            return override
        for candidate in DEFAULT_CITIES_PATHS:
            if candidate.exists():
                return candidate
        return DEFAULT_CITIES_PATHS[0]

