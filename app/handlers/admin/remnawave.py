import html
import math
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.server_squad import (
    count_active_users_for_squad,
    get_all_server_squads,
    get_server_squad_by_uuid,
)
from app.database.models import User
from app.keyboards.admin import (
    get_admin_remnawave_keyboard,
    get_node_management_keyboard,
    get_squad_edit_keyboard,
    get_squad_management_keyboard,
)
from app.localization.texts import get_texts
from app.services.remnawave_service import RemnaWaveConfigurationError, RemnaWaveService
from app.services.remnawave_sync_service import (
    RemnaWaveAutoSyncStatus,
    remnawave_sync_service,
)
from app.services.system_settings_service import bot_configuration_service
from app.states import (
    RemnaWaveSyncStates,
    SquadCreateStates,
    SquadMigrationStates,
    SquadRenameStates,
)
from app.utils.decorators import admin_required, error_handler
from app.utils.formatters import format_bytes, format_datetime
from app.utils.jalali_datetime import format_user_datetime


def _rw_yes_no(texts, value: bool) -> str:
    return texts.t('ADMIN_RW_YES', 'Да') if value else texts.t('ADMIN_RW_NO', 'Нет')


def _rw_xray_state(texts, running: bool) -> str:
    return (
        texts.t('ADMIN_RW_XRAY_RUNNING', 'Запущен')
        if running
        else texts.t('ADMIN_RW_XRAY_STOPPED', 'Остановлен')
    )


def _rw_format_dt(dt, language: str) -> str:
    if not dt:
        return '—'
    if language == 'fa':
        return format_user_datetime(dt, language=language)
    return format_datetime(dt)


def _rw_connected(texts, connected: bool) -> str:
    return (
        texts.t('ADMIN_RW_CONNECTED', '📡 Да')
        if connected
        else texts.t('ADMIN_RW_NOT_CONNECTED', '📵 Нет')
    )


def _rw_disabled_flag(texts, disabled: bool) -> str:
    return (
        texts.t('ADMIN_RW_DISABLED_YES', '❌ Да')
        if disabled
        else texts.t('ADMIN_RW_DISABLED_NO', '✅ Нет')
    )


def _rw_tracking(texts, active: bool) -> str:
    return (
        texts.t('ADMIN_RW_ACTIVE', '✅ Активен')
        if active
        else texts.t('ADMIN_RW_INACTIVE', '❌ Отключен')
    )


def _rw_traffic_limit(texts, limit_bytes) -> str:
    if limit_bytes:
        return format_bytes(limit_bytes)
    return texts.t('ADMIN_RW_NO_LIMIT', 'Без лимита')


def _rw_format_traffic_change(difference_str: str) -> str:
    if not difference_str or difference_str == '0':
        return ''
    if difference_str.startswith('-'):
        return f' (🔻 {difference_str[1:]})'
    return f' (🔺 {difference_str})'


def _rw_node_action_label(texts, action: str) -> str:
    action_map = {
        'enable': texts.t('ADMIN_RW_NODE_ACTION_ENABLE', 'включена'),
        'disable': texts.t('ADMIN_RW_NODE_ACTION_DISABLE', 'отключена'),
        'restart': texts.t('ADMIN_RW_NODE_ACTION_RESTART', 'перезагружена'),
    }
    return action_map.get(action, texts.t('ADMIN_RW_NODE_ACTION_DEFAULT', 'обработана'))

def _build_node_detail_text(texts, node: dict, *, language: str, include_versions: bool = True) -> str:
    status_emoji = '🟢' if node['is_node_online'] else '🔴'
    xray_emoji = '✅' if node['is_xray_running'] else '❌'
    status_change = _rw_format_dt(node.get('last_status_change'), language)
    created_at = _rw_format_dt(node.get('created_at'), language)
    updated_at = _rw_format_dt(node.get('updated_at'), language)
    notify_percent = f'{node["notify_percent"]}%' if node.get('notify_percent') is not None else '—'
    sys_info = (node.get('system') or {}).get('info', {})
    cpu_model = html.escape(str(sys_info.get('cpuModel') or '—'))
    cpu_count = sys_info.get('cpus', 0)
    cpu_info = f'{cpu_count}x {cpu_model}' if cpu_count else cpu_model
    memory_total = sys_info.get('memoryTotal', 0)
    total_ram = format_bytes(memory_total) if memory_total else '—'
    versions = node.get('versions') or {}
    xray_ver = html.escape(str(versions.get('xray') or '—'))
    node_ver = html.escape(str(versions.get('node') or '—'))
    xray_uptime_sec = node.get('xray_uptime', 0)
    if xray_uptime_sec:
        days, rem = divmod(int(xray_uptime_sec), 86400)
        hours, rem = divmod(rem, 3600)
        mins = rem // 60
        xray_uptime_str = f'{days}d {hours}h {mins}m' if days else (f'{hours}h {mins}m' if hours else f'{mins}m')
    else:
        xray_uptime_str = '—'

    text = texts.t('ADMIN_RW_NODE_DETAIL_TITLE', '🖥️ <b>Нода: {name}</b>').format(
        name=html.escape(node['name'])
    ) + '\n\n'
    text += texts.t('ADMIN_RW_NODE_STATUS_HEADER', '<b>Статус:</b>') + '\n'
    text += texts.t('ADMIN_RW_NODE_ONLINE', '- Онлайн: {emoji} {value}').format(
        emoji=status_emoji, value=_rw_yes_no(texts, node['is_node_online'])
    ) + '\n'
    text += texts.t('ADMIN_RW_NODE_XRAY', '- Xray: {emoji} {value}').format(
        emoji=xray_emoji, value=_rw_xray_state(texts, node['is_xray_running'])
    ) + '\n'
    text += texts.t('ADMIN_RW_NODE_CONNECTED', '- Подключена: {value}').format(
        value=_rw_connected(texts, node['is_connected'])
    ) + '\n'
    text += texts.t('ADMIN_RW_NODE_DISABLED', '- Отключена: {value}').format(
        value=_rw_disabled_flag(texts, node['is_disabled'])
    ) + '\n'
    text += texts.t('ADMIN_RW_NODE_STATUS_CHANGE', '- Изменение статуса: {time}').format(time=status_change) + '\n'
    text += texts.t('ADMIN_RW_NODE_MESSAGE', '- Сообщение: {message}').format(
        message=html.escape(str(node.get('last_status_message') or '—'))
    ) + '\n'
    text += texts.t('ADMIN_RW_NODE_XRAY_UPTIME', '- Uptime Xray: {uptime}').format(uptime=xray_uptime_str) + '\n'

    if include_versions:
        text += '\n' + texts.t('ADMIN_RW_NODE_VERSIONS', '<b>Версии:</b>') + '\n'
        text += texts.t('ADMIN_RW_NODE_XRAY_VER', '- Xray: {version}').format(version=xray_ver) + '\n'
        text += texts.t('ADMIN_RW_NODE_VER', '- Node: {version}').format(version=node_ver) + '\n'

    text += '\n' + texts.t('ADMIN_RW_NODE_INFO', '<b>Информация:</b>') + '\n'
    text += texts.t('ADMIN_RW_NODE_ADDRESS', '- Адрес: {address}').format(address=html.escape(node['address'])) + '\n'
    text += texts.t('ADMIN_RW_NODE_COUNTRY', '- Страна: {code}').format(code=html.escape(node['country_code'])) + '\n'
    text += texts.t('ADMIN_RW_NODE_USERS', '- Пользователей онлайн: {count}').format(count=node['users_online']) + '\n'
    text += texts.t('ADMIN_RW_NODE_CPU', '- CPU: {info}').format(info=cpu_info) + '\n'
    text += texts.t('ADMIN_RW_NODE_RAM', '- RAM: {ram}').format(ram=total_ram) + '\n'
    text += texts.t('ADMIN_RW_NODE_PROVIDER', '- Провайдер: {provider}').format(
        provider=html.escape(str(node.get('provider_uuid') or '—'))
    ) + '\n'
    text += '\n' + texts.t('ADMIN_RW_NODE_TRAFFIC_HEADER', '<b>Трафик:</b>') + '\n'
    text += texts.t('ADMIN_RW_NODE_TRAFFIC_USED', '- Использовано: {value}').format(
        value=format_bytes(node['traffic_used_bytes'])
    ) + '\n'
    text += texts.t('ADMIN_RW_NODE_TRAFFIC_LIMIT', '- Лимит: {value}').format(
        value=_rw_traffic_limit(texts, node['traffic_limit_bytes'])
    ) + '\n'
    text += texts.t('ADMIN_RW_NODE_TRACKING', '- Трекинг: {value}').format(
        value=_rw_tracking(texts, node.get('is_traffic_tracking_active'))
    ) + '\n'
    text += texts.t('ADMIN_RW_NODE_RESET_DAY', '- День сброса: {day}').format(
        day=node.get('traffic_reset_day') or '—'
    ) + '\n'
    text += texts.t('ADMIN_RW_NODE_NOTIFY', '- Уведомления: {percent}').format(percent=notify_percent) + '\n'
    text += texts.t('ADMIN_RW_NODE_MULTIPLIER', '- Множитель: {value}').format(
        value=node.get('consumption_multiplier') or 1
    ) + '\n'
    text += '\n' + texts.t('ADMIN_RW_NODE_META', '<b>Метаданные:</b>') + '\n'
    text += texts.t('ADMIN_RW_NODE_CREATED', '- Создана: {time}').format(time=created_at) + '\n'
    text += texts.t('ADMIN_RW_NODE_UPDATED', '- Обновлена: {time}').format(time=updated_at)
    return text



logger = structlog.get_logger(__name__)

squad_inbound_selections = {}
squad_create_data = {}

MIGRATION_PAGE_SIZE = 8


def _format_duration(texts, seconds: float) -> str:
    if seconds < 1:
        return texts.t('ADMIN_RW_DURATION_LT1', 'менее 1с')

    minutes, sec = divmod(int(seconds), 60)
    if minutes:
        if sec:
            return texts.t('ADMIN_RW_DURATION_MIN_SEC', '{minutes} мин {sec} с').format(minutes=minutes, sec=sec)
        return texts.t('ADMIN_RW_DURATION_MIN', '{minutes} мин').format(minutes=minutes)
    return texts.t('ADMIN_RW_DURATION_SEC', '{sec} с').format(sec=sec)


def _format_user_stats(texts, stats: dict[str, Any] | None) -> str:
    if not stats:
        return '—'

    created = stats.get('created', 0)
    updated = stats.get('updated', 0)
    deleted = stats.get('deleted', stats.get('deactivated', 0))
    errors = stats.get('errors', 0)

    return texts.t(
        'ADMIN_RW_USER_STATS',
        '• Создано: {created}\n• Обновлено: {updated}\n• Деактивировано: {deleted}\n• Ошибок: {errors}',
    ).format(created=created, updated=updated, deleted=deleted, errors=errors)


def _format_server_stats(texts, stats: dict[str, Any] | None) -> str:
    if not stats:
        return '—'

    created = stats.get('created', 0)
    updated = stats.get('updated', 0)
    removed = stats.get('removed', 0)
    total = stats.get('total', 0)

    return texts.t(
        'ADMIN_RW_SERVER_STATS',
        '• Создано: {created}\n• Обновлено: {updated}\n• Удалено: {removed}\n• Всего в панели: {total}',
    ).format(created=created, updated=updated, removed=removed, total=total)


def _build_auto_sync_view(texts, status: RemnaWaveAutoSyncStatus) -> tuple[str, types.InlineKeyboardMarkup]:
    times_text = ', '.join(t.strftime('%H:%M') for t in status.times) if status.times else '—'
    next_run_text = format_datetime(status.next_run) if status.next_run else '—'

    if status.last_run_finished_at:
        finished_text = format_datetime(status.last_run_finished_at)
        started_text = format_datetime(status.last_run_started_at) if status.last_run_started_at else '—'
        duration = status.last_run_finished_at - status.last_run_started_at if status.last_run_started_at else None
        duration_text = f' ({_format_duration(texts, duration.total_seconds())})' if duration else ''
        reason_map = {
            'manual': texts.t('ADMIN_RW_SYNC_REASON_MANUAL', 'вручную'),
            'auto': texts.t('ADMIN_RW_SYNC_REASON_AUTO', 'по расписанию'),
            'immediate': texts.t('ADMIN_RW_SYNC_REASON_IMMEDIATE', 'при включении'),
        }
        reason_text = reason_map.get(status.last_run_reason or '', '—')
        result_icon = '✅' if status.last_run_success else '❌'
        result_label = (
            texts.t('ADMIN_RW_SYNC_RESULT_OK', 'успешно')
            if status.last_run_success
            else texts.t('ADMIN_RW_SYNC_RESULT_ERR', 'с ошибками')
        )
        error_block = (
            texts.t('ADMIN_RW_SYNC_ERROR', '\n⚠️ Ошибка: {error}').format(error=status.last_run_error)
            if status.last_run_error
            else ''
        )
        last_run_text = (
            f'{result_icon} {result_label}\n'
            f'{texts.t("ADMIN_RW_SYNC_STARTED", "• Старт: {time}").format(time=started_text)}\n'
            f'{texts.t("ADMIN_RW_SYNC_FINISHED", "• Завершено: {time}{duration}").format(time=finished_text, duration=duration_text)}\n'
            f'{texts.t("ADMIN_RW_SYNC_REASON", "• Причина запуска: {reason}").format(reason=reason_text)}{error_block}'
        )
    elif status.last_run_started_at:
        last_run_text = (
            texts.t('ADMIN_RW_SYNC_IN_PROGRESS', '⏳ Синхронизация началась, но еще не завершилась')
            if status.is_running
            else texts.t('ADMIN_RW_SYNC_LAST_START', 'ℹ️ Последний запуск: {time}').format(
                time=format_datetime(status.last_run_started_at)
            )
        )
    else:
        last_run_text = '—'

    running_text = (
        texts.t('ADMIN_RW_SYNC_RUNNING', '⏳ Выполняется сейчас')
        if status.is_running
        else texts.t('ADMIN_RW_SYNC_IDLE', 'Ожидание')
    )
    toggle_text = (
        texts.t('ADMIN_RW_SYNC_DISABLE', '❌ Отключить')
        if status.enabled
        else texts.t('ADMIN_RW_SYNC_ENABLE', '✅ Включить')
    )

    text = texts.t(
        'ADMIN_RW_AUTO_SYNC_PANEL',
        '🔄 <b>Автосинхронизация RemnaWave</b>\n\n'
        '⚙️ <b>Статус:</b> {status}\n'
        '🕒 <b>Расписание:</b> {times}\n'
        '📅 <b>Следующий запуск:</b> {next_run}\n'
        '⏱️ <b>Состояние:</b> {running}\n\n'
        '📊 <b>Последний запуск:</b>\n{last_run}\n\n'
        '👥 <b>Пользователи:</b>\n{users}\n\n'
        '🌐 <b>Серверы:</b>\n{servers}',
    ).format(
        status=texts.t('ADMIN_RW_SYNC_ON', '✅ Включена')
        if status.enabled
        else texts.t('ADMIN_RW_SYNC_OFF', '❌ Отключена'),
        times=times_text,
        next_run=next_run_text if status.enabled else '—',
        running=running_text,
        last_run=last_run_text,
        users=_format_user_stats(texts, status.last_user_stats),
        servers=_format_server_stats(texts, status.last_server_stats),
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_RW_SYNC_RUN_NOW', '🔁 Запустить сейчас'),
                    callback_data='remnawave_auto_sync_run',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=toggle_text,
                    callback_data='remnawave_auto_sync_toggle',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_RW_SYNC_EDIT_SCHEDULE', '🕒 Изменить расписание'),
                    callback_data='remnawave_auto_sync_times',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'),
                    callback_data='admin_rw_sync',
                )
            ],
        ]
    )

    return text, keyboard


