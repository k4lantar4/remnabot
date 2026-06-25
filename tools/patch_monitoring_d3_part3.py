#!/usr/bin/env python3
"""Patch monitoring.py part 3 — stats, nalogo, traffic settings, keyboards."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app/handlers/admin/monitoring.py"
src = path.read_text(encoding="utf-8")

# test notifications
old = """async def test_notifications_callback(callback: CallbackQuery):
    try:
        test_message = f\"\"\"
🧪 <b>Тестовое уведомление системы мониторинга</b>

Это тестовое сообщение для проверки работы системы уведомлений.

📊 <b>Статус системы:</b>
• Мониторинг: {'🟢 Работает' if monitoring_service.is_running else '🔴 Остановлен'}
• Уведомления: {'🟢 Включены' if settings.ENABLE_NOTIFICATIONS else '🔴 Отключены'}
• Время теста: {datetime.now(UTC).strftime('%H:%M:%S %d.%m.%Y')}

✅ Если вы получили это сообщение, система уведомлений работает корректно!
\"\"\"

        await callback.bot.send_message(callback.from_user.id, test_message, parse_mode='HTML')

        await callback.answer('✅ Тестовое уведомление отправлено!')"""
new = """async def test_notifications_callback(callback: CallbackQuery):
    try:
        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
        texts = get_texts(language)
        running = (
            texts.t('ADMIN_MON_RUNNING', '🟢 Работает')
            if monitoring_service.is_running
            else texts.t('ADMIN_MON_STOPPED', '🔴 Остановлен')
        )
        notify = (
            texts.t('ADMIN_MON_GLOBAL_ON', '🟢 Включены')
            if settings.ENABLE_NOTIFICATIONS
            else texts.t('ADMIN_MON_GLOBAL_OFF', '🔴 Отключены')
        )
        test_message = texts.t(
            'ADMIN_MON_TEST_MSG',
            '🧪 <b>Тестовое уведомление системы мониторинга</b>\\n\\nЭто тестовое сообщение для проверки работы системы уведомлений.\\n\\n📊 <b>Статус системы:</b>\\n• Мониторинг: {running}\\n• Уведомления: {notify}\\n• Время теста: {time}\\n\\n✅ Если вы получили это сообщение, система уведомлений работает корректно!',
        ).format(running=running, notify=notify, time=datetime.now(UTC).strftime('%H:%M:%S %d.%m.%Y'))

        await callback.bot.send_message(callback.from_user.id, test_message, parse_mode='HTML')

        await callback.answer(texts.t('ADMIN_MON_TEST_SENT', '✅ Тестовое уведомление отправлено!'))"""
src = src.replace(old, new)

src = src.replace(
    """        await callback.answer(f'❌ Ошибка отправки: {e!s}', show_alert=True)

    except Exception as e:
        logger.error('Ошибка отправки тестового уведомления', error=e)""",
    """        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
        await callback.answer(get_texts(language).t('ADMIN_MON_TEST_ERR', '❌ Ошибка отправки: {error}').format(error=e), show_alert=True)

    except Exception as e:
        logger.error('Ошибка отправки тестового уведомления', error=e)""",
)

# monitoring statistics - add texts at start
old = """async def monitoring_statistics_callback(callback: CallbackQuery):
    try:
        async with AsyncSessionLocal() as db:"""
new = """async def monitoring_statistics_callback(callback: CallbackQuery):
    try:
        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
        texts = get_texts(language)
        async with AsyncSessionLocal() as db:"""
src = src.replace(old, new)

# Replace stats text block
old_stats = """            text = f\"\"\"
📊 <b>Статистика мониторинга</b>

📱 <b>Подписки:</b>
• Всего: {sub_stats['total_subscriptions']}
• Активных: {sub_stats['active_subscriptions']}
• Тестовых: {sub_stats['trial_subscriptions']}
• Платных: {sub_stats['paid_subscriptions']}

📈 <b>За сегодня:</b>
• Успешных операций: {mon_status['stats_24h']['successful']}
• Ошибок: {mon_status['stats_24h']['failed']}
• Успешность: {mon_status['stats_24h']['success_rate']}%

📊 <b>За неделю:</b>
• Всего событий: {len(week_logs)}
• Успешных: {week_success}
• Ошибок: {week_errors}
• Успешность: {round(week_success / len(week_logs) * 100, 1) if week_logs else 0}%

