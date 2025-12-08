import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, List, Tuple, Dict, Any

from aiogram import Bot, Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.localization.texts import get_texts
from app.services.system_settings_service import bot_configuration_service
from app.states import PricingStates
from app.utils.decorators import admin_required, error_handler

logger = logging.getLogger(__name__)


PriceItem = Tuple[str, str, int]


TRAFFIC_PACKAGE_FIELDS: Tuple[Tuple[int, str], ...] = (
    (5, "PRICE_TRAFFIC_5GB"),
    (10, "PRICE_TRAFFIC_10GB"),
    (25, "PRICE_TRAFFIC_25GB"),
    (50, "PRICE_TRAFFIC_50GB"),
    (100, "PRICE_TRAFFIC_100GB"),
    (250, "PRICE_TRAFFIC_250GB"),
    (500, "PRICE_TRAFFIC_500GB"),
    (1000, "PRICE_TRAFFIC_1000GB"),
    (0, "PRICE_TRAFFIC_UNLIMITED"),
)

TRAFFIC_PACKAGE_FIELD_MAP: Dict[int, str] = {gb: field for gb, field in TRAFFIC_PACKAGE_FIELDS}
TRAFFIC_PACKAGE_ORDER: Tuple[int, ...] = tuple(gb for gb, _ in TRAFFIC_PACKAGE_FIELDS)
TRAFFIC_PACKAGE_ORDER_INDEX: Dict[int, int] = {
    gb: index for index, gb in enumerate(TRAFFIC_PACKAGE_ORDER)
}


@dataclass(slots=True)
class ChoiceOption:
    value: Any
    label: str  # localization key
    default_label: str

    def get_label(self, texts: Any) -> str:
        return texts.t(self.label, self.default_label)


@dataclass(slots=True)
class SettingEntry:
    key: str
    section: str
    label: str  # localization key
    default_label: str
    action: str  # "input", "toggle", "price", "choice"
    description: str | None = None  # localization key
    default_description: str | None = None
    choices: Tuple[ChoiceOption, ...] | None = None

    def get_label(self, texts: Any) -> str:
        return texts.t(self.label, self.default_label)

    def get_description(self, texts: Any) -> str | None:
        if not self.description:
            return None
        return texts.t(self.description, self.default_description or "")


TRIAL_ENTRIES: Tuple[SettingEntry, ...] = (
    SettingEntry(
        key="TRIAL_DURATION_DAYS",
        section="trial",
        label="ADMIN_PRICING_TRIAL_DURATION_LABEL",
        default_label="⏳ Duration (days)",
        action="input",
    ),
    SettingEntry(
        key="TRIAL_TRAFFIC_LIMIT_GB",
        section="trial",
        label="ADMIN_PRICING_TRIAL_TRAFFIC_LIMIT_LABEL",
        default_label="📦 Traffic limit (GB)",
        action="input",
    ),
    SettingEntry(
        key="TRIAL_DEVICE_LIMIT",
        section="trial",
        label="ADMIN_PRICING_TRIAL_DEVICE_LIMIT_LABEL",
        default_label="📱 Device limit",
        action="input",
    ),
    SettingEntry(
        key="TRIAL_PAYMENT_ENABLED",
        section="trial",
        label="ADMIN_PRICING_TRIAL_PAYMENT_ENABLED_LABEL",
        default_label="💳 Paid activation",
        action="toggle",
        description="ADMIN_PRICING_TRIAL_PAYMENT_ENABLED_DESCRIPTION",
        default_description="When enabled, the configured amount is charged during trial activation.",
    ),
    SettingEntry(
        key="TRIAL_ACTIVATION_PRICE",
        section="trial",
        label="ADMIN_PRICING_TRIAL_ACTIVATION_PRICE_LABEL",
        default_label="💰 Activation price",
        action="price",
        description="ADMIN_PRICING_TRIAL_ACTIVATION_PRICE_DESCRIPTION",
        default_description="Amount in kopeks. 0 — free activation.",
    ),
    SettingEntry(
        key="TRIAL_ADD_REMAINING_DAYS_TO_PAID",
        section="trial",
        label="ADMIN_PRICING_TRIAL_ADD_REMAINING_LABEL",
        default_label="➕ Add remaining trial days to paid plan",
        action="toggle",
        description="ADMIN_PRICING_TRIAL_ADD_REMAINING_DESCRIPTION",
        default_description="When enabled, remaining trial days are added to paid subscription duration.",
    ),
)


