"""
Multi-tariff subscription list handler.

Shows all user subscriptions with per-subscription management.
Only active when MULTI_TARIFF_ENABLED=True.
"""

from __future__ import annotations

import html
from types import SimpleNamespace

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
from app.localization.texts import Texts, get_texts
from app.services.subscription_service import SubscriptionService
from app.services.subscription_user_toggle_service import (
    SubscriptionToggleError,
    disable_user_subscription,
    enable_user_subscription,
)
from app.states import SubscriptionStates
from app.utils.jalali_datetime import format_user_datetime
from app.utils.photo_message import edit_or_answer_photo
from app.utils.subscription_list_display import (
    filter_subscriptions_by_query,
    format_subscription_list_line,
    subscription_list_identity,
)


logger = structlog.get_logger(__name__)

router = Router()

MY_SUBS_PAGE_SIZE = 5


def parse_my_subs_page(callback_data: str | None) -> int:
    """1-based page from my_subscriptions / ms_pg:N callbacks."""
    if not callback_data:
        return 1
    if callback_data.startswith('ms_pg:'):
        try:
            page = int(callback_data.split(':', 1)[1])
        except (TypeError, ValueError, IndexError):
            return 1
        return max(1, page)
    return 1


def paginate_items(items: list, page: int, page_size: int = MY_SUBS_PAGE_SIZE) -> tuple[list, int, int]:
    """Return (page_items, clamped_page, total_pages). Page is 1-based."""
    total = len(items)
    if total == 0:
        return [], 1, 1
    total_pages = (total + page_size - 1) // page_size
    page = min(max(1, page), total_pages)
    start = (page - 1) * page_size
    return items[start : start + page_size], page, total_pages


logger = structlog.get_logger(__name__)

router = Router()


def _subscription_status_display(sub, texts) -> str:
    if bool(getattr(sub, 'user_disabled', False)):
        return texts.t('SUBSCRIPTION_STATUS_USER_DISABLED')
    actual = sub.actual_status
    if actual == 'limited':
        return texts.t('SUBSCRIPTION_STATUS_LIMITED')
    if actual == 'disabled':
        return texts.t('SUBSCRIPTION_STATUS_DISABLED')
    if actual == 'expired':
        return texts.t('SUBSCRIPTION_STATUS_EXPIRED')
    if actual in ('active', 'trial'):
        if getattr(sub, 'is_trial', False):
            return texts.t('SUBSCRIPTION_STATUS_TRIAL')
        return texts.t('SUBSCRIPTION_STATUS_ACTIVE')
    return texts.t('SUBSCRIPTION_STATUS_UNKNOWN')


def _format_subscription_line(sub, idx: int, texts=None, language: str = 'ru', db_user=None) -> str:
    texts = texts or get_texts(language)
    user = db_user or SimpleNamespace(is_partner=False, panel_brand_prefix=None)
    return format_subscription_list_line(sub, idx, texts, texts.language, user)


