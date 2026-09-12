"""Card-to-card is a cabinet payment method, offered first and quoted in Toman.

C2C limits were always Toman 1:1 (``C2C_MIN_AMOUNT_KOPEKS=100000`` means 100,000 Toman), and since
Phase C every other method's defaults are too, so the entry needs no conversion of its own: the
single x100 happens in the route, through ``wire_catalog_kopeks``, like it does for every other
method.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.cabinet.routes import balance as balance_routes
from app.config import settings
from app.services import payment_method_config_service as pmcs


CARDS = json.dumps([{'label': 'Bank', 'number': '6037991234567890', 'holder': 'Test Holder'}])


@pytest.fixture
def c2c_on(monkeypatch):
    monkeypatch.setattr(settings, 'C2C_ENABLED', True, raising=False)
    monkeypatch.setattr(settings, 'C2C_CARDS', CARDS, raising=False)
    monkeypatch.setattr(settings, 'C2C_DISPLAY_NAME', 'کارت به کارت 💳', raising=False)
    monkeypatch.setattr(settings, 'C2C_MIN_AMOUNT_KOPEKS', 100_000, raising=False)
    monkeypatch.setattr(settings, 'C2C_MAX_AMOUNT_KOPEKS', 10_000_000, raising=False)


def _config(method_id: str, **overrides):
    data = {
        'method_id': method_id,
        'is_enabled': True,
        'display_name': None,
        'description': None,
        'min_amount_kopeks': None,
        'max_amount_kopeks': None,
        'quick_amounts': None,
        'sub_options': None,
        'sort_order': 0,
        'user_type_filter': 'all',
        'first_topup_filter': 'any',
        'promo_group_filter_mode': 'all',
        'allowed_promo_groups': [],
        'open_url_direct': False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_c2c_is_configured_when_enabled_with_cards(c2c_on):
    c2c = pmcs._get_method_defaults()['c2c']
    assert c2c['is_configured'] is True
    assert c2c['default_display_name'] == 'کارت به کارت 💳'
    assert c2c['available_sub_options'] is None


def test_c2c_limits_are_the_stored_toman_numbers(c2c_on):
    c2c = pmcs._get_method_defaults()['c2c']
    # Toman 1:1 — the same numbers the bot's own C2C flow compares against.
    assert c2c['default_min'] == 100_000
    assert c2c['default_max'] == 10_000_000


def test_c2c_is_not_configured_without_cards(monkeypatch, c2c_on):
    monkeypatch.setattr(settings, 'C2C_CARDS', '[]', raising=False)
    assert pmcs._get_method_defaults()['c2c']['is_configured'] is False


def test_c2c_is_not_configured_when_disabled(monkeypatch, c2c_on):
    monkeypatch.setattr(settings, 'C2C_ENABLED', False, raising=False)
    assert pmcs._get_method_defaults()['c2c']['is_configured'] is False


def test_c2c_leads_the_default_method_order():
    # Card-to-card is the primary method: a fresh install must seed it at sort_order 0.
    assert pmcs.DEFAULT_METHOD_ORDER[0] == 'c2c'
    assert pmcs.DEFAULT_METHOD_ORDER.count('c2c') == 1


@pytest.mark.asyncio
async def test_enabled_methods_offer_c2c_in_toman(monkeypatch, c2c_on):
    monkeypatch.setattr(pmcs, 'get_all_configs', AsyncMock(return_value=[_config('c2c')]))

    methods = await pmcs.get_enabled_methods_for_user(db=None)

    assert [m['id'] for m in methods] == ['c2c']
    assert methods[0]['name'] == 'کارت به کارت 💳'
    assert methods[0]['min_amount_kopeks'] == 100_000
    assert methods[0]['max_amount_kopeks'] == 10_000_000


@pytest.mark.asyncio
async def test_enabled_methods_drop_c2c_without_cards(monkeypatch, c2c_on):
    monkeypatch.setattr(settings, 'C2C_CARDS', '[]', raising=False)
    monkeypatch.setattr(pmcs, 'get_all_configs', AsyncMock(return_value=[_config('c2c')]))

    assert await pmcs.get_enabled_methods_for_user(db=None) == []


@pytest.mark.asyncio
async def test_route_serialises_c2c_limits_on_the_wire_scale(monkeypatch):
    monkeypatch.setattr(
        balance_routes,
        'get_enabled_methods_for_user',
        AsyncMock(
            return_value=[
                {
                    'id': 'c2c',
                    'name': 'کارت به کارت 💳',
                    'description': None,
                    'min_amount_kopeks': 100_000,
                    'max_amount_kopeks': 10_000_000,
                    'options': None,
                    'quick_amounts': [100_000],
                    'sort_order': 0,
                    'open_url_direct': False,
                }
            ]
        ),
    )
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar=lambda: False)))

    methods = await balance_routes.get_payment_methods(user=SimpleNamespace(id=1), db=db)

    assert methods[0].id == 'c2c'
    # The cabinet still divides by 100: 100,000 T -> 10,000,000; 10,000,000 T -> 1,000,000,000.
    assert methods[0].min_amount_kopeks == 10_000_000
    assert methods[0].max_amount_kopeks == 1_000_000_000
    assert methods[0].quick_amounts == [10_000_000]