def _format_migration_server_label(texts, server) -> str:
    status = (
        texts.t('ADMIN_SQUAD_MIGRATION_STATUS_AVAILABLE', '✅ Доступен')
        if getattr(server, 'is_available', True)
        else texts.t('ADMIN_SQUAD_MIGRATION_STATUS_UNAVAILABLE', '🚫 Недоступен')
    )
    return texts.t(
        'ADMIN_SQUAD_MIGRATION_SERVER_LABEL',
        '{name} — 👥 {users} ({status})',
    ).format(name=html.escape(server.display_name), users=server.current_users, status=status)


def _build_migration_keyboard(
    texts,
    squads,
    page: int,
    total_pages: int,
    stage: str,
    *,
    exclude_uuid: str = None,
):
    prefix = 'admin_migration_source' if stage == 'source' else 'admin_migration_target'
    rows = []
    has_items = False

    button_template = texts.t(
        'ADMIN_SQUAD_MIGRATION_SQUAD_BUTTON',
        '🌍 {name} — 👥 {users} ({status})',
    )

    for squad in squads:
        if exclude_uuid and squad.squad_uuid == exclude_uuid:
            continue

        has_items = True
        status = (
            texts.t('ADMIN_SQUAD_MIGRATION_STATUS_AVAILABLE_SHORT', '✅')
            if getattr(squad, 'is_available', True)
            else texts.t('ADMIN_SQUAD_MIGRATION_STATUS_UNAVAILABLE_SHORT', '🚫')
        )
        rows.append(
            [
                types.InlineKeyboardButton(
                    text=button_template.format(
                        name=squad.display_name,
                        users=squad.current_users,
                        status=status,
                    ),
                    callback_data=f'{prefix}_{squad.squad_uuid}',
                )
            ]
        )

    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                types.InlineKeyboardButton(
                    text='⬅️',
                    callback_data=f'{prefix}_page_{page - 1}',
                )
            )
        nav_buttons.append(
            types.InlineKeyboardButton(
                text=texts.t(
                    'ADMIN_SQUAD_MIGRATION_PAGE',
                    'Стр. {page}/{pages}',
                ).format(page=page, pages=total_pages),
                callback_data='admin_migration_page_info',
            )
        )
        if page < total_pages:
            nav_buttons.append(
                types.InlineKeyboardButton(
                    text='➡️',
                    callback_data=f'{prefix}_page_{page + 1}',
                )
            )
        rows.append(nav_buttons)

    rows.append(
        [
            types.InlineKeyboardButton(
                text=texts.CANCEL,
                callback_data='admin_migration_cancel',
            )
        ]
    )

    return types.InlineKeyboardMarkup(inline_keyboard=rows), has_items


async def _fetch_migration_page(
    db: AsyncSession,
    page: int,
):
    squads, total = await get_all_server_squads(
        db,
        page=max(1, page),
        limit=MIGRATION_PAGE_SIZE,
    )
    total_pages = max(1, math.ceil(total / MIGRATION_PAGE_SIZE))

    page = max(page, 1)
    if page > total_pages:
        page = total_pages
        squads, total = await get_all_server_squads(
            db,
            page=page,
            limit=MIGRATION_PAGE_SIZE,
        )
        total_pages = max(1, math.ceil(total / MIGRATION_PAGE_SIZE))

    return squads, page, total_pages


@admin_required
@error_handler
async def show_squad_migration_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)

    await state.clear()

    squads, page, total_pages = await _fetch_migration_page(db, page=1)
    keyboard, has_items = _build_migration_keyboard(
        texts,
        squads,
        page,
        total_pages,
        'source',
    )

    message = (
        texts.t('ADMIN_SQUAD_MIGRATION_TITLE', '🚚 <b>Переезд сквадов</b>')
        + '\n\n'
        + texts.t(
            'ADMIN_SQUAD_MIGRATION_SELECT_SOURCE',
            'Выберите сквад, из которого нужно переехать:',
        )
    )

    if not has_items:
        message += '\n\n' + texts.t(
            'ADMIN_SQUAD_MIGRATION_NO_OPTIONS',
            'Нет доступных сквадов. Добавьте новые или отмените операцию.',
        )

    await state.set_state(SquadMigrationStates.selecting_source)

    await callback.message.edit_text(
        message,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()


@admin_required
@error_handler
async def paginate_migration_source(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    if await state.get_state() != SquadMigrationStates.selecting_source:
        await callback.answer()
        return

    try:
        page = int(callback.data.split('_page_')[-1])
    except (ValueError, IndexError):
        await callback.answer()
        return

    squads, page, total_pages = await _fetch_migration_page(db, page=page)
    texts = get_texts(db_user.language)
    keyboard, has_items = _build_migration_keyboard(
        texts,
        squads,
        page,
        total_pages,
        'source',
    )

    message = (
        texts.t('ADMIN_SQUAD_MIGRATION_TITLE', '🚚 <b>Переезд сквадов</b>')
        + '\n\n'
        + texts.t(
            'ADMIN_SQUAD_MIGRATION_SELECT_SOURCE',
            'Выберите сквад, из которого нужно переехать:',
        )
    )

    if not has_items:
        message += '\n\n' + texts.t(
            'ADMIN_SQUAD_MIGRATION_NO_OPTIONS',
            'Нет доступных сквадов. Добавьте новые или отмените операцию.',
        )

    await callback.message.edit_text(
        message,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()


@admin_required
@error_handler
async def handle_migration_source_selection(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    if await state.get_state() != SquadMigrationStates.selecting_source:
        await callback.answer()
        return

    if '_page_' in callback.data:
        await callback.answer()
        return

    source_uuid = callback.data.replace('admin_migration_source_', '', 1)

    texts = get_texts(db_user.language)
    server = await get_server_squad_by_uuid(db, source_uuid)

    if not server:
        await callback.answer(
            texts.t(
                'ADMIN_SQUAD_MIGRATION_SQUAD_NOT_FOUND',
                'Сквад не найден или недоступен.',
            ),
            show_alert=True,
        )
        return

    await state.update_data(
        source_uuid=server.squad_uuid,
        source_display=_format_migration_server_label(texts, server),
    )

    squads, page, total_pages = await _fetch_migration_page(db, page=1)
    keyboard, has_items = _build_migration_keyboard(
        texts,
        squads,
        page,
        total_pages,
        'target',
        exclude_uuid=server.squad_uuid,
    )

    message = (
        texts.t('ADMIN_SQUAD_MIGRATION_TITLE', '🚚 <b>Переезд сквадов</b>')
        + '\n\n'
        + texts.t(
            'ADMIN_SQUAD_MIGRATION_SELECTED_SOURCE',
            'Источник: {source}',
        ).format(source=_format_migration_server_label(texts, server))
        + '\n\n'
        + texts.t(
            'ADMIN_SQUAD_MIGRATION_SELECT_TARGET',
            'Выберите сквад, в который нужно переехать:',
        )
    )

    if not has_items:
        message += '\n\n' + texts.t(
            'ADMIN_SQUAD_MIGRATION_TARGET_EMPTY',
            'Нет других сквадов для переезда. Отмените операцию или создайте новые сквады.',
        )

    await state.set_state(SquadMigrationStates.selecting_target)

    await callback.message.edit_text(
        message,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()


@admin_required
@error_handler
async def paginate_migration_target(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    if await state.get_state() != SquadMigrationStates.selecting_target:
        await callback.answer()
        return

    try:
        page = int(callback.data.split('_page_')[-1])
    except (ValueError, IndexError):
        await callback.answer()
        return

    data = await state.get_data()
    source_uuid = data.get('source_uuid')
    if not source_uuid:
        await callback.answer()
        return

    texts = get_texts(db_user.language)

    squads, page, total_pages = await _fetch_migration_page(db, page=page)
    keyboard, has_items = _build_migration_keyboard(
        texts,
        squads,
        page,
        total_pages,
        'target',
        exclude_uuid=source_uuid,
    )

    source_display = data.get('source_display') or source_uuid

    message = (
        texts.t('ADMIN_SQUAD_MIGRATION_TITLE', '🚚 <b>Переезд сквадов</b>')
        + '\n\n'
        + texts.t(
            'ADMIN_SQUAD_MIGRATION_SELECTED_SOURCE',
            'Источник: {source}',
        ).format(source=source_display)
        + '\n\n'
        + texts.t(
            'ADMIN_SQUAD_MIGRATION_SELECT_TARGET',
            'Выберите сквад, в который нужно переехать:',
        )
    )

    if not has_items:
        message += '\n\n' + texts.t(
            'ADMIN_SQUAD_MIGRATION_TARGET_EMPTY',
            'Нет других сквадов для переезда. Отмените операцию или создайте новые сквады.',
        )

    await callback.message.edit_text(
        message,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()


@admin_required
@error_handler
async def handle_migration_target_selection(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    current_state = await state.get_state()
    if current_state != SquadMigrationStates.selecting_target:
        await callback.answer()
        return

    if '_page_' in callback.data:
        await callback.answer()
        return

    data = await state.get_data()
    source_uuid = data.get('source_uuid')

    if not source_uuid:
        await callback.answer()
        return

    target_uuid = callback.data.replace('admin_migration_target_', '', 1)

    texts = get_texts(db_user.language)

    if target_uuid == source_uuid:
        await callback.answer(
            texts.t(
                'ADMIN_SQUAD_MIGRATION_SAME_SQUAD',
                'Нельзя выбрать тот же сквад.',
            ),
            show_alert=True,
        )
        return

    target_server = await get_server_squad_by_uuid(db, target_uuid)
    if not target_server:
        await callback.answer(
            texts.t(
                'ADMIN_SQUAD_MIGRATION_SQUAD_NOT_FOUND',
                'Сквад не найден или недоступен.',
            ),
            show_alert=True,
        )
        return

    source_display = data.get('source_display') or source_uuid

    users_to_move = await count_active_users_for_squad(db, source_uuid)

    await state.update_data(
        target_uuid=target_server.squad_uuid,
        target_display=_format_migration_server_label(texts, target_server),
        migration_count=users_to_move,
    )

    await state.set_state(SquadMigrationStates.confirming)

    message_lines = [
        texts.t('ADMIN_SQUAD_MIGRATION_TITLE', '🚚 <b>Переезд сквадов</b>'),
        '',
        texts.t(
            'ADMIN_SQUAD_MIGRATION_CONFIRM_DETAILS',
            'Проверьте параметры переезда:',
        ),
        texts.t(
            'ADMIN_SQUAD_MIGRATION_CONFIRM_SOURCE',
            '• Из: {source}',
        ).format(source=source_display),
        texts.t(
            'ADMIN_SQUAD_MIGRATION_CONFIRM_TARGET',
            '• В: {target}',
        ).format(target=_format_migration_server_label(texts, target_server)),
        texts.t(
            'ADMIN_SQUAD_MIGRATION_CONFIRM_COUNT',
            '• Пользователей к переносу: {count}',
        ).format(count=users_to_move),
        '',
        texts.t(
            'ADMIN_SQUAD_MIGRATION_CONFIRM_PROMPT',
            'Подтвердите выполнение операции.',
        ),
    ]

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        'ADMIN_SQUAD_MIGRATION_CONFIRM_BUTTON',
                        '✅ Подтвердить',
                    ),
                    callback_data='admin_migration_confirm',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        'ADMIN_SQUAD_MIGRATION_CHANGE_TARGET',
                        '🔄 Изменить сервер назначения',
                    ),
                    callback_data='admin_migration_change_target',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.CANCEL,
                    callback_data='admin_migration_cancel',
                )
            ],
        ]
    )

    await callback.message.edit_text(
        '\n'.join(message_lines),
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()


@admin_required
@error_handler
async def change_migration_target(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    data = await state.get_data()
    source_uuid = data.get('source_uuid')

    if not source_uuid:
        await callback.answer()
        return

    await state.set_state(SquadMigrationStates.selecting_target)

    texts = get_texts(db_user.language)
    squads, page, total_pages = await _fetch_migration_page(db, page=1)
    keyboard, has_items = _build_migration_keyboard(
        texts,
        squads,
        page,
        total_pages,
        'target',
        exclude_uuid=source_uuid,
    )

    source_display = data.get('source_display') or source_uuid

    message = (
        texts.t('ADMIN_SQUAD_MIGRATION_TITLE', '🚚 <b>Переезд сквадов</b>')
        + '\n\n'
        + texts.t(
            'ADMIN_SQUAD_MIGRATION_SELECTED_SOURCE',
            'Источник: {source}',
        ).format(source=source_display)
        + '\n\n'
        + texts.t(
            'ADMIN_SQUAD_MIGRATION_SELECT_TARGET',
            'Выберите сквад, в который нужно переехать:',
        )
    )

    if not has_items:
        message += '\n\n' + texts.t(
            'ADMIN_SQUAD_MIGRATION_TARGET_EMPTY',
            'Нет других сквадов для переезда. Отмените операцию или создайте новые сквады.',
        )

    await callback.message.edit_text(
        message,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()


@admin_required
@error_handler
async def confirm_squad_migration(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    current_state = await state.get_state()
    if current_state != SquadMigrationStates.confirming:
        await callback.answer()
        return

    data = await state.get_data()
    source_uuid = data.get('source_uuid')
    target_uuid = data.get('target_uuid')

    if not source_uuid or not target_uuid:
        await callback.answer()
        return

    texts = get_texts(db_user.language)
    remnawave_service = RemnaWaveService()

    await callback.answer(texts.t('ADMIN_SQUAD_MIGRATION_IN_PROGRESS', 'Запускаю переезд...'))

    try:
        result = await remnawave_service.migrate_squad_users(
            db,
            source_uuid=source_uuid,
            target_uuid=target_uuid,
        )
    except RemnaWaveConfigurationError as error:
        message = texts.t(
            'ADMIN_SQUAD_MIGRATION_API_ERROR',
            '❌ RemnaWave API не настроен: {error}',
        ).format(error=str(error))
        reply_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t(
                            'ADMIN_SQUAD_MIGRATION_BACK_BUTTON',
                            '⬅️ В Remnawave',
                        ),
                        callback_data='admin_remnawave',
                    )
                ]
            ]
        )
        await callback.message.edit_text(message, reply_markup=reply_markup)
        await state.clear()
        return

    source_display = data.get('source_display') or source_uuid
    target_display = data.get('target_display') or target_uuid

    if not result.get('success'):
        error_message = result.get('message') or ''
        error_code = result.get('error') or 'unexpected'
        message = texts.t(
            'ADMIN_SQUAD_MIGRATION_ERROR',
            '❌ Не удалось выполнить переезд (код: {code}). {details}',
        ).format(code=error_code, details=error_message)
        reply_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t(
                            'ADMIN_SQUAD_MIGRATION_BACK_BUTTON',
                            '⬅️ В Remnawave',
                        ),
                        callback_data='admin_remnawave',
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t(
                            'ADMIN_SQUAD_MIGRATION_NEW_BUTTON',
                            '🔁 Новый переезд',
                        ),
                        callback_data='admin_rw_migration',
                    )
                ],
            ]
        )
        await callback.message.edit_text(message, reply_markup=reply_markup)
        await state.clear()
        return

    message_lines = [
        texts.t('ADMIN_SQUAD_MIGRATION_SUCCESS_TITLE', '✅ Переезд завершен'),
        '',
        texts.t('ADMIN_SQUAD_MIGRATION_CONFIRM_SOURCE', '• Из: {source}').format(source=source_display),
        texts.t('ADMIN_SQUAD_MIGRATION_CONFIRM_TARGET', '• В: {target}').format(target=target_display),
        '',
        texts.t(
            'ADMIN_SQUAD_MIGRATION_RESULT_TOTAL',
            'Найдено подписок: {count}',
        ).format(count=result.get('total', 0)),
        texts.t(
            'ADMIN_SQUAD_MIGRATION_RESULT_UPDATED',
            'Перенесено: {count}',
        ).format(count=result.get('updated', 0)),
    ]

    panel_updated = result.get('panel_updated', 0)
    panel_failed = result.get('panel_failed', 0)

    if panel_updated:
        message_lines.append(
            texts.t(
                'ADMIN_SQUAD_MIGRATION_RESULT_PANEL_UPDATED',
                'Обновлено в панели: {count}',
            ).format(count=panel_updated)
        )
    if panel_failed:
        message_lines.append(
            texts.t(
                'ADMIN_SQUAD_MIGRATION_RESULT_PANEL_FAILED',
                'Не удалось обновить в панели: {count}',
            ).format(count=panel_failed)
        )

    reply_markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        'ADMIN_SQUAD_MIGRATION_NEW_BUTTON',
                        '🔁 Новый переезд',
                    ),
                    callback_data='admin_rw_migration',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        'ADMIN_SQUAD_MIGRATION_BACK_BUTTON',
                        '⬅️ В Remnawave',
                    ),
                    callback_data='admin_remnawave',
                )
            ],
        ]
    )

    await callback.message.edit_text(
        '\n'.join(message_lines),
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )
    await state.clear()


