from __future__ import annotations

import asyncio
import datetime as dt
from typing import Set

from loguru import logger
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from logistics_bot.config.settings import get_settings
from logistics_bot.db.repository import ChatRepository
from logistics_bot.db.session import get_session
from logistics_bot.services.message_pipeline import MessagePipeline

REFRESH_INTERVAL_SECONDS = 300


class CollectorAgent:
    def __init__(self, pipeline: MessagePipeline) -> None:
        self.settings = get_settings()
        if not self.settings.tg_session_string:
            raise RuntimeError("TG_SESSION_STRING is required for collector agent")
        self.pipeline = pipeline
        self.client = TelegramClient(
            StringSession(self.settings.tg_session_string),
            self.settings.tg_api_id,
            self.settings.tg_api_hash,
        )
        self.allowed_chats: Set[int] = set()

    async def refresh_allowed_chats(self) -> None:
        async with get_session() as session:
            chats = await ChatRepository(session).list_active()
        self.allowed_chats = {chat.telegram_id for chat in chats}
        logger.info("Loaded %s allowed chats", len(self.allowed_chats))

    async def _handle_new_message(self, event: events.NewMessage.Event) -> None:
        if event.message.raw_text is None:
            return
        chat = await event.get_chat()
        if chat is None:
            return
        chat_id = getattr(chat, "id", None)
        if chat_id is None:
            return
        if self.allowed_chats and chat_id not in self.allowed_chats:
            return
        message = event.message
        posted_at = dt.datetime.fromtimestamp(message.date.timestamp(), dt.timezone.utc)
        await self.pipeline.handle_message(
            chat_id=chat_id,
            message_id=message.id,
            posted_at=posted_at,
            text=message.raw_text,
        )

    async def run(self) -> None:
        await self.refresh_allowed_chats()
        self.client.add_event_handler(self._handle_new_message, events.NewMessage())
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise RuntimeError("Telegram session is not authorized")
        logger.info("Collector agent started")
        task = asyncio.create_task(self._refresh_loop())
        try:
            await self.client.run_until_disconnected()
        finally:
            task.cancel()
            await self.client.disconnect()

    async def _refresh_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
                await self.refresh_allowed_chats()
        except asyncio.CancelledError:
            return


async def run_collector(pipeline: MessagePipeline) -> None:
    agent = CollectorAgent(pipeline)
    await agent.run()
