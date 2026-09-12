"""The subscription endpoints keep the frozen catalog wire scale after Phase C.

Revision ``0115`` put every price in storage on the Toman scale, but the cabinet still divides
``*_kopeks`` price fields by 100 (``formatPrice``, ``catalogPriceInToman``). So each price field
these endpoints emit is the Toman amount ×100 (``wire_catalog_kopeks``), while the labels and the
``*_rubles`` twins carry the plain Toman number. ``balance_kopeks`` was never divided and stays 1:1.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.database.models import Tariff


def _user(*, balance: int = 0, group_pct: int = 0) -> SimpleNamespace:
    group = SimpleNamespace(id=7, name='Group', get_discount_percent=lambda _cat, _days: group_pct)
    return SimpleNamespace(
        id=1,
        language='fa',
        balance_kopeks=balance,
        promo_group=None,
        promo_group_id=None,
        get_primary_promo_group=lambda: group if group_pct else None,
        promo_offer_discount_percent=0,
        promo_offer_discount_expires_at=None,
    )


def _tariff(**overrides) -> Tariff:
    fields = dict(
        id=3,
        name='Pro',
        description='',
        is_active=True,
        is_daily=False,
        period_prices={'30': 990},
        daily_price_kopeks=0,
        device_price_kopeks=50,
        price_per_day_kopeks=40,
        traffic_price_per_gb_kopeks=20,
        traffic_topup_packages={'10': 35},
        traffic_limit_gb=100,
        device_limit=1,
        allowed_squads=[],
        display_order=1,
    )
    fields.update(overrides)
    return Tariff(**fields)


# ---------------------------------------------------------------- purchase options (tariffs mode)


@pytest.mark.asyncio
async def test_tariff_purchase_options_put_every_price_on_the_wire_scale():
    from app.cabinet.routes.subscription_modules.purchase import _build_tariff_response

    data = await _build_tariff_response(SimpleNamespace(), _tariff(), user=_user())

    period = data['periods'][0]
    assert period['price_kopeks'] == 99_000
    assert period['price_per_month_kopeks'] == 99_000
    assert period['price_label'] == settings.format_balance(990)
    assert 'original_price_kopeks' not in period

    assert data['device_price_kopeks'] == 5_000
    assert data['price_per_day_kopeks'] == 4_000
    assert data['traffic_price_per_gb_kopeks'] == 2_000
    assert data['traffic_topup_packages'] == {10: 3_500}


@pytest.mark.asyncio
async def test_tariff_purchase_options_discount_fields_share_the_wire_scale():
    from app.cabinet.routes.subscription_modules.purchase import _build_tariff_response

    data = await _build_tariff_response(SimpleNamespace(), _tariff(), user=_user(group_pct=20))

    period = data['periods'][0]
    assert period['price_kopeks'] == 79_200
    assert period['original_price_kopeks'] == 99_000
    assert period['original_per_month_kopeks'] == 99_000
    assert period['discount_amount_kopeks'] == 19_800
    assert period['discount_percent'] == 20
    assert period['original_price_label'] == settings.format_balance(990)


@pytest.mark.asyncio
async def test_tariff_purchase_options_extra_devices_cost_is_wire_scaled():
    from app.cabinet.routes.subscription_modules.purchase import _build_tariff_response

    subscription = SimpleNamespace(tariff_id=3, device_limit=3)
    data = await _build_tariff_response(SimpleNamespace(), _tariff(), 3, 'fa', _user(), subscription)

    period = data['periods'][0]
    assert period['extra_devices_count'] == 2
    assert period['extra_devices_cost_kopeks'] == 10_000  # 2 devices × 50 Toman × 1 month
    assert period['base_tariff_price_kopeks'] == 99_000
    assert period['price_kopeks'] == 109_000
    assert period['extra_devices_cost_label'] == settings.format_balance(100)


@pytest.mark.asyncio
async def test_daily_tariff_price_is_wire_scaled_and_its_label_is_toman():
    from app.cabinet.routes.subscription_modules.purchase import _build_tariff_response

    data = await _build_tariff_response(
        SimpleNamespace(), _tariff(is_daily=True, daily_price_kopeks=15, period_prices={}), user=_user(group_pct=20)
    )

    assert data['daily_price_kopeks'] == 1_200
    assert data['original_daily_price_kopeks'] == 1_500
    assert data['daily_discount_percent'] == 20


# ---------------------------------------------------------------- subscription response


def test_subscription_response_daily_price_is_wire_scaled():
    from app.cabinet.routes.subscription_modules.helpers import _subscription_to_response

    now = datetime.now(UTC)
    subscription = SimpleNamespace(
        id=10,
        user_id=1,
        status='active',
        actual_status='active',
        is_trial=False,
        is_daily_tariff=True,
        is_daily_paused=False,
        tariff_id=3,
        tariff=SimpleNamespace(is_daily=True, daily_price_kopeks=15, name='Daily', traffic_reset_mode=None),
        start_date=now,
        end_date=now + timedelta(days=5),
        traffic_limit_gb=10,
        traffic_used_gb=1.0,
        device_limit=1,
        connected_squads=[],
        subscription_url='',
        subscription_crypto_link='',
        autopay_enabled=False,
        autopay_days_before=3,
        next_daily_charge_at=None,
        remnawave_short_uuid=None,
        purchased_traffic_gb=0,
    )

    response = _subscription_to_response(subscription, user=_user(group_pct=20))  # type: ignore[arg-type]

    assert response.daily_price_kopeks == 1_200


# ---------------------------------------------------------------- trial info


@pytest.mark.asyncio
async def test_trial_info_price_is_wire_scaled_and_rubles_is_toman(monkeypatch):
    import app.database.crud.tariff as tariff_crud
    from app.cabinet.routes.subscription_modules.purchase import get_trial_info

    settings_cls = type(settings)
    monkeypatch.setattr(settings_cls, 'is_trial_disabled_for_user', lambda self, auth_type: False)
    monkeypatch.setattr(settings_cls, 'get_trial_tariff_id', lambda self: 0)
    monkeypatch.setattr(settings, 'TRIAL_PAYMENT_ENABLED', True, raising=False)
    monkeypatch.setattr(settings, 'TRIAL_ACTIVATION_PRICE', 500, raising=False)
    monkeypatch.setattr(tariff_crud, 'get_trial_tariff', AsyncMock(return_value=None))

    user = _user()
    user.auth_type = 'telegram'
    user.subscriptions = []
    user.is_trial_already_used = lambda: False

    info = await get_trial_info(user=user, db=SimpleNamespace(refresh=AsyncMock()))

    assert info.is_available is True
    assert info.price_kopeks == 50_000
    assert info.price_rubles == 500


# ---------------------------------------------------------------- renewal options


@pytest.mark.asyncio
async def test_renewal_options_are_wire_scaled(monkeypatch):
    from app.cabinet.routes.subscription_modules import helpers, renewal

    subscription = SimpleNamespace(
        tariff_id=3,
        status='active',
        actual_status='active',
        tariff=SimpleNamespace(is_active=True, period_prices={'30': 990}),
    )
    monkeypatch.setattr(helpers, 'resolve_subscription', AsyncMock(return_value=subscription))
    monkeypatch.setattr(type(settings), 'is_tariffs_mode', lambda self: True)
    monkeypatch.setattr(
        renewal.pricing_engine,
        'calculate_renewal_price',
        AsyncMock(return_value=SimpleNamespace(final_total=792, original_total=990)),
    )

    options = await renewal.get_renewal_options(user=_user(), db=object(), subscription_id=None)

    assert len(options) == 1
    option = options[0]
    assert option.price_kopeks == 79_200
    assert option.price_rubles == 792
    assert option.original_price_kopeks == 99_000
    assert option.discount_percent == 20


# ---------------------------------------------------------------- countries


@pytest.mark.asyncio
async def test_available_countries_are_wire_scaled(monkeypatch):
    import app.database.crud.server_squad as server_squad_crud
    from app.cabinet.routes.subscription_modules import servers
    from app.services.pricing_engine import PricingEngine

    server = SimpleNamespace(
        squad_uuid='sq-1',
        display_name='Germany',
        country_code='DE',
        price_kopeks=300,
        is_available=True,
        is_full=False,
    )
    monkeypatch.setattr(servers, 'resolve_subscription', AsyncMock(return_value=None))
    monkeypatch.setattr(server_squad_crud, 'get_available_server_squads', AsyncMock(return_value=[server]))
    monkeypatch.setattr(PricingEngine, 'get_addon_discount_percent', staticmethod(lambda user, cat, hint: 10))

    data = await servers.get_available_countries(user=_user(), db=object(), subscription_id=None)

    country = data['countries'][0]
    assert country['base_price_kopeks'] == 30_000
    assert country['price_per_month_kopeks'] == 27_000
    assert country['price_kopeks'] == 27_000  # no subscription → nothing to prorate
    assert country['price_rubles'] == 270


# ---------------------------------------------------------------- device price


def _device_subscription(days_left: int) -> SimpleNamespace:
    return SimpleNamespace(
        status='active', tariff_id=None, device_limit=1, end_date=datetime.now(UTC) + timedelta(days=days_left)
    )


@pytest.mark.asyncio
async def test_device_price_preview_is_wire_scaled(monkeypatch):
    from app.cabinet.routes.subscription_modules import devices

    monkeypatch.setattr(devices, 'resolve_subscription', AsyncMock(return_value=_device_subscription(30)))
    monkeypatch.setattr(settings, 'PRICE_PER_DEVICE', 50, raising=False)
    monkeypatch.setattr(settings, 'MAX_DEVICES_LIMIT', 0, raising=False)
    monkeypatch.setattr(settings, 'DEFAULT_DEVICE_LIMIT', 1, raising=False)
    monkeypatch.setattr(
        devices,
        '_apply_addon_discount',
        lambda user, cat, price, hint: {'discounted': price - 10, 'percent': 20, 'discount': 10},
    )

    data = await devices.get_device_price(devices=2, subscription_id=None, user=_user(), db=object())

    assert data['available'] is True
    assert data['total_price_kopeks'] == 9_000  # 2 × 50 Toman − 10 Toman discount
    assert data['price_per_device_kopeks'] == 4_500
    assert data['base_device_price_kopeks'] == 5_000
    assert data['discount_kopeks'] == 1_000
    assert data['base_total_price_kopeks'] == 10_000
    assert data['original_price_per_device_kopeks'] == 5_000
    assert data['total_price_label'] == settings.format_balance(90)


@pytest.mark.asyncio
async def test_device_price_floor_is_one_toman(monkeypatch):
    """The floor used to be ``max(100, …)`` on ×100 storage; on Toman storage it is 1 Toman."""
    from app.cabinet.routes.subscription_modules import devices

    monkeypatch.setattr(devices, 'resolve_subscription', AsyncMock(return_value=_device_subscription(1)))
    monkeypatch.setattr(settings, 'PRICE_PER_DEVICE', 5, raising=False)
    monkeypatch.setattr(settings, 'MAX_DEVICES_LIMIT', 0, raising=False)
    monkeypatch.setattr(settings, 'DEFAULT_DEVICE_LIMIT', 1, raising=False)
    monkeypatch.setattr(
        devices,
        '_apply_addon_discount',
        lambda user, cat, price, hint: {'discounted': price, 'percent': 0, 'discount': 0},
    )

    data = await devices.get_device_price(devices=1, subscription_id=None, user=_user(), db=object())

    assert data['total_price_kopeks'] == 100  # 5 Toman × 1/30 → 0 → floored to 1 Toman
    assert data['total_price_label'] == settings.format_balance(1)


# ---------------------------------------------------------------- tariff switch preview


@pytest.mark.asyncio
async def test_switch_preview_costs_are_wire_scaled(monkeypatch):
    import app.cabinet.routes.subscription_modules.tariff_switch as switch

    current = SimpleNamespace(id=1, name='A', is_free=False)
    target = SimpleNamespace(id=2, name='B', is_active=True, is_available_for_promo_group=lambda gid: True)
    subscription = SimpleNamespace(
        tariff_id=1, actual_status='active', is_trial=False, end_date=datetime.now(UTC) + timedelta(days=10)
    )

    monkeypatch.setattr(type(settings), 'is_tariffs_mode', lambda self: True)
    monkeypatch.setattr(settings, 'TARIFF_SWITCH_RESET_FREE_DAYS', False, raising=False)
    monkeypatch.setattr(switch, 'resolve_subscription', AsyncMock(return_value=subscription))
    monkeypatch.setattr(switch, 'get_tariff_by_id', AsyncMock(side_effect=lambda db, tid: {1: current, 2: target}[tid]))
    monkeypatch.setattr(switch, 'is_switch_direction_allowed', lambda is_upgrade: True)
    monkeypatch.setattr(
        switch.pricing_engine,
        'calculate_tariff_switch_cost',
        lambda *a, **k: SimpleNamespace(
            upgrade_cost=700, is_upgrade=True, raw_cost=900, discount_value=200, effective_discount_pct=22
        ),
    )

    data = await switch.preview_tariff_switch(
        request=SimpleNamespace(tariff_id=2), user=_user(balance=500), db=object(), subscription_id=None
    )

    assert data['upgrade_cost_kopeks'] == 70_000
    assert data['base_upgrade_cost_kopeks'] == 90_000
    assert data['discount_kopeks'] == 20_000
    assert data['missing_amount_kopeks'] == 20_000  # 700 − 500 Toman short
    assert data['balance_kopeks'] == 500
    assert data['has_enough_balance'] is False
    assert data['upgrade_cost_label'] == settings.format_balance(700)


# ---------------------------------------------------------------- classic purchase service payloads


def test_classic_option_payloads_are_wire_scaled():
    from app.services.subscription_purchase_service import (
        PurchaseDevicesConfig,
        PurchasePeriodConfig,
        PurchaseServerOption,
        PurchaseServersConfig,
        PurchaseTrafficConfig,
        PurchaseTrafficOption,
    )

    traffic = PurchaseTrafficOption(
        value=50,
        label='50 GB',
        price_per_month=90,
        price_label='90',
        original_price_per_month=100,
        original_price_label='100',
        discount_percent=10,
    )
    server = PurchaseServerOption(uuid='u', name='n', price_per_month=300, price_label='300')
    devices = PurchaseDevicesConfig(
        minimum=1,
        maximum=5,
        default=1,
        current=1,
        price_per_device=50,
        discounted_price_per_device=45,
        price_label='45',
        original_price_label='50',
        discount_percent=10,
    )
    period = PurchasePeriodConfig(
        id='30',
        days=30,
        months=1,
        label='30 days',
        base_price=990,
        base_price_label='990',
        base_price_original=1100,
        base_price_original_label='1100',
        discount_percent=10,
        per_month_price=990,
        per_month_price_label='990',
        traffic=PurchaseTrafficConfig(selectable=True, mode='fixed', options=[traffic]),
        servers=PurchaseServersConfig(options=[server], min_selectable=1, max_selectable=3, default_selection=['u']),
        devices=devices,
    )

    payload = period.to_payload()

    assert payload['price_kopeks'] == 99_000
    assert payload['per_month_price_kopeks'] == 99_000
    assert payload['original_price_kopeks'] == 110_000
    assert payload['traffic']['options'][0]['price_kopeks'] == 9_000
    assert payload['traffic']['options'][0]['original_price_kopeks'] == 10_000
    assert payload['servers']['options'][0]['price_kopeks'] == 30_000
    assert payload['devices']['price_per_device_kopeks'] == 4_500
    assert payload['devices']['price_per_device_original_kopeks'] == 5_000
    # labels are the Toman numbers the service was given
    assert payload['price_label'] == '990'