CORE_PRICING_ENTRIES: Tuple[SettingEntry, ...] = (
    SettingEntry(
        key="BASE_SUBSCRIPTION_PRICE",
        section="core",
        label="ADMIN_PRICING_CORE_BASE_SUBSCRIPTION_PRICE_LABEL",
        default_label="💳 Base subscription price",
        action="price",
    ),
    SettingEntry(
        key="BASE_PROMO_GROUP_PERIOD_DISCOUNTS_ENABLED",
        section="core",
        label="ADMIN_PRICING_CORE_PROMO_DISCOUNTS_ENABLED_LABEL",
        default_label="🎟️ Base group discounts",
        action="toggle",
        description="ADMIN_PRICING_CORE_PROMO_DISCOUNTS_ENABLED_DESCRIPTION",
        default_description="Enables base discounts for promo group periods.",
    ),
    SettingEntry(
        key="BASE_PROMO_GROUP_PERIOD_DISCOUNTS",
        section="core",
        label="ADMIN_PRICING_CORE_PROMO_DISCOUNTS_LABEL",
        default_label="🔖 Period discounts",
        action="input",
        description="ADMIN_PRICING_CORE_PROMO_DISCOUNTS_DESCRIPTION",
        default_description="Format: comma-separated day/discount pairs (e.g. 30:10,60:20).",
    ),
    SettingEntry(
        key="DEFAULT_DEVICE_LIMIT",
        section="core",
        label="ADMIN_PRICING_CORE_DEFAULT_DEVICE_LIMIT_LABEL",
        default_label="📱 Default device limit",
        action="input",
    ),
    SettingEntry(
        key="DEFAULT_TRAFFIC_LIMIT_GB",
        section="core",
        label="ADMIN_PRICING_CORE_DEFAULT_TRAFFIC_LIMIT_LABEL",
        default_label="📦 Default traffic (GB)",
        action="input",
    ),
    SettingEntry(
        key="MAX_DEVICES_LIMIT",
        section="core",
        label="ADMIN_PRICING_CORE_MAX_DEVICES_LABEL",
        default_label="📈 Maximum devices",
        action="input",
    ),
    SettingEntry(
        key="RESET_TRAFFIC_ON_PAYMENT",
        section="core",
        label="ADMIN_PRICING_CORE_RESET_TRAFFIC_LABEL",
        default_label="🔄 Reset traffic on payment",
        action="toggle",
    ),
    SettingEntry(
        key="DEFAULT_TRAFFIC_RESET_STRATEGY",
        section="core",
        label="ADMIN_PRICING_CORE_TRAFFIC_RESET_STRATEGY_LABEL",
        default_label="🗓 Traffic reset strategy",
        action="input",
        description="ADMIN_PRICING_CORE_TRAFFIC_RESET_STRATEGY_DESCRIPTION",
        default_description="Available values: DAY, WEEK, MONTH, NEVER.",
    ),
    SettingEntry(
        key="TRAFFIC_SELECTION_MODE",
        section="core",
        label="ADMIN_PRICING_CORE_TRAFFIC_SELECTION_MODE_LABEL",
        default_label="⚙️ Traffic selection mode",
        action="choice",
        choices=(
            ChoiceOption(
                "selectable",
                "ADMIN_PRICING_CORE_TRAFFIC_SELECTION_SELECTABLE",
                "Selectable",
            ),
            ChoiceOption(
                "fixed",
                "ADMIN_PRICING_CORE_TRAFFIC_SELECTION_FIXED",
                "Fixed limit",
            ),
        ),
        description="ADMIN_PRICING_CORE_TRAFFIC_SELECTION_MODE_DESCRIPTION",
        default_description="Defines whether users pick packages or use a fixed limit.",
    ),
    SettingEntry(
        key="FIXED_TRAFFIC_LIMIT_GB",
        section="core",
        label="ADMIN_PRICING_CORE_FIXED_TRAFFIC_LIMIT_LABEL",
        default_label="📏 Fixed traffic limit (GB)",
        action="input",
        description="ADMIN_PRICING_CORE_FIXED_TRAFFIC_LIMIT_DESCRIPTION",
        default_description="Used only in fixed traffic mode. 0 = unlimited.",
    ),
)


SETTING_ENTRIES_BY_SECTION: Dict[str, Tuple[SettingEntry, ...]] = {
    "trial": TRIAL_ENTRIES,
    "core": CORE_PRICING_ENTRIES,
}

SETTING_ENTRY_BY_KEY: Dict[str, SettingEntry] = {
    entry.key: entry for entries in SETTING_ENTRIES_BY_SECTION.values() for entry in entries
}

SETTING_ENTRIES: Tuple[SettingEntry, ...] = tuple(
    entry for entries in SETTING_ENTRIES_BY_SECTION.values() for entry in entries
)

SETTING_KEY_TO_TOKEN: Dict[str, str] = {
    entry.key: f"s{index}" for index, entry in enumerate(SETTING_ENTRIES)
}

SETTING_TOKEN_TO_KEY: Dict[str, str] = {
    token: key for key, token in SETTING_KEY_TO_TOKEN.items()
}


def _encode_setting_callback_key(key: str) -> str:
    return SETTING_KEY_TO_TOKEN.get(key, key)


def _decode_setting_callback_key(raw: str) -> str:
    return SETTING_TOKEN_TO_KEY.get(raw, raw)


def _traffic_package_sort_key(package: Dict[str, Any]) -> Tuple[int, int]:
    order_index = TRAFFIC_PACKAGE_ORDER_INDEX.get(package["gb"])
    if order_index is not None:
        return (0, order_index)
    return (1, package["gb"])


def _collect_traffic_packages() -> List[Dict[str, Any]]:
    raw_packages = settings.get_traffic_packages()

    packages_map: Dict[int, Dict[str, Any]] = {}
    for package in raw_packages:
        gb = int(package.get("gb", 0))
        packages_map[gb] = {
            "gb": gb,
            "price": int(package.get("price") or 0),
            "enabled": bool(package.get("enabled", True)),
            "field": TRAFFIC_PACKAGE_FIELD_MAP.get(gb),
        }

    for gb, field in TRAFFIC_PACKAGE_FIELDS:
        if not hasattr(settings, field):
            continue

        price = getattr(settings, field)
        existing = packages_map.get(gb)
        enabled = existing["enabled"] if existing is not None else True

        packages_map[gb] = {
            "gb": gb,
            "price": int(price),
            "enabled": enabled,
            "field": field,
        }

    packages = list(packages_map.values())
    packages.sort(key=_traffic_package_sort_key)
    return packages


def _serialize_traffic_packages(packages: Iterable[Dict[str, Any]]) -> str:
    parts = []
    for package in packages:
        enabled_flag = "true" if package.get("enabled") else "false"
        parts.append(f"{int(package['gb'])}:{int(package['price'])}:{enabled_flag}")
    return ",".join(parts)


async def _save_traffic_packages(
    db: AsyncSession,
    packages: Iterable[Dict[str, Any]],
    *,
    skip_if_same: bool = False,
) -> bool:
    new_value = _serialize_traffic_packages(packages)
    current_value = bot_configuration_service.get_current_value("TRAFFIC_PACKAGES_CONFIG") or ""

    if skip_if_same and current_value == new_value:
        return False

    await bot_configuration_service.set_value(db, "TRAFFIC_PACKAGES_CONFIG", new_value)
    await db.commit()
    return True


def _language_code(language: str | None) -> str:
    return (language or "ru").split("-")[0].lower()


