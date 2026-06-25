#!/usr/bin/env python3
"""Patch monitoring.py for Phase 10 Slice D3."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "app/handlers/admin/monitoring.py"
src = path.read_text(encoding="utf-8")

# --- helpers ---
old = """def _format_toggle(enabled: bool) -> str:
    return '🟢 Вкл' if enabled else '🔴 Выкл'


def _build_notification_settings_view(language: str):
    get_texts(language)"""
new = """def _format_toggle(enabled: bool, language: str) -> str:
    texts = get_texts(language)
    return texts.t('ADMIN_MON_TOGGLE_ON', '🟢 Вкл') if enabled else texts.t('ADMIN_MON_TOGGLE_OFF', '🔴 Выкл')


def _build_notification_settings_view(language: str):
    texts = get_texts(language)"""
src = src.replace(old, new)

old = """    trial_channel_status = _format_toggle(config.get('trial_channel_unsubscribed', {}).get('enabled', True))
    expired_1d_status = _format_toggle(config['expired_1d'].get('enabled', True))
    second_wave_status = _format_toggle(config['expired_second_wave'].get('enabled', True))
    third_wave_status = _format_toggle(config['expired_third_wave'].get('enabled', True))

    summary_text = (
        '🔔 <b>Уведомления пользователям</b>\\n\\n'
        f'• Отписка от канала: {trial_channel_status}\\n'
        f'• 1 день после истечения: {expired_1d_status}\\n'
        f'• 2-3 дня (скидка {second_percent}% / {second_hours} ч): {second_wave_status}\\n'
        f'• {third_days} дней (скидка {third_percent}% / {third_hours} ч): {third_wave_status}'
    )"""
new = """    trial_channel_status = _format_toggle(config.get('trial_channel_unsubscribed', {}).get('enabled', True), language)
    expired_1d_status = _format_toggle(config['expired_1d'].get('enabled', True), language)
    second_wave_status = _format_toggle(config['expired_second_wave'].get('enabled', True), language)
    third_wave_status = _format_toggle(config['expired_third_wave'].get('enabled', True), language)

    summary_text = texts.t(
        'ADMIN_MON_NOTIFY_TITLE',
        '🔔 <b>Уведомления пользователям</b>\\n\\n• Отписка от канала: {trial}\\n• 1 день после истечения: {exp1}\\n• 2-3 дня (скидка {p2}% / {h2} ч): {wave2}\\n• {d3} дней (скидка {p3}% / {h3} ч): {wave3}',
    ).format(
        trial=trial_channel_status,
        exp1=expired_1d_status,
        p2=second_percent,
        h2=second_hours,
        wave2=second_wave_status,
        d3=third_days,
        p3=third_percent,
        h3=third_hours,
        wave3=third_wave_status,
    )"""
src = src.replace(old, new)

# notification settings keyboard buttons
btn_repls = [
    (
        "text=f'{trial_channel_status} • Отписка от канала'",
        "text=texts.t('ADMIN_MON_BTN_TRIAL', '{status} • Отписка от канала').format(status=trial_channel_status)",
    ),
    (
        "text='🧪 Тест: отписка от канала'",
        "text=texts.t('ADMIN_MON_BTN_TEST_TRIAL', '🧪 Тест: отписка от канала')",
    ),
    (
        "text=f'{expired_1d_status} • 1 день после истечения'",
        "text=texts.t('ADMIN_MON_BTN_EXP1', '{status} • 1 день после истечения').format(status=expired_1d_status)",
    ),
    (
        "text='🧪 Тест: 1 день после истечения'",
        "text=texts.t('ADMIN_MON_BTN_TEST_EXP1', '🧪 Тест: 1 день после истечения')",
    ),
    (
        "text=f'{second_wave_status} • 2-3 дня со скидкой'",
        "text=texts.t('ADMIN_MON_BTN_WAVE2', '{status} • 2-3 дня со скидкой').format(status=second_wave_status)",
    ),
    (
        "text='🧪 Тест: скидка 2-3 день'",
        "text=texts.t('ADMIN_MON_BTN_TEST_WAVE2', '🧪 Тест: скидка 2-3 день')",
    ),
    (
        "text=f'✏️ Скидка 2-3 дня: {second_percent}%'",
        "text=texts.t('ADMIN_MON_BTN_EDIT_P2', '✏️ Скидка 2-3 дня: {percent}%').format(percent=second_percent)",
    ),
    (
        "text=f'⏱️ Срок скидки 2-3 дня: {second_hours} ч'",
        "text=texts.t('ADMIN_MON_BTN_EDIT_H2', '⏱️ Срок скидки 2-3 дня: {hours} ч').format(hours=second_hours)",
    ),
    (
        "text=f'{third_wave_status} • {third_days} дней со скидкой'",
        "text=texts.t('ADMIN_MON_BTN_WAVE3', '{status} • {days} дней со скидкой').format(status=third_wave_status, days=third_days)",
    ),
    (
        "text='🧪 Тест: скидка спустя дни'",
        "text=texts.t('ADMIN_MON_BTN_TEST_WAVE3', '🧪 Тест: скидка спустя дни')",
    ),
    (
        "text=f'✏️ Скидка {third_days} дней: {third_percent}%'",
        "text=texts.t('ADMIN_MON_BTN_EDIT_P3', '✏️ Скидка {days} дней: {percent}%').format(days=third_days, percent=third_percent)",
    ),
    (
        "text=f'⏱️ Срок скидки {third_days} дней: {third_hours} ч'",
        "text=texts.t('ADMIN_MON_BTN_EDIT_H3', '⏱️ Срок скидки {days} дней: {hours} ч').format(days=third_days, hours=third_hours)",
    ),
    (
        "text=f'📆 Порог уведомления: {third_days} дн.'",
        "text=texts.t('ADMIN_MON_BTN_THRESHOLD', '📆 Порог уведомления: {days} дн.').format(days=third_days)",
    ),
    (
        "text='🧪 Отправить все тесты'",
        "text=texts.t('ADMIN_MON_BTN_TEST_ALL', '🧪 Отправить все тесты')",
    ),
    (
        "[InlineKeyboardButton(text='⬅️ Назад', callback_data='admin_mon_settings')]",
        "[InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'), callback_data='admin_mon_settings')]",
    ),
]
for old_b, new_b in btn_repls:
    src = src.replace(old_b, new_b)

# preview header/footer/discount btn
src = src.replace(
    "    header = '🧪 <b>Тестовое уведомление мониторинга</b>\\n\\n'",
    "    header = texts.t('ADMIN_MON_PREVIEW_HEADER', '🧪 <b>Тестовое уведомление мониторинга</b>\\n\\n')",
)
src = src.replace(
    "                        text='🎁 Получить скидку',",
    "                        text=texts.t('ADMIN_MON_PREVIEW_DISCOUNT_BTN', '🎁 Получить скидку'),",
)
src = src.replace(
    "    footer = '\\n\\n<i>Сообщение отправлено только вам для проверки оформления.</i>'",
    "    footer = texts.t('ADMIN_MON_PREVIEW_FOOTER', '\\n\\n<i>Сообщение отправлено только вам для проверки оформления.</i>')",
)

# admin_monitoring_menu
old = """async def admin_monitoring_menu(callback: CallbackQuery):
    try:
        async with AsyncSessionLocal() as db:
            status = await monitoring_service.get_monitoring_status(db)

            running_status = '🟢 Работает' if status['is_running'] else '🔴 Остановлен'
            last_update = status['last_update'].strftime('%H:%M:%S') if status['last_update'] else 'Никогда'

            text = f\"\"\"
