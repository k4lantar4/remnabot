import asyncio
import html
import json
from datetime import UTC, datetime, timedelta

import structlog
from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.referral import (
    get_referral_statistics,
    get_top_referrers_by_period,
)
from app.database.crud.user import get_user_by_id, get_user_by_telegram_id
from app.database.models import ReferralEarning, User, WithdrawalRequest, WithdrawalRequestStatus
from app.localization.texts import get_texts
from app.services.referral_withdrawal_service import referral_withdrawal_service
from app.states import AdminStates
from app.utils.decorators import admin_required, error_handler


logger = structlog.get_logger(__name__)


def _ref_notifications_status(texts, enabled: bool) -> str:
    if enabled:
        return texts.t('ADMIN_REFERRAL_NOTIF_ON', '✅ Включены')
    return texts.t('ADMIN_REFERRAL_NOTIF_OFF', '❌ Отключены')


def _ref_period_display(period: str, texts) -> str:
    keys = {
        'today': ('ADMIN_REFERRAL_PERIOD_TODAY', 'сегодня'),
        'yesterday': ('ADMIN_REFERRAL_PERIOD_YESTERDAY', 'вчера'),
        'week': ('ADMIN_REFERRAL_PERIOD_7D', '7 дней'),
        'month': ('ADMIN_REFERRAL_PERIOD_30D', '30 дней'),
        'uploaded_file': ('ADMIN_REFERRAL_PERIOD_UPLOADED', 'загруженный файл'),
    }
    key, fb = keys.get(period, keys['today'])
    return texts.t(key, fb)


def _ref_withdrawal_status_map(texts) -> dict:
    return {
        WithdrawalRequestStatus.PENDING.value: texts.t('ADMIN_REFERRAL_WD_STATUS_PENDING', '⏳ Ожидает'),
        WithdrawalRequestStatus.APPROVED.value: texts.t('ADMIN_REFERRAL_WD_STATUS_APPROVED', '✅ Одобрена'),
        WithdrawalRequestStatus.REJECTED.value: texts.t('ADMIN_REFERRAL_WD_STATUS_REJECTED', '❌ Отклонена'),
        WithdrawalRequestStatus.COMPLETED.value: texts.t('ADMIN_REFERRAL_WD_STATUS_COMPLETED', '✅ Выполнена'),
        WithdrawalRequestStatus.CANCELLED.value: texts.t('ADMIN_REFERRAL_WD_STATUS_CANCELLED', '🚫 Отменена'),
    }


def _ref_lost_status(lost, texts) -> str:
    if not lost.registered:
        return texts.t('ADMIN_REFERRAL_DIAG_STATUS_NOT_DB', '⚠️ Не в БД')
    if not lost.has_referrer:
        return texts.t('ADMIN_REFERRAL_DIAG_STATUS_NO_REF', '❌ Без реферера')
    return texts.t('ADMIN_REFERRAL_DIAG_STATUS_OTHER_REF', '⚡ Другой реферер (ID{id})').format(
        id=lost.current_referrer_id
    )


def _ref_append_lost_referrals(text: str, lost_referrals: list, texts, time_fmt: str) -> str:
    if not lost_referrals:
        return text + texts.t('ADMIN_REFERRAL_DIAG_ALL_OK', '\n✅ <b>Все рефералы засчитаны!</b>\n')
    text += texts.t(
        'ADMIN_REFERRAL_DIAG_LOST_HEADER',
        '\n<b>❌ Потерянные рефералы:</b>\n<i>(пришли по ссылке, но реферер не засчитался)</i>\n\n',
    )
    for i, lost in enumerate(lost_referrals[:15], 1):
        status = _ref_lost_status(lost, texts)
        if lost.username:
            user_name = f'@{html.escape(lost.username)}'
        elif lost.full_name:
            user_name = html.escape(lost.full_name)
        else:
            user_name = f'ID{lost.telegram_id}'
        referrer_info = ''
        if lost.expected_referrer_name:
            referrer_info = f' → {html.escape(lost.expected_referrer_name)}'
        elif lost.expected_referrer_id:
            referrer_info = f' → ID{lost.expected_referrer_id}'
        time_str = lost.click_time.strftime(time_fmt)
        text += f'{i}. {user_name} — {status}\n'
        text += f'   <code>{html.escape(lost.referral_code)}</code>{referrer_info} ({time_str})\n'
    if len(lost_referrals) > 15:
        text += texts.t('ADMIN_REFERRAL_DIAG_MORE', '\n<i>... и ещё {count}</i>\n').format(
            count=len(lost_referrals) - 15
        )
    return text


@admin_required
@error_handler
async def show_referral_statistics(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    try:
        stats = await get_referral_statistics(db)

        avg_per_referrer = 0
        if stats.get('active_referrers', 0) > 0:
            avg_per_referrer = stats.get('total_paid_kopeks', 0) / stats['active_referrers']

        current_time = datetime.now(UTC).strftime('%H:%M:%S')

        text = (
            texts.t('ADMIN_REFERRAL_STATS_TITLE', '🤝 <b>Реферальная статистика</b>')
            + '\n\n'
            + texts.t(
                'ADMIN_REFERRAL_STATS_GENERAL',
                '<b>Общие показатели:</b>\n- Пользователей с рефералами: {users_with}\n- Активных рефереров: {active_referrers}\n- Выплачено всего: {total_paid}',
            ).format(
                users_with=stats.get('users_with_referrals', 0),
                active_referrers=stats.get('active_referrers', 0),
                total_paid=settings.format_price(stats.get('total_paid_kopeks', 0)),
            )
            + '\n\n'
            + texts.t(
                'ADMIN_REFERRAL_STATS_PERIOD',
                '<b>За период:</b>\n- Сегодня: {today}\n- За неделю: {week}\n- За месяц: {month}',
            ).format(
                today=settings.format_price(stats.get('today_earnings_kopeks', 0)),
                week=settings.format_price(stats.get('week_earnings_kopeks', 0)),
                month=settings.format_price(stats.get('month_earnings_kopeks', 0)),
            )
            + '\n\n'
            + texts.t(
                'ADMIN_REFERRAL_STATS_AVG',
                '<b>Средние показатели:</b>\n- На одного реферера: {avg}',
            ).format(avg=settings.format_price(int(avg_per_referrer)))
            + '\n\n'
            + texts.t('ADMIN_REFERRAL_STATS_TOP5', '<b>Топ-5 рефереров:</b>')
            + '\n'
        )

        top_referrers = stats.get('top_referrers', [])
        if top_referrers:
            for i, referrer in enumerate(top_referrers[:5], 1):
                earned = referrer.get('total_earned_kopeks', 0)
                count = referrer.get('referrals_count', 0)
                user_id = referrer.get('user_id', 'N/A')

                if count > 0:
                    text += texts.t(
                        'ADMIN_REFERRAL_STATS_TOP_LINE',
                        '{i}. ID {user_id}: {earned} ({count} реф.)\n',
                    ).format(
                        i=i,
                        user_id=user_id,
                        earned=settings.format_price(earned),
                        count=count,
                    )
                else:
                    logger.warning('Реферер имеет рефералов, но есть в топе', user_id=user_id, count=count)
        else:
            text += texts.t('ADMIN_REFERRAL_NO_DATA', 'Нет данных') + '\n'

        text += (
            '\n\n'
            + texts.t(
                'ADMIN_REFERRAL_STATS_SETTINGS',
                '<b>Настройки реферальной системы:</b>\n- Минимальное пополнение: {min_topup}\n- Бонус за первое пополнение: {first_bonus}\n- Бонус пригласившему: {inviter_bonus}\n- Комиссия с покупок: {commission}%\n- Уведомления: {notifications}',
            ).format(
                min_topup=settings.format_price(settings.REFERRAL_MINIMUM_TOPUP_KOPEKS),
                first_bonus=settings.format_price(settings.REFERRAL_FIRST_TOPUP_BONUS_KOPEKS),
                inviter_bonus=settings.format_price(settings.REFERRAL_INVITER_BONUS_KOPEKS),
                commission=settings.REFERRAL_COMMISSION_PERCENT,
                notifications=_ref_notifications_status(texts, settings.REFERRAL_NOTIFICATIONS_ENABLED),
            )
            + '\n\n'
            + texts.t('ADMIN_REFERRAL_STATS_UPDATED', '<i>🕐 Обновлено: {time}</i>').format(time=current_time)
        )

        keyboard_rows = [
            [types.InlineKeyboardButton(text=texts.t('ADMIN_REFERRAL_BTN_REFRESH', '🔄 Обновить'), callback_data='admin_referrals')],
            [types.InlineKeyboardButton(text=texts.t('ADMIN_REFERRAL_BTN_TOP', '👥 Топ рефереров'), callback_data='admin_referrals_top')],
            [types.InlineKeyboardButton(text=texts.t('ADMIN_REFERRAL_BTN_DIAG', '🔍 Диагностика логов'), callback_data='admin_referral_diagnostics')],
        ]

        # Кнопка заявок на вывод (если функция включена)
        if settings.is_referral_withdrawal_enabled():
            keyboard_rows.append(
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_BTN_WITHDRAWALS', '💸 Заявки на вывод'),
                        callback_data='admin_withdrawal_requests',
                    )
                ]
            )

        keyboard_rows.extend(
            [
                [types.InlineKeyboardButton(text=texts.t('ADMIN_REFERRAL_BTN_SETTINGS', '⚙️ Настройки'), callback_data='admin_referrals_settings')],
                [types.InlineKeyboardButton(text=texts.t('ADMIN_REFERRAL_BTN_BACK_PANEL', '⬅️ Назад'), callback_data='admin_panel')],
            ]
        )

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer(texts.t('ADMIN_REFERRAL_UPDATED', 'Обновлено'))
        except Exception as edit_error:
            if 'message is not modified' in str(edit_error):
                await callback.answer(texts.t('ADMIN_REFERRAL_DATA_CURRENT', 'Данные актуальны'))
            else:
                logger.error('Ошибка редактирования сообщения', edit_error=edit_error)
                await callback.answer(texts.t('ADMIN_REFERRAL_UPDATE_ERROR', 'Ошибка обновления'))

    except Exception as e:
        logger.error('Ошибка в show_referral_statistics', error=e, exc_info=True)

        current_time = datetime.now(UTC).strftime('%H:%M:%S')
        text = (
            texts.t('ADMIN_REFERRAL_STATS_TITLE', '🤝 <b>Реферальная статистика</b>')
            + '\n\n'
            + texts.t('ADMIN_REFERRAL_STATS_ERROR', '❌ <b>Ошибка загрузки данных</b>')
            + '\n\n'
            + texts.t(
                'ADMIN_REFERRAL_STATS_ERROR_SETTINGS',
                '<b>Текущие настройки:</b>\n- Минимальное пополнение: {min_topup}\n- Бонус за первое пополнение: {first_bonus}\n- Бонус пригласившему: {inviter_bonus}\n- Комиссия с покупок: {commission}%',
            ).format(
                min_topup=settings.format_price(settings.REFERRAL_MINIMUM_TOPUP_KOPEKS),
                first_bonus=settings.format_price(settings.REFERRAL_FIRST_TOPUP_BONUS_KOPEKS),
                inviter_bonus=settings.format_price(settings.REFERRAL_INVITER_BONUS_KOPEKS),
                commission=settings.REFERRAL_COMMISSION_PERCENT,
            )
            + '\n\n'
            + texts.t('ADMIN_REFERRAL_STATS_ERROR_TIME', '<i>🕐 Время: {time}</i>').format(time=current_time)
        )

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t('ADMIN_REFERRAL_BTN_RETRY', '🔄 Повторить'), callback_data='admin_referrals')],
                [types.InlineKeyboardButton(text=texts.t('ADMIN_REFERRAL_BTN_BACK_PANEL', '⬅️ Назад'), callback_data='admin_panel')],
            ]
        )

        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except:
            pass
        await callback.answer(texts.t('ADMIN_REFERRAL_LOAD_ERROR', 'Произошла ошибка при загрузке статистики'))


