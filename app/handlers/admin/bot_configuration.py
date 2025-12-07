import html
import io
import logging
import math
import time
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from aiogram import Dispatcher, F, types
from aiogram.filters import BaseFilter, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import SystemSetting, User
from app.database.crud.server_squad import (
    get_all_server_squads,
    get_server_squad_by_id,
    get_server_squad_by_uuid,
)
from app.localization.texts import get_texts
from app.config import settings
from app.services.remnawave_service import RemnaWaveService
from app.services.payment_service import PaymentService
from app.services.system_settings_service import (
    ReadOnlySettingError,
    bot_configuration_service,
)
from app.states import BotConfigStates
from app.utils.decorators import admin_required, error_handler
from app.utils.currency_converter import currency_converter
from app.external.telegram_stars import TelegramStarsService


CATEGORY_PAGE_SIZE = 10
SETTINGS_PAGE_SIZE = 8
SIMPLE_SUBSCRIPTION_SQUADS_PAGE_SIZE = 6

CATEGORY_GROUP_METADATA: Dict[str, Dict[str, object]] = {
    "core": {
        "title_key": "ADMIN_CFG_GROUP_CORE_TITLE",
        "title_default": "🤖 Core",
        "desc_key": "ADMIN_CFG_GROUP_CORE_DESC",
        "desc_default": "Basic bot settings, required channels, and key services.",
        "icon": "🤖",
        "categories": (
            "CORE",
            "CHANNEL",
            "TIMEZONE",
            "DATABASE",
            "POSTGRES",
            "SQLITE",
            "REDIS",
            "REMNAWAVE",
        ),
    },
    "support": {
        "title_key": "ADMIN_CFG_GROUP_SUPPORT_TITLE",
        "title_default": "💬 Support",
        "desc_key": "ADMIN_CFG_GROUP_SUPPORT_DESC",
        "desc_default": "Contacts, ticket modes, SLA, and moderator notifications.",
        "icon": "💬",
        "categories": ("SUPPORT",),
    },
    "payments": {
        "title_key": "ADMIN_CFG_GROUP_PAYMENTS_TITLE",
        "title_default": "💳 Payment Systems",
        "desc_key": "ADMIN_CFG_GROUP_PAYMENTS_DESC",
        "desc_default": "YooKassa, CryptoBot, Heleket, MulenPay, PAL24, Wata, Platega, Tribute, and Telegram Stars.",
        "icon": "💳",
        "categories": (
            "PAYMENT",
            "PAYMENT_VERIFICATION",
            "YOOKASSA",
            "CRYPTOBOT",
            "HELEKET",
            "MULENPAY",
            "PAL24",
            "WATA",
            "PLATEGA",
            "TRIBUTE",
            "TELEGRAM",
        ),
    },
    "subscriptions": {
        "title_key": "ADMIN_CFG_GROUP_SUBSCRIPTIONS_TITLE",
        "title_default": "📅 Subscriptions & Pricing",
        "desc_key": "ADMIN_CFG_GROUP_SUBSCRIPTIONS_DESC",
        "desc_default": "Plans, simple purchase, periods, traffic limits, and auto-renewal.",
        "icon": "📅",
        "categories": (
            "SUBSCRIPTIONS_CORE",
            "SIMPLE_SUBSCRIPTION",
            "PERIODS",
            "SUBSCRIPTION_PRICES",
            "TRAFFIC",
            "TRAFFIC_PACKAGES",
            "AUTOPAY",
        ),
    },
    "trial": {
        "title_key": "ADMIN_CFG_GROUP_TRIAL_TITLE",
        "title_default": "🎁 Trial Period",
        "desc_key": "ADMIN_CFG_GROUP_TRIAL_DESC",
        "desc_default": "Duration and limitations of free access.",
        "icon": "🎁",
        "categories": ("TRIAL",),
    },
    "referral": {
        "title_key": "ADMIN_CFG_GROUP_REFERRAL_TITLE",
        "title_default": "👥 Referral Program",
        "desc_key": "ADMIN_CFG_GROUP_REFERRAL_DESC",
        "desc_default": "Bonuses, thresholds, and partner notifications.",
        "icon": "👥",
        "categories": ("REFERRAL",),
    },
    "notifications": {
        "title_key": "ADMIN_CFG_GROUP_NOTIFICATIONS_TITLE",
        "title_default": "🔔 Notifications",
        "desc_key": "ADMIN_CFG_GROUP_NOTIFICATIONS_DESC",
        "desc_default": "User and admin alerts and reports.",
        "icon": "🔔",
        "categories": ("NOTIFICATIONS", "ADMIN_NOTIFICATIONS", "ADMIN_REPORTS"),
    },
    "interface": {
        "title_key": "ADMIN_CFG_GROUP_INTERFACE_TITLE",
        "title_default": "🎨 Interface & Branding",
        "desc_key": "ADMIN_CFG_GROUP_INTERFACE_DESC",
        "desc_default": "Logo, texts, languages, main menu, miniapp, and deep links.",
        "icon": "🎨",
        "categories": (
            "INTERFACE",
            "INTERFACE_BRANDING",
            "INTERFACE_SUBSCRIPTION",
            "CONNECT_BUTTON",
            "MINIAPP",
            "HAPP",
            "SKIP",
            "LOCALIZATION",
            "ADDITIONAL",
        ),
    },
    "server": {
        "title_key": "ADMIN_CFG_GROUP_SERVER_TITLE",
        "title_default": "📊 Server Status",
        "desc_key": "ADMIN_CFG_GROUP_SERVER_DESC",
        "desc_default": "Server monitoring, SLA, and external metrics.",
        "icon": "📊",
        "categories": ("SERVER_STATUS", "MONITORING"),
    },
    "maintenance": {
        "title_key": "ADMIN_CFG_GROUP_MAINTENANCE_TITLE",
        "title_default": "🔧 Maintenance",
        "desc_key": "ADMIN_CFG_GROUP_MAINTENANCE_DESC",
        "desc_default": "Maintenance mode, backups, and update checks.",
        "icon": "🔧",
        "categories": ("MAINTENANCE", "BACKUP", "VERSION"),
    },
    "advanced": {
        "title_key": "ADMIN_CFG_GROUP_ADVANCED_TITLE",
        "title_default": "⚡ Advanced",
        "desc_key": "ADMIN_CFG_GROUP_ADVANCED_DESC",
        "desc_default": "Web API, webhook, logging, moderation, and debug mode.",
        "icon": "⚡",
        "categories": (
            "WEB_API",
            "WEBHOOK",
            "LOG",
            "MODERATION",
            "DEBUG",
            "EXTERNAL_ADMIN",
        ),
    },
}

CATEGORY_GROUP_ORDER: Tuple[str, ...] = (
    "core",
    "support",
    "payments",
    "subscriptions",
    "trial",
    "referral",
    "notifications",
    "interface",
    "server",
    "maintenance",
    "advanced",
)

CATEGORY_GROUP_DEFINITIONS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = tuple(
    (
        group_key,
        str(CATEGORY_GROUP_METADATA[group_key]["title_default"]),
        tuple(CATEGORY_GROUP_METADATA[group_key]["categories"]),
    )
    for group_key in CATEGORY_GROUP_ORDER
)

CATEGORY_TO_GROUP: Dict[str, str] = {}
for _group_key, _title, _category_keys in CATEGORY_GROUP_DEFINITIONS:
    for _category_key in _category_keys:
        CATEGORY_TO_GROUP[_category_key] = _group_key

CATEGORY_FALLBACK_KEY = "other"
CATEGORY_FALLBACK_TITLE_KEY = "ADMIN_CFG_GROUP_OTHER_TITLE"
CATEGORY_FALLBACK_TITLE_DEFAULT = "📦 Other Settings"

PRESET_CONFIGS: Dict[str, Dict[str, object]] = {
    "recommended": {
        "ENABLE_NOTIFICATIONS": True,
        "ADMIN_NOTIFICATIONS_ENABLED": True,
        "ADMIN_REPORTS_ENABLED": True,
        "MONITORING_INTERVAL": 60,
        "TRIAL_DURATION_DAYS": 3,
    },
    "minimal": {
        "ENABLE_NOTIFICATIONS": False,
        "ADMIN_NOTIFICATIONS_ENABLED": False,
        "ADMIN_REPORTS_ENABLED": False,
        "TRIAL_DURATION_DAYS": 0,
        "REFERRAL_NOTIFICATIONS_ENABLED": False,
    },
    "secure": {
        "MAINTENANCE_AUTO_ENABLE": True,
        "ADMIN_NOTIFICATIONS_ENABLED": True,
        "ADMIN_REPORTS_ENABLED": True,
        "REFERRAL_MINIMUM_TOPUP_KOPEKS": 100000,
        "SERVER_STATUS_MODE": "disabled",
    },
    "testing": {
        "DEBUG": True,
        "ENABLE_NOTIFICATIONS": False,
        "TRIAL_DURATION_DAYS": 7,
        "SERVER_STATUS_MODE": "disabled",
        "ADMIN_NOTIFICATIONS_ENABLED": False,
    },
}

PRESET_METADATA: Dict[str, Dict[str, str]] = {
    "recommended": {
        "title_key": "ADMIN_CFG_PRESET_RECOMMENDED_TITLE",
        "title_default": "Recommended Settings",
        "desc_key": "ADMIN_CFG_PRESET_RECOMMENDED_DESC",
        "desc_default": "Balance between stability and team communication.",
    },
    "minimal": {
        "title_key": "ADMIN_CFG_PRESET_MINIMAL_TITLE",
        "title_default": "Minimal Configuration",
        "desc_key": "ADMIN_CFG_PRESET_MINIMAL_DESC",
        "desc_default": "Suitable for test launch without notifications.",
    },
    "secure": {
        "title_key": "ADMIN_CFG_PRESET_SECURE_TITLE",
        "title_default": "Maximum Security",
        "desc_key": "ADMIN_CFG_PRESET_SECURE_DESC",
        "desc_default": "Enhanced access control and disabled extra integrations.",
    },
    "testing": {
        "title_key": "ADMIN_CFG_PRESET_TESTING_TITLE",
        "title_default": "For Testing",
        "desc_key": "ADMIN_CFG_PRESET_TESTING_DESC",
        "desc_default": "Enables debug mode and disables external notifications.",
    },
}


def _get_group_meta(group_key: str) -> Dict[str, object]:
    return CATEGORY_GROUP_METADATA.get(group_key, {})


def _get_group_title(group_key: str, language: str = "en") -> str:
    texts = get_texts(language)
    meta = _get_group_meta(group_key)
    if not meta:
        return texts.t(CATEGORY_FALLBACK_TITLE_KEY, CATEGORY_FALLBACK_TITLE_DEFAULT)
    title_key = str(meta.get("title_key", ""))
    title_default = str(meta.get("title_default", ""))
    return texts.t(title_key, title_default) if title_key else title_default


def _get_group_description(group_key: str, language: str = "en") -> str:
    texts = get_texts(language)
    meta = _get_group_meta(group_key)
    desc_key = str(meta.get("desc_key", ""))
    desc_default = str(meta.get("desc_default", ""))
    return texts.t(desc_key, desc_default) if desc_key else desc_default


def _get_group_icon(group_key: str) -> str:
    meta = _get_group_meta(group_key)
    return str(meta.get("icon", "⚙️"))