🔧 <b>Система:</b>
• Интервал: {settings.MONITORING_INTERVAL} мин
• Уведомления: {'🟢 Вкл' if getattr(settings, 'ENABLE_NOTIFICATIONS', True) else '🔴 Выкл'}
• Автооплата: {', '.join(map(str, settings.get_autopay_warning_days()))} дней
\"\"\""""
new_stats = """            notify_toggle = (
                texts.t('ADMIN_MON_TOGGLE_ON', '🟢 Вкл')
                if getattr(settings, 'ENABLE_NOTIFICATIONS', True)
                else texts.t('ADMIN_MON_TOGGLE_OFF', '🔴 Выкл')
            )
            week_rate = round(week_success / len(week_logs) * 100, 1) if week_logs else 0
            text = texts.t(
                'ADMIN_MON_STATS_TITLE',
                '📊 <b>Статистика мониторинга</b>\\n\\n📱 <b>Подписки:</b>\\n• Всего: {total}\\n• Активных: {active}\\n• Тестовых: {trial}\\n• Платных: {paid}\\n\\n📈 <b>За сегодня:</b>\\n• Успешных операций: {today_ok}\\n• Ошибок: {today_err}\\n• Успешность: {today_rate}%\\n\\n📊 <b>За неделю:</b>\\n• Всего событий: {week_total}\\n• Успешных: {week_ok}\\n• Ошибок: {week_err}\\n• Успешность: {week_rate}%\\n\\n🔧 <b>Система:</b>\\n• Интервал: {interval} мин\\n• Уведомления: {notify_toggle}\\n• Автооплата: {autopay_days} дней',
            ).format(
                total=sub_stats['total_subscriptions'],
                active=sub_stats['active_subscriptions'],
                trial=sub_stats['trial_subscriptions'],
                paid=sub_stats['paid_subscriptions'],
                today_ok=mon_status['stats_24h']['successful'],
                today_err=mon_status['stats_24h']['failed'],
                today_rate=mon_status['stats_24h']['success_rate'],
                week_total=len(week_logs),
                week_ok=week_success,
                week_err=week_errors,
                week_rate=week_rate,
                interval=settings.MONITORING_INTERVAL,
                notify_toggle=notify_toggle,
                autopay_days=', '.join(map(str, settings.get_autopay_warning_days())),
            )"""
src = src.replace(old_stats, new_stats)

# nalogo section in stats
old_nalogo = """                nalogo_section = f\"\"\"
🧾 <b>Чеки NaloGO:</b>
• Сервис: {'🟢 Работает' if running else '🔴 Остановлен'}
• В очереди: {queue_len} чек(ов)\"\"\"
                if queue_len > 0:
                    nalogo_section += f'\\n• На сумму: {total_amount:,.2f} ₽'
                if pending_count > 0:
                    nalogo_section += f'\\n⚠️ <b>Требуют проверки: {pending_count} ({pending_amount:,.2f} ₽)</b>'
                text += nalogo_section"""
new_nalogo = """                svc = texts.t('ADMIN_MON_RUNNING', '🟢 Работает') if running else texts.t('ADMIN_MON_STOPPED', '🔴 Остановлен')
                nalogo_section = texts.t(
                    'ADMIN_MON_NALOGO_SECTION',
                    '\\n🧾 <b>Чеки NaloGO:</b>\\n• Сервис: {running}\\n• В очереди: {queue} чек(ов)',
                ).format(running=svc, queue=queue_len)
                if queue_len > 0:
                    nalogo_section += texts.t('ADMIN_MON_NALOGO_AMOUNT', '\\n• На сумму: {amount:,.2f} ₽').format(amount=total_amount)
                if pending_count > 0:
                    nalogo_section += texts.t(
                        'ADMIN_MON_NALOGO_PENDING',
                        '\\n⚠️ <b>Требуют проверки: {count} ({amount:,.2f} ₽)</b>',
                    ).format(count=pending_count, amount=pending_amount)
                text += nalogo_section"""
src = src.replace(old_nalogo, new_nalogo)

# nalogo buttons in stats
src = src.replace(
    "text=f'🧾 Отправить ({nalogo_status[\"queue_length\"]})'",
    "text=texts.t('ADMIN_MON_BTN_SEND_NALOGO', '🧾 Отправить ({count})').format(count=nalogo_status['queue_length'])",
)
src = src.replace(
    "text=f'⚠️ Проверить ({pending_count})'",
    "text=texts.t('ADMIN_MON_BTN_CHECK_NALOGO', '⚠️ Проверить ({count})').format(count=pending_count)",
)
src = src.replace(
    "InlineKeyboardButton(text='📊 Сверка чеков', callback_data='admin_mon_receipts_missing')",
    "InlineKeyboardButton(text=texts.t('ADMIN_MON_BTN_RECONCILE', '📊 Сверка чеков'), callback_data='admin_mon_receipts_missing')",
)
src = src.replace(
    "[InlineKeyboardButton(text='⬅️ Назад', callback_data='admin_monitoring')]",
    "[InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'), callback_data='admin_monitoring')]",
)

