"""
Multi-tariff subscription list handler.

Shows all user subscriptions with per-subscription management.
Only active when MULTI_TARIFF_ENABLED=True.
"""

from __future__ import annotations

import structlog
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.subscription import (
    decrement_subscription_server_counts,
    get_all_subscriptions_by_user_id,
    get_subscription_by_id_for_user,
)
from app.database.models import Subscription, SubscriptionStatus, User
from app.localization.texts import get_texts
from app.keyboards.inline import get_pagination_keyboard
from app.services.subscription_service import SubscriptionService
from app.utils.formatting import format_traffic
from app.utils.jalali_datetime import format_user_datetime


logger = structlog.get_logger(__name__)

router = Router()

MY_SUBS_PER_PAGE = 6


def _parse_list_page(callback_data: str | None) -> int:
    data = callback_data or ''
    if data == 'my_subscriptions':
        return 1
    if data.startswith('my_subs_page_'):
        try:
            return max(1, int(data.rsplit('_', 1)[-1]))
        except ValueError:
            return 1
    return 1


def _status_emoji(sub) -> str:
    """Return status emoji based on subscription's actual status."""
    actual = sub.actual_status
    if actual in ('active', 'trial'):
        return '🟢'
    if actual == 'limited':
        return '🟡'
    return '🔴'


def _status_label(sub, texts) -> str:
    """Return a short human-readable status label for non-active subscriptions."""
    actual = sub.actual_status
    if actual == 'expired':
        return texts.t('MY_SUB_STATUS_EXPIRED', ' (Истекла)')
    if actual == 'disabled':
        return texts.t('MY_SUB_STATUS_DISABLED', ' (Отключена)')
    if actual == 'limited':
        return texts.t('MY_SUB_STATUS_LIMITED', ' (Лимит)')
    return ''


def _account_display_name(sub, texts) -> str:
    tariff_name = sub.tariff.name if sub.tariff else texts.t('MY_SUB_DEFAULT_NAME', 'Подписка')
    seq = getattr(sub, 'account_sequence', 1) or 1
    return texts.t('MY_SUB_ACCOUNT_LABEL', '{tariff} #{seq}').format(tariff=tariff_name, seq=seq)


def _format_subscription_line(sub, idx: int, texts, language: str) -> str:
    """Format a single subscription for the list view."""
    tariff_name = _account_display_name(sub, texts)
    emoji = _status_emoji(sub)
    label = _status_label(sub, texts)

    # Traffic info
    if sub.traffic_limit_gb == 0:
        traffic = '∞'
    else:
        used = f'{sub.traffic_used_gb:.1f}' if sub.traffic_used_gb else '0'
        traffic = f'{used}/{format_traffic(sub.traffic_limit_gb, language)}'

    # Devices
    devices = (
        texts.t('MY_SUB_DEVICES_COUNT_SHORT', '{count} устр.').format(count=sub.device_limit)
        if sub.device_limit
        else ''
    )

    # End date
    end_date = (
        format_user_datetime(sub.end_date, language=texts.language, fmt='%d.%m.%Y')
        if sub.end_date
        else '—'
    )

    parts = [f'{emoji} <b>{idx}. {tariff_name}</b>{label}']
    parts.append(texts.t('MY_SUB_TRAFFIC_LINE', '   📊 Трафик: {traffic}').format(traffic=traffic))
    if devices:
        parts.append(texts.t('MY_SUB_DEVICES_LINE', '   📱 Устройства: {devices}').format(devices=devices))
    parts.append(texts.t('MY_SUB_UNTIL_LINE', '   📅 До: {end_date}').format(end_date=end_date))

    return '\n'.join(parts)