def _get_group_status(group_key: str, language: str = "en") -> Tuple[str, str]:
    texts = get_texts(language)
    key = group_key
    if key == "payments":
        payment_statuses = {
            "YooKassa": settings.is_yookassa_enabled(),
            "CryptoBot": settings.is_cryptobot_enabled(),
            "Platega": settings.is_platega_enabled(),
            "MulenPay": settings.is_mulenpay_enabled(),
            "PAL24": settings.is_pal24_enabled(),
            "Tribute": settings.TRIBUTE_ENABLED,
            "Stars": settings.TELEGRAM_STARS_ENABLED,
        }
        active = sum(1 for value in payment_statuses.values() if value)
        total = len(payment_statuses)
        if active == 0:
            return "🔴", texts.t("ADMIN_CFG_STATUS_NO_PAYMENTS", "No active payments")
        if active < total:
            return "🟡", texts.t("ADMIN_CFG_STATUS_PAYMENTS_PARTIAL", "Active {active} of {total}").format(active=active, total=total)
        return "🟢", texts.t("ADMIN_CFG_STATUS_PAYMENTS_ALL", "All systems active")

    if key == "remnawave":
        api_ready = bool(
            settings.REMNAWAVE_API_URL
            and (
                settings.REMNAWAVE_API_KEY
                or (settings.REMNAWAVE_USERNAME and settings.REMNAWAVE_PASSWORD)
            )
        )
        if api_ready:
            return "🟢", texts.t("ADMIN_CFG_STATUS_API_CONNECTED", "API connected")
        return "🟡", texts.t("ADMIN_CFG_STATUS_API_NEEDS_CONFIG", "URL and keys required")

    if key == "server":
        mode = (settings.SERVER_STATUS_MODE or "").lower()
        monitoring_active = mode not in {"", "disabled"}
        if monitoring_active:
            return "🟢", texts.t("ADMIN_CFG_STATUS_MONITORING_ACTIVE", "Monitoring active")
        if settings.MONITORING_INTERVAL:
            return "🟡", texts.t("ADMIN_CFG_STATUS_REPORTS_ONLY", "Reports only")
        return "⚪", texts.t("ADMIN_CFG_STATUS_MONITORING_OFF", "Monitoring disabled")

    if key == "maintenance":
        if settings.MAINTENANCE_MODE:
            return "🟡", texts.t("ADMIN_CFG_STATUS_MAINTENANCE_ON", "Maintenance mode on")
        return "🟢", texts.t("ADMIN_CFG_STATUS_WORKING", "Working mode")

    if key == "notifications":
        user_on = settings.is_notifications_enabled()
        admin_on = settings.is_admin_notifications_enabled()
        if user_on and admin_on:
            return "🟢", texts.t("ADMIN_CFG_STATUS_NOTIF_ALL_ON", "All notifications enabled")
        if user_on or admin_on:
            return "🟡", texts.t("ADMIN_CFG_STATUS_NOTIF_PARTIAL", "Some notifications enabled")
        return "⚪", texts.t("ADMIN_CFG_STATUS_NOTIF_OFF", "Notifications disabled")

    if key == "trial":
        if settings.TRIAL_DURATION_DAYS > 0:
            return "🟢", texts.t("ADMIN_CFG_STATUS_TRIAL_DAYS", "{days} days trial period").format(days=settings.TRIAL_DURATION_DAYS)
        return "⚪", texts.t("ADMIN_CFG_STATUS_TRIAL_OFF", "Trial disabled")

    if key == "referral":
        active = (
            settings.REFERRAL_COMMISSION_PERCENT
            or settings.REFERRAL_FIRST_TOPUP_BONUS_KOPEKS
            or settings.REFERRAL_INVITER_BONUS_KOPEKS
        )
        if active:
            return "🟢", texts.t("ADMIN_CFG_STATUS_REFERRAL_ACTIVE", "Program active")
        return "⚪", texts.t("ADMIN_CFG_STATUS_REFERRAL_NO_BONUS", "No bonuses set")

    if key == "core":
        token_ok = bool(getattr(settings, "BOT_TOKEN", ""))
        channel_ok = bool(settings.CHANNEL_LINK or not settings.CHANNEL_IS_REQUIRED_SUB)
        if token_ok and channel_ok:
            return "🟢", texts.t("ADMIN_CFG_STATUS_BOT_READY", "Bot ready")
        return "🟡", texts.t("ADMIN_CFG_STATUS_CHECK_TOKEN", "Check token and required subscription")

    if key == "subscriptions":
        price_ready = settings.PRICE_30_DAYS > 0 and settings.AVAILABLE_SUBSCRIPTION_PERIODS
        if price_ready:
            return "🟢", texts.t("ADMIN_CFG_STATUS_PRICES_SET", "Pricing configured")
        return "⚪", texts.t("ADMIN_CFG_STATUS_PRICES_NEEDED", "Prices need to be set")

    if key == "database":
        mode = (settings.DATABASE_MODE or "auto").lower()
        if mode == "postgresql":
            return "🟢", "PostgreSQL"
        if mode == "sqlite":
            return "🟡", texts.t("ADMIN_CFG_STATUS_SQLITE_MODE", "SQLite mode")
        return "🟢", texts.t("ADMIN_CFG_STATUS_AUTO_MODE", "Auto mode")

    if key == "interface":
        branding = bool(settings.ENABLE_LOGO_MODE or settings.MINIAPP_CUSTOM_URL)
        if branding:
            return "🟢", texts.t("ADMIN_CFG_STATUS_BRANDING_SET", "Branding configured")
        return "⚪", texts.t("ADMIN_CFG_STATUS_DEFAULT_SETTINGS", "Default settings")

    return "🟢", texts.t("ADMIN_CFG_STATUS_READY", "Ready")


def _get_setting_icon(definition, current_value: object) -> str:
    key_upper = definition.key.upper()

    if definition.python_type is bool:
        return "✅" if bool(current_value) else "❌"

    if bot_configuration_service.has_choices(definition.key):
        return "📋"

    if isinstance(current_value, (int, float)):
        return "🔢"

    if isinstance(current_value, str):
        if not current_value.strip():
            return "⚪"
        if "URL" in key_upper:
            return "🔗"
        if any(keyword in key_upper for keyword in ("TOKEN", "SECRET", "PASSWORD", "KEY")):
            return "🔒"

    if any(keyword in key_upper for keyword in ("TIME", "HOUR", "MINUTE")):
        return "⏱"
    if "DAYS" in key_upper:
        return "📆"
    if "GB" in key_upper or "TRAFFIC" in key_upper:
        return "📊"

    return "⚙️"


def _render_dashboard_overview(language: str = "en") -> str:
    texts = get_texts(language)
    grouped = _get_grouped_categories(language)
    total_settings = 0
    total_overrides = 0

    for group_key, _title, items in grouped:
        for category_key, _label, count in items:
            total_settings += count
            definitions = bot_configuration_service.get_settings_for_category(category_key)
            total_overrides += sum(
                1 for definition in definitions if bot_configuration_service.has_override(definition.key)
            )

    lines: List[str] = [
        texts.t("ADMIN_CFG_DASHBOARD_TITLE", "⚙️ <b>BOT CONTROL PANEL</b>"),
        "",
        texts.t("ADMIN_CFG_DASHBOARD_STATS", "Total parameters: <b>{total}</b> • Overridden: <b>{overrides}</b>").format(
            total=total_settings, overrides=total_overrides
        ),
        "",
        texts.t("ADMIN_CFG_DASHBOARD_GROUPS_HEADER", "<b>Settings Groups</b>"),
        "",
    ]

    for group_key, title, items in grouped:
        status_icon, status_text = _get_group_status(group_key, language)
        total = sum(count for _, _, count in items)
        lines.append(f"{status_icon} <b>{title}</b> — {status_text}")
        lines.append(texts.t("ADMIN_CFG_DASHBOARD_SETTINGS_COUNT", "└ Settings: {count}").format(count=total))
        lines.append("")

    lines.append(texts.t("ADMIN_CFG_DASHBOARD_SEARCH_HINT", "🔍 Use search to quickly find a setting by key or name."))
    return "\n".join(lines).strip()


def _build_group_category_index() -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
    for group_key, _title, items in _get_grouped_categories():
        mapping[group_key] = [category_key for category_key, _label, _count in items]
    return mapping


def _perform_settings_search(query: str) -> List[Dict[str, object]]:
    normalized = query.strip().lower()
    if not normalized:
        return []

    categories = bot_configuration_service.get_categories()
    group_category_index = _build_group_category_index()
    results: List[Dict[str, object]] = []

    for category_key, _label, _count in categories:
        definitions = bot_configuration_service.get_settings_for_category(category_key)
        group_key = CATEGORY_TO_GROUP.get(category_key, CATEGORY_FALLBACK_KEY)
        available_categories = group_category_index.get(group_key, [])
        if category_key in available_categories:
            category_index = available_categories.index(category_key)
            category_page = category_index // CATEGORY_PAGE_SIZE + 1
        else:
            category_page = 1

        for definition_index, definition in enumerate(definitions):
            fields = [definition.key.lower(), definition.display_name.lower()]
            guidance = bot_configuration_service.get_setting_guidance(definition.key)
            fields.extend(
                [
                    guidance.get("description", "").lower(),
                    guidance.get("format", "").lower(),
                    str(guidance.get("dependencies", "")).lower(),
                ]
            )

            if not any(normalized in field for field in fields if field):
                continue

            settings_page = definition_index // SETTINGS_PAGE_SIZE + 1
            results.append(
                {
                    "key": definition.key,
                    "name": definition.display_name,
                    "category_key": category_key,
                    "category_label": definition.category_label,
                    "group_key": group_key,
                    "category_page": category_page,
                    "settings_page": settings_page,
                    "token": bot_configuration_service.get_callback_token(definition.key),
                    "value": bot_configuration_service.format_value_human(
                        definition.key,
                        bot_configuration_service.get_current_value(definition.key),
                    ),
                }
            )

    results.sort(key=lambda item: item["name"].lower())
    return results[:20]


def _build_search_results_keyboard(results: List[Dict[str, object]], language: str = "en") -> types.InlineKeyboardMarkup:
    from app.localization.texts import get_texts
    texts = get_texts(language)
    rows: List[List[types.InlineKeyboardButton]] = []
    for result in results:
        group_key = str(result["group_key"])
        category_page = int(result["category_page"])
        settings_page = int(result["settings_page"])
        token = str(result["token"])
        text = f"{result['name']}"
        if len(text) > 60:
            text = text[:59] + "…"
        rows.append(
            [
                types.InlineKeyboardButton(
                    text=text,
                    callback_data=(
                        f"botcfg_setting:{group_key}:{category_page}:{settings_page}:{token}"
                    ),
                )
            ]
        )

    rows.append(
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BACK_TO_MAIN", "🏠 Back to main menu"),
                callback_data="admin_bot_config",
            )
        ]
    )
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def _parse_env_content(content: str) -> Dict[str, Optional[str]]:
    parsed: Dict[str, Optional[str]] = {}
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


