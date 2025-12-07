import logging
import re
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import (
    CallbackQuery,
    Message,
    PreCheckoutQuery,
    TelegramObject,
    User as TgUser,
)

from app.config import settings
from app.localization.texts import get_texts

logger = logging.getLogger(__name__)


ZERO_WIDTH_PATTERN = re.compile(r"[\u200B-\u200D\uFEFF]")

LINK_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"t\.me/\+",
        r"joinchat",
        r"https?://",
        r"www\.",
        r"tg://",
        r"telegram\.me",
        r"t\.me",
    )
]

# Pattern to detect obfuscated "t.me" domain variations using Cyrillic look-alikes.
# Cyrillic ranges: \u0430-\u044f (a-ya), \u0451 (yo)
# Cyrillic substitutes: \u0442 (te, looks like t), \u043c (em, looks like m), \u0435 (ie, looks like e)
DOMAIN_OBFUSCATION_PATTERN = re.compile(
    r"(?<![0-9a-z\u0430-\u044f\u0451])(?:t|\u0442)[\s\W_]*?(?:m|\u043c)(?:e|\u0435)",
    re.IGNORECASE,
)

# Translation table: Cyrillic characters that visually resemble Latin letters (homoglyphs).
# Used for spam detection to catch obfuscated links/usernames.
# Each key is a Cyrillic Unicode character mapped to its Latin look-alike.
CHAR_TRANSLATION = str.maketrans({
    "\u0430": "a",  # Cyrillic Small Letter A -> Latin a
    "\u0435": "e",  # Cyrillic Small Letter Ie -> Latin e
    "\u043e": "o",  # Cyrillic Small Letter O -> Latin o
    "\u0440": "p",  # Cyrillic Small Letter Er -> Latin p
    "\u0441": "c",  # Cyrillic Small Letter Es -> Latin c
    "\u0445": "x",  # Cyrillic Small Letter Ha -> Latin x
    "\u0443": "y",  # Cyrillic Small Letter U -> Latin y
    "\u043a": "k",  # Cyrillic Small Letter Ka -> Latin k
    "\u0442": "t",  # Cyrillic Small Letter Te -> Latin t
    "\u0433": "g",  # Cyrillic Small Letter Ghe -> Latin g
    "\u043c": "m",  # Cyrillic Small Letter Em -> Latin m
    "\u043d": "n",  # Cyrillic Small Letter En -> Latin n
    "\u043b": "l",  # Cyrillic Small Letter El -> Latin l
    "\u0456": "i",  # Cyrillic Small Letter Byelorussian-Ukrainian I -> Latin i
    "\u0457": "i",  # Cyrillic Small Letter Yi -> Latin i
    "\u0451": "e",  # Cyrillic Small Letter Io -> Latin e
    "\u044c": "",   # Cyrillic Small Letter Soft Sign -> removed
    "\u044a": "",   # Cyrillic Small Letter Hard Sign -> removed
    "\u045e": "u",  # Cyrillic Small Letter Short U -> Latin u
    "\uff20": "@",  # Fullwidth Commercial At -> ASCII @
})

COLLAPSE_PATTERN = re.compile(r"[\s\._\-/\\|,:;•·﹒․⋅··`~'\"!?()\[\]{}<>+=]+")

class DisplayNameRestrictionMiddleware(BaseMiddleware):
    """Blocks users whose display name imitates links or official accounts."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user: TgUser | None = None

        if isinstance(event, (Message, CallbackQuery, PreCheckoutQuery)):
            user = event.from_user

        if not user or user.is_bot:
            return await handler(event, data)

        display_name = self._build_display_name(user)
        username = user.username or ""

        display_suspicious = self._is_suspicious(display_name)
        username_suspicious = self._is_suspicious(username)

        if display_suspicious or username_suspicious:
            suspicious_value = display_name if display_suspicious else username
            language = self._resolve_language(user, data)
            texts = get_texts(language)
            warning = texts.get(
                "SUSPICIOUS_DISPLAY_NAME_BLOCKED",
                "🚫 Your display name looks like a link or service account. "
                "Please change your name and try again.",
            )

            logger.warning(
                "🚫 DisplayNameRestriction: user %s blocked due to suspicious name '%s'",
                user.id,
                suspicious_value,
            )

            if isinstance(event, Message):
                await event.answer(warning)
            elif isinstance(event, CallbackQuery):
                await event.answer(warning, show_alert=True)
            elif isinstance(event, PreCheckoutQuery):
                await event.answer(ok=False, error_message=warning)
            return None

        return await handler(event, data)

    @staticmethod
    def _build_display_name(user: TgUser) -> str:
        parts = [user.first_name or "", user.last_name or ""]
        return " ".join(part for part in parts if part).strip()

    @staticmethod
    def _resolve_language(user: TgUser, data: Dict[str, Any]) -> str:
        db_user = data.get("db_user")
        if db_user and getattr(db_user, "language", None):
            return db_user.language
        language_code = getattr(user, "language_code", None)
        return language_code or settings.DEFAULT_LANGUAGE

    def _is_suspicious(self, value: str) -> bool:
        if not value:
            return False

        cleaned = ZERO_WIDTH_PATTERN.sub("", value)
        lower_value = cleaned.lower()

        if "@" in cleaned or "＠" in cleaned:
            return True

        if any(pattern.search(lower_value) for pattern in LINK_PATTERNS):
            return True

        if DOMAIN_OBFUSCATION_PATTERN.search(lower_value):
            return True

        normalized = self._normalize_text(lower_value)
        collapsed = COLLAPSE_PATTERN.sub("", normalized)

        if "tme" in collapsed:
            return True

        banned_keywords = settings.get_display_name_banned_keywords()

        return any(
            keyword in normalized or keyword in collapsed
            for keyword in banned_keywords
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        return value.translate(CHAR_TRANSLATION)