def _get_top_keyboard(period: str, sort_by: str, texts) -> types.InlineKeyboardMarkup:
    """Создаёт клавиатуру для выбора периода и сортировки."""
    period_week = (
        texts.t('ADMIN_REFERRAL_PERIOD_WEEK_ON', '✅ Неделя')
        if period == 'week'
        else texts.t('ADMIN_REFERRAL_PERIOD_WEEK', 'Неделя')
    )
    period_month = (
        texts.t('ADMIN_REFERRAL_PERIOD_MONTH_ON', '✅ Месяц')
        if period == 'month'
        else texts.t('ADMIN_REFERRAL_PERIOD_MONTH', 'Месяц')
    )
    sort_earnings = (
        texts.t('ADMIN_REFERRAL_SORT_EARNINGS_ON', '✅ По заработку')
        if sort_by == 'earnings'
        else texts.t('ADMIN_REFERRAL_SORT_EARNINGS', 'По заработку')
    )
    sort_invited = (
        texts.t('ADMIN_REFERRAL_SORT_INVITED_ON', '✅ По приглашённым')
        if sort_by == 'invited'
        else texts.t('ADMIN_REFERRAL_SORT_INVITED', 'По приглашённым')
    )

    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text=period_week, callback_data=f'admin_top_ref:week:{sort_by}'),
                types.InlineKeyboardButton(text=period_month, callback_data=f'admin_top_ref:month:{sort_by}'),
            ],
            [
                types.InlineKeyboardButton(text=sort_earnings, callback_data=f'admin_top_ref:{period}:earnings'),
                types.InlineKeyboardButton(text=sort_invited, callback_data=f'admin_top_ref:{period}:invited'),
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_BTN_REFRESH', '🔄 Обновить'),
                    callback_data=f'admin_top_ref:{period}:{sort_by}',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_BTN_BACK_STATS', '⬅️ К статистике'),
                    callback_data='admin_referrals',
                )
            ],
        ]
    )


