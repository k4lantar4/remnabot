"""Daily price parity outside the cabinet: bot and Mini App show what is charged.

Upstream 968687ce made ``PricingEngine.daily_group_price`` the single "per day" price for
the cabinet and the daily charge. Our fork also shows a recurring daily price in the bot's
subscription screen and in two Mini App responses, and all three still stacked the active
promo offer on top. The offer is taken once, at activation; every later day is charged
group-only (``daily_subscription_service``), so these screens promised a lower price than
the one actually charged.

The Mini App purchase list (``_build_tariff_model``) is deliberately left alone: that client
never re-applies the offer, so its list shows the activation price, as its periods do.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.database.models import Tariff


ROOT = Path(__file__).resolve().parents[2]

# file -> function that shows the recurring daily price of an existing subscription
RECURRING_DAILY_PRICE_SITES = {
    'app/handlers/subscription/purchase.py': 'show_subscription_info',
    'app/webapi/routes/miniapp.py': 'get_subscription_details',
    'app/webapi/routes/miniapp.py#current': '_build_current_tariff_model',
}


def _function(relative: str, name: str) -> ast.AST:
    tree = ast.parse((ROOT / relative.split('#')[0]).read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f'{relative}: function {name} not found; update this guard')


@pytest.mark.parametrize(('relative', 'function_name'), RECURRING_DAILY_PRICE_SITES.items())
def test_recurring_daily_price_comes_from_daily_group_price(relative, function_name):
    func = _function(relative, function_name)
    attrs = {node.attr for node in ast.walk(func) if isinstance(node, ast.Attribute)}
    assert 'daily_group_price' in attrs, f'{relative}:{function_name} computes the daily price itself'


def _group(pct: int) -> SimpleNamespace:
    return SimpleNamespace(id=7, name='g', get_discount_percent=lambda _cat, _days: pct)


def _user(*, group_pct: int, offer_pct: int) -> SimpleNamespace:
    group = _group(group_pct)
    return SimpleNamespace(
        id=1,
        language='fa',
        promo_group=None,
        get_primary_promo_group=lambda: group if group_pct else None,
        promo_offer_discount_percent=offer_pct,
        promo_offer_discount_expires_at=datetime.now(UTC) + timedelta(days=1),
        promo_offer_discount_source='test',
    )


def _daily_tariff() -> Tariff:
    return Tariff(
        id=3,
        name='daily',
        description='',
        is_active=True,
        is_daily=True,
        daily_price_kopeks=1500,
        period_prices={},
        traffic_limit_gb=2,
        device_limit=1,
        allowed_squads=[],
        display_order=1,
        tier_level=1,
    )


@pytest.mark.asyncio
async def test_miniapp_current_tariff_daily_price_is_group_only():
    from app.webapi.routes.miniapp import _build_current_tariff_model

    user = _user(group_pct=20, offer_pct=20)
    model = await _build_current_tariff_model(None, _daily_tariff(), _group(20), user=user)

    assert model.daily_price_kopeks == 1200, 'the promo offer is not charged every day'
