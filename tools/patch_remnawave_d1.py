#!/usr/bin/env python3
"""Patch remaining hardcoded Cyrillic in remnawave.py for Slice D1."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "app/handlers/admin/remnawave.py"

HELPER = '''

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
    ) + '\\n\\n'
    text += texts.t('ADMIN_RW_NODE_STATUS_HEADER', '<b>Статус:</b>') + '\\n'
    text += texts.t('ADMIN_RW_NODE_ONLINE', '- Онлайн: {emoji} {value}').format(
        emoji=status_emoji, value=_rw_yes_no(texts, node['is_node_online'])
    ) + '\\n'
    text += texts.t('ADMIN_RW_NODE_XRAY', '- Xray: {emoji} {value}').format(
        emoji=xray_emoji, value=_rw_xray_state(texts, node['is_xray_running'])
    ) + '\\n'
    text += texts.t('ADMIN_RW_NODE_CONNECTED', '- Подключена: {value}').format(
        value=_rw_connected(texts, node['is_connected'])
    ) + '\\n'
    text += texts.t('ADMIN_RW_NODE_DISABLED', '- Отключена: {value}').format(
        value=_rw_disabled_flag(texts, node['is_disabled'])
    ) + '\\n'
    text += texts.t('ADMIN_RW_NODE_STATUS_CHANGE', '- Изменение статуса: {time}').format(time=status_change) + '\\n'
    text += texts.t('ADMIN_RW_NODE_MESSAGE', '- Сообщение: {message}').format(
        message=html.escape(str(node.get('last_status_message') or '—'))
    ) + '\\n'
    text += texts.t('ADMIN_RW_NODE_XRAY_UPTIME', '- Uptime Xray: {uptime}').format(uptime=xray_uptime_str) + '\\n'

    if include_versions:
        text += '\\n' + texts.t('ADMIN_RW_NODE_VERSIONS', '<b>Версии:</b>') + '\\n'
        text += texts.t('ADMIN_RW_NODE_XRAY_VER', '- Xray: {version}').format(version=xray_ver) + '\\n'
        text += texts.t('ADMIN_RW_NODE_VER', '- Node: {version}').format(version=node_ver) + '\\n'

    text += '\\n' + texts.t('ADMIN_RW_NODE_INFO', '<b>Информация:</b>') + '\\n'
    text += texts.t('ADMIN_RW_NODE_ADDRESS', '- Адрес: {address}').format(address=html.escape(node['address'])) + '\\n'
    text += texts.t('ADMIN_RW_NODE_COUNTRY', '- Страна: {code}').format(code=html.escape(node['country_code'])) + '\\n'
    text += texts.t('ADMIN_RW_NODE_USERS', '- Пользователей онлайн: {count}').format(count=node['users_online']) + '\\n'
    text += texts.t('ADMIN_RW_NODE_CPU', '- CPU: {info}').format(info=cpu_info) + '\\n'
    text += texts.t('ADMIN_RW_NODE_RAM', '- RAM: {ram}').format(ram=total_ram) + '\\n'
    text += texts.t('ADMIN_RW_NODE_PROVIDER', '- Провайдер: {provider}').format(
        provider=html.escape(str(node.get('provider_uuid') or '—'))
    ) + '\\n'
    text += '\\n' + texts.t('ADMIN_RW_NODE_TRAFFIC_HEADER', '<b>Трафик:</b>') + '\\n'
    text += texts.t('ADMIN_RW_NODE_TRAFFIC_USED', '- Использовано: {value}').format(
        value=format_bytes(node['traffic_used_bytes'])
    ) + '\\n'
    text += texts.t('ADMIN_RW_NODE_TRAFFIC_LIMIT', '- Лимит: {value}').format(
        value=_rw_traffic_limit(texts, node['traffic_limit_bytes'])
    ) + '\\n'
    text += texts.t('ADMIN_RW_NODE_TRACKING', '- Трекинг: {value}').format(
        value=_rw_tracking(texts, node.get('is_traffic_tracking_active'))
    ) + '\\n'
    text += texts.t('ADMIN_RW_NODE_RESET_DAY', '- День сброса: {day}').format(
        day=node.get('traffic_reset_day') or '—'
    ) + '\\n'
    text += texts.t('ADMIN_RW_NODE_NOTIFY', '- Уведомления: {percent}').format(percent=notify_percent) + '\\n'
    text += texts.t('ADMIN_RW_NODE_MULTIPLIER', '- Множитель: {value}').format(
        value=node.get('consumption_multiplier') or 1
    ) + '\\n'
    text += '\\n' + texts.t('ADMIN_RW_NODE_META', '<b>Метаданные:</b>') + '\\n'
    text += texts.t('ADMIN_RW_NODE_CREATED', '- Создана: {time}').format(time=created_at) + '\\n'
    text += texts.t('ADMIN_RW_NODE_UPDATED', '- Обновлена: {time}').format(time=updated_at)
    return text
'''

REPLACEMENTS: list[tuple[str, str]] = [
    # inject helper if missing
]

def main() -> None:
    src = PATH.read_text(encoding='utf-8')
    if '_build_node_detail_text' not in src:
        marker = 'def _rw_node_action_label'
        idx = src.find(marker)
        if idx == -1:
            raise SystemExit('marker not found')
        end = src.find('\n\n', idx)
        src = src[:end] + HELPER + src[end:]

    # show_node_details
    src = re.sub(
        r"async def show_node_details\(callback: types\.CallbackQuery, db_user: User, db: AsyncSession\):\n"
        r"    node_uuid = callback\.data\.split\('_'\)\[-1\]\n\n"
        r"    remnawave_service = RemnaWaveService\(\)\n"
        r"    node = await remnawave_service\.get_node_details\(node_uuid\)\n\n"
        r"    if not node:\n"
        r"        await callback\.answer\('❌ Нода не найдена', show_alert=True\)\n"
        r"        return\n\n"
        r"    status_emoji.*?"
        r"    await callback\.message\.edit_text\(text, reply_markup=get_node_management_keyboard\(node_uuid, db_user\.language\)\)\n"
        r"    await callback\.answer\(\)",
        """async def show_node_details(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    node_uuid = callback.data.split('_')[-1]

    remnawave_service = RemnaWaveService()
    node = await remnawave_service.get_node_details(node_uuid)

    if not node:
        await callback.answer(texts.t('ADMIN_RW_NODE_NOT_FOUND', '❌ Нода не найдена'), show_alert=True)
        return

    text = _build_node_detail_text(texts, node, language=db_user.language)

    await callback.message.edit_text(text, reply_markup=get_node_management_keyboard(node_uuid, db_user.language))
    await callback.answer()""",
        src,
        count=1,
        flags=re.DOTALL,
    )

    # manage_node
    src = src.replace(
        """async def manage_node(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    action, node_uuid = callback.data.split('_')[1], callback.data.split('_')[-1]

    remnawave_service = RemnaWaveService()
    success = await remnawave_service.manage_node(node_uuid, action)

    if success:
        action_text = {'enable': 'включена', 'disable': 'отключена', 'restart': 'перезагружена'}
        await callback.answer(f'✅ Нода {action_text.get(action, "обработана")}')
    else:
        await callback.answer('❌ Ошибка выполнения действия', show_alert=True)""",
        """async def manage_node(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    action, node_uuid = callback.data.split('_')[1], callback.data.split('_')[-1]

    remnawave_service = RemnaWaveService()
    success = await remnawave_service.manage_node(node_uuid, action)

    if success:
        await callback.answer(
            texts.t('ADMIN_RW_NODE_ACTION_OK', '✅ Нода {action}').format(action=_rw_node_action_label(texts, action))
        )
    else:
        await callback.answer(texts.t('ADMIN_RW_NODE_ACTION_FAIL', '❌ Ошибка выполнения действия'), show_alert=True)""",
    )

    PATH.write_text(src, encoding='utf-8')
    print('patched remnawave.py (partial)')


if __name__ == '__main__':
    main()
