"""Bot flow for partner (agency) application."""

from __future__ import annotations

import structlog
from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import PartnerStatus, User
from app.keyboards.inline import get_referral_keyboard
from app.localization.texts import get_texts
from app.services.partner_application_service import partner_application_service
from app.states import PartnerApplicationStates
from app.utils.photo_message import edit_or_answer_photo


logger = structlog.get_logger(__name__)

_MIN_DESCRIPTION_LEN = 10


async def _notify_admins_partner_application(user: User, application_data: dict) -> None:
    try:
        from app.bot_factory import create_bot
        from app.services.admin_notification_service import AdminNotificationService

        if not getattr(settings, 'ADMIN_NOTIFICATIONS_ENABLED', False) or not settings.BOT_TOKEN:
            return

        bot = create_bot()
        try:
            notification_service = AdminNotificationService(bot)
            await notification_service.send_partner_application_notification(
                user=user,
                application_data=application_data,
            )
        finally:
            await bot.session.close()
    except Exception as e:
        logger.error('Failed to send admin notification for partner application', error=e)


def _partner_apply_cancel_keyboard(language: str) -> types.InlineKeyboardMarkup:
    texts = get_texts(language)
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t('PARTNER_APPLY_CANCEL_BTN', '❌ Отмена'),
                    callback_data='partner_apply_cancel',
                )
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data='menu_referrals')],
        ]
    )


async def start_partner_application(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)

    if db_user.partner_status == PartnerStatus.APPROVED.value:
        await callback.answer(
            texts.t('PARTNER_APPLY_ERROR', '❌ {error}').format(
                error=texts.t('PARTNER_ONLY', 'Только для партнёров'),
            ),
            show_alert=True,
        )
        return

    if db_user.partner_status == PartnerStatus.PENDING.value:
        await callback.answer(
            texts.t('PARTNER_APPLY_PENDING_HINT', '⏳ Заявка на рассмотрении'),
            show_alert=True,
        )
        return

    await callback.answer()
    await state.set_state(PartnerApplicationStates.waiting_description)
    await edit_or_answer_photo(
        callback,
        texts.t('PARTNER_APPLY_INTRO', '🤝 <b>Заявка на партнёрство</b>'),
        _partner_apply_cancel_keyboard(db_user.language),
    )


async def cancel_partner_application(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    from app.handlers.referral import show_referral_info

    await state.clear()
    texts = get_texts(db_user.language)
    await callback.answer(texts.t('CANCELLED', 'Отменено'))
    await show_referral_info(callback, db_user, db)


async def process_partner_application_description(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    raw = (message.text or '').strip()

    if raw.lower() in ('/cancel', 'cancel', 'انصراف'):
        await state.clear()
        await message.answer(texts.t('CANCELLED', 'Отменено'))
        return

    if len(raw) < _MIN_DESCRIPTION_LEN:
        await message.answer(
            texts.t('PARTNER_APPLY_TOO_SHORT', '❌ Слишком коротко'),
            reply_markup=_partner_apply_cancel_keyboard(db_user.language),
        )
        return

    telegram_channel = raw if raw.startswith('@') else None
    application_data = {
        'description': raw,
        'telegram_channel': telegram_channel,
        'company_name': None,
        'website_url': None,
        'expected_monthly_referrals': None,
        'desired_commission_percent': None,
    }

    application, error = await partner_application_service.submit_application(
        db,
        user_id=db_user.id,
        description=raw,
        telegram_channel=telegram_channel,
    )

    await state.clear()

    if not application:
        await message.answer(
            texts.t('PARTNER_APPLY_ERROR', '❌ {error}').format(error=error),
            reply_markup=get_referral_keyboard(
                db_user.language,
                is_partner=db_user.is_partner,
                partner_status=db_user.partner_status,
            ),
        )
        return

    db_user.partner_status = PartnerStatus.PENDING.value
    await _notify_admins_partner_application(db_user, application_data)

    await message.answer(
        texts.t('PARTNER_APPLY_SUCCESS', '✅ Заявка отправлена'),
        reply_markup=get_referral_keyboard(
            db_user.language,
            is_partner=False,
            partner_status=PartnerStatus.PENDING.value,
        ),
    )


def register_partner_application_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(start_partner_application, F.data == 'partner_apply_start')
    dp.callback_query.register(cancel_partner_application, F.data == 'partner_apply_cancel')
    dp.message.register(
        process_partner_application_description,
        PartnerApplicationStates.waiting_description,
        F.text,
    )