def _format_period_label(days: int, lang_code: str, short: bool = False) -> str:
    texts = get_texts(lang_code)
    if short:
        suffix = texts.t("ADMIN_PRICING_PERIOD_SUFFIX_SHORT", "d")
        return f"{days}{suffix}"
    if days == 1:
        return texts.t("ADMIN_PRICING_PERIOD_ONE_DAY", "1 day")
    return texts.t("ADMIN_PRICING_PERIOD_DAYS", "{days} days").format(days=days)


def _format_traffic_label(gb: int, lang_code: str, short: bool = False) -> str:
    texts = get_texts(lang_code)
    if gb == 0:
        return "∞" if short else texts.t("ADMIN_PRICING_TRAFFIC_UNLIMITED", "Unlimited")
    unit = texts.t("ADMIN_PRICING_TRAFFIC_UNIT", "GB")
    if short:
        return f"{gb}{unit}"
    return texts.t("ADMIN_PRICING_TRAFFIC_FORMAT", "{gb} {unit}").format(gb=gb, unit=unit)


def _format_trial_summary(lang_code: str) -> str:
    duration = settings.TRIAL_DURATION_DAYS
    traffic = settings.TRIAL_TRAFFIC_LIMIT_GB
    devices = settings.TRIAL_DEVICE_LIMIT
    price_note = ""
    if settings.is_trial_paid_activation_enabled():
        price_note = f", 💳 {settings.format_price(settings.get_trial_activation_price())}"

    texts = get_texts(lang_code)
    traffic_label = _format_traffic_label(traffic, lang_code, short=True)
    devices_label = texts.t("ADMIN_PRICING_DEVICES_FORMAT", "{devices}📱").format(devices=devices)
    days_suffix = texts.t("ADMIN_PRICING_PERIOD_SUFFIX_SHORT", "d")
    return texts.t("ADMIN_PRICING_TRIAL_SUMMARY_FORMAT", "{duration}{suffix}, {traffic}, {devices}{price}").format(
        duration=duration, suffix=days_suffix, traffic=traffic_label, devices=devices_label, price=price_note
    )


def _format_core_summary(lang_code: str) -> str:
    texts = get_texts(lang_code)
    base_price = settings.format_price(settings.BASE_SUBSCRIPTION_PRICE)
    device_limit = settings.DEFAULT_DEVICE_LIMIT
    traffic_limit = settings.DEFAULT_TRAFFIC_LIMIT_GB
    if settings.TRAFFIC_SELECTION_MODE == "fixed":
        traffic_mode = texts.t("ADMIN_PRICING_TRAFFIC_MODE_FIXED", "⚙️ fixed")
    else:
        traffic_mode = texts.t("ADMIN_PRICING_TRAFFIC_MODE_SELECTABLE", "⚙️ selectable")
    traffic_label = _format_traffic_label(traffic_limit, lang_code, short=True)
    devices_label = texts.t("ADMIN_PRICING_DEVICES_FORMAT", "{devices}📱").format(devices=device_limit)
    return texts.t("ADMIN_PRICING_CORE_SUMMARY_FORMAT", "{price}, {devices}, {traffic}, {mode}").format(
        price=base_price, devices=devices_label, traffic=traffic_label, mode=traffic_mode
    )


def _get_period_items(lang_code: str) -> List[PriceItem]:
    items: List[PriceItem] = []
    for days in settings.get_available_subscription_periods():
        key = f"PRICE_{days}_DAYS"
        if hasattr(settings, key):
            price = getattr(settings, key)
            items.append((key, _format_period_label(days, lang_code), price))
    return items


def _get_traffic_items(lang_code: str) -> List[PriceItem]:
    packages = _collect_traffic_packages()

    items: List[PriceItem] = []
    for package in packages:
        field = package.get("field")
        if not field:
            continue

        label = _format_traffic_label(package["gb"], lang_code)
        icon = "✅" if package["enabled"] else "⚪️"
        items.append((field, f"{icon} {label}", int(package["price"])))
    return items


def _get_extra_items(lang_code: str) -> List[PriceItem]:
    texts = get_texts(lang_code)
    items: List[PriceItem] = []

    if hasattr(settings, "PRICE_PER_DEVICE"):
        label = texts.t("ADMIN_PRICING_EXTRA_DEVICE", "Extra device")
        items.append(("PRICE_PER_DEVICE", label, settings.PRICE_PER_DEVICE))

    return items


def _build_period_summary(items: Iterable[PriceItem], lang_code: str, fallback: str) -> str:
    texts = get_texts(lang_code)
    parts: List[str] = []
    for key, label, price in items:
        try:
            days = int(key.replace("PRICE_", "").replace("_DAYS", ""))
        except ValueError:
            days = None

        if days is not None:
            suffix = texts.t("ADMIN_PRICING_PERIOD_SUFFIX_SHORT", "d")
            short_label = f"{days}{suffix}"
        else:
            short_label = label

        parts.append(texts.t("ADMIN_PRICING_SUMMARY_ITEM", "{label}: {price}").format(
            label=short_label, price=settings.format_price(price)
        ))

    return ", ".join(parts) if parts else fallback


def _build_traffic_summary(lang_code: str, fallback: str) -> str:
    texts = get_texts(lang_code)
    packages = _collect_traffic_packages()
    enabled_packages = [package for package in packages if package["enabled"]]

    if not enabled_packages:
        return fallback

    parts: List[str] = []
    for package in enabled_packages:
        short_label = _format_traffic_label(package["gb"], lang_code, short=True)
        parts.append(texts.t("ADMIN_PRICING_SUMMARY_ITEM", "{label}: {price}").format(
            label=short_label, price=settings.format_price(int(package['price']))
        ))

    return ", ".join(parts) if parts else fallback