@admin_required
@error_handler
async def show_top_referrers(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    """Показывает топ рефереров (по умолчанию: неделя, по заработку)."""
    texts = get_texts(db_user.language)
    await _show_top_referrers_filtered(callback, db, period='week', sort_by='earnings', texts=texts)


@admin_required
@error_handler
async def show_top_referrers_filtered(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    """Обрабатывает выбор периода и сортировки."""
    texts = get_texts(db_user.language)
    # Парсим callback_data: admin_top_ref:period:sort_by
    parts = callback.data.split(':')
    if len(parts) != 3:
        await callback.answer(texts.t('ADMIN_REFERRAL_PARAM_ERROR', 'Ошибка параметров'))
        return

    period = parts[1]  # week или month
    sort_by = parts[2]  # earnings или invited

    if period not in ('week', 'month'):
        period = 'week'
    if sort_by not in ('earnings', 'invited'):
        sort_by = 'earnings'

    await _show_top_referrers_filtered(callback, db, period, sort_by, texts=texts)


async def _show_top_referrers_filtered(callback: types.CallbackQuery, db: AsyncSession, period: str, sort_by: str, *, texts):
    """Внутренняя функция отображения топа с фильтрами."""
    try:
        top_referrers = await get_top_referrers_by_period(db, period=period, sort_by=sort_by)

        period_text = (
            texts.t('ADMIN_REFERRAL_TOP_TITLE_WEEK', 'за неделю')
            if period == 'week'
            else texts.t('ADMIN_REFERRAL_TOP_TITLE_MONTH', 'за месяц')
        )
        sort_text = (
            texts.t('ADMIN_REFERRAL_TOP_SORT_EARNINGS', 'по заработку')
            if sort_by == 'earnings'
            else texts.t('ADMIN_REFERRAL_TOP_SORT_INVITED', 'по приглашённым')
        )

        text = texts.t('ADMIN_REFERRAL_TOP_HEADER', '🏆 <b>Топ рефереров {period}</b>\n').format(period=period_text)
        text += texts.t('ADMIN_REFERRAL_TOP_SORT', '<i>Сортировка: {sort}</i>\n\n').format(sort=sort_text)

        if top_referrers:
            for i, referrer in enumerate(top_referrers[:20], 1):
                earned = referrer.get('earnings_kopeks', 0)
                count = referrer.get('invited_count', 0)
                display_name = referrer.get('display_name', 'N/A')
                username = referrer.get('username', '')
                telegram_id = referrer.get('telegram_id')
                user_email = referrer.get('email', '')
                user_id = referrer.get('user_id', '')
                id_display = telegram_id or user_email or f'#{user_id}' if user_id else 'N/A'

                if username:
                    display_text = f'@{html.escape(username)} (ID{id_display})'
                elif display_name and display_name != f'ID{id_display}':
                    display_text = f'{html.escape(display_name)} (ID{id_display})'
                else:
                    display_text = f'ID{id_display}'

                emoji = ''
                if i == 1:
                    emoji = '🥇 '
                elif i == 2:
                    emoji = '🥈 '
                elif i == 3:
                    emoji = '🥉 '

                # Выделяем основную метрику в зависимости от сортировки
                if sort_by == 'invited':
                    text += f'{emoji}{i}. {display_text}\n'
                    text += texts.t(
                        'ADMIN_REFERRAL_TOP_LINE_INVITED',
                        '   👥 <b>{count} приглашённых</b> | 💰 {earned}\n\n',
                    ).format(count=count, earned=settings.format_price(earned))
                else:
                    text += f'{emoji}{i}. {display_text}\n'
                    text += texts.t(
                        'ADMIN_REFERRAL_TOP_LINE_EARNINGS',
                        '   💰 <b>{earned}</b> | 👥 {count} приглашённых\n\n',
                    ).format(earned=settings.format_price(earned), count=count)
        else:
            text += texts.t('ADMIN_REFERRAL_TOP_NO_DATA', 'Нет данных за выбранный период') + '\n'

        keyboard = _get_top_keyboard(period, sort_by, texts)

        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.answer()
        except Exception as edit_error:
            if 'message is not modified' in str(edit_error):
                await callback.answer(texts.t('ADMIN_REFERRAL_DATA_CURRENT', 'Данные актуальны'))
            else:
                raise

    except Exception as e:
        logger.error('Ошибка в show_top_referrers_filtered', error=e, exc_info=True)
        await callback.answer(texts.t('ADMIN_REFERRAL_TOP_LOAD_ERROR', 'Ошибка загрузки топа рефереров'))


@admin_required
@error_handler
async def show_referral_settings(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    text = (
        texts.t('ADMIN_REFERRAL_SETTINGS_TITLE', '⚙️ <b>Настройки реферальной системы</b>')
        + '\n\n'
        + texts.t(
            'ADMIN_REFERRAL_SETTINGS_BONUSES',
            '<b>Бонусы и награды:</b>\n• Минимальная сумма пополнения для участия: {min_topup}\n• Бонус за первое пополнение реферала: {first_bonus}\n• Бонус пригласившему за первое пополнение: {inviter_bonus}',
        ).format(
            min_topup=settings.format_price(settings.REFERRAL_MINIMUM_TOPUP_KOPEKS),
            first_bonus=settings.format_price(settings.REFERRAL_FIRST_TOPUP_BONUS_KOPEKS),
            inviter_bonus=settings.format_price(settings.REFERRAL_INVITER_BONUS_KOPEKS),
        )
        + '\n\n'
        + texts.t(
            'ADMIN_REFERRAL_SETTINGS_COMMISSION',
            '<b>Комиссионные:</b>\n• Процент с каждой покупки реферала: {commission}%',
        ).format(commission=settings.REFERRAL_COMMISSION_PERCENT)
        + '\n\n'
        + texts.t(
            'ADMIN_REFERRAL_SETTINGS_NOTIF',
            '<b>Уведомления:</b>\n• Статус: {status}\n• Попытки отправки: {retries}',
        ).format(
            status=_ref_notifications_status(texts, settings.REFERRAL_NOTIFICATIONS_ENABLED),
            retries=getattr(settings, 'REFERRAL_NOTIFICATION_RETRY_ATTEMPTS', 3),
        )
        + '\n\n'
        + texts.t(
            'ADMIN_REFERRAL_SETTINGS_ENV_HINT',
            '<i>💡 Для изменения настроек отредактируйте файл .env и перезапустите бота</i>',
        )
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_BTN_BACK_STATS', '⬅️ К статистике'),
                    callback_data='admin_referrals',
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@admin_required
@error_handler
async def show_pending_withdrawal_requests(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    """Показывает список ожидающих заявок на вывод."""
    texts = get_texts(db_user.language)
    requests = await referral_withdrawal_service.get_pending_requests(db)

    if not requests:
        text = texts.t(
            'ADMIN_REFERRAL_WITHDRAWALS_EMPTY',
            '📋 <b>Заявки на вывод</b>\n\nНет ожидающих заявок.',
        )

        keyboard_rows = []
        # Кнопка тестового начисления (только в тестовом режиме)
        if settings.REFERRAL_WITHDRAWAL_TEST_MODE:
            keyboard_rows.append(
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_TEST_EARNING_BTN', '🧪 Тестовое начисление'),
                        callback_data='admin_test_referral_earning',
                    )
                ]
            )
        keyboard_rows.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_BTN_BACK', '⬅️ Назад'),
                    callback_data='admin_referrals',
                )
            ]
        )

        await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows))
        await callback.answer()
        return

    text = texts.t('ADMIN_REFERRAL_WITHDRAWALS_LIST', '📋 <b>Заявки на вывод ({count})</b>\n\n').format(
        count=len(requests)
    )

    for req in requests[:10]:
        user = await get_user_by_id(db, req.user_id)
        user_name = html.escape(user.full_name) if user and user.full_name else texts.t(
            'ADMIN_REFERRAL_UNKNOWN_USER', 'Неизвестно'
        )
        user_tg_id = user.telegram_id if user else 'N/A'

        risk_emoji = (
            '🟢' if req.risk_score < 30 else '🟡' if req.risk_score < 50 else '🟠' if req.risk_score < 70 else '🔴'
        )

        text += f'<b>#{req.id}</b> — {user_name} (ID{user_tg_id})\n'
        text += texts.t(
            'ADMIN_REFERRAL_RISK_LINE',
            '💰 {amount}₽ | {emoji} Риск: {score}/100',
        ).format(amount=f'{req.amount_kopeks / 100:.0f}', emoji=risk_emoji, score=req.risk_score) + '\n'
        text += f'📅 {req.created_at.strftime("%d.%m.%Y %H:%M")}\n\n'

    keyboard_rows = []
    for req in requests[:5]:
        keyboard_rows.append(
            [
                types.InlineKeyboardButton(
                    text=f'#{req.id} — {req.amount_kopeks / 100:.0f}₽', callback_data=f'admin_withdrawal_view_{req.id}'
                )
            ]
        )

    # Кнопка тестового начисления (только в тестовом режиме)
    if settings.REFERRAL_WITHDRAWAL_TEST_MODE:
        keyboard_rows.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_TEST_EARNING_BTN', '🧪 Тестовое начисление'),
                    callback_data='admin_test_referral_earning',
                )
            ]
        )

    keyboard_rows.append(
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_REFERRAL_BTN_BACK', '⬅️ Назад'),
                callback_data='admin_referrals',
            )
        ]
    )

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows))
    await callback.answer()