def _build_subscriptions_keyboard(
    subscriptions: list,
    language: str,
    gift_enabled: bool = False,
    *,
    page: int = 1,
    total_pages: int = 1,
    db_user=None,
    show_search: bool = False,
    search_query: str = '',
) -> types.InlineKeyboardMarkup:
    """Build inline keyboard with per-subscription management buttons."""
    texts = get_texts(language)
    buttons = []
    for sub in subscriptions:
        label = subscription_list_identity(sub, db_user or SimpleNamespace(is_partner=False), texts)
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text=f'⚙️ {label}',
                    callback_data=f'sm:{sub.id}',
                )
            ]
        )

    buy_text = getattr(texts, 'MENU_BUY_SUBSCRIPTION', None) or texts.t('MY_SUB_BTN_BUY_ANOTHER')
    buttons.append(
        [
            types.InlineKeyboardButton(text=f'➕ {buy_text}', callback_data='menu_buy'),
        ]
    )
    if show_search:
        if search_query:
            buttons.append(
                [
                    types.InlineKeyboardButton(
                        text=texts.t('MY_SUB_SEARCH_RESET', '❌ Сбросить поиск'),
                        callback_data='my_subs_search_reset',
                    )
                ]
            )
        else:
            buttons.append(
                [
                    types.InlineKeyboardButton(
                        text=texts.t('MY_SUB_SEARCH', '🔍 Поиск'),
                        callback_data='my_subs_search',
                    )
                ]
            )
    if gift_enabled:
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('GIFT_SUBSCRIPTION_BUTTON', '🎁 Подарить подписку'),
                    callback_data='subscription_gift',
                )
            ]
        )
    if total_pages > 1:
        nav: list[types.InlineKeyboardButton] = []
        if page > 1:
            nav.append(types.InlineKeyboardButton(text='⬅️', callback_data=f'ms_pg:{page - 1}'))
        if page < total_pages:
            nav.append(types.InlineKeyboardButton(text='➡️', callback_data=f'ms_pg:{page + 1}'))
        if nav:
            buttons.append(nav)
    buttons.append(
        [
            types.InlineKeyboardButton(text=texts.t('MY_SUB_BACK'), callback_data='back_to_menu'),
        ]
    )

    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_subscription_detail_keyboard(sub_id: int, sub=None, *, language: str = 'ru') -> types.InlineKeyboardMarkup:
    """Build keyboard for single subscription management.

    For expired/disabled subscriptions, only 'Renew' and 'Back' are shown —
    connection link and traffic/device management are irrelevant.
    """
    texts = get_texts(language)
    if sub is not None and hasattr(sub, 'user_disabled') and getattr(sub, 'user_disabled', False):
        return types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t('MY_SUB_BTN_ENABLE', '🟢'),
                        callback_data=f'sub_enable:{sub_id}',
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t('MY_SUB_BTN_BACK_TO_LIST'),
                        callback_data='my_subscriptions',
                    )
                ],
            ]
        )

    is_inactive = sub is not None and sub.actual_status in ('expired', 'disabled')

    buttons = []

    if not is_inactive:
        buttons.append(
            [types.InlineKeyboardButton(text=texts.t('MY_SUB_BTN_CONNECT_LINK'), callback_data=f'sl:{sub_id}')]
        )

    buttons.append([types.InlineKeyboardButton(text=texts.t('MY_SUB_BTN_RENEW'), callback_data=f'se:{sub_id}')])

    if not is_inactive:
        buttons.append(
            [types.InlineKeyboardButton(text=texts.t('MY_SUB_BTN_AUTOPAY'), callback_data='subscription_autopay')]
        )
        buttons.append([types.InlineKeyboardButton(text=texts.t('MY_SUB_BTN_TRAFFIC'), callback_data=f'st:{sub_id}')])
        buttons.append([types.InlineKeyboardButton(text=texts.t('MY_SUB_BTN_DEVICES'), callback_data=f'sd:{sub_id}')])

    if is_inactive:
        buttons.append(
            [types.InlineKeyboardButton(text=texts.t('MY_SUB_BTN_DELETE'), callback_data=f'sub_del:{sub_id}')]
        )

    if not is_inactive and settings.is_subscription_revoke_enabled():
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('MY_SUB_BTN_REISSUE'),
                    callback_data=f'sr:{sub_id}',
                )
            ]
        )

    if (
        sub is not None
        and hasattr(sub, 'user_disabled')
        and sub.actual_status in ('active', 'trial', 'limited')
        and not getattr(sub, 'user_disabled', False)
    ):
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('MY_SUB_BTN_DISABLE', '⏸'),
                    callback_data=f'sub_disable:{sub_id}',
                )
            ]
        )

    buttons.append(
        [types.InlineKeyboardButton(text=texts.t('MY_SUB_BTN_BACK_TO_LIST'), callback_data='my_subscriptions')]
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

    texts = get_texts(db_user.language)
    gift_enabled = True
    subscriptions = await get_all_subscriptions_by_user_id(db, db_user.id)
    page = parse_my_subs_page(callback.data)

    search_query = ''
    if state:
        data = await state.get_data()
        search_query = (data.get('my_subs_search_query') or '').strip()

    if not subscriptions:
        text = texts.t('MY_SUB_LIST_EMPTY')
        buttons = [
            [types.InlineKeyboardButton(text=texts.t('MY_SUB_BTN_BUY'), callback_data='menu_buy')],
        ]
        if gift_enabled:
            buttons.append(
                [
                    types.InlineKeyboardButton(
                        text=texts.t('GIFT_SUBSCRIPTION_BUTTON', '🎁 Подарить подписку'),
                        callback_data='subscription_gift',
                    )
                ]
            )
        buttons.append([types.InlineKeyboardButton(text=texts.t('MY_SUB_BACK'), callback_data='back_to_menu')])
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    else:
        visible = (
            filter_subscriptions_by_query(subscriptions, search_query, texts, db_user)
            if search_query
            else subscriptions
        )
        if search_query and not visible:
            text = texts.t('MY_SUB_SEARCH_NO_RESULTS', 'Ничего не найдено.')
            page_items: list = []
            page = 1
            total_pages = 1
            keyboard = _build_subscriptions_keyboard(
                page_items,
                db_user.language,
                gift_enabled=gift_enabled,
                page=page,
                total_pages=total_pages,
                db_user=db_user,
                show_search=True,
                search_query=search_query,
            )
        else:
            page_items, page, total_pages = paginate_items(visible, page, MY_SUBS_PAGE_SIZE)
            start_idx = (page - 1) * MY_SUBS_PAGE_SIZE
            title = texts.t('MY_SUB_LIST_TITLE')
            lines = [f'{title} ({page}/{total_pages})\n']
            for idx, sub in enumerate(page_items, start_idx + 1):
                lines.append(format_subscription_list_line(sub, idx, texts, db_user.language, db_user))
                lines.append('')
            text = '\n'.join(lines)
            keyboard = _build_subscriptions_keyboard(
                page_items,
                db_user.language,
                gift_enabled=gift_enabled,
                page=page,
                total_pages=total_pages,
                db_user=db_user,
                show_search=True,
                search_query=search_query,
            )

    if callback.message:
        await edit_or_answer_photo(callback, text, keyboard, parse_mode='HTML')
    await callback.answer()


async def start_my_subs_search(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    await callback.answer()
    await state.set_state(SubscriptionStates.searching_my_subscriptions)
    await callback.message.answer(texts.t('MY_SUB_SEARCH_PROMPT', 'Введите текст поиска'))


async def reset_my_subs_search(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    await state.update_data(my_subs_search_query=None)
    await show_my_subscriptions(callback, db_user, db, state)


async def receive_my_subs_search(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    raw = (message.text or '').strip()
    if not raw:
        await message.answer(texts.t('MY_SUB_SEARCH_EMPTY_QUERY', '❌ Введите текст'))
        return
    await state.update_data(my_subs_search_query=raw)
    await state.set_state(None)
    safe = html.escape(raw)
    await message.answer(
        texts.t('MY_SUB_SEARCH_ACTIVE', 'Поиск: <b>{query}</b>').format(query=safe),
        parse_mode='HTML',
    )

    async def _noop_answer(*_args, **_kwargs) -> None:
        return None

    fake_callback = SimpleNamespace(
        data='my_subscriptions',
        message=message,
        answer=_noop_answer,
    )
    await show_my_subscriptions(fake_callback, db_user, db, state)


async def _render_subscription_detail(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    sub_id: int,
    *,
    answer: bool = True,
) -> None:
    """Render detail for an owned subscription id (IDOR protected)."""
    # Capture ids before any ORM IO — never expire_all() here: it expires db_user
    # and a later sync access to db_user.id raises MissingGreenlet (A4 / sm: crash).
    user_id = int(db_user.id)
    language = db_user.language
    subscription = await get_subscription_by_id_for_user(db, sub_id, user_id)

    if not subscription:
        await callback.answer(
            get_texts(language).t('SUBSCRIPTION_NOT_FOUND', 'Подписка не найдена'),
            show_alert=True,
        )
        return

    # Persist active sub_id so downstream handlers without sub_id in callback_data
    # (e.g. 'subscription_autopay') can resolve the right subscription via FSM.
    await state.update_data(active_subscription_id=sub_id)

    texts = get_texts(language)
    display_name = subscription_list_identity(subscription, db_user, texts)

    if subscription.traffic_limit_gb == 0:
        traffic = '∞'
    else:
        used = f'{subscription.traffic_used_gb:.1f}' if subscription.traffic_used_gb else '0'
        traffic = f'{used} / {subscription.traffic_limit_gb} GB'

    end_date = (
        format_user_datetime(subscription.end_date, language=language, fmt='%d.%m.%Y %H:%M')
        if subscription.end_date
        else '—'
    )
    status = _subscription_status_display(subscription, texts)
    devices = Texts.format_device_limit(subscription.device_limit)

    text = (
        f'📋 {texts.t("MY_SUB_DETAIL_HEADER").format(label=display_name)}\n\n'
        f'{texts.t("MY_SUB_DETAIL_STATUS").format(status=status)}\n'
        f'{texts.t("MY_SUB_DETAIL_TRAFFIC").format(traffic=traffic)}\n'
        f'{texts.t("MY_SUB_DETAIL_DEVICES").format(devices=devices)}\n'
        f'{texts.t("MY_SUB_DETAIL_UNTIL").format(end_date=end_date)}\n'
    )

    if subscription.subscription_url and not settings.should_hide_subscription_link():
        text += f'\n🔗 <code>{subscription.subscription_url}</code>'

    keyboard = _build_subscription_detail_keyboard(sub_id, sub=subscription, language=language)

    if callback.message:
        await edit_or_answer_photo(callback, text, keyboard, parse_mode='HTML')
    if answer:
        try:
            await callback.answer()
        except Exception:
            pass


async def show_subscription_detail(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    """Show detail view for a single subscription (IDOR protected)."""
    parts = (callback.data or '').split(':')
    if len(parts) < 2:
        await callback.answer('Неверный формат', show_alert=True)
        return

    try:
        sub_id = int(parts[1])
    except (TypeError, ValueError):
        await callback.answer('Неверный формат', show_alert=True)
        return

    await _render_subscription_detail(callback, db_user, db, state, sub_id, answer=True)

async def _resolve_and_store_sub(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> Subscription | None:
    """Extract sub_id from callback, validate ownership, store in FSM state."""
    sub_id = _extract_sub_id(callback)
    if sub_id is None:
        await callback.answer('Неверный формат', show_alert=True)
        return None

    subscription = await get_subscription_by_id_for_user(db, sub_id, db_user.id)
    if not subscription:
        await callback.answer('Подписка не найдена', show_alert=True)
        return None

    # Store in FSM state so downstream handlers can use it
    await state.update_data(active_subscription_id=sub_id)
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
    current_devices = Texts.format_device_limit(subscription.device_limit)
    text = texts.t('MY_SUB_DEVICES_MENU').format(current=current_devices)

    keyboard = []
    if can_buy_devices:
        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('MY_SUB_BTN_BUY_DEVICES'),
                    callback_data=f'change_devices_menu:{sub_id}',
                )
            ]
        )
    keyboard.append(
        [
            types.InlineKeyboardButton(
                text=texts.t('MY_SUB_BTN_MANAGE_DEVICES'),
                callback_data=f'device_management:{sub_id}',
            )
        ]
    )
    keyboard.append([types.InlineKeyboardButton(text=texts.t('MY_SUB_BACK'), callback_data=f'sm:{sub_id}')])

    await edit_or_answer_photo(
        callback,
        text,
        types.InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode='HTML',
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
    sub_id = _extract_sub_id(callback)
    if sub_id is None:
        await callback.answer('Неверный формат', show_alert=True)
        return

    subscription = await get_subscription_by_id_for_user(db, sub_id, db_user.id)
    if not subscription:
        await callback.answer('Подписка не найдена', show_alert=True)
        return

    if subscription.actual_status not in ('expired', 'disabled'):
        await callback.answer('Можно удалить только истекшую или отключённую подписку', show_alert=True)
        return

    tariff_name = subscription.tariff.name if subscription.tariff else 'Подписка'

    text = (
        f'🗑 <b>Удалить подписку «{tariff_name}»?</b>\n\n'
        '⚠️ Подписка будет удалена безвозвратно.\n'
        'Все данные, устройства и настройки будут потеряны.\n'
        'Это действие нельзя отменить.'
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text='🗑 Да, удалить', callback_data=f'sub_del_yes:{sub_id}')],
            [types.InlineKeyboardButton(text='◀️ Отмена', callback_data=f'sm:{sub_id}')],
        ]
    )

    if callback.message:
        await edit_or_answer_photo(callback, text, keyboard, parse_mode='HTML')
    await callback.answer()


async def handle_subscription_delete_execute(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    """Actually delete an expired/disabled subscription."""
    sub_id = _extract_sub_id(callback)
    if sub_id is None:
        await callback.answer('Неверный формат', show_alert=True)
        return

    subscription = await get_subscription_by_id_for_user(db, sub_id, db_user.id)
    if not subscription:
        await callback.answer('Подписка не найдена', show_alert=True)
        return

    deletable_statuses = {SubscriptionStatus.EXPIRED.value, SubscriptionStatus.DISABLED.value}
    if getattr(subscription, 'actual_status', subscription.status) not in deletable_statuses:
        await callback.answer('Можно удалить только истекшую или отключённую подписку', show_alert=True)
        return

    from app.services.grace_access_runtime import (
        GraceAccessDeletionBlocked,
        ensure_no_open_grace_for_subscriptions,
    )

    try:
        await ensure_no_open_grace_for_subscriptions(db, (subscription.id,))
    except GraceAccessDeletionBlocked:
        await callback.answer(
            'Подписку нельзя удалить, пока действует временный доступ для продления.',
            show_alert=True,
        )
        return

    # Best-effort: stop Platega SBP autopay before the row disappears — the
    # platega_subscriptions record CASCADE-deletes with it, so cancelling
    # after the delete would find nothing to cancel on Platega's side.
    # NOTE: this commits its own transaction internally, which releases the
    # grace-guard's Postgres advisory lock acquired just above. It therefore
    # runs BEFORE any irreversible panel/DB step, and the guard is
    # re-acquired immediately below — closing that window before anything
    # that can't be undone happens.
    from app.services.payment.lava import cancel_lava_recurring_for_subscription_safe
    from app.services.payment.platega import cancel_platega_recurring_for_subscription_safe

    await cancel_platega_recurring_for_subscription_safe(db, subscription.id)

    await cancel_lava_recurring_for_subscription_safe(db, subscription.id)
    try:
        await ensure_no_open_grace_for_subscriptions(db, (subscription.id,))
    except GraceAccessDeletionBlocked:
        await callback.answer(
            'Подписку нельзя удалить, пока действует временный доступ для продления.',
            show_alert=True,
        )
        return

    # Delete from RemnaWave panel (stops webhooks / phantom notifications)
    if subscription.remnawave_id:
        try:
            from app.services.remnawave_webhook_service import RemnaWaveWebhookService

            # Suppress the self-inflicted user.deleted webhook so its sibling-expiry
            # sweep never touches the user's other (still-active) subscriptions.
            # Только по панельному id: `id` — обязательное поле UsersSchema в
            # 3.0.0, поэтому этот уровень guard'а срабатывает всегда. Добавить
            # сюда telegram_id значило бы на 5 минут заглушить user.deleted для
            # ВСЕХ панельных аккаунтов этого пользователя — включая законное
            # удаление соседней подписки оператором.
            RemnaWaveWebhookService.mark_intentional_panel_deletion(
                panel_user_ids=[subscription.remnawave_id],
            )
            service = SubscriptionService()
            await service.delete_remnawave_user(subscription.remnawave_id)
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

    await callback.answer('Подписка удалена', show_alert=True)

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


async def handle_subscription_user_disable(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    """Confirm step before pausing (production pattern)."""
    texts = get_texts(db_user.language)
    sub_id = _extract_sub_id(callback)
    if sub_id is None:
        await callback.answer(texts.t('CB_INVALID_FORMAT', 'Неверный формат'), show_alert=True)
        return

    subscription = await get_subscription_by_id_for_user(db, sub_id, db_user.id)
    if not subscription:
        await callback.answer(texts.t('SUBSCRIPTION_NOT_FOUND', 'Подписка не найдена'), show_alert=True)
        return

    if subscription.actual_status not in ('active', 'trial', 'limited'):
        await callback.answer(
            texts.t('MY_SUB_DISABLE_NOT_ACTIVE', 'Отключить можно только активную подписку'),
            show_alert=True,
        )
        return

    display_name = subscription_list_identity(subscription, db_user, texts)
    text = texts.t(
        'MY_SUB_DISABLE_CONFIRM',
        '⏸ <b>اشتراک «{name}» متوقف شود؟</b>\n\n'
        'دسترسی VPN قطع می‌شود. هر زمان با «روشن کردن اشتراک» دوباره فعال می‌شود — بدون تمدید.',
    ).format(name=html.escape(display_name))

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t('MY_SUB_BTN_DISABLE_YES', '⏸ بله، متوقف کن'),
                    callback_data=f'sub_disable_yes:{sub_id}',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t('MY_SUB_BTN_BACK_TO_LIST', '◀️'),
                    callback_data=f'sm:{sub_id}',
                )
            ],
        ]
    )

    await callback.answer()
    if callback.message:
        await edit_or_answer_photo(callback, text, keyboard, parse_mode='HTML')