def _build_period_options_summary(lang_code: str) -> str:
    texts = get_texts(lang_code)
    suffix = texts.t("ADMIN_PRICING_PERIOD_SUFFIX_SHORT", "d")
    available = ", ".join(f"{days}{suffix}" for days in settings.get_available_subscription_periods())
    renewal = ", ".join(f"{days}{suffix}" for days in settings.get_available_renewal_periods())
    empty_marker = texts.t("ADMIN_PRICING_SUMMARY_EMPTY", "—")
    return texts.t("ADMIN_PRICING_PERIOD_OPTIONS_SUMMARY", "Subscriptions: {subs} | Renewals: {renew}").format(
        subs=available or empty_marker, renew=renewal or empty_marker
    )


def _build_extra_summary(items: Iterable[PriceItem], fallback: str) -> str:
    parts = [f"{label}: {settings.format_price(price)}" for key, label, price in items]
    return ", ".join(parts) if parts else fallback


def _build_settings_section(
    section: str,
    language: str,
) -> Tuple[str, types.InlineKeyboardMarkup]:
    texts = get_texts(language)
    lang_code = _language_code(language)
    entries = SETTING_ENTRIES_BY_SECTION.get(section, ())

    if section == "trial":
        title = texts.t("ADMIN_PRICING_SECTION_TRIAL_TITLE", "🎁 Trial period")
    elif section == "core":
        title = texts.t("ADMIN_PRICING_SECTION_CORE_TITLE", "⚙️ Core limits")
    else:
        title = texts.t("ADMIN_PRICING_SECTION_SETTINGS_GENERIC", "⚙️ Settings")

    lines: List[str] = [title, ""]
    keyboard_rows: List[List[types.InlineKeyboardButton]] = []

    if entries:
        lines.append(
            texts.t(
                "ADMIN_PRICING_SECTION_CURRENT",
                "Current values:",
            )
        )
        lines.append("")

    for entry in entries:
        label = entry.get_label(texts)
        value = bot_configuration_service.get_current_value(entry.key)
        formatted = bot_configuration_service.format_value_human(entry.key, value)

        if entry.action == "toggle":
            state_icon = "✅" if bool(value) else "⚪️"
            lines.append(f"{state_icon} <b>{label}</b> — {formatted}")
            button_text = texts.t(
                "ADMIN_PRICING_SETTING_TOGGLE_STATEFUL",
                "{icon} {label}",
            ).format(icon=state_icon, label=label)
            keyboard_rows.append(
                [
                    types.InlineKeyboardButton(
                        text=button_text,
                        callback_data=(
                            f"admin_pricing_toggle:{section}:{_encode_setting_callback_key(entry.key)}"
                        ),
                    )
                ]
            )
        elif entry.action == "choice" and entry.choices:
            lines.append(f"• <b>{label}</b>: {formatted}")
            buttons: List[types.InlineKeyboardButton] = []
            for option in entry.choices:
                is_active = value == option.value
                icon = "✅" if is_active else "⚪️"
                buttons.append(
                    types.InlineKeyboardButton(
                        text=f"{icon} {option.get_label(texts)}",
                        callback_data=(
                            f"admin_pricing_choice:{section}:{_encode_setting_callback_key(entry.key)}:{option.value}"
                        ),
                    )
                )
            for i in range(0, len(buttons), 2):
                keyboard_rows.append(buttons[i : i + 2])
        else:
            lines.append(f"• <b>{label}</b>: {formatted}")
            button_text = texts.t(
                "ADMIN_PRICING_SETTING_EDIT_WITH_VALUE",
                "✏️ {label} • {value}",
            ).format(label=label, value=formatted)
            keyboard_rows.append(
                [
                    types.InlineKeyboardButton(
                        text=button_text,
                        callback_data=(
                            f"admin_pricing_setting:{section}:{_encode_setting_callback_key(entry.key)}"
                        ),
                    )
                ]
            )

        description = entry.get_description(texts)
        if description:
            lines.append(f"<i>{description}</i>")
        lines.append("")

    if entries:
        lines.append(texts.t("ADMIN_PRICING_SECTION_PROMPT", "Select what to update:"))
    else:
        lines.append(texts.t("ADMIN_PRICING_SECTION_EMPTY", "No parameters available."))

    keyboard_rows.append([types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_pricing")])
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    return "\n".join(lines).strip(), keyboard


def _build_traffic_options_section(language: str) -> Tuple[str, types.InlineKeyboardMarkup]:
    texts = get_texts(language)
    lang_code = _language_code(language)
    packages = _collect_traffic_packages()

    title = texts.t(
        "ADMIN_PRICING_SECTION_TRAFFIC_OPTIONS_TITLE",
        "🚦 Traffic package visibility",
    )

    lines: List[str] = [title, ""]

    enabled_labels = [
        _format_traffic_label(package["gb"], lang_code, short=True)
        for package in packages
        if package["enabled"]
    ]

    if enabled_labels:
        lines.append(
            texts.t(
                "ADMIN_PRICING_SECTION_TRAFFIC_OPTIONS_ACTIVE",
                "Active packages: {items}",
            ).format(items=", ".join(enabled_labels))
        )
    else:
        lines.append(
            texts.t(
                "ADMIN_PRICING_SECTION_TRAFFIC_OPTIONS_NONE",
                "No active packages.",
            )
        )

    lines.append("")
    lines.append(
        texts.t(
            "ADMIN_PRICING_SECTION_TRAFFIC_OPTIONS_PROMPT",
            "Tap a package to toggle its visibility.",
        )
    )

    keyboard_rows: List[List[types.InlineKeyboardButton]] = []
    buttons: List[types.InlineKeyboardButton] = []

    for package in packages:
        icon = "✅" if package["enabled"] else "⚪️"
        label = _format_traffic_label(package["gb"], lang_code, short=True)
        buttons.append(
            types.InlineKeyboardButton(
                text=f"{icon} {label}",
                callback_data=f"admin_pricing_toggle_traffic:{package['gb']}",
            )
        )

    for i in range(0, len(buttons), 3):
        keyboard_rows.append(buttons[i : i + 3])

    keyboard_rows.append([types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_pricing")])
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    return "\n".join(lines), keyboard


def _build_period_options_section(language: str) -> Tuple[str, types.InlineKeyboardMarkup]:
    texts = get_texts(language)
    lang_code = _language_code(language)
    suffix = texts.t("ADMIN_PRICING_PERIOD_SUFFIX_SHORT", "d")

    available_subscription = set(settings.get_available_subscription_periods())
    available_renewal = set(settings.get_available_renewal_periods())

    subscription_options = (14, 30, 60, 90, 180, 360)
    renewal_options = (30, 60, 90, 180, 360)

    title = texts.t("ADMIN_PRICING_SECTION_PERIOD_OPTIONS_TITLE", "🗓 Available periods")
    lines: List[str] = [title, ""]

    empty_marker = texts.t("ADMIN_PRICING_SUMMARY_EMPTY", "—")
    sub_list = ", ".join(f"{days}{suffix}" for days in sorted(available_subscription)) or empty_marker
    renew_list = ", ".join(f"{days}{suffix}" for days in sorted(available_renewal)) or empty_marker

    lines.append(
        texts.t(
            "ADMIN_PRICING_SECTION_PERIOD_OPTIONS_SUB",
            "Active subscription periods: {items}",
        ).format(items=sub_list)
    )
    lines.append(
        texts.t(
            "ADMIN_PRICING_SECTION_PERIOD_OPTIONS_RENEW",
            "Active renewal periods: {items}",
        ).format(items=renew_list)
    )
    lines.append("")
    lines.append(
        texts.t(
            "ADMIN_PRICING_SECTION_PERIOD_OPTIONS_PROMPT",
            "Tap a period to toggle its visibility.",
        )
    )

    keyboard_rows: List[List[types.InlineKeyboardButton]] = []

    sub_buttons = []
    for days in subscription_options:
        icon = "✅" if days in available_subscription else "⚪️"
        sub_buttons.append(
            types.InlineKeyboardButton(
                text=f"{icon} {days}{suffix}",
                callback_data=f"admin_pricing_toggle_period:subscription:{days}",
            )
        )
    for i in range(0, len(sub_buttons), 3):
        keyboard_rows.append(sub_buttons[i : i + 3])

    renew_buttons = []
    for days in renewal_options:
        icon = "✅" if days in available_renewal else "⚪️"
        renew_buttons.append(
            types.InlineKeyboardButton(
                text=f"{icon} {days}{suffix}",
                callback_data=f"admin_pricing_toggle_period:renewal:{days}",
            )
        )
    for i in range(0, len(renew_buttons), 3):
        keyboard_rows.append(renew_buttons[i : i + 3])

    keyboard_rows.append([types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_pricing")])
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    return "\n".join(lines), keyboard


def _build_overview(language: str) -> Tuple[str, types.InlineKeyboardMarkup]:
    texts = get_texts(language)
    lang_code = _language_code(language)

    period_items = _get_period_items(lang_code)
    traffic_items = _get_traffic_items(lang_code)
    extra_items = _get_extra_items(lang_code)

    fallback = texts.t("ADMIN_PRICING_SUMMARY_EMPTY", "—")
    summary_periods = _build_period_summary(period_items, lang_code, fallback)
    summary_traffic = _build_traffic_summary(lang_code, fallback)
    summary_extra = _build_extra_summary(extra_items, fallback)
    summary_trial = _format_trial_summary(lang_code)
    summary_core = _format_core_summary(lang_code)
    summary_period_options = _build_period_options_summary(lang_code)

    lines = [
        f"💰 <b>{texts.t('ADMIN_PRICING_MENU_TITLE', 'Pricing management')}</b>",
        texts.t(
            'ADMIN_PRICING_MENU_DESCRIPTION',
            'Quick access to subscription plans, traffic bundles and extra services.',
        ),
        "",
        f"<b>{texts.t('ADMIN_PRICING_MENU_SUMMARY', 'Quick summary:')}</b>",
        f"🎁 {texts.t('ADMIN_PRICING_MENU_SUMMARY_TRIAL', 'Trial: {summary}').format(summary=summary_trial)}",
        f"⚙️ {texts.t('ADMIN_PRICING_MENU_SUMMARY_CORE', 'Core limits: {summary}').format(summary=summary_core)}",
        f"🗓 {texts.t('ADMIN_PRICING_MENU_SUMMARY_PERIOD_OPTIONS', 'Available periods: {summary}').format(summary=summary_period_options)}",
        f"💵 {texts.t('ADMIN_PRICING_MENU_SUMMARY_PERIODS', 'Periods: {summary}').format(summary=summary_periods)}",
        f"📦 {texts.t('ADMIN_PRICING_MENU_SUMMARY_TRAFFIC', 'Traffic: {summary}').format(summary=summary_traffic)}",
        f"➕ {texts.t('ADMIN_PRICING_MENU_SUMMARY_EXTRA', 'Extras: {summary}').format(summary=summary_extra)}",
        "",
        texts.t('ADMIN_PRICING_MENU_PROMPT', 'Choose a section to edit:'),
    ]

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_PRICING_BUTTON_TRIAL", "🎁 Trial period"),
                    callback_data="admin_pricing_section:trial",
                ),
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_PRICING_BUTTON_CORE", "⚙️ Core limits"),
                    callback_data="admin_pricing_section:core",
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_PRICING_BUTTON_PERIOD_OPTIONS", "🗓 Available periods"),
                    callback_data="admin_pricing_section:period_options",
                ),
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_PRICING_BUTTON_PERIODS", "🗓 Subscription periods"),
                    callback_data="admin_pricing_section:periods",
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_PRICING_BUTTON_TRAFFIC", "📦 Traffic packages"),
                    callback_data="admin_pricing_section:traffic",
                ),
                types.InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_PRICING_BUTTON_TRAFFIC_OPTIONS",
                        "🚦 Package visibility",
                    ),
                    callback_data="admin_pricing_section:traffic_options",
                ),
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_PRICING_BUTTON_EXTRA", "➕ Extras"),
                    callback_data="admin_pricing_section:extra",
                ),
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")],
        ]
    )

    return "\n".join(lines), keyboard