@admin_required
@error_handler
async def cancel_squad_migration(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    await state.clear()

    message = texts.t(
        'ADMIN_SQUAD_MIGRATION_CANCELLED',
        '❌ Переезд отменен.',
    )

    reply_markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        'ADMIN_SQUAD_MIGRATION_BACK_BUTTON',
                        '⬅️ В Remnawave',
                    ),
                    callback_data='admin_remnawave',
                )
            ]
        ]
    )

    await callback.message.edit_text(message, reply_markup=reply_markup)
    await callback.answer()


@admin_required
@error_handler
async def handle_migration_page_info(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    await callback.answer(
        texts.t('ADMIN_SQUAD_MIGRATION_PAGE_HINT', 'Это текущая страница.'),
        show_alert=False,
    )


@admin_required
@error_handler
async def show_remnawave_menu(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    remnawave_service = RemnaWaveService()
    connection_test = await remnawave_service.test_api_connection()

    status = connection_test.get('status')
    if status == 'connected':
        status_emoji = '✅'
    elif status == 'not_configured':
        status_emoji = 'ℹ️'
    else:
        status_emoji = '❌'

    api_url_display = settings.REMNAWAVE_API_URL or '—'

    text = texts.t(
        'ADMIN_RW_MENU',
        '🖥️ <b>Управление Remnawave</b>\n\n'
        '📡 <b>Соединение:</b> {emoji} {message}\n'
        '🌐 <b>URL:</b> <code>{url}</code>\n\n'
        'Выберите действие:',
    ).format(
        emoji=status_emoji,
        message=connection_test.get('message', texts.t('ADMIN_RW_NO_DATA', 'Нет данных')),
        url=api_url_display,
    )

    await callback.message.edit_text(text, reply_markup=get_admin_remnawave_keyboard(db_user.language))
    await callback.answer()


@admin_required
@error_handler
async def show_system_stats(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    remnawave_service = RemnaWaveService()
    stats = await remnawave_service.get_system_statistics()

    if 'error' in stats:
        await callback.message.edit_text(
            texts.t('ADMIN_RW_STATS_ERROR', '❌ Ошибка получения статистики: {error}').format(error=stats['error']),
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'),
                            callback_data='admin_remnawave',
                        )
                    ]
                ]
            ),
        )
        await callback.answer()
        return

    system = stats.get('system', {})
    users_by_status = stats.get('users_by_status', {})
    server_info = stats.get('server_info', {})
    bandwidth = stats.get('bandwidth', {})
    traffic_periods = stats.get('traffic_periods', {})
    nodes_realtime = stats.get('nodes_realtime', [])
    nodes_weekly = stats.get('nodes_weekly', [])

    memory_total = server_info.get('memory_total', 1)
    memory_used_percent = (server_info.get('memory_used', 0) / memory_total * 100) if memory_total > 0 else 0

    uptime_seconds = server_info.get('uptime_seconds', 0)
    uptime_days = int(uptime_seconds // 86400)
    uptime_hours = int((uptime_seconds % 86400) // 3600)
    uptime_str = f'{uptime_days}d {uptime_hours}h'

    users_status_text = ''
    for status, count in users_by_status.items():
        status_emoji = {'ACTIVE': '✅', 'DISABLED': '❌', 'LIMITED': '⚠️', 'EXPIRED': '⏰'}.get(status, '❓')
        users_status_text += f'  {status_emoji} {status}: {count}\n'

    top_nodes_text = ''
    for i, node in enumerate(nodes_weekly[:3], 1):
        top_nodes_text += texts.t('ADMIN_RW_SYSTEM_TOP_LINE', '  {rank}. {name}: {value}\n').format(
            rank=i, name=node['name'], value=format_bytes(node['total_bytes'])
        )

    realtime_nodes_text = ''
    for node in nodes_realtime[:3]:
        node_total = node.get('downloadBytes', 0) + node.get('uploadBytes', 0)
        if node_total > 0:
            realtime_nodes_text += texts.t('ADMIN_RW_SYSTEM_RT_LINE', '  📡 {name}: {value}\n').format(
                name=node.get('nodeName', 'Unknown'),
                value=format_bytes(node_total),
            )

    period_defs = [
        ('last_2_days', texts.t('ADMIN_RW_SYSTEM_PERIOD_2D', '2 дня')),
        ('last_7_days', texts.t('ADMIN_RW_SYSTEM_PERIOD_7D', '7 дней')),
        ('last_30_days', texts.t('ADMIN_RW_SYSTEM_PERIOD_30D', '30 дней')),
        ('current_month', texts.t('ADMIN_RW_SYSTEM_PERIOD_MONTH', 'Месяц')),
        ('current_year', texts.t('ADMIN_RW_SYSTEM_PERIOD_YEAR', 'Год')),
    ]

    text = texts.t('ADMIN_RW_SYSTEM_STATS_TITLE', '📊 <b>Детальная статистика Remnawave</b>') + '\n\n'
    text += texts.t('ADMIN_RW_SYSTEM_SERVER', '🖥️ <b>Сервер:</b>') + '\n'
    text += texts.t('ADMIN_RW_SYSTEM_CPU', '- CPU: {cores} ядер').format(cores=server_info.get('cpu_cores', 0)) + '\n'
    text += (
        texts.t('ADMIN_RW_SYSTEM_RAM', '- RAM: {used} / {total} ({percent}%)').format(
            used=format_bytes(server_info.get('memory_used', 0)),
            total=format_bytes(memory_total),
            percent=f'{memory_used_percent:.1f}',
        )
        + '\n'
    )
    text += texts.t('ADMIN_RW_SYSTEM_FREE', '- Свободно: {free}').format(
        free=format_bytes(server_info.get('memory_free', 0))
    ) + '\n'
    text += texts.t('ADMIN_RW_SYSTEM_UPTIME', '- Uptime: {uptime}').format(uptime=uptime_str) + '\n\n'
    text += texts.t('ADMIN_RW_SYSTEM_USERS', '👥 <b>Пользователи ({total} всего):</b>').format(
        total=system.get('total_users', 0)
    ) + '\n'
    text += texts.t('ADMIN_RW_SYSTEM_ONLINE', '- 🟢 Онлайн сейчас: {count}').format(
        count=system.get('users_online', 0)
    ) + '\n'
    text += texts.t('ADMIN_RW_SYSTEM_DAY', '- 📅 За сутки: {count}').format(
        count=system.get('users_last_day', 0)
    ) + '\n'
    text += texts.t('ADMIN_RW_SYSTEM_WEEK', '- 📊 За неделю: {count}').format(
        count=system.get('users_last_week', 0)
    ) + '\n'
    text += texts.t('ADMIN_RW_SYSTEM_NEVER', '- 💤 Никогда не заходили: {count}').format(
        count=system.get('users_never_online', 0)
    ) + '\n\n'
    text += texts.t('ADMIN_RW_SYSTEM_STATUS_HEADER', '<b>Статусы пользователей:</b>') + '\n'
    text += users_status_text + '\n'
    text += texts.t('ADMIN_RW_SYSTEM_NODES', '🌐 <b>Ноды ({online} онлайн):</b>').format(
        online=system.get('nodes_online', 0)
    )

    if realtime_nodes_text:
        text += '\n' + texts.t('ADMIN_RW_SYSTEM_RT', '<b>Реалтайм активность:</b>') + '\n'
        text += realtime_nodes_text

    if top_nodes_text:
        text += '\n' + texts.t('ADMIN_RW_SYSTEM_TOP_WEEK', '<b>Топ нод за неделю:</b>') + '\n'
        text += top_nodes_text

    text += texts.t('ADMIN_RW_SYSTEM_USER_TRAFFIC', '\n📈 <b>Общий трафик пользователей:</b> {value}').format(
        value=format_bytes(system.get('total_user_traffic', 0))
    )
    text += texts.t('ADMIN_RW_SYSTEM_TRAFFIC_PERIODS', '\n📊 <b>Трафик по периодам:</b>') + '\n'
    for key, label in period_defs:
        period = traffic_periods.get(key, {})
        change = _rw_format_traffic_change(period.get('difference', ''))
        text += texts.t('ADMIN_RW_SYSTEM_PERIOD_LINE', '- {label}: {value}{change}').format(
            label=label,
            value=format_bytes(period.get('current', 0)),
            change=change,
        ) + '\n'

    if bandwidth.get('realtime_total', 0) > 0:
        text += texts.t('ADMIN_RW_SYSTEM_RT_TRAFFIC', '\n⚡ <b>Реалтайм трафик:</b>') + '\n'
        text += texts.t('ADMIN_RW_SYSTEM_RT_DL', '- Скачивание: {value}').format(
            value=format_bytes(bandwidth.get('realtime_download', 0))
        ) + '\n'
        text += texts.t('ADMIN_RW_SYSTEM_RT_UL', '- Загрузка: {value}').format(
            value=format_bytes(bandwidth.get('realtime_upload', 0))
        ) + '\n'
        text += texts.t('ADMIN_RW_SYSTEM_RT_TOTAL', '- Итого: {value}').format(
            value=format_bytes(bandwidth.get('realtime_total', 0))
        ) + '\n'

    text += texts.t('ADMIN_RW_SYSTEM_UPDATED', '\n🕒 <b>Обновлено:</b> {time}').format(
        time=_rw_format_dt(stats.get('last_updated', datetime.now(UTC)), db_user.language)
    )

    keyboard = [
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_REFRESH', '🔄 Обновить'),
                callback_data='admin_rw_system',
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_REMNAWAVE_MANAGE_NODES', '📈 Ноды'),
                callback_data='admin_rw_nodes',
            ),
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_REMNAWAVE_SYNC', '👥 Синхронизация'),
                callback_data='admin_rw_sync',
            ),
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'),
                callback_data='admin_remnawave',
            )
        ],
    ]

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def show_traffic_stats(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    remnawave_service = RemnaWaveService()

    try:
        async with remnawave_service.get_api_client() as api:
            bandwidth_stats = await api.get_bandwidth_stats()

            realtime_usage = await api.get_nodes_realtime_usage()

            nodes_stats = await api.get_nodes_statistics()

    except Exception as e:
        await callback.message.edit_text(
            texts.t('ADMIN_RW_TRAFFIC_ERROR', '❌ Ошибка получения статистики трафика: {error}').format(error=e),
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'),
                            callback_data='admin_remnawave',
                        )
                    ]
                ]
            ),
        )
        await callback.answer()
        return

    def parse_bandwidth(bandwidth_str):
        return remnawave_service._parse_bandwidth_string(bandwidth_str)

    total_realtime_download = sum(node.get('downloadBytes', 0) for node in realtime_usage)
    total_realtime_upload = sum(node.get('uploadBytes', 0) for node in realtime_usage)
    total_realtime = total_realtime_download + total_realtime_upload

    total_users_online = sum(node.get('usersOnline', 0) for node in realtime_usage)

    periods = {
        'last_2_days': bandwidth_stats.get('bandwidthLastTwoDays', {}),
        'last_7_days': bandwidth_stats.get('bandwidthLastSevenDays', {}),
        'last_30_days': bandwidth_stats.get('bandwidthLast30Days', {}),
        'current_month': bandwidth_stats.get('bandwidthCalendarMonth', {}),
        'current_year': bandwidth_stats.get('bandwidthCurrentYear', {}),
    }

    def format_change(diff_str):
        if not diff_str or diff_str == '0':
            return ''
        if diff_str.startswith('-'):
            return f' 🔻 {diff_str[1:]}'
        return f' 🔺 {diff_str}'

    period_labels = {
        'last_2_days': texts.t('ADMIN_RW_TRAFFIC_PERIOD_2D', '<b>За 2 дня:</b>'),
        'last_7_days': texts.t('ADMIN_RW_TRAFFIC_PERIOD_7D', '<b>За 7 дней:</b>'),
        'last_30_days': texts.t('ADMIN_RW_TRAFFIC_PERIOD_30D', '<b>За 30 дней:</b>'),
        'current_month': texts.t('ADMIN_RW_TRAFFIC_PERIOD_MONTH', '<b>Текущий месяц:</b>'),
        'current_year': texts.t('ADMIN_RW_TRAFFIC_PERIOD_YEAR', '<b>Текущий год:</b>'),
    }

    text = texts.t('ADMIN_RW_TRAFFIC_STATS_TITLE', '📊 <b>Статистика трафика Remnawave</b>') + '\n\n'
    text += texts.t('ADMIN_RW_TRAFFIC_INBOUND', '⚡ <b>Трафик по inbounds:</b>') + '\n'
    text += texts.t('ADMIN_RW_TRAFFIC_DOWNLOAD', '- Скачивание: {value}').format(
        value=format_bytes(total_realtime_download)
    ) + '\n'
    text += texts.t('ADMIN_RW_TRAFFIC_UPLOAD', '- Загрузка: {value}').format(
        value=format_bytes(total_realtime_upload)
    ) + '\n'
    text += texts.t('ADMIN_RW_TRAFFIC_TOTAL', '- Общий трафик: {value}').format(value=format_bytes(total_realtime)) + '\n'
    text += texts.t('ADMIN_RW_TRAFFIC_ONLINE', '- Пользователи онлайн: {count}').format(count=total_users_online) + '\n\n'
    text += texts.t('ADMIN_RW_TRAFFIC_PERIODS', '📈 <b>Статистика по периодам:</b>') + '\n\n'

    for key, label in period_labels.items():
        period = periods[key]
        text += label + '\n'
        text += texts.t('ADMIN_RW_TRAFFIC_CURRENT', '- Текущий: {value}').format(
            value=format_bytes(parse_bandwidth(period.get('current', '0')))
        ) + '\n'
        text += texts.t('ADMIN_RW_TRAFFIC_PREVIOUS', '- Предыдущий: {value}').format(
            value=format_bytes(parse_bandwidth(period.get('previous', '0')))
        ) + '\n'
        text += texts.t('ADMIN_RW_TRAFFIC_CHANGE', '- Изменение:{change}').format(
            change=format_change(period.get('difference', ''))
        ) + '\n\n'

    if realtime_usage:
        text += texts.t('ADMIN_RW_TRAFFIC_NODES_RT', '\n🌐 <b>Трафик по нодам (реалтайм):</b>\n')
        for node in sorted(realtime_usage, key=lambda x: x.get('totalBytes', 0), reverse=True):
            node_total = node.get('totalBytes', 0)
            if node_total > 0:
                text += texts.t('ADMIN_RW_TRAFFIC_NODE_LINE', '- {name}: {value}\n').format(
                    name=node.get('nodeName', 'Unknown'),
                    value=format_bytes(node_total),
                )

    if nodes_stats.get('lastSevenDays'):
        text += texts.t('ADMIN_RW_TRAFFIC_TOP_NODES', '\n📊 <b>Топ нод за 7 дней:</b>\n')

        nodes_weekly = {}
        for day_data in nodes_stats['lastSevenDays']:
            node_name = day_data['nodeName']
            if node_name not in nodes_weekly:
                nodes_weekly[node_name] = 0
            nodes_weekly[node_name] += int(day_data['totalBytes'])

        sorted_nodes = sorted(nodes_weekly.items(), key=lambda x: x[1], reverse=True)
        for i, (node_name, total_bytes) in enumerate(sorted_nodes[:5], 1):
            text += texts.t('ADMIN_RW_TRAFFIC_TOP_LINE', '{rank}. {name}: {value}\n').format(
                rank=i, name=node_name, value=format_bytes(total_bytes)
            )

    text += texts.t('ADMIN_RW_TRAFFIC_UPDATED', '\n🕒 <b>Обновлено:</b> {time}').format(
        time=_rw_format_dt(datetime.now(UTC), db_user.language)
    )

    keyboard = [
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_REFRESH', '🔄 Обновить'),
                callback_data='admin_rw_traffic',
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_RW_BTN_NODES', '📈 Ноды'),
                callback_data='admin_rw_nodes',
            ),
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_RW_BTN_SYSTEM', '📊 Система'),
                callback_data='admin_rw_system',
            ),
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'),
                callback_data='admin_remnawave',
            )
        ],
    ]

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def show_nodes_management(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    remnawave_service = RemnaWaveService()
    nodes = await remnawave_service.get_all_nodes()

    if not nodes:
        await callback.message.edit_text(
            texts.t('ADMIN_RW_NODES_EMPTY', '🖥️ Ноды не найдены или ошибка подключения'),
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'),
                            callback_data='admin_remnawave',
                        )
                    ]
                ]
            ),
        )
        await callback.answer()
        return

    text = texts.t('ADMIN_RW_NODES_TITLE', '🖥️ <b>Управление нодами</b>\n\n')
    keyboard = []

    for node in nodes:
        status_emoji = '🟢' if node['is_node_online'] else '🔴'
        connection_emoji = '📡' if node['is_connected'] else '📵'

        text += f'{status_emoji} {connection_emoji} <b>{node["name"]}</b>\n'
        text += f'🌍 {node["country_code"]} • {node["address"]}\n'
        text += texts.t('ADMIN_RW_NODES_ONLINE', '👥 Онлайн: {count}\n\n').format(count=node['users_online'] or 0)

        keyboard.append(
            [types.InlineKeyboardButton(text=f'⚙️ {node["name"]}', callback_data=f'admin_node_manage_{node["uuid"]}')]
        )

    keyboard.extend(
        [
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_RW_BTN_RESTART_ALL', '🔄 Перезагрузить все'),
                    callback_data='admin_restart_all_nodes',
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'),
                    callback_data='admin_remnawave',
                )
            ],
        ]
    )

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def show_node_details(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    node_uuid = callback.data.split('_')[-1]

    remnawave_service = RemnaWaveService()
    node = await remnawave_service.get_node_details(node_uuid)

    if not node:
        await callback.answer(texts.t('ADMIN_RW_NODE_NOT_FOUND', '❌ Нода не найдена'), show_alert=True)
        return

    text = _build_node_detail_text(texts, node, language=db_user.language)

    await callback.message.edit_text(text, reply_markup=get_node_management_keyboard(node_uuid, db_user.language))
    await callback.answer()


@admin_required
@error_handler
async def manage_node(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    action, node_uuid = callback.data.split('_')[1], callback.data.split('_')[-1]

    remnawave_service = RemnaWaveService()
    success = await remnawave_service.manage_node(node_uuid, action)

    if success:
        await callback.answer(
            texts.t('ADMIN_RW_NODE_ACTION_OK', '✅ Нода {action}').format(action=_rw_node_action_label(texts, action))
        )
    else:
        await callback.answer(texts.t('ADMIN_RW_NODE_ACTION_FAIL', '❌ Ошибка выполнения действия'), show_alert=True)

    await show_node_details(callback, db_user, db)


@admin_required
@error_handler
@admin_required
@error_handler
async def show_node_statistics(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    node_uuid = callback.data.split('_')[-1]

    remnawave_service = RemnaWaveService()
    node = await remnawave_service.get_node_details(node_uuid)

    if not node:
        await callback.answer(texts.t('ADMIN_RW_NODE_NOT_FOUND', '❌ Нода не найдена'), show_alert=True)
        return

    status_emoji = '🟢' if node['is_node_online'] else '🔴'
    xray_emoji = '✅' if node['is_xray_running'] else '❌'
    xray_uptime_sec = node.get('xray_uptime', 0)
    if xray_uptime_sec:
        days, rem = divmod(int(xray_uptime_sec), 86400)
        hours, rem = divmod(rem, 3600)
        mins = rem // 60
        xray_uptime_str = f'{days}d {hours}h {mins}m' if days else (f'{hours}h {mins}m' if hours else f'{mins}m')
    else:
        xray_uptime_str = '—'

    back_btn = texts.t('ADMIN_REQCH_BACK', '⬅️ Назад')
    retry_btn = texts.t('ADMIN_RW_BTN_RETRY', '🔄 Обновить')
    retry_again = texts.t('ADMIN_RW_BTN_RETRY', '🔄 Попробовать снова')

    try:
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=7)
        node_usage = await remnawave_service.get_node_user_usage_by_range(node_uuid, start_date, end_date)
        realtime_stats = await remnawave_service.get_nodes_realtime_usage()
        node_realtime = next((s for s in realtime_stats if s.get('nodeUuid') == node_uuid), None)

        status_change = _rw_format_dt(node.get('last_status_change'), db_user.language)
        sys_info = (node.get('system') or {}).get('info', {})
        cpu_model = html.escape(str(sys_info.get('cpuModel') or '—'))
        cpu_count = sys_info.get('cpus', 0)
        cpu_info = f'{cpu_count}x {cpu_model}' if cpu_count else cpu_model
        memory_total = sys_info.get('memoryTotal', 0)
        total_ram = format_bytes(memory_total) if memory_total else '—'
        load_avg = (node.get('system') or {}).get('stats', {}).get('loadAvg', [])
        load_str = ' / '.join(f'{v:.2f}' for v in load_avg[:3]) if load_avg else '—'
        versions = node.get('versions') or {}
        xray_ver = html.escape(str(versions.get('xray') or '—'))
        node_ver = html.escape(str(versions.get('node') or '—'))
        notify_percent = f'{node["notify_percent"]}%' if node.get('notify_percent') is not None else '—'

        text = texts.t('ADMIN_RW_NODE_STATS_TITLE', '📊 <b>Статистика ноды: {name}</b>').format(
            name=html.escape(node['name'])
        ) + '\n\n'
        text += texts.t('ADMIN_RW_NODE_STATUS_HEADER', '<b>Статус:</b>') + '\n'
        text += texts.t('ADMIN_RW_NODE_ONLINE', '- Онлайн: {emoji} {value}').format(
            emoji=status_emoji, value=_rw_yes_no(texts, node['is_node_online'])
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_XRAY', '- Xray: {emoji} {value}').format(
            emoji=xray_emoji,
            value=f"{_rw_xray_state(texts, node['is_xray_running'])} (v{xray_ver})",
        ) + '\n'
        text += f'- Node: v{node_ver}\n'
        text += texts.t('ADMIN_RW_NODE_USERS', '- Пользователей онлайн: {count}').format(count=node['users_online']) + '\n'
        text += texts.t('ADMIN_RW_NODE_STATUS_CHANGE', '- Изменение статуса: {time}').format(time=status_change) + '\n'
        text += texts.t('ADMIN_RW_NODE_MESSAGE', '- Сообщение: {message}').format(
            message=html.escape(str(node.get('last_status_message') or '—'))
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_XRAY_UPTIME', '- Uptime Xray: {uptime}').format(uptime=xray_uptime_str) + '\n\n'
        text += texts.t('ADMIN_RW_NODE_RESOURCES', '<b>Ресурсы:</b>') + '\n'
        text += texts.t('ADMIN_RW_NODE_CPU', '- CPU: {info}').format(info=cpu_info) + '\n'
        text += texts.t('ADMIN_RW_NODE_RAM', '- RAM: {ram}').format(ram=total_ram) + '\n'
        text += texts.t('ADMIN_RW_NODE_LOAD', '- Load: {value}').format(value=load_str) + '\n'
        text += texts.t('ADMIN_RW_NODE_PROVIDER', '- Провайдер: {provider}').format(
            provider=html.escape(str(node.get('provider_uuid') or '—'))
        ) + '\n\n'
        text += texts.t('ADMIN_RW_NODE_TRAFFIC_HEADER', '<b>Трафик:</b>') + '\n'
        text += texts.t('ADMIN_RW_NODE_TRAFFIC_USED', '- Использовано: {value}').format(
            value=format_bytes(node['traffic_used_bytes'] or 0)
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_TRAFFIC_LIMIT', '- Лимит: {value}').format(
            value=_rw_traffic_limit(texts, node['traffic_limit_bytes'])
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_TRACKING', '- Трекинг: {value}').format(
            value=_rw_tracking(texts, node.get('is_traffic_tracking_active'))
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_RESET_DAY', '- День сброса: {day}').format(day=node.get('traffic_reset_day') or '—') + '\n'
        text += texts.t('ADMIN_RW_NODE_NOTIFY', '- Уведомления: {percent}').format(percent=notify_percent) + '\n'
        text += texts.t('ADMIN_RW_NODE_MULTIPLIER', '- Множитель: {value}').format(value=node.get('consumption_multiplier') or 1) + '\n\n'
        text += texts.t('ADMIN_RW_NODE_META', '<b>Метаданные:</b>') + '\n'
        text += texts.t('ADMIN_RW_NODE_CREATED', '- Создана: {time}').format(
            time=_rw_format_dt(node.get('created_at'), db_user.language)
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_UPDATED', '- Обновлена: {time}').format(
            time=_rw_format_dt(node.get('updated_at'), db_user.language)
        )

        if node_realtime:
            text += '\n' + texts.t('ADMIN_RW_NODE_INBOUND_RT', '<b>Трафик по inbounds:</b>') + '\n'
            text += texts.t('ADMIN_RW_NODE_RT_DOWNLOAD', '- Скачано: {value}').format(
                value=format_bytes(node_realtime.get('downloadBytes', 0))
            ) + '\n'
            text += texts.t('ADMIN_RW_NODE_RT_UPLOAD', '- Загружено: {value}').format(
                value=format_bytes(node_realtime.get('uploadBytes', 0))
            ) + '\n'
            text += texts.t('ADMIN_RW_NODE_RT_TOTAL', '- Общий трафик: {value}').format(
                value=format_bytes(node_realtime.get('totalBytes', 0))
            ) + '\n'
            text += texts.t('ADMIN_RW_NODE_RT_ONLINE', '- Онлайн: {count}').format(
                count=node_realtime.get('usersOnline', 0)
            )

        if node_usage:
            text += texts.t('ADMIN_RW_NODE_STATS_7D', '\n<b>Статистика за 7 дней:</b>\n')
            total_usage = 0
            for usage in node_usage[-5:]:
                daily_usage = usage.get('total', 0)
                total_usage += daily_usage
                text += texts.t('ADMIN_RW_NODE_STATS_DAY', '- {date}: {value}\n').format(
                    date=usage.get('date', 'N/A'), value=format_bytes(daily_usage)
                )
            text += texts.t('ADMIN_RW_NODE_STATS_7D_TOTAL', '\n<b>Общий трафик за 7 дней:</b> {value}').format(
                value=format_bytes(total_usage)
            )
        else:
            text += texts.t('ADMIN_RW_NODE_STATS_NO_DATA', '\n<b>Статистика за 7 дней:</b> Данные недоступны')

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=retry_btn, callback_data=f'node_stats_{node_uuid}')],
                [types.InlineKeyboardButton(text=back_btn, callback_data=f'admin_node_manage_{node_uuid}')],
            ]
        )
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()

    except Exception as e:
        logger.error('Ошибка получения статистики ноды', node_uuid=node_uuid, error=e)
        text = texts.t('ADMIN_RW_NODE_STATS_TITLE', '📊 <b>Статистика ноды: {name}</b>').format(
            name=html.escape(node['name'])
        ) + '\n\n'
        text += texts.t('ADMIN_RW_NODE_STATUS_HEADER', '<b>Статус:</b>') + '\n'
        text += texts.t('ADMIN_RW_NODE_ONLINE', '- Онлайн: {emoji} {value}').format(
            emoji=status_emoji, value=_rw_yes_no(texts, node['is_node_online'])
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_XRAY', '- Xray: {emoji} {value}').format(
            emoji=xray_emoji, value=_rw_xray_state(texts, node['is_xray_running'])
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_USERS', '- Пользователей онлайн: {count}').format(count=node['users_online']) + '\n'
        text += texts.t('ADMIN_RW_NODE_STATUS_CHANGE', '- Изменение статуса: {time}').format(
            time=_rw_format_dt(node.get('last_status_change'), db_user.language)
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_MESSAGE', '- Сообщение: {message}').format(
            message=html.escape(str(node.get('last_status_message') or '—'))
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_XRAY_UPTIME', '- Uptime Xray: {uptime}').format(uptime=xray_uptime_str) + '\n\n'
        text += texts.t('ADMIN_RW_NODE_TRAFFIC_HEADER', '<b>Трафик:</b>') + '\n'
        text += texts.t('ADMIN_RW_NODE_TRAFFIC_USED', '- Использовано: {value}').format(
            value=format_bytes(node['traffic_used_bytes'] or 0)
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_TRAFFIC_LIMIT', '- Лимит: {value}').format(
            value=_rw_traffic_limit(texts, node['traffic_limit_bytes'])
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_TRACKING', '- Трекинг: {value}').format(
            value=_rw_tracking(texts, node.get('is_traffic_tracking_active'))
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_RESET_DAY', '- День сброса: {day}').format(day=node.get('traffic_reset_day') or '—') + '\n'
        text += texts.t('ADMIN_RW_NODE_NOTIFY', '- Уведомления: {percent}').format(
            percent=node.get('notify_percent') or '—'
        ) + '\n'
        text += texts.t('ADMIN_RW_NODE_MULTIPLIER', '- Множитель: {value}').format(value=node.get('consumption_multiplier') or 1)
        text += '\n\n' + texts.t('ADMIN_RW_NODE_STATS_ERROR_TITLE', '⚠️ <b>Детальная статистика временно недоступна</b>') + '\n'
        text += texts.t('ADMIN_RW_NODE_STATS_ERROR_BODY', 'Возможные причины:\n• Проблемы с подключением к API\n• Нода недавно добавлена\n• Недостаточно данных для отображения')

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=retry_again, callback_data=f'node_stats_{node_uuid}')],
                [types.InlineKeyboardButton(text=back_btn, callback_data=f'admin_node_manage_{node_uuid}')],
            ]
        )
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()




