from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from loguru import logger

from logistics_bot.db import models
from logistics_bot.db.repository import MessageRepository
from logistics_bot.db.session import get_session
from logistics_bot.parsing.parser import MessageParser
from logistics_bot.parsing.schemas import ParsedMessage
from logistics_bot.services.dedup_service import DedupDecision, DedupService


@dataclass(slots=True)
class PipelineResult:
    stored_id: uuid.UUID | None
    duplicate_of: uuid.UUID | None
    parsed: ParsedMessage


class MessagePipeline:
    def __init__(self, parser: MessageParser, dedup_service: DedupService) -> None:
        self.parser = parser
        self.dedup_service = dedup_service

    async def handle_message(
        self,
        *,
        chat_id: int,
        message_id: int,
        posted_at: dt.datetime,
        text: str,
    ) -> PipelineResult:
        preview = text.replace("\n", " ")
        if len(preview) > 300:
            preview = preview[:300] + "…"
        logger.info(
            "Collector received message chat_id=%s message_id=%s text=%s",
            chat_id,
            message_id,
            preview,
        )
        parsed = self.parser.parse(
            chat_id=chat_id,
            message_id=message_id,
            posted_at=posted_at,
            text=text,
        )
        normalized_text = parsed.metadata.get("normalized_text", parsed.raw_text)
        hash_digest = self.dedup_service.hash_payload(chat_id, message_id, normalized_text)

        async with get_session() as session:
            repo = MessageRepository(session)
            decision = await self.dedup_service.detect_duplicate(
                repo=repo, hash_digest=hash_digest, candidate_text=normalized_text
            )

            if decision.is_duplicate and decision.duplicate_of_id:
                logger.info(
                    "Duplicate message skipped (chat_id=%s message_id=%s) -> %s",
                    chat_id,
                    message_id,
                    decision.duplicate_of_id,
                )
                await session.rollback()
                return PipelineResult(None, decision.duplicate_of_id, parsed)

            record = models.Message(
                chat_id=str(parsed.chat_id),
                message_id=parsed.message_id,
                posted_at=parsed.posted_at,
                raw_text=parsed.raw_text,
                route_from=parsed.route_from,
                route_to=parsed.route_to,
                route_from_city_id=parsed.route_from_city_id,
                route_from_city_name=parsed.route_from_city_name,
                route_from_country=parsed.route_from_country,
                route_from_region=parsed.route_from_region,
                route_to_city_id=parsed.route_to_city_id,
                route_to_city_name=parsed.route_to_city_name,
                route_to_country=parsed.route_to_country,
                route_to_region=parsed.route_to_region,
                vehicle_type=parsed.vehicle_type,
                tonnage_tons=parsed.tonnage_tons,
                price_amount=parsed.price_amount,
                price_currency=parsed.price_currency,
                contact=parsed.contact,
                tags=parsed.tags,
                extra_metadata=parsed.metadata,
                hash_digest=hash_digest,
            )
            stored = await repo.insert_message(record)
            await session.commit()
            await self.dedup_service.register_message(
                hash_digest=hash_digest, message_id=stored.id
            )
            logger.info(
                "Stored message %s from chat %s", stored.id, parsed.chat_id
            )
            return PipelineResult(stored.id, None, parsed)

