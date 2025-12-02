import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union, get_args, get_origin

from app.database.universal_migration import ensure_default_web_api_token

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    Settings,
    settings,
    refresh_period_prices,
    refresh_traffic_prices,
    ENV_OVERRIDE_KEYS,
)
from app.database.crud.system_setting import (
    delete_system_setting,
    upsert_system_setting,
)
from app.database.database import AsyncSessionLocal
from app.database.models import SystemSetting


logger = logging.getLogger(__name__)


def _title_from_key(key: str) -> str:
    parts = key.split("_")
    if not parts:
        return key
    return " ".join(part.capitalize() for part in parts)


def _truncate(value: str, max_len: int = 60) -> str:
    value = value.strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 1] + "…"


@dataclass(slots=True)
class SettingDefinition:
    key: str
    category_key: str
    category_label: str
    python_type: Type[Any]
    type_label: str
    is_optional: bool

    @property
    def display_name(self) -> str:
        return _title_from_key(self.key)


@dataclass(slots=True)
class ChoiceOption:
    value: Any
    label: str
    description: Optional[str] = None


class ReadOnlySettingError(RuntimeError):
    """Exception raised when attempting to modify a read-only setting."""


class BotConfigurationService:
    EXCLUDED_KEYS: set[str] = {"BOT_TOKEN", "ADMIN_IDS"}

    READ_ONLY_KEYS: set[str] = {"EXTERNAL_ADMIN_TOKEN", "EXTERNAL_ADMIN_TOKEN_BOT_ID"}
    PLAIN_TEXT_KEYS: set[str] = {"EXTERNAL_ADMIN_TOKEN", "EXTERNAL_ADMIN_TOKEN_BOT_ID"}

    CATEGORY_TITLES: Dict[str, str] = {
        "CORE": "🤖 Core settings",
        "SUPPORT": "💬 Support and tickets",
        "LOCALIZATION": "🌍 Interface languages",
        "CHANNEL": "📣 Required subscription",
        "TIMEZONE": "🗂 Timezone",
        "PAYMENT": "💳 General payment settings",
        "PAYMENT_VERIFICATION": "🕵️ Payment verification",
        "TELEGRAM": "⭐ Telegram Stars",
        "CRYPTOBOT": "🪙 CryptoBot",
        "HELEKET": "🪙 Heleket",
        "YOOKASSA": "🟣 YooKassa",
        "PLATEGA": "💳 Platega",
        "TRIBUTE": "🎁 Tribute",
        "MULENPAY": "💰 {mulenpay_name}",
        "PAL24": "🏦 PAL24 / PayPalych",
        "WATA": "💠 Wata",
        "EXTERNAL_ADMIN": "🛡️ External admin",
        "SUBSCRIPTIONS_CORE": "📅 Subscriptions and limits",
        "SIMPLE_SUBSCRIPTION": "⚡ Simple purchase",
        "PERIODS": "📆 Subscription periods",
        "SUBSCRIPTION_PRICES": "💵 Plan pricing",
        "TRAFFIC": "📊 Traffic",
        "TRAFFIC_PACKAGES": "📦 Traffic packages",
        "TRIAL": "🎁 Trial period",
        "REFERRAL": "👥 Referral program",
        "AUTOPAY": "🔄 Auto-renewal",
        "NOTIFICATIONS": "🔔 User notifications",
        "ADMIN_NOTIFICATIONS": "📣 Admin notifications",
        "ADMIN_REPORTS": "🗂 Automatic reports",
        "INTERFACE": "🎨 Interface and branding",
        "INTERFACE_BRANDING": "🖼️ Branding",
        "INTERFACE_SUBSCRIPTION": "🔗 Subscription link",
        "CONNECT_BUTTON": "🚀 Connect button",
        "MINIAPP": "📱 Mini App",
        "HAPP": "🅷 Happ",
        "SKIP": "⚡ Quick start",
        "ADDITIONAL": "📱 Additional apps",
        "DATABASE": "💾 Database",
        "POSTGRES": "🐘 PostgreSQL",
        "SQLITE": "🧱 SQLite",
        "REDIS": "🧠 Redis",
        "REMNAWAVE": "🌐 RemnaWave API",
        "SERVER_STATUS": "📊 Server status",
        "MONITORING": "📈 Monitoring",
        "MAINTENANCE": "🔧 Maintenance",
        "BACKUP": "💾 Backups",
        "VERSION": "🔄 Version check",
        "WEB_API": "⚡ Web API",
        "WEBHOOK": "🌐 Webhook",
        "LOG": "📝 Logging",
        "DEBUG": "🧪 Development mode",
        "MODERATION": "🛡️ Moderation and filters",
    }

    CATEGORY_DESCRIPTIONS: Dict[str, str] = {
        "CORE": "Basic bot operation parameters and required links.",
        "SUPPORT": "Support contacts, SLA and ticket processing modes.",
        "LOCALIZATION": "Available languages, interface localization and language selection.",
        "CHANNEL": "Required channel or group subscription settings.",
        "TIMEZONE": "Panel timezone and time display.",
        "PAYMENT": "General payment texts, receipt descriptions and templates.",
        "PAYMENT_VERIFICATION": "Automatic payment verification and execution interval.",
        "YOOKASSA": "YooKassa integration: shop identifiers and webhooks.",
        "CRYPTOBOT": "CryptoBot and cryptocurrency payments via Telegram.",
        "HELEKET": "Heleket: cryptocurrency payments, merchant keys and webhooks.",
        "PLATEGA": "Platega: merchant ID, secret, return links and payment methods.",
        "MULENPAY": "{mulenpay_name} payments and shop parameters.",
        "PAL24": "PAL24 / PayPalych connections and limits.",
        "TRIBUTE": "Tribute and donation services.",
        "TELEGRAM": "Telegram Stars and their cost.",
        "WATA": "Wata: access token, payment type and amount limits.",
        "EXTERNAL_ADMIN": "External admin token for request verification.",
        "SUBSCRIPTIONS_CORE": "Device limits, traffic limits and base subscription prices.",
        "SIMPLE_SUBSCRIPTION": "Simple purchase parameters: period, traffic, devices and squads.",
        "PERIODS": "Available subscription and renewal periods.",
        "SUBSCRIPTION_PRICES": "Subscription prices by period in kopecks.",
        "TRAFFIC": "Traffic limits and reset strategies.",
        "TRAFFIC_PACKAGES": "Traffic package prices and offer configuration.",
        "TRIAL": "Trial period duration and limitations.",
        "REFERRAL": "Referral program bonuses and thresholds.",
        "AUTOPAY": "Auto-renewal settings and minimum balance.",
        "NOTIFICATIONS": "User notifications and message caching.",
        "ADMIN_NOTIFICATIONS": "Admin alerts about events and tickets.",
        "ADMIN_REPORTS": "Automatic reports for the team.",
        "INTERFACE": "Global interface and branding parameters.",
        "INTERFACE_BRANDING": "Logo and brand style.",
        "INTERFACE_SUBSCRIPTION": "Subscription links and button display.",
        "CONNECT_BUTTON": "Connect button behavior and miniapp.",
        "MINIAPP": "Mini App and custom links.",
        "HAPP": "Happ integration and related links.",
        "SKIP": "Quick start settings and connection guide.",
        "ADDITIONAL": "app-config.json configuration, deep links and cache.",
        "DATABASE": "Database operation mode and file paths.",
        "POSTGRES": "PostgreSQL connection parameters.",
        "SQLITE": "SQLite file and backup parameters.",
        "REDIS": "Redis connection for cache.",
        "REMNAWAVE": "Authorization parameters and RemnaWave API integration.",
        "SERVER_STATUS": "Server status display and external URL.",
        "MONITORING": "Monitoring intervals and log storage.",
        "MAINTENANCE": "Maintenance mode, messages and intervals.",
        "BACKUP": "Backup and schedule.",
        "VERSION": "Repository update tracking.",
        "WEB_API": "Web API, tokens and access rights.",
        "WEBHOOK": "Webhook paths and secrets.",
        "LOG": "Logging levels and rotation.",
        "DEBUG": "Debug functions and safe mode.",
        "MODERATION": "Display name filter settings and phishing protection.",
    }

    @staticmethod
    def _format_dynamic_copy(category_key: Optional[str], value: str) -> str:
        if not value:
            return value
        if category_key == "MULENPAY":
            return value.format(mulenpay_name=settings.get_mulenpay_display_name())
        return value

    CATEGORY_KEY_OVERRIDES: Dict[str, str] = {
        "DATABASE_URL": "DATABASE",
        "DATABASE_MODE": "DATABASE",
        "LOCALES_PATH": "LOCALIZATION",
        "CHANNEL_SUB_ID": "CHANNEL",
        "CHANNEL_LINK": "CHANNEL",
        "CHANNEL_IS_REQUIRED_SUB": "CHANNEL",
        "BOT_USERNAME": "CORE",
        "DEFAULT_LANGUAGE": "LOCALIZATION",
        "AVAILABLE_LANGUAGES": "LOCALIZATION",
        "LANGUAGE_SELECTION_ENABLED": "LOCALIZATION",
        "DEFAULT_DEVICE_LIMIT": "SUBSCRIPTIONS_CORE",
        "DEFAULT_TRAFFIC_LIMIT_GB": "SUBSCRIPTIONS_CORE",
        "MAX_DEVICES_LIMIT": "SUBSCRIPTIONS_CORE",
        "PRICE_PER_DEVICE": "SUBSCRIPTIONS_CORE",
        "DEVICES_SELECTION_ENABLED": "SUBSCRIPTIONS_CORE",
        "DEVICES_SELECTION_DISABLED_AMOUNT": "SUBSCRIPTIONS_CORE",
        "BASE_SUBSCRIPTION_PRICE": "SUBSCRIPTIONS_CORE",
        "DEFAULT_TRAFFIC_RESET_STRATEGY": "TRAFFIC",
        "RESET_TRAFFIC_ON_PAYMENT": "TRAFFIC",
        "TRAFFIC_SELECTION_MODE": "TRAFFIC",
        "FIXED_TRAFFIC_LIMIT_GB": "TRAFFIC",
        "AVAILABLE_SUBSCRIPTION_PERIODS": "PERIODS",
        "AVAILABLE_RENEWAL_PERIODS": "PERIODS",
        "PRICE_14_DAYS": "SUBSCRIPTION_PRICES",
        "PRICE_30_DAYS": "SUBSCRIPTION_PRICES",
        "PRICE_60_DAYS": "SUBSCRIPTION_PRICES",
        "PRICE_90_DAYS": "SUBSCRIPTION_PRICES",
        "PRICE_180_DAYS": "SUBSCRIPTION_PRICES",
        "PRICE_360_DAYS": "SUBSCRIPTION_PRICES",
        "TRAFFIC_PACKAGES_CONFIG": "TRAFFIC_PACKAGES",
        "BASE_PROMO_GROUP_PERIOD_DISCOUNTS_ENABLED": "SUBSCRIPTIONS_CORE",
        "BASE_PROMO_GROUP_PERIOD_DISCOUNTS": "SUBSCRIPTIONS_CORE",
        "DEFAULT_AUTOPAY_ENABLED": "AUTOPAY",
        "DEFAULT_AUTOPAY_DAYS_BEFORE": "AUTOPAY",
        "MIN_BALANCE_FOR_AUTOPAY_KOPEKS": "AUTOPAY",
        "TRIAL_WARNING_HOURS": "TRIAL",
        "SUPPORT_USERNAME": "SUPPORT",
        "SUPPORT_MENU_ENABLED": "SUPPORT",
        "SUPPORT_SYSTEM_MODE": "SUPPORT",
        "SUPPORT_TICKET_SLA_ENABLED": "SUPPORT",
        "SUPPORT_TICKET_SLA_MINUTES": "SUPPORT",
        "SUPPORT_TICKET_SLA_CHECK_INTERVAL_SECONDS": "SUPPORT",
        "SUPPORT_TICKET_SLA_REMINDER_COOLDOWN_MINUTES": "SUPPORT",
        "ADMIN_NOTIFICATIONS_ENABLED": "ADMIN_NOTIFICATIONS",
        "ADMIN_NOTIFICATIONS_CHAT_ID": "ADMIN_NOTIFICATIONS",
        "ADMIN_NOTIFICATIONS_TOPIC_ID": "ADMIN_NOTIFICATIONS",
        "ADMIN_NOTIFICATIONS_TICKET_TOPIC_ID": "ADMIN_NOTIFICATIONS",
        "ADMIN_REPORTS_ENABLED": "ADMIN_REPORTS",
        "ADMIN_REPORTS_CHAT_ID": "ADMIN_REPORTS",
        "ADMIN_REPORTS_TOPIC_ID": "ADMIN_REPORTS",
        "ADMIN_REPORTS_SEND_TIME": "ADMIN_REPORTS",
        "PAYMENT_SERVICE_NAME": "PAYMENT",
        "PAYMENT_BALANCE_DESCRIPTION": "PAYMENT",
        "PAYMENT_SUBSCRIPTION_DESCRIPTION": "PAYMENT",
        "PAYMENT_BALANCE_TEMPLATE": "PAYMENT",
        "PAYMENT_SUBSCRIPTION_TEMPLATE": "PAYMENT",
        "AUTO_PURCHASE_AFTER_TOPUP_ENABLED": "PAYMENT",
        "SIMPLE_SUBSCRIPTION_ENABLED": "SIMPLE_SUBSCRIPTION",
        "SIMPLE_SUBSCRIPTION_PERIOD_DAYS": "SIMPLE_SUBSCRIPTION",
        "SIMPLE_SUBSCRIPTION_DEVICE_LIMIT": "SIMPLE_SUBSCRIPTION",
        "SIMPLE_SUBSCRIPTION_TRAFFIC_GB": "SIMPLE_SUBSCRIPTION",
        "SIMPLE_SUBSCRIPTION_SQUAD_UUID": "SIMPLE_SUBSCRIPTION",
        "DISABLE_TOPUP_BUTTONS": "PAYMENT",
        "SUPPORT_TOPUP_ENABLED": "PAYMENT",
        "ENABLE_NOTIFICATIONS": "NOTIFICATIONS",
        "NOTIFICATION_RETRY_ATTEMPTS": "NOTIFICATIONS",
        "NOTIFICATION_CACHE_HOURS": "NOTIFICATIONS",
        "MONITORING_LOGS_RETENTION_DAYS": "MONITORING",
        "MONITORING_INTERVAL": "MONITORING",
        "ENABLE_LOGO_MODE": "INTERFACE_BRANDING",
        "LOGO_FILE": "INTERFACE_BRANDING",
        "HIDE_SUBSCRIPTION_LINK": "INTERFACE_SUBSCRIPTION",
        "MAIN_MENU_MODE": "INTERFACE",
        "CONNECT_BUTTON_MODE": "CONNECT_BUTTON",
        "MINIAPP_CUSTOM_URL": "CONNECT_BUTTON",
        "APP_CONFIG_PATH": "ADDITIONAL",
        "ENABLE_DEEP_LINKS": "ADDITIONAL",
        "APP_CONFIG_CACHE_TTL": "ADDITIONAL",
        "INACTIVE_USER_DELETE_MONTHS": "MAINTENANCE",
        "MAINTENANCE_MESSAGE": "MAINTENANCE",
        "MAINTENANCE_CHECK_INTERVAL": "MAINTENANCE",
        "MAINTENANCE_AUTO_ENABLE": "MAINTENANCE",
        "MAINTENANCE_RETRY_ATTEMPTS": "MAINTENANCE",
        "WEBHOOK_URL": "WEBHOOK",
        "WEBHOOK_SECRET": "WEBHOOK",
        "VERSION_CHECK_ENABLED": "VERSION",
        "VERSION_CHECK_REPO": "VERSION",
        "VERSION_CHECK_INTERVAL_HOURS": "VERSION",
        "TELEGRAM_STARS_RATE_RUB": "TELEGRAM",
        "REMNAWAVE_USER_DESCRIPTION_TEMPLATE": "REMNAWAVE",
        "REMNAWAVE_USER_USERNAME_TEMPLATE": "REMNAWAVE",
        "REMNAWAVE_AUTO_SYNC_ENABLED": "REMNAWAVE",
        "REMNAWAVE_AUTO_SYNC_TIMES": "REMNAWAVE",
    }

    CATEGORY_PREFIX_OVERRIDES: Dict[str, str] = {
        "SUPPORT_": "SUPPORT",
        "ADMIN_NOTIFICATIONS": "ADMIN_NOTIFICATIONS",
        "ADMIN_REPORTS": "ADMIN_REPORTS",
        "CHANNEL_": "CHANNEL",
        "POSTGRES_": "POSTGRES",
        "SQLITE_": "SQLITE",
        "REDIS_": "REDIS",
        "REMNAWAVE": "REMNAWAVE",
        "TRIAL_": "TRIAL",
        "TRAFFIC_PACKAGES": "TRAFFIC_PACKAGES",
        "PRICE_TRAFFIC": "TRAFFIC_PACKAGES",
        "TRAFFIC_": "TRAFFIC",
        "REFERRAL_": "REFERRAL",
        "AUTOPAY_": "AUTOPAY",
        "TELEGRAM_STARS": "TELEGRAM",
        "TRIBUTE_": "TRIBUTE",
        "YOOKASSA_": "YOOKASSA",
        "CRYPTOBOT_": "CRYPTOBOT",
        "HELEKET_": "HELEKET",
        "PLATEGA_": "PLATEGA",
        "MULENPAY_": "MULENPAY",
        "PAL24_": "PAL24",
        "PAYMENT_": "PAYMENT",
        "PAYMENT_VERIFICATION_": "PAYMENT_VERIFICATION",
        "WATA_": "WATA",
        "EXTERNAL_ADMIN_": "EXTERNAL_ADMIN",
        "SIMPLE_SUBSCRIPTION_": "SIMPLE_SUBSCRIPTION",
        "CONNECT_BUTTON_HAPP": "HAPP",
        "HAPP_": "HAPP",
        "SKIP_": "SKIP",
        "MINIAPP_": "MINIAPP",
        "MONITORING_": "MONITORING",
        "NOTIFICATION_": "NOTIFICATIONS",
        "SERVER_STATUS": "SERVER_STATUS",
        "MAINTENANCE_": "MAINTENANCE",
        "VERSION_CHECK": "VERSION",
        "BACKUP_": "BACKUP",
        "WEBHOOK_": "WEBHOOK",
        "LOG_": "LOG",
        "WEB_API_": "WEB_API",
        "DEBUG": "DEBUG",
        "DISPLAY_NAME_": "MODERATION",
    }

    CHOICES: Dict[str, List[ChoiceOption]] = {
        "DATABASE_MODE": [
            ChoiceOption("auto", "🤖 Auto"),
            ChoiceOption("postgresql", "🐘 PostgreSQL"),
            ChoiceOption("sqlite", "💾 SQLite"),
        ],
        "REMNAWAVE_AUTH_TYPE": [
            ChoiceOption("api_key", "🔑 API Key"),
            ChoiceOption("basic_auth", "🧾 Basic Auth"),
        ],
        "REMNAWAVE_USER_DELETE_MODE": [
            ChoiceOption("delete", "🗑 Delete"),
            ChoiceOption("disable", "🚫 Disable"),
        ],
        "TRAFFIC_SELECTION_MODE": [
            ChoiceOption("selectable", "📦 Package selection"),
            ChoiceOption("fixed", "📏 Fixed limit"),
        ],
        "DEFAULT_TRAFFIC_RESET_STRATEGY": [
            ChoiceOption("NO_RESET", "♾️ No reset"),
            ChoiceOption("DAY", "📅 Daily"),
            ChoiceOption("WEEK", "🗓 Weekly"),
            ChoiceOption("MONTH", "📆 Monthly"),
        ],
        "SUPPORT_SYSTEM_MODE": [
            ChoiceOption("tickets", "🎫 Tickets only"),
            ChoiceOption("contact", "💬 Contact only"),
            ChoiceOption("both", "🔁 Both options"),
        ],
        "CONNECT_BUTTON_MODE": [
            ChoiceOption("guide", "📘 Guide"),
            ChoiceOption("miniapp_subscription", "🧾 Mini App subscription"),
            ChoiceOption("miniapp_custom", "🧩 Mini App (link)"),
            ChoiceOption("link", "🔗 Direct link"),
            ChoiceOption("happ_cryptolink", "🪙 Happ CryptoLink"),
        ],
        "MAIN_MENU_MODE": [
            ChoiceOption("default", "📋 Full menu"),
            ChoiceOption("text", "📝 Text menu"),
        ],
        "SERVER_STATUS_MODE": [
            ChoiceOption("disabled", "🚫 Disabled"),
            ChoiceOption("external_link", "🌐 External link"),
            ChoiceOption("external_link_miniapp", "🧭 Mini App link"),
            ChoiceOption("xray", "📊 XRay Checker"),
        ],
        "YOOKASSA_PAYMENT_MODE": [
            ChoiceOption("full_payment", "💳 Full payment"),
            ChoiceOption("partial_payment", "🪙 Partial payment"),
            ChoiceOption("advance", "💼 Advance"),
            ChoiceOption("full_prepayment", "📦 Full prepayment"),
            ChoiceOption("partial_prepayment", "📦 Partial prepayment"),
            ChoiceOption("credit", "💰 Credit"),
            ChoiceOption("credit_payment", "💸 Credit payment"),
        ],
        "YOOKASSA_PAYMENT_SUBJECT": [
            ChoiceOption("commodity", "📦 Commodity"),
            ChoiceOption("excise", "🥃 Excise goods"),
            ChoiceOption("job", "🛠 Job"),
            ChoiceOption("service", "🧾 Service"),
            ChoiceOption("gambling_bet", "🎲 Bet"),
            ChoiceOption("gambling_prize", "🏆 Prize"),
            ChoiceOption("lottery", "🎫 Lottery"),
            ChoiceOption("lottery_prize", "🎁 Lottery prize"),
            ChoiceOption("intellectual_activity", "🧠 Intellectual activity"),
            ChoiceOption("payment", "💱 Payment"),
            ChoiceOption("agent_commission", "🤝 Agent commission"),
            ChoiceOption("composite", "🧩 Composite"),
            ChoiceOption("another", "📄 Other"),
        ],
        "YOOKASSA_VAT_CODE": [
            ChoiceOption(1, "1 — VAT exempt"),
            ChoiceOption(2, "2 — VAT 0%"),
            ChoiceOption(3, "3 — VAT 10%"),
            ChoiceOption(4, "4 — VAT 20%"),
            ChoiceOption(5, "5 — VAT 10/110"),
            ChoiceOption(6, "6 — VAT 20/120"),
        ],
        "MULENPAY_LANGUAGE": [
            ChoiceOption("ru", "🇷🇺 Russian"),
            ChoiceOption("en", "🇬🇧 English"),
        ],
        "LOG_LEVEL": [
            ChoiceOption("DEBUG", "🐞 Debug"),
            ChoiceOption("INFO", "ℹ️ Info"),
            ChoiceOption("WARNING", "⚠️ Warning"),
            ChoiceOption("ERROR", "❌ Error"),
            ChoiceOption("CRITICAL", "🔥 Critical"),
        ],
    }

    SETTING_HINTS: Dict[str, Dict[str, str]] = {
        "YOOKASSA_ENABLED": {
            "description": (
                "Enables payment via YooKassa. "
                "Requires correct shop identifiers and secret key."
            ),
            "format": "Boolean value: select \"Enable\" or \"Disable\".",
            "example": "Enabled when integration is fully configured.",
            "warning": "If enabled without Shop ID and Secret Key, users will see errors during payment.",
            "dependencies": "YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, YOOKASSA_RETURN_URL",
        },
        "SIMPLE_SUBSCRIPTION_ENABLED": {
            "description": "Shows a menu item for quick subscription purchase.",
            "format": "Boolean value.",
            "example": "true",
            "warning": "If unconfigured parameters remain, the offer may behave incorrectly.",
        },
        "SIMPLE_SUBSCRIPTION_PERIOD_DAYS": {
            "description": "Subscription period offered for quick purchase.",
            "format": "Select one of the available periods.",
            "example": "30 days — 990 ₽",
            "warning": "Don't forget to configure the period price in the \"Plan pricing\" section.",
        },
        "SIMPLE_SUBSCRIPTION_DEVICE_LIMIT": {
            "description": "Number of devices the user will receive with the subscription via quick purchase.",
            "format": "Select number of devices.",
            "example": "2 devices",
            "warning": "Value must not exceed the allowed limit in subscription settings.",
        },
        "SIMPLE_SUBSCRIPTION_TRAFFIC_GB": {
            "description": "Traffic volume included in simple subscription (0 = unlimited).",
            "format": "Select traffic package.",
            "example": "Unlimited",
        },
        "SIMPLE_SUBSCRIPTION_SQUAD_UUID": {
            "description": (
                "Binding quick subscription to a specific squad. "
                "Leave empty for any available server."
            ),
            "format": "Select squad from list or clear value.",
            "example": "d4aa2b8c-9a36-4f31-93a2-6f07dad05fba",
            "warning": "Ensure the selected squad is active and available for subscription.",
        },
        "DEVICES_SELECTION_ENABLED": {
            "description": "Allows users to select number of devices when purchasing and renewing subscription.",
            "format": "Boolean value.",
            "example": "false",
            "warning": "When disabled, users won't be able to purchase additional devices from bot interface.",
        },
        "DEVICES_SELECTION_DISABLED_AMOUNT": {
            "description": (
                "Device limit automatically assigned when device selection is disabled. "
                "Value 0 disables device assignment."
            ),
            "format": "Integer from 0 and above.",
            "example": "3",
            "warning": "At 0, RemnaWave won't receive device limit, numbers won't be shown to users in interface.",
        },
        "CRYPTOBOT_ENABLED": {
            "description": "Allows accepting cryptocurrency payments via CryptoBot.",
            "format": "Boolean value.",
            "example": "Enable after specifying API token and webhook secret.",
            "warning": "Empty token or invalid webhook will cause payment failures.",
            "dependencies": "CRYPTOBOT_API_TOKEN, CRYPTOBOT_WEBHOOK_SECRET",
        },
        "PAYMENT_VERIFICATION_AUTO_CHECK_ENABLED": {
            "description": (
                "Starts background verification of pending top-ups and re-checks "
                "payment providers without administrator involvement."
            ),
            "format": "Boolean value.",
            "example": "Enabled to automatically re-check stuck payments.",
            "warning": "Requires active integrations: YooKassa, {mulenpay_name}, PayPalych, WATA or CryptoBot.",
        },
        "PAYMENT_VERIFICATION_AUTO_CHECK_INTERVAL_MINUTES": {
            "description": (
                "Interval between automatic checks of pending top-ups in minutes."
            ),
            "format": "Integer not less than 1.",
            "example": "10",
            "warning": "Too small interval may lead to frequent calls to payment APIs.",
            "dependencies": "PAYMENT_VERIFICATION_AUTO_CHECK_ENABLED",
        },
        "BASE_PROMO_GROUP_PERIOD_DISCOUNTS_ENABLED": {
            "description": (
                "Enables application of base discounts on subscription periods in group promos."
            ),
            "format": "Boolean value.",
            "example": "true",
            "warning": "Discounts are applied only if correct period and percentage pairs are specified.",
        },
        "BASE_PROMO_GROUP_PERIOD_DISCOUNTS": {
            "description": (
                "List of discounts for groups: each pair sets period days and discount percentage."
            ),
            "format": "Comma-separated pairs in format &lt;days&gt;:&lt;discount&gt;.",
            "example": "30:10,60:20,90:30,180:50,360:65",
            "warning": "Invalid entries will be ignored. Percentage limited to 0-100.",
        },
        "AUTO_PURCHASE_AFTER_TOPUP_ENABLED": {
            "description": (
                "With sufficient balance, automatically processes saved subscription immediately after top-up."
            ),
            "format": "Boolean value.",
            "example": "true",
            "warning": (
                "Use with caution: funds will be debited instantly if cart is found."
            ),
        },
        "SUPPORT_TICKET_SLA_MINUTES": {
            "description": "Time limit for moderators to respond to ticket in minutes.",
            "format": "Integer from 1 to 1440.",
            "example": "5",
            "warning": "Too low value may cause frequent reminders, too high — worsen SLA.",
            "dependencies": "SUPPORT_TICKET_SLA_ENABLED, SUPPORT_TICKET_SLA_REMINDER_COOLDOWN_MINUTES",
        },
        "MAINTENANCE_MODE": {
            "description": "Puts bot in maintenance mode and hides actions from users.",
            "format": "Boolean value.",
            "example": "Enabled during scheduled work.",
            "warning": "Don't forget to disable after work completion, otherwise bot will remain unavailable.",
            "dependencies": "MAINTENANCE_MESSAGE, MAINTENANCE_CHECK_INTERVAL",
        },
        "MAINTENANCE_MONITORING_ENABLED": {
            "description": (
                "Controls automatic startup of Remnawave panel monitoring when bot starts."
            ),
            "format": "Boolean value.",
            "example": "false",
            "warning": (
                "When disabled, monitoring can be started manually from admin panel."
            ),
            "dependencies": "MAINTENANCE_CHECK_INTERVAL",
        },
        "MAINTENANCE_RETRY_ATTEMPTS": {
            "description": (
                "How many times to retry Remnawave panel check before marking as unavailable."
            ),
            "format": "Integer not less than 1.",
            "example": "3",
            "warning": (
                "Large values increase reaction time to real failures, but help avoid false positives."
            ),
            "dependencies": "MAINTENANCE_CHECK_INTERVAL",
        },
        "DISPLAY_NAME_BANNED_KEYWORDS": {
            "description": (
                "List of words and fragments that, if present in display name, "
                "will result in user being blocked."
            ),
            "format": "List keywords separated by comma or newline.",
            "example": "support, security, service",
            "warning": "Too aggressive filters may block legitimate users.",
            "dependencies": "Display name filter",
        },
        "REMNAWAVE_API_URL": {
            "description": "Base address of RemnaWave panel that bot synchronizes with.",
            "format": "Full URL like https://panel.example.com.",
            "example": "https://panel.remnawave.net",
            "warning": "Unavailable address will cause errors when managing VPN accounts.",
            "dependencies": "REMNAWAVE_API_KEY or REMNAWAVE_USERNAME/REMNAWAVE_PASSWORD",
        },
        "REMNAWAVE_AUTO_SYNC_ENABLED": {
            "description": "Automatically starts synchronization of users and servers with RemnaWave panel.",
            "format": "Boolean value.",
            "example": "Enabled when API keys are correctly configured.",
            "warning": "If enabled without schedule, synchronization won't be executed.",
            "dependencies": "REMNAWAVE_AUTO_SYNC_TIMES",
        },
        "REMNAWAVE_AUTO_SYNC_TIMES": {
            "description": (
                "List of times in HH:MM format when auto-sync runs "
                "throughout the day."
            ),
            "format": "List times separated by comma or newline (e.g., 03:00, 15:00).",
            "example": "03:00, 15:00",
            "warning": (
                "Minimum interval between runs is not limited, but too frequent "
                "synchronizations load the panel."
            ),
            "dependencies": "REMNAWAVE_AUTO_SYNC_ENABLED",
        },
        "REMNAWAVE_USER_DESCRIPTION_TEMPLATE": {
            "description": (
                "Text template that bot passes to Description field when creating "
                "or updating user in RemnaWave panel."
            ),
            "format": (
                "Available placeholders: {full_name}, {username}, {username_clean}, {telegram_id}."
            ),
            "example": "Bot user: {full_name} {username}",
            "warning": "Placeholder {username} is automatically cleared if user has no @username.",
        },
        "REMNAWAVE_USER_USERNAME_TEMPLATE": {
            "description": (
                "Username template created in RemnaWave panel for "
                "telegram user."
            ),
            "format": (
                "Available placeholders: {full_name}, {username}, {username_clean}, {telegram_id}."
            ),
            "example": "vpn_{username_clean}_{telegram_id}",
            "warning": (
                "Invalid characters are automatically replaced with underscores. "
                "If result is empty, user_{telegram_id} is used."
            ),
        },
        "EXTERNAL_ADMIN_TOKEN": {
            "description": "Private token used by external admin panel for request verification.",
            "format": "Value is automatically generated from bot username and token and is read-only.",
            "example": "Generated automatically",
            "warning": "Token will update when bot username or token changes.",
            "dependencies": "Telegram bot username, bot token",
        },
        "EXTERNAL_ADMIN_TOKEN_BOT_ID": {
            "description": "Telegram bot identifier associated with external admin token.",
            "format": "Set automatically after first startup and not edited manually.",
            "example": "123456789",
            "warning": "ID mismatch blocks token update, preventing substitution on another bot.",
            "dependencies": "Result of getMe() call in Telegram Bot API",
        },
    }

    @classmethod
    def get_category_description(cls, category_key: str) -> str:
        description = cls.CATEGORY_DESCRIPTIONS.get(category_key, "")
        return cls._format_dynamic_copy(category_key, description)

    @classmethod
    def is_toggle(cls, key: str) -> bool:
        definition = cls.get_definition(key)
        return definition.python_type is bool

    @classmethod
    def is_read_only(cls, key: str) -> bool:
        return key in cls.READ_ONLY_KEYS

    @classmethod
    def _is_env_override(cls, key: str) -> bool:
        return key in cls._env_override_keys

    @classmethod
    def _format_numeric_with_unit(cls, key: str, value: Union[int, float]) -> Optional[str]:
        if isinstance(value, bool):
            return None
        upper_key = key.upper()
        if any(suffix in upper_key for suffix in ("PRICE", "_KOPEKS", "AMOUNT")):
            try:
                return settings.format_price(int(value))
            except Exception:
                return f"{value}"
        if upper_key.endswith("_PERCENT") or "PERCENT" in upper_key:
            return f"{value}%"
        if upper_key.endswith("_HOURS"):
            return f"{value} h"
        if upper_key.endswith("_MINUTES"):
            return f"{value} min"
        if upper_key.endswith("_SECONDS"):
            return f"{value} sec"
        if upper_key.endswith("_DAYS"):
            return f"{value} days"
        if upper_key.endswith("_GB"):
            return f"{value} GB"
        if upper_key.endswith("_MB"):
            return f"{value} MB"
        return None

    @classmethod
    def _split_comma_values(cls, text: str) -> Optional[List[str]]:
        raw = (text or "").strip()
        if not raw or "," not in raw:
            return None
        parts = [segment.strip() for segment in raw.split(",") if segment.strip()]
        return parts or None

    @classmethod
    def format_value_human(cls, key: str, value: Any) -> str:
        if key == "SIMPLE_SUBSCRIPTION_SQUAD_UUID":
            if value is None:
                return "Any available"
            if isinstance(value, str):
                cleaned_value = value.strip()
                if not cleaned_value:
                    return "Any available"

        if value is None:
            return "—"

        if isinstance(value, bool):
            return "✅ ENABLED" if value else "❌ DISABLED"

        if isinstance(value, (int, float)):
            formatted = cls._format_numeric_with_unit(key, value)
            return formatted or str(value)

        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return "—"
            if key in cls.PLAIN_TEXT_KEYS:
                return cleaned
            if any(keyword in key.upper() for keyword in ("TOKEN", "SECRET", "PASSWORD", "KEY")):
                return "••••••••"
            items = cls._split_comma_values(cleaned)
            if items:
                return ", ".join(items)
            return cleaned

        if isinstance(value, (list, tuple, set)):
            return ", ".join(str(item) for item in value)

        if isinstance(value, dict):
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)

        return str(value)

    @classmethod
    def get_setting_guidance(cls, key: str) -> Dict[str, str]:
        definition = cls.get_definition(key)
        original = cls.get_original_value(key)
        type_label = definition.type_label
        hints = dict(cls.SETTING_HINTS.get(key, {}))

        base_description = (
            hints.get("description")
            or f"Parameter <b>{definition.display_name}</b> controls category «{definition.category_label}»."
        )
        base_format = hints.get("format") or (
            "Boolean value (yes/no)." if definition.python_type is bool
            else "Enter value of appropriate type (number or string)."
        )
        example = hints.get("example") or (
            cls.format_value_human(key, original) if original is not None else "—"
        )
        warning = hints.get("warning") or (
            "Invalid values may lead to incorrect bot operation."
        )
        dependencies = hints.get("dependencies") or definition.category_label

        return {
            "description": base_description,
            "format": base_format,
            "example": example,
            "warning": warning,
            "dependencies": dependencies,
            "type": type_label,
        }

    _definitions: Dict[str, SettingDefinition] = {}
    _original_values: Dict[str, Any] = settings.model_dump()
    _overrides_raw: Dict[str, Optional[str]] = {}
    _env_override_keys: set[str] = set(ENV_OVERRIDE_KEYS)
    _callback_tokens: Dict[str, str] = {}
    _token_to_key: Dict[str, str] = {}
    _choice_tokens: Dict[str, Dict[Any, str]] = {}
    _choice_token_lookup: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def initialize_definitions(cls) -> None:
        if cls._definitions:
            return

        for key, field in Settings.model_fields.items():
            if key in cls.EXCLUDED_KEYS:
                continue

            annotation = field.annotation
            python_type, is_optional = cls._normalize_type(annotation)
            type_label = cls._type_to_label(python_type, is_optional)

            category_key = cls._resolve_category_key(key)
            category_label = cls.CATEGORY_TITLES.get(
                category_key,
                category_key.capitalize() if category_key else "Other",
            )
            category_label = cls._format_dynamic_copy(category_key, category_label)

            cls._definitions[key] = SettingDefinition(
                key=key,
                category_key=category_key or "other",
                category_label=category_label,
                python_type=python_type,
                type_label=type_label,
                is_optional=is_optional,
            )

            cls._register_callback_token(key)
            if key in cls.CHOICES:
                cls._ensure_choice_tokens(key)


    @classmethod
    def _resolve_category_key(cls, key: str) -> str:
        override = cls.CATEGORY_KEY_OVERRIDES.get(key)
        if override:
            return override

        for prefix, category in sorted(
            cls.CATEGORY_PREFIX_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if key.startswith(prefix):
                return category

        if "_" not in key:
            return key.upper()
        prefix = key.split("_", 1)[0]
        return prefix.upper()

    @classmethod
    def _normalize_type(cls, annotation: Any) -> Tuple[Type[Any], bool]:
        if annotation is None:
            return str, True

        origin = get_origin(annotation)
        if origin is Union:
            args = [arg for arg in get_args(annotation) if arg is not type(None)]
            if len(args) == 1:
                nested_type, nested_optional = cls._normalize_type(args[0])
                return nested_type, True
            return str, True

        if annotation in {int, float, bool, str}:
            return annotation, False

        if annotation in {Optional[int], Optional[float], Optional[bool], Optional[str]}:
            nested = get_args(annotation)[0]
            return nested, True

        # Paths, lists, dicts and other types will be stored as strings
        return str, False

    @classmethod
    def _type_to_label(cls, python_type: Type[Any], is_optional: bool) -> str:
        base = {
            bool: "bool",
            int: "int",
            float: "float",
            str: "str",
        }.get(python_type, "str")
        return f"optional[{base}]" if is_optional else base

    @classmethod
    def get_categories(cls) -> List[Tuple[str, str, int]]:
        cls.initialize_definitions()
        categories: Dict[str, List[SettingDefinition]] = {}

        for definition in cls._definitions.values():
            categories.setdefault(definition.category_key, []).append(definition)

        result: List[Tuple[str, str, int]] = []
        for category_key, items in categories.items():
            label = items[0].category_label
            result.append((category_key, label, len(items)))

        result.sort(key=lambda item: item[1])
        return result

    @classmethod
    def get_settings_for_category(cls, category_key: str) -> List[SettingDefinition]:
        cls.initialize_definitions()
        filtered = [
            definition
            for definition in cls._definitions.values()
            if definition.category_key == category_key
        ]
        filtered.sort(key=lambda definition: definition.key)
        return filtered

    @classmethod
    def get_definition(cls, key: str) -> SettingDefinition:
        cls.initialize_definitions()
        return cls._definitions[key]

    @classmethod
    def has_override(cls, key: str) -> bool:
        if cls._is_env_override(key):
            return False
        return key in cls._overrides_raw

    @classmethod
    def get_current_value(cls, key: str) -> Any:
        return getattr(settings, key)

    @classmethod
    def get_original_value(cls, key: str) -> Any:
        return cls._original_values.get(key)

    @classmethod
    def format_value(cls, value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, bool):
            return "✅ Yes" if value else "❌ No"
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (list, dict, tuple, set)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        return str(value)

    @classmethod
    def format_value_for_list(cls, key: str) -> str:
        value = cls.get_current_value(key)
        formatted = cls.format_value_human(key, value)
        if formatted == "—":
            return formatted
        return _truncate(formatted)

    @classmethod
    def get_choice_options(cls, key: str) -> List[ChoiceOption]:
        cls.initialize_definitions()
        dynamic = cls._get_dynamic_choice_options(key)
        if dynamic is not None:
            cls.CHOICES[key] = dynamic
            cls._invalidate_choice_cache(key)
            return dynamic
        return cls.CHOICES.get(key, [])

    @classmethod
    def _invalidate_choice_cache(cls, key: str) -> None:
        cls._choice_tokens.pop(key, None)
        cls._choice_token_lookup.pop(key, None)

    @classmethod
    def _get_dynamic_choice_options(cls, key: str) -> Optional[List[ChoiceOption]]:
        if key == "SIMPLE_SUBSCRIPTION_PERIOD_DAYS":
            return cls._build_simple_subscription_period_choices()
        if key == "SIMPLE_SUBSCRIPTION_DEVICE_LIMIT":
            return cls._build_simple_subscription_device_choices()
        if key == "SIMPLE_SUBSCRIPTION_TRAFFIC_GB":
            return cls._build_simple_subscription_traffic_choices()
        return None

    @staticmethod
    def _build_simple_subscription_period_choices() -> List[ChoiceOption]:
        raw_periods = str(getattr(settings, "AVAILABLE_SUBSCRIPTION_PERIODS", "") or "")
        period_values: set[int] = set()

        for segment in raw_periods.split(","):
            segment = segment.strip()
            if not segment:
                continue
            try:
                period = int(segment)
            except ValueError:
                continue
            if period > 0:
                period_values.add(period)

        fallback_period = getattr(settings, "SIMPLE_SUBSCRIPTION_PERIOD_DAYS", 30) or 30
        try:
            fallback_period = int(fallback_period)
        except (TypeError, ValueError):
            fallback_period = 30
        period_values.add(max(1, fallback_period))

        options: List[ChoiceOption] = []
        for days in sorted(period_values):
            price_attr = f"PRICE_{days}_DAYS"
            price_value = getattr(settings, price_attr, None)
            if not isinstance(price_value, int):
                price_value = settings.BASE_SUBSCRIPTION_PRICE

            label = f"{days} days"
            try:
                if isinstance(price_value, int):
                    label = f"{label} — {settings.format_price(price_value)}"
            except Exception:
                logger.debug("Failed to format price for period %s", days, exc_info=True)

            options.append(ChoiceOption(days, label))

        return options

    @classmethod
    def _build_simple_subscription_device_choices(cls) -> List[ChoiceOption]:
        default_limit = getattr(settings, "DEFAULT_DEVICE_LIMIT", 1) or 1
        try:
            default_limit = int(default_limit)
        except (TypeError, ValueError):
            default_limit = 1

        max_limit = getattr(settings, "MAX_DEVICES_LIMIT", default_limit) or default_limit
        try:
            max_limit = int(max_limit)
        except (TypeError, ValueError):
            max_limit = default_limit

        current_limit = getattr(settings, "SIMPLE_SUBSCRIPTION_DEVICE_LIMIT", default_limit) or default_limit
        try:
            current_limit = int(current_limit)
        except (TypeError, ValueError):
            current_limit = default_limit

        upper_bound = max(default_limit, max_limit, current_limit, 1)
        upper_bound = min(max(upper_bound, 1), 50)

        options: List[ChoiceOption] = []
        for count in range(1, upper_bound + 1):
            label = f"{count} {cls._pluralize_devices(count)}"
            if count == default_limit:
                label = f"{label} (default)"
            options.append(ChoiceOption(count, label))

        return options

    @staticmethod
    def _build_simple_subscription_traffic_choices() -> List[ChoiceOption]:
        try:
            packages = settings.get_traffic_packages()
        except Exception as error:
            logger.warning("Failed to get traffic packages: %s", error, exc_info=True)
            packages = []

        traffic_values: set[int] = {0}
        for package in packages:
            gb_value = package.get("gb")
            try:
                gb = int(gb_value)
            except (TypeError, ValueError):
                continue
            if gb >= 0:
                traffic_values.add(gb)

        default_limit = getattr(settings, "DEFAULT_TRAFFIC_LIMIT_GB", 0) or 0
        try:
            default_limit = int(default_limit)
        except (TypeError, ValueError):
            default_limit = 0
        if default_limit >= 0:
            traffic_values.add(default_limit)

        current_limit = getattr(settings, "SIMPLE_SUBSCRIPTION_TRAFFIC_GB", default_limit)
        try:
            current_limit = int(current_limit)
        except (TypeError, ValueError):
            current_limit = default_limit
        if current_limit >= 0:
            traffic_values.add(current_limit)

        options: List[ChoiceOption] = []
        for gb in sorted(traffic_values):
            if gb <= 0:
                label = "Unlimited"
            else:
                label = f"{gb} GB"

            price_label = None
            for package in packages:
                try:
                    package_gb = int(package.get("gb"))
                except (TypeError, ValueError):
                    continue
                if package_gb != gb:
                    continue
                price_raw = package.get("price")
                try:
                    price_value = int(price_raw)
                    if price_value >= 0:
                        price_label = settings.format_price(price_value)
                except (TypeError, ValueError):
                    continue
                break

            if price_label:
                label = f"{label} — {price_label}"

            options.append(ChoiceOption(gb, label))

        return options

    @staticmethod
    def _pluralize_devices(count: int) -> str:
        count = abs(int(count))
        if count == 1:
            return "device"
        return "devices"

    @classmethod
    def has_choices(cls, key: str) -> bool:
        return bool(cls.get_choice_options(key))

    @classmethod
    def get_callback_token(cls, key: str) -> str:
        cls.initialize_definitions()
        return cls._callback_tokens[key]

    @classmethod
    def resolve_callback_token(cls, token: str) -> str:
        cls.initialize_definitions()
        return cls._token_to_key[token]

    @classmethod
    def get_choice_token(cls, key: str, value: Any) -> Optional[str]:
        cls.initialize_definitions()
        cls._ensure_choice_tokens(key)
        return cls._choice_tokens.get(key, {}).get(value)

    @classmethod
    def resolve_choice_token(cls, key: str, token: str) -> Any:
        cls.initialize_definitions()
        cls._ensure_choice_tokens(key)
        return cls._choice_token_lookup.get(key, {})[token]

    @classmethod
    def _register_callback_token(cls, key: str) -> None:
        if key in cls._callback_tokens:
            return

        base = hashlib.blake2s(key.encode("utf-8"), digest_size=6).hexdigest()
        candidate = base
        counter = 1
        while candidate in cls._token_to_key and cls._token_to_key[candidate] != key:
            suffix = cls._encode_base36(counter)
            candidate = f"{base}{suffix}"[:16]
            counter += 1

        cls._callback_tokens[key] = candidate
        cls._token_to_key[candidate] = key

    @classmethod
    def _ensure_choice_tokens(cls, key: str) -> None:
        if key in cls._choice_tokens:
            return

        options = cls.CHOICES.get(key, [])
        value_to_token: Dict[Any, str] = {}
        token_to_value: Dict[str, Any] = {}

        for index, option in enumerate(options):
            token = cls._encode_base36(index)
            value_to_token[option.value] = token
            token_to_value[token] = option.value

        cls._choice_tokens[key] = value_to_token
        cls._choice_token_lookup[key] = token_to_value

    @staticmethod
    def _encode_base36(number: int) -> str:
        if number < 0:
            raise ValueError("number must be non-negative")
        alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
        if number == 0:
            return "0"
        result = []
        while number:
            number, rem = divmod(number, 36)
            result.append(alphabet[rem])
        return "".join(reversed(result))

    @classmethod
    async def initialize(cls) -> None:
        cls.initialize_definitions()

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(SystemSetting))
            rows = result.scalars().all()

        overrides: Dict[str, Optional[str]] = {}
        for row in rows:
            if row.key in cls._definitions:
                overrides[row.key] = row.value

        for key, raw_value in overrides.items():
            if cls._is_env_override(key):
                logger.debug(
                    "Skipping setting %s from DB: using value from environment",
                    key,
                )
                continue
            try:
                parsed_value = cls.deserialize_value(key, raw_value)
            except Exception as error:
                logger.error("Failed to apply setting %s: %s", key, error)
                continue

            cls._overrides_raw[key] = raw_value
            cls._apply_to_settings(key, parsed_value)

        await cls._sync_default_web_api_token()

    @classmethod
    async def reload(cls) -> None:
        cls._overrides_raw.clear()
        await cls.initialize()

    @classmethod
    def deserialize_value(cls, key: str, raw_value: Optional[str]) -> Any:
        if raw_value is None:
            return None

        definition = cls.get_definition(key)
        python_type = definition.python_type

        if python_type is bool:
            value_lower = raw_value.strip().lower()
            if value_lower in {"1", "true", "on", "yes"}:
                return True
            if value_lower in {"0", "false", "off", "no"}:
                return False
            raise ValueError(f"Invalid boolean value: {raw_value}")

        if python_type is int:
            return int(raw_value)

        if python_type is float:
            return float(raw_value)

        return raw_value

    @classmethod
    def serialize_value(cls, key: str, value: Any) -> Optional[str]:
        if value is None:
            return None

        definition = cls.get_definition(key)
        python_type = definition.python_type

        if python_type is bool:
            return "true" if value else "false"
        if python_type in {int, float}:
            return str(value)
        return str(value)

    @classmethod
    def parse_user_value(cls, key: str, user_input: str) -> Any:
        definition = cls.get_definition(key)
        text = (user_input or "").strip()

        if text.lower() in {"cancel"}:
            raise ValueError("Input cancelled by user")

        if definition.is_optional and text.lower() in {"none", "null", ""}:
            return None

        python_type = definition.python_type

        if python_type is bool:
            lowered = text.lower()
            if lowered in {"1", "true", "on", "yes", "enable", "enabled"}:
                return True
            if lowered in {"0", "false", "off", "no", "disable", "disabled"}:
                return False
            raise ValueError("Enter 'true' or 'false' (or 'yes'/'no')")

        if python_type is int:
            parsed_value: Any = int(text)
        elif python_type is float:
            parsed_value = float(text.replace(",", "."))
        else:
            parsed_value = text

        choices = cls.get_choice_options(key)
        if choices:
            allowed_values = {option.value for option in choices}
            if python_type is str:
                lowered_map = {
                    str(option.value).lower(): option.value for option in choices
                }
                normalized = lowered_map.get(str(parsed_value).lower())
                if normalized is not None:
                    parsed_value = normalized
                elif parsed_value not in allowed_values:
                    readable = ", ".join(
                        f"{option.label} ({cls.format_value(option.value)})" for option in choices
                    )
                    raise ValueError(f"Available values: {readable}")
            elif parsed_value not in allowed_values:
                readable = ", ".join(
                    f"{option.label} ({cls.format_value(option.value)})" for option in choices
                )
                raise ValueError(f"Available values: {readable}")

        return parsed_value

    @classmethod
    async def set_value(
        cls,
        db: AsyncSession,
        key: str,
        value: Any,
        *,
        force: bool = False,
    ) -> None:
        if cls.is_read_only(key) and not force:
            raise ReadOnlySettingError(f"Setting {key} is read-only")

        raw_value = cls.serialize_value(key, value)
        await upsert_system_setting(db, key, raw_value)
        if cls._is_env_override(key):
            logger.info(
                "Setting %s saved to DB but not applied: value is set via environment",
                key,
            )
            cls._overrides_raw.pop(key, None)
        else:
            cls._overrides_raw[key] = raw_value
            cls._apply_to_settings(key, value)

        if key in {"WEB_API_DEFAULT_TOKEN", "WEB_API_DEFAULT_TOKEN_NAME"}:
            await cls._sync_default_web_api_token()

    @classmethod
    async def reset_value(
        cls,
        db: AsyncSession,
        key: str,
        *,
        force: bool = False,
    ) -> None:
        if cls.is_read_only(key) and not force:
            raise ReadOnlySettingError(f"Setting {key} is read-only")

        await delete_system_setting(db, key)
        cls._overrides_raw.pop(key, None)
        if cls._is_env_override(key):
            logger.info(
                "Setting %s reset in DB, using value from environment",
                key,
            )
        else:
            original = cls.get_original_value(key)
            cls._apply_to_settings(key, original)

        if key in {"WEB_API_DEFAULT_TOKEN", "WEB_API_DEFAULT_TOKEN_NAME"}:
            await cls._sync_default_web_api_token()

    @classmethod
    def _apply_to_settings(cls, key: str, value: Any) -> None:
        if cls._is_env_override(key):
            logger.debug(
                "Skipping application of setting %s: value is set via environment",
                key,
            )
            return
        try:
            setattr(settings, key, value)
            if key in {
                "PRICE_14_DAYS",
                "PRICE_30_DAYS",
                "PRICE_60_DAYS",
                "PRICE_90_DAYS",
                "PRICE_180_DAYS",
                "PRICE_360_DAYS",
            }:
                refresh_period_prices()
            elif key.startswith("PRICE_TRAFFIC_") or key == "TRAFFIC_PACKAGES_CONFIG":
                refresh_traffic_prices()
            elif key in {"REMNAWAVE_AUTO_SYNC_ENABLED", "REMNAWAVE_AUTO_SYNC_TIMES"}:
                try:
                    from app.services.remnawave_sync_service import remnawave_sync_service

                    remnawave_sync_service.schedule_refresh(
                        run_immediately=(key == "REMNAWAVE_AUTO_SYNC_ENABLED" and bool(value))
                    )
                except Exception as error:
                    logger.error(
                        "Failed to update RemnaWave auto-sync service: %s",
                        error,
                    )
            elif key in {
                "REMNAWAVE_API_URL",
                "REMNAWAVE_API_KEY",
                "REMNAWAVE_SECRET_KEY",
                "REMNAWAVE_USERNAME",
                "REMNAWAVE_PASSWORD",
                "REMNAWAVE_AUTH_TYPE",
            }:
                try:
                    from app.services.remnawave_sync_service import remnawave_sync_service

                    remnawave_sync_service.refresh_configuration()
                except Exception as error:
                    logger.error(
                        "Failed to update RemnaWave auto-sync service configuration: %s",
                        error,
                    )
        except Exception as error:
            logger.error("Failed to apply value %s=%s: %s", key, value, error)

    @staticmethod
    async def _sync_default_web_api_token() -> None:
        default_token = (settings.WEB_API_DEFAULT_TOKEN or "").strip()
        if not default_token:
            return

        success = await ensure_default_web_api_token()
        if not success:
            logger.warning(
                "Failed to synchronize web API bootstrap token after settings update",
            )

    @classmethod
    def get_setting_summary(cls, key: str) -> Dict[str, Any]:
        definition = cls.get_definition(key)
        current = cls.get_current_value(key)
        original = cls.get_original_value(key)
        has_override = cls.has_override(key)

        return {
            "key": key,
            "name": definition.display_name,
            "current": cls.format_value_human(key, current),
            "original": cls.format_value_human(key, original),
            "type": definition.type_label,
            "category_key": definition.category_key,
            "category_label": definition.category_label,
            "has_override": has_override,
            "is_read_only": cls.is_read_only(key),
        }


bot_configuration_service = BotConfigurationService