@admin_required
@error_handler
async def view_withdrawal_request(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    """Показывает детали заявки на вывод."""
    texts = get_texts(db_user.language)
    request_id = int(callback.data.split('_')[-1])

    result = await db.execute(select(WithdrawalRequest).where(WithdrawalRequest.id == request_id))
    request = result.scalar_one_or_none()

    if not request:
        await callback.answer(texts.t('ADMIN_REFERRAL_WD_NOT_FOUND', 'Заявка не найдена'), show_alert=True)
        return

    user = await get_user_by_id(db, request.user_id)
    user_name = html.escape(user.full_name) if user and user.full_name else texts.t(
        'ADMIN_REFERRAL_UNKNOWN_USER', 'Неизвестно'
    )
    user_tg_id = (user.telegram_id or user.email or f'#{user.id}') if user else 'N/A'

    analysis = json.loads(request.risk_analysis) if request.risk_analysis else {}

    status_text = _ref_withdrawal_status_map(texts).get(request.status, request.status)

    text = texts.t(
        'ADMIN_REFERRAL_WD_DETAIL',
        '📋 <b>Заявка #{id}</b>\n\n👤 Пользователь: {user}\n🆔 ID: <code>{tg_id}</code>\n💰 Сумма: <b>{amount}₽</b>\n📊 Статус: {status}\n\n💳 <b>Реквизиты:</b>\n<code>{details}</code>\n\n📅 Создана: {created}\n\n{analysis}',
    ).format(
        id=request.id,
        user=user_name,
        tg_id=user_tg_id,
        amount=f'{request.amount_kopeks / 100:.0f}',
        status=status_text,
        details=html.escape(request.payment_details or ''),
        created=request.created_at.strftime('%d.%m.%Y %H:%M'),
        analysis=referral_withdrawal_service.format_analysis_for_admin(analysis),
    )

    keyboard = []

    if request.status == WithdrawalRequestStatus.PENDING.value:
        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_WD_APPROVE_BTN', '✅ Одобрить'),
                    callback_data=f'admin_withdrawal_approve_{request.id}',
                ),
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_WD_REJECT_BTN', '❌ Отклонить'),
                    callback_data=f'admin_withdrawal_reject_{request.id}',
                ),
            ]
        )

    if request.status == WithdrawalRequestStatus.APPROVED.value:
        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_WD_COMPLETE_BTN', '✅ Деньги переведены'),
                    callback_data=f'admin_withdrawal_complete_{request.id}',
                )
            ]
        )

    if user:
        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_WD_PROFILE_BTN', '👤 Профиль пользователя'),
                    callback_data=f'admin_user_manage_{user.id}',
                )
            ]
        )
    keyboard.append(
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_REFERRAL_WD_BACK_LIST', '⬅️ К списку'),
                callback_data='admin_withdrawal_requests',
            )
        ]
    )

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def approve_withdrawal_request(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    """Одобряет заявку на вывод."""
    texts = get_texts(db_user.language)
    request_id = int(callback.data.split('_')[-1])

    result = await db.execute(select(WithdrawalRequest).where(WithdrawalRequest.id == request_id))
    request = result.scalar_one_or_none()

    if not request:
        await callback.answer(texts.t('ADMIN_REFERRAL_WD_NOT_FOUND', 'Заявка не найдена'), show_alert=True)
        return

    success, error = await referral_withdrawal_service.approve_request(db, request_id, db_user.id)

    if success:
        # Уведомляем пользователя (только если есть telegram_id)
        user = await get_user_by_id(db, request.user_id)
        if user and user.telegram_id:
            try:
                texts = get_texts(user.language)
                await callback.bot.send_message(
                    user.telegram_id,
                    texts.t(
                        'REFERRAL_WITHDRAWAL_APPROVED',
                        '✅ <b>Заявка на вывод #{id} одобрена!</b>\n\n'
                        'Сумма: <b>{amount}</b>\n'
                        'Средства списаны с баланса.\n\n'
                        'Ожидайте перевод на указанные реквизиты.',
                    ).format(id=request.id, amount=texts.format_price(request.amount_kopeks)),
                )
            except Exception as e:
                logger.error('Ошибка отправки уведомления пользователю', error=e)

        await callback.answer(texts.t('ADMIN_REFERRAL_WD_APPROVED_TOAST', '✅ Заявка одобрена, средства списаны с баланса'))

        # Обновляем отображение
        await view_withdrawal_request(callback, db_user, db)
    else:
        await callback.answer(f'❌ {error}', show_alert=True)


@admin_required
@error_handler
async def reject_withdrawal_request(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    """Отклоняет заявку на вывод."""
    texts = get_texts(db_user.language)
    request_id = int(callback.data.split('_')[-1])

    result = await db.execute(select(WithdrawalRequest).where(WithdrawalRequest.id == request_id))
    request = result.scalar_one_or_none()

    if not request:
        await callback.answer(texts.t('ADMIN_REFERRAL_WD_NOT_FOUND', 'Заявка не найдена'), show_alert=True)
        return

    success, _error = await referral_withdrawal_service.reject_request(
        db,
        request_id,
        db_user.id,
        texts.t('ADMIN_REFERRAL_REJECT_REASON', 'Отклонено администратором'),
    )

    if success:
        # Уведомляем пользователя (только если есть telegram_id)
        user = await get_user_by_id(db, request.user_id)
        if user and user.telegram_id:
            try:
                texts = get_texts(user.language)
                await callback.bot.send_message(
                    user.telegram_id,
                    texts.t(
                        'REFERRAL_WITHDRAWAL_REJECTED',
                        '❌ <b>Заявка на вывод #{id} отклонена</b>\n\n'
                        'Сумма: <b>{amount}</b>\n\n'
                        'Если у вас есть вопросы, обратитесь в поддержку.',
                    ).format(id=request.id, amount=texts.format_price(request.amount_kopeks)),
                )
            except Exception as e:
                logger.error('Ошибка отправки уведомления пользователю', error=e)

        await callback.answer(texts.t('ADMIN_REFERRAL_WD_REJECTED_TOAST', '❌ Заявка отклонена'))

        # Обновляем отображение
        await view_withdrawal_request(callback, db_user, db)
    else:
        await callback.answer(texts.t('ADMIN_REFERRAL_WD_REJECT_ERROR', '❌ Ошибка отклонения'), show_alert=True)


@admin_required
@error_handler
async def complete_withdrawal_request(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    """Отмечает заявку как выполненную (деньги переведены)."""
    texts = get_texts(db_user.language)
    request_id = int(callback.data.split('_')[-1])

    result = await db.execute(select(WithdrawalRequest).where(WithdrawalRequest.id == request_id))
    request = result.scalar_one_or_none()

    if not request:
        await callback.answer(texts.t('ADMIN_REFERRAL_WD_NOT_FOUND', 'Заявка не найдена'), show_alert=True)
        return

    success, _error = await referral_withdrawal_service.complete_request(
        db,
        request_id,
        db_user.id,
        texts.t('ADMIN_REFERRAL_COMPLETE_NOTE', 'Перевод выполнен'),
    )

    if success:
        # Уведомляем пользователя (только если есть telegram_id)
        user = await get_user_by_id(db, request.user_id)
        if user and user.telegram_id:
            try:
                texts = get_texts(user.language)
                await callback.bot.send_message(
                    user.telegram_id,
                    texts.t(
                        'REFERRAL_WITHDRAWAL_COMPLETED',
                        '💸 <b>Выплата по заявке #{id} выполнена!</b>\n\n'
                        'Сумма: <b>{amount}</b>\n\n'
                        'Деньги отправлены на указанные реквизиты.',
                    ).format(id=request.id, amount=texts.format_price(request.amount_kopeks)),
                )
            except Exception as e:
                logger.error('Ошибка отправки уведомления пользователю', error=e)

        await callback.answer(texts.t('ADMIN_REFERRAL_WD_COMPLETED_TOAST', '✅ Заявка выполнена'))

        # Обновляем отображение
        await view_withdrawal_request(callback, db_user, db)
    else:
        await callback.answer(texts.t('ADMIN_REFERRAL_WD_COMPLETE_ERROR', '❌ Ошибка выполнения'), show_alert=True)


@admin_required
@error_handler
async def start_test_referral_earning(
    callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext
):
    """Начинает процесс тестового начисления реферального дохода."""
    texts = get_texts(db_user.language)
    if not settings.REFERRAL_WITHDRAWAL_TEST_MODE:
        await callback.answer(texts.t('ADMIN_REFERRAL_TEST_MODE_OFF', 'Тестовый режим отключён'), show_alert=True)
        return

    await state.set_state(AdminStates.test_referral_earning_input)

    text = texts.t(
        'ADMIN_REFERRAL_TEST_PROMPT',
        '🧪 <b>Тестовое начисление реферального дохода</b>\n\nВведите данные в формате:\n<code>telegram_id сумма_в_рублях</code>\n\nПримеры:\n• <code>123456789 500</code> — начислит 500₽ пользователю 123456789\n• <code>987654321 1000</code> — начислит 1000₽ пользователю 987654321\n\n⚠️ Это создаст реальную запись ReferralEarning, как будто пользователь заработал с реферала.',
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_CANCEL', '❌ Отмена'),
                    callback_data='admin_withdrawal_requests',
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@admin_required
@error_handler
async def process_test_referral_earning(message: types.Message, db_user: User, db: AsyncSession, state: FSMContext):
    """Обрабатывает ввод тестового начисления."""
    texts = get_texts(db_user.language)
    if not settings.REFERRAL_WITHDRAWAL_TEST_MODE:
        await message.answer(texts.t('ADMIN_REFERRAL_TEST_MODE_OFF', '❌ Тестовый режим отключён'))
        await state.clear()
        return

    text_input = message.text.strip()
    parts = text_input.split()

    if len(parts) != 2:
        await message.answer(
            texts.t(
                'ADMIN_REFERRAL_TEST_FORMAT_ERROR',
                '❌ Неверный формат. Введите: <code>telegram_id сумма</code>\n\nНапример: <code>123456789 500</code>',
            )
        )
        return

    try:
        target_telegram_id = int(parts[0])
        amount_rubles = float(parts[1].replace(',', '.'))
        amount_kopeks = int(amount_rubles * 100)

        if amount_kopeks <= 0:
            await message.answer(texts.t('ADMIN_REFERRAL_TEST_AMOUNT_POSITIVE', '❌ Сумма должна быть положительной'))
            return

        if amount_kopeks > 10000000:  # Лимит 100 000₽
            await message.answer(
                texts.t('ADMIN_REFERRAL_TEST_AMOUNT_MAX', '❌ Максимальная сумма тестового начисления: 100 000₽')
            )
            return

    except ValueError:
        await message.answer(
            texts.t(
                'ADMIN_REFERRAL_TEST_NUMBERS_ERROR',
                '❌ Неверный формат чисел. Введите: <code>telegram_id сумма</code>\n\nНапример: <code>123456789 500</code>',
            )
        )
        return

    # Ищем целевого пользователя
    target_user = await get_user_by_telegram_id(db, target_telegram_id)
    if not target_user:
        await message.answer(
            texts.t('ADMIN_REFERRAL_TEST_USER_NOT_FOUND', '❌ Пользователь с ID {tg_id} не найден в базе').format(
                tg_id=target_telegram_id
            )
        )
        return

    # Создаём тестовое начисление
    earning = ReferralEarning(
        user_id=target_user.id,
        referral_id=target_user.id,  # Сам на себя (тестовое)
        amount_kopeks=amount_kopeks,
        reason='test_earning',
    )
    db.add(earning)

    # Добавляем на баланс пользователя
    from app.database.crud.user import lock_user_for_update

    target_user = await lock_user_for_update(db, target_user)
    target_user.balance_kopeks += amount_kopeks

    await db.commit()
    await state.clear()

    await message.answer(
        texts.t(
            'ADMIN_REFERRAL_TEST_SUCCESS',
            '✅ <b>Тестовое начисление создано!</b>\n\n👤 Пользователь: {name}\n🆔 ID: <code>{tg_id}</code>\n💰 Сумма: <b>{amount}₽</b>\n💳 Новый баланс: <b>{balance}₽</b>\n\nНачисление добавлено как реферальный доход.',
        ).format(
            name=html.escape(target_user.full_name)
            if target_user.full_name
            else texts.t('ADMIN_REFERRAL_TEST_NO_NAME', 'Без имени'),
            tg_id=target_telegram_id,
            amount=f'{amount_rubles:.0f}',
            balance=settings.format_balance(target_user.balance_kopeks),
        ),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_TEST_TO_REQUESTS', '📋 К заявкам'),
                        callback_data='admin_withdrawal_requests',
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_TEST_PROFILE', '👤 Профиль'),
                        callback_data=f'admin_user_manage_{target_user.id}',
                    )
                ],
            ]
        ),
    )

    logger.info(
        'Тестовое начисление: админ начислил ₽ пользователю',
        telegram_id=db_user.telegram_id,
        amount_rubles=amount_rubles,
        target_telegram_id=target_telegram_id,
    )


