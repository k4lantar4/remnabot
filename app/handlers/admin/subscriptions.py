import structlog
from aiogram import Dispatcher, F, types
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.subscription import (
    get_all_subscriptions,
    get_expired_subscriptions,
    get_expiring_subscriptions,
    get_subscriptions_statistics,
)
from app.database.models import (
    ServerSquad,
    Subscription,
    SubscriptionServer,
    SubscriptionStatus,
    User,
)
from app.localization.texts import get_texts
from app.utils.decorators import admin_required, error_handler
from app.utils.formatters import format_datetime


logger = structlog.get_logger(__name__)


def get_country_flag(country_name: str) -> str:
    flags = {
        'USA': '🇺🇸',
        'United States': '🇺🇸',
        'US': '🇺🇸',
        'Germany': '🇩🇪',
        'DE': '🇩🇪',
        'Deutschland': '🇩🇪',
        'Netherlands': '🇳🇱',
        'NL': '🇳🇱',
        'Holland': '🇳🇱',
        'United Kingdom': '🇬🇧',
        'UK': '🇬🇧',
        'GB': '🇬🇧',
        'Japan': '🇯🇵',
        'JP': '🇯🇵',
        'France': '🇫🇷',
        'FR': '🇫🇷',
        'Canada': '🇨🇦',
        'CA': '🇨🇦',
        'Russia': '🇷🇺',
        'RU': '🇷🇺',
        'Singapore': '🇸🇬',
        'SG': '🇸🇬',
    }
    return flags.get(country_name, '🌍')


async def get_users_by_countries(db: AsyncSession) -> dict:
    try:
        result = await db.execute(
            select(
                ServerSquad.country_code,
                func.count(distinct(Subscription.user_id)),
            )
            .select_from(Subscription)
            .join(SubscriptionServer, SubscriptionServer.subscription_id == Subscription.id)
            .join(ServerSquad, SubscriptionServer.server_squad_id == ServerSquad.id)
            .where(Subscription.status == SubscriptionStatus.ACTIVE.value)
            .where(ServerSquad.country_code.isnot(None))
            .group_by(ServerSquad.country_code)
        )

        stats = {}
        for country_code, count in result.fetchall():
            if country_code:
                stats[country_code] = count

        return stats
    except Exception as error:
        logger.error('Ошибка получения статистики по странам', error=str(error), exc_info=True)
        return {}


def _subs_menu_keyboard(texts) -> list:
    return [
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_SUBS_BTN_LIST', '📋 Список подписок'),
                callback_data='admin_subs_list',
            ),
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_SUBS_BTN_EXPIRING', '⏰ Истекающие'),
                callback_data='admin_subs_expiring',
            ),
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_SUBS_BTN_STATS', '📊 Статистика'),
                callback_data='admin_subs_stats',
            ),
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_SUBS_BTN_GEO', '🌍 География'),
                callback_data='admin_subs_countries',
            ),
        ],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '◀️ Назад'), callback_data='admin_panel')],
    ]


@admin_required
@error_handler
async def show_subscriptions_menu(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    stats = await get_subscriptions_statistics(db)

    text = texts.t(
        'ADMIN_SUBS_MENU',
        '📱 <b>Управление подписками</b>\n\n'
        '📊 <b>Статистика:</b>\n'
        '- Всего: {total}\n'
        '- Активных: {active}\n'
        '- Платных: {paid}\n'
        '- Триальных: {trial}\n\n'
        '📈 <b>Продажи:</b>\n'
        '- Сегодня: {today}\n'
        '- За неделю: {week}\n'
        '- За месяц: {month}\n\n'
        'Выберите действие:',
    ).format(
        total=stats['total_subscriptions'],
        active=stats['active_subscriptions'],
        paid=stats['paid_subscriptions'],
        trial=stats['trial_subscriptions'],
        today=stats['purchased_today'],
        week=stats['purchased_week'],
        month=stats['purchased_month'],
    )

    await callback.message.edit_text(
        text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=_subs_menu_keyboard(texts))
    )
    await callback.answer()