src = src.replace(
    "        await callback.answer(f'❌ Ошибка получения статистики: {e!s}', show_alert=True)",
    "        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_STATS_ERR', '❌ Ошибка получения статистики: {error}').format(error=e), show_alert=True)",
)

# traffic settings helpers
old = """def _format_traffic_toggle(enabled: bool) -> str:
    return '🟢 Вкл' if enabled else '🔴 Выкл'


def _build_traffic_settings_keyboard() -> InlineKeyboardMarkup:"""
new = """def _format_traffic_toggle(enabled: bool, language: str) -> str:
    texts = get_texts(language)
    return texts.t('ADMIN_MON_TOGGLE_ON', '🟢 Вкл') if enabled else texts.t('ADMIN_MON_TOGGLE_OFF', '🔴 Выкл')


def _build_traffic_settings_keyboard(language: str) -> InlineKeyboardMarkup:
    texts = get_texts(language)"""
src = src.replace(old, new)

src = src.replace(
    "text=f'{_format_traffic_toggle(fast_enabled)} Быстрая проверка'",
    "text=texts.t('ADMIN_MON_BTN_FAST', '{toggle} Быстрая проверка').format(toggle=_format_traffic_toggle(fast_enabled, language))",
)
src = src.replace(
    "text=f'⏱ Интервал: {fast_interval} мин'",
    "text=texts.t('ADMIN_MON_BTN_FAST_INTERVAL', '⏱ Интервал: {minutes} мин').format(minutes=fast_interval)",
)
src = src.replace(
    "text=f'📊 Порог дельты: {fast_threshold} ГБ'",
    "text=texts.t('ADMIN_MON_BTN_FAST_THRESHOLD', '📊 Порог дельты: {gb} GB').format(gb=fast_threshold)",
)
src = src.replace(
    "text=f'{_format_traffic_toggle(daily_enabled)} Суточная проверка'",
    "text=texts.t('ADMIN_MON_BTN_DAILY', '{toggle} Суточная проверка').format(toggle=_format_traffic_toggle(daily_enabled, language))",
)
src = src.replace(
    "text=f'🕐 Время проверки: {daily_time}'",
    "text=texts.t('ADMIN_MON_BTN_DAILY_TIME', '🕐 Время проверки: {time}').format(time=daily_time)",
)
src = src.replace(
    "text=f'📈 Суточный порог: {daily_threshold} ГБ'",
    "text=texts.t('ADMIN_MON_BTN_DAILY_THRESHOLD', '📈 Суточный порог: {gb} GB').format(gb=daily_threshold)",
)
src = src.replace(
    "[InlineKeyboardButton(text=f'⏳ Кулдаун: {cooldown} мин', callback_data='admin_traffic_edit_cooldown')]",
    "[InlineKeyboardButton(text=texts.t('ADMIN_MON_BTN_COOLDOWN', '⏳ Кулдаун: {minutes} мин').format(minutes=cooldown), callback_data='admin_traffic_edit_cooldown')]",
)
src = src.replace(
    "[InlineKeyboardButton(text='⬅️ Назад', callback_data='admin_monitoring')],\n        ]\n    )\n\n\ndef _build_traffic_settings_text()",
    "[InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'), callback_data='admin_monitoring')],\n        ]\n    )\n\n\ndef _build_traffic_settings_text(language: str)",
)

