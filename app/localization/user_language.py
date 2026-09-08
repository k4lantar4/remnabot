"""Resolve effective user-facing locale when language selection is disabled."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.config import settings
from app.localization.loader import DEFAULT_LANGUAGE

if TYPE_CHECKING:
    from app.database.models import User


def normalize_language_code(language: str | None) -> str:
    if not language or not str(language).strip():
        return DEFAULT_LANGUAGE
    return str(language).strip().lower().split('-')[0]


def resolve_user_facing_language(stored_language: str | None) -> str:
    """Return locale for user-facing bot UI when selection may be disabled."""
    if settings.is_language_selection_enabled():
        return normalize_language_code(stored_language)

    configured = getattr(settings, 'DEFAULT_LANGUAGE', None) or DEFAULT_LANGUAGE
    if not isinstance(configured, str):
        configured = DEFAULT_LANGUAGE
    return normalize_language_code(configured)


def apply_forced_user_language(user: User) -> bool:
    """Align ``user.language`` with the effective locale when selection is disabled."""
    effective = resolve_user_facing_language(user.language)
    if user.language == effective:
        return False
    user.language = effective
    return True


def mark_user_language_synced(user: User) -> None:
    """Update profile timestamps after a forced language correction."""
    user.updated_at = datetime.now(UTC)
