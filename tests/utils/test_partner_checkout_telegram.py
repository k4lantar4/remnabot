from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.utils.partner_checkout_telegram import (
    apply_partner_checkout_from_state,
    checkout_partner_options,
    extend_confirm_keyboard,
    sanitize_purchase_note,
)
from app.utils.remnawave_panel_identity import validate_brand_prefix


def test_validate_brand_prefix() -> None:
    assert validate_brand_prefix('Moonvpn') == 'Moonvpn'
    assert validate_brand_prefix('ab') is None


def test_options_fail_open_without_partner() -> None:
    user = SimpleNamespace(is_partner=False, panel_brand_prefix='Moonvpn')
    opts = checkout_partner_options(user, {'purchase_note': 'x', 'use_brand_prefix': True})
    assert opts['use_brand_prefix'] is False


class DummyTexts:
    def t(self, key, default=None):
        return default or key


def test_extend_keyboard_noop_for_non_partner() -> None:
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)
    buttons = [['confirm']]
    assert extend_confirm_keyboard(buttons, user, 1, 30, DummyTexts()) == buttons


def test_prompt_purchase_note_clears_markup() -> None:
    from pathlib import Path

    src = Path('app/handlers/subscription/partner_checkout.py').read_text()
    assert 'reply_markup=None' in src
    assert 'pnote_cancel:' in src


def test_sanitize_purchase_note() -> None:
    assert sanitize_purchase_note('  hello  ') == 'hello'
    assert sanitize_purchase_note('') is None
    assert sanitize_purchase_note(None) is None
    assert len(sanitize_purchase_note('x' * 600) or '') == 500


def test_options_fail_open_without_prefix_attr() -> None:
    user = SimpleNamespace(is_partner=True)
    opts = checkout_partner_options(user, {'purchase_note': 'x', 'use_brand_prefix': True})
    assert opts == {'purchase_note': None, 'use_brand_prefix': False, 'has_brand_prefix': False}


def test_extend_keyboard_noop_without_prefix_attr() -> None:
    user = SimpleNamespace(is_partner=True)
    buttons = [['confirm'], ['back']]
    assert extend_confirm_keyboard(buttons, user, 1, 30, DummyTexts()) == buttons


def test_extend_keyboard_inserts_partner_rows() -> None:
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='Moonvpn')
    buttons = [['confirm'], ['back']]
    extended = extend_confirm_keyboard(buttons, user, 7, 30, DummyTexts(), {'use_brand_prefix': True})
    assert extended[0] == ['confirm']
    assert extended[-1] == ['back']
    callbacks = [btn.callback_data for row in extended[1:-1] for btn in row]
    assert 'pnote:7:30' in callbacks
    assert 'pbrand:7:30' in callbacks


@pytest.mark.asyncio
async def test_apply_partner_checkout_sets_note_and_commits() -> None:
    db = AsyncMock()
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='Moonvpn')
    subscription = SimpleNamespace(purchase_note=None)
    await apply_partner_checkout_from_state(
        db,
        user,
        subscription,
        {'purchase_note': '  shop-1 ', 'use_brand_prefix': False},
    )
    assert subscription.purchase_note == 'shop-1'
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_partner_checkout_commits_when_clearing_note() -> None:
    db = AsyncMock()
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='Moonvpn')
    subscription = SimpleNamespace(purchase_note='old')
    await apply_partner_checkout_from_state(
        db,
        user,
        subscription,
        {'purchase_note': '', 'use_brand_prefix': True},
    )
    assert subscription.purchase_note is None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_partner_checkout_noop_for_non_partner() -> None:
    db = AsyncMock()
    user = SimpleNamespace(is_partner=False, panel_brand_prefix='Moonvpn')
    subscription = SimpleNamespace(purchase_note=None)
    await apply_partner_checkout_from_state(
        db,
        user,
        subscription,
        {'purchase_note': 'x', 'use_brand_prefix': True},
    )
    assert subscription.purchase_note is None
    db.commit.assert_not_awaited()