🔍 <b>Система мониторинга</b>

📊 <b>Статус:</b> {running_status}
🕐 <b>Последнее обновление:</b> {last_update}
⚙️ <b>Интервал проверки:</b> {settings.MONITORING_INTERVAL} мин

📈 <b>Статистика за 24 часа:</b>
• Всего событий: {status['stats_24h']['total_events']}
• Успешных: {status['stats_24h']['successful']}
• Ошибок: {status['stats_24h']['failed']}
• Успешность: {status['stats_24h']['success_rate']}%

🔧 Выберите действие:
\"\"\"

            language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE"""
new = """async def admin_monitoring_menu(callback: CallbackQuery):
    try:
        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
        texts = get_texts(language)
        async with AsyncSessionLocal() as db:
            status = await monitoring_service.get_monitoring_status(db)

            running_status = (
                texts.t('ADMIN_MON_RUNNING', '🟢 Работает')
                if status['is_running']
                else texts.t('ADMIN_MON_STOPPED', '🔴 Остановлен')
            )
            last_update = (
                status['last_update'].strftime('%H:%M:%S')
                if status['last_update']
                else texts.t('ADMIN_MON_NEVER', 'Никогда')
            )

            text = texts.t(
                'ADMIN_MON_MENU',
                '🔍 <b>Система мониторинга</b>\\n\\n📊 <b>Статус:</b> {running}\\n🕐 <b>Последнее обновление:</b> {last}\\n⚙️ <b>Интервал проверки:</b> {interval} мин\\n\\n📈 <b>Статистика за 24 часа:</b>\\n• Всего событий: {events}\\n• Успешных: {success}\\n• Ошибок: {errors}\\n• Успешность: {rate}%\\n\\n🔧 Выберите действие:',
            ).format(
                running=running_status,
                last=last_update,
                interval=settings.MONITORING_INTERVAL,
                events=status['stats_24h']['total_events'],
                success=status['stats_24h']['successful'],
                errors=status['stats_24h']['failed'],
                rate=status['stats_24h']['success_rate'],
            )"""
src = src.replace(old, new)

src = src.replace(
    "        await callback.answer('❌ Ошибка получения данных', show_alert=True)",
    "        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_DATA_ERR', '❌ Ошибка получения данных'), show_alert=True)",
    1,
)

# admin_monitoring_settings
old = """async def admin_monitoring_settings(callback: CallbackQuery):
    try:
        global_status = (
            '🟢 Включены' if NotificationSettingsService.are_notifications_globally_enabled() else '🔴 Отключены'
        )
        second_percent = NotificationSettingsService.get_second_wave_discount_percent()
        third_percent = NotificationSettingsService.get_third_wave_discount_percent()
        third_days = NotificationSettingsService.get_third_wave_trigger_days()

        text = (
            '⚙️ <b>Настройки мониторинга</b>\\n\\n'
            f'🔔 <b>Уведомления пользователям:</b> {global_status}\\n'
            f'• Скидка 2-3 дня: {second_percent}%\\n'
            f'• Скидка после {third_days} дней: {third_percent}%\\n\\n'
            'Выберите раздел для настройки.'
        )

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='🔔 Уведомления пользователям', callback_data='admin_mon_notify_settings')],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='admin_submenu_settings')],
            ]
        )"""
new = """async def admin_monitoring_settings(callback: CallbackQuery):
    try:
        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
        texts = get_texts(language)
        global_status = (
            texts.t('ADMIN_MON_GLOBAL_ON', '🟢 Включены')
            if NotificationSettingsService.are_notifications_globally_enabled()
            else texts.t('ADMIN_MON_GLOBAL_OFF', '🔴 Отключены')
        )
        second_percent = NotificationSettingsService.get_second_wave_discount_percent()
        third_percent = NotificationSettingsService.get_third_wave_discount_percent()
        third_days = NotificationSettingsService.get_third_wave_trigger_days()

        text = texts.t(
            'ADMIN_MON_SETTINGS',
            '⚙️ <b>Настройки мониторинга</b>\\n\\n🔔 <b>Уведомления пользователям:</b> {global}\\n• Скидка 2-3 дня: {p2}%\\n• Скидка после {d3} дней: {p3}%\\n\\nВыберите раздел для настройки.',
        ).format(global=global_status, p2=second_percent, d3=third_days, p3=third_percent)

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=texts.t('ADMIN_MON_BTN_NOTIFY', '🔔 Уведомления пользователям'), callback_data='admin_mon_notify_settings')],
                [InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'), callback_data='admin_submenu_settings')],
            ]
        )"""
src = src.replace(old, new)

src = src.replace(
    "        await callback.answer('❌ Не удалось открыть настройки', show_alert=True)",
    "        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_SETTINGS_ERR', '❌ Не удалось открыть настройки'), show_alert=True)",
)
src = src.replace(
    "        await callback.answer('❌ Не удалось загрузить настройки', show_alert=True)",
    "        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_NOTIFY_ERR', '❌ Не удалось загрузить настройки'), show_alert=True)",
)

# toggle/preview callbacks - helper pattern
def _mon_answer_lang(old_on: str, key_on: str, key_off: str) -> None:
    pass


for old_a, new_a in [
    ("await callback.answer('✅ Включено' if not enabled else '⏸️ Отключено')", """language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
    texts = get_texts(language)
    await callback.answer(texts.t('ADMIN_MON_TOGGLED_ON', '✅ Включено') if not enabled else texts.t('ADMIN_MON_TOGGLED_OFF', '⏸️ Отключено'))"""),
    ("await callback.answer('✅ Пример отправлен')", """language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
        await callback.answer(get_texts(language).t('ADMIN_MON_PREVIEW_SENT', '✅ Пример отправлен'))"""),
    ("await callback.answer('❌ Не удалось отправить тест', show_alert=True)", """language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
        await callback.answer(get_texts(language).t('ADMIN_MON_PREVIEW_FAIL', '❌ Не удалось отправить тест'), show_alert=True)"""),
    ("await callback.answer('✅ Все тестовые уведомления отправлены')", """language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
        await callback.answer(get_texts(language).t('ADMIN_MON_ALL_SENT', '✅ Все тестовые уведомления отправлены'))"""),
    ("await callback.answer('❌ Не удалось отправить тесты', show_alert=True)", """language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
        await callback.answer(get_texts(language).t('ADMIN_MON_ALL_FAIL', '❌ Не удалось отправить тесты'), show_alert=True)"""),
]:
    src = src.replace(old_a, new_a)

# edit prompts - use texts.t in _start_notification_value_edit
src = src.replace(
    "    await callback.message.answer(texts.get(prompt_key, default_prompt))",
    "    await callback.message.answer(texts.t(prompt_key, default_prompt))",
)

src = src.replace(
    "'NOTIFY_PROMPT_SECOND_PERCENT',\n        'Введите новый процент скидки для уведомления через 2-3 дня (0-100):',",
    "'ADMIN_MON_PROMPT_SECOND_PERCENT',\n        'Введите новый процент скидки для уведомления через 2-3 дня (0-100):',",
)
src = src.replace(
    "'NOTIFY_PROMPT_SECOND_HOURS',\n        'Введите количество часов действия скидки (1-168):',",
    "'ADMIN_MON_PROMPT_SECOND_HOURS',\n        'Введите количество часов действия скидки (1-168):',",
)
src = src.replace(
    "'NOTIFY_PROMPT_THIRD_PERCENT',\n        'Введите новый процент скидки для позднего предложения (0-100):',",
    "'ADMIN_MON_PROMPT_THIRD_PERCENT',\n        'Введите новый процент скидки для позднего предложения (0-100):',",
)
src = src.replace(
    "'NOTIFY_PROMPT_THIRD_HOURS',\n        'Введите количество часов действия скидки (1-168):',",
    "'ADMIN_MON_PROMPT_THIRD_HOURS',\n        'Введите количество часов действия скидки (1-168):',",
)
src = src.replace(
    "'NOTIFY_PROMPT_THIRD_DAYS',\n        'Через сколько дней после истечения отправлять предложение? (минимум 2):',",
    "'ADMIN_MON_PROMPT_THIRD_DAYS',\n        'Через сколько дней после истечения отправлять предложение? (минимум 2):',",
)

# start/stop monitoring
mon_cb = [
    ("await callback.answer('ℹ️ Мониторинг уже запущен')", "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n            await callback.answer(get_texts(language).t('ADMIN_MON_ALREADY_RUNNING', 'ℹ️ Мониторинг уже запущен'))"),
    ("await callback.answer('✅ Мониторинг запущен!')", "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_STARTED', '✅ Мониторинг запущен!'))"),
    ("await callback.answer(f'❌ Ошибка запуска: {e!s}', show_alert=True)", "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_START_ERR', '❌ Ошибка запуска: {error}').format(error=e), show_alert=True)"),
    ("await callback.answer('ℹ️ Мониторинг уже остановлен')", "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n            await callback.answer(get_texts(language).t('ADMIN_MON_ALREADY_STOPPED', 'ℹ️ Мониторинг уже остановлен'))"),
    ("await callback.answer('⏹️ Мониторинг остановлен!')", "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_STOPPED_MSG', '⏹️ Мониторинг остановлен!'))"),
    ("await callback.answer(f'❌ Ошибка остановки: {e!s}', show_alert=True)", "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_STOP_ERR', '❌ Ошибка остановки: {error}').format(error=e), show_alert=True)"),
    ("await callback.answer('⏳ Выполняем проверку подписок...')", "language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_FORCE_CHECK', '⏳ Выполняем проверку подписок...'))"),
]
for o, n in mon_cb:
    src = src.replace(o, n)

# force check result
old = """            text = f\"\"\"
✅ <b>Принудительная проверка завершена</b>