def _build_subscriptions_keyboard(
    subscriptions: list,
    language: str,
    *,
    page: int,
    total_pages: int,
) -> types.InlineKeyboardMarkup:
    """Build inline keyboard with per-subscription management buttons (2 per row)."""
    texts = get_texts(language)
    buttons: list[list[types.InlineKeyboardButton]] = []
    row: list[types.InlineKeyboardButton] = []

    for sub in subscriptions:
        tariff_name = _account_display_name(sub, texts)
        row.append(
            types.InlineKeyboardButton(
                text=f'⚙️ {tariff_name}',
                callback_data=f'sm:{sub.id}',
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.extend(get_pagination_keyboard(page, total_pages, 'my_subs', language))

    buy_text = texts.t('MY_SUB_BTN_BUY_ANOTHER', 'Купить ещё тариф')
    buttons.append(
        [
            types.InlineKeyboardButton(text=f'➕ {buy_text}', callback_data='menu_buy'),
        ]
    )
    buttons.append(
        [
            types.InlineKeyboardButton(
                text=texts.BACK,
                callback_data='back_to_menu',
            ),
        ]
    )

    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_subscription_detail_keyboard(sub_id: int, sub=None, *, language: str = 'ru') -> types.InlineKeyboardMarkup:
    texts = get_texts(language)
    """Build keyboard for single subscription management.

    For expired/disabled subscriptions, only 'Renew' and 'Back' are shown —
    connection link and traffic/device management are irrelevant.
    """
    is_inactive = sub is not None and sub.actual_status in ('expired', 'disabled')

    buttons = []

    if not is_inactive:
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('MY_SUB_BTN_CONNECT_LINK', '🔗 Ссылка подключения'),
                    callback_data=f'sl:{sub_id}',
                )
            ]
        )

    buttons.append(
        [types.InlineKeyboardButton(text=texts.t('MY_SUB_BTN_RENEW', '🔄 Продлить'), callback_data=f'se:{sub_id}')]
    )

    if not is_inactive:
        buttons.append(
            [types.InlineKeyboardButton(text=texts.t('MY_SUB_BTN_AUTOPAY', '💳 Автоплатеж'), callback_data='subscription_autopay')]
        )
        buttons.append(
            [types.InlineKeyboardButton(text=texts.t('MY_SUB_BTN_TRAFFIC', '📊 Трафик'), callback_data=f'st:{sub_id}')]
        )
        buttons.append(
            [types.InlineKeyboardButton(text=texts.t('MY_SUB_BTN_DEVICES', '📱 Устройства'), callback_data=f'sd:{sub_id}')]
        )

    if is_inactive:
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('MY_SUB_BTN_DELETE', '🗑 Удалить подписку'),
                    callback_data=f'sub_del:{sub_id}',
                )
            ]
        )

    if not is_inactive and settings.is_subscription_revoke_enabled():
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('MY_SUB_BTN_REISSUE', '🔄 Перевыпустить'),
                    callback_data=f'sr:{sub_id}',
                )
            ]
        )

    buttons.append(
        [
            types.InlineKeyboardButton(
                text=texts.t('MY_SUB_BTN_BACK_TO_LIST', '◀️ К списку подписок'),
                callback_data='my_subscriptions',
            )
        ]
    )

    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


async def show_my_subscriptions(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext | None = None,
) -> None:
    """Show list of all user subscriptions."""
    if not settings.is_multi_tariff_enabled():
        # Fallback to legacy single subscription view
        return

    subscriptions = await get_all_subscriptions_by_user_id(db, db_user.id)
    texts = get_texts(db_user.language)
    page = _parse_list_page(callback.data)
    total_count = len(subscriptions)
    total_pages = max(1, (total_count + MY_SUBS_PER_PAGE - 1) // MY_SUBS_PER_PAGE)
    page = min(page, total_pages)
    start = (page - 1) * MY_SUBS_PER_PAGE
    page_subs = subscriptions[start : start + MY_SUBS_PER_PAGE]

    if not subscriptions:
        text = texts.t('MY_SUB_LIST_EMPTY', '📋 <b>Мои подписки</b>\n\nУ вас нет подписок.')
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t('MY_SUB_BTN_BUY', '🛒 Купить подписку'),
                        callback_data='menu_buy',
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.BACK,
                        callback_data='back_to_menu',
                    )
                ],
            ]
        )
    else:
        lines = [texts.t('MY_SUB_LIST_TITLE', '📋 <b>Мои подписки</b>') + '\n']
        if total_pages > 1:
            lines.append(
                texts.t(
                    'MY_SUB_LIST_PAGE',
                    '📄 Страница {page}/{pages} · всего {total}\n',
                ).format(page=page, pages=total_pages, total=total_count)
            )
        for idx, sub in enumerate(page_subs, start + 1):
            lines.append(_format_subscription_line(sub, idx, texts, db_user.language))
            lines.append('')
        text = '\n'.join(lines).rstrip()
        keyboard = _build_subscriptions_keyboard(
            page_subs,
            db_user.language,
            page=page,
            total_pages=total_pages,
        )

    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()