@admin_required
@error_handler
async def show_subscriptions_list(callback: types.CallbackQuery, db_user: User, db: AsyncSession, page: int = 1):
    texts = get_texts(db_user.language)
    subscriptions, total_count = await get_all_subscriptions(db, page=page, limit=10)
    total_pages = (total_count + 9) // 10

    if not subscriptions:
        text = texts.t('ADMIN_SUBS_LIST_EMPTY', '📱 <b>Список подписок</b>\n\n❌ Подписки не найдены.')
    else:
        text = texts.t('ADMIN_SUBS_LIST_TITLE', '📱 <b>Список подписок</b>\n\n')
        text += texts.t(
            'ADMIN_SUBS_LIST_PAGE_INFO',
            '📊 Всего: {total} | Страница: {page}/{pages}\n\n',
        ).format(total=total_count, page=page, pages=total_pages)

        for i, sub in enumerate(subscriptions, 1 + (page - 1) * 10):
            user_info = (
                (f'ID{sub.user.telegram_id}' if sub.user.telegram_id else sub.user.email or f'#{sub.user.id}')
                if sub.user
                else texts.t('ADMIN_SUBS_UNKNOWN', 'Неизвестно')
            )
            sub_type = '🎁' if sub.is_trial else '💎'
            status = (
                texts.t('ADMIN_SUBS_STATUS_ACTIVE', '✅ Активна')
                if sub.is_active
                else texts.t('ADMIN_SUBS_STATUS_INACTIVE', '❌ Неактивна')
            )

            text += f'{i}. {sub_type} {user_info}\n'
            text += texts.t('ADMIN_SUBS_LIST_ROW', '   {status} | До: {end}\n').format(
                status=status, end=format_datetime(sub.end_date)
            )
            if sub.device_limit > 0:
                text += texts.t('ADMIN_SUBS_DEVICES', '   📱 Устройств: {count}\n').format(count=sub.device_limit)
            text += '\n'

    keyboard = []

    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(types.InlineKeyboardButton(text='⬅️', callback_data=f'admin_subs_list_page_{page - 1}'))

        nav_row.append(types.InlineKeyboardButton(text=f'{page}/{total_pages}', callback_data='current_page'))

        if page < total_pages:
            nav_row.append(types.InlineKeyboardButton(text='➡️', callback_data=f'admin_subs_list_page_{page + 1}'))

        keyboard.append(nav_row)

    keyboard.extend(
        [
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_STATS_REFRESH', '🔄 Обновить'),
                    callback_data='admin_subs_list',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REQCH_BACK', '◀️ Назад'),
                    callback_data='admin_subscriptions',
                )
            ],
        ]
    )

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def show_expiring_subscriptions(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    expiring_3d = await get_expiring_subscriptions(db, 3)
    expiring_1d = await get_expiring_subscriptions(db, 1)
    expired = await get_expired_subscriptions(db)

    text = texts.t(
        'ADMIN_SUBS_EXPIRING',
        '⏰ <b>Истекающие подписки</b>\n\n'
        '📊 <b>Статистика:</b>\n'
        '- Истекают через 3 дня: {in_3d}\n'
        '- Истекают завтра: {in_1d}\n'
        '- Уже истекли: {expired}\n\n'
        '<b>Истекают через 3 дня:</b>\n',
    ).format(in_3d=len(expiring_3d), in_1d=len(expiring_1d), expired=len(expired))

    for sub in expiring_3d[:5]:
        user_info = (
            (f'ID{sub.user.telegram_id}' if sub.user.telegram_id else sub.user.email or f'#{sub.user.id}')
            if sub.user
            else texts.t('ADMIN_SUBS_UNKNOWN', 'Неизвестно')
        )
        sub_type = '🎁' if sub.is_trial else '💎'
        text += f'{sub_type} {user_info} - {format_datetime(sub.end_date)}\n'

    if len(expiring_3d) > 5:
        text += texts.t('ADMIN_SUBS_MORE', '... и еще {count}\n').format(count=len(expiring_3d) - 5)

    text += texts.t('ADMIN_SUBS_EXPIRING_TOMORROW', '\n<b>Истекают завтра:</b>\n')
    for sub in expiring_1d[:5]:
        user_info = (
            (f'ID{sub.user.telegram_id}' if sub.user.telegram_id else sub.user.email or f'#{sub.user.id}')
            if sub.user
            else texts.t('ADMIN_SUBS_UNKNOWN', 'Неизвестно')
        )
        sub_type = '🎁' if sub.is_trial else '💎'
        text += f'{sub_type} {user_info} - {format_datetime(sub.end_date)}\n'

    if len(expiring_1d) > 5:
        text += texts.t('ADMIN_SUBS_MORE', '... и еще {count}\n').format(count=len(expiring_1d) - 5)

    keyboard = [
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_SUBS_BTN_REMIND', '📨 Отправить напоминания'),
                callback_data='admin_send_expiry_reminders',
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_STATS_REFRESH', '🔄 Обновить'),
                callback_data='admin_subs_expiring',
            )
        ],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '◀️ Назад'), callback_data='admin_subscriptions')],
    ]

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def show_subscriptions_stats(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    stats = await get_subscriptions_statistics(db)

    expiring_3d = await get_expiring_subscriptions(db, 3)
    expiring_7d = await get_expiring_subscriptions(db, 7)
    expired = await get_expired_subscriptions(db)

    text = texts.t(
        'ADMIN_SUBS_STATS_DETAIL',
        '📊 <b>Детальная статистика подписок</b>\n\n'
        '<b>📱 Общая информация:</b>\n'
        '• Всего подписок: {total}\n'
        '• Активных: {active}\n'
        '• Неактивных: {inactive}\n\n'
        '<b>💎 По типам:</b>\n'
        '• Платных: {paid}\n'
        '• Триальных: {trial}\n\n'
        '<b>📈 Продажи:</b>\n'
        '• Сегодня: {today}\n'
        '• За неделю: {week}\n'
        '• За месяц: {month}\n\n'
        '<b>⏰ Истечение:</b>\n'
        '• Истекают через 3 дня: {in_3d}\n'
        '• Истекают через 7 дней: {in_7d}\n'
        '• Уже истекли: {expired}\n\n'
        '<b>💰 Конверсия:</b>\n'
        '• Из триала в платную: {conversion}%\n'
        '• Продлений: {renewals}',
    ).format(
        total=stats['total_subscriptions'],
        active=stats['active_subscriptions'],
        inactive=stats['total_subscriptions'] - stats['active_subscriptions'],
        paid=stats['paid_subscriptions'],
        trial=stats['trial_subscriptions'],
        today=stats['purchased_today'],
        week=stats['purchased_week'],
        month=stats['purchased_month'],
        in_3d=len(expiring_3d),
        in_7d=len(expiring_7d),
        expired=len(expired),
        conversion=stats.get('trial_to_paid_conversion', 0),
        renewals=stats.get('renewals_count', 0),
    )

    keyboard = [[types.InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '◀️ Назад'), callback_data='admin_subscriptions')]]

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def show_countries_management(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    try:
        from app.services.remnawave_service import RemnaWaveService

        remnawave_service = RemnaWaveService()

        nodes_data = await remnawave_service.get_all_nodes()
        squads_data = await remnawave_service.get_all_squads()

        text = texts.t('ADMIN_SUBS_GEO_TITLE', '🌍 <b>Управление странами</b>\n\n')

        if nodes_data:
            text += texts.t('ADMIN_SUBS_GEO_SERVERS', '<b>Доступные серверы:</b>\n')
            countries = {}

            for node in nodes_data:
                country_code = node.get('country_code', 'XX')
                country_name = country_code

                if country_name not in countries:
                    countries[country_name] = []
                countries[country_name].append(node)

            for country, nodes in countries.items():
                active_nodes = len([n for n in nodes if n.get('is_connected') and n.get('is_node_online')])
                total_nodes = len(nodes)

                country_flag = get_country_flag(country)
                text += texts.t(
                    'ADMIN_SUBS_GEO_SERVER_ROW',
                    '{flag} {country}: {active}/{total} серверов\n',
                ).format(flag=country_flag, country=country, active=active_nodes, total=total_nodes)

                total_users_online = sum(n.get('users_online', 0) or 0 for n in nodes)
                if total_users_online > 0:
                    text += texts.t(
                        'ADMIN_SUBS_GEO_ONLINE',
                        '   👥 Пользователей онлайн: {count}\n',
                    ).format(count=total_users_online)
        else:
            text += texts.t('ADMIN_SUBS_GEO_LOAD_FAIL', '❌ Не удалось загрузить данные о серверах\n')

        if squads_data:
            text += texts.t('ADMIN_SUBS_GEO_SQUADS_TOTAL', '\n<b>Всего сквадов:</b> {count}\n').format(
                count=len(squads_data)
            )

            total_members = sum(squad.get('members_count', 0) for squad in squads_data)
            text += texts.t('ADMIN_SUBS_GEO_MEMBERS', '<b>Участников в сквадах:</b> {count}\n').format(
                count=total_members
            )

            text += texts.t('ADMIN_SUBS_GEO_SQUADS_LIST', '\n<b>Сквады:</b>\n')
            for squad in squads_data[:5]:
                name = squad.get('name', texts.t('ADMIN_SUBS_UNKNOWN', 'Неизвестно'))
                members = squad.get('members_count', 0)
                inbounds = squad.get('inbounds_count', 0)
                text += texts.t(
                    'ADMIN_SUBS_GEO_SQUAD_ROW',
                    '• {name}: {members} участников, {inbounds} inbound(s)\n',
                ).format(name=name, members=members, inbounds=inbounds)

            if len(squads_data) > 5:
                text += texts.t('ADMIN_SUBS_MORE_SQUADS', '... и еще {count} сквадов\n').format(
                    count=len(squads_data) - 5
                )

        user_stats = await get_users_by_countries(db)
        if user_stats:
            text += texts.t('ADMIN_SUBS_GEO_USERS', '\n<b>Пользователи по регионам:</b>\n')
            for country, count in user_stats.items():
                country_flag = get_country_flag(country)
                text += texts.t(
                    'ADMIN_SUBS_GEO_USER_ROW',
                    '{flag} {country}: {count} пользователей\n',
                ).format(flag=country_flag, country=country, count=count)

    except Exception as e:
        logger.error('Ошибка получения данных о странах', error=e)
        text = texts.t(
            'ADMIN_SUBS_GEO_ERROR',
            '🌍 <b>Управление странами</b>\n\n'
            '❌ <b>Ошибка загрузки данных</b>\n'
            'Не удалось получить информацию о серверах.\n\n'
            'Проверьте подключение к RemnaWave API.\n\n'
            '<b>Детали ошибки:</b> {error}',
        ).format(error=e)

    keyboard = [
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_STATS_REFRESH', '🔄 Обновить'),
                callback_data='admin_subs_countries',
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_SUBS_BTN_NODES', '📊 Статистика нод'),
                callback_data='admin_rw_nodes',
            ),
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_SUBS_BTN_SQUADS', '🔧 Сквады'),
                callback_data='admin_rw_squads',
            ),
        ],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '◀️ Назад'), callback_data='admin_subscriptions')],
    ]

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def send_expiry_reminders(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t(
            'ADMIN_SUBS_REMIND_PROGRESS',
            '📨 Отправка напоминаний...\n\nПодождите, это может занять время.',
        ),
        reply_markup=None,
    )

    expiring_subs = await get_expiring_subscriptions(db, 1)
    sent_count = 0

    for subscription in expiring_subs:
        if subscription.user:
            try:
                user = subscription.user
                if not user.telegram_id:
                    logger.debug('Пропуск email-пользователя при отправке напоминания', user_id=user.id)
                    continue

                days_left = max(1, subscription.days_left)
                user_texts = get_texts(user.language)

                tariff_label = ''
                if settings.is_multi_tariff_enabled() and hasattr(subscription, 'tariff') and subscription.tariff:
                    tariff_label = f' «{subscription.tariff.name}»'
                reminder_text = user_texts.t(
                    'ADMIN_SUBS_REMINDER_USER',
                    '⚠️ <b>Подписка{tariff} истекает!</b>\n\n'
                    'Ваша подписка истекает через {days} день(а).\n\n'
                    'Не забудьте продлить подписку, чтобы не потерять доступ к серверам.\n\n'
                    '💎 Продлить подписку можно в главном меню.',
                ).format(tariff=tariff_label, days=days_left)

                await callback.bot.send_message(chat_id=user.telegram_id, text=reminder_text)
                sent_count += 1

            except Exception as e:
                logger.error('Ошибка отправки напоминания пользователю', user_id=subscription.user_id, error=e)

    await callback.message.edit_text(
        texts.t(
            'ADMIN_SUBS_REMIND_DONE',
            '✅ Напоминания отправлены: {sent} из {total}',
        ).format(sent=sent_count, total=len(expiring_subs)),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t('ADMIN_REQCH_BACK', '◀️ Назад'),
                        callback_data='admin_subs_expiring',
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def handle_subscriptions_pagination(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    page = int(callback.data.split('_')[-1])
    await show_subscriptions_list(callback, db_user, db, page)


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_subscriptions_menu, F.data == 'admin_subscriptions')
    dp.callback_query.register(show_subscriptions_list, F.data == 'admin_subs_list')
    dp.callback_query.register(show_expiring_subscriptions, F.data == 'admin_subs_expiring')
    dp.callback_query.register(show_subscriptions_stats, F.data == 'admin_subs_stats')
    dp.callback_query.register(show_countries_management, F.data == 'admin_subs_countries')
    dp.callback_query.register(send_expiry_reminders, F.data == 'admin_send_expiry_reminders')

    dp.callback_query.register(handle_subscriptions_pagination, F.data.startswith('admin_subs_list_page_'))