📊 <b>Результаты проверки:</b>
• Истекших подписок: {results['expired']}
• Истекающих подписок: {results['expiring']}
• Готовых к автооплате: {results['autopay_ready']}

🕐 <b>Время проверки:</b> {datetime.now(UTC).strftime('%H:%M:%S')}

Нажмите "Назад" для возврата в меню мониторинга.
\"\"\"

            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text='⬅️ Назад', callback_data='admin_monitoring')]]
            )"""
new = """            language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
            texts = get_texts(language)
            text = texts.t(
                'ADMIN_MON_FORCE_DONE',
                '✅ <b>Принудительная проверка завершена</b>\\n\\n📊 <b>Результаты проверки:</b>\\n• Истекших подписок: {expired}\\n• Истекающих подписок: {expiring}\\n• Готовых к автооплате: {autopay}\\n\\n🕐 <b>Время проверки:</b> {time}\\n\\nНажмите \"Назад\" для возврата в меню мониторинга.',
            ).format(
                expired=results['expired'],
                expiring=results['expiring'],
                autopay=results['autopay_ready'],
                time=datetime.now(UTC).strftime('%H:%M:%S'),
            )

            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'), callback_data='admin_monitoring')]]
            )"""
src = src.replace(old, new)
src = src.replace(
    "        await callback.answer(f'❌ Ошибка проверки: {e!s}', show_alert=True)",
    "        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_FORCE_ERR', '❌ Ошибка проверки: {error}').format(error=e), show_alert=True)",
    1,
)

path.write_text(src, encoding="utf-8")
print("patch part 1 done")

# part 2 - re-read
src = path.read_text(encoding="utf-8")

# traffic check
old = """            await callback.answer(
                '⚠️ Мониторинг трафика отключен в настройках\\nВключите TRAFFIC_FAST_CHECK_ENABLED=true в .env',
                show_alert=True,
            )"""
new = """            language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
            await callback.answer(
                get_texts(language).t(
                    'ADMIN_MON_TRAFFIC_DISABLED',
                    '⚠️ Мониторинг трафика отключен в настройках\\nВключите TRAFFIC_FAST_CHECK_ENABLED=true в .env',
                ),
                show_alert=True,
            )"""
src = src.replace(old, new)

src = src.replace(
    "        await callback.answer('⏳ Запускаем проверку трафика (дельта)...')",
    "        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        texts = get_texts(language)\n        await callback.answer(texts.t('ADMIN_MON_TRAFFIC_CHECK', '⏳ Запускаем проверку трафика (дельта)...'))",
)

# traffic check result block - replace the big f-string section
old_traffic = """        text = f\"\"\"
📊 <b>Проверка трафика завершена</b>