@admin_required
@error_handler
async def start_settings_search(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    await state.set_state(BotConfigStates.waiting_for_search_query)
    await state.update_data(botcfg_origin="bot_config")

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_BACK_TO_MAIN", "🏠 Back to main menu"), callback_data="admin_bot_config"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        texts.t("ADMIN_CFG_SEARCH_PROMPT", "🔍 <b>Search settings</b>\n\nSend part of the key or setting name.\nExample: <code>yookassa</code> or <code>notifications</code>."),
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer(texts.t("ADMIN_CFG_ENTER_QUERY", "Enter query"), show_alert=False)


@admin_required
@error_handler
async def handle_search_query(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    if message.chat.type != "private":
        return

    data = await state.get_data()
    if data.get("botcfg_origin") != "bot_config":
        return

    texts = get_texts(db_user.language)
    query = (message.text or "").strip()
    results = _perform_settings_search(query)

    if results:
        keyboard = _build_search_results_keyboard(results, db_user.language)
        lines = [
            texts.t("ADMIN_CFG_SEARCH_RESULTS_TITLE", "🔍 <b>Search Results</b>"),
            texts.t("ADMIN_CFG_SEARCH_QUERY", "Query: <code>{query}</code>").format(query=html.escape(query)),
            "",
        ]
        for index, item in enumerate(results, start=1):
            lines.append(
                f"{index}. {item['name']} — {item['value']} ({item['category_label']})"
            )
        text = "\n".join(lines)
    else:
        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_CFG_BTN_TRY_AGAIN", "⬅️ Try again"),
                        callback_data="botcfg_action:search",
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_BACK_TO_MAIN", "🏠 Back to main menu"), callback_data="admin_bot_config"
                    )
                ],
            ]
        )
        text = texts.t(
            "ADMIN_CFG_SEARCH_NO_RESULTS",
            "🔍 <b>Search Results</b>\n\nQuery: <code>{query}</code>\n\nNothing found. Try changing your search terms."
        ).format(query=html.escape(query))

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
    await state.clear()


@admin_required
@error_handler
async def show_presets(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    lines = [
        texts.t("ADMIN_CFG_PRESETS_TITLE", "🎯 <b>Ready Presets</b>"),
        "",
        texts.t("ADMIN_CFG_PRESETS_HINT", "Select a preset to quickly apply it to the bot."),
        "",
    ]
    for key, meta in PRESET_METADATA.items():
        title = texts.t(meta["title_key"], meta["title_default"])
        desc = texts.t(meta["desc_key"], meta["desc_default"])
        lines.append(f"• <b>{title}</b> — {desc}")
    text = "\n".join(lines)

    buttons: List[types.InlineKeyboardButton] = []
    for key, meta in PRESET_METADATA.items():
        title = texts.t(meta["title_key"], meta["title_default"])
        buttons.append(
            types.InlineKeyboardButton(
                text=title, callback_data=f"botcfg_preset:{key}"
            )
        )

    rows: List[List[types.InlineKeyboardButton]] = []
    for chunk in _chunk(buttons, 2):
        rows.append(list(chunk))
    rows.append(
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BACK_TO_MAIN", "🏠 Back to main menu"), callback_data="admin_bot_config"
            )
        ]
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await callback.answer()


def _format_preset_preview(preset_key: str, language: str = "en") -> Tuple[str, List[str]]:
    texts = get_texts(language)
    config = PRESET_CONFIGS.get(preset_key, {})
    meta = PRESET_METADATA.get(preset_key, {"title_default": preset_key, "desc_default": ""})
    title = texts.t(meta.get("title_key", ""), meta.get("title_default", preset_key))
    description = texts.t(meta.get("desc_key", ""), meta.get("desc_default", ""))

    lines = [f"🎯 <b>{title}</b>"]
    if description:
        lines.append(description)
    lines.append("")
    lines.append(texts.t("ADMIN_CFG_PRESET_WILL_SET", "The following values will be set:"))

    for index, (setting_key, new_value) in enumerate(config.items(), start=1):
        current_value = bot_configuration_service.get_current_value(setting_key)
        current_pretty = bot_configuration_service.format_value_human(setting_key, current_value)
        new_pretty = bot_configuration_service.format_value_human(setting_key, new_value)
        current_label = texts.t("ADMIN_CFG_PRESET_CURRENT", "Current")
        new_label = texts.t("ADMIN_CFG_PRESET_NEW", "New")
        lines.append(
            f"{index}. <code>{setting_key}</code>\n"
            f"   {current_label}: {current_pretty}\n"
            f"   {new_label}: {new_pretty}"
        )

    return title, lines


@admin_required
@error_handler
async def preview_preset(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    parts = callback.data.split(":", 1)
    preset_key = parts[1] if len(parts) > 1 else ""
    if preset_key not in PRESET_CONFIGS:
        await callback.answer(texts.t("ADMIN_CFG_PRESET_UNAVAILABLE", "This preset is unavailable"), show_alert=True)
        return

    title, lines = _format_preset_preview(preset_key, db_user.language)
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CFG_BTN_APPLY", "✅ Apply"), callback_data=f"botcfg_preset_apply:{preset_key}"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.BACK, callback_data="botcfg_action:presets"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await callback.answer()


@admin_required
@error_handler
async def apply_preset(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    parts = callback.data.split(":", 1)
    preset_key = parts[1] if len(parts) > 1 else ""
    config = PRESET_CONFIGS.get(preset_key)
    if not config:
        await callback.answer(texts.t("ADMIN_CFG_PRESET_UNAVAILABLE", "This preset is unavailable"), show_alert=True)
        return

    applied: List[str] = []
    for setting_key, value in config.items():
        try:
            await bot_configuration_service.set_value(db, setting_key, value)
            applied.append(setting_key)
        except ReadOnlySettingError:
            logging.getLogger(__name__).info(
                "Skipping setting %s from preset %s: read-only",
                setting_key,
                preset_key,
            )
        except Exception as error:
            logging.getLogger(__name__).warning(
                "Failed to apply preset %s for %s: %s",
                preset_key,
                setting_key,
                error,
            )
    await db.commit()

    meta = PRESET_METADATA.get(preset_key, {})
    title = texts.t(meta.get("title_key", ""), meta.get("title_default", preset_key))
    summary_lines = [
        texts.t("ADMIN_CFG_PRESET_APPLIED", "✅ Preset <b>{title}</b> applied").format(title=title),
        "",
        texts.t("ADMIN_CFG_PRESET_PARAMS_CHANGED", "Parameters changed: <b>{count}</b>").format(count=len(applied)),
    ]
    if applied:
        summary_lines.append("\n".join(f"• <code>{key}</code>" for key in applied))

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CFG_BTN_TO_PRESETS", "⬅️ To presets"), callback_data="botcfg_action:presets"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_BACK_TO_MAIN", "🏠 Back to main menu"), callback_data="admin_bot_config"
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "\n".join(summary_lines),
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await callback.answer(texts.t("ADMIN_CFG_SETTINGS_UPDATED", "Settings updated"), show_alert=False)


@admin_required
@error_handler
async def export_settings(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    categories = bot_configuration_service.get_categories()
    keys: List[str] = []
    for category_key, _label, _count in categories:
        for definition in bot_configuration_service.get_settings_for_category(category_key):
            keys.append(definition.key)

    keys = sorted(set(keys))
    lines = [
        "# RemnaWave bot configuration export",
        f"# Generated at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
    ]

    for setting_key in keys:
        current_value = bot_configuration_service.get_current_value(setting_key)
        raw_value = bot_configuration_service.serialize_value(setting_key, current_value)
        if raw_value is None:
            raw_value = ""
        lines.append(f"{setting_key}={raw_value}")

    content = "\n".join(lines)
    filename = f"bot-settings-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.env"
    file = types.BufferedInputFile(content.encode("utf-8"), filename=filename)

    texts = get_texts(db_user.language)
    await callback.message.answer_document(
        document=file,
        caption=texts.t("ADMIN_CFG_EXPORT_CAPTION", "📤 Current settings export"),
        parse_mode="HTML",
    )
    await callback.answer(texts.t("ADMIN_CFG_FILE_READY", "File ready"), show_alert=False)


@admin_required
@error_handler
async def start_import_settings(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    await state.set_state(BotConfigStates.waiting_for_import_file)
    await state.update_data(botcfg_origin="bot_config")

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_BACK_TO_MAIN", "🏠 Back to main menu"), callback_data="admin_bot_config"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        texts.t("ADMIN_CFG_IMPORT_PROMPT", "📥 <b>Import settings</b>\n\nAttach a .env file or send text with <code>KEY=value</code> pairs.\nUnknown parameters will be ignored."),
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    await callback.answer(texts.t("ADMIN_CFG_UPLOAD_ENV", "Upload .env file"), show_alert=False)


@admin_required
@error_handler
async def handle_import_message(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    if message.chat.type != "private":
        return

    data = await state.get_data()
    if data.get("botcfg_origin") != "bot_config":
        return

    content = ""
    if message.document:
        buffer = io.BytesIO()
        await message.document.download(destination=buffer)
        buffer.seek(0)
        content = buffer.read().decode("utf-8", errors="ignore")
    else:
        content = message.text or ""

    texts = get_texts(db_user.language)
    parsed = _parse_env_content(content)
    if not parsed:
        await message.answer(
            texts.t("ADMIN_CFG_IMPORT_NO_PARAMS", "❌ Could not find parameters in the file. Make sure to use KEY=value format."),
            parse_mode="HTML",
        )
        await state.clear()
        return

    applied: List[str] = []
    skipped: List[str] = []
    errors: List[str] = []

    for setting_key, raw_value in parsed.items():
        try:
            bot_configuration_service.get_definition(setting_key)
        except KeyError:
            skipped.append(setting_key)
            continue

        value_to_apply: Optional[object]
        try:
            if raw_value in {"", '""'}:
                value_to_apply = None
            else:
                value_to_apply = bot_configuration_service.deserialize_value(
                    setting_key, raw_value
                )
        except Exception as error:
            errors.append(f"{setting_key}: {error}")
            continue

        if bot_configuration_service.is_read_only(setting_key):
            skipped.append(setting_key)
            continue
        try:
            await bot_configuration_service.set_value(db, setting_key, value_to_apply)
            applied.append(setting_key)
        except ReadOnlySettingError:
            skipped.append(setting_key)

    await db.commit()

    summary_lines = [
        texts.t("ADMIN_CFG_IMPORT_DONE", "📥 <b>Import completed</b>"),
        texts.t("ADMIN_CFG_IMPORT_UPDATED", "Updated parameters: <b>{count}</b>").format(count=len(applied)),
    ]
    if applied:
        summary_lines.append("\n".join(f"• <code>{key}</code>" for key in applied))

    if skipped:
        summary_lines.append("\n" + texts.t("ADMIN_CFG_IMPORT_SKIPPED", "Skipped (unknown keys):"))
        summary_lines.append("\n".join(f"• <code>{key}</code>" for key in skipped))

    if errors:
        summary_lines.append("\n" + texts.t("ADMIN_CFG_IMPORT_ERRORS", "Parse errors:"))
        summary_lines.append("\n".join(f"• {html.escape(err)}" for err in errors))
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_BACK_TO_MAIN", "🏠 Back to main menu"), callback_data="admin_bot_config"
                )
            ]
        ]
    )

    await message.answer(
        "\n".join(summary_lines), parse_mode="HTML", reply_markup=keyboard
    )
    await state.clear()


