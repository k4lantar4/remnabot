"""Inline keyboards for C2C admin review."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.plugins.c2c.constants import C2C_CALLBACK_APPROVE_PREFIX, C2C_CALLBACK_REJECT_PREFIX


def get_c2c_admin_review_keyboard(receipt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='✅ Approve', callback_data=f'{C2C_CALLBACK_APPROVE_PREFIX}{receipt_id}'),
                InlineKeyboardButton(text='❌ Reject', callback_data=f'{C2C_CALLBACK_REJECT_PREFIX}{receipt_id}'),
            ],
        ]
    )
