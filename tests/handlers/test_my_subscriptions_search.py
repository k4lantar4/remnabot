"""Tests for my subscriptions list search filter and keyboard."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.handlers.subscription.my_subscriptions import (
    _build_subscriptions_keyboard,
    _filter_subscriptions_by_query,
    _subscription_matches_search,
)


class _Texts:
    language = 'fa'

    def t(self, key: str, default: str) -> str:
        return default


def _texts() -> _Texts:
    return _Texts()


def _callbacks(keyboard) -> list[str]:
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def test_matches_legacy_panel_username_partial() -> None:
    sub = SimpleNamespace(
        id=10,
        panel_username='Germany(2)-134500',
        tariff=SimpleNamespace(name='Germany'),
        account_sequence=2,
    )
    texts = _texts()
    assert _subscription_matches_search(sub, '134500', texts) is True


def test_does_not_match_hidden_user_unknown_in_db() -> None:
    sub = SimpleNamespace(
        id=1,
        panel_username='user_unknown_abc123',
        tariff=SimpleNamespace(name='Germany'),
        account_sequence=3,
    )
    texts = _texts()
    assert _subscription_matches_search(sub, 'user_unknown', texts) is False
    assert _subscription_matches_search(sub, 'germany', texts) is True


def test_matches_tariff_name_when_label_is_legacy_panel() -> None:
    sub = SimpleNamespace(
        id=5,
        panel_username='Germany(2)-134500',
        tariff=SimpleNamespace(name='VIP'),
        account_sequence=1,
    )
    texts = _texts()
    assert _subscription_matches_search(sub, 'vip', texts) is True


def test_matches_subscription_id() -> None:
    sub = SimpleNamespace(id=42, panel_username='', tariff=None, account_sequence=1)
    assert _subscription_matches_search(sub, '42', _texts()) is True


def test_filter_returns_only_matches() -> None:
    subs = [
        SimpleNamespace(id=1, panel_username='Alpha', tariff=None, account_sequence=1),
        SimpleNamespace(id=2, panel_username='Beta', tariff=None, account_sequence=1),
    ]
    result = _filter_subscriptions_by_query(subs, 'beta', _texts())
    assert [s.id for s in result] == [2]


def test_empty_query_returns_all_subscriptions() -> None:
    subs = [
        SimpleNamespace(id=1, panel_username='Alpha', tariff=None, account_sequence=1),
        SimpleNamespace(id=2, panel_username='Beta', tariff=None, account_sequence=1),
    ]
    result = _filter_subscriptions_by_query(subs, '', _texts())
    assert [s.id for s in result] == [1, 2]


def test_keyboard_shows_search_when_no_active_query() -> None:
    subs = [
        SimpleNamespace(id=1, panel_username='Alpha', tariff=None, account_sequence=1),
        SimpleNamespace(id=2, panel_username='Beta', tariff=None, account_sequence=1),
    ]
    keyboard = _build_subscriptions_keyboard(
        subs,
        'ru',
        page=1,
        total_pages=1,
        search_query='',
        show_search=True,
    )
    callbacks = _callbacks(keyboard)
    assert 'my_subs_search' in callbacks
    assert 'my_subs_search_reset' not in callbacks
    search_idx = callbacks.index('my_subs_search')
    back_idx = callbacks.index('back_to_menu')
    assert search_idx < back_idx


def test_keyboard_shows_reset_when_query_active() -> None:
    subs = [
        SimpleNamespace(id=1, panel_username='Alpha', tariff=None, account_sequence=1),
    ]
    keyboard = _build_subscriptions_keyboard(
        subs,
        'ru',
        page=1,
        total_pages=1,
        search_query='alpha',
        show_search=True,
    )
    callbacks = _callbacks(keyboard)
    assert 'my_subs_search_reset' in callbacks
    assert 'my_subs_search' not in callbacks