@admin_required
@error_handler
async def show_settings_history(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    result = await db.execute(
        select(SystemSetting).order_by(SystemSetting.updated_at.desc()).limit(10)
    )
    rows = result.scalars().all()

    lines = [texts.t("ADMIN_CFG_HISTORY_TITLE", "🕘 <b>Change History</b>"), ""]
    if rows:
        for row in rows:
            timestamp = row.updated_at or row.created_at
            ts_text = timestamp.strftime("%d.%m %H:%M") if timestamp else "—"
            try:
                parsed_value = bot_configuration_service.deserialize_value(row.key, row.value)
                formatted_value = bot_configuration_service.format_value_human(
                    row.key, parsed_value
                )
            except Exception:
                formatted_value = row.value or "—"
            lines.append(f"{ts_text} • <code>{row.key}</code> = {formatted_value}")
    else:
        lines.append(texts.t("ADMIN_CFG_HISTORY_EMPTY", "Change history is empty."))
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_BACK_TO_MAIN", "🏠 Back to main menu"), callback_data="admin_bot_config"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=keyboard
    )
    await callback.answer()


@admin_required
@error_handler
async def show_help(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    text = texts.t(
        "ADMIN_CFG_HELP_TEXT",
        "❓ <b>How to use the panel</b>\n\n"
        "• Navigate through categories to see related settings.\n"
        "• The ✳️ icon next to a parameter means the value is overridden.\n"
        "• Use 🔍 search for quick access to a setting.\n"
        "• Export .env before major changes to have a backup.\n"
        "• Import allows you to restore configuration or apply a template.\n"
        "• All secret keys are hidden in the interface automatically."
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_BACK_TO_MAIN", "🏠 Back to main menu"), callback_data="admin_bot_config"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=keyboard
    )
    await callback.answer()


async def _store_setting_context(
    state: FSMContext,
    *,
    key: str,
    group_key: str,
    category_page: int,
    settings_page: int,
) -> None:
    await state.update_data(
        setting_key=key,
        setting_group_key=group_key,
        setting_category_page=category_page,
        setting_settings_page=settings_page,
        botcfg_origin="bot_config",
        botcfg_timestamp=time.time(),
    )


class BotConfigInputFilter(BaseFilter):
    def __init__(self, timeout: float = 300.0) -> None:
        self.timeout = timeout

    async def __call__(
        self,
        message: types.Message,
        state: FSMContext,
    ) -> bool:
        if not message.text or message.text.startswith("/"):
            return False

        if message.chat.type != "private":
            return False

        data = await state.get_data()

        if data.get("botcfg_origin") != "bot_config":
            return False

        if not data.get("setting_key"):
            return False

        timestamp = data.get("botcfg_timestamp")
        if timestamp is None:
            return True

        try:
            return (time.time() - float(timestamp)) <= self.timeout
        except (TypeError, ValueError):
            return False


def _chunk(buttons: Iterable[types.InlineKeyboardButton], size: int) -> Iterable[List[types.InlineKeyboardButton]]:
    buttons_list = list(buttons)
    for index in range(0, len(buttons_list), size):
        yield buttons_list[index : index + size]


def _parse_category_payload(payload: str) -> Tuple[str, str, int, int]:
    parts = payload.split(":")
    group_key = parts[1] if len(parts) > 1 else CATEGORY_FALLBACK_KEY
    category_key = parts[2] if len(parts) > 2 else ""

    def _safe_int(value: str, default: int = 1) -> int:
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return default

    category_page = _safe_int(parts[3]) if len(parts) > 3 else 1
    settings_page = _safe_int(parts[4]) if len(parts) > 4 else 1
    return group_key, category_key, category_page, settings_page


def _parse_group_payload(payload: str) -> Tuple[str, int]:
    parts = payload.split(":")
    group_key = parts[1] if len(parts) > 1 else CATEGORY_FALLBACK_KEY
    try:
        page = max(1, int(parts[2]))
    except (IndexError, ValueError):
        page = 1
    return group_key, page


def _get_grouped_categories(language: str = "en") -> List[Tuple[str, str, List[Tuple[str, str, int]]]]:
    categories = bot_configuration_service.get_categories()
    categories_map = {key: (label, count) for key, label, count in categories}
    used: set[str] = set()
    grouped: List[Tuple[str, str, List[Tuple[str, str, int]]]] = []

    for group_key, _title_default, category_keys in CATEGORY_GROUP_DEFINITIONS:
        items: List[Tuple[str, str, int]] = []
        for category_key in category_keys:
            if category_key in categories_map:
                label, count = categories_map[category_key]
                items.append((category_key, label, count))
                used.add(category_key)
        if items:
            localized_title = _get_group_title(group_key, language)
            grouped.append((group_key, localized_title, items))

    remaining = [
        (key, label, count)
        for key, (label, count) in categories_map.items()
        if key not in used
    ]

    if remaining:
        remaining.sort(key=lambda item: item[1])
        texts = get_texts(language)
        fallback_title = texts.t(CATEGORY_FALLBACK_TITLE_KEY, CATEGORY_FALLBACK_TITLE_DEFAULT)
        grouped.append((CATEGORY_FALLBACK_KEY, fallback_title, remaining))

    return grouped


def _build_groups_keyboard(language: str = "en") -> types.InlineKeyboardMarkup:
    texts = get_texts(language)
    grouped = _get_grouped_categories(language)
    rows: list[list[types.InlineKeyboardButton]] = []

    for group_key, title, items in grouped:
        total = sum(count for _, _, count in items)
        status_icon, status_text = _get_group_status(group_key, language)
        button_text = f"{status_icon} {title} — {status_text}"
        rows.append(
            [
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"botcfg_group:{group_key}:1",
                )
            ]
        )

    rows.append(
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_SEARCH", "🔍 Find setting"),
                callback_data="botcfg_action:search",
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_PRESETS", "🎯 Presets"),
                callback_data="botcfg_action:presets",
            ),
        ]
    )

    rows.append(
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_EXPORT", "📤 Export .env"),
                callback_data="botcfg_action:export",
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_IMPORT", "📥 Import .env"),
                callback_data="botcfg_action:import",
            ),
        ]
    )

    rows.append(
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_HISTORY", "🕘 History"),
                callback_data="botcfg_action:history",
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_HELP", "❓ Help"),
                callback_data="botcfg_action:help",
            ),
        ]
    )

    rows.append(
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_BACK_ADMIN", "⬅️ Back to admin"),
                callback_data="admin_submenu_settings",
            )
        ]
    )

    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def _build_categories_keyboard(
    group_key: str,
    group_title: str,
    categories: List[Tuple[str, str, int]],
    page: int = 1,
    language: str = "en",
) -> types.InlineKeyboardMarkup:
    texts = get_texts(language)
    total_pages = max(1, math.ceil(len(categories) / CATEGORY_PAGE_SIZE))
    page = max(1, min(page, total_pages))

    start = (page - 1) * CATEGORY_PAGE_SIZE
    end = start + CATEGORY_PAGE_SIZE
    sliced = categories[start:end]

    rows: list[list[types.InlineKeyboardButton]] = []

    buttons: List[types.InlineKeyboardButton] = []
    for category_key, label, count in sliced:
        overrides = 0
        for definition in bot_configuration_service.get_settings_for_category(category_key):
            if bot_configuration_service.has_override(definition.key):
                overrides += 1
        badge = "✳️ •" if overrides else "•"
        button_text = f"{badge} {label} ({count})"
        buttons.append(
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"botcfg_cat:{group_key}:{category_key}:{page}:1",
            )
        )

    for chunk in _chunk(buttons, 2):
        rows.append(list(chunk))

    if total_pages > 1:
        nav_row: list[types.InlineKeyboardButton] = []
        if page > 1:
            nav_row.append(
                types.InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"botcfg_group:{group_key}:{page - 1}",
                )
            )
        nav_row.append(
            types.InlineKeyboardButton(
                text=f"[{page}/{total_pages}]",
                callback_data="botcfg_group:noop",
            )
        )
        if page < total_pages:
            nav_row.append(
                types.InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"botcfg_group:{group_key}:{page + 1}",
                )
            )
        rows.append(nav_row)

    rows.append(
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_TO_SECTIONS", "⬅️ To sections"),
                callback_data="admin_bot_config",
            )
        ]
    )

    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def _build_settings_keyboard(
    category_key: str,
    group_key: str,
    category_page: int,
    language: str,
    page: int = 1,
) -> types.InlineKeyboardMarkup:
    definitions = bot_configuration_service.get_settings_for_category(category_key)
    total_pages = max(1, math.ceil(len(definitions) / SETTINGS_PAGE_SIZE))
    page = max(1, min(page, total_pages))

    start = (page - 1) * SETTINGS_PAGE_SIZE
    end = start + SETTINGS_PAGE_SIZE
    sliced = definitions[start:end]

    rows: list[list[types.InlineKeyboardButton]] = []
    texts = get_texts(language)

    test_suffix = texts.t("ADMIN_CFG_TEST_SUFFIX", "test")

    if category_key == "REMNAWAVE":
        rows.append(
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CFG_BTN_TEST_CONNECTION", "🔌 Test connection"),
                    callback_data=(
                        f"botcfg_test_remnawave:{group_key}:{category_key}:{category_page}:{page}"
                    ),
                )
            ]
        )

    test_payment_buttons: list[list[types.InlineKeyboardButton]] = []

    def _test_button(text: str, method: str) -> types.InlineKeyboardButton:
        return types.InlineKeyboardButton(
            text=text,
            callback_data=(
                f"botcfg_test_payment:{method}:{group_key}:{category_key}:{category_page}:{page}"
            ),
        )

    if category_key == "YOOKASSA":
        label = texts.t("PAYMENT_CARD_YOOKASSA", "💳 Bank card (YooKassa)")
        test_payment_buttons.append([_test_button(f"{label} · {test_suffix}", "yookassa")])
    elif category_key == "TRIBUTE":
        label = texts.t("PAYMENT_CARD_TRIBUTE", "💳 Bank card (Tribute)")
        test_payment_buttons.append([_test_button(f"{label} · {test_suffix}", "tribute")])
    elif category_key == "MULENPAY":
        label = texts.t(
            "PAYMENT_CARD_MULENPAY",
            "💳 Bank card ({mulenpay_name})",
        ).format(mulenpay_name=settings.get_mulenpay_display_name())
        test_payment_buttons.append([_test_button(f"{label} · {test_suffix}", "mulenpay")])
    elif category_key == "WATA":
        label = texts.t("PAYMENT_CARD_WATA", "💳 Bank card (WATA)")
        test_payment_buttons.append([_test_button(f"{label} · {test_suffix}", "wata")])
    elif category_key == "PAL24":
        label = texts.t("PAYMENT_CARD_PAL24", "💳 Bank card (PayPalych)")
        test_payment_buttons.append([_test_button(f"{label} · {test_suffix}", "pal24")])
    elif category_key == "TELEGRAM":
        label = texts.t("PAYMENT_TELEGRAM_STARS", "⭐ Telegram Stars")
        test_payment_buttons.append([_test_button(f"{label} · {test_suffix}", "stars")])
    elif category_key == "CRYPTOBOT":
        label = texts.t("PAYMENT_CRYPTOBOT", "🪙 Cryptocurrency (CryptoBot)")
        test_payment_buttons.append([_test_button(f"{label} · {test_suffix}", "cryptobot")])

    if test_payment_buttons:
        rows.extend(test_payment_buttons)

    for definition in sliced:
        current_value = bot_configuration_service.get_current_value(definition.key)
        value_preview = bot_configuration_service.format_value_for_list(definition.key)
        icon = _get_setting_icon(definition, current_value)
        override_badge = "✳️" if bot_configuration_service.has_override(definition.key) else "•"
        button_text = f"{override_badge} {icon} {definition.display_name}"
        if value_preview != "—":
            button_text += f" · {value_preview}"
        if len(button_text) > 64:
            button_text = button_text[:63] + "…"
        callback_token = bot_configuration_service.get_callback_token(definition.key)
        rows.append(
            [
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=(
                        f"botcfg_setting:{group_key}:{category_page}:{page}:{callback_token}"
                    ),
                )
            ]
        )

    if total_pages > 1:
        nav_row: list[types.InlineKeyboardButton] = []
        if page > 1:
            nav_row.append(
                types.InlineKeyboardButton(
                    text="⬅️",
                    callback_data=(
                        f"botcfg_cat:{group_key}:{category_key}:{category_page}:{page - 1}"
                    ),
                )
            )
        nav_row.append(
            types.InlineKeyboardButton(
                text=f"[{page}/{total_pages}]", callback_data="botcfg_cat_page:noop"
            )
        )
        if page < total_pages:
            nav_row.append(
                types.InlineKeyboardButton(
                    text="➡️",
                    callback_data=(
                        f"botcfg_cat:{group_key}:{category_key}:{category_page}:{page + 1}"
                    ),
                )
            )
        rows.append(nav_row)

    rows.append([
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_CFG_BTN_TO_CATEGORIES", "⬅️ To categories"),
            callback_data=f"botcfg_group:{group_key}:{category_page}",
        )
    ])

    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def _build_setting_keyboard(
    key: str,
    group_key: str,
    category_page: int,
    settings_page: int,
    language: str = "en",
) -> types.InlineKeyboardMarkup:
    texts = get_texts(language)
    definition = bot_configuration_service.get_definition(key)
    rows: list[list[types.InlineKeyboardButton]] = []
    callback_token = bot_configuration_service.get_callback_token(key)
    is_read_only = bot_configuration_service.is_read_only(key)

    choice_options = bot_configuration_service.get_choice_options(key)
    if choice_options and not is_read_only:
        current_value = bot_configuration_service.get_current_value(key)
        choice_buttons: list[types.InlineKeyboardButton] = []
        for option in choice_options:
            choice_token = bot_configuration_service.get_choice_token(key, option.value)
            if choice_token is None:
                continue
            button_text = option.label
            if current_value == option.value and not button_text.startswith("✅"):
                button_text = f"✅ {button_text}"
            choice_buttons.append(
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=(
                        f"botcfg_choice:{group_key}:{category_page}:{settings_page}:{callback_token}:{choice_token}"
                    ),
                )
            )

        for chunk in _chunk(choice_buttons, 2):
            rows.append(list(chunk))

    if key == "SIMPLE_SUBSCRIPTION_SQUAD_UUID" and not is_read_only:
        rows.append([
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_SELECT_SQUAD", "🌍 Select squad"),
                callback_data=(
                    f"botcfg_simple_squad:{group_key}:{category_page}:{settings_page}:{callback_token}:1"
                ),
            )
        ])

    if definition.python_type is bool and not is_read_only:
        rows.append([
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_TOGGLE", "🔁 Toggle"),
                callback_data=(
                    f"botcfg_toggle:{group_key}:{category_page}:{settings_page}:{callback_token}"
                ),
            )
        ])

    if not is_read_only:
        rows.append([
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_EDIT", "✏️ Edit"),
                callback_data=(
                    f"botcfg_edit:{group_key}:{category_page}:{settings_page}:{callback_token}"
                ),
            )
        ])

    if bot_configuration_service.has_override(key) and not is_read_only:
        rows.append([
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_RESET", "♻️ Reset"),
                callback_data=(
                    f"botcfg_reset:{group_key}:{category_page}:{settings_page}:{callback_token}"
                ),
            )
        ])

    if is_read_only:
        rows.append([
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CFG_BTN_READ_ONLY", "🔒 Read only"),
                callback_data="botcfg_group:noop",
            )
        ])

    rows.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data=(
                f"botcfg_cat:{group_key}:{definition.category_key}:{category_page}:{settings_page}"
            ),
        )
    ])

    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def _render_setting_text(key: str, language: str = "en") -> str:
    texts = get_texts(language)
    summary = bot_configuration_service.get_setting_summary(key)
    guidance = bot_configuration_service.get_setting_guidance(key)

    definition = bot_configuration_service.get_definition(key)

    description = guidance.get("description") or "—"
    format_hint = guidance.get("format") or "—"
    example = guidance.get("example") or "—"
    warning = guidance.get("warning") or "—"
    dependencies = guidance.get("dependencies") or "—"
    type_label = guidance.get("type") or summary.get("type") or definition.type_label

    yes_label = texts.t("YES", "Yes")
    no_label = texts.t("NO", "No")

    lines = [
        f"🧩 <b>{summary['name']}</b>",
        texts.t("ADMIN_CFG_SETTING_KEY", "🔑 Key: <code>{key}</code>").format(key=summary['key']),
        texts.t("ADMIN_CFG_SETTING_CATEGORY", "📁 Category: {label}").format(label=summary['category_label']),
        texts.t("ADMIN_CFG_SETTING_TYPE", "📝 Type: {type}").format(type=type_label),
        texts.t("ADMIN_CFG_SETTING_CURRENT", "📌 Current: {value}").format(value=summary['current']),
    ]

    original_value = summary.get("original")
    if original_value not in {None, ""}:
        lines.append(texts.t("ADMIN_CFG_SETTING_DEFAULT", "📦 Default: {value}").format(value=original_value))

    override_status = yes_label if summary['has_override'] else no_label
    lines.append(texts.t("ADMIN_CFG_SETTING_OVERRIDDEN", "✳️ Overridden: {status}").format(status=override_status))

    if summary.get("is_read_only"):
        lines.append(texts.t("ADMIN_CFG_SETTING_READ_ONLY_MODE", "🔒 Mode: Read only (managed automatically)"))

    lines.append("")
    if description:
        lines.append(texts.t("ADMIN_CFG_SETTING_DESCRIPTION", "📘 Description: {desc}").format(desc=description))
    if format_hint:
        lines.append(texts.t("ADMIN_CFG_SETTING_FORMAT", "📐 Format: {format}").format(format=format_hint))
    if example:
        lines.append(texts.t("ADMIN_CFG_SETTING_EXAMPLE", "💡 Example: {example}").format(example=example))
    if warning:
        lines.append(texts.t("ADMIN_CFG_SETTING_IMPORTANT", "⚠️ Important: {warning}").format(warning=warning))
    if dependencies:
        lines.append(texts.t("ADMIN_CFG_SETTING_RELATED", "🔗 Related: {deps}").format(deps=dependencies))

    choices = bot_configuration_service.get_choice_options(key)
    if choices:
        current_raw = bot_configuration_service.get_current_value(key)
        lines.append("")
        lines.append(texts.t("ADMIN_CFG_SETTING_AVAILABLE_VALUES", "📋 Available values:"))
        for option in choices:
            marker = "✅" if current_raw == option.value else "•"
            value_display = bot_configuration_service.format_value_human(key, option.value)
            opt_description = option.description or ""
            base_line = f"{marker} {option.label} — <code>{value_display}</code>"
            if opt_description:
                base_line += f"\n└ {opt_description}"
            lines.append(base_line)

    return "\n".join(lines)


