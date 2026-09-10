"""The cabinet email-login switch — one answer for the UI, the API and the provider list.

Adapted from upstream 23a58172 + fdebcad1. The admin toggle (PATCH
/cabinet/branding/email-auth) writes the ``CABINET_EMAIL_AUTH_ENABLED`` row in
system_settings and never touches ``settings`` in memory, which only knows the
environment. So the only honest answer to "is email login on" is: the DB row if
there is one, the environment otherwise. The public GET /cabinet/branding/email-auth
answers exactly that way, and the routes must decide the same way — otherwise the
button disappears while direct API requests still get through.
"""

from __future__ import annotations

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.system_setting import get_setting_value
from app.services.system_settings_service import BotConfigurationService


logger = structlog.get_logger(__name__)


EMAIL_AUTH_ENABLED_KEY = 'CABINET_EMAIL_AUTH_ENABLED'  # stored as "true" / "false" (or raw "1" from .env import)
EMAIL_AUTH_DISABLED_CODE = 'email_auth_disabled'


def _parse_stored_flag(stored: str) -> bool | None:
    """Same parser as the settings editor: the row is written by the admin toggle ('true'),
    by the editor, and by the .env-to-DB import (raw '1')."""
    try:
        return bool(BotConfigurationService.deserialize_value(EMAIL_AUTH_ENABLED_KEY, stored))
    except (ValueError, KeyError):
        logger.warning('Unreadable email-login flag in the DB, falling back to the environment', value=stored)
        return None


async def is_email_auth_enabled(db: AsyncSession) -> bool:
    """The system_settings row beats the environment."""
    stored = await get_setting_value(db, EMAIL_AUTH_ENABLED_KEY)
    parsed = _parse_stored_flag(stored) if stored is not None else None
    if parsed is not None:
        return parsed
    return settings.is_cabinet_email_auth_enabled()


async def require_email_auth_enabled(db: AsyncSession) -> None:
    """First step of every email/password route: before the rate limiter and the users table."""
    if await is_email_auth_enabled(db):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={'code': EMAIL_AUTH_DISABLED_CODE, 'message': 'Email authentication is disabled'},
    )
