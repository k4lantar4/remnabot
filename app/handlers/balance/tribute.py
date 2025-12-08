import logging
from aiogram import types

from app.config import settings
from app.database.models import User
from app.keyboards.inline import get_back_keyboard
from app.localization.texts import get_texts
from app.utils.decorators import error_handler

logger = logging.getLogger(__name__)


@error_handler
async def start_tribute_payment(
    callback: types.CallbackQuery,
    db_user: User,
):
    texts = get_texts(db_user.language)

    if not settings.TRIBUTE_ENABLED:
        await callback.answer(texts.t("CARD_PAYMENT_UNAVAILABLE", "❌ Card payment temporarily unavailable"), show_alert=True)
        return

    try:
        await callback.answer("❌ Tribute payments are not available in this build", show_alert=True)
    except Exception as e:
        logger.error(f"Error creating Tribute payment: {e}")
        await callback.answer(texts.t("PAYMENT_CREATE_ERROR_SHORT", "❌ Payment creation error"), show_alert=True)

    await callback.answer()
