from __future__ import annotations

from typing import Any

from aiogram.types import InlineKeyboardButton

from app.utils.remnawave_panel_identity import MAX_PURCHASE_NOTE_LEN


def sanitize_purchase_note(value: str | None) -> str | None:
    note = (value or '').strip()
    if not note:
        return None
    return note[:MAX_PURCHASE_NOTE_LEN]


def checkout_partner_options(user: Any, state_data: dict) -> dict:
    if not getattr(user, 'is_partner', False):
        return {'purchase_note': None, 'use_brand_prefix': False, 'has_brand_prefix': False}
    if not hasattr(user, 'panel_brand_prefix'):
        return {'purchase_note': None, 'use_brand_prefix': False, 'has_brand_prefix': False}
    has_brand = bool((getattr(user, 'panel_brand_prefix', None) or '').strip())
    use_brand = state_data.get('use_brand_prefix')
    if use_brand is None:
        use_brand = has_brand
    return {
        'purchase_note': sanitize_purchase_note(state_data.get('purchase_note')),
        'use_brand_prefix': bool(use_brand) if has_brand else False,
        'has_brand_prefix': has_brand,
    }


def extend_confirm_keyboard(
    buttons: list,
    user: Any,
    tariff_id: int,
    period: int,
    texts,
    state_data: dict | None = None,
) -> list:
    if not getattr(user, 'is_partner', False) or not hasattr(user, 'panel_brand_prefix'):
        return buttons
    opts = checkout_partner_options(user, state_data or {})
    extra = [
        [
            InlineKeyboardButton(
                text=texts.t('PARTNER_PURCHASE_NOTE_BTN', '📝'),
                callback_data=f'pnote:{tariff_id}:{period}',
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t(
                    'PARTNER_BRAND_TOGGLE_ON' if opts['use_brand_prefix'] else 'PARTNER_BRAND_TOGGLE_OFF',
                    '🏷',
                ),
                callback_data=f'pbrand:{tariff_id}:{period}',
            )
        ],
    ]
    return buttons[:-1] + extra + buttons[-1:]


async def apply_partner_checkout_from_state(db, user, subscription, state_data: dict) -> None:
    if subscription is None or not getattr(user, 'is_partner', False):
        return
    if not hasattr(subscription, 'purchase_note'):
        return
    opts = checkout_partner_options(user, state_data)
    subscription.purchase_note = opts['purchase_note']
    await db.commit()
    if opts['use_brand_prefix'] is False:
        return
    # prefix already on user; nothing else if validate would fail