async def show_subscription_detail(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    """Show detail view for a single subscription (IDOR protected)."""
    texts = get_texts(db_user.language)
    parts = callback.data.split(':')
    if len(parts) < 2:
        await callback.answer(
            texts.t('CB_INVALID_FORMAT', 'Неверный формат'),
            show_alert=True,
        )
        return

    sub_id = int(parts[1])
    subscription = await get_subscription_by_id_for_user(db, sub_id, db_user.id)

    if not subscription:
        await callback.answer(
            texts.t('SUBSCRIPTION_NOT_FOUND', 'Подписка не найдена'),
            show_alert=True,
        )
        return

    # Persist active sub_id so downstream handlers without sub_id in callback_data
    # (e.g. 'subscription_autopay') can resolve the right subscription via FSM.
    await state.update_data(
        active_subscription_id=sub_id,
        target_subscription_id=sub_id,
    )

    display_name = _account_display_name(subscription, texts)

    # Traffic
    if subscription.traffic_limit_gb == 0:
        traffic = '∞'
    else:
        used = f'{subscription.traffic_used_gb:.1f}' if subscription.traffic_used_gb else '0'
        traffic = f'{used} / {format_traffic(subscription.traffic_limit_gb, db_user.language)}'

    end_date = (
        format_user_datetime(subscription.end_date, language=texts.language, fmt='%d.%m.%Y %H:%M')
        if subscription.end_date
        else '—'
    )
    status = subscription.status_display

    text = (
        f'📋 {texts.t("MY_SUB_DETAIL_HEADER", "<b>{label}</b>").format(label=display_name)}\n\n'
        f'{texts.t("MY_SUB_DETAIL_STATUS", "Статус: {status}").format(status=status)}\n'
        f'{texts.t("MY_SUB_DETAIL_TRAFFIC", "📊 Трафик: {traffic}").format(traffic=traffic)}\n'
        f'{texts.t("MY_SUB_DETAIL_DEVICES", "📱 Устройства: {devices}").format(devices=subscription.device_limit)}\n'
        f'{texts.t("MY_SUB_DETAIL_UNTIL", "📅 До: {end_date}").format(end_date=end_date)}\n'
    )

    if subscription.subscription_url and not settings.should_hide_subscription_link():
        text += f'\n🔗 <code>{subscription.subscription_url}</code>'

    keyboard = _build_subscription_detail_keyboard(sub_id, sub=subscription, language=db_user.language)

    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()


async def _resolve_and_store_sub(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> Subscription | None:
    """Extract sub_id from callback, validate ownership, store in FSM state."""
    texts = get_texts(db_user.language)
    sub_id = _extract_sub_id(callback)
    if sub_id is None:
        await callback.answer(
            texts.t('CB_INVALID_FORMAT', 'Неверный формат'),
            show_alert=True,
        )
        return None

    subscription = await get_subscription_by_id_for_user(db, sub_id, db_user.id)
    if not subscription:
        await callback.answer(
            texts.t('SUBSCRIPTION_NOT_FOUND', 'Подписка не найдена'),
            show_alert=True,
        )
        return None

    # Store in FSM state so downstream handlers can use it
    await state.update_data(
        active_subscription_id=sub_id,
        target_subscription_id=sub_id,
    )
    return subscription


async def handle_subscription_link(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    """Delegation: sl:{sub_id} → connect subscription link handler."""
    subscription = await _resolve_and_store_sub(callback, db_user, db, state)
    if not subscription:
        return

    from .links import handle_connect_subscription

    await handle_connect_subscription(callback, db_user, db, state)


async def handle_subscription_extend(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    """Delegation: se:{sub_id} → extend/renew subscription handler."""
    subscription = await _resolve_and_store_sub(callback, db_user, db, state)
    if not subscription:
        return

    from .purchase import handle_extend_subscription

    await handle_extend_subscription(callback, db_user, db, state)


async def handle_subscription_traffic(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    """Delegation: st:{sub_id} → traffic management handler."""
    subscription = await _resolve_and_store_sub(callback, db_user, db, state)
    if not subscription:
        return

    from .traffic import handle_add_traffic

    await handle_add_traffic(callback, db_user, db, state)


async def handle_subscription_devices(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    """Delegation: sd:{sub_id} → devices menu with buy + manage options."""
    subscription = await _resolve_and_store_sub(callback, db_user, db, state)
    if not subscription:
        return

    sub_id = subscription.id

    # Проверяем доступность докупки устройств
    can_buy_devices = False
    if subscription.tariff_id:
        from app.database.crud.tariff import get_tariff_by_id

        tariff = await get_tariff_by_id(db, subscription.tariff_id)
        tariff_device_price = getattr(tariff, 'device_price_kopeks', None) if tariff else None
        can_buy_devices = bool(tariff_device_price and tariff_device_price > 0)
    else:
        can_buy_devices = settings.is_devices_selection_enabled()

    texts = get_texts(db_user.language)
    current_devices = subscription.device_limit or 0
    text = texts.t(
        'MY_SUB_DEVICES_MENU',
        '📱 <b>Устройства</b>\n\nТекущий лимит: {current} устройств\n\nВыберите действие:',
    ).format(current=current_devices)

    keyboard = []
    if can_buy_devices:
        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('MY_SUB_BTN_BUY_DEVICES', '➕ Докупить устройства'),
                    callback_data=f'change_devices_menu:{sub_id}',
                )
            ]
        )
    keyboard.append(
        [
            types.InlineKeyboardButton(
                text=texts.t('MY_SUB_BTN_MANAGE_DEVICES', '📱 Управление устройствами'),
                callback_data=f'device_management:{sub_id}',
            )
        ]
    )
    keyboard.append(
        [
            types.InlineKeyboardButton(
                text=texts.BACK,
                callback_data=f'sm:{sub_id}',
            )
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
    )
    await callback.answer()


async def handle_change_devices_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    """Delegation: change_devices_menu:{sub_id} → buy/change device limit."""
    subscription = await _resolve_and_store_sub(callback, db_user, db, state)
    if not subscription:
        return

    from .devices import handle_change_devices

    await handle_change_devices(callback, db_user, db, state)


async def handle_device_management_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    """Delegation: device_management:{sub_id} → manage connected devices."""
    subscription = await _resolve_and_store_sub(callback, db_user, db, state)
    if not subscription:
        return

    from .devices import handle_device_management

    await handle_device_management(callback, db_user, db, state)


async def handle_subscription_delete_confirm(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    """Show delete confirmation for an expired/disabled subscription."""
    texts = get_texts(db_user.language)
    sub_id = _extract_sub_id(callback)
    if sub_id is None:
        await callback.answer(
            texts.t('CB_INVALID_FORMAT', 'Неверный формат'),
            show_alert=True,
        )
        return

    subscription = await get_subscription_by_id_for_user(db, sub_id, db_user.id)
    if not subscription:
        await callback.answer(
            texts.t('SUBSCRIPTION_NOT_FOUND', 'Подписка не найдена'),
            show_alert=True,
        )
        return

    if subscription.actual_status not in ('expired', 'disabled'):
        await callback.answer(
            texts.t(
                'CB_SUBSCRIPTION_DELETE_ONLY_EXPIRED',
                'Можно удалить только истекшую или отключённую подписку',
            ),
            show_alert=True,
        )
        return

    tariff_name = subscription.tariff.name if subscription.tariff else texts.t('MY_SUB_DEFAULT_NAME', 'Подписка')

    text = texts.t(
        'MY_SUB_DELETE_CONFIRM',
        '🗑 <b>Удалить подписку «{name}»?</b>\n\n'
        '⚠️ Подписка будет удалена безвозвратно.\n'
        'Все данные, устройства и настройки будут потеряны.\n'
        'Это действие нельзя отменить.',
    ).format(name=tariff_name)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t('MY_SUB_BTN_DELETE_YES', '🗑 Да, удалить'),
                    callback_data=f'sub_del_yes:{sub_id}',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.BACK,
                    callback_data=f'sm:{sub_id}',
                )
            ],
        ]
    )

    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode='HTML')
    await callback.answer()


