"""Integration hooks for balance menu and payment routing."""

from __future__ import annotations

from collections.abc import Callable

from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User


def append_payment_button(
    keyboard: list[list[InlineKeyboardButton]],
    texts,
    build_callback: Callable[[str], str],
) -> bool:
    """Append C2C payment button when enabled."""
    if not settings.is_c2c_enabled():
        return False

    display_name = settings.get_c2c_display_name()
    keyboard.append(
        [
            InlineKeyboardButton(
                text=texts.t('PAYMENT_C2C', display_name),
                callback_data=build_callback('c2c'),
            )
        ]
    )
    return True


async def route_c2c_payment(
    message,
    db_user: User,
    db: AsyncSession,
    amount_kopeks: int,
    state: FSMContext,
) -> None:
    from app.plugins.c2c.handlers.user import process_c2c_payment_amount

    await process_c2c_payment_amount(message, db_user, db, amount_kopeks, state)
