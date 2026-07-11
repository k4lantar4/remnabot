"""Round-trip tests for Telegram entity serialization."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from aiogram.types import MessageEntity

from app.utils.telegram_entities import (
    deserialize_entities,
    forward_copy_ref,
    is_channel_forward,
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


def test_is_channel_forward_legacy_forward_from_chat() -> None:
    message = MagicMock()
    message.forward_origin = None
    message.forward_from_chat = SimpleNamespace(type='channel', title='Test Channel')
    assert is_channel_forward(message) is True


def test_forward_copy_ref_builds_admin_message_source() -> None:
    message = MagicMock()
    message.forward_origin = None
    message.forward_from_chat = SimpleNamespace(type='channel', title='MoonVPN News')
    message.chat = SimpleNamespace(id=9001)
    message.message_id = 42

    ref = forward_copy_ref(message)
    assert ref is not None
    assert ref.from_chat_id == 9001
    assert ref.message_id == 42
    assert ref.channel_label == 'MoonVPN News'


def test_forward_copy_ref_none_for_plain_text() -> None:
    message = MagicMock()
    message.forward_origin = None
    message.forward_from_chat = None
    assert forward_copy_ref(message) is None