def _get_period_dates(period: str) -> tuple[datetime, datetime]:
    """Возвращает начальную и конечную даты для заданного периода."""
    now = datetime.now(UTC)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == 'today':
        start_date = today
        end_date = today + timedelta(days=1)
    elif period == 'yesterday':
        start_date = today - timedelta(days=1)
        end_date = today
    elif period == 'week':
        start_date = today - timedelta(days=7)
        end_date = today + timedelta(days=1)
    elif period == 'month':
        start_date = today - timedelta(days=30)
        end_date = today + timedelta(days=1)
    else:
        # По умолчанию — сегодня
        start_date = today
        end_date = today + timedelta(days=1)

    return start_date, end_date


async def _show_diagnostics_for_period(
    callback: types.CallbackQuery,
    db: AsyncSession,
    state: FSMContext,
    period: str,
    *,
    texts,
):
    """Внутренняя функция для отображения диагностики за указанный период."""
    try:
        await callback.answer(texts.t('ADMIN_REFERRAL_DIAG_ANALYZING', 'Анализирую логи...'))

        from app.services.referral_diagnostics_service import referral_diagnostics_service

        # Сохраняем период в state
        await state.update_data(diagnostics_period=period)
        from app.states import AdminStates

        await state.set_state(AdminStates.referral_diagnostics_period)

        # Получаем даты периода
        start_date, end_date = _get_period_dates(period)

        # Анализируем логи
        report = await referral_diagnostics_service.analyze_period(db, start_date, end_date)

        # Формируем отчёт
        period_display = _ref_period_display(period, texts)

        text = texts.t('ADMIN_REFERRAL_DIAG_TITLE', '🔍 <b>Диагностика рефералов — {period}</b>\n\n').format(
            period=period_display
        )
        text += texts.t(
            'ADMIN_REFERRAL_DIAG_STATS',
            '<b>📊 Статистика переходов:</b>\n• Всего кликов по реф-ссылкам: {clicks}\n• Уникальных пользователей: {unique}\n• Потерянных рефералов: {lost}',
        ).format(
            clicks=report.total_ref_clicks,
            unique=report.unique_users_clicked,
            lost=len(report.lost_referrals),
        )
        text = _ref_append_lost_referrals(text, report.lost_referrals, texts, '%H:%M')

        # Информация о логах
        log_path = referral_diagnostics_service.log_path
        log_exists = await asyncio.to_thread(log_path.exists)
        log_size = (await asyncio.to_thread(log_path.stat)).st_size if log_exists else 0

        text += f'\n<i>📂 {log_path.name}'
        if log_exists:
            text += f' ({log_size / 1024:.0f} KB)'
            text += texts.t('ADMIN_REFERRAL_DIAG_LOG_LINES', ' | Строк: {lines}').format(lines=report.lines_in_period)
        else:
            text += texts.t('ADMIN_REFERRAL_DIAG_LOG_NOT_FOUND', ' (не найден!)')
        text += '</i>'

        keyboard_rows = [
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_DIAG_BTN_TODAY', '📅 Сегодня (текущий лог)'),
                    callback_data='admin_ref_diag:today',
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_DIAG_BTN_UPLOAD', '📤 Загрузить лог-файл'),
                    callback_data='admin_ref_diag_upload',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_DIAG_BTN_BONUSES', '🔍 Проверить бонусы (по БД)'),
                    callback_data='admin_ref_check_bonuses',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_DIAG_BTN_CONTEST', '🏆 Синхронизировать с конкурсом'),
                    callback_data='admin_ref_sync_contest',
                )
            ],
        ]

        if report.lost_referrals:
            keyboard_rows.append(
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_DIAG_BTN_FIX_PREVIEW', '📋 Предпросмотр исправлений'),
                        callback_data='admin_ref_fix_preview',
                    )
                ]
            )

        keyboard_rows.extend(
            [
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_BTN_REFRESH', '🔄 Обновить'),
                        callback_data=f'admin_ref_diag:{period}',
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_BTN_BACK_STATS', '⬅️ К статистике'),
                        callback_data='admin_referrals',
                    )
                ],
            ]
        )

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error('Ошибка в _show_diagnostics_for_period', error=e, exc_info=True)
        await callback.answer(texts.t('ADMIN_REFERRAL_DIAG_ERROR', 'Ошибка при анализе логов'), show_alert=True)


@admin_required
@error_handler
async def show_referral_diagnostics(callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    """Показывает диагностику реферальной системы по логам."""
    texts = get_texts(db_user.language)
    # Определяем период из callback_data или используем "today" по умолчанию
    if ':' in callback.data:
        period = callback.data.split(':')[1]
    else:
        period = 'today'

    await _show_diagnostics_for_period(callback, db, state, period, texts=texts)


@admin_required
@error_handler
async def preview_referral_fixes(callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    """Показывает предпросмотр исправлений потерянных рефералов."""
    texts = get_texts(db_user.language)
    try:
        await callback.answer(texts.t('ADMIN_REFERRAL_FIX_ANALYZING', 'Анализирую...'))

        # Получаем период из state
        state_data = await state.get_data()
        period = state_data.get('diagnostics_period', 'today')

        from app.services.referral_diagnostics_service import DiagnosticReport, referral_diagnostics_service

        # Проверяем, работаем ли с загруженным файлом
        if period == 'uploaded_file':
            # Используем сохранённый отчёт из загруженного файла (десериализуем)
            report_data = state_data.get('uploaded_file_report')
            if not report_data:
                await callback.answer(
                    texts.t('ADMIN_REFERRAL_UPLOAD_REPORT_MISSING', 'Отчёт загруженного файла не найден'),
                    show_alert=True,
                )
                return
            report = DiagnosticReport.from_dict(report_data)
            period_display = _ref_period_display('uploaded_file', texts)
        else:
            # Получаем даты периода
            start_date, end_date = _get_period_dates(period)

            # Анализируем логи
            report = await referral_diagnostics_service.analyze_period(db, start_date, end_date)
            period_display = _ref_period_display(period, texts)

        if not report.lost_referrals:
            await callback.answer(texts.t('ADMIN_REFERRAL_NO_LOST', 'Нет потерянных рефералов для исправления'), show_alert=True)
            return

        # Запускаем предпросмотр исправлений
        fix_report = await referral_diagnostics_service.fix_lost_referrals(db, report.lost_referrals, apply=False)

        # Формируем отчёт
        text = texts.t('ADMIN_REFERRAL_FIX_PREVIEW_TITLE', '📋 <b>Предпросмотр исправлений — {period}</b>\n\n').format(
            period=period_display
        )
        text += texts.t(
            'ADMIN_REFERRAL_FIX_PREVIEW_SUMMARY',
            '<b>📊 Что будет сделано:</b>\n• Исправлено рефералов: {fixed}\n• Бонусов рефералам: {to_referrals}\n• Бонусов рефереам: {to_referrers}\n• Ошибок: {errors}\n\n',
        ).format(
            fixed=fix_report.users_fixed,
            to_referrals=settings.format_price(fix_report.bonuses_to_referrals),
            to_referrers=settings.format_price(fix_report.bonuses_to_referrers),
            errors=fix_report.errors,
        )
        text += texts.t('ADMIN_REFERRAL_FIX_DETAILS', '<b>🔍 Детали:</b>') + '\n'

        # Показываем первые 10 деталей
        for i, detail in enumerate(fix_report.details[:10], 1):
            if detail.username:
                user_name = f'@{html.escape(detail.username)}'
            elif detail.full_name:
                user_name = html.escape(detail.full_name)
            else:
                user_name = f'ID{detail.telegram_id}'

            if detail.error:
                text += f'{i}. {user_name} — ❌ {html.escape(str(detail.error))}\n'
            else:
                text += f'{i}. {user_name}\n'
                if detail.referred_by_set:
                    referrer_display = (
                        html.escape(detail.referrer_name) if detail.referrer_name else f'ID{detail.referrer_id}'
                    )
                    text += texts.t('ADMIN_REFERRAL_FIX_REFERRER', '   • Реферер: {name}\n').format(name=referrer_display)
                if detail.had_first_topup:
                    text += texts.t('ADMIN_REFERRAL_FIX_FIRST_TOPUP', '   • Первое пополнение: {amount}\n').format(
                        amount=settings.format_price(detail.topup_amount_kopeks)
                    )
                if detail.bonus_to_referral_kopeks > 0:
                    text += texts.t('ADMIN_REFERRAL_FIX_BONUS_REFERRAL', '   • Бонус рефералу: {amount}\n').format(
                        amount=settings.format_price(detail.bonus_to_referral_kopeks)
                    )
                if detail.bonus_to_referrer_kopeks > 0:
                    text += texts.t('ADMIN_REFERRAL_FIX_BONUS_REFERRER', '   • Бонус рефереру: {amount}\n').format(
                        amount=settings.format_price(detail.bonus_to_referrer_kopeks)
                    )

        if len(fix_report.details) > 10:
            text += texts.t('ADMIN_REFERRAL_DIAG_MORE', '\n<i>... и ещё {count}</i>\n').format(
                count=len(fix_report.details) - 10
            )

        text += texts.t(
            'ADMIN_REFERRAL_FIX_PREVIEW_WARN',
            '\n⚠️ <b>Внимание!</b> Это только предпросмотр. Нажмите "Применить", чтобы выполнить исправления.',
        )

        back_button_callback = f'admin_ref_diag:{period}' if period != 'uploaded_file' else 'admin_referral_diagnostics'

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_FIX_BTN_APPLY', '✅ Применить исправления'),
                        callback_data='admin_ref_fix_apply',
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_FIX_BACK_DIAG', '⬅️ К диагностике'),
                        callback_data=back_button_callback,
                    )
                ],
            ]
        )

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error('Ошибка в preview_referral_fixes', error=e, exc_info=True)
        await callback.answer(texts.t('ADMIN_REFERRAL_FIX_PREVIEW_ERROR', 'Ошибка при создании предпросмотра'), show_alert=True)


