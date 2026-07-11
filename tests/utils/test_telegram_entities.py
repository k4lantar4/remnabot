"""Round-trip tests for Telegram entity serialization."""

from __future__ import annotations

from aiogram.types import MessageEntity

from app.utils.telegram_entities import (
    deserialize_entities,
    serialize_entities,
)


def test_serialize_custom_emoji_entity_round_trip() -> None:
    entity = MessageEntity(type='custom_emoji', offset=0, length=2, custom_emoji_id='543210987654321')
    payload = serialize_entities([entity])
    assert payload is not None

    restored = deserialize_entities(payload)
    assert restored is not None
    assert len(restored) == 1
    assert restored[0].type == 'custom_emoji'
    assert restored[0].custom_emoji_id == '543210987654321'
    assert restored[0].offset == 0
    assert restored[0].length == 2
