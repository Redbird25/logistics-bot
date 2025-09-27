from __future__ import annotations

import asyncio
import re
import unicodedata
import uuid
from dataclasses import dataclass
from hashlib import sha1
from typing import Iterable

from difflib import SequenceMatcher
from redis.asyncio import Redis

from logistics_bot.db.repository import MessageRepository
from logistics_bot.parsing.cities import CityDirectory


_CYR_TO_LAT = {
    'а': 'a',
    'б': 'b',
    'в': 'v',
    'г': 'g',
    'д': 'd',
    'е': 'e',
    'ё': 'yo',
    'ж': 'zh',
    'з': 'z',
    'и': 'i',
    'й': 'y',
    'к': 'k',
    'л': 'l',
    'м': 'm',
    'н': 'n',
    'о': 'o',
    'п': 'p',
    'р': 'r',
    'с': 's',
    'т': 't',
    'у': 'u',
    'ф': 'f',
    'х': 'h',
    'ц': 'ts',
    'ч': 'ch',
    'ш': 'sh',
    'щ': 'shch',
    'ъ': '',
    'ы': 'y',
    'ь': '',
    'э': 'e',
    'ю': 'yu',
    'я': 'ya',
    'ә': 'a',
    'ғ': 'g',
    'қ': 'q',
    'ҳ': 'h',
    'ӣ': 'i',
    'ө': 'o',
    'ү': 'u',
    'ў': 'u',
    'ӱ': 'u',
    'ҕ': 'g',
    'ң': 'ng',
    'җ': 'zh',
    'ї': 'i',
    'і': 'i',
}



@dataclass(slots=True)
class DedupDecision:
    is_duplicate: bool
    duplicate_of_id: uuid.UUID | None = None


class DedupService:
    def __init__(
        self,
        redis_client: Redis,
        *,
        ttl_seconds: int,
        similarity_threshold: float,
        city_directory: CityDirectory | None = None,
    ) -> None:
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
        self.similarity_threshold = similarity_threshold
        self.city_directory = city_directory or CityDirectory()

    @staticmethod
    def hash_payload(chat_id: int, message_id: int, text: str) -> str:
        digest = sha1()
        digest.update(str(chat_id).encode())
        digest.update(b'::')
        digest.update(str(message_id).encode())
        digest.update(b'::')
        digest.update(text.strip().lower().encode())
        return digest.hexdigest()

    def _transliterate(self, value: str) -> str:
        return ''.join(_CYR_TO_LAT.get(char, char) for char in value)

    def _normalize_for_similarity(self, text: str) -> str:
        text = unicodedata.normalize('NFKC', text)
        segments = re.split(r'(\W+)', text)
        parts: list[str] = []
        for segment in segments:
            if not segment:
                continue
            if segment.isspace():
                parts.append(' ')
                continue
            record = self.city_directory.find(segment) if self.city_directory else None
            if record:
                parts.append(record.name.lower())
                continue
            parts.append(self._transliterate(segment.lower()))
        normalized = ''.join(parts)
        normalized = re.sub(r'[^a-z0-9]+', ' ', normalized)
        return normalized.strip()

    async def detect_duplicate(
        self,
        *,
        repo: MessageRepository,
        hash_digest: str,
        candidate_text: str,
    ) -> DedupDecision:
        cache_key = f"msg-hash:{hash_digest}"
        cached = await self.redis.get(cache_key)
        if cached:
            try:
                return DedupDecision(True, uuid.UUID(cached.decode()))
            except ValueError:
                return DedupDecision(True, None)

        db_match = await repo.get_by_hash(hash_digest)
        if db_match:
            await self.redis.setex(cache_key, self.ttl_seconds, str(db_match.id))
            return DedupDecision(True, db_match.id)

        recent: Iterable = await repo.recent_messages(limit=25)
        normalized_candidate = self._normalize_for_similarity(candidate_text)
        if not normalized_candidate:
            normalized_candidate = candidate_text.strip().lower()
        for message in recent:
            reference = self._normalize_for_similarity(message.raw_text)
            if not reference:
                reference = message.raw_text.strip().lower()
            similarity = SequenceMatcher(None, reference, normalized_candidate).ratio()
            if similarity >= self.similarity_threshold:
                await self.redis.setex(cache_key, self.ttl_seconds, str(message.id))
                return DedupDecision(True, message.id)

        await self.redis.setex(cache_key, self.ttl_seconds, "unique")
        return DedupDecision(False)

    async def register_message(self, *, hash_digest: str, message_id: uuid.UUID) -> None:
        cache_key = f"msg-hash:{hash_digest}"
        await self.redis.setex(cache_key, self.ttl_seconds, str(message_id))

    async def close(self) -> None:
        if hasattr(self.redis, "aclose"):
            await self.redis.aclose()  # type: ignore[attr-defined]
        else:
            await self.redis.close()


async def build_dedup_service(
    redis_url: str,
    *,
    ttl_seconds: int,
    similarity_threshold: float,
) -> DedupService:
    redis = Redis.from_url(redis_url, decode_responses=False)
    await redis.ping()
    city_directory = CityDirectory()
    return DedupService(
        redis,
        ttl_seconds=ttl_seconds,
        similarity_threshold=similarity_threshold,
        city_directory=city_directory,
    )