old_traffic_text = """def _build_traffic_settings_text(language: str) -> str:
    \"\"\"Строит текст настроек мониторинга трафика.\"\"\"
    fast_enabled = settings.TRAFFIC_FAST_CHECK_ENABLED
    daily_enabled = settings.TRAFFIC_DAILY_CHECK_ENABLED

    fast_status = _format_traffic_toggle(fast_enabled)
    daily_status = _format_traffic_toggle(daily_enabled)

    text = (
        '⚙️ <b>Настройки мониторинга трафика</b>\\n\\n'
        f'<b>Быстрая проверка:</b> {fast_status}\\n'
        f'• Интервал: {settings.TRAFFIC_FAST_CHECK_INTERVAL_MINUTES} мин\\n'
        f'• Порог дельты: {settings.TRAFFIC_FAST_CHECK_THRESHOLD_GB} ГБ\\n\\n'
        f'<b>Суточная проверка:</b> {daily_status}\\n'
        f'• Время: {settings.TRAFFIC_DAILY_CHECK_TIME} UTC\\n'
        f'• Порог: {settings.TRAFFIC_DAILY_THRESHOLD_GB} ГБ\\n\\n'
        f'<b>Общие:</b>\\n'
        f'• Кулдаун уведомлений: {settings.TRAFFIC_NOTIFICATION_COOLDOWN_MINUTES} мин\\n'
    )

    # Информация о фильтрах
    monitored_nodes = settings.get_traffic_monitored_nodes()
    ignored_nodes = settings.get_traffic_ignored_nodes()
    excluded_uuids = settings.get_traffic_excluded_user_uuids()

    if monitored_nodes:
        text += f'• Мониторим только: {len(monitored_nodes)} нод(ы)\\n'
    if ignored_nodes:
        text += f'• Игнорируем: {len(ignored_nodes)} нод(ы)\\n'
    if excluded_uuids:
        text += f'• Исключено юзеров: {len(excluded_uuids)}\\n'

    return text"""
new_traffic_text = """def _build_traffic_settings_text(language: str) -> str:
    \"\"\"Строит текст настроек мониторинга трафика.\"\"\"
    texts = get_texts(language)
    fast_enabled = settings.TRAFFIC_FAST_CHECK_ENABLED
    daily_enabled = settings.TRAFFIC_DAILY_CHECK_ENABLED

    fast_status = _format_traffic_toggle(fast_enabled, language)
    daily_status = _format_traffic_toggle(daily_enabled, language)

    text = texts.t(
        'ADMIN_MON_TRAFFIC_SETTINGS',
        '⚙️ <b>Настройки мониторинга трафика</b>\\n\\n<b>Быстрая проверка:</b> {fast}\\n• Интервал: {fast_interval} мин\\n• Порог дельты: {fast_threshold} GB\\n\\n<b>Суточная проверка:</b> {daily}\\n• Время: {daily_time} UTC\\n• Порог: {daily_threshold} GB\\n\\n<b>Общие:</b>\\n• Кулдаун уведомлений: {cooldown} мин\\n',
    ).format(
        fast=fast_status,
        fast_interval=settings.TRAFFIC_FAST_CHECK_INTERVAL_MINUTES,
        fast_threshold=settings.TRAFFIC_FAST_CHECK_THRESHOLD_GB,
        daily=daily_status,
        daily_time=settings.TRAFFIC_DAILY_CHECK_TIME,
        daily_threshold=settings.TRAFFIC_DAILY_THRESHOLD_GB,
        cooldown=settings.TRAFFIC_NOTIFICATION_COOLDOWN_MINUTES,
    )

    monitored_nodes = settings.get_traffic_monitored_nodes()
    ignored_nodes = settings.get_traffic_ignored_nodes()
    excluded_uuids = settings.get_traffic_excluded_user_uuids()

    if monitored_nodes:
        text += texts.t('ADMIN_MON_TRAFFIC_MONITORED', '• Мониторим только: {count} нод(ы)\\n').format(count=len(monitored_nodes))
    if ignored_nodes:
        text += texts.t('ADMIN_MON_TRAFFIC_IGNORED', '• Игнорируем: {count} нод(ы)\\n').format(count=len(ignored_nodes))
    if excluded_uuids:
        text += texts.t('ADMIN_MON_TRAFFIC_EXCLUDED', '• Исключено юзеров: {count}\\n').format(count=len(excluded_uuids))

    return text"""
src = src.replace(old_traffic_text, new_traffic_text)

# update traffic settings call sites
src = src.replace("text = _build_traffic_settings_text()\n        keyboard = _build_traffic_settings_keyboard()", "text = _build_traffic_settings_text(language)\n        keyboard = _build_traffic_settings_keyboard(language)")
src = src.replace("async def admin_traffic_settings(callback: CallbackQuery):\n    \"\"\"Показывает настройки мониторинга трафика.\"\"\"\n    try:\n        text = _build_traffic_settings_text(language)", "async def admin_traffic_settings(callback: CallbackQuery):\n    \"\"\"Показывает настройки мониторинга трафика.\"\"\"\n    try:\n        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        text = _build_traffic_settings_text(language)")

