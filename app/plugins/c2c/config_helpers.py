"""C2C configuration helpers (card list and rotation)."""

from __future__ import annotations

from typing import TypedDict

from app.config import settings
from app.plugins.c2c.constants import C2C_CARD_ROTATION_REDIS_KEY
from app.utils.cache import cache


class C2cCard(TypedDict):
    label: str
    number: str
    holder: str


def get_card_by_index(card_index: int) -> C2cCard | None:
    """Return configured card by rotation index, or None if out of range."""
    cards = settings.get_c2c_cards()
    if not cards or card_index < 0 or card_index >= len(cards):
        return None
    card = cards[card_index]
    return {
        'label': card['label'],
        'number': card['number'],
        'holder': card['holder'],
    }


async def get_next_card() -> tuple[C2cCard, int]:
    """Return the next card from rotation and its index."""
    cards = settings.get_c2c_cards()
    if not cards:
        raise ValueError('C2C cards are not configured')

    card_count = len(cards)
    rotation_value = await cache.increment(C2C_CARD_ROTATION_REDIS_KEY)
    if rotation_value is None:
        index = 0
    else:
        index = (rotation_value - 1) % card_count

    card = cards[index]
    return (
        {
            'label': card['label'],
            'number': card['number'],
            'holder': card['holder'],
        },
        index,
    )


def format_card_message(card: C2cCard, amount_kopeks: int, guide_text: str, texts) -> str:
    """Build user-facing card transfer instructions."""
    card_number_label = texts.t('C2C_CARD_NUMBER_LABEL', '🔢 <b>Номер карты:</b>')
    holder_label = texts.t('C2C_CARD_HOLDER_LABEL', '👤 <b>Держатель:</b>')
    amount_label = texts.t('C2C_AMOUNT_TO_TRANSFER_LABEL', '💰 <b>Сумма к переводу:</b>')

    holder_line = f'\n{holder_label} {card["holder"]}' if card.get('holder') else ''
    guide = (guide_text or '').strip()
    guide_block = f'\n\n{guide}' if guide else ''
    return (
        f'💳 <b>{card["label"]}</b>\n\n'
        f'{card_number_label} <code>{card["number"]}</code>'
        f'{holder_line}\n\n'
        f'{amount_label} {settings.format_balance(amount_kopeks)}'
        f'{guide_block}'
    )
