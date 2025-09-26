import datetime as dt
from pathlib import Path

from logistics_bot.parsing.parser import MessageParser


def test_parser_extracts_route_and_price(tmp_path: Path) -> None:
    parser = MessageParser()
    text = "Ташкент -> Москва, тент 20т, 2500 usd, +998901234567"
    parsed = parser.parse(
        chat_id=1,
        message_id=42,
        posted_at=dt.datetime.now(dt.timezone.utc),
        text=text,
    )
    assert parsed.route_from == "Ташкент"
    assert parsed.route_to == "Москва"
    assert parsed.vehicle_type == "tent"
    assert parsed.tonnage_tons == 20
    assert parsed.price_amount == 2500
    assert parsed.price_currency == "USD"
    assert parsed.contact == "+998901234567"


def test_parser_handles_dan_pattern() -> None:
    parser = MessageParser()
    text = "Toshkentdan Fargonaga ref fura kk dispechir kk emas 333179688"
    parsed = parser.parse(
        chat_id=1,
        message_id=1,
        posted_at=dt.datetime.now(dt.timezone.utc),
        text=text,
    )
    assert parsed.route_from == "Toshkent"
    assert parsed.route_to == "Fargona"
    assert parsed.vehicle_type == "refrigerated"
    assert parsed.contact == "333179688"


def test_parser_extracts_price_with_symbol_after_amount() -> None:
    parser = MessageParser()
    text = "ТОШКЕНТ -> УРГЕНЧ\nТент 22 тонна\nЦена 7 000 000 сум\nКонтакт +998901234567"
    parsed = parser.parse(
        chat_id=2,
        message_id=2,
        posted_at=dt.datetime.now(dt.timezone.utc),
        text=text,
    )
    assert parsed.route_from == "ТОШКЕНТ"
    assert parsed.route_to == "УРГЕНЧ"
    assert parsed.tonnage_tons == 22
    assert parsed.price_amount == 7000000
    assert parsed.price_currency == "UZS"
    assert parsed.contact == "+998901234567"


def test_parser_filters_reklama_lines() -> None:
    parser = MessageParser()
    text = "ErikApex reklama tarqatmang!"
    parsed = parser.parse(
        chat_id=3,
        message_id=3,
        posted_at=dt.datetime.now(dt.timezone.utc),
        text=text,
    )
    assert parsed.route_from is None
    assert parsed.route_to is None
    assert parsed.vehicle_type is None
