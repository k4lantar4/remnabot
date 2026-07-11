"""Serialize Telegram MessageEntity lists for broadcast/pinned delivery."""

from __future__ import annotations

import json
from dataclasses import dataclass

from aiogram.types import Message, MessageEntity


@dataclass(slots=True)
class ForwardableDraft:
    """Plain text/caption + optional entities and media from an admin message."""

    text: str
    entities_json: str | None = None
    media_type: str | None = None
    media_file_id: str | None = None


def serialize_entities(entities: list[MessageEntity] | None) -> str | None:
    if not entities:
        return None
    payload = [entity.model_dump(mode='json', exclude_none=True) for entity in entities]
    return json.dumps(payload, ensure_ascii=False)


def deserialize_entities(payload: str | None) -> list[MessageEntity] | None:
    if not payload:
        return None
    raw = json.loads(payload)
    if not raw:
        return None
    return [MessageEntity.model_validate(item) for item in raw]


def extract_forwardable_content(message: Message) -> ForwardableDraft:
    """Extract sendable text/caption, entities, and inline media from a Telegram message."""
    media_type: str | None = None
    media_file_id: str | None = None

    if message.photo:
        media_type = 'photo'
        media_file_id = message.photo[-1].file_id
        text = message.caption or ''
        entities_json = serialize_entities(message.caption_entities)
    elif message.video:
        media_type = 'video'
        media_file_id = message.video.file_id
        text = message.caption or ''
        entities_json = serialize_entities(message.caption_entities)
    elif message.document:
        media_type = 'document'
        media_file_id = message.document.file_id
        text = message.caption or ''
        entities_json = serialize_entities(message.caption_entities)
    else:
        text = message.text or message.html_text or ''
        entities_json = serialize_entities(message.entities)

    return ForwardableDraft(
        text=text,
        entities_json=entities_json,
        media_type=media_type,
        media_file_id=media_file_id,
    )


def message_send_kwargs(*, text: str, entities_json: str | None) -> dict:
    """Build kwargs for bot.send_message — entities win over HTML parse_mode."""
    entities = deserialize_entities(entities_json)
    if entities:
        return {'text': text, 'entities': entities}
    return {'text': text, 'parse_mode': 'HTML'}


def caption_send_kwargs(*, caption: str, entities_json: str | None) -> dict:
    """Build kwargs for media send_* caption fields."""
    entities = deserialize_entities(entities_json)
    if entities:
        return {'caption': caption, 'caption_entities': entities}
    if caption:
        return {'caption': caption, 'parse_mode': 'HTML'}
    return {}