# fix if double language
src = src.replace(
    "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE",
    "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE",
)

# traffic settings callbacks
for old_a, new_a in [
    ("await callback.answer('❌ Ошибка загрузки настроек', show_alert=True)", "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_TRAFFIC_LOAD_ERR', '❌ Ошибка загрузки настроек'), show_alert=True)"),
    ("await callback.answer('✅ Включено' if new_value else '⏸️ Отключено')", "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        texts = get_texts(language)\n        await callback.answer(texts.t('ADMIN_MON_TOGGLED_ON', '✅ Включено') if new_value else texts.t('ADMIN_MON_TOGGLED_OFF', '⏸️ Отключено'))"),
    ("await callback.answer('❌ Ошибка', show_alert=True)", "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_TRAFFIC_TOGGLE_ERR', '❌ Ошибка'), show_alert=True)"),
]:
    src = src.replace(old_a, new_a)

# traffic edit prompts
src = src.replace(
    "await callback.message.answer('⏱ Введите интервал быстрой проверки в минутах (минимум 1):')",
    "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n    await callback.message.answer(get_texts(language).t('ADMIN_MON_PROMPT_FAST_INTERVAL', '⏱ Введите интервал быстрой проверки в минутах (минимум 1):'))",
)
src = src.replace(
    "await callback.message.answer('📊 Введите порог дельты трафика в ГБ (например: 5.0):')",
    "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n    await callback.message.answer(get_texts(language).t('ADMIN_MON_PROMPT_FAST_THRESHOLD', '📊 Введите порог дельты трафика в ГБ (например: 5.0):'))",
)
src = src.replace(
    """    await callback.message.answer(
        '🕐 Введите время суточной проверки в формате HH:MM (UTC):\\nНапример: 00:00, 03:00, 12:30'
    )""",
    """    language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    await callback.message.answer(
        get_texts(language).t(
            'ADMIN_MON_PROMPT_DAILY_TIME',
            '🕐 Введите время суточной проверки в формате HH:MM (UTC):\\nНапример: 00:00, 03:00, 12:30',
        )
    )""",
)
src = src.replace(
    "await callback.message.answer('📈 Введите суточный порог трафика в ГБ (например: 50.0):')",
    "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n    await callback.message.answer(get_texts(language).t('ADMIN_MON_PROMPT_DAILY_THRESHOLD', '📈 Введите суточный порог трафика в ГБ (например: 50.0):'))",
)
src = src.replace(
    "await callback.message.answer('⏳ Введите кулдаун уведомлений в минутах (минимум 1):')",
    "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n    await callback.message.answer(get_texts(language).t('ADMIN_MON_PROMPT_COOLDOWN', '⏳ Введите кулдаун уведомлений в минутах (минимум 1):'))",
)

# process_traffic_setting_input
src = src.replace(
    "        await message.answer('ℹ️ Контекст утерян, попробуйте снова из меню настроек.')",
    "        language = message.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await message.answer(get_texts(language).t('ADMIN_MON_CONTEXT_LOST', 'ℹ️ Контекст утерян, попробуйте снова из меню настроек.'))",
)
src = src.replace(
    "[InlineKeyboardButton(text='⬅️ К настройкам трафика', callback_data='admin_mon_traffic_settings')]",
    "[InlineKeyboardButton(text=get_texts(message.from_user.language_code or settings.DEFAULT_LANGUAGE).t('ADMIN_MON_BACK_TRAFFIC', '⬅️ К настройкам трафика'), callback_data='admin_mon_traffic_settings')]",
)
src = src.replace(
    "        await message.answer('✅ Настройка сохранена!', reply_markup=back_keyboard)",
    "        language = message.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await message.answer(get_texts(language).t('ADMIN_MON_VALUE_SAVED', '✅ Настройка сохранена!'), reply_markup=back_keyboard)",
)
src = src.replace(
    "                text = _build_traffic_settings_text()\n                keyboard = _build_traffic_settings_keyboard()",
    "                lang = message.from_user.language_code or settings.DEFAULT_LANGUAGE\n                text = _build_traffic_settings_text(lang)\n                keyboard = _build_traffic_settings_keyboard(lang)",
)
src = src.replace(
    "        await message.answer(f'❌ Ошибка сохранения: {e!s}')",
    "        language = message.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await message.answer(get_texts(language).t('ADMIN_MON_SAVE_ERR', '❌ Ошибка сохранения: {error}').format(error=e))",
)

path.write_text(src, encoding="utf-8")
print("patch part 3 done")
