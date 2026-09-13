"""F-029 / plan 2026-09-11 Task 4: a partner's listed tariff prices equal the checkout price.

The cabinet tariff list (``_build_tariff_response``) and the Mini App models applied only the
promo group (and, in the Mini App, the offer), while checkout (``_calculate_tariff_core``)
charges an approved partner wholesale on the undiscounted subtotal. Amounts are Toman 1:1 in
storage; cabinet ``*_kopeks`` fields travel through ``wire_catalog_kopeks``.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.database.models import PartnerStatus, Tariff
from app.services.pricing_engine import pricing_engine
from app.utils.wire_scale import wire_catalog_kopeks


ROOT = Path(__file__).resolve().parents[2]


def _user(*, partner: bool, group_pct: int = 10, offer_pct: int = 20) -> SimpleNamespace:
    group = SimpleNamespace(id=7, name='g', get_discount_percent=lambda _cat, _days: group_pct)
    return SimpleNamespace(
        id=1,
        language='fa',
        balance_kopeks=0,
        partner_status=PartnerStatus.APPROVED.value if partner else PartnerStatus.NONE.value,
        wholesale_discount_bps=3000 if partner else 0,
        promo_group=None,
        promo_group_id=None,
        get_primary_promo_group=lambda: group if group_pct else None,
        promo_offer_discount_percent=offer_pct,
        promo_offer_discount_expires_at=datetime.now(UTC) + timedelta(days=1),
        promo_offer_discount_source='test',
    )


def _tariff(**overrides) -> Tariff:
    fields = dict(
        id=2,
        name='مستقیم',
        description='',
        is_active=True,
        is_daily=False,
        period_prices={'30': 100_000, '90': 250_000},
        daily_price_kopeks=0,
        device_price_kopeks=5_000,
        price_per_day_kopeks=4_000,
        custom_days_enabled=True,
        traffic_limit_gb=100,
        device_limit=1,
        allowed_squads=[],
        display_order=1,
        tier_level=1,
    )
    fields.update(overrides)
    return Tariff(**fields)


@pytest.mark.asyncio
@pytest.mark.parametrize('subscription_devices', [None, 3])
async def test_cabinet_partner_period_prices_equal_checkout(subscription_devices):
    from app.cabinet.routes.subscription_modules.purchase import _build_tariff_response

    tariff = _tariff()
    partner = _user(partner=True)
    subscription = SimpleNamespace(tariff_id=2, device_limit=subscription_devices) if subscription_devices else None
    data = await _build_tariff_response(SimpleNamespace(), tariff, 2, 'fa', partner, subscription)

    for period in data['periods']:
        checkout = await pricing_engine.calculate_tariff_purchase_price(
            tariff, period['days'], device_limit=subscription_devices, user=partner
        )
        assert period['price_kopeks'] == wire_catalog_kopeks(checkout.final_total)
        assert period['discount_percent'] == 30
        assert period['original_price_kopeks'] == wire_catalog_kopeks(checkout.base_price + checkout.devices_price)
        assert period['discount_amount_kopeks'] == wire_catalog_kopeks(checkout.promo_group_discount)

    assert data['periods'][0]['price_kopeks'] == wire_catalog_kopeks(70_000 if subscription_devices is None else 77_000)


@pytest.mark.asyncio
async def test_low_rate_partner_whose_percent_rounds_to_zero_still_lists_checkout_price():
    """50 bps rounds to a 0% label, but checkout still charges wholesale, not group/offer."""
    from app.cabinet.routes.subscription_modules.purchase import _build_tariff_response
    from app.webapi.routes.miniapp import _build_tariff_model

    tariff = _tariff()
    partner = _user(partner=True)
    partner.wholesale_discount_bps = 50
    checkout = await pricing_engine.calculate_tariff_purchase_price(tariff, 30, user=partner)
    assert checkout.final_total == 99_500

    data = await _build_tariff_response(SimpleNamespace(), tariff, user=partner)
    assert data['periods'][0]['price_kopeks'] == wire_catalog_kopeks(99_500)
    assert data['device_price_kopeks'] == wire_catalog_kopeks(4_975)

    model = await _build_tariff_model(None, tariff, promo_group=partner.get_primary_promo_group(), user=partner)
    assert model.periods[0].price_kopeks == 99_500


@pytest.mark.asyncio
async def test_cabinet_partner_device_and_custom_day_prices_are_wholesale():
    from app.cabinet.routes.subscription_modules.purchase import _build_tariff_response

    data = await _build_tariff_response(SimpleNamespace(), _tariff(), user=_user(partner=True))

    assert data['device_price_kopeks'] == wire_catalog_kopeks(3_500)
    assert data['original_device_price_kopeks'] == wire_catalog_kopeks(5_000)
    assert data['device_discount_percent'] == 30
    assert data['price_per_day_kopeks'] == wire_catalog_kopeks(2_800)
    assert data['original_price_per_day_kopeks'] == wire_catalog_kopeks(4_000)
    assert data['custom_days_discount_percent'] == 30


@pytest.mark.asyncio
async def test_cabinet_b2c_listing_keeps_group_logic():
    from app.cabinet.routes.subscription_modules.purchase import _build_tariff_response

    data = await _build_tariff_response(SimpleNamespace(), _tariff(), user=_user(partner=False))

    assert data['periods'][0]['price_kopeks'] == wire_catalog_kopeks(90_000)  # group 10%, offer is the client's
    assert data['periods'][0]['discount_percent'] == 10
    assert data['device_price_kopeks'] == wire_catalog_kopeks(4_500)
    assert data['price_per_day_kopeks'] == wire_catalog_kopeks(3_600)


@pytest.mark.asyncio
async def test_miniapp_partner_tariff_model_is_wholesale_without_offer():
    from app.webapi.routes.miniapp import _build_tariff_model

    partner = _user(partner=True)
    model = await _build_tariff_model(None, _tariff(), promo_group=partner.get_primary_promo_group(), user=partner)

    assert [p.price_kopeks for p in model.periods] == [70_000, 175_000]
    assert all(p.discount_percent == 30 for p in model.periods)
    assert [p.original_price_kopeks for p in model.periods] == [100_000, 250_000]

    daily = await _build_tariff_model(
        None, _tariff(id=9, is_daily=True, daily_price_kopeks=10_000, period_prices={}), user=partner
    )
    assert daily.daily_price_kopeks == 7_000


@pytest.mark.asyncio
async def test_miniapp_b2c_tariff_model_unchanged():
    from app.webapi.routes.miniapp import _build_tariff_model

    user = _user(partner=False)
    model = await _build_tariff_model(None, _tariff(), promo_group=user.get_primary_promo_group(), user=user)

    assert model.periods[0].price_kopeks == 72_000  # 10% group, then 20% offer
    assert model.periods[0].discount_percent == 28


@pytest.mark.asyncio
async def test_miniapp_partner_current_tariff_monthly_price_is_wholesale():
    from app.webapi.routes.miniapp import _build_current_tariff_model

    partner = _user(partner=True)
    model = await _build_current_tariff_model(None, _tariff(), partner.get_primary_promo_group(), user=partner)

    assert model.monthly_price_kopeks == 70_000


def test_miniapp_subscription_details_hides_offer_from_partners():
    tree = ast.parse((ROOT / 'app/webapi/routes/miniapp.py').read_text(encoding='utf-8'))
    func = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == 'get_subscription_details'
    )
    attrs = {node.attr for node in ast.walk(func) if isinstance(node, ast.Attribute)}
    assert 'uses_wholesale_pricing' in attrs, 'a wholesale partner must not be shown a promo offer it never gets'
