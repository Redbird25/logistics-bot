from __future__ import annotations

import datetime as dt
import re
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger

from logistics_bot.config.settings import get_settings
from logistics_bot.db.repository import ChatRepository, MessageRepository
from logistics_bot.db.session import get_session
from logistics_bot.parsing.cities import CityDirectory
from logistics_bot.parsing.parser import MessageParser

CITY_DIRECTORY = CityDirectory()
VEHICLE_ALIASES = MessageParser.VEHICLE_CANONICAL


def _build_message_link(chat_id: str, message_id: int) -> str | None:
    try:
        chat_int = int(chat_id)
    except (TypeError, ValueError):
        return None
    if chat_int < 0:
        return f"https://t.me/c/{str(abs(chat_int))[3:]}/{message_id}"
    return None


def _humanize_timedelta(delta: dt.timedelta) -> str:
    minutes = max(int(delta.total_seconds() // 60), 0)
    if minutes < 1:
        return "меньше минуты назад"
    if minutes < 60:
        return f"{minutes} мин назад"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} ч назад"
    days = hours // 24
    return f"{days} дн назад"


def _format_amount(amount: float | None, currency: str | None) -> str:
    if amount is None:
        return "Цена: Не указано"
    value = float(amount)
    if value >= 1_000_000:
        text = f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + " млн"
    elif value >= 1_000:
        text = f"{value / 1_000:.1f}".rstrip("0").rstrip(".") + " тыс"
    else:
        text = f"{value:.0f}" if value.is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")
    currency_map = {"USD": "USD", "EUR": "EUR", "RUB": "₽", "UZS": "сум"}
    suffix = currency_map.get((currency or "").upper(), (currency or "").upper())
    return f"Цена: {text} {suffix}".strip()


def _format_distance(metadata: dict[str, Any]) -> str | None:
    distance = metadata.get("distance_km")
    duration = metadata.get("duration_hours")
    parts: list[str] = []
    if isinstance(distance, (int, float)):
        parts.append(f"{distance:.0f} км")
    if isinstance(duration, (int, float)):
        parts.append(f"{duration:.1f} ч")
    if not parts:
        return None
    return " • ".join(parts)


def _normalize_vehicle_query(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    key = candidate.lower()
    canonical = VEHICLE_ALIASES.get(key)
    if canonical:
        return canonical
    cleaned = re.sub(r"[^\w\s]", "", key)
    canonical = VEHICLE_ALIASES.get(cleaned)
    if canonical:
        return canonical
    return candidate


def _resolve_city_query(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    candidate = value.strip()
    if not candidate:
        return None, None
    record = CITY_DIRECTORY.find(candidate)
    if not record:
        return candidate, None
    return record.name, record.city_id


def _format_result(item, index: int) -> str:
    route_from = (item.route_from or "").strip() or "Не указано"
    route_to = (item.route_to or "").strip() or "Не указано"
    metadata: dict[str, Any] = getattr(item, "extra_metadata", None) or {}
    tags = list(dict.fromkeys(item.tags or [])) if getattr(item, "tags", None) else []
    vehicle = item.vehicle_type or None
    cargo = metadata.get("cargo") or metadata.get("notes")
    distance_line = _format_distance(metadata)
    amount_line = _format_amount(item.price_amount, item.price_currency)
    contact = (item.contact or "Не указано").strip() or "Не указано"
    posted_at = getattr(item, "posted_at", None)
    time_line = None
    if isinstance(posted_at, dt.datetime):
        time_line = _humanize_timedelta(dt.datetime.now(dt.timezone.utc) - posted_at)

    lines = [f"{index}. {route_from} → {route_to}"]

    vehicle_parts: list[str] = []
    if vehicle:
        vehicle_parts.append(vehicle)
    for tag in tags:
        clean = str(tag or "").strip()
        if clean and clean.lower() not in {vehicle.lower() if vehicle else ""}:
            vehicle_parts.append(clean)
    if vehicle_parts:
        lines.append("Кузов: " + ", ".join(vehicle_parts))

    if cargo and str(cargo).strip().lower() != 'n/a':
        lines.append(f"Груз: {cargo}")

    lines.append(amount_line)
    lines.append(f"Контакт: {contact}")

    if distance_line:
        lines.append(f"Маршрут: {distance_line}")
    if time_line:
        lines.append(f"Обновлено: {time_line}")

    return "\n".join(lines)


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
                "Привет! Используйте `/find Ташкент->Бухара` или `/find Ташкент реф`, чтобы найти грузы.",
                parse_mode="Markdown",
            )

        @dp.message(Command("find"))
        async def find_handler(message: Message, command: CommandObject) -> None:
            args = command.args or ""
            origin = None
            destination = None
            vehicle_type = None
            if "->" in args:
                left, right = [part.strip() for part in args.split("->", maxsplit=1)]
                origin = left or None
                destination = right or None
            else:
                parts = [part.strip() for part in args.split() if part.strip()]
                if parts:
                    origin = parts[0]
                if len(parts) > 1:
                    destination = parts[1]
                if len(parts) > 2:
                    vehicle_type = parts[2]

            resolved_origin, resolved_origin_id = _resolve_city_query(origin)
            resolved_destination, resolved_destination_id = _resolve_city_query(destination)
            resolved_vehicle = _normalize_vehicle_query(vehicle_type)

            async with get_session() as session:
                repo = MessageRepository(session)
                results = await repo.search_messages(
                    origin=resolved_origin or origin,
                    destination=resolved_destination or destination,
                    origin_city_id=resolved_origin_id,
                    destination_city_id=resolved_destination_id,
                    vehicle_type=resolved_vehicle or (vehicle_type.strip() if vehicle_type else None),
                    limit=self.settings.max_results_per_query,
                )

            filtered = [item for item in results if (item.route_from and item.route_from.strip()) or (item.route_to and item.route_to.strip())]
            if not filtered:
                await message.answer("Сообщений не найдено. Попробуйте скорректировать запрос.")
                return

            for index, item in enumerate(filtered, start=1):
                link = _build_message_link(item.chat_id, item.message_id)
                text = _format_result(item, index)
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
                await message.answer("Формат: /add_chat <id> <title>")
                return
            try:
                chat_id = int(args[0])
            except ValueError:
                await message.answer("ID должен быть числом")
                return
            title = args[1].strip()
            async with get_session() as session:
                repo = ChatRepository(session)
                chat = await repo.upsert_chat(chat_id, title)
                await session.commit()
            await message.answer(f"Чат {chat.title} добавлен в отслеживание.")

    async def run(self) -> None:
        logger.info("Starting bot agent")
        await self.dispatcher.start_polling(self.bot)


async def run_bot() -> None:
    agent = BotAgent()
    await agent.run()