@admin_required
@error_handler
async def apply_referral_fixes(callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    """Применяет исправления потерянных рефералов."""
    texts = get_texts(db_user.language)
    try:
        await callback.answer(texts.t('ADMIN_REFERRAL_FIX_APPLYING', 'Применяю исправления...'))

        # Получаем период из state
        state_data = await state.get_data()
        period = state_data.get('diagnostics_period', 'today')

        from app.services.referral_diagnostics_service import DiagnosticReport, referral_diagnostics_service

        # Проверяем, работаем ли с загруженным файлом
        if period == 'uploaded_file':
            # Используем сохранённый отчёт из загруженного файла (десериализуем)
            report_data = state_data.get('uploaded_file_report')
            if not report_data:
                await callback.answer(
                    texts.t('ADMIN_REFERRAL_UPLOAD_REPORT_MISSING', 'Отчёт загруженного файла не найден'),
                    show_alert=True,
                )
                return
            report = DiagnosticReport.from_dict(report_data)
            period_display = _ref_period_display('uploaded_file', texts)
        else:
            # Получаем даты периода
            start_date, end_date = _get_period_dates(period)

            # Анализируем логи
            report = await referral_diagnostics_service.analyze_period(db, start_date, end_date)
            period_display = _ref_period_display(period, texts)

        if not report.lost_referrals:
            await callback.answer(texts.t('ADMIN_REFERRAL_NO_LOST', 'Нет потерянных рефералов для исправления'), show_alert=True)
            return

        # Применяем исправления
        fix_report = await referral_diagnostics_service.fix_lost_referrals(db, report.lost_referrals, apply=True)

        # Формируем отчёт
        text = texts.t('ADMIN_REFERRAL_FIX_APPLIED_TITLE', '✅ <b>Исправления применены — {period}</b>\n\n').format(
            period=period_display
        )
        text += texts.t(
            'ADMIN_REFERRAL_FIX_APPLIED_SUMMARY',
            '<b>📊 Результаты:</b>\n• Исправлено рефералов: {fixed}\n• Бонусов рефералам: {to_referrals}\n• Бонусов рефереам: {to_referrers}\n• Ошибок: {errors}\n\n',
        ).format(
            fixed=fix_report.users_fixed,
            to_referrals=settings.format_price(fix_report.bonuses_to_referrals),
            to_referrers=settings.format_price(fix_report.bonuses_to_referrers),
            errors=fix_report.errors,
        )
        text += texts.t('ADMIN_REFERRAL_FIX_DETAILS', '<b>🔍 Детали:</b>') + '\n'

        # Показываем первые 10 успешных деталей
        success_count = 0
        for detail in fix_report.details:
            if not detail.error and success_count < 10:
                success_count += 1
                if detail.username:
                    user_name = f'@{html.escape(detail.username)}'
                elif detail.full_name:
                    user_name = html.escape(detail.full_name)
                else:
                    user_name = f'ID{detail.telegram_id}'

                text += f'{success_count}. {user_name}\n'
                if detail.referred_by_set:
                    referrer_display = (
                        html.escape(detail.referrer_name) if detail.referrer_name else f'ID{detail.referrer_id}'
                    )
                    text += texts.t('ADMIN_REFERRAL_FIX_REFERRER', '   • Реферер: {name}\n').format(name=referrer_display)
                if detail.bonus_to_referral_kopeks > 0:
                    text += texts.t('ADMIN_REFERRAL_FIX_BONUS_REFERRAL', '   • Бонус рефералу: {amount}\n').format(
                        amount=settings.format_price(detail.bonus_to_referral_kopeks)
                    )
                if detail.bonus_to_referrer_kopeks > 0:
                    text += texts.t('ADMIN_REFERRAL_FIX_BONUS_REFERRER', '   • Бонус рефереру: {amount}\n').format(
                        amount=settings.format_price(detail.bonus_to_referrer_kopeks)
                    )

        if fix_report.users_fixed > 10:
            text += texts.t('ADMIN_REFERRAL_FIX_MORE_FIXES', '\n<i>... и ещё {count} исправлений</i>\n').format(
                count=fix_report.users_fixed - 10
            )

        # Показываем ошибки
        if fix_report.errors > 0:
            text += texts.t('ADMIN_REFERRAL_FIX_ERRORS_HEADER', '\n<b>❌ Ошибки:</b>\n')
            error_count = 0
            for detail in fix_report.details:
                if detail.error and error_count < 5:
                    error_count += 1
                    if detail.username:
                        user_name = f'@{html.escape(detail.username)}'
                    elif detail.full_name:
                        user_name = html.escape(detail.full_name)
                    else:
                        user_name = f'ID{detail.telegram_id}'
                    text += f'• {user_name}: {html.escape(str(detail.error))}\n'
            if fix_report.errors > 5:
                text += texts.t('ADMIN_REFERRAL_FIX_MORE_ERRORS', '<i>... и ещё {count} ошибок</i>\n').format(
                    count=fix_report.errors - 5
                )

        # Кнопки зависят от источника
        keyboard_rows = []
        if period != 'uploaded_file':
            keyboard_rows.append(
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_FIX_REFRESH_DIAG', '🔄 Обновить диагностику'),
                        callback_data=f'admin_ref_diag:{period}',
                    )
                ]
            )
        keyboard_rows.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REFERRAL_BTN_BACK_STATS', '⬅️ К статистике'),
                    callback_data='admin_referrals',
                )
            ]
        )

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        await callback.message.edit_text(text, reply_markup=keyboard)

        # Очищаем сохранённый отчёт из state
        if period == 'uploaded_file':
            await state.update_data(uploaded_file_report=None)

    except Exception as e:
        logger.error('Ошибка в apply_referral_fixes', error=e, exc_info=True)
        await callback.answer(texts.t('ADMIN_REFERRAL_FIX_APPLY_ERROR', 'Ошибка при применении исправлений'), show_alert=True)


# =============================================================================
# Проверка бонусов по БД
# =============================================================================