@admin_required
@error_handler
async def show_bot_config_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    await state.clear()
    keyboard = _build_groups_keyboard(db_user.language)
    overview = _render_dashboard_overview(db_user.language)
    await callback.message.edit_text(
        overview,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@admin_required
@error_handler
async def show_bot_config_group(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    group_key, page = _parse_group_payload(callback.data)
    grouped = _get_grouped_categories(db_user.language)
    group_lookup = {key: (title, items) for key, title, items in grouped}

    if group_key not in group_lookup:
        await callback.answer(texts.t("ADMIN_CFG_GROUP_UNAVAILABLE", "This group is no longer available"), show_alert=True)
        return

    group_title, items = group_lookup[group_key]
    keyboard = _build_categories_keyboard(group_key, group_title, items, page, db_user.language)
    status_icon, status_text = _get_group_status(group_key, db_user.language)
    description = _get_group_description(group_key, db_user.language)
    icon = _get_group_icon(group_key)
    raw_title = str(group_title).strip()
    clean_title = raw_title
    if icon and raw_title.startswith(icon):
        clean_title = raw_title[len(icon) :].strip()
    elif " " in raw_title:
        possible_icon, remainder = raw_title.split(" ", 1)
        if possible_icon:
            icon = possible_icon
            clean_title = remainder.strip()
    lines = [f"{icon} <b>{clean_title}</b>"]
    if status_text:
        lines.append(texts.t("ADMIN_CFG_STATUS_LABEL", "Status: {icon} {text}").format(icon=status_icon, text=status_text))
    lines.append(f"🏠 → {clean_title}")
    if description:
        lines.append("")
        lines.append(description)
    lines.append("")
    lines.append(texts.t("ADMIN_CFG_GROUP_CATEGORIES", "📂 Group categories:"))
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@admin_required
@error_handler
async def show_bot_config_category(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    group_key, category_key, category_page, settings_page = _parse_category_payload(
        callback.data
    )
    definitions = bot_configuration_service.get_settings_for_category(category_key)

    if not definitions:
        await callback.answer(texts.t("ADMIN_CFG_CATEGORY_EMPTY", "No settings in this category yet"), show_alert=True)
        return

    category_label = definitions[0].category_label
    category_description = bot_configuration_service.get_category_description(category_key)
    group_meta = _get_group_meta(group_key)
    group_title = _get_group_title(group_key, db_user.language)
    group_icon = _get_group_icon(group_key)
    raw_group_title = group_title.strip()
    if group_icon and raw_group_title.startswith(group_icon):
        group_plain_title = raw_group_title[len(group_icon) :].strip()
    elif " " in raw_group_title:
        possible_icon, remainder = raw_group_title.split(" ", 1)
        group_plain_title = remainder.strip()
        if possible_icon:
            group_icon = possible_icon
    else:
        group_plain_title = raw_group_title
    keyboard = _build_settings_keyboard(
        category_key,
        group_key,
        category_page,
        db_user.language,
        settings_page,
    )
    text_lines = [
        f"🗂 <b>{category_label}</b>",
        f"🏠 → {group_plain_title} → {category_label}",
    ]
    if category_description:
        text_lines.append(category_description)
    text_lines.append("")
    text_lines.append(texts.t("ADMIN_CFG_CATEGORY_SETTINGS_LIST", "📋 Category settings list:"))
    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@admin_required
@error_handler
async def show_simple_subscription_squad_selector(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    parts = callback.data.split(":", 5)
    group_key = parts[1] if len(parts) > 1 else CATEGORY_FALLBACK_KEY
    try:
        category_page = max(1, int(parts[2])) if len(parts) > 2 else 1
    except ValueError:
        category_page = 1
    try:
        settings_page = max(1, int(parts[3])) if len(parts) > 3 else 1
    except ValueError:
        settings_page = 1
    token = parts[4] if len(parts) > 4 else ""

    try:
        key = bot_configuration_service.resolve_callback_token(token)
    except KeyError:
        await callback.answer(texts.t("ADMIN_CFG_SETTING_UNAVAILABLE", "This setting is no longer available"), show_alert=True)
        return

    if key != "SIMPLE_SUBSCRIPTION_SQUAD_UUID":
        await callback.answer(texts.t("ADMIN_CFG_SETTING_UNAVAILABLE", "This setting is no longer available"), show_alert=True)
        return

    try:
        page = max(1, int(parts[5])) if len(parts) > 5 else 1
    except ValueError:
        page = 1

    limit = SIMPLE_SUBSCRIPTION_SQUADS_PAGE_SIZE
    squads, total_count = await get_all_server_squads(
        db,
        available_only=False,
        page=page,
        limit=limit,
    )

    total_count = total_count or 0
    total_pages = max(1, math.ceil(total_count / limit)) if total_count else 1
    if total_count and page > total_pages:
        page = total_pages
        squads, total_count = await get_all_server_squads(
            db,
            available_only=False,
            page=page,
            limit=limit,
        )

    current_uuid = bot_configuration_service.get_current_value(key) or ""
    current_display = texts.t("ADMIN_CFG_SQUAD_ANY_AVAILABLE", "Any available")

    if current_uuid:
        selected_server = next((srv for srv in squads if srv.squad_uuid == current_uuid), None)
        if not selected_server:
            selected_server = await get_server_squad_by_uuid(db, current_uuid)
        if selected_server:
            current_display = selected_server.display_name
        else:
            current_display = current_uuid

    lines = [
        texts.t("ADMIN_CFG_SELECT_SQUAD_TITLE", "🌍 <b>Select squad for simple purchase</b>"),
        "",
        texts.t("ADMIN_CFG_CURRENT_SELECTION", "Current selection: {selection}").format(selection=html.escape(current_display)) if current_display else texts.t("ADMIN_CFG_CURRENT_SELECTION", "Current selection: —"),
        "",
    ]

    if total_count == 0:
        lines.append(texts.t("ADMIN_CFG_NO_SERVERS_FOUND", "❌ No available servers found."))
    else:
        lines.append(texts.t("ADMIN_CFG_SELECT_SERVER_HINT", "Select a server from the list below."))
        if total_pages > 1:
            lines.append(texts.t("ADMIN_CFG_PAGE_INFO", "Page {page}/{total}").format(page=page, total=total_pages))

    text = "\n".join(lines)

    keyboard_rows: List[List[types.InlineKeyboardButton]] = []

    for server in squads:
        status_icon = (
            "✅" if server.squad_uuid == current_uuid else ("🟢" if server.is_available else "🔒")
        )
        label_parts = [status_icon, server.display_name]
        if server.country_code:
            label_parts.append(f"({server.country_code.upper()})")
        if isinstance(server.price_kopeks, int) and server.price_kopeks > 0:
            try:
                label_parts.append(f"— {settings.format_price(server.price_kopeks)}")
            except Exception:
                pass
        label = " ".join(label_parts)

        keyboard_rows.append([
            types.InlineKeyboardButton(
                text=label,
                callback_data=(
                    f"botcfg_simple_squad_select:{group_key}:{category_page}:{settings_page}:{token}:{server.id}:{page}"
                ),
            )
        ])

    if total_pages > 1:
        nav_row: List[types.InlineKeyboardButton] = []
        if page > 1:
            nav_row.append(
                types.InlineKeyboardButton(
                    text="⬅️",
                    callback_data=(
                        f"botcfg_simple_squad:{group_key}:{category_page}:{settings_page}:{token}:{page - 1}"
                    ),
                )
            )
        if page < total_pages:
            nav_row.append(
                types.InlineKeyboardButton(
                    text="➡️",
                    callback_data=(
                        f"botcfg_simple_squad:{group_key}:{category_page}:{settings_page}:{token}:{page + 1}"
                    ),
                )
            )
        if nav_row:
            keyboard_rows.append(nav_row)

    keyboard_rows.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data=(
                f"botcfg_setting:{group_key}:{category_page}:{settings_page}:{token}"
            ),
        )
    ])

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_required
@error_handler
async def select_simple_subscription_squad(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    parts = callback.data.split(":", 6)
    group_key = parts[1] if len(parts) > 1 else CATEGORY_FALLBACK_KEY
    try:
        category_page = max(1, int(parts[2])) if len(parts) > 2 else 1
    except ValueError:
        category_page = 1
    try:
        settings_page = max(1, int(parts[3])) if len(parts) > 3 else 1
    except ValueError:
        settings_page = 1
    token = parts[4] if len(parts) > 4 else ""
    try:
        server_id = int(parts[5]) if len(parts) > 5 else None
    except ValueError:
        server_id = None

    if server_id is None:
        await callback.answer(texts.t("ADMIN_CFG_SERVER_NOT_IDENTIFIED", "Could not identify server"), show_alert=True)
        return

    try:
        key = bot_configuration_service.resolve_callback_token(token)
    except KeyError:
        await callback.answer(texts.t("ADMIN_CFG_SETTING_UNAVAILABLE", "This setting is no longer available"), show_alert=True)
        return

    if bot_configuration_service.is_read_only(key):
        await callback.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY", "This setting is read-only"), show_alert=True)
        return

    server = await get_server_squad_by_id(db, server_id)
    if not server:
        await callback.answer(texts.t("ADMIN_CFG_SERVER_NOT_FOUND", "Server not found"), show_alert=True)
        return

    try:
        await bot_configuration_service.set_value(db, key, server.squad_uuid)
    except ReadOnlySettingError:
        await callback.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY", "This setting is read-only"), show_alert=True)
        return

    await db.commit()

    text = _render_setting_text(key, db_user.language)
    keyboard = _build_setting_keyboard(key, group_key, category_page, settings_page, db_user.language)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await _store_setting_context(
        state,
        key=key,
        group_key=group_key,
        category_page=category_page,
        settings_page=settings_page,
    )
    await callback.answer(texts.t("ADMIN_CFG_SQUAD_SELECTED", "Squad selected"))


@admin_required
@error_handler
async def test_remnawave_connection(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    parts = callback.data.split(":", 5)
    group_key = parts[1] if len(parts) > 1 else CATEGORY_FALLBACK_KEY
    category_key = parts[2] if len(parts) > 2 else "REMNAWAVE"

    try:
        category_page = max(1, int(parts[3])) if len(parts) > 3 else 1
    except ValueError:
        category_page = 1

    try:
        settings_page = max(1, int(parts[4])) if len(parts) > 4 else 1
    except ValueError:
        settings_page = 1

    service = RemnaWaveService()
    result = await service.test_api_connection()

    status = result.get("status")
    message: str

    if status == "connected":
        message = texts.t("ADMIN_CFG_CONNECTION_SUCCESS", "✅ Connection successful")
    elif status == "not_configured":
        message = f"⚠️ {result.get('message', texts.t('ADMIN_CFG_API_NOT_CONFIGURED', 'RemnaWave API not configured'))}"
    else:
        base_message = result.get("message", texts.t("ADMIN_CFG_CONNECTION_ERROR", "Connection error"))
        status_code = result.get("status_code")
        if status_code:
            message = f"❌ {base_message} (HTTP {status_code})"
        else:
            message = f"❌ {base_message}"

    definitions = bot_configuration_service.get_settings_for_category(category_key)
    if definitions:
        keyboard = _build_settings_keyboard(
            category_key,
            group_key,
            category_page,
            db_user.language,
            settings_page,
        )
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        except Exception:
            pass

    await callback.answer(message, show_alert=True)


@admin_required
@error_handler
async def test_payment_provider(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    parts = callback.data.split(":", 6)
    method = parts[1] if len(parts) > 1 else ""
    group_key = parts[2] if len(parts) > 2 else CATEGORY_FALLBACK_KEY
    category_key = parts[3] if len(parts) > 3 else "PAYMENT"

    try:
        category_page = max(1, int(parts[4])) if len(parts) > 4 else 1
    except ValueError:
        category_page = 1

    try:
        settings_page = max(1, int(parts[5])) if len(parts) > 5 else 1
    except ValueError:
        settings_page = 1

    language = db_user.language
    texts = get_texts(language)
    payment_service = PaymentService(callback.bot)

    message_text: str

    async def _refresh_markup() -> None:
        definitions = bot_configuration_service.get_settings_for_category(category_key)
        if definitions:
            keyboard = _build_settings_keyboard(
                category_key,
                group_key,
                category_page,
                language,
                settings_page,
            )
            try:
                await callback.message.edit_reply_markup(reply_markup=keyboard)
            except Exception:
                pass

    if method == "yookassa":
        if not settings.is_yookassa_enabled():
            await callback.answer(texts.t("ADMIN_CFG_YOOKASSA_DISABLED", "❌ YooKassa is disabled"), show_alert=True)
            return

        amount_kopeks = 10 * 100
        description = settings.get_balance_payment_description(amount_kopeks)
        payment_result = await payment_service.create_yookassa_payment(
            db=db,
            user_id=db_user.id,
            amount_kopeks=amount_kopeks,
            description=f"Test payment (admin): {description}",
            metadata={
                "user_telegram_id": str(db_user.telegram_id),
                "purpose": "admin_test_payment",
                "provider": "yookassa",
            },
        )

        if not payment_result or not payment_result.get("confirmation_url"):
            await callback.answer(texts.t("ADMIN_CFG_YOOKASSA_CREATE_FAILED", "❌ Failed to create YooKassa test payment"), show_alert=True)
            await _refresh_markup()
            return

        confirmation_url = payment_result["confirmation_url"]
        message_text = texts.t(
            "ADMIN_CFG_TEST_PAYMENT_YOOKASSA",
            "🧪 <b>YooKassa Test Payment</b>\n\n💰 Amount: {amount}\n🆔 ID: {payment_id}"
        ).format(amount=texts.format_price(amount_kopeks), payment_id=payment_result['yookassa_payment_id'])
        reply_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_CFG_BTN_PAY_CARD", "💳 Pay by card"),
                        url=confirmation_url,
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_CFG_BTN_CHECK_STATUS", "📊 Check status"),
                        callback_data=f"check_yookassa_{payment_result['local_payment_id']}",
                    )
                ],
            ]
        )
        await callback.message.answer(message_text, reply_markup=reply_markup, parse_mode="HTML")
        await callback.answer(texts.t("ADMIN_CFG_PAYMENT_LINK_SENT", "✅ Payment link sent"), show_alert=True)
        await _refresh_markup()
        return

    if method == "tribute":
        await callback.answer(
            "❌ Tribute payments are not available in this build",
            show_alert=True,
        )
        await _refresh_markup()
        return

    if method == "mulenpay":
        mulenpay_name = settings.get_mulenpay_display_name()
        mulenpay_name_html = settings.get_mulenpay_display_name_html()
        if not settings.is_mulenpay_enabled():
            await callback.answer(
                texts.t("ADMIN_CFG_PROVIDER_DISABLED", "❌ {provider} is disabled").format(provider=mulenpay_name),
                show_alert=True,
            )
            return

        amount_kopeks = 1 * 100
        payment_result = await payment_service.create_mulenpay_payment(
            db=db,
            user_id=db_user.id,
            amount_kopeks=amount_kopeks,
            description=f"Test payment {mulenpay_name} (admin)",
            language=language,
        )

        if not payment_result or not payment_result.get("payment_url"):
            await callback.answer(
                texts.t("ADMIN_CFG_PAYMENT_CREATE_FAILED", "❌ Failed to create payment {provider}").format(provider=mulenpay_name),
                show_alert=True,
            )
            await _refresh_markup()
            return

        payment_url = payment_result["payment_url"]
        message_text = texts.t(
            "ADMIN_CFG_TEST_PAYMENT_GENERIC",
            "🧪 <b>{provider} Test Payment</b>\n\n💰 Amount: {amount}\n🆔 ID: {payment_id}"
        ).format(provider=mulenpay_name_html, amount=texts.format_price(amount_kopeks), payment_id=payment_result['mulen_payment_id'])
        reply_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_CFG_BTN_GO_TO_PAY", "💳 Go to payment"),
                        url=payment_url,
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_CFG_BTN_CHECK_STATUS", "📊 Check status"),
                        callback_data=f"check_mulenpay_{payment_result['local_payment_id']}",
                    )
                ],
            ]
        )
        await callback.message.answer(message_text, reply_markup=reply_markup, parse_mode="HTML")
        await callback.answer(texts.t("ADMIN_CFG_PAYMENT_LINK_SENT", "✅ Payment link sent"), show_alert=True)
        await _refresh_markup()
        return

    if method == "pal24":
        if not settings.is_pal24_enabled():
            await callback.answer(texts.t("ADMIN_CFG_PAL24_DISABLED", "❌ PayPalych is disabled"), show_alert=True)
            return

        amount_kopeks = 10 * 100
        payment_result = await payment_service.create_pal24_payment(
            db=db,
            user_id=db_user.id,
            amount_kopeks=amount_kopeks,
            description="Test payment PayPalych (admin)",
            language=language or "ru",
        )

        if not payment_result:
            await callback.answer(texts.t("ADMIN_CFG_PAL24_CREATE_FAILED", "❌ Failed to create PayPalych payment"), show_alert=True)
            await _refresh_markup()
            return

        sbp_url = (
            payment_result.get("sbp_url")
            or payment_result.get("transfer_url")
            or payment_result.get("link_url")
        )
        card_url = payment_result.get("card_url")
        fallback_url = payment_result.get("link_page_url") or payment_result.get("link_url")

        if not (sbp_url or card_url or fallback_url):
            await callback.answer(texts.t("ADMIN_CFG_PAL24_CREATE_FAILED", "❌ Failed to create PayPalych payment"), show_alert=True)
            await _refresh_markup()
            return

        if not sbp_url:
            sbp_url = fallback_url

        default_sbp_text = texts.t(
            "PAL24_SBP_PAY_BUTTON",
            "🏦 Pay via PayPalych (SBP)",
        )
        sbp_button_text = settings.get_pal24_sbp_button_text(default_sbp_text)

        default_card_text = texts.t(
            "PAL24_CARD_PAY_BUTTON",
            "💳 Pay by bank card (PayPalych)",
        )
        card_button_text = settings.get_pal24_card_button_text(default_card_text)

        pay_rows: list[list[types.InlineKeyboardButton]] = []
        if sbp_url:
            pay_rows.append([
                types.InlineKeyboardButton(
                    text=sbp_button_text,
                    url=sbp_url,
                )
            ])

        if card_url and card_url != sbp_url:
            pay_rows.append([
                types.InlineKeyboardButton(
                    text=card_button_text,
                    url=card_url,
                )
            ])

        if not pay_rows and fallback_url:
            pay_rows.append([
                types.InlineKeyboardButton(
                    text=sbp_button_text,
                    url=fallback_url,
                )
            ])

        message_text = texts.t(
            "ADMIN_CFG_TEST_PAYMENT_PAL24",
            "🧪 <b>PayPalych Test Payment</b>\n\n💰 Amount: {amount}\n🆔 Bill ID: {bill_id}"
        ).format(amount=texts.format_price(amount_kopeks), bill_id=payment_result['bill_id'])
        keyboard_rows = pay_rows + [
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CFG_BTN_CHECK_STATUS", "📊 Check status"),
                    callback_data=f"check_pal24_{payment_result['local_payment_id']}",
                )
            ],
        ]

        reply_markup = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
        await callback.message.answer(message_text, reply_markup=reply_markup, parse_mode="HTML")
        await callback.answer(texts.t("ADMIN_CFG_PAYMENT_LINK_SENT", "✅ Payment link sent"), show_alert=True)
        await _refresh_markup()
        return

    if method == "stars":
        if not settings.TELEGRAM_STARS_ENABLED:
            await callback.answer(texts.t("ADMIN_CFG_STARS_DISABLED", "❌ Telegram Stars is disabled"), show_alert=True)
            return

        stars_rate = settings.get_stars_rate()
        amount_kopeks = max(1, int(round(stars_rate * 100)))
        payload = f"admin_stars_test_{db_user.id}_{int(time.time())}"
        try:
            invoice_link = await payment_service.create_stars_invoice(
                amount_kopeks=amount_kopeks,
                description="Test payment Telegram Stars (admin)",
                payload=payload,
            )
        except Exception:
            invoice_link = None

        if not invoice_link:
            await callback.answer(texts.t("ADMIN_CFG_STARS_CREATE_FAILED", "❌ Failed to create Telegram Stars payment"), show_alert=True)
            await _refresh_markup()
            return

        stars_amount = TelegramStarsService.calculate_stars_from_rubles(amount_kopeks / 100)
        message_text = texts.t(
            "ADMIN_CFG_TEST_PAYMENT_STARS",
            "🧪 <b>Telegram Stars Test Payment</b>\n\n💰 Amount: {amount}\n⭐ To pay: {stars}"
        ).format(amount=texts.format_price(amount_kopeks), stars=stars_amount)
        reply_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("PAYMENT_TELEGRAM_STARS", "⭐ Open invoice"),
                        url=invoice_link,
                    )
                ]
            ]
        )
        await callback.message.answer(message_text, reply_markup=reply_markup, parse_mode="HTML")
        await callback.answer(texts.t("ADMIN_CFG_PAYMENT_LINK_SENT", "✅ Payment link sent"), show_alert=True)
        await _refresh_markup()
        return

    if method == "cryptobot":
        if not settings.is_cryptobot_enabled():
            await callback.answer(texts.t("ADMIN_CFG_CRYPTOBOT_DISABLED", "❌ CryptoBot is disabled"), show_alert=True)
            return

        amount_rubles = 100.0
        try:
            current_rate = await currency_converter.get_usd_to_rub_rate()
        except Exception:
            current_rate = None

        if not current_rate or current_rate <= 0:
            current_rate = 100.0

        amount_usd = round(amount_rubles / current_rate, 2)
        if amount_usd < 1:
            amount_usd = 1.0

        payment_result = await payment_service.create_cryptobot_payment(
            db=db,
            user_id=db_user.id,
            amount_usd=amount_usd,
            asset=settings.CRYPTOBOT_DEFAULT_ASSET,
            description=f"Test payment CryptoBot {amount_rubles:.0f} RUB ({amount_usd:.2f} USD)",
            payload=f"admin_cryptobot_test_{db_user.id}_{int(time.time())}",
        )

        if not payment_result:
            await callback.answer(texts.t("ADMIN_CFG_CRYPTOBOT_CREATE_FAILED", "❌ Failed to create CryptoBot payment"), show_alert=True)
            await _refresh_markup()
            return

        payment_url = (
            payment_result.get("bot_invoice_url")
            or payment_result.get("mini_app_invoice_url")
            or payment_result.get("web_app_invoice_url")
        )

        if not payment_url:
            await callback.answer(texts.t("ADMIN_CFG_CRYPTOBOT_URL_FAILED", "❌ Failed to get CryptoBot payment link"), show_alert=True)
            await _refresh_markup()
            return

        amount_kopeks = int(amount_rubles * 100)
        message_text = texts.t(
            "ADMIN_CFG_TEST_PAYMENT_CRYPTOBOT",
            "🧪 <b>CryptoBot Test Payment</b>\n\n💰 Amount to credit: {amount}\n💵 To pay: {usd} USD\n🪙 Asset: {asset}"
        ).format(amount=texts.format_price(amount_kopeks), usd=f"{amount_usd:.2f}", asset=payment_result['asset'])
        reply_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(text=texts.t("ADMIN_CFG_BTN_OPEN_INVOICE", "🪙 Open invoice"), url=payment_url)
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_CFG_BTN_CHECK_STATUS", "📊 Check status"),
                        callback_data=f"check_cryptobot_{payment_result['local_payment_id']}",
                    )
                ],
            ]
        )
        await callback.message.answer(message_text, reply_markup=reply_markup, parse_mode="HTML")
        await callback.answer(texts.t("ADMIN_CFG_PAYMENT_LINK_SENT", "✅ Payment link sent"), show_alert=True)
        await _refresh_markup()
        return

    await callback.answer(texts.t("ADMIN_CFG_UNKNOWN_PAYMENT_METHOD", "❌ Unknown payment test method"), show_alert=True)
    await _refresh_markup()


