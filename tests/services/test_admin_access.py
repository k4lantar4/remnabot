"""Tests for unified admin access (legacy ADMIN_IDS + RBAC)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services.admin_access_service import is_user_admin


def _user(*, user_id: int = 1, telegram_id: int = 100, email: str | None = None, email_verified: bool = False):
    user = MagicMock()
    user.id = user_id
    user.telegram_id = telegram_id
    user.email = email
    user.email_verified = email_verified
    return user


@pytest.mark.anyio
async def test_legacy_admin_by_telegram_id() -> None:
    user = _user(telegram_id=6371108688)
    db = AsyncMock()

    with patch.object(Settings, 'is_admin', return_value=True) as legacy:
        assert await is_user_admin(db, user) is True

    legacy.assert_called_once()
    db.execute.assert_not_called()


@pytest.mark.anyio
async def test_rbac_admin_without_legacy() -> None:
    user = _user(user_id=600, telegram_id=6371108688)
    db = AsyncMock()

    with (
        patch.object(Settings, 'is_admin', return_value=False),
        patch(
            'app.services.admin_access_service.UserRoleCRUD.get_user_permissions',
            new_callable=AsyncMock,
            return_value=([], ['Admin'], 100),
        ) as rbac,
    ):
        assert await is_user_admin(db, user) is True

    rbac.assert_awaited_once_with(db, 600)


@pytest.mark.anyio
async def test_non_admin_user() -> None:
    user = _user(user_id=42, telegram_id=999)
    db = AsyncMock()

    with (
        patch.object(Settings, 'is_admin', return_value=False),
        patch(
            'app.services.admin_access_service.UserRoleCRUD.get_user_permissions',
            new_callable=AsyncMock,
            return_value=([], [], 0),
        ),
    ):
        assert await is_user_admin(db, user) is False