async def handle_subscription_delete_execute(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    """Actually delete an expired/disabled subscription."""
    texts = get_texts(db_user.language)
    sub_id = _extract_sub_id(callback)
    if sub_id is None:
        await callback.answer(
            texts.t('CB_INVALID_FORMAT', 'Неверный формат'),
            show_alert=True,
        )
        return

    subscription = await get_subscription_by_id_for_user(db, sub_id, db_user.id)
    if not subscription:
        await callback.answer(
            texts.t('SUBSCRIPTION_NOT_FOUND', 'Подписка не найдена'),
            show_alert=True,
        )
        return

    deletable_statuses = {SubscriptionStatus.EXPIRED.value, SubscriptionStatus.DISABLED.value}
    if getattr(subscription, 'actual_status', subscription.status) not in deletable_statuses:
        await callback.answer(
            texts.t(
                'CB_SUBSCRIPTION_DELETE_ONLY_EXPIRED',
                'Можно удалить только истекшую или отключённую подписку',
            ),
            show_alert=True,
        )
        return

    # Delete from RemnaWave panel (stops webhooks / phantom notifications)
    if subscription.remnawave_uuid:
        try:
            service = SubscriptionService()
            await service.delete_remnawave_user(subscription.remnawave_uuid)
        except Exception as e:
            logger.warning('Failed to delete RemnaWave user on subscription delete', error=e)

    # Decrement server counts
    await decrement_subscription_server_counts(db, subscription)

    # Hard delete from DB
    await db.delete(subscription)
    await db.commit()

    logger.info(
        'Subscription deleted by user via bot',
        subscription_id=sub_id,
        user_id=db_user.id,
    )

    await callback.answer(
        texts.t('CB_SUBSCRIPTION_DELETED', 'Подписка удалена'),
        show_alert=True,
    )

    # Return to subscriptions list
    await show_my_subscriptions(callback, db_user, db, state)


def _extract_sub_id(callback: types.CallbackQuery) -> int | None:
    """Extract subscription ID from callback_data format 'prefix:sub_id'."""
    parts = (callback.data or '').split(':')
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except (ValueError, TypeError):
            return None
    return None
