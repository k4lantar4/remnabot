"""RemnaWave panel identity helpers — description merge and brand username."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings
    from app.database.models import Subscription, User

PANEL_NOTE_DELIMITER = '\n---\n'
MAX_PURCHASE_NOTE_LEN = 500
BRAND_PREFIX_PATTERN = re.compile(r'^[A-Za-z0-9_-]{3,20}$')


def sanitize_remnawave_username(value: str) -> str:
    result = re.sub(r'[^0-9A-Za-z_-]+', '_', value)
    return re.sub(r'_+', '_', result).strip('_-')


def build_panel_description(*, auto_description: str, purchase_note: str | None) -> str:
    note = (purchase_note or '').strip()
    if not note:
        return auto_description
    note = note[:MAX_PURCHASE_NOTE_LEN]
    return f'{auto_description}{PANEL_NOTE_DELIMITER}{note}'


def parse_purchase_note_from_panel_description(full: str | None) -> str | None:
    if not full or PANEL_NOTE_DELIMITER not in full:
        return None
    parsed = full.split(PANEL_NOTE_DELIMITER, 1)[1].strip()
    return parsed or None


def resolve_remnawave_panel_description(
    settings: Settings,
    *,
    user: User,
    subscription: Subscription | None = None,
) -> str:
    auto = settings.format_remnawave_user_description(
        full_name=user.full_name,
        username=user.username,
        telegram_id=user.telegram_id,
        email=user.email,
        user_id=user.id,
    )
    purchase_note = getattr(subscription, 'purchase_note', None) if subscription else None
    return build_panel_description(auto_description=auto, purchase_note=purchase_note)


def build_subscription_panel_username(
    settings: Settings,
    user: User,
    *,
    suffix: str,
    use_brand_prefix: bool = True,
) -> str:
    prefix = (getattr(user, 'panel_brand_prefix', None) or '').strip()
    if use_brand_prefix and prefix and getattr(user, 'is_partner', False):
        sanitized = sanitize_remnawave_username(prefix)
        if sanitized and len(sanitized) >= settings.REMNAWAVE_USERNAME_MIN_LENGTH:
            result = f'{sanitized}{suffix}'
            if len(result) > settings.REMNAWAVE_USERNAME_MAX_LENGTH:
                keep_for_base = max(0, settings.REMNAWAVE_USERNAME_MAX_LENGTH - len(suffix))
                result = f'{sanitized[:keep_for_base].rstrip("_-")}{suffix}'
            result = result[: settings.REMNAWAVE_USERNAME_MAX_LENGTH]
            if len(result) >= settings.REMNAWAVE_USERNAME_MIN_LENGTH:
                return result

    return settings.build_remnawave_subscription_username(
        full_name=user.full_name,
        username=user.username,
        telegram_id=user.telegram_id,
        email=user.email,
        user_id=user.id,
        suffix=suffix,
    )


def validate_brand_prefix(value: str) -> str | None:
    """Return sanitized prefix or None if invalid."""
    cleaned = (value or '').strip()
    if not cleaned or not BRAND_PREFIX_PATTERN.match(cleaned):
        return None
    return cleaned