🔍 <b>Результаты (дельта):</b>
• Превышений за интервал: {len(violations)}
• Порог дельты: {threshold_gb} ГБ
• Возраст snapshot: {snapshot_age:.1f} мин

🕐 <b>Время проверки:</b> {datetime.now(UTC).strftime('%H:%M:%S')}
\"\"\"

        if violations:
            text += '\\n⚠️ <b>Превышения дельты:</b>\\n'
            for v in violations[:10]:
                name = html.escape(v.full_name or '') or v.user_uuid[:8]
                text += f'• {name}: +{v.used_traffic_gb:.1f} ГБ\\n'
            if len(violations) > 10:
                text += f'... и ещё {len(violations) - 10}\\n'
            text += '\\n📨 Уведомления отправлены (с учётом кулдауна)'
        else:
            text += '\\n✅ Превышений не обнаружено'

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text='🔄 Повторить', callback_data='admin_mon_traffic_check')],
                [InlineKeyboardButton(text='⬅️ Назад', callback_data='admin_monitoring')],
            ]
        )"""
new_traffic = """        text = texts.t(
            'ADMIN_MON_TRAFFIC_DONE',
            '📊 <b>Проверка трафика завершена</b>\\n\\n🔍 <b>Результаты (дельта):</b>\\n• Превышений за интервал: {count}\\n• Порог дельты: {threshold} GB\\n• Возраст snapshot: {age:.1f} мин\\n\\n🕐 <b>Время проверки:</b> {time}',
        ).format(
            count=len(violations),
            threshold=threshold_gb,
            age=snapshot_age or 0,
            time=datetime.now(UTC).strftime('%H:%M:%S'),
        )

        if violations:
            text += texts.t('ADMIN_MON_TRAFFIC_VIOLATIONS', '\\n⚠️ <b>Превышения дельты:</b>\\n')
            for v in violations[:10]:
                name = html.escape(v.full_name or '') or v.user_uuid[:8]
                text += texts.t('ADMIN_MON_TRAFFIC_VIOLATION_LINE', '• {name}: +{gb:.1f} GB\\n').format(
                    name=name, gb=v.used_traffic_gb
                )
            if len(violations) > 10:
                text += texts.t('ADMIN_MON_TRAFFIC_MORE', '... и ещё {count}\\n').format(count=len(violations) - 10)
            text += texts.t('ADMIN_MON_TRAFFIC_NOTIFY', '\\n📨 Уведомления отправлены (с учётом кулдауна)')
        else:
            text += texts.t('ADMIN_MON_TRAFFIC_OK', '\\n✅ Превышений не обнаружено')

        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=texts.t('ADMIN_MON_BTN_REPEAT', '🔄 Повторить'), callback_data='admin_mon_traffic_check')],
                [InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'), callback_data='admin_monitoring')],
            ]
        )"""
src = src.replace(old_traffic, new_traffic)

src = src.replace(
    "        await callback.answer(f'❌ Ошибка: {e!s}', show_alert=True)",
    "        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_TRAFFIC_ERR', '❌ Ошибка: {error}').format(error=e), show_alert=True)",
    1,
)

# monitoring logs
old = """async def monitoring_logs_callback(callback: CallbackQuery):
    try:
        page = 1"""
new = """async def monitoring_logs_callback(callback: CallbackQuery):
    try:
        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
        texts = get_texts(language)
        page = 1"""
src = src.replace(old, new)

src = src.replace(
    "                text = '📋 <b>Логи мониторинга пусты</b>\\n\\nСистема еще не выполнила проверки.'\n                keyboard = get_monitoring_logs_back_keyboard()",
    "                text = texts.t('ADMIN_MON_LOGS_EMPTY', '📋 <b>Логи мониторинга пусты</b>\\n\\nСистема еще не выполнила проверки.')\n                keyboard = get_monitoring_logs_back_keyboard(language)",
)

src = src.replace(
    "            text = f'📋 <b>Логи мониторинга</b> (стр. {page}/{paginated_logs.total_pages})\\n\\n'",
    "            text = texts.t('ADMIN_MON_LOGS_TITLE', '📋 <b>Логи мониторинга</b> (стр. {page}/{pages})\\n\\n').format(page=page, pages=paginated_logs.total_pages)",
)

old_log_line = """                text += f'{icon} <code>{time_str}</code> {event_type}\\n'
                text += f'   📄 {message}\\n\\n'"""
new_log_line = """                text += texts.t(
                    'ADMIN_MON_LOGS_LINE',
                    '{icon} <code>{time}</code> {event}\\n   📄 {message}\\n\\n',
                ).format(icon=icon, time=time_str, event=event_type, message=message)"""
src = src.replace(old_log_line, new_log_line)

src = src.replace(
    """            text += '📊 <b>Общая статистика:</b>\\n'
            text += f'• Всего событий: {len(all_logs)}\\n'
            text += f'• Успешных: {total_success}\\n'
            text += f'• Ошибок: {total_failed}\\n'
            text += f'• Успешность: {success_rate}%'""",
    """            text += texts.t(
                'ADMIN_MON_LOGS_STATS',
                '📊 <b>Общая статистика:</b>\\n• Всего событий: {total}\\n• Успешных: {success}\\n• Ошибок: {failed}\\n• Успешность: {rate}%',
            ).format(total=len(all_logs), success=total_success, failed=total_failed, rate=success_rate)""",
)

src = src.replace(
    "            keyboard = get_monitoring_logs_keyboard(page, paginated_logs.total_pages)",
    "            keyboard = get_monitoring_logs_keyboard(page, paginated_logs.total_pages, language)",
)

src = src.replace(
    "        await callback.answer('❌ Ошибка получения логов', show_alert=True)",
    "        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_LOGS_ERR', '❌ Ошибка получения логов'), show_alert=True)",
)

# clear logs
src = src.replace(
    """async def clear_logs_callback(callback: CallbackQuery):
    try:""",
    """async def clear_logs_callback(callback: CallbackQuery):
    try:
        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE
        texts = get_texts(language)""",
)

src = src.replace(
    "                await callback.answer(f'🗑️ Удалено {deleted_count} записей логов')",
    "                await callback.answer(texts.t('ADMIN_MON_LOGS_CLEARED', '🗑️ Удалено {count} записей логов').format(count=deleted_count))",
)
src = src.replace(
    "                await callback.answer('ℹ️ Логи уже пусты')",
    "                await callback.answer(texts.t('ADMIN_MON_LOGS_ALREADY_EMPTY', 'ℹ️ Логи уже пусты'))",
)
src = src.replace(
    "        await callback.answer(f'❌ Ошибка очистки: {e!s}', show_alert=True)",
    "        language = callback.from_user.language_code or settings.DEFAULT_LANGUAGE\n        await callback.answer(get_texts(language).t('ADMIN_MON_LOGS_CLEAR_ERR', '❌ Ошибка очистки: {error}').format(error=e), show_alert=True)",
    1,
)

path.write_text(src, encoding="utf-8")
print("patch part 2 done")