async def show_squad_details(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    squad_uuid = callback.data.split('_')[-1]

    remnawave_service = RemnaWaveService()
    squad = await remnawave_service.get_squad_details(squad_uuid)

    if not squad:
        await callback.answer(texts.t('ADMIN_RW_SQUAD_NOT_FOUND', '❌ Сквад не найден'), show_alert=True)
        return

    text = texts.t('ADMIN_RW_SQUAD_TITLE', '🌐 <b>Сквад: {name}</b>').format(name=squad['name']) + '\n\n'
    text += texts.t('ADMIN_RW_SQUAD_INFO', '<b>Информация:</b>') + '\n'
    text += texts.t('ADMIN_RW_SQUAD_UUID', '- UUID: <code>{uuid}</code>').format(uuid=squad['uuid']) + '\n'
    text += texts.t('ADMIN_RW_SQUAD_MEMBERS', '- Участников: {count}').format(count=squad['members_count']) + '\n'
    text += texts.t('ADMIN_RW_SQUAD_INBOUNDS', '- Инбаундов: {count}').format(count=squad['inbounds_count']) + '\n\n'
    text += texts.t('ADMIN_RW_SQUAD_INBOUNDS_HEADER', '<b>Инбаунды:</b>') + '\n'

    if squad.get('inbounds'):
        for inbound in squad['inbounds']:
            text += texts.t('ADMIN_RW_SQUAD_INBOUND_LINE', '- {tag} ({type})\n').format(
                tag=inbound['tag'], type=inbound['type']
            )
    else:
        text += texts.t('ADMIN_RW_SQUAD_NO_INBOUNDS', 'Нет активных инбаундов')

    await callback.message.edit_text(text, reply_markup=get_squad_management_keyboard(squad_uuid, db_user.language))
    await callback.answer()


@admin_required
@error_handler
async def manage_squad_action(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    parts = callback.data.split('_')
    action = parts[1]
    squad_uuid = parts[-1]

    remnawave_service = RemnaWaveService()

    if action == 'add_users':
        success = await remnawave_service.add_all_users_to_squad(squad_uuid)
        if success:
            await callback.answer(texts.t('ADMIN_RW_SQUAD_ADD_USERS_OK', '✅ Задача добавления пользователей в очередь'))
        else:
            await callback.answer(texts.t('ADMIN_RW_SQUAD_ADD_USERS_FAIL', '❌ Ошибка добавления пользователей'), show_alert=True)

    elif action == 'remove_users':
        success = await remnawave_service.remove_all_users_from_squad(squad_uuid)
        if success:
            await callback.answer(texts.t('ADMIN_RW_SQUAD_REMOVE_USERS_OK', '✅ Задача удаления пользователей в очередь'))
        else:
            await callback.answer(texts.t('ADMIN_RW_SQUAD_REMOVE_USERS_FAIL', '❌ Ошибка удаления пользователей'), show_alert=True)

    elif action == 'delete':
        success = await remnawave_service.delete_squad(squad_uuid)
        if success:
            await callback.message.edit_text(
                texts.t('ADMIN_RW_SQUAD_DELETED', '✅ Сквад успешно удален'),
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_TO_SQUADS', '⬅️ К сквадам'), callback_data='admin_rw_squads')]]
                ),
            )
        else:
            await callback.answer(texts.t('ADMIN_RW_SQUAD_DELETE_FAIL', '❌ Ошибка удаления сквада'), show_alert=True)
        return

    refreshed_callback = callback.model_copy(update={'data': f'admin_squad_manage_{squad_uuid}'}).as_(callback.bot)

    await show_squad_details(refreshed_callback, db_user, db)


@admin_required
@error_handler
async def show_squad_edit_menu(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    squad_uuid = callback.data.split('_')[-1]

    remnawave_service = RemnaWaveService()
    squad = await remnawave_service.get_squad_details(squad_uuid)

    if not squad:
        await callback.answer(texts.t('ADMIN_RW_SQUAD_NOT_FOUND', '❌ Сквад не найден'), show_alert=True)
        return

    text = f"""
✏️ <b>Редактирование сквада: {squad['name']}</b>

<b>Текущие инбаунды:</b>
"""

    if squad.get('inbounds'):
        for inbound in squad['inbounds']:
            text += f'✅ {inbound["tag"]} ({inbound["type"]})\n'
    else:
        text += texts.t('ADMIN_RW_SQUAD_NO_INBOUNDS', 'Нет активных инбаундов') + '\n'

    text += '\n<b>Доступные действия:</b>'

    await callback.message.edit_text(text, reply_markup=get_squad_edit_keyboard(squad_uuid, db_user.language))
    await callback.answer()


@admin_required
@error_handler
async def show_squad_inbounds_selection(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    squad_uuid = callback.data.split('_')[-1]

    remnawave_service = RemnaWaveService()

    squad = await remnawave_service.get_squad_details(squad_uuid)
    all_inbounds = await remnawave_service.get_all_inbounds()

    if not squad:
        await callback.answer(texts.t('ADMIN_RW_SQUAD_NOT_FOUND', '❌ Сквад не найден'), show_alert=True)
        return

    if not all_inbounds:
        await callback.answer(texts.t('ADMIN_RW_SQUAD_NO_INBOUNDS', '❌ Нет доступных инбаундов'), show_alert=True)
        return

    if squad_uuid not in squad_inbound_selections:
        squad_inbound_selections[squad_uuid] = {inbound['uuid'] for inbound in squad.get('inbounds', [])}

    text = f"""
🔧 <b>Изменение инбаундов</b>

<b>Сквад:</b> {squad['name']}
<b>Текущих инбаундов:</b> {len(squad_inbound_selections[squad_uuid])}

<b>Доступные инбаунды:</b>
"""

    keyboard = []

    for i, inbound in enumerate(all_inbounds[:15]):
        is_selected = inbound['uuid'] in squad_inbound_selections[squad_uuid]
        emoji = '✅' if is_selected else '☐'

        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=f'{emoji} {inbound["tag"]} ({inbound["type"]})', callback_data=f'sqd_tgl_{i}_{squad_uuid[:8]}'
                )
            ]
        )

    if len(all_inbounds) > 15:
        text += f'\n⚠️ Показано первые 15 из {len(all_inbounds)} инбаундов'

    keyboard.extend(
        [
            [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_SAVE', '💾 Сохранить изменения'), callback_data=f'sqd_save_{squad_uuid[:8]}')],
            [types.InlineKeyboardButton(text='⬅️ Назад', callback_data=f'sqd_edit_{squad_uuid[:8]}')],
        ]
    )

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def show_squad_rename_form(callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    squad_uuid = callback.data.split('_')[-1]

    remnawave_service = RemnaWaveService()
    squad = await remnawave_service.get_squad_details(squad_uuid)

    if not squad:
        await callback.answer(texts.t('ADMIN_RW_SQUAD_NOT_FOUND', '❌ Сквад не найден'), show_alert=True)
        return

    await state.update_data(squad_uuid=squad_uuid, squad_name=squad['name'])
    await state.set_state(SquadRenameStates.waiting_for_new_name)

    text = (
        texts.t('ADMIN_RW_SQUAD_RENAME_TITLE', '✏️ <b>Переименование сквада</b>') + '\n\n'
        + texts.t('ADMIN_RW_SQUAD_CURRENT_NAME', '<b>Текущее название:</b> {name}').format(name=squad['name'])
        + '\n\n'
        + texts.t('ADMIN_RW_SQUAD_RENAME_PROMPT', '📝 <b>Введите новое название сквада:</b>')
        + '\n\n'
        + texts.t('ADMIN_RW_SQUAD_RENAME_RULES', '<i>Требования к названию:</i>\n• От 2 до 20 символов\n• Только буквы, цифры, дефисы и подчеркивания\n• Без пробелов и специальных символов')
        + '\n\n'
        + texts.t('ADMIN_RW_SQUAD_RENAME_HINT', 'Отправьте сообщение с новым названием или нажмите «Отмена» для выхода.')
    )

    keyboard = [[types.InlineKeyboardButton(text='❌ Отмена', callback_data=f'cancel_rename_{squad_uuid}')]]

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def cancel_squad_rename(callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    squad_uuid = callback.data.split('_')[-1]

    await state.clear()

    refreshed_callback = callback.model_copy(update={'data': f'squad_edit_{squad_uuid}'}).as_(callback.bot)

    await show_squad_edit_menu(refreshed_callback, db_user, db)


@admin_required
@error_handler
async def process_squad_new_name(message: types.Message, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    squad_uuid = data.get('squad_uuid')
    old_name = data.get('squad_name')

    if not squad_uuid:
        await message.answer(texts.t('ADMIN_RW_SQUAD_RENAME_ERR', '❌ Ошибка: сквад не найден'))
        await state.clear()
        return

    new_name = message.text.strip()

    if not new_name:
        await message.answer(texts.t('ADMIN_RW_SQUAD_NAME_EMPTY', '❌ Название не может быть пустым. Попробуйте еще раз:'))
        return

    if len(new_name) < 2 or len(new_name) > 20:
        await message.answer(texts.t('ADMIN_RW_SQUAD_NAME_LENGTH', '❌ Название должно быть от 2 до 20 символов. Попробуйте еще раз:'))
        return

    import re

    if not re.match(r'^[A-Za-z0-9_-]+$', new_name):
        await message.answer(
            '❌ Название может содержать только буквы, цифры, дефисы и подчеркивания. Попробуйте еще раз:'
        )
        return

    if new_name == old_name:
        await message.answer(texts.t('ADMIN_RW_SQUAD_NAME_SAME', '❌ Новое название совпадает с текущим. Введите другое название:'))
        return

    remnawave_service = RemnaWaveService()
    success = await remnawave_service.rename_squad(squad_uuid, new_name)

    if success:
        await message.answer(
            f'✅ <b>Сквад успешно переименован!</b>\n\n'
            f'<b>Старое название:</b> {old_name}\n'
            f'<b>Новое название:</b> {new_name}',
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.t('ADMIN_RW_BTN_SQUAD_DETAIL', '📋 Детали сквада'), callback_data=f'admin_squad_manage_{squad_uuid}'
                        )
                    ],
                    [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_TO_SQUADS', '⬅️ К сквадам'), callback_data='admin_rw_squads')],
                ]
            ),
        )
        await state.clear()
    else:
        await message.answer(
            '❌ <b>Ошибка переименования сквада</b>\n\n'
            'Возможные причины:\n'
            '• Сквад с таким названием уже существует\n'
            '• Проблемы с подключением к API\n'
            '• Недостаточно прав\n\n'
            'Попробуйте другое название:',
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text='❌ Отмена', callback_data=f'cancel_rename_{squad_uuid}')]
                ]
            ),
        )