def _build_section(
    section: str,
    language: str,
) -> Tuple[str, types.InlineKeyboardMarkup]:
    texts = get_texts(language)
    lang_code = _language_code(language)

    if section == "periods":
        items = _get_period_items(lang_code)
        title = texts.t("ADMIN_PRICING_SECTION_PERIODS_TITLE", "🗓 Subscription periods")
    elif section == "traffic":
        items = _get_traffic_items(lang_code)
        title = texts.t("ADMIN_PRICING_SECTION_TRAFFIC_TITLE", "📦 Traffic packages")
    elif section == "extra":
        items = _get_extra_items(lang_code)
        title = texts.t("ADMIN_PRICING_SECTION_EXTRA_TITLE", "➕ Extra options")
    elif section == "traffic_options":
        return _build_traffic_options_section(language)
    elif section in SETTING_ENTRIES_BY_SECTION:
        return _build_settings_section(section, language)
    elif section == "period_options":
        return _build_period_options_section(language)
    else:
        items = _get_extra_items(lang_code)
        title = texts.t("ADMIN_PRICING_SECTION_EXTRA_TITLE", "➕ Extra options")

    lines = [title, ""]

    if items:
        for key, label, price in items:
            lines.append(f"• {label} — {settings.format_price(price)}")
        lines.append("")
        lines.append(texts.t("ADMIN_PRICING_SECTION_PROMPT", "Select what to update:"))
    else:
        lines.append(texts.t("ADMIN_PRICING_SECTION_EMPTY", "No values available."))

    keyboard_rows: List[List[types.InlineKeyboardButton]] = []
    for key, label, price in items:
        keyboard_rows.append(
            [
                types.InlineKeyboardButton(
                    text=f"{label} • {settings.format_price(price)}",
                    callback_data=f"admin_pricing_edit:{section}:{key}",
                )
            ]
        )

    keyboard_rows.append(
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_pricing")]
    )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    return "\n".join(lines), keyboard