async def handle_subscription_user_disable_execute(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    sub_id = _extract_sub_id(callback)
    if sub_id is None:
        await callback.answer(texts.t('CB_INVALID_FORMAT', 'Неверный формат'), show_alert=True)
        return

    subscription = await get_subscription_by_id_for_user(db, sub_id, db_user.id)
    if not subscription:
        await callback.answer(texts.t('SUBSCRIPTION_NOT_FOUND', 'Подписка не найдена'), show_alert=True)
        return

    try:
        await disable_user_subscription(db, subscription, db_user)
    except SubscriptionToggleError as exc:
        error_key = 'MY_SUB_DISABLE_PANEL_ERROR' if exc.code == 'panel_error' else 'MY_SUB_DISABLE_NOT_ACTIVE'
        if exc.code == 'panel_error':
            error_default = '❌ Не удалось отключить VPN в панели'
        else:
            error_default = 'Отключить можно только активную подписку'
        await callback.answer(texts.t(error_key, error_default), show_alert=True)
        return

    try:
        await callback.answer(texts.t('MY_SUB_DISABLE_SUCCESS', '⏸ اشتراک متوقف شد'))
    except Exception:
        pass
    await _render_subscription_detail(callback, db_user, db, state, sub_id, answer=False)


async def handle_subscription_user_enable(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    sub_id = _extract_sub_id(callback)
    if sub_id is None:
        await callback.answer(texts.t('CB_INVALID_FORMAT', 'Неверный формат'), show_alert=True)
        return

    subscription = await get_subscription_by_id_for_user(db, sub_id, db_user.id)
    if not subscription:
        await callback.answer(texts.t('SUBSCRIPTION_NOT_FOUND', 'Подписка не найдена'), show_alert=True)
        return

    try:
        await enable_user_subscription(db, subscription, db_user)
    except SubscriptionToggleError as exc:
        enable_toasts = {
            'panel_error': ('MY_SUB_ENABLE_PANEL_ERROR', '❌ Не удалось включить VPN в панели'),
            'expired': ('MY_SUB_ENABLE_EXPIRED', 'Подписка истекла — продлите её'),
            'not_user_disabled': (
                'MY_SUB_ENABLE_NOT_USER_DISABLED',
                'Подписка не была отключена пользователем',
            ),
            'not_disabled': (
                'MY_SUB_ENABLE_NOT_DISABLED',
                'Подписка не находится в отключённом состоянии',
            ),
        }
        error_key, error_default = enable_toasts.get(exc.code, ('MY_SUB_ENABLE_PANEL_ERROR', exc.message))
        await callback.answer(texts.t(error_key, error_default), show_alert=True)
        return

    try:
        await callback.answer(texts.t('MY_SUB_ENABLE_SUCCESS', '🟢 اشتراک روشن شد'))
    except Exception:
        pass
    await _render_subscription_detail(callback, db_user, db, state, sub_id, answer=False)