@admin_required
@error_handler
async def toggle_squad_inbound(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    parts = callback.data.split('_')
    inbound_index = int(parts[2])
    short_squad_uuid = parts[3]

    remnawave_service = RemnaWaveService()
    squads = await remnawave_service.get_all_squads()

    full_squad_uuid = None
    for squad in squads:
        if squad['uuid'].startswith(short_squad_uuid):
            full_squad_uuid = squad['uuid']
            break

    if not full_squad_uuid:
        await callback.answer(texts.t('ADMIN_RW_SQUAD_NOT_FOUND', '❌ Сквад не найден'), show_alert=True)
        return

    all_inbounds = await remnawave_service.get_all_inbounds()
    if inbound_index >= len(all_inbounds):
        await callback.answer(texts.t('ADMIN_RW_INBOUND_NOT_FOUND', '❌ Инбаунд не найден'), show_alert=True)
        return

    selected_inbound = all_inbounds[inbound_index]

    if full_squad_uuid not in squad_inbound_selections:
        squad_inbound_selections[full_squad_uuid] = set()

    if selected_inbound['uuid'] in squad_inbound_selections[full_squad_uuid]:
        squad_inbound_selections[full_squad_uuid].remove(selected_inbound['uuid'])
        await callback.answer(texts.t('ADMIN_RW_INBOUND_REMOVED', '➖ Убран: {tag}').format(tag=selected_inbound['tag']))
    else:
        squad_inbound_selections[full_squad_uuid].add(selected_inbound['uuid'])
        await callback.answer(texts.t('ADMIN_RW_INBOUND_ADDED', '➕ Добавлен: {tag}').format(tag=selected_inbound['tag']))

    text = f"""
🔧 <b>Изменение инбаундов</b>

<b>Сквад:</b> {squads[0]['name'] if squads else texts.t('ADMIN_RW_SQUAD_UNKNOWN', 'Неизвестно')}
<b>Выбрано инбаундов:</b> {len(squad_inbound_selections[full_squad_uuid])}

<b>Доступные инбаунды:</b>
"""

    keyboard = []
    for i, inbound in enumerate(all_inbounds[:15]):
        is_selected = inbound['uuid'] in squad_inbound_selections[full_squad_uuid]
        emoji = '✅' if is_selected else '☐'

        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=f'{emoji} {inbound["tag"]} ({inbound["type"]})',
                    callback_data=f'sqd_tgl_{i}_{short_squad_uuid}',
                )
            ]
        )

    keyboard.extend(
        [
            [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_SAVE', '💾 Сохранить изменения'), callback_data=f'sqd_save_{short_squad_uuid}')],
            [types.InlineKeyboardButton(text='⬅️ Назад', callback_data=f'sqd_edit_{short_squad_uuid}')],
        ]
    )

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))