def _build_price_prompt(texts: Any, label: str, current_price: str) -> str:
    lines = [
        f"💰 <b>{texts.t('ADMIN_PRICING_EDIT_TITLE', 'Update price')}</b>",
        "",
        f"{texts.t('ADMIN_PRICING_EDIT_TARGET', 'Current item')}: <b>{label}</b>",
        f"{texts.t('ADMIN_PRICING_EDIT_CURRENT', 'Current value')}: <b>{current_price}</b>",
        "",
        texts.t(
            'ADMIN_PRICING_EDIT_PROMPT',
            'Enter a new price in RUB (e.g. 990 or 990.50). Use 0 for a free plan.',
        ),
        texts.t(
            'ADMIN_PRICING_EDIT_CANCEL_HINT',
            'Send "Cancel" to return without changes.',
        ),
    ]
    return "\n".join(lines)


async def _render_message(
    message: types.Message,
    text: str,
    keyboard: types.InlineKeyboardMarkup,
) -> None:
    try:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramBadRequest as error:  # message changed elsewhere
        logger.debug("Failed to edit pricing message: %s", error)
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


async def _render_message_by_id(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    keyboard: types.InlineKeyboardMarkup,
) -> None:
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except TelegramBadRequest as error:
        logger.debug("Failed to edit pricing message by id: %s", error)
        await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")


def _parse_price_input(text: str) -> int:
    normalized = text.replace("₽", "").replace("р", "").replace("RUB", "")
    normalized = normalized.replace(" ", "").replace(",", ".").strip()
    if not normalized:
        raise ValueError("empty")

    try:
        value = Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError("invalid") from error

    if value < 0:
        raise ValueError("negative")

    kopeks = int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return kopeks


def _resolve_label(section: str, key: str, language: str) -> str:
    texts = get_texts(language)
    lang_code = _language_code(language)

    entry = SETTING_ENTRY_BY_KEY.get(key)
    if entry is not None:
        return entry.get_label(texts)

    if section == "periods" and key.startswith("PRICE_") and key.endswith("_DAYS"):
        try:
            days = int(key.replace("PRICE_", "").replace("_DAYS", ""))
        except ValueError:
            days = None
        if days is not None:
            return _format_period_label(days, lang_code)

    if section == "traffic" and key.startswith("PRICE_TRAFFIC_"):
        if key.endswith("UNLIMITED"):
            return _format_traffic_label(0, lang_code)
        digits = ''.join(ch for ch in key if ch.isdigit())
        try:
            gb = int(digits)
        except ValueError:
            gb = None
        if gb is not None:
            return _format_traffic_label(gb, lang_code)

    if key == "PRICE_PER_DEVICE":
        return texts.t("ADMIN_PRICING_EXTRA_DEVICE", "Extra device")

    return key


@admin_required
@error_handler
async def show_pricing_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    text, keyboard = _build_overview(db_user.language)
    await _render_message(callback.message, text, keyboard)
    await state.clear()
    await callback.answer()


@admin_required
@error_handler
async def show_pricing_section(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    section = callback.data.split(":", 1)[1]
    text, keyboard = _build_section(section, db_user.language)
    await _render_message(callback.message, text, keyboard)
    await state.clear()
    await callback.answer()


@admin_required
@error_handler
async def start_price_edit(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    _, section, key = callback.data.split(":", 2)
    texts = get_texts(db_user.language)
    label = _resolve_label(section, key, db_user.language)

    await state.update_data(
        pricing_key=key,
        pricing_section=section,
        pricing_message_id=callback.message.message_id,
        pricing_mode="price",
    )
    await state.set_state(PricingStates.waiting_for_value)

    current_price = settings.format_price(getattr(settings, key, 0))
    prompt = _build_price_prompt(texts, label, current_price)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_PRICING_EDIT_CANCEL", "❌ Cancel"),
                    callback_data=f"admin_pricing_section:{section}",
                )
            ]
        ]
    )

    await _render_message(callback.message, prompt, keyboard)
    await callback.answer()


