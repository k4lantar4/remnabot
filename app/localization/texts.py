from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from app.config import settings
from app.localization.loader import (
    DEFAULT_LANGUAGE,
    clear_locale_cache,
    load_locale,
)

_logger = logging.getLogger(__name__)

_cached_rules: Dict[str, str] = {}


# This mapping defines which setting attribute corresponds to which traffic tier key.
# The format strings (patterns) will now be fetched from the locale files or default to English.
_TRAFFIC_TIERS = (
    ("TRAFFIC_5GB", "5", "PRICE_TRAFFIC_5GB"),
    ("TRAFFIC_10GB", "10", "PRICE_TRAFFIC_10GB"),
    ("TRAFFIC_25GB", "25", "PRICE_TRAFFIC_25GB"),
    ("TRAFFIC_50GB", "50", "PRICE_TRAFFIC_50GB"),
    ("TRAFFIC_100GB", "100", "PRICE_TRAFFIC_100GB"),
    ("TRAFFIC_250GB", "250", "PRICE_TRAFFIC_250GB"),
)


def _get_cached_rules_value(language: str) -> str:
    if language in _cached_rules:
        return _cached_rules[language]

    default = _get_default_rules(language)
    _cached_rules[language] = default
    return default


class Texts:
    def __init__(self, language: str = DEFAULT_LANGUAGE):
        self.language = language or DEFAULT_LANGUAGE
        
        # Load raw data from JSON/YAML
        raw_data = load_locale(self.language)
        self._values = {key: value for key, value in raw_data.items()}

        # Load fallback data (English) if current language is not default
        if self.language != DEFAULT_LANGUAGE:
            fallback_data = load_locale(DEFAULT_LANGUAGE)
        else:
            fallback_data = self._values

        self._fallback_values = {
            key: value for key, value in fallback_data.items() if key not in self._values
        }

        # Inject dynamic values (Traffic prices, Support info, etc.)
        self._inject_dynamic_values()

    def _inject_dynamic_values(self) -> None:
        """
        Calculates dynamic text values based on patterns found in the locale
        or uses English defaults if patterns are missing.
        """
        # 1. Traffic Patterns
        # Try to get the pattern from locale, otherwise use English default
        traffic_pattern = self.get("TRAFFIC_PATTERN_TEMPLATE", "📊 {size} GB - {price}")
        
        for key, size, price_attr in _TRAFFIC_TIERS:
            price_value = getattr(settings, price_attr, 0)
            self._values[key] = traffic_pattern.format(
                size=size,
                price=settings.format_price(price_value),
            )

        # 2. Unlimited Traffic Pattern
        unlimited_pattern = self.get("UNLIMITED_PATTERN_TEMPLATE", "📊 Unlimited - {price}")
        self._values["TRAFFIC_UNLIMITED"] = unlimited_pattern.format(
            price=settings.format_price(settings.PRICE_TRAFFIC_UNLIMITED)
        )

        # 3. Support Info
        # Default English Support Template
        default_support = (
            "\n🛟 <b>Support Center</b>\n\n"
            "Create a ticket for any inquiries:\n\n"
            "• 🎫 Create Ticket — Describe your issue\n"
            "• 📋 My Tickets — View history\n"
            "• 💬 Contact — Direct message (if urgent)\n"
        )
        
        support_template = self.get("SUPPORT_INFO_TEMPLATE", default_support)
        
        # Format if the template expects a username placeholder
        try:
            # Check if {support_username} is present in the string to avoid KeyError
            if "{support_username}" in support_template:
                self._values["SUPPORT_INFO"] = support_template.format(
                    support_username=settings.SUPPORT_USERNAME
                )
            else:
                self._values["SUPPORT_INFO"] = support_template
        except Exception as e:
            _logger.warning(f"Failed to format SUPPORT_INFO for {self.language}: {e}")
            self._values["SUPPORT_INFO"] = support_template

    def __getattr__(self, item: str) -> Any:
        if item == "language":
            return super().__getattribute__(item)
        try:
            return self._get_value(item)
        except KeyError as error:
            raise AttributeError(item) from error

    def __getitem__(self, item: str) -> Any:
        return self._get_value(item)

    def get(self, item: str, default: Any = None) -> Any:
        try:
            return self._get_value(item)
        except KeyError:
            return default

    def get_text(self, key: str, default: Any = None) -> Any:
        """
        Public alias for t(), kept for readability at call sites.
        """
        return self.t(key, default)

    def t(self, key: str, default: Any = None) -> Any:
        try:
            return self._get_value(key)
        except KeyError:
            if default is not None:
                return default
            # If no default provided, return the key itself or raise
            # Returning key helps debugging missing translations
            return key 

    def _get_value(self, item: str) -> Any:
        if item == "RULES_TEXT":
            return _get_cached_rules_value(self.language)

        if item in self._values:
            return self._values[item]

        if item in self._fallback_values:
            return self._fallback_values[item]

        # Explicitly checking for missing keys to log warnings
        # _logger.warning("Missing localization key '%s' for language '%s'", item, self.language)
        raise KeyError(item)

    @staticmethod
    def format_price(kopeks: int) -> str:
        return settings.format_price(kopeks)

    @staticmethod
    def format_traffic(gb: float) -> str:
        if gb == 0:
            return "∞ (Unlimited)"
        if gb >= 1024:
            return f"{gb / 1024:.1f} TB"
        return f"{gb:.0f} GB"


def get_texts(language: str = DEFAULT_LANGUAGE) -> Texts:
    return Texts(language)


async def get_rules_from_db(language: str = DEFAULT_LANGUAGE) -> str:
    try:
        from app.database.database import get_db
        from app.database.crud.rules import get_current_rules_content

        async for db in get_db():
            rules = await get_current_rules_content(db, language)
            if rules:
                _cached_rules[language] = rules
                return rules
            break

    except Exception as error:
        _logger.warning("Failed to load rules from DB for %s: %s", language, error)

    default = _get_default_rules(language)
    _cached_rules[language] = default
    return default


def _get_default_rules(language: str = DEFAULT_LANGUAGE) -> str:
    default_key = "RULES_TEXT_DEFAULT"
    locale = load_locale(language)
    if default_key in locale:
        return locale[default_key]
    fallback = load_locale(DEFAULT_LANGUAGE)
    return fallback.get(default_key, "")


def _get_default_privacy_policy(language: str = DEFAULT_LANGUAGE) -> str:
    default_key = "PRIVACY_POLICY_TEXT_DEFAULT"
    locale = load_locale(language)
    if default_key in locale:
        return locale[default_key]
    fallback = load_locale(DEFAULT_LANGUAGE)
    return fallback.get(default_key, "")


def get_privacy_policy(language: str = DEFAULT_LANGUAGE) -> str:
    return _get_default_privacy_policy(language)


def get_rules_sync(language: str = DEFAULT_LANGUAGE) -> str:
    if language in _cached_rules:
        return _cached_rules[language]

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(get_rules(language))

    loop.create_task(get_rules(language))
    return _get_cached_rules_value(language)


async def get_rules(language: str = DEFAULT_LANGUAGE) -> str:
    if language in _cached_rules:
        return _cached_rules[language]

    return await get_rules_from_db(language)


async def refresh_rules_cache(language: str = DEFAULT_LANGUAGE) -> None:
    if language in _cached_rules:
        del _cached_rules[language]
    await get_rules_from_db(language)


def clear_rules_cache() -> None:
    _cached_rules.clear()


def reload_locales() -> None:
    clear_locale_cache()