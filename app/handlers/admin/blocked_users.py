"""
Хендлеры админ-панели для управления заблокированными пользователями.

Позволяет сканировать пользователей, выявлять тех, кто заблокировал бота,
и выполнять очистку БД и панели Remnawave.
"""

import html
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.localization.texts import get_texts
from app.services.blocked_users_service import (
    BlockCheckResult,
    BlockedUserAction,
    BlockedUsersService,
)
from app.utils.decorators import admin_required, error_handler


logger = structlog.get_logger(__name__)


# =============================================================================
# Enums для текстов и callback_data
# =============================================================================


class BlockedUsersText(Enum):
    """Fallback Cyrillic strings for blocked-users admin module."""

    MENU_TITLE = 'ADMIN_BLOCKED_MENU_TITLE'
    MENU_DESCRIPTION = 'ADMIN_BLOCKED_MENU_DESC'
    SCAN_STARTED = 'ADMIN_BLOCKED_SCAN_STARTED'
    SCAN_PROGRESS = 'ADMIN_BLOCKED_SCAN_PROGRESS'
    SCAN_COMPLETE = 'ADMIN_BLOCKED_SCAN_COMPLETE'
    SCAN_NO_BLOCKED = 'ADMIN_BLOCKED_SCAN_NONE'
    BLOCKED_LIST_TITLE = 'ADMIN_BLOCKED_LIST_TITLE'
    BLOCKED_USER_ROW = 'ADMIN_BLOCKED_USER_ROW'
    CLEANUP_CONFIRM_TITLE = 'ADMIN_BLOCKED_CONFIRM_TITLE'
    CLEANUP_CONFIRM_DELETE_DB = 'ADMIN_BLOCKED_CONFIRM_DB'
    CLEANUP_CONFIRM_DELETE_REMNAWAVE = 'ADMIN_BLOCKED_CONFIRM_RW'
    CLEANUP_CONFIRM_DELETE_BOTH = 'ADMIN_BLOCKED_CONFIRM_BOTH'
    CLEANUP_CONFIRM_MARK = 'ADMIN_BLOCKED_CONFIRM_MARK'
    CLEANUP_PROGRESS = 'ADMIN_BLOCKED_CLEANUP_PROGRESS'
    CLEANUP_COMPLETE = 'ADMIN_BLOCKED_CLEANUP_COMPLETE'
    BUTTON_START_SCAN = 'ADMIN_BLOCKED_BTN_SCAN'
    BUTTON_VIEW_BLOCKED = 'ADMIN_BLOCKED_BTN_LIST'
    BUTTON_DELETE_DB = 'ADMIN_BLOCKED_BTN_DELETE_DB'
    BUTTON_DELETE_REMNAWAVE = 'ADMIN_BLOCKED_BTN_DELETE_RW'
    BUTTON_DELETE_BOTH = 'ADMIN_BLOCKED_BTN_DELETE_BOTH'
    BUTTON_MARK_BLOCKED = 'ADMIN_BLOCKED_BTN_MARK'
    BUTTON_CONFIRM = 'ADMIN_BLOCKED_BTN_CONFIRM'
    BUTTON_CANCEL = 'ADMIN_BLOCKED_BTN_CANCEL'
    BUTTON_BACK = 'ADMIN_BLOCKED_BTN_BACK'
    BUTTON_BACK_TO_USERS = 'ADMIN_BLOCKED_BTN_BACK_USERS'