@admin_required
@error_handler
async def start_setting_edit(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    try:
        _, section, raw_key = callback.data.split(":", 2)
    except ValueError:
        await callback.answer()
        return

    key = _decode_setting_callback_key(raw_key)
    entry = SETTING_ENTRY_BY_KEY.get(key)
    texts = get_texts(db_user.language)
    label = entry.get_label(texts) if entry else key
    current_value = bot_configuration_service.get_current_value(key)
    formatted_current = bot_configuration_service.format_value_human(key, current_value)
    guidance = bot_configuration_service.get_setting_guidance(key)

    mode = "price" if entry and entry.action == "price" else "setting"

    await state.update_data(
        pricing_key=key,
        pricing_section=section,
        pricing_message_id=callback.message.message_id,
        pricing_mode=mode,
        pricing_label=label,
    )
    await state.set_state(PricingStates.waiting_for_value)

    if mode == "price":
        prompt = _build_price_prompt(
            texts,
            label,
            settings.format_price(int(current_value or 0)),
        )
    else:
        description = guidance.get("description") or ""
        format_hint = guidance.get("format") or ""
        example = guidance.get("example") or texts.t("ADMIN_PRICING_SUMMARY_EMPTY", "—")
        warning = guidance.get("warning") or ""
        prompt_parts = [
            f"⚙️ <b>{texts.t('ADMIN_PRICING_SETTING_EDIT_TITLE', 'Parameter configuration')}</b>",
            "",
            f"{texts.t('ADMIN_PRICING_SETTING_PARAMETER', 'Parameter')}: <b>{label}</b>",
            f"{texts.t('ADMIN_PRICING_SETTING_CURRENT', 'Current value')}: <b>{formatted_current}</b>",
        ]
        if description:
            prompt_parts.extend(["", description])
        prompt_parts.extend(
            [
                "",
                f"ℹ️ {texts.t('ADMIN_PRICING_SETTING_FORMAT', 'Input format')}: {format_hint}",
                f"📌 {texts.t('ADMIN_PRICING_SETTING_EXAMPLE', 'Example')}: {example}",
            ]
        )
        if warning:
            prompt_parts.append(
                f"⚠️ {texts.t('ADMIN_PRICING_SETTING_WARNING', 'Important')}: {warning}"
            )
        prompt_parts.extend(
            [
                "",
                texts.t(
                    'ADMIN_PRICING_SETTING_PROMPT',
                    'Send a new value or type "Cancel". Use none to clear.',
                ),
                texts.t(
                    'ADMIN_PRICING_SETTING_CANCEL_HINT',
                    'Reply "Cancel" to go back without changes.',
                ),
            ]
        )
        prompt = "\n".join(prompt_parts)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_PRICING_EDIT_CANCEL", "❌ Cancel"),
                    callback_data=f"admin_pricing_section:{section}",
                )
            ]
        ]
    )

    await _render_message(callback.message, prompt, keyboard)
    await callback.answer()


async def process_pricing_input(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession,
) -> None:
    data = await state.get_data()
    key = data.get("pricing_key")
    section = data.get("pricing_section", "periods")
    message_id = data.get("pricing_message_id")
    mode = data.get("pricing_mode", "price")
    stored_label = data.get("pricing_label")

    texts = get_texts(db_user.language)

    if not key:
        await message.answer(texts.t("ADMIN_PRICING_EDIT_EXPIRED", "Editing session expired."))
        await state.clear()
        return

    raw_value = message.text or ""
    if raw_value.strip().lower() in {"cancel", "отмена"}:
        await state.clear()
        section_text, section_keyboard = _build_section(section, db_user.language)
        if message_id:
            await _render_message_by_id(
                message.bot,
                message.chat.id,
                message_id,
                section_text,
                section_keyboard,
            )
        await message.answer(texts.t("ADMIN_PRICING_EDIT_CANCELLED", "Changes cancelled."))
        return

    if mode == "price":
        try:
            new_value = _parse_price_input(raw_value)
        except ValueError:
            await message.answer(
                texts.t(
                    "ADMIN_PRICING_EDIT_INVALID",
                    "Could not parse the price. Please enter a number in RUB (e.g. 990 or 990.50).",
                )
            )
            return
    else:
        try:
            new_value = bot_configuration_service.parse_user_value(key, raw_value)
        except ValueError as error:
            error_text = str(error) or texts.t(
                "ADMIN_PRICING_SETTING_INVALID",
                "Could not update the parameter. Please check the value format.",
            )
            await message.answer(error_text)
            return

    await bot_configuration_service.set_value(db, key, new_value)
    await db.commit()

    if key.startswith("PRICE_TRAFFIC_"):
        packages = _collect_traffic_packages()
        await _save_traffic_packages(db, packages, skip_if_same=True)

    section_text, section_keyboard = _build_section(section, db_user.language)

    if mode == "price":
        if message_id:
            await _render_message_by_id(
                message.bot,
                message.chat.id,
                message_id,
                section_text,
                section_keyboard,
            )
        try:
            await message.delete()
        except TelegramBadRequest as error:
            logger.debug("Failed to delete pricing input message: %s", error)
        await state.clear()
        return
    else:
        entry = SETTING_ENTRY_BY_KEY.get(key)
        label = entry.get_label(texts) if entry else (stored_label or key)
        formatted_value = bot_configuration_service.format_value_human(
            key, bot_configuration_service.get_current_value(key)
        )
        await message.answer(
            texts.t(
                "ADMIN_PRICING_SETTING_SUCCESS",
                "Parameter {label} updated: {value}",
            ).format(label=label, value=formatted_value)
        )

    await state.clear()

    if message_id:
        section_text, section_keyboard = _build_section(section, db_user.language)
        await _render_message_by_id(
            message.bot,
            message.chat.id,
            message_id,
            section_text,
            section_keyboard,
        )