@admin_required
@error_handler
async def check_missing_bonuses(callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    """Проверяет по БД — всем ли рефералам начислены бонусы."""
    from app.services.referral_diagnostics_service import (
        referral_diagnostics_service,
    )

    texts = get_texts(db_user.language)
    await callback.answer(texts.t('ADMIN_REFERRAL_BONUS_CHECKING', '🔍 Проверяю бонусы...'))

    try:
        report = await referral_diagnostics_service.check_missing_bonuses(db)

        # Сохраняем отчёт в state для последующего применения
        await state.update_data(missing_bonuses_report=report.to_dict())

        text = texts.t('ADMIN_REFERRAL_BONUS_TITLE', '🔍 <b>Проверка бонусов по БД</b>\n\n')
        text += texts.t(
            'ADMIN_REFERRAL_BONUS_STATS',
            '📊 <b>Статистика:</b>\n• Всего рефералов: {total}\n• С пополнением ≥ минимума: {with_topup}\n• <b>Без бонусов: {missing}</b>',
        ).format(
            total=report.total_referrals_checked,
            with_topup=report.referrals_with_topup,
            missing=len(report.missing_bonuses),
        )

        if report.missing_bonuses:
            text += texts.t(
                'ADMIN_REFERRAL_BONUS_NEEDED',
                '\n💰 <b>Требуется начислить:</b>\n• Рефералам: {to_referrals}₽\n• Рефереерам: {to_referrers}₽\n• <b>Итого: {total}₽</b>\n\n👤 <b>Список ({count} чел.):</b>',
            ).format(
                to_referrals=f'{report.total_missing_to_referrals / 100:.0f}',
                to_referrers=f'{report.total_missing_to_referrers / 100:.0f}',
                total=f'{(report.total_missing_to_referrals + report.total_missing_to_referrers) / 100:.0f}',
                count=len(report.missing_bonuses),
            )
            for i, mb in enumerate(report.missing_bonuses[:15], 1):
                referral_name = html.escape(
                    mb.referral_full_name or mb.referral_username or str(mb.referral_telegram_id)
                )
                referrer_name = html.escape(
                    mb.referrer_full_name or mb.referrer_username or str(mb.referrer_telegram_id)
                )
                text += texts.t(
                    'ADMIN_REFERRAL_BONUS_ITEM',
                    '\n{i}. <b>{referral}</b>\n   └ Пригласил: {referrer}\n   └ Пополнение: {topup}₽\n   └ Бонусы: {ref_bonus}₽ + {referrer_bonus}₽',
                ).format(
                    i=i,
                    referral=referral_name,
                    referrer=referrer_name,
                    topup=f'{mb.first_topup_amount_kopeks / 100:.0f}',
                    ref_bonus=f'{mb.referral_bonus_amount / 100:.0f}',
                    referrer_bonus=f'{mb.referrer_bonus_amount / 100:.0f}',
                )

            if len(report.missing_bonuses) > 15:
                text += texts.t('ADMIN_REFERRAL_BONUS_MORE', '\n\n<i>... и ещё {count} чел.</i>').format(
                    count=len(report.missing_bonuses) - 15
                )

            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.t('ADMIN_REFERRAL_BONUS_APPLY_BTN', '✅ Начислить все бонусы'),
                            callback_data='admin_ref_bonus_apply',
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=texts.t('ADMIN_REFERRAL_BTN_REFRESH', '🔄 Обновить'),
                            callback_data='admin_ref_check_bonuses',
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=texts.t('ADMIN_REFERRAL_FIX_BACK_DIAG', '⬅️ К диагностике'),
                            callback_data='admin_referral_diagnostics',
                        )
                    ],
                ]
            )
        else:
            text += texts.t('ADMIN_REFERRAL_BONUS_ALL_OK', '\n✅ <b>Все бонусы начислены!</b>')
            keyboard = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.t('ADMIN_REFERRAL_BTN_REFRESH', '🔄 Обновить'),
                            callback_data='admin_ref_check_bonuses',
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=texts.t('ADMIN_REFERRAL_FIX_BACK_DIAG', '⬅️ К диагностике'),
                            callback_data='admin_referral_diagnostics',
                        )
                    ],
                ]
            )

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error('Ошибка в check_missing_bonuses', error=e, exc_info=True)
        await callback.answer(texts.t('ADMIN_REFERRAL_BONUS_CHECK_ERROR', 'Ошибка при проверке бонусов'), show_alert=True)


@admin_required
@error_handler
async def apply_missing_bonuses(callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    """Применяет начисление пропущенных бонусов."""
    from app.services.referral_diagnostics_service import (
        MissingBonusReport,
        referral_diagnostics_service,
    )

    texts = get_texts(db_user.language)
    await callback.answer(texts.t('ADMIN_REFERRAL_BONUS_APPLYING', '💰 Начисляю бонусы...'))

    try:
        # Получаем сохранённый отчёт
        data = await state.get_data()
        report_dict = data.get('missing_bonuses_report')

        if not report_dict:
            await callback.answer(
                texts.t('ADMIN_REFERRAL_BONUS_REPORT_MISSING', '❌ Отчёт не найден. Обновите проверку.'),
                show_alert=True,
            )
            return

        report = MissingBonusReport.from_dict(report_dict)

        if not report.missing_bonuses:
            await callback.answer(texts.t('ADMIN_REFERRAL_BONUS_NONE', '✅ Нет бонусов для начисления'), show_alert=True)
            return

        # Применяем исправления
        fix_report = await referral_diagnostics_service.fix_missing_bonuses(db, report.missing_bonuses, apply=True)

        text = texts.t(
            'ADMIN_REFERRAL_BONUS_APPLIED',
            '✅ <b>Бонусы начислены!</b>\n\n📊 <b>Результат:</b>\n• Обработано: {fixed} пользователей\n• Начислено рефералам: {to_referrals}₽\n• Начислено рефереерам: {to_referrers}₽\n• <b>Итого: {total}₽</b>',
        ).format(
            fixed=fix_report.users_fixed,
            to_referrals=f'{fix_report.bonuses_to_referrals / 100:.0f}',
            to_referrers=f'{fix_report.bonuses_to_referrers / 100:.0f}',
            total=f'{(fix_report.bonuses_to_referrals + fix_report.bonuses_to_referrers) / 100:.0f}',
        )

        if fix_report.errors > 0:
            text += texts.t('ADMIN_REFERRAL_BONUS_ERRORS', '\n⚠️ Ошибок: {errors}').format(errors=fix_report.errors)

        # Очищаем отчёт из state
        await state.update_data(missing_bonuses_report=None)

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_BONUS_RECHECK', '🔍 Проверить снова'),
                        callback_data='admin_ref_check_bonuses',
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_FIX_BACK_DIAG', '⬅️ К диагностике'),
                        callback_data='admin_referral_diagnostics',
                    )
                ],
            ]
        )

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error('Ошибка в apply_missing_bonuses', error=e, exc_info=True)
        await callback.answer(texts.t('ADMIN_REFERRAL_BONUS_APPLY_ERROR', 'Ошибка при начислении бонусов'), show_alert=True)


@admin_required
@error_handler
async def sync_referrals_with_contest(
    callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext
):
    """Синхронизирует всех рефералов с активными конкурсами."""
    from app.database.crud.referral_contest import get_contests_for_events
    from app.services.referral_contest_service import referral_contest_service

    texts = get_texts(db_user.language)
    await callback.answer(texts.t('ADMIN_REFERRAL_CONTEST_SYNCING', '🏆 Синхронизирую с конкурсами...'))

    try:
        now_utc = datetime.now(UTC)

        # Получаем активные конкурсы
        paid_contests = await get_contests_for_events(db, now_utc, contest_types=['referral_paid'])
        reg_contests = await get_contests_for_events(db, now_utc, contest_types=['referral_registered'])

        all_contests = list(paid_contests) + list(reg_contests)

        if not all_contests:
            await callback.message.edit_text(
                texts.t(
                    'ADMIN_REFERRAL_CONTEST_NONE',
                    '❌ <b>Нет активных конкурсов рефералов</b>\n\nСоздайте конкурс в разделе "Конкурсы" для синхронизации.',
                ),
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text=texts.t('ADMIN_REFERRAL_FIX_BACK_DIAG', '⬅️ К диагностике'),
                                callback_data='admin_referral_diagnostics',
                            )
                        ]
                    ]
                ),
            )
            return

        # Синхронизируем каждый конкурс
        total_created = 0
        total_updated = 0
        total_skipped = 0
        contest_results = []

        for contest in all_contests:
            stats = await referral_contest_service.sync_contest(db, contest.id)
            if 'error' not in stats:
                total_created += stats.get('created', 0)
                total_updated += stats.get('updated', 0)
                total_skipped += stats.get('skipped', 0)
                contest_results.append(
                    texts.t('ADMIN_REFERRAL_CONTEST_LINE_OK', '• {title}: +{created} новых').format(
                        title=html.escape(contest.title),
                        created=stats.get('created', 0),
                    )
                )
            else:
                contest_results.append(
                    texts.t('ADMIN_REFERRAL_CONTEST_LINE_ERR', '• {title}: ошибка').format(
                        title=html.escape(contest.title)
                    )
                )

        text = texts.t(
            'ADMIN_REFERRAL_CONTEST_DONE',
            '🏆 <b>Синхронизация с конкурсами завершена!</b>\n\n📊 <b>Результат:</b>\n• Конкурсов обработано: {contests}\n• Новых событий добавлено: {created}\n• Обновлено: {updated}\n• Пропущено (уже есть): {skipped}\n\n📋 <b>По конкурсам:</b>',
        ).format(
            contests=len(all_contests),
            created=total_created,
            updated=total_updated,
            skipped=total_skipped,
        )
        text += '\n' + '\n'.join(contest_results)

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_CONTEST_RESYNC', '🔄 Синхронизировать снова'),
                        callback_data='admin_ref_sync_contest',
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_FIX_BACK_DIAG', '⬅️ К диагностике'),
                        callback_data='admin_referral_diagnostics',
                    )
                ],
            ]
        )

        await callback.message.edit_text(text, reply_markup=keyboard)

    except Exception as e:
        logger.error('Ошибка в sync_referrals_with_contest', error=e, exc_info=True)
        await callback.answer(texts.t('ADMIN_REFERRAL_CONTEST_SYNC_ERROR', 'Ошибка при синхронизации'), show_alert=True)


