"""Inline keyboards for C2C admin review."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import settings
from app.localization.texts import get_texts
from app.plugins.c2c.constants import (
    C2C_CALLBACK_ADMIN_INBOX,
    C2C_CALLBACK_APPROVE_PREFIX,
    C2C_CALLBACK_CUSTOM_AMOUNT_PREFIX,
    C2C_CALLBACK_INBOX_PREFIX,
    C2C_CALLBACK_REJECT_PREFIX,
    C2C_CALLBACK_REJECT_REASON_PREFIX,
    C2C_CALLBACK_RESTORE_REVIEW_PREFIX,
)
from app.plugins.c2c.reject_reasons import get_admin_reject_button_label, get_reject_reason_codes


def _admin_texts(language: str | None = None):
    lang = language or (settings.DEFAULT_LANGUAGE if isinstance(settings.DEFAULT_LANGUAGE, str) else 'fa')
    return get_texts(lang)


def get_c2c_admin_review_keyboard(
    receipt_id: int,
    requested_amount_display: str,
    *,
    language: str | None = None,
    include_inbox_back: bool = False,
) -> InlineKeyboardMarkup:
    texts = _admin_texts(language)
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=texts.t(
                    'C2C_ADMIN_REVIEW_APPROVE',
                    '✅ Approve ({amount})',
                ).format(amount=requested_amount_display),
                callback_data=f'{C2C_CALLBACK_APPROVE_PREFIX}{receipt_id}',
            ),
        ],
        [
            InlineKeyboardButton(
                text=texts.t('C2C_ADMIN_REVIEW_CUSTOM', '💰 Custom amount'),
                callback_data=f'{C2C_CALLBACK_CUSTOM_AMOUNT_PREFIX}{receipt_id}',
            ),
        ],
        [
            InlineKeyboardButton(
                text=texts.t('C2C_ADMIN_REVIEW_REJECT', '❌ Reject'),
                callback_data=f'{C2C_CALLBACK_REJECT_PREFIX}{receipt_id}',
            ),
        ],
    ]
    if include_inbox_back:
        rows.append(
            [
                InlineKeyboardButton(
                    text=texts.t('C2C_ADMIN_INBOX_BACK', '📥 صندوق ورودی'),
                    callback_data=C2C_CALLBACK_ADMIN_INBOX,
                ),
            ],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_c2c_reject_reason_keyboard(
    receipt_id: int,
    *,
    language: str | None = None,
) -> InlineKeyboardMarkup:
    texts = _admin_texts(language)
    rows: list[list[InlineKeyboardButton]] = []
    for code in get_reject_reason_codes():
        rows.append(
            [
                InlineKeyboardButton(
                    text=get_admin_reject_button_label(code, texts),
                    callback_data=f'{C2C_CALLBACK_REJECT_REASON_PREFIX}{receipt_id}:{code}',
                ),
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text=texts.t('C2C_ADMIN_REJECT_CANCEL', '↩️ Cancel'),
                callback_data=f'{C2C_CALLBACK_RESTORE_REVIEW_PREFIX}{receipt_id}',
            ),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_c2c_inbox_list_keyboard(
    receipts: list,
    *,
    page: int,
    total_count: int,
    page_size: int,
    language: str | None = None,
) -> InlineKeyboardMarkup:
    texts = _admin_texts(language)
    rows: list[list[InlineKeyboardButton]] = []
    for receipt in receipts:
        user = getattr(receipt, 'user', None)
        user_label = '—'
        if user is not None:
            user_label = user.full_name or user.username or f'ID {user.id}'
        amount_display = settings.format_balance(receipt.amount_kopeks)
        rows.append(
            [
                InlineKeyboardButton(
                    text=texts.t(
                        'C2C_ADMIN_INBOX_ROW',
                        '#{id} — {user} — {amount}',
                    ).format(id=receipt.id, user=user_label, amount=amount_display),
                    callback_data=f'{C2C_CALLBACK_INBOX_PREFIX}{receipt.id}',
                ),
            ]
        )

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text='◀️',
                callback_data=f'{C2C_CALLBACK_INBOX_PREFIX}page:{page - 1}',
            )
        )
    if (page + 1) * page_size < total_count:
        nav_row.append(
            InlineKeyboardButton(
                text='▶️',
                callback_data=f'{C2C_CALLBACK_INBOX_PREFIX}page:{page + 1}',
            )
        )
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text=texts.BACK, callback_data='admin_panel')])
    return InlineKeyboardMarkup(inline_keyboard=rows)
