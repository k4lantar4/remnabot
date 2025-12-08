import logging
from aiogram import Dispatcher, types, F, Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.states import PromoCodeStates
from app.database.models import User
from app.keyboards.inline import get_back_keyboard
from app.localization.texts import get_texts
from app.services.promocode_service import PromoCodeService
from app.services.admin_notification_service import AdminNotificationService
from app.utils.decorators import error_handler

logger = logging.getLogger(__name__)


@error_handler
async def show_promocode_menu(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    
    await callback.message.edit_text(
        texts.PROMOCODE_ENTER,
        reply_markup=get_back_keyboard(db_user.language)
    )
    
    await state.set_state(PromoCodeStates.waiting_for_code)
    await callback.answer()


async def activate_promocode_for_registration(
    db: AsyncSession,
    user_id: int,
    code: str,
    bot: Bot = None
) -> dict:
    """
    Activates a promo code for a user during registration.
    Returns the activation result without sending messages.
    """
    promocode_service = PromoCodeService()
    result = await promocode_service.activate_promocode(db, user_id, code)

    if result["success"]:
        logger.info(f"✅ User {user_id} activated promocode {code} during registration")

        # Send admin notification if the bot is available
        if bot:
            try:
                from app.database.crud.user import get_user_by_id
                user = await get_user_by_id(db, user_id)
                if user:
                    notification_service = AdminNotificationService(bot)
                    await notification_service.send_promocode_activation_notification(
                        db,
                        user,
                        result.get("promocode", {"code": code}),
                        result["description"],
                        result.get("balance_before_kopeks"),
                        result.get("balance_after_kopeks"),
                    )
            except Exception as notify_error:
                logger.error(
                    "Failed to send admin notification about promocode %s activation: %s",
                    code,
                    notify_error,
                )

    return result


@error_handler
async def process_promocode(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)

    code = message.text.strip()

    if not code:
        await message.answer(
            texts.t(
                "PROMOCODE_EMPTY_INPUT",
                "❌ Please enter a valid promo code",
            ),
            reply_markup=get_back_keyboard(db_user.language)
        )
        return

    result = await activate_promocode_for_registration(db, db_user.id, code, message.bot)

    if result["success"]:
        await message.answer(
            texts.PROMOCODE_SUCCESS.format(description=result["description"]),
            reply_markup=get_back_keyboard(db_user.language)
        )
    else:
        error_messages = {
            "not_found": texts.PROMOCODE_INVALID,
            "expired": texts.PROMOCODE_EXPIRED,
            "used": texts.PROMOCODE_USED,
            "already_used_by_user": texts.PROMOCODE_USED,
            "server_error": texts.ERROR
        }

        error_text = error_messages.get(result["error"], texts.PROMOCODE_INVALID)
        await message.answer(
            error_text,
            reply_markup=get_back_keyboard(db_user.language)
        )

    await state.clear()


def register_handlers(dp: Dispatcher):
    
    dp.callback_query.register(
        show_promocode_menu,
        F.data == "menu_promocode"
    )
    
    dp.message.register(
        process_promocode,
        PromoCodeStates.waiting_for_code
    )