@admin_required
@error_handler
async def save_squad_inbounds(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    short_squad_uuid = callback.data.split('_')[-1]

    remnawave_service = RemnaWaveService()
    squads = await remnawave_service.get_all_squads()

    full_squad_uuid = None
    squad_name = None
    for squad in squads:
        if squad['uuid'].startswith(short_squad_uuid):
            full_squad_uuid = squad['uuid']
            squad_name = squad['name']
            break

    if not full_squad_uuid:
        await callback.answer(texts.t('ADMIN_RW_SQUAD_NOT_FOUND', '❌ Сквад не найден'), show_alert=True)
        return

    selected_inbounds = squad_inbound_selections.get(full_squad_uuid, set())

    try:
        success = await remnawave_service.update_squad_inbounds(full_squad_uuid, list(selected_inbounds))

        if success:
            squad_inbound_selections.pop(full_squad_uuid, None)

            await callback.message.edit_text(
                f'✅ <b>Инбаунды сквада обновлены</b>\n\n'
                f'<b>Сквад:</b> {squad_name}\n'
                f'<b>Количество инбаундов:</b> {len(selected_inbounds)}',
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_TO_SQUADS', '⬅️ К сквадам'), callback_data='admin_rw_squads')],
                        [
                            types.InlineKeyboardButton(
                                text=texts.t('ADMIN_RW_BTN_SQUAD_DETAIL', '📋 Детали сквада'), callback_data=f'admin_squad_manage_{full_squad_uuid}'
                            )
                        ],
                    ]
                ),
            )
            await callback.answer(texts.t('ADMIN_RW_SQUAD_INBOUNDS_SAVED', '✅ Изменения сохранены!'))
        else:
            await callback.answer(texts.t('ADMIN_RW_SQUAD_INBOUNDS_SAVE_FAIL', '❌ Ошибка сохранения изменений'), show_alert=True)

    except Exception as e:
        logger.error('Error saving squad inbounds', error=e)
        await callback.answer(texts.t('ADMIN_RW_SQUAD_INBOUNDS_SAVE_ERR', '❌ Ошибка при сохранении'), show_alert=True)


@admin_required
@error_handler
async def show_squad_edit_menu_short(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    short_squad_uuid = callback.data.split('_')[-1]

    remnawave_service = RemnaWaveService()
    squads = await remnawave_service.get_all_squads()

    full_squad_uuid = None
    for squad in squads:
        if squad['uuid'].startswith(short_squad_uuid):
            full_squad_uuid = squad['uuid']
            break

    if not full_squad_uuid:
        await callback.answer(texts.t('ADMIN_RW_SQUAD_NOT_FOUND', '❌ Сквад не найден'), show_alert=True)
        return

    refreshed_callback = callback.model_copy(update={'data': f'squad_edit_{full_squad_uuid}'}).as_(callback.bot)

    await show_squad_edit_menu(refreshed_callback, db_user, db)


@admin_required
@error_handler
async def start_squad_creation(callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    await state.set_state(SquadCreateStates.waiting_for_name)

    text = (
        texts.t('ADMIN_RW_SQUAD_CREATE_TITLE', '➕ <b>Создание нового сквада</b>') + '\n\n'
        + texts.t('ADMIN_RW_SQUAD_CREATE_STEP1', '<b>Шаг 1 из 2: Название сквада</b>') + '\n\n'
        + texts.t('ADMIN_RW_SQUAD_CREATE_NAME_PROMPT', '📝 <b>Введите название для нового сквада:</b>') + '\n\n'
        + texts.t('ADMIN_RW_SQUAD_RENAME_RULES', '<i>Требования к названию:</i>\n• От 2 до 20 символов\n• Только буквы, цифры, дефисы и подчеркивания\n• Без пробелов и специальных символов')
        + '\n\n'
        + texts.t('ADMIN_RW_SQUAD_RENAME_HINT', 'Отправьте сообщение с названием или нажмите «Отмена» для выхода.')
    )

    keyboard = [[types.InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_squad_create')]]

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def process_squad_name(message: types.Message, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    squad_name = message.text.strip()

    if not squad_name:
        await message.answer(texts.t('ADMIN_RW_SQUAD_NAME_EMPTY', '❌ Название не может быть пустым. Попробуйте еще раз:'))
        return

    if len(squad_name) < 2 or len(squad_name) > 20:
        await message.answer(texts.t('ADMIN_RW_SQUAD_NAME_LENGTH', '❌ Название должно быть от 2 до 20 символов. Попробуйте еще раз:'))
        return

    import re

    if not re.match(r'^[A-Za-z0-9_-]+$', squad_name):
        await message.answer(
            '❌ Название может содержать только буквы, цифры, дефисы и подчеркивания. Попробуйте еще раз:'
        )
        return

    await state.update_data(squad_name=squad_name)
    await state.set_state(SquadCreateStates.selecting_inbounds)

    user_id = message.from_user.id
    squad_create_data[user_id] = {'name': squad_name, 'selected_inbounds': set()}

    remnawave_service = RemnaWaveService()
    all_inbounds = await remnawave_service.get_all_inbounds()

    if not all_inbounds:
        await message.answer(
            '❌ <b>Нет доступных инбаундов</b>\n\nДля создания сквада необходимо иметь хотя бы один инбаунд.',
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_TO_SQUADS', '⬅️ К сквадам'), callback_data='admin_rw_squads')]]
            ),
        )
        await state.clear()
        return

    text = f"""
➕ <b>Создание сквада: {squad_name}</b>

<b>Шаг 2 из 2: Выбор инбаундов</b>

<b>Выбрано инбаундов:</b> 0

<b>Доступные инбаунды:</b>
"""

    keyboard = []

    for i, inbound in enumerate(all_inbounds[:15]):
        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=f'☐ {inbound["tag"]} ({inbound["type"]})', callback_data=f'create_tgl_{i}'
                )
            ]
        )

    if len(all_inbounds) > 15:
        text += f'\n⚠️ Показано первые 15 из {len(all_inbounds)} инбаундов'

    keyboard.extend(
        [
            [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_CREATE_SQUAD', '✅ Создать сквад'), callback_data='create_squad_finish')],
            [types.InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_squad_create')],
        ]
    )

    await message.answer(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))


@admin_required
@error_handler
async def toggle_create_inbound(callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    inbound_index = int(callback.data.split('_')[-1])
    user_id = callback.from_user.id

    if user_id not in squad_create_data:
        await callback.answer(texts.t('ADMIN_RW_SESSION_ERR', '❌ Ошибка: данные сессии не найдены'), show_alert=True)
        await state.clear()
        return

    remnawave_service = RemnaWaveService()
    all_inbounds = await remnawave_service.get_all_inbounds()

    if inbound_index >= len(all_inbounds):
        await callback.answer(texts.t('ADMIN_RW_INBOUND_NOT_FOUND', '❌ Инбаунд не найден'), show_alert=True)
        return

    selected_inbound = all_inbounds[inbound_index]
    selected_inbounds = squad_create_data[user_id]['selected_inbounds']

    if selected_inbound['uuid'] in selected_inbounds:
        selected_inbounds.remove(selected_inbound['uuid'])
        await callback.answer(texts.t('ADMIN_RW_INBOUND_REMOVED', '➖ Убран: {tag}').format(tag=selected_inbound['tag']))
    else:
        selected_inbounds.add(selected_inbound['uuid'])
        await callback.answer(texts.t('ADMIN_RW_INBOUND_ADDED', '➕ Добавлен: {tag}').format(tag=selected_inbound['tag']))

    squad_name = squad_create_data[user_id]['name']

    text = f"""
➕ <b>Создание сквада: {squad_name}</b>

<b>Шаг 2 из 2: Выбор инбаундов</b>

<b>Выбрано инбаундов:</b> {len(selected_inbounds)}

<b>Доступные инбаунды:</b>
"""

    keyboard = []

    for i, inbound in enumerate(all_inbounds[:15]):
        is_selected = inbound['uuid'] in selected_inbounds
        emoji = '✅' if is_selected else '☐'

        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=f'{emoji} {inbound["tag"]} ({inbound["type"]})', callback_data=f'create_tgl_{i}'
                )
            ]
        )

    keyboard.extend(
        [
            [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_CREATE_SQUAD', '✅ Создать сквад'), callback_data='create_squad_finish')],
            [types.InlineKeyboardButton(text='❌ Отмена', callback_data='cancel_squad_create')],
        ]
    )

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))


@admin_required
@error_handler
async def finish_squad_creation(callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    user_id = callback.from_user.id

    if user_id not in squad_create_data:
        await callback.answer(texts.t('ADMIN_RW_SESSION_ERR', '❌ Ошибка: данные сессии не найдены'), show_alert=True)
        await state.clear()
        return

    squad_name = squad_create_data[user_id]['name']
    selected_inbounds = list(squad_create_data[user_id]['selected_inbounds'])

    if not selected_inbounds:
        await callback.answer(texts.t('ADMIN_RW_SQUAD_SELECT_INBOUND', '❌ Необходимо выбрать хотя бы один инбаунд'), show_alert=True)
        return

    remnawave_service = RemnaWaveService()
    success = await remnawave_service.create_squad(squad_name, selected_inbounds)

    squad_create_data.pop(user_id, None)
    await state.clear()

    if success:
        await callback.message.edit_text(
            f'✅ <b>Сквад успешно создан!</b>\n\n'
            f'<b>Название:</b> {squad_name}\n'
            f'<b>Количество инбаундов:</b> {len(selected_inbounds)}\n\n'
            f'Сквад готов к использованию!',
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_SQUAD_LIST', '📋 Список сквадов'), callback_data='admin_rw_squads')],
                    [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_TO_RW_PANEL', '⬅️ К панели Remnawave'), callback_data='admin_remnawave')],
                ]
            ),
        )
        await callback.answer(texts.t('ADMIN_RW_SQUAD_CREATED_TOAST', '✅ Сквад создан!'))
    else:
        await callback.message.edit_text(
            f'❌ <b>Ошибка создания сквада</b>\n\n'
            f'<b>Название:</b> {squad_name}\n\n'
            f'Возможные причины:\n'
            f'• Сквад с таким названием уже существует\n'
            f'• Проблемы с подключением к API\n'
            f'• Недостаточно прав\n'
            f'• Некорректные инбаунды',
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_RETRY', '🔄 Попробовать снова'), callback_data='admin_squad_create')],
                    [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_TO_SQUADS', '⬅️ К сквадам'), callback_data='admin_rw_squads')],
                ]
            ),
        )
        await callback.answer(texts.t('ADMIN_RW_SQUAD_CREATE_FAIL_TOAST', '❌ Ошибка создания сквада'), show_alert=True)


@admin_required
@error_handler
async def cancel_squad_creation(callback: types.CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    user_id = callback.from_user.id

    squad_create_data.pop(user_id, None)
    await state.clear()

    await show_squads_management(callback, db_user, db)


@admin_required
@error_handler
async def restart_all_nodes(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    remnawave_service = RemnaWaveService()
    success = await remnawave_service.restart_all_nodes()

    if success:
        await callback.message.edit_text(
            texts.t('ADMIN_RW_RESTART_ALL_OK', '✅ Команда перезагрузки всех нод отправлена'),
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_TO_NODES', '⬅️ К нодам'), callback_data='admin_rw_nodes')]]
            ),
        )
    else:
        await callback.message.edit_text(
            texts.t('ADMIN_RW_RESTART_ALL_FAIL', '❌ Ошибка перезагрузки нод'),
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_TO_NODES', '⬅️ К нодам'), callback_data='admin_rw_nodes')]]
            ),
        )

    await callback.answer()


@admin_required
@error_handler
async def show_sync_options(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    status = remnawave_sync_service.get_status()
    times_text = ', '.join(t.strftime('%H:%M') for t in status.times) if status.times else '—'
    next_run_text = format_datetime(status.next_run) if status.next_run else '—'
    last_result = '—'

    if status.last_run_finished_at:
        result_icon = '✅' if status.last_run_success else '❌'
        result_label = texts.t('ADMIN_RW_SYNC_RESULT_OK', 'успешно') if status.last_run_success else texts.t('ADMIN_RW_SYNC_RESULT_ERR', 'с ошибками')
        finished_text = format_datetime(status.last_run_finished_at)
        last_result = f'{result_icon} {result_label} ({finished_text})'
    elif status.last_run_started_at:
        last_result = texts.t('ADMIN_RW_SYNC_LAST_RUNNING', '⏳ Запущено {time}').format(
            time=format_datetime(status.last_run_started_at)
        )

    status_on = texts.t('ADMIN_RW_SYNC_STATUS_ON', '✅ Включена')
    status_off = texts.t('ADMIN_RW_SYNC_STATUS_OFF', '❌ Отключена')
    status_lines = [
        texts.t('ADMIN_RW_SYNC_STATUS_LINE', '⚙️ Статус: {status}').format(
            status=status_on if status.enabled else status_off
        ),
        texts.t('ADMIN_RW_SYNC_SCHEDULE_LINE', '🕒 Расписание: {times}').format(times=times_text),
        texts.t('ADMIN_RW_SYNC_NEXT_LINE', '📅 Следующий запуск: {next}').format(
            next=next_run_text if status.enabled else '—'
        ),
        texts.t('ADMIN_RW_SYNC_LAST_LINE', '📊 Последний запуск: {last}').format(last=last_result),
    ]

    text = texts.t(
        'ADMIN_RW_SYNC_PANEL_TITLE',
        '🔄 <b>Синхронизация с Remnawave</b>',
    ) + '\n\n' + texts.t('ADMIN_RW_SYNC_PANEL_BODY', '') + '\n' + '\n'.join(status_lines)

    keyboard = [
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_SYNC_FULL', '🔄 Запустить полную синхронизацию'), callback_data='sync_all_users')],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_SYNC_TO_PANEL', '⬆️ Синхронизация в панель'), callback_data='sync_to_panel')],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_AUTO_SYNC', '⚙️ Настройки автосинхронизации'), callback_data='admin_rw_auto_sync')],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'), callback_data='admin_remnawave')],
    ]

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required@admin_required
@error_handler
async def show_auto_sync_settings(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    await state.clear()
    status = remnawave_sync_service.get_status()
    text, keyboard = _build_auto_sync_view(texts, status)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML',
    )
    await callback.answer()