@admin_required
@error_handler
async def show_bot_config_setting(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    parts = callback.data.split(":", 4)
    group_key = parts[1] if len(parts) > 1 else CATEGORY_FALLBACK_KEY
    try:
        category_page = max(1, int(parts[2])) if len(parts) > 2 else 1
    except ValueError:
        category_page = 1
    try:
        settings_page = max(1, int(parts[3])) if len(parts) > 3 else 1
    except ValueError:
        settings_page = 1
    texts = get_texts(db_user.language)
    token = parts[4] if len(parts) > 4 else ""
    try:
        key = bot_configuration_service.resolve_callback_token(token)
    except KeyError:
        await callback.answer(texts.t("ADMIN_CFG_SETTING_UNAVAILABLE", "This setting is no longer available"), show_alert=True)
        return
    text = _render_setting_text(key, db_user.language)
    keyboard = _build_setting_keyboard(key, group_key, category_page, settings_page, db_user.language)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await _store_setting_context(
        state,
        key=key,
        group_key=group_key,
        category_page=category_page,
        settings_page=settings_page,
    )
    await callback.answer()


@admin_required
@error_handler
async def start_edit_setting(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    parts = callback.data.split(":", 4)
    group_key = parts[1] if len(parts) > 1 else CATEGORY_FALLBACK_KEY
    try:
        category_page = max(1, int(parts[2])) if len(parts) > 2 else 1
    except ValueError:
        category_page = 1
    try:
        settings_page = max(1, int(parts[3])) if len(parts) > 3 else 1
    except ValueError:
        settings_page = 1
    token = parts[4] if len(parts) > 4 else ""
    try:
        key = bot_configuration_service.resolve_callback_token(token)
    except KeyError:
        await callback.answer(texts.t("ADMIN_CFG_SETTING_UNAVAILABLE", "This setting is no longer available"), show_alert=True)
        return
    if bot_configuration_service.is_read_only(key):
        await callback.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY", "This setting is read-only"), show_alert=True)
        return
    definition = bot_configuration_service.get_definition(key)

    summary = bot_configuration_service.get_setting_summary(key)

    instructions = [
        texts.t("ADMIN_CFG_EDIT_TITLE", "✏️ <b>Edit setting</b>"),
        texts.t("ADMIN_CFG_EDIT_NAME", "Name: {name}").format(name=summary['name']),
        texts.t("ADMIN_CFG_EDIT_KEY", "Key: <code>{key}</code>").format(key=summary['key']),
        texts.t("ADMIN_CFG_EDIT_TYPE", "Type: {type}").format(type=summary['type']),
        texts.t("ADMIN_CFG_EDIT_CURRENT", "Current value: {value}").format(value=summary['current']),
        "\n" + texts.t("ADMIN_CFG_EDIT_SEND_NEW", "Send the new value as a message."),
    ]

    if definition.is_optional:
        instructions.append(texts.t("ADMIN_CFG_EDIT_OPTIONAL_HINT", "Send 'none' or leave empty to reset to default."))

    instructions.append(texts.t("ADMIN_CFG_EDIT_CANCEL_HINT", "To cancel, send 'cancel'."))

    await callback.message.edit_text(
        "\n".join(instructions),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.BACK,
                        callback_data=(
                            f"botcfg_setting:{group_key}:{category_page}:{settings_page}:{token}"
                        ),
                    )
                ]
            ]
        ),
    )

    await _store_setting_context(
        state,
        key=key,
        group_key=group_key,
        category_page=category_page,
        settings_page=settings_page,
    )
    await state.set_state(BotConfigStates.waiting_for_value)
    await callback.answer()


