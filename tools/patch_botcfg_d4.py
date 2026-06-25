#!/usr/bin/env python3
"""One-shot patch: bot_configuration.py D4 + fa.json ADMIN_BOTCFG_* / ADMIN_REMNA_CFG_* keys."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FA_PATH = ROOT / 'app/localization/locales/fa.json'
BOTCFG_PATH = ROOT / 'app/handlers/admin/bot_configuration.py'

FA_KEYS: dict[str, str] = {
    'ADMIN_BOTCFG_DASHBOARD_TITLE': '⚙️ <b>پنل تنظیمات ربات</b>',
    'ADMIN_BOTCFG_DASHBOARD_TOTAL': 'مجموع پارامترها: <b>{total}</b> • بازنویسی‌شده: <b>{overrides}</b>',
    'ADMIN_BOTCFG_DASHBOARD_GROUPS': '<b>گروه‌های تنظیمات</b>',
    'ADMIN_BOTCFG_DASHBOARD_GROUP_LINE': '{icon} <b>{title}</b> — {status}',
    'ADMIN_BOTCFG_DASHBOARD_GROUP_COUNT': '└ تنظیمات: {count}',
    'ADMIN_BOTCFG_DASHBOARD_SEARCH_HINT': '🔍 برای یافتن سریع پارامتر، جستجو را امتحان کنید.',
    'ADMIN_BOTCFG_GROUP_STATUS': 'وضعیت: {icon} {status}',
    'ADMIN_BOTCFG_GROUP_BREADCRUMB': '🏠 → {title}',
    'ADMIN_BOTCFG_GROUP_CATEGORIES': '📂 دسته‌های این گروه:',
    'ADMIN_BOTCFG_CATEGORY_LIST': '📋 فهرست تنظیمات دسته:',
    'ADMIN_BOTCFG_CATEGORY_BREADCRUMB': '🏠 → {group} → {category}',
    'ADMIN_BOTCFG_BTN_MAIN_MENU': '⬅️ منوی اصلی',
    'ADMIN_BOTCFG_BTN_SEARCH': '🔍 جستجوی تنظیم',
    'ADMIN_BOTCFG_BTN_PRESETS': '🎯 پیش‌تنظیم‌ها',
    'ADMIN_BOTCFG_BTN_EXPORT': '📤 خروجی .env',
    'ADMIN_BOTCFG_BTN_IMPORT': '📥 ورود .env',
    'ADMIN_BOTCFG_BTN_HISTORY': '🕘 تاریخچه',
    'ADMIN_BOTCFG_BTN_HELP': '❓ راهنما',
    'ADMIN_BOTCFG_BTN_BACK_ADMIN': '⬅️ بازگشت به ادمین',
    'ADMIN_BOTCFG_BTN_BACK_CATEGORIES': '⬅️ به دسته‌ها',
    'ADMIN_BOTCFG_BTN_TRY_AGAIN': '⬅️ دوباره امتحان کنید',
    'ADMIN_BOTCFG_GROUP_UNAVAILABLE': 'این گروه دیگر در دسترس نیست.',
    'ADMIN_BOTCFG_CATEGORY_EMPTY': 'در این دسته هنوز تنظیمی نیست.',
    'ADMIN_BOTCFG_GROUP_CORE_TITLE': '🤖 اصلی',
    'ADMIN_BOTCFG_GROUP_CORE_DESC': 'تنظیمات پایه ربات، کانال‌های اجباری و سرویس‌های کلیدی.',
    'ADMIN_BOTCFG_GROUP_SUPPORT_TITLE': '💬 پشتیبانی',
    'ADMIN_BOTCFG_GROUP_SUPPORT_DESC': 'تماس، تیکت، SLA و اعلان به ناظران.',
    'ADMIN_BOTCFG_GROUP_PAYMENTS_TITLE': '💳 درگاه‌های پرداخت',
    'ADMIN_BOTCFG_GROUP_PAYMENTS_DESC': 'YooKassa، CryptoBot، Stars و سایر درگاه‌ها.',
    'ADMIN_BOTCFG_GROUP_SUBSCRIPTIONS_TITLE': '📅 اشتراک و قیمت',
    'ADMIN_BOTCFG_GROUP_SUBSCRIPTIONS_DESC': 'سرویس‌ها، خرید ساده، دوره‌ها، حجم و تمدید خودکار.',
    'ADMIN_BOTCFG_GROUP_TRIAL_TITLE': '🎁 دوره آزمایشی',
    'ADMIN_BOTCFG_GROUP_TRIAL_DESC': 'مدت و محدودیت‌های دسترسی رایگان.',
    'ADMIN_BOTCFG_GROUP_REFERRAL_TITLE': '👥 برنامه ریفرال',
    'ADMIN_BOTCFG_GROUP_REFERRAL_DESC': 'پاداش، آستانه‌ها و اعلان به همکاران.',
    'ADMIN_BOTCFG_GROUP_NOTIFICATIONS_TITLE': '🔔 اعلان‌ها',
    'ADMIN_BOTCFG_GROUP_NOTIFICATIONS_DESC': 'اعلان کاربر، ادمین و گزارش‌ها.',
    'ADMIN_BOTCFG_GROUP_INTERFACE_TITLE': '🎨 رابط و برند',
    'ADMIN_BOTCFG_GROUP_INTERFACE_DESC': 'لوگو، متن‌ها، زبان‌ها، منو، مینی‌اپ و لینک‌ها.',
    'ADMIN_BOTCFG_GROUP_SERVER_TITLE': '📊 وضعیت سرورها',
    'ADMIN_BOTCFG_GROUP_SERVER_DESC': 'مانیتورینگ سرور، SLA و متریک‌های خارجی.',
    'ADMIN_BOTCFG_GROUP_MAINTENANCE_TITLE': '🔧 نگهداری',
    'ADMIN_BOTCFG_GROUP_MAINTENANCE_DESC': 'حالت تعمیر، پشتیبان و بررسی به‌روزرسانی.',
    'ADMIN_BOTCFG_GROUP_ADVANCED_TITLE': '⚡ پیشرفته',
    'ADMIN_BOTCFG_GROUP_ADVANCED_DESC': 'Web API، webhook، لاگ، moderation و حالت دیباگ.',
    'ADMIN_BOTCFG_GROUP_OTHER_TITLE': '📦 سایر تنظیمات',
    'ADMIN_BOTCFG_GROUP_OTHER_DESC': 'تنظیمات متفرقه.',
    'ADMIN_BOTCFG_STATUS_PAYMENTS_NONE': 'هیچ درگاه فعالی نیست',
    'ADMIN_BOTCFG_STATUS_PAYMENTS_PARTIAL': 'فعال {active} از {total}',
    'ADMIN_BOTCFG_STATUS_PAYMENTS_ALL': 'همه سیستم‌ها فعال',
    'ADMIN_BOTCFG_STATUS_RW_OK': 'API متصل است',
    'ADMIN_BOTCFG_STATUS_RW_NEEDS_CREDS': 'URL و کلیدها را وارد کنید',
    'ADMIN_BOTCFG_STATUS_SERVER_MON_ON': 'مانیتورینگ فعال',
    'ADMIN_BOTCFG_STATUS_SERVER_REPORTS': 'فقط گزارش در دسترس',
    'ADMIN_BOTCFG_STATUS_SERVER_OFF': 'مانیتورینگ خاموش',
    'ADMIN_BOTCFG_STATUS_MAINT_ON': 'حالت تعمیر روشن',
    'ADMIN_BOTCFG_STATUS_MAINT_OFF': 'حالت عادی',
    'ADMIN_BOTCFG_STATUS_NOTIFY_ALL': 'همه اعلان‌ها روشن',
    'ADMIN_BOTCFG_STATUS_NOTIFY_PARTIAL': 'بخشی از اعلان‌ها روشن',
    'ADMIN_BOTCFG_STATUS_NOTIFY_OFF': 'اعلان‌ها خاموش',
    'ADMIN_BOTCFG_STATUS_TRIAL_ON': '{days} روز دوره آزمایشی',
    'ADMIN_BOTCFG_STATUS_TRIAL_OFF': 'آزمایشی غیرفعال',
    'ADMIN_BOTCFG_STATUS_REF_ACTIVE': 'برنامه فعال',
    'ADMIN_BOTCFG_STATUS_REF_INACTIVE': 'پاداش تنظیم نشده',
    'ADMIN_BOTCFG_STATUS_CORE_OK': 'ربات آماده است',
    'ADMIN_BOTCFG_STATUS_CORE_TOKEN': 'توکن ربات را بررسی کنید',
    'ADMIN_BOTCFG_STATUS_SUB_OK': 'سرویس‌ها تنظیم شده',
    'ADMIN_BOTCFG_STATUS_SUB_NEEDS_PRICE': 'قیمت‌ها را تنظیم کنید',
    'ADMIN_BOTCFG_STATUS_DB_PG': 'PostgreSQL',
    'ADMIN_BOTCFG_STATUS_DB_SQLITE': 'حالت SQLite',
    'ADMIN_BOTCFG_STATUS_DB_AUTO': 'حالت خودکار',
    'ADMIN_BOTCFG_STATUS_IFACE_OK': 'برند تنظیم شده',
    'ADMIN_BOTCFG_STATUS_IFACE_DEFAULT': 'تنظیمات پیش‌فرض',
    'ADMIN_BOTCFG_STATUS_READY': 'آماده',
    'ADMIN_REMNA_CFG_TITLE': '📱 <b>پیکربندی اپ (Remnawave)</b>',
    'ADMIN_REMNA_CFG_EMPTY': 'در Remnawave پیکربندی صفحه اشتراک یافت نشد.\n\nدر پنل Remnawave یک پیکربندی بسازید و برگردید.',
    'ADMIN_REMNA_CFG_CURRENT': '✅ فعلی: <b>{name}</b>',
    'ADMIN_REMNA_CFG_UUID_MISSING': '⚠️ UUID فعلی یافت نشد: <code>{uuid}</code>',
    'ADMIN_REMNA_CFG_NOT_SELECTED': 'ℹ️ پیکربندی انتخاب نشده (حالت راهنما خاموش)',
    'ADMIN_REMNA_CFG_PICK': 'پیکربندی را برای حالت راهنما انتخاب کنید:',
    'ADMIN_REMNA_CFG_BTN_CLEAR': '🗑 پاک کردن (خاموش کردن راهنما)',
    'ADMIN_REMNA_CFG_LOAD_ERR': 'خطا در بارگذاری پیکربندی‌ها',
    'ADMIN_REMNA_CFG_UUID_INVALID': 'UUID پیکربندی نامعتبر است',
    'ADMIN_REMNA_CFG_SAVE_ERR': 'خطا در ذخیره',
    'ADMIN_REMNA_CFG_CLEAR_ERR': 'خطا در پاک‌سازی',
    'ADMIN_REMNA_CFG_SELECTED': '✅ پیکربندی انتخاب شد',
    'ADMIN_REMNA_CFG_CLEARED': '✅ پیکربندی پاک شد',
}


def merge_fa_json() -> None:
    data = json.loads(FA_PATH.read_text(encoding='utf-8'))
    data.update(FA_KEYS)
    FA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'fa.json: +{len(FA_KEYS)} keys')


def patch_bot_configuration() -> None:
    text = BOTCFG_PATH.read_text(encoding='utf-8')

    helper = '''
def _group_title(language: str, group_key: str) -> str:
    texts = get_texts(language)
    if group_key == CATEGORY_FALLBACK_KEY:
        return texts.t('ADMIN_BOTCFG_GROUP_OTHER_TITLE', CATEGORY_FALLBACK_TITLE)
    meta = _get_group_meta(group_key)
    fallback = str(meta.get('title', group_key))
    return texts.t(f'ADMIN_BOTCFG_GROUP_{group_key.upper()}_TITLE', fallback)


def _group_description_text(language: str, group_key: str) -> str:
    texts = get_texts(language)
    if group_key == CATEGORY_FALLBACK_KEY:
        return texts.t('ADMIN_BOTCFG_GROUP_OTHER_DESC', '')
    meta = _get_group_meta(group_key)
    fallback = str(meta.get('description', ''))
    return texts.t(f'ADMIN_BOTCFG_GROUP_{group_key.upper()}_DESC', fallback)

'''

    if '_group_title(' not in text:
        text = text.replace(
            'def _get_group_meta(group_key: str) -> dict[str, object]:\n',
            helper + 'def _get_group_meta(group_key: str) -> dict[str, object]:\n',
        )

    # _get_group_description -> delegate
    text = re.sub(
        r'def _get_group_description\(group_key: str\) -> str:\n    meta = _get_group_meta\(group_key\)\n    return str\(meta\.get\(\'description\', \'\'\)\)\n',
        'def _get_group_description(group_key: str, language: str) -> str:\n    return _group_description_text(language, group_key)\n',
        text,
    )

    # _get_group_status signature + body replacements
    text = text.replace(
        'def _get_group_status(group_key: str) -> tuple[str, str]:\n    key = group_key',
        'def _get_group_status(group_key: str, language: str) -> tuple[str, str]:\n    texts = get_texts(language)\n    key = group_key',
    )
    replacements = [
        ("return '🔴', 'Нет активных платежей'", "return '🔴', texts.t('ADMIN_BOTCFG_STATUS_PAYMENTS_NONE', 'Нет активных платежей')"),
        ("return '🟡', f'Активно {active} из {total}'", "return '🟡', texts.t('ADMIN_BOTCFG_STATUS_PAYMENTS_PARTIAL', 'Активно {active} из {total}').format(active=active, total=total)"),
        ("return '🟢', 'Все системы активны'", "return '🟢', texts.t('ADMIN_BOTCFG_STATUS_PAYMENTS_ALL', 'Все системы активны')"),
        ("return ('🟢', 'API подключено') if api_ready else ('🟡', 'Нужно указать URL и ключи')",
         "return ('🟢', texts.t('ADMIN_BOTCFG_STATUS_RW_OK', 'API подключено')) if api_ready else ('🟡', texts.t('ADMIN_BOTCFG_STATUS_RW_NEEDS_CREDS', 'Нужно указать URL и ключи'))"),
        ("return '🟢', 'Мониторинг активен'", "return '🟢', texts.t('ADMIN_BOTCFG_STATUS_SERVER_MON_ON', 'Мониторинг активен')"),
        ("return '🟡', 'Доступны только отчеты'", "return '🟡', texts.t('ADMIN_BOTCFG_STATUS_SERVER_REPORTS', 'Доступны только отчеты')"),
        ("return '⚪', 'Мониторинг выключен'", "return '⚪', texts.t('ADMIN_BOTCFG_STATUS_SERVER_OFF', 'Мониторинг выключен')"),
        ("return '🟡', 'Режим ТО включен'", "return '🟡', texts.t('ADMIN_BOTCFG_STATUS_MAINT_ON', 'Режим ТО включен')"),
        ("return '🟢', 'Рабочий режим'", "return '🟢', texts.t('ADMIN_BOTCFG_STATUS_MAINT_OFF', 'Рабочий режим')"),
        ("return '🟢', 'Все уведомления включены'", "return '🟢', texts.t('ADMIN_BOTCFG_STATUS_NOTIFY_ALL', 'Все уведомления включены')"),
        ("return '🟡', 'Часть уведомлений включена'", "return '🟡', texts.t('ADMIN_BOTCFG_STATUS_NOTIFY_PARTIAL', 'Часть уведомлений включена')"),
        ("return '⚪', 'Уведомления отключены'", "return '⚪', texts.t('ADMIN_BOTCFG_STATUS_NOTIFY_OFF', 'Уведомления отключены')"),
        ("return '🟢', f'{settings.TRIAL_DURATION_DAYS} дней пробного периода'",
         "return '🟢', texts.t('ADMIN_BOTCFG_STATUS_TRIAL_ON', '{days} дней пробного периода').format(days=settings.TRIAL_DURATION_DAYS)"),
        ("return '⚪', 'Триал отключен'", "return '⚪', texts.t('ADMIN_BOTCFG_STATUS_TRIAL_OFF', 'Триал отключен')"),
        ("return ('🟢', 'Программа активна') if active else ('⚪', 'Бонусы не заданы')",
         "return ('🟢', texts.t('ADMIN_BOTCFG_STATUS_REF_ACTIVE', 'Программа активна')) if active else ('⚪', texts.t('ADMIN_BOTCFG_STATUS_REF_INACTIVE', 'Бонусы не заданы'))"),
        ("return '🟢', 'Бот готов к работе'", "return '🟢', texts.t('ADMIN_BOTCFG_STATUS_CORE_OK', 'Бот готов к работе')"),
        ("return '🟡', 'Проверьте токен бота'", "return '🟡', texts.t('ADMIN_BOTCFG_STATUS_CORE_TOKEN', 'Проверьте токен бота')"),
        ("return ('🟢', 'Тарифы настроены') if price_ready else ('⚪', 'Нужно задать цены')",
         "return ('🟢', texts.t('ADMIN_BOTCFG_STATUS_SUB_OK', 'Тарифы настроены')) if price_ready else ('⚪', texts.t('ADMIN_BOTCFG_STATUS_SUB_NEEDS_PRICE', 'Нужно задать цены'))"),
        ("return '🟢', 'PostgreSQL'", "return '🟢', texts.t('ADMIN_BOTCFG_STATUS_DB_PG', 'PostgreSQL')"),
        ("return '🟡', 'SQLite режим'", "return '🟡', texts.t('ADMIN_BOTCFG_STATUS_DB_SQLITE', 'SQLite режим')"),
        ("return '🟢', 'Авто режим'", "return '🟢', texts.t('ADMIN_BOTCFG_STATUS_DB_AUTO', 'Авто режим')"),
        ("return ('🟢', 'Брендинг настроен') if branding else ('⚪', 'Настройки по умолчанию')",
         "return ('🟢', texts.t('ADMIN_BOTCFG_STATUS_IFACE_OK', 'Брендинг настроен')) if branding else ('⚪', texts.t('ADMIN_BOTCFG_STATUS_IFACE_DEFAULT', 'Настройки по умолчанию'))"),
        ("return '🟢', 'Готово к работе'", "return '🟢', texts.t('ADMIN_BOTCFG_STATUS_READY', 'Готово к работе')"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)

    # _render_dashboard_overview
    text = text.replace(
        'def _render_dashboard_overview() -> str:\n    grouped = _get_grouped_categories()',
        'def _render_dashboard_overview(language: str) -> str:\n    texts = get_texts(language)\n    grouped = _get_grouped_categories(language)',
    )
    text = text.replace(
        "    lines: list[str] = [\n        '⚙️ <b>ПАНЕЛЬ УПРАВЛЕНИЯ БОТОМ</b>',\n        '',\n        f'Всего параметров: <b>{total_settings}</b> • Переопределено: <b>{total_overrides}</b>',\n        '',\n        '<b>Группы настроек</b>',\n        '',\n    ]",
        "    lines: list[str] = [\n        texts.t('ADMIN_BOTCFG_DASHBOARD_TITLE', '⚙️ <b>ПАНЕЛЬ УПРАВЛЕНИЯ БОТОМ</b>'),\n        '',\n        texts.t('ADMIN_BOTCFG_DASHBOARD_TOTAL', 'Всего параметров: <b>{total}</b> • Переопределено: <b>{overrides}</b>').format(total=total_settings, overrides=total_overrides),\n        '',\n        texts.t('ADMIN_BOTCFG_DASHBOARD_GROUPS', '<b>Группы настроек</b>'),\n        '',\n    ]",
    )
    text = text.replace(
        '        status_icon, status_text = _get_group_status(group_key)\n        total = sum(count for _, _, count in items)\n        lines.append(f\'{status_icon} <b>{title}</b> — {status_text}\')\n        lines.append(f\'└ Настроек: {total}\')',
        '        status_icon, status_text = _get_group_status(group_key, language)\n        total = sum(count for _, _, count in items)\n        lines.append(texts.t(\'ADMIN_BOTCFG_DASHBOARD_GROUP_LINE\', \'{icon} <b>{title}</b> — {status}\').format(icon=status_icon, title=title, status=status_text))\n        lines.append(texts.t(\'ADMIN_BOTCFG_DASHBOARD_GROUP_COUNT\', \'└ Настроек: {count}\').format(count=total))',
    )
    text = text.replace(
        "    lines.append('🔍 Используйте поиск, чтобы быстро найти нужный параметр по ключу или названию.')",
        "    lines.append(texts.t('ADMIN_BOTCFG_DASHBOARD_SEARCH_HINT', '🔍 Используйте поиск, чтобы быстро найти нужный параметр по ключу или названию.'))",
    )

    # _get_grouped_categories
    text = text.replace(
        'def _get_grouped_categories() -> list[tuple[str, str, list[tuple[str, str, int]]]]:',
        'def _get_grouped_categories(language: str = \'ru\') -> list[tuple[str, str, list[tuple[str, str, int]]]]:',
    )
    text = text.replace(
        '            grouped.append((group_key, title, items))',
        '            grouped.append((group_key, _group_title(language, group_key), items))',
    )
    text = text.replace(
        '        grouped.append((CATEGORY_FALLBACK_KEY, CATEGORY_FALLBACK_TITLE, remaining))',
        '        grouped.append((CATEGORY_FALLBACK_KEY, _group_title(language, CATEGORY_FALLBACK_KEY), remaining))',
    )

    # _build_groups_keyboard
    text = text.replace(
        'def _build_groups_keyboard() -> types.InlineKeyboardMarkup:\n    grouped = _get_grouped_categories()',
        'def _build_groups_keyboard(language: str) -> types.InlineKeyboardMarkup:\n    texts = get_texts(language)\n    grouped = _get_grouped_categories(language)',
    )
    text = text.replace(
        '        status_icon, status_text = _get_group_status(group_key)\n        button_text = f\'{status_icon} {title} — {status_text}\'',
        '        status_icon, status_text = _get_group_status(group_key, language)\n        button_text = f\'{status_icon} {title} — {status_text}\'',
    )
    kb_replacements = [
        ("text='🔍 Найти настройку'", "text=texts.t('ADMIN_BOTCFG_BTN_SEARCH', '🔍 Найти настройку')"),
        ("text='🎯 Пресеты'", "text=texts.t('ADMIN_BOTCFG_BTN_PRESETS', '🎯 Пресеты')"),
        ("text='📤 Экспорт .env'", "text=texts.t('ADMIN_BOTCFG_BTN_EXPORT', '📤 Экспорт .env')"),
        ("text='📥 Импорт .env'", "text=texts.t('ADMIN_BOTCFG_BTN_IMPORT', '📥 Импорт .env')"),
        ("text='🕘 История'", "text=texts.t('ADMIN_BOTCFG_BTN_HISTORY', '🕘 История')"),
        ("text='❓ Помощь'", "text=texts.t('ADMIN_BOTCFG_BTN_HELP', '❓ Помощь')"),
        ("text='⬅️ Назад в админку'", "text=texts.t('ADMIN_BOTCFG_BTN_BACK_ADMIN', '⬅️ Назад в админку')"),
        ("text='⬅️ В главное меню'", "text=texts.t('ADMIN_BOTCFG_BTN_MAIN_MENU', '⬅️ В главное меню')"),
        ("text='🏠 Главное меню'", "text=texts.t('ADMIN_BOTCFG_BTN_MAIN_MENU', '🏠 Главное меню')"),
        ("text='⬅️ К категориям'", "text=texts.t('ADMIN_BOTCFG_BTN_BACK_CATEGORIES', '⬅️ К категориям')"),
        ("text='⬅️ Попробовать снова'", "text=texts.t('ADMIN_BOTCFG_BTN_TRY_AGAIN', '⬅️ Попробовать снова')"),
    ]
    for old, new in kb_replacements:
        text = text.replace(old, new)

    # show_bot_config_menu
    text = text.replace(
        '    keyboard = _build_groups_keyboard()\n    overview = _render_dashboard_overview()',
        '    keyboard = _build_groups_keyboard(db_user.language)\n    overview = _render_dashboard_overview(db_user.language)',
    )

    # show_bot_config_group
    text = text.replace(
        '    grouped = _get_grouped_categories()\n    group_lookup = {key: (title, items) for key, title, items in grouped}\n\n    if group_key not in group_lookup:\n        await callback.answer(\'Эта группа больше недоступна\', show_alert=True)',
        '    texts = get_texts(db_user.language)\n    grouped = _get_grouped_categories(db_user.language)\n    group_lookup = {key: (title, items) for key, title, items in grouped}\n\n    if group_key not in group_lookup:\n        await callback.answer(texts.t(\'ADMIN_BOTCFG_GROUP_UNAVAILABLE\', \'Эта группа больше недоступна\'), show_alert=True)',
    )
    text = text.replace(
        '    status_icon, status_text = _get_group_status(group_key)\n    description = _get_group_description(group_key)',
        '    status_icon, status_text = _get_group_status(group_key, db_user.language)\n    description = _get_group_description(group_key, db_user.language)',
    )
    text = text.replace(
        "        lines.append(f'Статус: {status_icon} {status_text}')\n    lines.append(f'🏠 → {clean_title}')",
        "        lines.append(texts.t('ADMIN_BOTCFG_GROUP_STATUS', 'Статус: {icon} {status}').format(icon=status_icon, status=status_text))\n    lines.append(texts.t('ADMIN_BOTCFG_GROUP_BREADCRUMB', '🏠 → {title}').format(title=clean_title))",
    )
    text = text.replace(
        "    lines.append('📂 Категории группы:')",
        "    lines.append(texts.t('ADMIN_BOTCFG_GROUP_CATEGORIES', '📂 Категории группы:'))",
    )

    # show_bot_config_category partial
    text = text.replace(
        "        await callback.answer('В этой категории пока нет настроек', show_alert=True)",
        "        await callback.answer(get_texts(db_user.language).t('ADMIN_BOTCFG_CATEGORY_EMPTY', 'В этой категории пока нет настроек'), show_alert=True)",
    )
    text = text.replace(
        "    text_lines.append('📋 Список настроек категории:')",
        "    text_lines.append(get_texts(db_user.language).t('ADMIN_BOTCFG_CATEGORY_LIST', '📋 Список настроек категории:'))",
    )

    # remna config menu
    remna_old = '''async def show_remna_config_menu(callback: types.CallbackQuery, db_user: User, db: AsyncSession, **kwargs):
    """Show available Remnawave subscription page configs for selection."""
    current_uuid = bot_configuration_service.get_current_value('CABINET_REMNA_SUB_CONFIG')

    try:
        service = RemnaWaveService()
        async with service.get_api_client() as api:
            configs = await api.get_subscription_page_configs()
    except Exception as e:
        logger.error('Failed to load Remnawave configs', error=e)
        await callback.answer('Ошибка загрузки конфигов', show_alert=True)
        return

    keyboard: list[list[types.InlineKeyboardButton]] = []

    if not configs:
        text = (
            '📱 <b>Конфиг приложений (Remnawave)</b>\\n\\n'
            'В Remnawave не найдено конфигураций страниц подписки.\\n\\n'
            'Создайте конфигурацию в панели Remnawave, затем вернитесь сюда для выбора.'
        )
    else:
        text = '📱 <b>Конфиг приложений (Remnawave)</b>\\n\\n'
        if current_uuid:
            current_name = next((c.name for c in configs if c.uuid == current_uuid), None)
            if current_name:
                text += f'✅ Текущий: <b>{html.escape(current_name)}</b>\\n\\n'
            else:
                text += f'⚠️ Текущий UUID не найден: <code>{html.escape(str(current_uuid))}</code>\\n\\n'
        else:
            text += 'ℹ️ Конфиг не выбран (гайд-режим отключён)\\n\\n'

        text += 'Выберите конфигурацию для гайд-режима:'

        for config in configs:
            prefix = '✅ ' if config.uuid == current_uuid else ''
            keyboard.append(
                [
                    types.InlineKeyboardButton(
                        text=f'{prefix}{config.name}',
                        callback_data=f'admin_remna_select_{config.uuid}',
                    )
                ]
            )

    if current_uuid:
        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text='🗑 Сбросить (отключить гайд-режим)',
                    callback_data='admin_remna_clear',
                )
            ]
        )

    keyboard.append([types.InlineKeyboardButton(text='⬅️ Назад', callback_data='admin_submenu_settings')])'''

    remna_new = '''async def show_remna_config_menu(callback: types.CallbackQuery, db_user: User, db: AsyncSession, **kwargs):
    """Show available Remnawave subscription page configs for selection."""
    texts = get_texts(db_user.language)
    current_uuid = bot_configuration_service.get_current_value('CABINET_REMNA_SUB_CONFIG')

    try:
        service = RemnaWaveService()
        async with service.get_api_client() as api:
            configs = await api.get_subscription_page_configs()
    except Exception as e:
        logger.error('Failed to load Remnawave configs', error=e)
        await callback.answer(texts.t('ADMIN_REMNA_CFG_LOAD_ERR', 'Ошибка загрузки конфигов'), show_alert=True)
        return

    keyboard: list[list[types.InlineKeyboardButton]] = []

    if not configs:
        text = texts.t(
            'ADMIN_REMNA_CFG_TITLE',
            '📱 <b>Конфиг приложений (Remnawave)</b>',
        ) + '\\n\\n' + texts.t(
            'ADMIN_REMNA_CFG_EMPTY',
            'В Remnawave не найдено конфигураций страниц подписки.\\n\\nСоздайте конфигурацию в панели Remnawave, затем вернитесь сюда для выбора.',
        )
    else:
        text = texts.t('ADMIN_REMNA_CFG_TITLE', '📱 <b>Конфиг приложений (Remnawave)</b>') + '\\n\\n'
        if current_uuid:
            current_name = next((c.name for c in configs if c.uuid == current_uuid), None)
            if current_name:
                text += texts.t('ADMIN_REMNA_CFG_CURRENT', '✅ Текущий: <b>{name}</b>').format(name=html.escape(current_name)) + '\\n\\n'
            else:
                text += texts.t('ADMIN_REMNA_CFG_UUID_MISSING', '⚠️ Текущий UUID не найден: <code>{uuid}</code>').format(uuid=html.escape(str(current_uuid))) + '\\n\\n'
        else:
            text += texts.t('ADMIN_REMNA_CFG_NOT_SELECTED', 'ℹ️ Конфиг не выбран (гайд-режим отключён)') + '\\n\\n'

        text += texts.t('ADMIN_REMNA_CFG_PICK', 'Выберите конфигурацию для гайд-режима:')

        for config in configs:
            prefix = '✅ ' if config.uuid == current_uuid else ''
            keyboard.append(
                [
                    types.InlineKeyboardButton(
                        text=f'{prefix}{config.name}',
                        callback_data=f'admin_remna_select_{config.uuid}',
                    )
                ]
            )

    if current_uuid:
        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t('ADMIN_REMNA_CFG_BTN_CLEAR', '🗑 Сбросить (отключить гайд-режим)'),
                    callback_data='admin_remna_clear',
                )
            ]
        )

    keyboard.append([types.InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '⬅️ Назад'), callback_data='admin_submenu_settings')])'''

    if remna_old in text:
        text = text.replace(remna_old, remna_new)
    else:
        print('WARN: remna block not found verbatim')

  # select/clear remna
    text = text.replace(
        "        await callback.answer('Некорректный UUID конфигурации', show_alert=True)",
        "        await callback.answer(get_texts(db_user.language).t('ADMIN_REMNA_CFG_UUID_INVALID', 'Некорректный UUID конфигурации'), show_alert=True)",
    )
    text = text.replace(
        "        await callback.answer('Ошибка сохранения', show_alert=True)",
        "        await callback.answer(get_texts(db_user.language).t('ADMIN_REMNA_CFG_SAVE_ERR', 'Ошибка сохранения'), show_alert=True)",
    )
    text = text.replace(
        "    await callback.answer('✅ Конфиг выбран', show_alert=True)",
        "    await callback.answer(get_texts(db_user.language).t('ADMIN_REMNA_CFG_SELECTED', '✅ Конфиг выбран'), show_alert=True)",
    )
    text = text.replace(
        "        await callback.answer('Ошибка сброса', show_alert=True)",
        "        await callback.answer(get_texts(db_user.language).t('ADMIN_REMNA_CFG_CLEAR_ERR', 'Ошибка сброса'), show_alert=True)",
    )
    text = text.replace(
        "    await callback.answer('✅ Конфиг сброшен', show_alert=True)",
        "    await callback.answer(get_texts(db_user.language).t('ADMIN_REMNA_CFG_CLEARED', '✅ Конфиг сброшен'), show_alert=True)",
    )

    BOTCFG_PATH.write_text(text, encoding='utf-8')
    print('bot_configuration.py patched')


if __name__ == '__main__':
    merge_fa_json()
    patch_bot_configuration()