_BLOCKED_FALLBACKS = {
    'ADMIN_BLOCKED_MENU_TITLE': '🔒 <b>Проверка заблокированных пользователей</b>',
    'ADMIN_BLOCKED_MENU_DESC': (
        '\n\nЗдесь вы можете проверить, какие пользователи заблокировали бота, '
        'и очистить их из базы данных и панели Remnawave.\n\n'
        '<b>Как это работает:</b>\n'
        '1. Сканирование отправляет тестовый запрос каждому пользователю\n'
        '2. Если пользователь заблокировал бота - получаем ошибку\n'
        '3. Можно удалить таких пользователей из БД и/или Remnawave'
    ),
    'ADMIN_BLOCKED_SCAN_STARTED': '🔄 <b>Сканирование запущено...</b>\n\nЭто может занять несколько минут.',
    'ADMIN_BLOCKED_SCAN_PROGRESS': '🔄 <b>Сканирование:</b> {checked}/{total} ({percent}%)',
    'ADMIN_BLOCKED_SCAN_COMPLETE': (
        '✅ <b>Сканирование завершено</b>\n\n'
        '📊 <b>Результаты:</b>\n'
        '• Проверено: {total_checked}\n'
        '• Заблокировали бота: {blocked_count}\n'
        '• Активных: {active_users}\n'
        '• Ошибок: {errors}\n'
        '• Без Telegram ID: {skipped}\n\n'
        '⏱ Время сканирования: {duration:.1f}с'
    ),
    'ADMIN_BLOCKED_SCAN_NONE': '✅ <b>Отлично!</b>\n\nНе найдено пользователей, заблокировавших бота.',
    'ADMIN_BLOCKED_LIST_TITLE': '🔒 <b>Заблокированные пользователи</b> ({count})\n\n',
    'ADMIN_BLOCKED_USER_ROW': '• {name} (ID: <code>{telegram_id}</code>)\n',
    'ADMIN_BLOCKED_CONFIRM_TITLE': '⚠️ <b>Подтверждение действия</b>\n\n',
    'ADMIN_BLOCKED_CONFIRM_DB': (
        'Вы собираетесь <b>удалить из БД</b> {count} пользователей.\n'
        'Это действие необратимо!\n\n'
        'Будут удалены:\n'
        '• Профили пользователей\n'
        '• Подписки\n'
        '• Транзакции\n'
        '• Реферальные данные'
    ),
    'ADMIN_BLOCKED_CONFIRM_RW': (
        'Вы собираетесь <b>удалить из Remnawave</b> {count} пользователей.\nИх VPN доступ будет полностью отключен.'
    ),
    'ADMIN_BLOCKED_CONFIRM_BOTH': (
        'Вы собираетесь <b>полностью удалить</b> {count} пользователей:\n'
        '• Из базы данных бота\n'
        '• Из панели Remnawave\n\n'
        'Это действие необратимо!'
    ),
    'ADMIN_BLOCKED_CONFIRM_MARK': (
        'Вы собираетесь <b>пометить как заблокированных</b> {count} пользователей.\n'
        'Они останутся в БД, но будут помечены статусом "blocked".'
    ),
    'ADMIN_BLOCKED_CLEANUP_PROGRESS': '🗑 <b>Очистка:</b> {processed}/{total}',
    'ADMIN_BLOCKED_CLEANUP_COMPLETE': (
        '✅ <b>Очистка завершена</b>\n\n'
        '📊 <b>Результаты:</b>\n'
        '• Удалено из БД: {deleted_db}\n'
        '• Удалено из Remnawave: {deleted_remnawave}\n'
        '• Помечено как заблокированные: {marked}\n'
        '• Ошибок: {errors}'
    ),
    'ADMIN_BLOCKED_BTN_SCAN': '🔍 Начать сканирование',
    'ADMIN_BLOCKED_BTN_LIST': '👥 Список заблокированных ({count})',
    'ADMIN_BLOCKED_BTN_DELETE_DB': '🗑 Удалить из БД',
    'ADMIN_BLOCKED_BTN_DELETE_RW': '🌐 Удалить из Remnawave',
    'ADMIN_BLOCKED_BTN_DELETE_BOTH': '💀 Удалить везде',
    'ADMIN_BLOCKED_BTN_MARK': '🚫 Пометить как заблокированных',
    'ADMIN_BLOCKED_BTN_CONFIRM': '✅ Подтвердить',
    'ADMIN_BLOCKED_BTN_CANCEL': '❌ Отмена',
    'ADMIN_BLOCKED_BTN_BACK': '⬅️ Назад',
    'ADMIN_BLOCKED_BTN_BACK_USERS': '⬅️ К пользователям',
}


def _blocked_t(texts, key: str, **kwargs) -> str:
    msg = texts.t(key, _BLOCKED_FALLBACKS[key])
    return msg.format(**kwargs) if kwargs else msg