@admin_required
@error_handler
async def toggle_setting(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    try:
        _, section, raw_key = callback.data.split(":", 2)
    except ValueError:
        await callback.answer()
        return

    key = _decode_setting_callback_key(raw_key)
    entry = SETTING_ENTRY_BY_KEY.get(key)
    if not entry or entry.action != "toggle":
        await callback.answer()
        return

    current = bool(bot_configuration_service.get_current_value(key))
    new_value = not current
    await bot_configuration_service.set_value(db, key, new_value)
    await db.commit()

    value_text = bot_configuration_service.format_value_human(key, new_value)
    await callback.answer(value_text, show_alert=False)

    text, keyboard = _build_section(section, db_user.language)
    await _render_message(callback.message, text, keyboard)


@admin_required
@error_handler
async def select_setting_choice(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    try:
        _, section, raw_key, value_raw = callback.data.split(":", 3)
    except ValueError:
        await callback.answer()
        return

    key = _decode_setting_callback_key(raw_key)
    entry = SETTING_ENTRY_BY_KEY.get(key)
    if not entry or entry.action != "choice" or not entry.choices:
        await callback.answer()
        return

    target_option = None
    for option in entry.choices:
        if str(option.value) == value_raw:
            target_option = option
            break

    if target_option is None:
        await callback.answer()
        return

    texts = get_texts(db_user.language)
    current_value = bot_configuration_service.get_current_value(key)
    if current_value == target_option.value:
        await callback.answer(
            texts.t(
                "ADMIN_PRICING_CHOICE_ALREADY",
                "This option is already active.",
            )
        )
        return

    await bot_configuration_service.set_value(db, key, target_option.value)
    await db.commit()

    await callback.answer(
        texts.t(
            "ADMIN_PRICING_CHOICE_UPDATED",
            "Selected: {label}",
        ).format(label=target_option.get_label(texts))
    )

    text, keyboard = _build_section(section, db_user.language)
    await _render_message(callback.message, text, keyboard)


@admin_required
@error_handler
async def toggle_traffic_package(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    try:
        _, gb_raw = callback.data.split(":", 1)
        gb_value = int(gb_raw)
    except (ValueError, TypeError):
        await callback.answer()
        return

    texts = get_texts(db_user.language)
    packages = _collect_traffic_packages()

    target_index = next((index for index, pkg in enumerate(packages) if pkg["gb"] == gb_value), None)
    if target_index is None:
        await callback.answer()
        return

    enabled_count = sum(1 for pkg in packages if pkg["enabled"])
    target_package = packages[target_index]

    if target_package["enabled"] and enabled_count <= 1:
        await callback.answer(
            texts.t(
                "ADMIN_PRICING_TRAFFIC_PACKAGE_MIN",
                "At least one package must remain.",
            ),
            show_alert=True,
        )
        return

    target_package["enabled"] = not target_package["enabled"]

    await _save_traffic_packages(db, packages)

    status_text = (
        texts.t("ADMIN_PRICING_TRAFFIC_PACKAGE_ENABLED", "Package enabled.")
        if target_package["enabled"]
        else texts.t("ADMIN_PRICING_TRAFFIC_PACKAGE_DISABLED", "Package disabled.")
    )
    await callback.answer(status_text)

    text, keyboard = _build_traffic_options_section(db_user.language)
    await _render_message(callback.message, text, keyboard)


@admin_required
@error_handler
async def toggle_period_option(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    try:
        _, target, value_raw = callback.data.split(":", 2)
        days = int(value_raw)
    except (ValueError, TypeError):
        await callback.answer()
        return

    texts = get_texts(db_user.language)

    if target == "subscription":
        current = set(settings.get_available_subscription_periods())
        options = {14, 30, 60, 90, 180, 360}
        setting_key = "AVAILABLE_SUBSCRIPTION_PERIODS"
    elif target == "renewal":
        current = set(settings.get_available_renewal_periods())
        options = {30, 60, 90, 180, 360}
        setting_key = "AVAILABLE_RENEWAL_PERIODS"
    else:
        await callback.answer()
        return

    if days not in options:
        await callback.answer()
        return

    if days in current:
        if len(current) == 1:
            await callback.answer(
                texts.t(
                    "ADMIN_PRICING_PERIOD_MIN",
                    "At least one period must remain.",
                ),
                show_alert=True,
            )
            return
        current.remove(days)
        action_text = texts.t("ADMIN_PRICING_PERIOD_DISABLED", "Period disabled.")
    else:
        current.add(days)
        action_text = texts.t("ADMIN_PRICING_PERIOD_ENABLED", "Period enabled.")

    new_value = ",".join(str(item) for item in sorted(current))
    await bot_configuration_service.set_value(db, setting_key, new_value)
    await db.commit()

    await callback.answer(action_text)

    text, keyboard = _build_period_options_section(db_user.language)
    await _render_message(callback.message, text, keyboard)


def register_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(
        show_pricing_menu,
        F.data.in_({"admin_pricing", "admin_subs_pricing"}),
    )
    dp.callback_query.register(
        show_pricing_section,
        F.data.startswith("admin_pricing_section:"),
    )
    dp.callback_query.register(
        start_price_edit,
        F.data.startswith("admin_pricing_edit:"),
    )
    dp.callback_query.register(
        start_setting_edit,
        F.data.startswith("admin_pricing_setting:"),
    )
    dp.callback_query.register(
        toggle_setting,
        F.data.startswith("admin_pricing_toggle:"),
    )
    dp.callback_query.register(
        select_setting_choice,
        F.data.startswith("admin_pricing_choice:"),
    )
    dp.callback_query.register(
        toggle_traffic_package,
        F.data.startswith("admin_pricing_toggle_traffic:"),
    )
    dp.callback_query.register(
        toggle_period_option,
        F.data.startswith("admin_pricing_toggle_period:"),
    )
    dp.message.register(
        process_pricing_input,
        PricingStates.waiting_for_value,
    )
