from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from hashlib import sha1
from typing import Iterable

from difflib import SequenceMatcher
from redis.asyncio import Redis

from logistics_bot.db.repository import MessageRepository


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
    ) -> None:
        self.redis = redis_client
        self.ttl_seconds = ttl_seconds
        self.similarity_threshold = similarity_threshold

    @staticmethod
    def hash_payload(chat_id: int, message_id: int, text: str) -> str:
        digest = sha1()
        digest.update(str(chat_id).encode())
        digest.update(b"::")
        digest.update(str(message_id).encode())
        digest.update(b"::")
        digest.update(text.strip().lower().encode())
        return digest.hexdigest()

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
        normalized_candidate = candidate_text.strip().lower()
        for message in recent:
            similarity = SequenceMatcher(
                None, message.raw_text.strip().lower(), normalized_candidate
            ).ratio()
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
    return DedupService(
        redis,
        ttl_seconds=ttl_seconds,
        similarity_threshold=similarity_threshold,
    )