class BlockedUsersCallback(Enum):
    """Callback data для кнопок модуля."""

    MENU = 'admin_blocked_users'
    START_SCAN = 'admin_blocked_scan'
    VIEW_LIST = 'admin_blocked_list'
    VIEW_LIST_PAGE = 'admin_blocked_list_page_'
    ACTION_DELETE_DB = 'admin_blocked_action_db'
    ACTION_DELETE_REMNAWAVE = 'admin_blocked_action_rw'
    ACTION_DELETE_BOTH = 'admin_blocked_action_both'
    ACTION_MARK = 'admin_blocked_action_mark'
    CONFIRM_PREFIX = 'admin_blocked_confirm_'
    CANCEL = 'admin_blocked_cancel'


# =============================================================================
# FSM States
# =============================================================================


class BlockedUsersStates(StatesGroup):
    """Состояния FSM для модуля заблокированных пользователей."""

    scanning = State()
    viewing_results = State()
    confirming_action = State()
    processing_cleanup = State()


# =============================================================================
# Keyboards
# =============================================================================


def get_blocked_users_menu_keyboard(
    language: str = 'ru',
    scan_result: dict[str, Any] | None = None,
) -> InlineKeyboardMarkup:
    """Клавиатура главного меню модуля."""
    texts = get_texts(language)
    buttons = [
        [
            InlineKeyboardButton(
                text=_blocked_t(texts, BlockedUsersText.BUTTON_START_SCAN.value),
                callback_data=BlockedUsersCallback.START_SCAN.value,
            )
        ]
    ]

    blocked_count = scan_result.get('blocked_count', 0) if scan_result else 0
    if blocked_count > 0:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=_blocked_t(texts, BlockedUsersText.BUTTON_VIEW_BLOCKED.value, count=blocked_count),
                    callback_data=BlockedUsersCallback.VIEW_LIST.value,
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text=_blocked_t(texts, BlockedUsersText.BUTTON_BACK_TO_USERS.value),
                callback_data='admin_users',
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_blocked_list_keyboard(
    language: str = 'ru',
    page: int = 1,
    total_pages: int = 1,
    has_blocked: bool = True,
) -> InlineKeyboardMarkup:
    """Клавиатура списка заблокированных пользователей."""
    texts = get_texts(language)
    buttons = []

    # Пагинация
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(
                InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{BlockedUsersCallback.VIEW_LIST_PAGE.value}{page - 1}',
                )
            )
        nav_row.append(
            InlineKeyboardButton(
                text=f'{page}/{total_pages}',
                callback_data='noop',
            )
        )
        if page < total_pages:
            nav_row.append(
                InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{BlockedUsersCallback.VIEW_LIST_PAGE.value}{page + 1}',
                )
            )
        buttons.append(nav_row)

    # Действия
    if has_blocked:
        buttons.extend(
            [
                [
                    InlineKeyboardButton(
                        text=_blocked_t(texts, BlockedUsersText.BUTTON_DELETE_DB.value),
                        callback_data=BlockedUsersCallback.ACTION_DELETE_DB.value,
                    ),
                    InlineKeyboardButton(
                        text=_blocked_t(texts, BlockedUsersText.BUTTON_DELETE_REMNAWAVE.value),
                        callback_data=BlockedUsersCallback.ACTION_DELETE_REMNAWAVE.value,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=_blocked_t(texts, BlockedUsersText.BUTTON_DELETE_BOTH.value),
                        callback_data=BlockedUsersCallback.ACTION_DELETE_BOTH.value,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=_blocked_t(texts, BlockedUsersText.BUTTON_MARK_BLOCKED.value),
                        callback_data=BlockedUsersCallback.ACTION_MARK.value,
                    ),
                ],
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text=_blocked_t(texts, BlockedUsersText.BUTTON_BACK.value),
                callback_data=BlockedUsersCallback.MENU.value,
            )
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_keyboard(action: BlockedUserAction, language: str = 'ru') -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия."""
    texts = get_texts(language)
    action_map = {
        BlockedUserAction.DELETE_FROM_DB: 'db',
        BlockedUserAction.DELETE_FROM_REMNAWAVE: 'rw',
        BlockedUserAction.DELETE_BOTH: 'both',
        BlockedUserAction.MARK_AS_BLOCKED: 'mark',
    }

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_blocked_t(texts, BlockedUsersText.BUTTON_CONFIRM.value),
                    callback_data=f'{BlockedUsersCallback.CONFIRM_PREFIX.value}{action_map[action]}',
                ),
                InlineKeyboardButton(
                    text=_blocked_t(texts, BlockedUsersText.BUTTON_CANCEL.value),
                    callback_data=BlockedUsersCallback.CANCEL.value,
                ),
            ]
        ]
    )


# =============================================================================
# Handlers
# =============================================================================


@admin_required
@error_handler
async def show_blocked_users_menu(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    """Показывает главное меню модуля заблокированных пользователей."""
    texts = get_texts(db_user.language)
    data = await state.get_data()
    scan_result = data.get('blocked_users_scan_result')

    text = _blocked_t(texts, BlockedUsersText.MENU_TITLE.value) + _blocked_t(
        texts, BlockedUsersText.MENU_DESCRIPTION.value
    )

    if scan_result:
        text += texts.t(
            'ADMIN_BLOCKED_LAST_SCAN',
            '\n\n📊 <b>Последнее сканирование:</b>\n• Заблокированных: {blocked}\n• Активных: {active}',
        ).format(blocked=scan_result.get('blocked_count', 0), active=scan_result.get('active_users', 0))

    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_blocked_users_menu_keyboard(db_user.language, scan_result),
    )
    await callback.answer()


@admin_required
@error_handler
async def start_scan(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    """Запускает сканирование пользователей."""
    texts = get_texts(db_user.language)
    await state.set_state(BlockedUsersStates.scanning)

    await callback.message.edit_text(
        _blocked_t(texts, BlockedUsersText.SCAN_STARTED.value),
        parse_mode=ParseMode.HTML,
    )

    service = BlockedUsersService(bot)
    last_update_time = datetime.now(tz=UTC)

    async def progress_callback(checked: int, total: int) -> None:
        nonlocal last_update_time
        now = datetime.now(tz=UTC)
        # Обновляем сообщение не чаще раза в 3 секунды
        if (now - last_update_time).total_seconds() >= 3:
            last_update_time = now
            percent = int(checked / total * 100) if total > 0 else 0
            try:
                await callback.message.edit_text(
                    _blocked_t(
                        texts,
                        BlockedUsersText.SCAN_PROGRESS.value,
                        checked=checked,
                        total=total,
                        percent=percent,
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass  # Игнорируем ошибки обновления сообщения

    # Выполняем сканирование
    result = await service.scan_all_users(
        db,
        only_active=True,
        progress_callback=progress_callback,
    )

    # Сериализуем результат в dict для Redis и keyboard
    scan_result_dict = {
        'total_checked': result.total_checked,
        'blocked_count': result.blocked_count,
        'active_users': result.active_users,
        'errors': result.errors,
        'skipped_no_telegram': result.skipped_no_telegram,
        'scan_duration_seconds': result.scan_duration_seconds,
    }

    # Сохраняем результат в state
    await state.update_data(
        blocked_users_scan_result=scan_result_dict,
        blocked_users_list=[
            {
                'user_id': u.user_id,
                'telegram_id': u.telegram_id,
                'username': u.username,
                'full_name': u.full_name,
                'remnawave_uuid': u.remnawave_uuid,
            }
            for u in result.blocked_users
        ],
    )

    await state.set_state(BlockedUsersStates.viewing_results)

    # Формируем итоговое сообщение
    if result.blocked_count == 0:
        text = _blocked_t(texts, BlockedUsersText.SCAN_NO_BLOCKED.value)
    else:
        text = _blocked_t(
            texts,
            BlockedUsersText.SCAN_COMPLETE.value,
            total_checked=result.total_checked,
            blocked_count=result.blocked_count,
            active_users=result.active_users,
            errors=result.errors,
            skipped=result.skipped_no_telegram,
            duration=result.scan_duration_seconds,
        )

    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_blocked_users_menu_keyboard(db_user.language, scan_result_dict),
    )
    await callback.answer()


@admin_required
@error_handler
async def show_blocked_list(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    page: int = 1,
) -> None:
    """Показывает список заблокированных пользователей."""
    texts = get_texts(db_user.language)
    data = await state.get_data()
    blocked_list: list[dict[str, Any]] = data.get('blocked_users_list', [])

    if not blocked_list:
        await callback.answer(
            texts.t('ADMIN_BLOCKED_LIST_EMPTY', 'Нет заблокированных пользователей'),
            show_alert=True,
        )
        return

    # Пагинация
    per_page = 15
    total_pages = (len(blocked_list) + per_page - 1) // per_page
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_users = blocked_list[start_idx:end_idx]

    text = _blocked_t(texts, BlockedUsersText.BLOCKED_LIST_TITLE.value, count=len(blocked_list))

    for user_data in page_users:
        name = user_data.get('full_name') or user_data.get('username') or texts.t('ADMIN_BLOCKED_NO_NAME', 'Без имени')
        telegram_id = user_data.get('telegram_id', '?')
        text += _blocked_t(
            texts,
            BlockedUsersText.BLOCKED_USER_ROW.value,
            name=html.escape(name),
            telegram_id=telegram_id,
        )

    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_blocked_list_keyboard(db_user.language, page, total_pages, bool(blocked_list)),
    )
    await callback.answer()


@admin_required
@error_handler
async def handle_blocked_list_pagination(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    """Обрабатывает пагинацию списка заблокированных."""
    try:
        page = int(callback.data.split('_')[-1])
    except (ValueError, IndexError):
        page = 1

    await show_blocked_list(callback, db_user, state, page)


@admin_required
@error_handler
async def show_action_confirm(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    action: BlockedUserAction,
) -> None:
    """Показывает подтверждение действия."""
    texts = get_texts(db_user.language)
    data = await state.get_data()
    blocked_list = data.get('blocked_users_list', [])
    count = len(blocked_list)

    if count == 0:
        await callback.answer(
            texts.t('ADMIN_BLOCKED_NONE_TO_PROCESS', 'Нет пользователей для обработки'),
            show_alert=True,
        )
        return

    await state.set_state(BlockedUsersStates.confirming_action)
    await state.update_data(pending_action=action.value)

    text = _blocked_t(texts, BlockedUsersText.CLEANUP_CONFIRM_TITLE.value)

    if action == BlockedUserAction.DELETE_FROM_DB:
        text += _blocked_t(texts, BlockedUsersText.CLEANUP_CONFIRM_DELETE_DB.value, count=count)
    elif action == BlockedUserAction.DELETE_FROM_REMNAWAVE:
        text += _blocked_t(texts, BlockedUsersText.CLEANUP_CONFIRM_DELETE_REMNAWAVE.value, count=count)
    elif action == BlockedUserAction.DELETE_BOTH:
        text += _blocked_t(texts, BlockedUsersText.CLEANUP_CONFIRM_DELETE_BOTH.value, count=count)
    elif action == BlockedUserAction.MARK_AS_BLOCKED:
        text += _blocked_t(texts, BlockedUsersText.CLEANUP_CONFIRM_MARK.value, count=count)

    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_confirm_keyboard(action, db_user.language),
    )
    await callback.answer()


@admin_required
@error_handler
async def handle_action_delete_db(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    """Обрабатывает выбор удаления из БД."""
    await show_action_confirm(callback, db_user, state, BlockedUserAction.DELETE_FROM_DB)


@admin_required
@error_handler
async def handle_action_delete_remnawave(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    """Обрабатывает выбор удаления из Remnawave."""
    await show_action_confirm(callback, db_user, state, BlockedUserAction.DELETE_FROM_REMNAWAVE)


@admin_required
@error_handler
async def handle_action_delete_both(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    """Обрабатывает выбор полного удаления."""
    await show_action_confirm(callback, db_user, state, BlockedUserAction.DELETE_BOTH)


@admin_required
@error_handler
async def handle_action_mark(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    """Обрабатывает выбор пометки как заблокированных."""
    await show_action_confirm(callback, db_user, state, BlockedUserAction.MARK_AS_BLOCKED)


@admin_required
@error_handler
async def handle_confirm_action(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    """Выполняет подтвержденное действие."""
    texts = get_texts(db_user.language)
    data = await state.get_data()
    blocked_list = data.get('blocked_users_list', [])

    # Определяем действие из callback_data
    action_code = callback.data.replace(BlockedUsersCallback.CONFIRM_PREFIX.value, '')
    action_map = {
        'db': BlockedUserAction.DELETE_FROM_DB,
        'rw': BlockedUserAction.DELETE_FROM_REMNAWAVE,
        'both': BlockedUserAction.DELETE_BOTH,
        'mark': BlockedUserAction.MARK_AS_BLOCKED,
    }
    action = action_map.get(action_code)

    if not action:
        await callback.answer(texts.t('ADMIN_BLOCKED_UNKNOWN_ACTION', 'Неизвестное действие'), show_alert=True)
        return

    if not blocked_list:
        await callback.answer(
            texts.t('ADMIN_BLOCKED_NONE_TO_PROCESS', 'Нет пользователей для обработки'),
            show_alert=True,
        )
        return

    await state.set_state(BlockedUsersStates.processing_cleanup)

    # Преобразуем обратно в BlockCheckResult
    blocked_results = [
        BlockCheckResult(
            user_id=u['user_id'],
            telegram_id=u['telegram_id'],
            username=u['username'],
            full_name=u['full_name'],
            status=None,  # type: ignore
            remnawave_uuid=u['remnawave_uuid'],
        )
        for u in blocked_list
    ]

    service = BlockedUsersService(bot)
    last_update_time = datetime.now(tz=UTC)

    async def progress_callback(processed: int, total_count: int) -> None:
        nonlocal last_update_time
        now = datetime.now(tz=UTC)
        if (now - last_update_time).total_seconds() >= 2:
            last_update_time = now
            try:
                await callback.message.edit_text(
                    _blocked_t(
                        texts,
                        BlockedUsersText.CLEANUP_PROGRESS.value,
                        processed=processed,
                        total=total_count,
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

    # Выполняем очистку
    result = await service.cleanup_blocked_users(
        db,
        blocked_results,
        action,
        progress_callback=progress_callback,
    )

    # Очищаем сохраненные данные
    await state.update_data(
        blocked_users_scan_result=None,
        blocked_users_list=[],
        pending_action=None,
    )
    await state.set_state(None)

    # Показываем результат
    text = _blocked_t(
        texts,
        BlockedUsersText.CLEANUP_COMPLETE.value,
        deleted_db=result.deleted_from_db,
        deleted_remnawave=result.deleted_from_remnawave,
        marked=result.marked_as_blocked,
        errors=len(result.errors),
    )

    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_blocked_users_menu_keyboard(db_user.language),
    )

    logger.info(
        'Очистка заблокированных пользователей завершена: DB=, RW=, marked=, errors',
        deleted_from_db=result.deleted_from_db,
        deleted_from_remnawave=result.deleted_from_remnawave,
        marked_as_blocked=result.marked_as_blocked,
        errors_count=len(result.errors),
    )

    await callback.answer()


@admin_required
@error_handler
async def handle_cancel(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
) -> None:
    """Отменяет текущее действие и возвращает в меню."""
    await state.update_data(pending_action=None)
    await state.set_state(BlockedUsersStates.viewing_results)
    await show_blocked_users_menu(callback, db_user, state)


# =============================================================================
# Registration
# =============================================================================


def register_handlers(dp: Dispatcher) -> None:
    """Регистрирует хендлеры модуля заблокированных пользователей."""

    # Главное меню
    dp.callback_query.register(
        show_blocked_users_menu,
        F.data == BlockedUsersCallback.MENU.value,
    )

    # Сканирование
    dp.callback_query.register(
        start_scan,
        F.data == BlockedUsersCallback.START_SCAN.value,
    )

    # Список заблокированных
    dp.callback_query.register(
        show_blocked_list,
        F.data == BlockedUsersCallback.VIEW_LIST.value,
    )

    # Пагинация списка
    dp.callback_query.register(
        handle_blocked_list_pagination,
        F.data.startswith(BlockedUsersCallback.VIEW_LIST_PAGE.value),
    )

    # Выбор действий
    dp.callback_query.register(
        handle_action_delete_db,
        F.data == BlockedUsersCallback.ACTION_DELETE_DB.value,
    )
    dp.callback_query.register(
        handle_action_delete_remnawave,
        F.data == BlockedUsersCallback.ACTION_DELETE_REMNAWAVE.value,
    )
    dp.callback_query.register(
        handle_action_delete_both,
        F.data == BlockedUsersCallback.ACTION_DELETE_BOTH.value,
    )
    dp.callback_query.register(
        handle_action_mark,
        F.data == BlockedUsersCallback.ACTION_MARK.value,
    )

    # Подтверждение действий
    dp.callback_query.register(
        handle_confirm_action,
        F.data.startswith(BlockedUsersCallback.CONFIRM_PREFIX.value),
    )

    # Отмена
    dp.callback_query.register(
        handle_cancel,
        F.data == BlockedUsersCallback.CANCEL.value,
    )
