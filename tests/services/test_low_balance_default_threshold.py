"""Default low-balance alert threshold is 100,000 Toman (user ruling 2026-09-11).

The old default of 100 was a leftover from the kopek scale: compared 1:1 with a Toman
balance it never fired. Only users who never saved a threshold get the new default;
a stored number is kept as is.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.cabinet.routes.notifications import (
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
    get_notification_settings,
    update_notification_settings,
)
from app.utils.notification_prefs import get_balance_low_threshold


DEFAULT_TOMAN = 100_000


def _user(notification_settings: dict | None) -> SimpleNamespace:
    return SimpleNamespace(id=1, language='fa', balance_kopeks=50_000, notification_settings=notification_settings)


@pytest.mark.parametrize('stored', [None, {}, {'balance_low_enabled': True}])
def test_unset_threshold_resolves_to_100000_toman(stored) -> None:
    assert get_balance_low_threshold(_user(stored)) == DEFAULT_TOMAN


def test_unparseable_threshold_falls_back_to_100000_toman() -> None:
    assert get_balance_low_threshold(_user({'balance_low_threshold': 'abc'})) == DEFAULT_TOMAN


def test_stored_threshold_keeps_its_number() -> None:
    assert get_balance_low_threshold(_user({'balance_low_threshold': 100})) == 100
    assert get_balance_low_threshold(_user({'balance_low_threshold': 250_000})) == 250_000


def test_schema_default_is_100000_toman() -> None:
    assert NotificationSettingsResponse().balance_low_threshold == DEFAULT_TOMAN


@pytest.mark.parametrize('stored', [None, {}])
def test_cabinet_get_returns_100000_for_unset_threshold(stored) -> None:
    response = asyncio.run(get_notification_settings(user=_user(stored)))

    assert response.balance_low_threshold == DEFAULT_TOMAN


def test_cabinet_get_keeps_stored_threshold() -> None:
    response = asyncio.run(get_notification_settings(user=_user({'balance_low_threshold': 100})))

    assert response.balance_low_threshold == 100


class _FakeDb:
    async def commit(self) -> None:
        return None

    async def refresh(self, _obj) -> None:
        return None


def test_cabinet_patch_of_other_pref_persists_new_default() -> None:
    user = _user({})
    response = asyncio.run(
        update_notification_settings(
            request=NotificationSettingsUpdate(balance_low_enabled=True),
            user=user,
            db=_FakeDb(),
        )
    )

    assert response.balance_low_threshold == DEFAULT_TOMAN
    assert user.notification_settings['balance_low_threshold'] == DEFAULT_TOMAN
