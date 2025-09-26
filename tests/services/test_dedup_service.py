import asyncio
import uuid
from dataclasses import dataclass

import pytest

from logistics_bot.services.dedup_service import DedupService


class FakeRedis:
    def __init__(self) -> None:
        self.storage: dict[str, bytes] = {}

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> bytes | None:
        return self.storage.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.storage[key] = value.encode()

    async def close(self) -> None:
        return None


@dataclass
class FakeMessage:
    id: uuid.UUID
    raw_text: str


class FakeRepo:
    def __init__(self) -> None:
        self.messages: list[FakeMessage] = []

    async def get_by_hash(self, hash_digest: str):
        return None

    async def recent_messages(self, limit: int = 50):
        return self.messages[:limit]


def build_service(similarity: float = 0.85) -> DedupService:
    redis = FakeRedis()
    return DedupService(redis, ttl_seconds=60, similarity_threshold=similarity)


@pytest.mark.anyio
async def test_detect_duplicate_by_similarity() -> None:
    service = build_service(similarity=0.8)
    repo = FakeRepo()
    original_id = uuid.uuid4()
    repo.messages.append(FakeMessage(id=original_id, raw_text="Ташкент -> Москва 20т"))

    candidate_hash = service.hash_payload(1, 2, "Tashkent -> Moscow 20t")
    decision = await service.detect_duplicate(
        repo=repo,
        hash_digest=candidate_hash,
        candidate_text="Tashkent -> Moscow 20t"
    )

    assert decision.is_duplicate is True
    assert decision.duplicate_of_id == original_id