@admin_required
@error_handler
async def handle_edit_setting(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    key = data.get("setting_key")
    group_key = data.get("setting_group_key", CATEGORY_FALLBACK_KEY)
    category_page = data.get("setting_category_page", 1)
    settings_page = data.get("setting_settings_page", 1)

    if not key:
        await message.answer(texts.t("ADMIN_CFG_COULD_NOT_IDENTIFY_SETTING", "Could not identify the setting to edit. Please try again."))
        await state.clear()
        return

    if bot_configuration_service.is_read_only(key):
        await message.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY_MSG", "⚠️ This setting is read-only."))
        await state.clear()
        return

    try:
        value = bot_configuration_service.parse_user_value(key, message.text or "")
    except ValueError as error:
        await message.answer(f"⚠️ {error}")
        return

    try:
        await bot_configuration_service.set_value(db, key, value)
    except ReadOnlySettingError:
        await message.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY_MSG", "⚠️ This setting is read-only."))
        await state.clear()
        return
    await db.commit()

    text = _render_setting_text(key, db_user.language)
    keyboard = _build_setting_keyboard(key, group_key, category_page, settings_page, db_user.language)
    await message.answer(texts.t("ADMIN_CFG_SETTING_UPDATED", "✅ Setting updated"))
    await message.answer(text, reply_markup=keyboard)
    await state.clear()
    await _store_setting_context(
        state,
        key=key,
        group_key=group_key,
        category_page=category_page,
        settings_page=settings_page,
    )


@admin_required
@error_handler
async def handle_direct_setting_input(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()

    key = data.get("setting_key")
    group_key = data.get("setting_group_key", CATEGORY_FALLBACK_KEY)
    category_page = int(data.get("setting_category_page", 1) or 1)
    settings_page = int(data.get("setting_settings_page", 1) or 1)

    if not key:
        return

    if bot_configuration_service.is_read_only(key):
        await message.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY_MSG", "⚠️ This setting is read-only."))
        await state.clear()
        return

    try:
        value = bot_configuration_service.parse_user_value(key, message.text or "")
    except ValueError as error:
        await message.answer(f"⚠️ {error}")
        return

    try:
        await bot_configuration_service.set_value(db, key, value)
    except ReadOnlySettingError:
        await message.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY_MSG", "⚠️ This setting is read-only."))
        await state.clear()
        return
    await db.commit()

    text = _render_setting_text(key, db_user.language)
    keyboard = _build_setting_keyboard(key, group_key, category_page, settings_page, db_user.language)
    await message.answer(texts.t("ADMIN_CFG_SETTING_UPDATED", "✅ Setting updated"))
    await message.answer(text, reply_markup=keyboard)

    await state.clear()
    await _store_setting_context(
        state,
        key=key,
        group_key=group_key,
        category_page=category_page,
        settings_page=settings_page,
    )


@admin_required
@error_handler
async def reset_setting(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    parts = callback.data.split(":", 4)
    group_key = parts[1] if len(parts) > 1 else CATEGORY_FALLBACK_KEY
    try:
        category_page = max(1, int(parts[2])) if len(parts) > 2 else 1
    except ValueError:
        category_page = 1
    try:
        settings_page = max(1, int(parts[3])) if len(parts) > 3 else 1
    except ValueError:
        settings_page = 1
    token = parts[4] if len(parts) > 4 else ""
    try:
        key = bot_configuration_service.resolve_callback_token(token)
    except KeyError:
        await callback.answer(texts.t("ADMIN_CFG_SETTING_UNAVAILABLE", "This setting is no longer available"), show_alert=True)
        return
    if bot_configuration_service.is_read_only(key):
        await callback.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY", "This setting is read-only"), show_alert=True)
        return
    try:
        await bot_configuration_service.reset_value(db, key)
    except ReadOnlySettingError:
        await callback.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY", "This setting is read-only"), show_alert=True)
        return
    await db.commit()

    text = _render_setting_text(key, db_user.language)
    keyboard = _build_setting_keyboard(key, group_key, category_page, settings_page, db_user.language)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await _store_setting_context(
        state,
        key=key,
        group_key=group_key,
        category_page=category_page,
        settings_page=settings_page,
    )
    await callback.answer(texts.t("ADMIN_CFG_RESET_TO_DEFAULT", "Reset to default"))


@admin_required
@error_handler
async def toggle_setting(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    parts = callback.data.split(":", 4)
    group_key = parts[1] if len(parts) > 1 else CATEGORY_FALLBACK_KEY
    try:
        category_page = max(1, int(parts[2])) if len(parts) > 2 else 1
    except ValueError:
        category_page = 1
    try:
        settings_page = max(1, int(parts[3])) if len(parts) > 3 else 1
    except ValueError:
        settings_page = 1
    token = parts[4] if len(parts) > 4 else ""
    try:
        key = bot_configuration_service.resolve_callback_token(token)
    except KeyError:
        await callback.answer(texts.t("ADMIN_CFG_SETTING_UNAVAILABLE", "This setting is no longer available"), show_alert=True)
        return
    if bot_configuration_service.is_read_only(key):
        await callback.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY", "This setting is read-only"), show_alert=True)
        return
    current = bot_configuration_service.get_current_value(key)
    new_value = not bool(current)
    try:
        await bot_configuration_service.set_value(db, key, new_value)
    except ReadOnlySettingError:
        await callback.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY", "This setting is read-only"), show_alert=True)
        return
    await db.commit()

    text = _render_setting_text(key, db_user.language)
    keyboard = _build_setting_keyboard(key, group_key, category_page, settings_page, db_user.language)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await _store_setting_context(
        state,
        key=key,
        group_key=group_key,
        category_page=category_page,
        settings_page=settings_page,
    )
    await callback.answer(texts.t("ADMIN_CFG_UPDATED", "Updated"))


@admin_required
@error_handler
async def apply_setting_choice(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    parts = callback.data.split(":", 5)
    group_key = parts[1] if len(parts) > 1 else CATEGORY_FALLBACK_KEY
    try:
        category_page = max(1, int(parts[2])) if len(parts) > 2 else 1
    except ValueError:
        category_page = 1
    try:
        settings_page = max(1, int(parts[3])) if len(parts) > 3 else 1
    except ValueError:
        settings_page = 1
    token = parts[4] if len(parts) > 4 else ""
    choice_token = parts[5] if len(parts) > 5 else ""

    try:
        key = bot_configuration_service.resolve_callback_token(token)
    except KeyError:
        await callback.answer(texts.t("ADMIN_CFG_SETTING_UNAVAILABLE", "This setting is no longer available"), show_alert=True)
        return
    if bot_configuration_service.is_read_only(key):
        await callback.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY", "This setting is read-only"), show_alert=True)
        return

    try:
        value = bot_configuration_service.resolve_choice_token(key, choice_token)
    except KeyError:
        await callback.answer(texts.t("ADMIN_CFG_VALUE_UNAVAILABLE", "This value is no longer available"), show_alert=True)
        return

    try:
        await bot_configuration_service.set_value(db, key, value)
    except ReadOnlySettingError:
        await callback.answer(texts.t("ADMIN_CFG_SETTING_READ_ONLY", "This setting is read-only"), show_alert=True)
        return
    await db.commit()

    text = _render_setting_text(key, db_user.language)
    keyboard = _build_setting_keyboard(key, group_key, category_page, settings_page, db_user.language)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await _store_setting_context(
        state,
        key=key,
        group_key=group_key,
        category_page=category_page,
        settings_page=settings_page,
    )
    await callback.answer(texts.t("ADMIN_CFG_VALUE_UPDATED", "Value updated"))


def register_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(
        show_bot_config_menu,
        F.data == "admin_bot_config",
    )
    dp.callback_query.register(
        start_settings_search,
        F.data == "botcfg_action:search",
    )
    dp.callback_query.register(
        show_presets,
        F.data == "botcfg_action:presets",
    )
    dp.callback_query.register(
        apply_preset,
        F.data.startswith("botcfg_preset_apply:"),
    )
    dp.callback_query.register(
        preview_preset,
        F.data.startswith("botcfg_preset:") & (~F.data.startswith("botcfg_preset_apply:")),
    )
    dp.callback_query.register(
        export_settings,
        F.data == "botcfg_action:export",
    )
    dp.callback_query.register(
        start_import_settings,
        F.data == "botcfg_action:import",
    )
    dp.callback_query.register(
        show_settings_history,
        F.data == "botcfg_action:history",
    )
    dp.callback_query.register(
        show_help,
        F.data == "botcfg_action:help",
    )
    dp.callback_query.register(
        show_bot_config_group,
        F.data.startswith("botcfg_group:") & (~F.data.endswith(":noop")),
    )
    dp.callback_query.register(
        show_bot_config_category,
        F.data.startswith("botcfg_cat:"),
    )
    dp.callback_query.register(
        test_remnawave_connection,
        F.data.startswith("botcfg_test_remnawave:"),
    )
    dp.callback_query.register(
        test_payment_provider,
        F.data.startswith("botcfg_test_payment:"),
    )
    dp.callback_query.register(
        select_simple_subscription_squad,
        F.data.startswith("botcfg_simple_squad_select:"),
    )
    dp.callback_query.register(
        show_simple_subscription_squad_selector,
        F.data.startswith("botcfg_simple_squad:"),
    )
    dp.callback_query.register(
        show_bot_config_setting,
        F.data.startswith("botcfg_setting:"),
    )
    dp.callback_query.register(
        start_edit_setting,
        F.data.startswith("botcfg_edit:"),
    )
    dp.callback_query.register(
        reset_setting,
        F.data.startswith("botcfg_reset:"),
    )
    dp.callback_query.register(
        toggle_setting,
        F.data.startswith("botcfg_toggle:"),
    )
    dp.callback_query.register(
        apply_setting_choice,
        F.data.startswith("botcfg_choice:"),
    )
    dp.message.register(
        handle_direct_setting_input,
        StateFilter(None),
        F.text,
        BotConfigInputFilter(),
    )
    dp.message.register(
        handle_edit_setting,
        BotConfigStates.waiting_for_value,
    )
    dp.message.register(
        handle_search_query,
        BotConfigStates.waiting_for_search_query,
    )
    dp.message.register(
        handle_import_message,
        BotConfigStates.waiting_for_import_file,
    )
