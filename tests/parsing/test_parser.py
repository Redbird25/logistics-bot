import datetime as dt

from logistics_bot.parsing.parser import MessageParser


NOW = dt.datetime(2025, 9, 27, tzinfo=dt.timezone.utc)


def test_parser_extracts_route_price_and_metadata() -> None:
    parser = MessageParser()
    text = "Tashkent -> Moscow, tent 20 tons, 2500 usd, +998901234567"
    parsed = parser.parse(
        chat_id=1,
        message_id=42,
        posted_at=NOW,
        text=text,
    )
    assert parsed.route_from == "Tashkent"
    assert parsed.route_to == "Moscow"
    assert parsed.vehicle_type == "Тент"
    assert parsed.tonnage_tons == 20
    assert parsed.price_amount == 2500
    assert parsed.price_currency == "USD"
    assert parsed.contact == "+998901234567"
    assert parsed.route_from_city_id == "UZ-TAS"
    assert parsed.route_to_city_id == "RU-MOW"
    assert parsed.metadata["segment_count"] == 1
    assert parsed.metadata["segments"][0]["route_from"] == "Tashkent"
    assert parsed.metadata["segments"][0]["vehicle_type"] == "Тент"
    assert parsed.metadata["segments"][0]["price_amount"] == 2500
    assert not parsed.metadata["multi_listing"]
    assert parsed.metadata["segmentation_strategy"] == "single"


def test_parser_handles_dan_pattern_and_segments() -> None:
    parser = MessageParser()
    text = "Toshkentdan Fargonaga ref fura kk dispechir kk emas 333179688"
    parsed = parser.parse(
        chat_id=2,
        message_id=1,
        posted_at=NOW,
        text=text,
    )
    assert parsed.route_from == "Tashkent"
    assert parsed.route_to == "Fergana"
    assert parsed.vehicle_type == "Реф"
    assert parsed.contact == "333179688"
    assert parsed.metadata["segment_count"] == 1
    segment = parsed.metadata["segments"][0]
    assert segment["confidence"] > 0
    assert segment["route_to"] == "Fergana"


def test_parser_extracts_price_with_symbol_after_amount() -> None:
    parser = MessageParser()
    text = """Tashkent -> Urgench
Tent 22 tons
Price 7 000 000 uzs
Contact +998901234567"""
    parsed = parser.parse(
        chat_id=3,
        message_id=2,
        posted_at=NOW,
        text=text,
    )
    assert parsed.route_from == "Tashkent"
    assert parsed.route_to == "Urgench"
    assert parsed.tonnage_tons == 22
    assert parsed.price_amount == 7_000_000
    assert parsed.price_currency == "UZS"
    assert parsed.contact == "+998901234567"
    assert parsed.metadata["segments"][0]["price_currency"] == "UZS"


def test_parser_extracts_cargo_and_urgency() -> None:
    parser = MessageParser()
    text = "Tashkent -> Moscow, зерно 18т, срочно до 18:00, +998901234567"
    parsed = parser.parse(
        chat_id=4,
        message_id=4,
        posted_at=NOW,
        text=text,
    )
    assert parsed.cargo == "grain"
    assert parsed.urgency == "urgent"
    assert parsed.valid_until is not None
    assert parsed.valid_until > NOW
    assert "grain" in parsed.tags
    assert "urgent" in parsed.metadata["urgency_matches"]


def test_parser_splits_multi_segment_message() -> None:
    parser = MessageParser()
    text = (
        "1) Tashkent -> Moscow, tent 20 tons, +998901111111\n"
        "2) Samarkand -> Kazan, ref 15t, завтра, +998902222222"
    )
    parsed = parser.parse(
        chat_id=5,
        message_id=5,
        posted_at=NOW,
        text=text,
    )
    assert parsed.metadata["multi_listing"] is True
    assert parsed.metadata["segment_count"] == 2
    segments = parsed.metadata["segments"]
    assert len(segments) == 2
    assert all(segment["confidence"] > 0 for segment in segments)
    assert segments[0]["route_from"] == "Tashkent"
    assert segments[1]["route_from"] == "Samarkand"
    assert "+998901111111" in segments[0]["contact"]
    assert "+998902222222" in segments[1]["contact"]
    best_segment = max(segments, key=lambda item: item["confidence"])
    assert parsed.route_from == best_segment["route_from"]
    assert parsed.contact == best_segment["contact"]
