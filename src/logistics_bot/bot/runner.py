from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger

from logistics_bot.config.settings import get_settings
from logistics_bot.db.repository import ChatRepository, MessageRepository
from logistics_bot.db.session import get_session


def _build_message_link(chat_id: str, message_id: int) -> str | None:
    try:
        chat_int = int(chat_id)
    except ValueError:
        return None
    if chat_int < 0:
        return f"https://t.me/c/{str(chat_int)[4:]}/{message_id}"
    return None


class BotAgent:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.tg_bot_token:
            raise RuntimeError("TG_BOT_TOKEN is required for bot agent")
        self.bot = Bot(token=self.settings.tg_bot_token)
        self.dispatcher = Dispatcher()
        self._register_handlers()

    def _register_handlers(self) -> None:
        dp = self.dispatcher

        @dp.message(Command("start"))
        async def start_handler(message: Message) -> None:
            await message.answer(
                "Привет! Отправь `/find Tashkent->Moscow` или `/find Samarkand` "
                "чтобы получить последние рейсы.",
                parse_mode="Markdown",
            )

        @dp.message(Command("find"))
        async def find_handler(message: Message, command: CommandObject) -> None:
            args = command.args or ""
            origin = None
            destination = None
            vehicle_type = None
            if "->" in args:
                parts = [part.strip() for part in args.split("->", maxsplit=1)]
                origin = parts[0] or None
                destination = parts[1] or None
            else:
                parts = args.split()
                if parts:
                    origin = parts[0]
                if len(parts) > 1:
                    destination = parts[1]
                if len(parts) > 2:
                    vehicle_type = parts[2]

            async with get_session() as session:
                repo = MessageRepository(session)
                results = await repo.search_messages(
                    origin=origin,
                    destination=destination,
                    vehicle_type=vehicle_type,
                    limit=self.settings.max_results_per_query,
                )

            if not results:
                await message.answer("Совпадений не найдено. Попробуйте уточнить маршрут.")
                return

            for item in results:
                link = _build_message_link(item.chat_id, item.message_id)
                text = (
                    f"{item.route_from or 'Не указано'} -> {item.route_to or 'Не указано'}\n"
                    f"Тип: {item.vehicle_type or 'n/a'} | Тоннаж: {item.tonnage_tons or 'n/a'}\n"
                    f"Цена: {item.price_amount or 'n/a'} {item.price_currency or ''}\n"
                    f"Контакт: {item.contact or 'n/a'}"
                )
                reply_markup = None
                if link:
                    reply_markup = InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text="Открыть пост", url=link)]]
                    )
                await message.answer(text, reply_markup=reply_markup)

        @dp.message(Command("add_chat"))
        async def add_chat_handler(message: Message, command: CommandObject) -> None:
            args = (command.args or "").split(maxsplit=1)
            if len(args) < 2:
                await message.answer("Использование: /add_chat <id> <title>")
                return
            try:
                chat_id = int(args[0])
            except ValueError:
                await message.answer("ID чата должен быть числом")
                return
            title = args[1].strip()
            async with get_session() as session:
                repo = ChatRepository(session)
                chat = await repo.upsert_chat(chat_id, title)
                await session.commit()
            await message.answer(f"Чат {chat.title} сохранен и активирован.")

    async def run(self) -> None:
        logger.info("Starting bot agent")
        await self.dispatcher.start_polling(self.bot)


async def run_bot() -> None:
    agent = BotAgent()
    await agent.run()