@admin_required
@error_handler
async def toggle_auto_sync_setting(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    await state.clear()
    new_value = not bool(settings.REMNAWAVE_AUTO_SYNC_ENABLED)
    await bot_configuration_service.set_value(
        db,
        'REMNAWAVE_AUTO_SYNC_ENABLED',
        new_value,
    )
    await db.commit()

    status = remnawave_sync_service.get_status()
    text, keyboard = _build_auto_sync_view(texts, status)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML',
    )
    await callback.answer(
        texts.t('ADMIN_RW_SYNC_TOGGLED_ON', 'Автосинхронизация включена')
        if new_value
        else texts.t('ADMIN_RW_SYNC_TOGGLED_OFF', 'Автосинхронизация отключена')
    )


@admin_required
@error_handler
async def prompt_auto_sync_schedule(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    status = remnawave_sync_service.get_status()
    current_schedule = ', '.join(t.strftime('%H:%M') for t in status.times) if status.times else '—'

    instructions = texts.t(
        'ADMIN_RW_SYNC_SCHEDULE_TITLE',
        '🕒 <b>Настройка расписания автосинхронизации</b>',
    ) + '\n\n' + texts.t(
        'ADMIN_RW_SYNC_SCHEDULE_BODY',
        'Укажите время запуска через запятую или с новой строки в формате HH:MM.\n'
        'Текущее расписание: <code>{schedule}</code>\n\n'
        'Примеры: <code>03:00, 15:30</code> или <code>00:15\n06:00\n18:45</code>\n\n'
        '<b>Отмена</b> — вернуться без изменений.',
    ).format(schedule=current_schedule)

    await state.set_state(RemnaWaveSyncStates.waiting_for_schedule)
    await state.update_data(
        auto_sync_message_id=callback.message.message_id,
        auto_sync_message_chat_id=callback.message.chat.id,
    )

    await callback.message.edit_text(
        instructions,
        parse_mode='HTML',
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text='❌ Отмена',
                        callback_data='remnawave_auto_sync_cancel',
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def cancel_auto_sync_schedule(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    texts = get_texts(db_user.language)
    await state.clear()
    status = remnawave_sync_service.get_status()
    text, keyboard = _build_auto_sync_view(texts, status)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode='HTML',
    )
    await callback.answer(texts.t('ADMIN_RW_SYNC_SCHEDULE_CANCELLED', 'Изменение расписания отменено'))


@admin_required
@error_handler
async def run_auto_sync_now(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    texts = get_texts(db_user.language)
    if remnawave_sync_service.get_status().is_running:
        await callback.answer(texts.t('ADMIN_RW_SYNC_ALREADY_RUNNING', 'Синхронизация уже выполняется'), show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        texts.t('ADMIN_RW_SYNC_STARTING', '🔄 Запуск автосинхронизации...\n\nПодождите, это может занять несколько минут.'),
        parse_mode='HTML',
    )
    await callback.answer(texts.t('ADMIN_RW_SYNC_STARTED_TOAST', 'Автосинхронизация запущена'))

    result = await remnawave_sync_service.run_sync_now(reason='manual')
    status = remnawave_sync_service.get_status()
    base_text, keyboard = _build_auto_sync_view(texts, status)

    if not result.get('started'):
        await callback.message.edit_text(
            texts.t('ADMIN_RW_SYNC_ALREADY_MSG', '⚠️ <b>Синхронизация уже выполняется</b>\n\n') + base_text,
            reply_markup=keyboard,
            parse_mode='HTML',
        )
        return

    if result.get('success'):
        user_stats = result.get('user_stats') or {}
        server_stats = result.get('server_stats') or {}
        summary = (
            '✅ <b>Синхронизация завершена</b>\n'
            f'👥 Пользователи: создано {user_stats.get("created", 0)}, обновлено {user_stats.get("updated", 0)}, '
            f'деактивировано {user_stats.get("deleted", user_stats.get("deactivated", 0))}, ошибок {user_stats.get("errors", 0)}\n'
            f'🌐 Серверы: создано {server_stats.get("created", 0)}, обновлено {server_stats.get("updated", 0)}, удалено {server_stats.get("removed", 0)}\n\n'
        )
        final_text = summary + base_text
        await callback.message.edit_text(
            final_text,
            reply_markup=keyboard,
            parse_mode='HTML',
        )
    else:
        error_text = result.get('error') or texts.t('ADMIN_RW_SYNC_UNKNOWN_ERR', 'Неизвестная ошибка')
        summary = f'❌ <b>Синхронизация завершилась с ошибкой</b>\nПричина: {error_text}\n\n'
        await callback.message.edit_text(
            summary + base_text,
            reply_markup=keyboard,
            parse_mode='HTML',
        )


@admin_required
@error_handler
async def save_auto_sync_schedule(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    text = (message.text or '').strip()
    data = await state.get_data()

    if text.lower() in {'отмена', 'cancel'}:
        await state.clear()
        status = remnawave_sync_service.get_status()
        view_text, keyboard = _build_auto_sync_view(texts, status)
        message_id = data.get('auto_sync_message_id')
        chat_id = data.get('auto_sync_message_chat_id', message.chat.id)
        if message_id:
            await message.bot.edit_message_text(
                view_text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=keyboard,
                parse_mode='HTML',
            )
        else:
            await message.answer(
                view_text,
                reply_markup=keyboard,
                parse_mode='HTML',
            )
        await message.answer(texts.t('ADMIN_RW_SYNC_SCHEDULE_CANCEL_MSG', 'Настройка расписания отменена'))
        return

    parsed_times = settings.parse_daily_time_list(text)

    if not parsed_times:
        await message.answer(
            texts.t('ADMIN_RW_SYNC_TIME_PARSE_FAIL', '❌ Не удалось распознать время. Используйте формат HH:MM, например 03:00 или 18:45.'),
        )
        return

    normalized_value = ', '.join(t.strftime('%H:%M') for t in parsed_times)
    await bot_configuration_service.set_value(
        db,
        'REMNAWAVE_AUTO_SYNC_TIMES',
        normalized_value,
    )
    await db.commit()

    status = remnawave_sync_service.get_status()
    view_text, keyboard = _build_auto_sync_view(texts, status)
    message_id = data.get('auto_sync_message_id')
    chat_id = data.get('auto_sync_message_chat_id', message.chat.id)

    if message_id:
        await message.bot.edit_message_text(
            view_text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=keyboard,
            parse_mode='HTML',
        )
    else:
        await message.answer(
            view_text,
            reply_markup=keyboard,
            parse_mode='HTML',
        )

    await state.clear()
    await message.answer(texts.t('ADMIN_RW_SYNC_SCHEDULE_UPDATED', '✅ Расписание автосинхронизации обновлено'))


@admin_required
@error_handler
async def sync_all_users(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    """Выполняет полную синхронизацию всех пользователей"""

    progress_text = texts.t(
        'ADMIN_RW_SYNC_FULL_PROGRESS',
        '🔄 <b>Выполняется полная синхронизация...</b>\n\n'
        '📋 Этапы:\n'
        '• Загрузка ВСЕХ пользователей из панели Remnawave\n'
        '• Создание новых пользователей в боте\n'
        '• Обновление существующих пользователей\n'
        '• Деактивация подписок отсутствующих пользователей\n'
        '• Сохранение балансов\n\n'
        '⏳ Пожалуйста, подождите...',
    )

    await callback.message.edit_text(progress_text, reply_markup=None)

    remnawave_service = RemnaWaveService()
    stats = await remnawave_service.sync_users_from_panel(db, 'all')

    total_operations = stats['created'] + stats['updated'] + stats.get('deleted', 0)

    if stats['errors'] == 0:
        status_emoji = '✅'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_OK', 'успешно завершена')
    elif stats['errors'] < total_operations:
        status_emoji = '⚠️'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_WARN', 'завершена с предупреждениями')
    else:
        status_emoji = '❌'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_ERR', 'завершена с ошибками')

    text = texts.t(
        'ADMIN_RW_SYNC_FULL_RESULT',
        '{emoji} <b>Полная синхронизация {status}</b>\n\n📊 <b>Результат:</b>\n• 🆕 Создано: {created}\n• 🔄 Обновлено: {updated}\n• 🗑️ Деактивировано: {deleted}\n• ❌ Ошибок: {errors}',
    ).format(
        emoji=status_emoji,
        status=status_text,
        created=stats['created'],
        updated=stats['updated'],
        deleted=stats.get('deleted', 0),
        errors=stats['errors'],
    )

    if stats.get('deleted', 0) > 0:
        text += texts.t('ADMIN_RW_SYNC_DEACTIVATED_BLOCK', '')

    if stats['errors'] > 0:
        text += texts.t('ADMIN_RW_SYNC_ERRORS_BLOCK', '')

    text += texts.t('ADMIN_RW_SYNC_RECOMMEND', '')

    keyboard = []

    if stats['errors'] > 0:
        keyboard.append([types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_RETRY_SYNC', '🔄 Повторить синхронизацию'), callback_data='sync_all_users')])

    keyboard.extend(
        [
            [
                types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_SYSTEM_STATS', '📊 Статистика системы'), callback_data='admin_rw_system'),
                types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_NODES', '🌐 Ноды'), callback_data='admin_rw_nodes'),
            ],
            [types.InlineKeyboardButton(text='⬅️ Назад', callback_data='admin_remnawave')],
        ]
    )

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def sync_users_to_panel(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t('ADMIN_RW_SYNC_TO_PANEL_PROGRESS', '⬆️ Выполняется синхронизация данных бота в панель Remnawave...\n\nЭто может занять несколько минут.'),
        reply_markup=None,
    )

    remnawave_service = RemnaWaveService()
    stats = await remnawave_service.sync_users_to_panel(db)

    if stats['errors'] == 0:
        status_emoji = '✅'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_OK', 'успешно завершена')
    else:
        status_emoji = '⚠️' if (stats['created'] + stats['updated']) > 0 else '❌'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_WARN', 'завершена с предупреждениями') if status_emoji == '⚠️' else 'завершена с ошибками'

    text = texts.t(
        'ADMIN_RW_SYNC_TO_PANEL_RESULT',
        '{emoji} <b>Синхронизация в панель {status}</b>\n\n📊 <b>Результаты:</b>\n• 🆕 Создано: {created}\n• 🔄 Обновлено: {updated}\n• ❌ Ошибок: {errors}',
    ).format(emoji=status_emoji, status=status_text, created=stats['created'], updated=stats['updated'], errors=stats['errors'])

    keyboard = [
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_RETRY', '🔄 Повторить'), callback_data='sync_to_panel')],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_SYNC_FULL', '🔄 Полная синхронизация'), callback_data='sync_all_users')],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_TO_SYNC', '⬅️ К синхронизации'), callback_data='admin_rw_sync')],
    ]

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
    )
    await callback.answer()


@admin_required
@error_handler
async def show_sync_recommendations(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(texts.t('ADMIN_RW_SYNC_ANALYZING', '🔍 Анализируем состояние синхронизации...'), reply_markup=None)

    remnawave_service = RemnaWaveService()
    recommendations = await remnawave_service.get_sync_recommendations(db)

    priority_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}

    text = f"""
💡 <b>Рекомендации по синхронизации</b>

{priority_emoji.get(recommendations['priority'], '🟢')} <b>Приоритет:</b> {recommendations['priority'].upper()}
⏱️ <b>Время выполнения:</b> {recommendations['estimated_time']}

<b>Рекомендуемое действие:</b>
"""

    if recommendations['sync_type'] == 'all':
        text += '🔄 Полная синхронизация'
    elif recommendations['sync_type'] == 'update_only':
        text += '📈 Обновление данных'
    elif recommendations['sync_type'] == 'new_only':
        text += '🆕 Синхронизация новых'
    else:
        text += '✅ Синхронизация не требуется'

    text += '\n\n<b>Причины:</b>\n'
    for reason in recommendations['reasons']:
        text += f'• {reason}\n'

    keyboard = []

    if recommendations['should_sync'] and recommendations['sync_type'] != 'none':
        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_RW_BTN_RUN_REC', '✅ Выполнить рекомендацию'),
                    callback_data=f'sync_{recommendations["sync_type"]}_users'
                    if recommendations['sync_type'] != 'update_only'
                    else 'sync_update_data',
                )
            ]
        )

    keyboard.extend(
        [
            [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_OTHER_SYNC', '🔄 Другие опции'), callback_data='admin_rw_sync')],
            [types.InlineKeyboardButton(text='⬅️ Назад', callback_data='admin_remnawave')],
        ]
    )

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def validate_subscriptions(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t('ADMIN_RW_VALIDATE_PROGRESS', '🔍 Выполняется валидация подписок...\n\nПроверяем данные, может занять несколько минут.'), reply_markup=None
    )

    remnawave_service = RemnaWaveService()
    stats = await remnawave_service.validate_and_fix_subscriptions(db)

    if stats['errors'] == 0:
        status_emoji = '✅'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_OK', 'успешно завершена')
    else:
        status_emoji = '⚠️'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_ERR', 'завершена с ошибками')

    text = f"""
{status_emoji} <b>Валидация {status_text}</b>

📊 <b>Результаты:</b>
• 🔍 Проверено подписок: {stats['checked']}
• 🔧 Исправлено подписок: {stats['fixed']}
• ⚠️ Найдено проблем: {stats['issues_found']}
• ❌ Ошибок: {stats['errors']}
"""

    if stats['fixed'] > 0:
        text += '\n✅ <b>Исправленные проблемы:</b>\n'
        text += '• Статусы просроченных подписок\n'
        text += '• Отсутствующие данные Remnawave\n'
        text += '• Некорректные лимиты трафика\n'
        text += '• Настройки устройств\n'

    if stats['errors'] > 0:
        text += '\n⚠️ Обнаружены ошибки при обработке.\nПроверьте логи для подробной информации.'

    keyboard = [
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_RETRY_VALIDATE', '🔄 Повторить валидацию'), callback_data='sync_validate')],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_SYNC_FULL', '🔄 Полная синхронизация'), callback_data='sync_all_users')],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_TO_SYNC', '⬅️ К синхронизации'), callback_data='admin_rw_sync')],
    ]

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def cleanup_subscriptions(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t('ADMIN_RW_CLEANUP_PROGRESS', '🧹 Выполняется очистка неактуальных подписок...\n\nУдаляем подписки пользователей, отсутствующих в панели.'),
        reply_markup=None,
    )

    remnawave_service = RemnaWaveService()
    stats = await remnawave_service.cleanup_orphaned_subscriptions(db)

    if stats['errors'] == 0:
        status_emoji = '✅'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_OK', 'успешно завершена')
    else:
        status_emoji = '⚠️'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_ERR', 'завершена с ошибками')

    text = f"""
{status_emoji} <b>Очистка {status_text}</b>

📊 <b>Результаты:</b>
• 🔍 Проверено подписок: {stats['checked']}
• 🗑️ Деактивировано: {stats['deactivated']}
• ❌ Ошибок: {stats['errors']}
"""

    if stats['deactivated'] > 0:
        text += '\n🗑️ <b>Деактивированные подписки:</b>\n'
        text += 'Отключены подписки пользователей, которые\n'
        text += 'отсутствуют в панели Remnawave.\n'
    else:
        text += '\n✅ Все подписки актуальны!\nНеактуальных подписок не найдено.'

    if stats['errors'] > 0:
        text += '\n⚠️ Обнаружены ошибки при обработке.\nПроверьте логи для подробной информации.'

    keyboard = [
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_RETRY_CLEANUP', '🔄 Повторить очистку'), callback_data='sync_cleanup')],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_VALIDATE', '🔍 Валидация'), callback_data='sync_validate')],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_TO_SYNC', '⬅️ К синхронизации'), callback_data='admin_rw_sync')],
    ]

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def force_cleanup_all_orphaned_users(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        '🗑️ Выполняется принудительная очистка всех пользователей, отсутствующих в панели...\n\n'
        '⚠️ ВНИМАНИЕ: Это полностью удалит ВСЕ данные пользователей!\n'
        '📊 Включая: транзакции, реферальные доходы, промокоды, серверы, балансы\n\n'
        '⏳ Пожалуйста, подождите...',
        reply_markup=None,
    )

    remnawave_service = RemnaWaveService()
    stats = await remnawave_service.cleanup_orphaned_subscriptions(db)

    if stats['errors'] == 0:
        status_emoji = '✅'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_OK', 'успешно завершена')
    else:
        status_emoji = '⚠️'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_ERR', 'завершена с ошибками')

    text = f"""
{status_emoji} <b>Принудительная очистка {status_text}</b>

📊 <b>Результаты:</b>
• 🔍 Проверено подписок: {stats['checked']}
• 🗑️ Полностью очищено: {stats['deactivated']}
• ❌ Ошибок: {stats['errors']}
"""

    if stats['deactivated'] > 0:
        text += """

🗑️ <b>Полностью очищенные данные:</b>
• Подписки сброшены к начальному состоянию
• Удалены ВСЕ транзакции пользователей
• Удалены ВСЕ реферальные доходы
• Удалены использования промокодов
• Сброшены балансы к нулю
• Удалены подключенные серверы
• Сброшены HWID устройства в Remnawave
• Очищены Remnawave UUID
"""
    else:
        text += '\n✅ Неактуальных подписок не найдено!\nВсе пользователи синхронизированы с панелью.'

    if stats['errors'] > 0:
        text += '\n⚠️ Обнаружены ошибки при обработке.\nПроверьте логи для подробной информации.'

    keyboard = [
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_RETRY_CLEANUP', '🔄 Повторить очистку'), callback_data='force_cleanup_orphaned')],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_SYNC_FULL', '🔄 Полная синхронизация'), callback_data='sync_all_users')],
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_TO_SYNC', '⬅️ К синхронизации'), callback_data='admin_rw_sync')],
    ]

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def confirm_force_cleanup(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    text = """
⚠️ <b>ВНИМАНИЕ! ОПАСНАЯ ОПЕРАЦИЯ!</b>

🗑️ <b>Принудительная очистка полностью удалит:</b>
• ВСЕ транзакции пользователей отсутствующих в панели
• ВСЕ реферальные доходы и связи
• ВСЕ использования промокодов
• ВСЕ подключенные серверы подписок
• ВСЕ балансы (сброс к нулю)
• ВСЕ HWID устройства в Remnawave
• ВСЕ Remnawave UUID и ссылки

⚡ <b>Это действие НЕОБРАТИМО!</b>

Используйте только если:
• Обычная синхронизация не помогает
• Нужно полностью очистить "мусорные" данные
• После массового удаления пользователей из панели

❓ <b>Вы действительно хотите продолжить?</b>
"""

    keyboard = [
        [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_FORCE_CLEANUP', '🗑️ ДА, ОЧИСТИТЬ ВСЕ'), callback_data='force_cleanup_orphaned')],
        [types.InlineKeyboardButton(text='❌ Отмена', callback_data='admin_rw_sync')],
    ]

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def sync_users(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    sync_type = callback.data.split('_')[-2] + '_' + callback.data.split('_')[-1]

    progress_text = texts.t('ADMIN_RW_SYNC_PROGRESS', '🔄 Выполняется синхронизация...\n\n')

    if sync_type == 'all_users':
        progress_text += '📋 Тип: Полная синхронизация\n'
        progress_text += '• Создание новых пользователей\n'
        progress_text += '• Обновление существующих\n'
        progress_text += '• Удаление неактуальных подписок\n'
    elif sync_type == 'new_users':
        progress_text += '📋 Тип: Только новые пользователи\n'
        progress_text += '• Создание пользователей из панели\n'
    elif sync_type == 'update_data':
        progress_text += '📋 Тип: Обновление данных\n'
        progress_text += '• Обновление информации о трафике\n'
        progress_text += '• Синхронизация подписок\n'

    progress_text += '\n⏳ Пожалуйста, подождите...'

    await callback.message.edit_text(progress_text, reply_markup=None)

    remnawave_service = RemnaWaveService()

    sync_map = {'all_users': 'all', 'new_users': 'new_only', 'update_data': 'update_only'}

    stats = await remnawave_service.sync_users_from_panel(db, sync_map.get(sync_type, 'all'))

    total_operations = stats['created'] + stats['updated'] + stats.get('deleted', 0)
    stats['created'] + stats['updated'] + stats.get('deleted', 0)

    if stats['errors'] == 0:
        status_emoji = '✅'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_OK', 'успешно завершена')
    elif stats['errors'] < total_operations:
        status_emoji = '⚠️'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_WARN', 'завершена с предупреждениями')
    else:
        status_emoji = '❌'
        status_text = texts.t('ADMIN_RW_SYNC_STATUS_ERR', 'завершена с ошибками')

    text = f"""
{status_emoji} <b>Синхронизация {status_text}</b>

📊 <b>Результат:</b>
"""

    if sync_type == 'all_users':
        text += f'• 🆕 Создано: {stats["created"]}\n'
        text += f'• 🔄 Обновлено: {stats["updated"]}\n'
        if 'deleted' in stats:
            text += f'• 🗑️ Удалено: {stats["deleted"]}\n'
        text += f'• ❌ Ошибок: {stats["errors"]}\n'
    elif sync_type == 'new_users':
        text += f'• 🆕 Создано: {stats["created"]}\n'
        text += f'• ❌ Ошибок: {stats["errors"]}\n'
        if stats['created'] == 0 and stats['errors'] == 0:
            text += '\n💡 Новых пользователей не найдено'
    elif sync_type == 'update_data':
        text += f'• 🔄 Обновлено: {stats["updated"]}\n'
        text += f'• ❌ Ошибок: {stats["errors"]}\n'
        if stats['updated'] == 0 and stats['errors'] == 0:
            text += '\n💡 Все данные актуальны'

    if stats['errors'] > 0:
        text += '\n⚠️ <b>Внимание:</b>\n'
        text += 'Некоторые операции завершились с ошибками.\n'
        text += 'Проверьте логи для получения подробной информации.'

    if sync_type == 'all_users' and 'deleted' in stats and stats['deleted'] > 0:
        text += '\n🗑️ <b>Удаленные подписки:</b>\n'
        text += 'Деактивированы подписки пользователей,\n'
        text += 'которые отсутствуют в панели Remnawave.'

    text += '\n\n💡 <b>Рекомендации:</b>\n'
    if sync_type == 'all_users':
        text += '• Полная синхронизация выполнена\n'
        text += '• Рекомендуется запускать раз в день\n'
    elif sync_type == 'new_users':
        text += '• Синхронизация новых пользователей\n'
        text += '• Используйте при массовом добавлении\n'
    elif sync_type == 'update_data':
        text += '• Обновление данных о трафике\n'
        text += '• Запускайте для актуализации статистики\n'

    keyboard = []

    if stats['errors'] > 0:
        keyboard.append([types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_RETRY_SYNC', '🔄 Повторить синхронизацию'), callback_data=callback.data)])

    if sync_type != 'all_users':
        keyboard.append([types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_SYNC_FULL', '🔄 Полная синхронизация'), callback_data='sync_all_users')])

    keyboard.extend(
        [
            [
                types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_SYSTEM_STATS', '📊 Статистика системы'), callback_data='admin_rw_system'),
                types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_NODES', '🌐 Ноды'), callback_data='admin_rw_nodes'),
            ],
            [types.InlineKeyboardButton(text='⬅️ Назад', callback_data='admin_remnawave')],
        ]
    )

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


@admin_required
@error_handler
async def show_squads_management(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    remnawave_service = RemnaWaveService()
    squads = await remnawave_service.get_all_squads()

    text = texts.t('ADMIN_RW_SQUADS_TITLE', '🌍 <b>Управление сквадами</b>\n\n')
    keyboard = []

    if squads:
        for squad in squads:
            text += f'🔹 <b>{squad["name"]}</b>\n'
            text += texts.t('ADMIN_RW_SQUAD_MEMBERS', '- Участников: {count}').format(count=squad['members_count']) + '\n'
            text += texts.t('ADMIN_RW_SQUAD_INBOUNDS', '- Инбаундов: {count}').format(count=squad['inbounds_count']) + '\n\n'

            keyboard.append(
                [
                    types.InlineKeyboardButton(
                        text=f'⚙️ {squad["name"]}', callback_data=f'admin_squad_manage_{squad["uuid"]}'
                    )
                ]
            )
    else:
        text += texts.t('ADMIN_RW_SQUAD_NOT_FOUND', 'Сквады не найдены')

    keyboard.extend(
        [
            [types.InlineKeyboardButton(text=texts.t('ADMIN_RW_BTN_CREATE_SQUAD', '➕ Создать сквад'), callback_data='admin_squad_create')],
            [types.InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'), callback_data='admin_remnawave')],
        ]
    )

    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_remnawave_menu, F.data == 'admin_remnawave')
    dp.callback_query.register(show_system_stats, F.data == 'admin_rw_system')
    dp.callback_query.register(show_traffic_stats, F.data == 'admin_rw_traffic')
    dp.callback_query.register(show_nodes_management, F.data == 'admin_rw_nodes')
    dp.callback_query.register(show_node_details, F.data.startswith('admin_node_manage_'))
    dp.callback_query.register(show_node_statistics, F.data.startswith('node_stats_'))
    dp.callback_query.register(manage_node, F.data.startswith('node_enable_'))
    dp.callback_query.register(manage_node, F.data.startswith('node_disable_'))
    dp.callback_query.register(manage_node, F.data.startswith('node_restart_'))
    dp.callback_query.register(restart_all_nodes, F.data == 'admin_restart_all_nodes')
    dp.callback_query.register(show_sync_options, F.data == 'admin_rw_sync')
    dp.callback_query.register(show_auto_sync_settings, F.data == 'admin_rw_auto_sync')
    dp.callback_query.register(toggle_auto_sync_setting, F.data == 'remnawave_auto_sync_toggle')
    dp.callback_query.register(prompt_auto_sync_schedule, F.data == 'remnawave_auto_sync_times')
    dp.callback_query.register(cancel_auto_sync_schedule, F.data == 'remnawave_auto_sync_cancel')
    dp.callback_query.register(run_auto_sync_now, F.data == 'remnawave_auto_sync_run')
    dp.callback_query.register(sync_all_users, F.data == 'sync_all_users')
    dp.callback_query.register(sync_users_to_panel, F.data == 'sync_to_panel')
    dp.callback_query.register(show_squad_migration_menu, F.data == 'admin_rw_migration')
    dp.callback_query.register(paginate_migration_source, F.data.startswith('admin_migration_source_page_'))
    dp.callback_query.register(handle_migration_source_selection, F.data.startswith('admin_migration_source_'))
    dp.callback_query.register(paginate_migration_target, F.data.startswith('admin_migration_target_page_'))
    dp.callback_query.register(handle_migration_target_selection, F.data.startswith('admin_migration_target_'))
    dp.callback_query.register(change_migration_target, F.data == 'admin_migration_change_target')
    dp.callback_query.register(confirm_squad_migration, F.data == 'admin_migration_confirm')
    dp.callback_query.register(cancel_squad_migration, F.data == 'admin_migration_cancel')
    dp.callback_query.register(handle_migration_page_info, F.data == 'admin_migration_page_info')
    dp.callback_query.register(show_squads_management, F.data == 'admin_rw_squads')
    dp.callback_query.register(show_squad_details, F.data.startswith('admin_squad_manage_'))
    dp.callback_query.register(manage_squad_action, F.data.startswith('squad_add_users_'))
    dp.callback_query.register(manage_squad_action, F.data.startswith('squad_remove_users_'))
    dp.callback_query.register(manage_squad_action, F.data.startswith('squad_delete_'))
    dp.callback_query.register(
        show_squad_edit_menu, F.data.startswith('squad_edit_') & ~F.data.startswith('squad_edit_inbounds_')
    )
    dp.callback_query.register(show_squad_inbounds_selection, F.data.startswith('squad_edit_inbounds_'))
    dp.callback_query.register(show_squad_rename_form, F.data.startswith('squad_rename_'))
    dp.callback_query.register(cancel_squad_rename, F.data.startswith('cancel_rename_'))
    dp.callback_query.register(toggle_squad_inbound, F.data.startswith('sqd_tgl_'))
    dp.callback_query.register(save_squad_inbounds, F.data.startswith('sqd_save_'))
    dp.callback_query.register(show_squad_edit_menu_short, F.data.startswith('sqd_edit_'))
    dp.callback_query.register(start_squad_creation, F.data == 'admin_squad_create')
    dp.callback_query.register(cancel_squad_creation, F.data == 'cancel_squad_create')
    dp.callback_query.register(toggle_create_inbound, F.data.startswith('create_tgl_'))
    dp.callback_query.register(finish_squad_creation, F.data == 'create_squad_finish')

    dp.message.register(process_squad_new_name, SquadRenameStates.waiting_for_new_name, F.text)

    dp.message.register(process_squad_name, SquadCreateStates.waiting_for_name, F.text)

    dp.message.register(
        save_auto_sync_schedule,
        RemnaWaveSyncStates.waiting_for_schedule,
        F.text,
    )