@admin_required
@error_handler
async def request_log_file_upload(callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    """Запрашивает загрузку лог-файла для анализа."""
    texts = get_texts(db_user.language)
    await state.set_state(AdminStates.waiting_for_log_file)

    text = texts.t(
        'ADMIN_REFERRAL_LOG_UPLOAD_TITLE',
        '📤 <b>Загрузка лог-файла для анализа</b>\n\nОтправьте файл лога (расширение .log или .txt).\n\nФайл будет проанализирован на наличие потерянных рефералов за ВСЕ время, записанное в логе.\n\n⚠️ <b>Важно:</b>\n• Файл должен быть текстовым (.log, .txt)\n• Максимальный размер: 50 MB\n• После анализа файл будет автоматически удалён\n\nЕсли ротация логов удалила старые данные — загрузите резервную копию.',
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_CANCEL', '❌ Отмена'),
                    callback_data='admin_referral_diagnostics',
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@admin_required
@error_handler
async def receive_log_file(message: types.Message, db_user: User, db: AsyncSession, state: FSMContext):
    """Получает и анализирует загруженный лог-файл."""
    import tempfile
    from pathlib import Path

    texts = get_texts(db_user.language)
    cancel_kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_CANCEL', '❌ Отмена'),
                    callback_data='admin_referral_diagnostics',
                )
            ]
        ]
    )

    if not message.document:
        await message.answer(texts.t('ADMIN_REFERRAL_LOG_SEND_DOC', '❌ Пожалуйста, отправьте файл документом.'), reply_markup=cancel_kb)
        return

    # Проверяем расширение файла
    file_name = message.document.file_name or 'unknown'
    file_ext = Path(file_name).suffix.lower()

    if file_ext not in ['.log', '.txt']:
        await message.answer(
            texts.t(
                'ADMIN_REFERRAL_LOG_BAD_EXT',
                '❌ Неверный формат файла: {ext}\n\nПоддерживаются только текстовые файлы (.log, .txt)',
            ).format(ext=html.escape(file_ext)),
            reply_markup=cancel_kb,
        )
        return

    # Проверяем размер файла
    max_size = 50 * 1024 * 1024  # 50 MB
    if message.document.file_size > max_size:
        await message.answer(
            texts.t(
                'ADMIN_REFERRAL_LOG_TOO_BIG',
                '❌ Файл слишком большой: {size} MB\n\nМаксимальный размер: 50 MB',
            ).format(size=f'{message.document.file_size / 1024 / 1024:.1f}'),
            reply_markup=cancel_kb,
        )
        return

    # Информируем о начале загрузки
    status_message = await message.answer(
        texts.t(
            'ADMIN_REFERRAL_LOG_DOWNLOADING',
            '📥 Загружаю файл {name} ({size} MB)...',
        ).format(name=html.escape(file_name), size=f'{message.document.file_size / 1024 / 1024:.1f}')
    )

    temp_file_path = None

    try:
        # Скачиваем файл во временную директорию
        temp_dir = tempfile.gettempdir()
        temp_file_path = str(Path(temp_dir) / f'ref_diagnostics_{message.from_user.id}_{file_name}')

        # Скачиваем файл
        file = await message.bot.get_file(message.document.file_id)
        await message.bot.download_file(file.file_path, temp_file_path)

        logger.info('📥 Файл загружен', temp_file_path=temp_file_path, file_size=message.document.file_size)

        # Обновляем статус
        await status_message.edit_text(
            texts.t(
                'ADMIN_REFERRAL_LOG_ANALYZING',
                '🔍 Анализирую файл {name}...\n\nЭто может занять некоторое время.',
            ).format(name=html.escape(file_name))
        )

        # Анализируем файл
        from app.services.referral_diagnostics_service import referral_diagnostics_service

        report = await referral_diagnostics_service.analyze_file(db, temp_file_path)

        # Формируем отчёт
        text = texts.t('ADMIN_REFERRAL_LOG_FILE_TITLE', '🔍 <b>Анализ лог-файла: {name}</b>\n\n').format(
            name=html.escape(file_name)
        )
        text += texts.t(
            'ADMIN_REFERRAL_DIAG_STATS',
            '<b>📊 Статистика переходов:</b>\n• Всего кликов по реф-ссылкам: {clicks}\n• Уникальных пользователей: {unique}\n• Потерянных рефералов: {lost}',
        ).format(
            clicks=report.total_ref_clicks,
            unique=report.unique_users_clicked,
            lost=len(report.lost_referrals),
        )
        text += texts.t('ADMIN_REFERRAL_DIAG_LOG_LINES', ' | Строк: {lines}').format(lines=report.lines_in_period)
        text = _ref_append_lost_referrals(text, report.lost_referrals, texts, '%d.%m.%Y %H:%M')

        # Сохраняем отчёт в state для дальнейшего использования (сериализуем в dict)
        await state.update_data(
            diagnostics_period='uploaded_file',
            uploaded_file_report=report.to_dict(),
        )

        # Кнопки действий
        keyboard_rows = []

        if report.lost_referrals:
            keyboard_rows.append(
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_DIAG_BTN_FIX_PREVIEW', '📋 Предпросмотр исправлений'),
                        callback_data='admin_ref_fix_preview',
                    )
                ]
            )

        keyboard_rows.extend(
            [
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_FIX_BACK_DIAG', '⬅️ К диагностике'),
                        callback_data='admin_referral_diagnostics',
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REFERRAL_BTN_BACK_STATS', '⬅️ К статистике'),
                        callback_data='admin_referrals',
                    )
                ],
            ]
        )

        keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

        # Удаляем статусное сообщение
        await status_message.delete()

        # Отправляем результат
        await message.answer(text, reply_markup=keyboard)

        # Очищаем состояние
        await state.set_state(AdminStates.referral_diagnostics_period)

    except Exception as e:
        logger.error('❌ Ошибка при обработке файла', error=e, exc_info=True)

        try:
            await status_message.edit_text(
                texts.t(
                    'ADMIN_REFERRAL_LOG_ANALYZE_ERROR',
                    '❌ <b>Ошибка при анализе файла</b>\n\nФайл: {name}\nОшибка: {error}\n\nПроверьте, что файл является текстовым логом бота.',
                ).format(name=html.escape(file_name), error=html.escape(str(e))),
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text=texts.t('ADMIN_REFERRAL_LOG_RETRY', '🔄 Попробовать снова'),
                                callback_data='admin_ref_diag_upload',
                            )
                        ],
                        [
                            types.InlineKeyboardButton(
                                text=texts.t('ADMIN_REFERRAL_FIX_BACK_DIAG', '⬅️ К диагностике'),
                                callback_data='admin_referral_diagnostics',
                            )
                        ],
                    ]
                ),
            )
        except:
            await message.answer(
                texts.t('ADMIN_REFERRAL_LOG_ERROR_SHORT', '❌ Ошибка при анализе: {error}').format(
                    error=html.escape(str(e))
                ),
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'),
                                callback_data='admin_referral_diagnostics',
                            )
                        ]
                    ]
                ),
            )

    finally:
        # Удаляем временный файл
        if temp_file_path and await asyncio.to_thread(Path(temp_file_path).exists):
            try:
                await asyncio.to_thread(Path(temp_file_path).unlink)
                logger.info('🗑️ Временный файл удалён', temp_file_path=temp_file_path)
            except Exception as e:
                logger.error('Ошибка удаления временного файла', error=e)


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_referral_statistics, F.data == 'admin_referrals')
    dp.callback_query.register(show_top_referrers, F.data == 'admin_referrals_top')
    dp.callback_query.register(show_top_referrers_filtered, F.data.startswith('admin_top_ref:'))
    dp.callback_query.register(show_referral_settings, F.data == 'admin_referrals_settings')
    dp.callback_query.register(show_referral_diagnostics, F.data == 'admin_referral_diagnostics')
    dp.callback_query.register(show_referral_diagnostics, F.data.startswith('admin_ref_diag:'))
    dp.callback_query.register(preview_referral_fixes, F.data == 'admin_ref_fix_preview')
    dp.callback_query.register(apply_referral_fixes, F.data == 'admin_ref_fix_apply')

    # Загрузка лог-файла
    dp.callback_query.register(request_log_file_upload, F.data == 'admin_ref_diag_upload')
    dp.message.register(receive_log_file, AdminStates.waiting_for_log_file)

    # Проверка бонусов по БД
    dp.callback_query.register(check_missing_bonuses, F.data == 'admin_ref_check_bonuses')
    dp.callback_query.register(apply_missing_bonuses, F.data == 'admin_ref_bonus_apply')
    dp.callback_query.register(sync_referrals_with_contest, F.data == 'admin_ref_sync_contest')

    # Хендлеры заявок на вывод
    dp.callback_query.register(show_pending_withdrawal_requests, F.data == 'admin_withdrawal_requests')
    dp.callback_query.register(view_withdrawal_request, F.data.startswith('admin_withdrawal_view_'))
    dp.callback_query.register(approve_withdrawal_request, F.data.startswith('admin_withdrawal_approve_'))
    dp.callback_query.register(reject_withdrawal_request, F.data.startswith('admin_withdrawal_reject_'))
    dp.callback_query.register(complete_withdrawal_request, F.data.startswith('admin_withdrawal_complete_'))

    # Тестовое начисление
    dp.callback_query.register(start_test_referral_earning, F.data == 'admin_test_referral_earning')
    dp.message.register(process_test_referral_earning, AdminStates.test_referral_earning_input)
