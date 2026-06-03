from datetime import UTC, datetime, timedelta

import structlog
from aiogram import Dispatcher, F, types
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.referral import get_referral_statistics
from app.database.crud.subscription import get_subscriptions_statistics
from app.database.crud.transaction import get_revenue_by_period, get_transactions_statistics
from app.database.models import User
from app.keyboards.admin import get_admin_statistics_keyboard
from app.localization.texts import get_texts
from app.services.user_service import UserService
from app.utils.decorators import admin_required, error_handler
from app.utils.formatters import format_datetime, format_percentage


logger = structlog.get_logger(__name__)


def _stats_nav_keyboard(texts, refresh_cb: str, back_cb: str = 'admin_statistics'):
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t('ADMIN_STATS_REFRESH', '🔄 Обновить'), callback_data=refresh_cb)],
            [types.InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'), callback_data=back_cb)],
        ]
    )


@admin_required
@error_handler
async def show_statistics_menu(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    text = texts.t(
        'ADMIN_STATS_MENU',
        '📊 <b>Статистика системы</b>\n\nВыберите раздел для просмотра статистики:',
    )

    await callback.message.edit_text(text, reply_markup=get_admin_statistics_keyboard(db_user.language))
    await callback.answer()


@admin_required
@error_handler
async def show_users_statistics(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    user_service = UserService()
    stats = await user_service.get_user_statistics(db)

    total_users = stats['total_users']
    active_rate = format_percentage(stats['active_users'] / total_users * 100 if total_users > 0 else 0)
    current_time = format_datetime(datetime.now(UTC))

    text = texts.t(
        'ADMIN_STATS_USERS',
        '👥 <b>Статистика пользователей</b>\n\n'
        '<b>Общие показатели:</b>\n'
        '- Всего зарегистрировано: {total}\n'
        '- Активных: {active} ({active_rate})\n'
        '- Заблокированных: {blocked}\n\n'
        '<b>Новые регистрации:</b>\n'
        '- Сегодня: {today}\n'
        '- За неделю: {week}\n'
        '- За месяц: {month}\n\n'
        '<b>Активность:</b>\n'
        '- Коэффициент активности: {active_rate}\n'
        '- Рост за месяц: +{month} ({growth_rate})\n\n'
        '<b>Обновлено:</b> {updated}',
    ).format(
        total=stats['total_users'],
        active=stats['active_users'],
        active_rate=active_rate,
        blocked=stats['blocked_users'],
        today=stats['new_today'],
        week=stats['new_week'],
        month=stats['new_month'],
        growth_rate=format_percentage(stats['new_month'] / total_users * 100 if total_users > 0 else 0),
        updated=current_time,
    )

    keyboard = _stats_nav_keyboard(texts, 'admin_stats_users')

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception as e:
        if 'message is not modified' in str(e):
            await callback.answer(texts.t('ADMIN_STATS_UP_TO_DATE', '📊 Данные актуальны'), show_alert=False)
        else:
            logger.error('Ошибка обновления статистики пользователей', error=e)
            await callback.answer(texts.t('ADMIN_STATS_UPDATE_ERROR', '❌ Ошибка обновления данных'), show_alert=True)
            return

    await callback.answer(texts.t('ADMIN_STATS_UPDATED', '✅ Статистика обновлена'))


@admin_required
@error_handler
async def show_subscriptions_statistics(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    stats = await get_subscriptions_statistics(db)

    total_subs = stats['total_subscriptions']
    conversion_rate = format_percentage(stats['paid_subscriptions'] / total_subs * 100 if total_subs > 0 else 0)
    current_time = format_datetime(datetime.now(UTC))

    text = texts.t(
        'ADMIN_STATS_SUBS',
        '📱 <b>Статистика подписок</b>\n\n'
        '<b>Общие показатели:</b>\n'
        '- Всего подписок: {total}\n'
        '- Активных: {active}\n'
        '- Платных: {paid}\n'
        '- Триальных: {trial}\n\n'
        '<b>Конверсия:</b>\n'
        '- Из триала в платную: {conversion}\n'
        '- Активных платных: {paid}\n\n'
        '<b>Продажи:</b>\n'
        '- Сегодня: {today}\n'
        '- За неделю: {week}\n'
        '- За месяц: {month}\n\n'
        '<b>Обновлено:</b> {updated}',
    ).format(
        total=stats['total_subscriptions'],
        active=stats['active_subscriptions'],
        paid=stats['paid_subscriptions'],
        trial=stats['trial_subscriptions'],
        conversion=conversion_rate,
        today=stats['purchased_today'],
        week=stats['purchased_week'],
        month=stats['purchased_month'],
        updated=current_time,
    )

    keyboard = _stats_nav_keyboard(texts, 'admin_stats_subs')

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer(texts.t('ADMIN_STATS_UPDATED', '✅ Статистика обновлена'))
    except Exception as e:
        if 'message is not modified' in str(e):
            await callback.answer(texts.t('ADMIN_STATS_UP_TO_DATE', '📊 Данные актуальны'), show_alert=False)
        else:
            logger.error('Ошибка обновления статистики подписок', error=e)
            await callback.answer(texts.t('ADMIN_STATS_UPDATE_ERROR', '❌ Ошибка обновления данных'), show_alert=True)


@admin_required
@error_handler
async def show_revenue_statistics(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    month_stats = await get_transactions_statistics(db, month_start, now)
    all_time_stats = await get_transactions_statistics(db, start_date=datetime(2020, 1, 1, tzinfo=UTC), end_date=now)
    current_time = format_datetime(datetime.now(UTC))

    text = texts.t(
        'ADMIN_STATS_REVENUE',
        '💰 <b>Статистика доходов</b>\n\n'
        '<b>За текущий месяц:</b>\n'
        '- Доходы: {month_income}\n'
        '- Расходы: {month_expenses}\n'
        '- Прибыль: {month_profit}\n'
        '- От подписок: {month_subs}\n\n'
        '<b>Сегодня:</b>\n'
        '- Транзакций: {today_count}\n'
        '- Доходы: {today_income}\n\n'
        '<b>За все время:</b>\n'
        '- Общий доход: {all_income}\n'
        '- Общая прибыль: {all_profit}\n\n'
        '<b>Способы оплаты:</b>\n',
    ).format(
        month_income=settings.format_price(month_stats['totals']['income_kopeks']),
        month_expenses=settings.format_price(month_stats['totals']['expenses_kopeks']),
        month_profit=settings.format_price(month_stats['totals']['profit_kopeks']),
        month_subs=settings.format_price(abs(month_stats['totals']['subscription_income_kopeks'])),
        today_count=month_stats['today']['transactions_count'],
        today_income=settings.format_price(month_stats['today']['income_kopeks']),
        all_income=settings.format_price(all_time_stats['totals']['income_kopeks']),
        all_profit=settings.format_price(all_time_stats['totals']['profit_kopeks']),
    )

    for method, data in month_stats['by_payment_method'].items():
        if method and data['count'] > 0:
            text += texts.t('ADMIN_STATS_PAYMENT_ROW', '• {method}: {count} ({amount})\n').format(
                method=method, count=data['count'], amount=settings.format_price(data['amount'])
            )

    text += texts.t('ADMIN_STATS_UPDATED_LINE', '\n<b>Обновлено:</b> {updated}').format(updated=current_time)

    keyboard = _stats_nav_keyboard(texts, 'admin_stats_revenue')

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer(texts.t('ADMIN_STATS_UPDATED', '✅ Статистика обновлена'))
    except Exception as e:
        if 'message is not modified' in str(e):
            await callback.answer(texts.t('ADMIN_STATS_UP_TO_DATE', '📊 Данные актуальны'), show_alert=False)
        else:
            logger.error('Ошибка обновления статистики доходов', error=e)
            await callback.answer(texts.t('ADMIN_STATS_UPDATE_ERROR', '❌ Ошибка обновления данных'), show_alert=True)


@admin_required
@error_handler
async def show_referral_statistics(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    stats = await get_referral_statistics(db)
    current_time = format_datetime(datetime.now(UTC))

    avg_per_referrer = 0
    if stats['active_referrers'] > 0:
        avg_per_referrer = stats['total_paid_kopeks'] / stats['active_referrers']

    text = texts.t(
        'ADMIN_STATS_REFERRALS',
        '🤝 <b>Реферальная статистика</b>\n\n'
        '<b>Общие показатели:</b>\n'
        '- Пользователей с рефералами: {with_refs}\n'
        '- Активных рефереров: {active_refs}\n'
        '- Выплачено всего: {total_paid}\n\n'
        '<b>За период:</b>\n'
        '- Сегодня: {today}\n'
        '- За неделю: {week}\n'
        '- За месяц: {month}\n\n'
        '<b>Средние показатели:</b>\n'
        '- На одного рефререра: {avg}\n\n'
        '<b>Топ рефереры:</b>\n',
    ).format(
        with_refs=stats['users_with_referrals'],
        active_refs=stats['active_referrers'],
        total_paid=settings.format_price(stats['total_paid_kopeks']),
        today=settings.format_price(stats['today_earnings_kopeks']),
        week=settings.format_price(stats['week_earnings_kopeks']),
        month=settings.format_price(stats['month_earnings_kopeks']),
        avg=settings.format_price(int(avg_per_referrer)),
    )

    if stats['top_referrers']:
        for i, referrer in enumerate(stats['top_referrers'][:5], 1):
            name = referrer['display_name']
            earned = settings.format_price(referrer['total_earned_kopeks'])
            count = referrer['referrals_count']
            text += texts.t('ADMIN_STATS_REFERRER_ROW', '{i}. {name}: {earned} ({count} реф.)\n').format(
                i=i, name=name, earned=earned, count=count
            )
    else:
        text += texts.t('ADMIN_STATS_NO_REFERRERS', 'Пока нет активных рефереров')

    text += texts.t('ADMIN_STATS_UPDATED_LINE', '\n<b>Обновлено:</b> {updated}').format(updated=current_time)

    keyboard = _stats_nav_keyboard(texts, 'admin_stats_referrals')

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer(texts.t('ADMIN_STATS_UPDATED', '✅ Статистика обновлена'))
    except Exception as e:
        if 'message is not modified' in str(e):
            await callback.answer(texts.t('ADMIN_STATS_UP_TO_DATE', '📊 Данные актуальны'), show_alert=False)
        else:
            logger.error('Ошибка обновления реферальной статистики', error=e)
            await callback.answer(texts.t('ADMIN_STATS_UPDATE_ERROR', '❌ Ошибка обновления данных'), show_alert=True)


@admin_required
@error_handler
async def show_summary_statistics(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    user_service = UserService()
    user_stats = await user_service.get_user_statistics(db)
    sub_stats = await get_subscriptions_statistics(db)

    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue_stats = await get_transactions_statistics(db, month_start, now)
    current_time = format_datetime(datetime.now(UTC))

    conversion_rate = 0
    if user_stats['total_users'] > 0:
        conversion_rate = sub_stats['paid_subscriptions'] / user_stats['total_users'] * 100

    arpu = 0
    if user_stats['active_users'] > 0:
        arpu = revenue_stats['totals']['income_kopeks'] / user_stats['active_users']

    text = texts.t(
        'ADMIN_STATS_SUMMARY',
        '📊 <b>Общая сводка системы</b>\n\n'
        '<b>Пользователи:</b>\n'
        '- Всего: {users_total}\n'
        '- Активных: {users_active}\n'
        '- Новых за месяц: {users_month}\n\n'
        '<b>Подписки:</b>\n'
        '- Активных: {subs_active}\n'
        '- Платных: {subs_paid}\n'
        '- Конверсия: {conversion}\n\n'
        '<b>Финансы (месяц):</b>\n'
        '- Доходы: {income}\n'
        '- ARPU: {arpu}\n'
        '- Транзакций: {tx_count}\n\n'
        '<b>Рост:</b>\n'
        '- Пользователи: +{users_month} за месяц\n'
        '- Продажи: +{sales_month} за месяц\n\n'
        '<b>Обновлено:</b> {updated}',
    ).format(
        users_total=user_stats['total_users'],
        users_active=user_stats['active_users'],
        users_month=user_stats['new_month'],
        subs_active=sub_stats['active_subscriptions'],
        subs_paid=sub_stats['paid_subscriptions'],
        conversion=format_percentage(conversion_rate),
        income=settings.format_price(revenue_stats['totals']['income_kopeks']),
        arpu=settings.format_price(int(arpu)),
        tx_count=sum(data['count'] for data in revenue_stats['by_type'].values()),
        sales_month=sub_stats['purchased_month'],
        updated=current_time,
    )

    keyboard = _stats_nav_keyboard(texts, 'admin_stats_summary')

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer(texts.t('ADMIN_STATS_UPDATED', '✅ Статистика обновлена'))
    except Exception as e:
        if 'message is not modified' in str(e):
            await callback.answer(texts.t('ADMIN_STATS_UP_TO_DATE', '📊 Данные актуальны'), show_alert=False)
        else:
            logger.error('Ошибка обновления общей статистики', error=e)
            await callback.answer(texts.t('ADMIN_STATS_UPDATE_ERROR', '❌ Ошибка обновления данных'), show_alert=True)


@admin_required
@error_handler
async def show_revenue_by_period(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    period = callback.data.split('_')[-1]

    period_map = {'today': 1, 'yesterday': 1, 'week': 7, 'month': 30, 'all': 365}

    days = period_map.get(period, 30)
    revenue_data = await get_revenue_by_period(db, days)

    if period == 'yesterday':
        yesterday = datetime.now(UTC).date() - timedelta(days=1)
        revenue_data = [r for r in revenue_data if r['date'] == yesterday]
    elif period == 'today':
        today = datetime.now(UTC).date()
        revenue_data = [r for r in revenue_data if r['date'] == today]

    total_revenue = sum(r['amount_kopeks'] for r in revenue_data)
    avg_daily = total_revenue / len(revenue_data) if revenue_data else 0

    text = texts.t(
        'ADMIN_STATS_REVENUE_PERIOD',
        '📈 <b>Доходы за период: {period}</b>\n\n'
        '<b>Сводка:</b>\n'
        '- Общий доход: {total}\n'
        '- Дней с данными: {days}\n'
        '- Средний доход в день: {avg}\n\n'
        '<b>По дням:</b>\n',
    ).format(
        period=period,
        total=settings.format_price(total_revenue),
        days=len(revenue_data),
        avg=settings.format_price(int(avg_daily)),
    )

    for revenue in revenue_data[-10:]:
        text += texts.t('ADMIN_STATS_REVENUE_DAY', '• {date}: {amount}\n').format(
            date=revenue['date'].strftime('%d.%m'),
            amount=settings.format_price(revenue['amount_kopeks']),
        )

    if len(revenue_data) > 10:
        text += texts.t('ADMIN_STATS_MORE_DAYS', '... и еще {count} дней').format(count=len(revenue_data) - 10)

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_STATS_OTHER_PERIOD', '📊 Другой период'),
                        callback_data='admin_revenue_period',
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_STATS_BACK_REVENUE', '⬅️ К доходам'),
                        callback_data='admin_stats_revenue',
                    )
                ],
            ]
        ),
    )
    await callback.answer()


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_statistics_menu, F.data == 'admin_statistics')
    dp.callback_query.register(show_users_statistics, F.data == 'admin_stats_users')
    dp.callback_query.register(show_subscriptions_statistics, F.data == 'admin_stats_subs')
    dp.callback_query.register(show_revenue_statistics, F.data == 'admin_stats_revenue')
    dp.callback_query.register(show_referral_statistics, F.data == 'admin_stats_referrals')
    dp.callback_query.register(show_summary_statistics, F.data == 'admin_stats_summary')
    dp.callback_query.register(show_revenue_by_period, F.data.startswith('period_'))

    periods = ['today', 'yesterday', 'week', 'month', 'all']
    for period in periods:
        dp.callback_query.register(show_revenue_by_period, F.data == f'period_{period}')
