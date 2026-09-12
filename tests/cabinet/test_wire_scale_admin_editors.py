"""Frozen HTTP contract for the cabinet admin editors after Toman Phase C.

Revision 0115 put every catalog column on Toman 1:1, but the cabinet frontend still divides these
JSON fields by 100 on display and multiplies them by 100 on save. So the admin editors have to keep
speaking the old x100 scale on the wire, through ``app/utils/wire_scale.py`` and nowhere else:

- outbound: Toman 990 in storage -> 99000 on the wire (``wire_catalog_kopeks``);
- inbound:  99000 from the client -> Toman 990 in storage (``toman_from_wire_catalog``).

``*_rubles`` twins stay the plain Toman number, ``None`` stays ``None``, and fields the frontend
already reads as Toman (balances, bonuses, transaction amounts) are not touched.

House style: handlers are called directly with hand-built fakes and the CRUD layer patched on the
route module, the same as ``test_coupon_routes.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings


TOMAN = 990
WIRE = 99_000
ADMIN = SimpleNamespace(id=1, telegram_id=111)
NOW = datetime.now(UTC)


def _ns(**kwargs) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


# ── admin_tariffs ─────────────────────────────────────────────────────────────


def _tariff(**overrides) -> SimpleNamespace:
    base = {
        'id': 7,
        'name': 'Basic',
        'description': None,
        'is_active': True,
        'is_trial_available': False,
        'allow_traffic_topup': True,
        'traffic_topup_enabled': True,
        'traffic_topup_packages': {'50': TOMAN},
        'max_topup_traffic_gb': 0,
        'traffic_limit_gb': 100,
        'device_limit': 1,
        'device_price_kopeks': TOMAN,
        'max_device_limit': None,
        'tier_level': 1,
        'display_order': 0,
        'period_prices': {'30': TOMAN},
        'allowed_squads': [],
        'server_traffic_limits': {},
        'allowed_promo_groups': [],
        'custom_days_enabled': False,
        'price_per_day_kopeks': TOMAN,
        'min_days': 1,
        'max_days': 365,
        'custom_traffic_enabled': False,
        'traffic_price_per_gb_kopeks': TOMAN,
        'min_traffic_gb': 1,
        'max_traffic_gb': 1000,
        'is_daily': False,
        'daily_price_kopeks': TOMAN,
        'lava_product_id': None,
        'traffic_reset_mode': None,
        'external_squad_uuid': None,
        'show_in_gift': True,
        'created_at': NOW,
        'updated_at': NOW,
        'is_available_for_promo_group': lambda promo_group_id: True,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_tariff_period_prices_list_puts_toman_on_the_wire_and_keeps_rubles_toman() -> None:
    from app.cabinet.routes.admin_tariffs import _period_prices_to_list

    [item] = _period_prices_to_list({'30': TOMAN})

    assert item.days == 30
    assert item.price_kopeks == WIRE
    assert item.price_rubles == TOMAN


@pytest.mark.asyncio
async def test_list_tariffs_daily_price_on_the_wire() -> None:
    from app.cabinet.routes import admin_tariffs

    with (
        patch.object(admin_tariffs, 'get_all_tariffs', AsyncMock(return_value=[_tariff()])),
        patch.object(admin_tariffs, 'get_tariff_subscriptions_count', AsyncMock(return_value=0)),
    ):
        response = await admin_tariffs.list_tariffs(include_inactive=True, admin=ADMIN, db=AsyncMock())

    assert response.tariffs[0].daily_price_kopeks == WIRE


@pytest.mark.asyncio
async def test_get_tariff_catalog_prices_on_the_wire() -> None:
    from app.cabinet.routes import admin_tariffs

    with (
        patch.object(admin_tariffs, 'get_tariff_by_id', AsyncMock(return_value=_tariff())),
        patch.object(admin_tariffs, '_get_tariff_servers', AsyncMock(return_value=[])),
        patch.object(admin_tariffs, '_get_tariff_promo_groups', AsyncMock(return_value=[])),
        patch.object(admin_tariffs, 'get_tariff_subscriptions_count', AsyncMock(return_value=0)),
    ):
        response = await admin_tariffs.get_tariff(7, admin=ADMIN, db=AsyncMock())

    assert response.device_price_kopeks == WIRE
    assert response.price_per_day_kopeks == WIRE
    assert response.traffic_price_per_gb_kopeks == WIRE
    assert response.daily_price_kopeks == WIRE
    assert response.traffic_topup_packages == {'50': WIRE}
    assert response.period_prices[0].price_kopeks == WIRE
    assert response.period_prices[0].price_rubles == TOMAN


@pytest.mark.asyncio
async def test_get_tariff_keeps_unset_device_price_none() -> None:
    from app.cabinet.routes import admin_tariffs

    with (
        patch.object(admin_tariffs, 'get_tariff_by_id', AsyncMock(return_value=_tariff(device_price_kopeks=None))),
        patch.object(admin_tariffs, '_get_tariff_servers', AsyncMock(return_value=[])),
        patch.object(admin_tariffs, '_get_tariff_promo_groups', AsyncMock(return_value=[])),
        patch.object(admin_tariffs, 'get_tariff_subscriptions_count', AsyncMock(return_value=0)),
    ):
        response = await admin_tariffs.get_tariff(7, admin=ADMIN, db=AsyncMock())

    assert response.device_price_kopeks is None


@pytest.mark.asyncio
async def test_create_tariff_stores_toman() -> None:
    from app.cabinet.routes import admin_tariffs
    from app.cabinet.schemas.tariffs import PeriodPrice, TariffCreateRequest

    request = TariffCreateRequest(
        name='Basic',
        period_prices=[PeriodPrice(days=30, price_kopeks=WIRE)],
        device_price_kopeks=WIRE,
        price_per_day_kopeks=WIRE,
        traffic_price_per_gb_kopeks=WIRE,
        daily_price_kopeks=WIRE,
        traffic_topup_packages={'50': WIRE},
    )

    with (
        patch.object(admin_tariffs, 'create_tariff', AsyncMock(return_value=_tariff())) as create_mock,
        patch.object(admin_tariffs, 'load_period_prices_from_db', AsyncMock()),
        patch.object(admin_tariffs, 'get_tariff', AsyncMock(return_value='detail')),
    ):
        await admin_tariffs.create_new_tariff(request, admin=ADMIN, db=AsyncMock())

    kwargs = create_mock.call_args.kwargs
    assert kwargs['period_prices'] == {'30': TOMAN}
    assert kwargs['device_price_kopeks'] == TOMAN
    assert kwargs['price_per_day_kopeks'] == TOMAN
    assert kwargs['traffic_price_per_gb_kopeks'] == TOMAN
    assert kwargs['daily_price_kopeks'] == TOMAN
    assert kwargs['traffic_topup_packages'] == {'50': TOMAN}


@pytest.mark.asyncio
async def test_create_tariff_keeps_unset_device_price_none() -> None:
    from app.cabinet.routes import admin_tariffs
    from app.cabinet.schemas.tariffs import TariffCreateRequest

    with (
        patch.object(admin_tariffs, 'create_tariff', AsyncMock(return_value=_tariff())) as create_mock,
        patch.object(admin_tariffs, 'load_period_prices_from_db', AsyncMock()),
        patch.object(admin_tariffs, 'get_tariff', AsyncMock(return_value='detail')),
    ):
        await admin_tariffs.create_new_tariff(TariffCreateRequest(name='Basic'), admin=ADMIN, db=AsyncMock())

    assert create_mock.call_args.kwargs['device_price_kopeks'] is None


@pytest.mark.asyncio
async def test_update_tariff_stores_toman_and_skips_unset_fields() -> None:
    from app.cabinet.routes import admin_tariffs
    from app.cabinet.schemas.tariffs import PeriodPrice, TariffUpdateRequest

    request = TariffUpdateRequest(
        period_prices=[PeriodPrice(days=90, price_kopeks=WIRE)],
        device_price_kopeks=WIRE,
        daily_price_kopeks=WIRE,
        traffic_topup_packages={'100': WIRE},
    )

    with (
        patch.object(admin_tariffs, 'get_tariff_by_id', AsyncMock(return_value=_tariff())),
        patch.object(admin_tariffs, 'update_tariff', AsyncMock()) as update_mock,
        patch.object(admin_tariffs, 'load_period_prices_from_db', AsyncMock()),
        patch.object(admin_tariffs, 'set_tariff_promo_groups', AsyncMock()),
        patch.object(admin_tariffs, 'get_tariff', AsyncMock(return_value='detail')),
    ):
        await admin_tariffs.update_existing_tariff(7, request, admin=ADMIN, db=AsyncMock())

    updates = update_mock.call_args.kwargs
    assert updates['period_prices'] == {'90': TOMAN}
    assert updates['device_price_kopeks'] == TOMAN
    assert updates['daily_price_kopeks'] == TOMAN
    assert updates['traffic_topup_packages'] == {'100': TOMAN}
    assert 'price_per_day_kopeks' not in updates
    assert 'traffic_price_per_gb_kopeks' not in updates


@pytest.mark.asyncio
async def test_update_tariff_per_day_and_per_gb_store_toman() -> None:
    from app.cabinet.routes import admin_tariffs
    from app.cabinet.schemas.tariffs import TariffUpdateRequest

    request = TariffUpdateRequest(price_per_day_kopeks=WIRE, traffic_price_per_gb_kopeks=WIRE)

    with (
        patch.object(admin_tariffs, 'get_tariff_by_id', AsyncMock(return_value=_tariff())),
        patch.object(admin_tariffs, 'update_tariff', AsyncMock()) as update_mock,
        patch.object(admin_tariffs, 'load_period_prices_from_db', AsyncMock()),
        patch.object(admin_tariffs, 'set_tariff_promo_groups', AsyncMock()),
        patch.object(admin_tariffs, 'get_tariff', AsyncMock(return_value='detail')),
    ):
        await admin_tariffs.update_existing_tariff(7, request, admin=ADMIN, db=AsyncMock())

    updates = update_mock.call_args.kwargs
    assert updates['price_per_day_kopeks'] == TOMAN
    assert updates['traffic_price_per_gb_kopeks'] == TOMAN


@pytest.mark.asyncio
async def test_tariff_stats_revenue_on_the_wire_and_rubles_toman() -> None:
    from app.cabinet.routes import admin_tariffs

    def _scalar(value):
        result = MagicMock()
        result.scalar.return_value = value
        return result

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[_scalar(3), _scalar(2), _scalar(1), _scalar(TOMAN)])

    with patch.object(admin_tariffs, 'get_tariff_by_id', AsyncMock(return_value=_tariff())):
        response = await admin_tariffs.get_tariff_stats(7, admin=ADMIN, db=db)

    assert response.revenue_kopeks == WIRE
    assert response.revenue_rubles == TOMAN


# ── admin_users ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_user_available_tariffs_catalog_prices_on_the_wire() -> None:
    from app.cabinet.routes import admin_users
    from app.database.crud import tariff as tariff_crud

    user = _ns(id=5, promo_group_id=None, promo_group=None, subscriptions=[])

    with (
        patch.object(admin_users, 'get_user_by_id', AsyncMock(return_value=user)),
        patch.object(tariff_crud, 'get_all_tariffs', AsyncMock(return_value=[_tariff()])),
    ):
        response = await admin_users.get_user_available_tariffs(5, include_inactive=True, admin=ADMIN, db=AsyncMock())

    [item] = response.tariffs
    assert item.daily_price_kopeks == WIRE
    assert item.price_per_day_kopeks == WIRE
    assert item.device_price_kopeks == WIRE
    assert item.traffic_topup_packages == {'50': WIRE}
    assert item.period_prices[0].price_kopeks == WIRE
    assert item.period_prices[0].price_rubles == TOMAN


@pytest.mark.asyncio
async def test_user_available_tariffs_keep_unset_device_price_none() -> None:
    from app.cabinet.routes import admin_users
    from app.database.crud import tariff as tariff_crud

    user = _ns(id=5, promo_group_id=None, promo_group=None, subscriptions=[])

    with (
        patch.object(admin_users, 'get_user_by_id', AsyncMock(return_value=user)),
        patch.object(tariff_crud, 'get_all_tariffs', AsyncMock(return_value=[_tariff(device_price_kopeks=None)])),
    ):
        response = await admin_users.get_user_available_tariffs(5, include_inactive=True, admin=ADMIN, db=AsyncMock())

    assert response.tariffs[0].device_price_kopeks is None


def test_admin_user_gift_item_price_on_the_wire() -> None:
    from app.cabinet.routes.admin_users import _build_gift_item

    purchase = _ns(
        id=1,
        token='abcdefghijklmnop',
        status='paid',
        tariff=_ns(name='Basic', device_limit=2),
        period_days=30,
        amount_kopeks=TOMAN,
        payment_method='balance',
        gift_recipient_type=None,
        gift_recipient_value=None,
        gift_message=None,
        buyer_user_id=None,
        user_id=5,
        created_at=NOW,
        paid_at=None,
        delivered_at=None,
    )

    assert _build_gift_item(purchase).amount_kopeks == WIRE


# ── admin_servers ─────────────────────────────────────────────────────────────


def _server(**overrides) -> SimpleNamespace:
    base = {
        'id': 3,
        'squad_uuid': 'u1',
        'display_name': 'NL-1',
        'original_name': 'nl1',
        'country_code': 'NL',
        'description': None,
        'is_available': True,
        'is_trial_eligible': True,
        'price_kopeks': TOMAN,
        'max_users': None,
        'current_users': 0,
        'sort_order': 0,
        'is_full': False,
        'availability_status': 'available',
        'allowed_promo_groups': [],
        'created_at': NOW,
        'updated_at': NOW,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_list_servers_price_on_the_wire_and_rubles_toman() -> None:
    from app.cabinet.routes import admin_servers

    with patch.object(admin_servers, 'get_all_server_squads', AsyncMock(return_value=([_server()], 1))):
        response = await admin_servers.list_servers(include_unavailable=True, admin=ADMIN, db=AsyncMock())

    assert response.servers[0].price_kopeks == WIRE
    assert response.servers[0].price_rubles == TOMAN


@pytest.mark.asyncio
async def test_get_server_price_on_the_wire_and_rubles_toman() -> None:
    from app.cabinet.routes import admin_servers

    with (
        patch.object(admin_servers, 'get_server_squad_by_id', AsyncMock(return_value=_server())),
        patch.object(admin_servers, '_get_server_promo_groups', AsyncMock(return_value=[])),
        patch.object(admin_servers, '_get_tariffs_using_server', AsyncMock(return_value=[])),
        patch.object(admin_servers, 'count_active_users_for_squad', AsyncMock(return_value=0)),
    ):
        response = await admin_servers.get_server(3, admin=ADMIN, db=AsyncMock())

    assert response.price_kopeks == WIRE
    assert response.price_rubles == TOMAN


@pytest.mark.asyncio
async def test_update_server_stores_toman() -> None:
    from app.cabinet.routes import admin_servers
    from app.cabinet.schemas.servers import ServerUpdateRequest

    with (
        patch.object(admin_servers, 'get_server_squad_by_id', AsyncMock(return_value=_server())),
        patch.object(admin_servers, 'update_server_squad', AsyncMock()) as update_mock,
        patch.object(admin_servers, 'get_server', AsyncMock(return_value='detail')),
    ):
        await admin_servers.update_existing_server(
            3, ServerUpdateRequest(price_kopeks=WIRE), admin=ADMIN, db=AsyncMock()
        )

    assert update_mock.call_args.kwargs['price_kopeks'] == TOMAN


# ── admin_remnawave ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_squads_local_price_on_the_wire_and_unsynced_none() -> None:
    from app.cabinet.routes import admin_remnawave

    service = _ns(
        is_configured=True,
        get_all_squads=AsyncMock(return_value=[{'uuid': 'u1', 'name': 'S'}, {'uuid': 'u2', 'name': 'T'}]),
    )

    with (
        patch.object(admin_remnawave, '_get_service', lambda: service),
        patch.object(admin_remnawave, 'get_all_server_squads', AsyncMock(return_value=([_server()], 1))),
    ):
        response = await admin_remnawave.list_squads(admin=ADMIN, db=AsyncMock())

    synced, unsynced = response.items
    assert synced.price_kopeks == WIRE
    assert unsynced.price_kopeks is None


@pytest.mark.asyncio
async def test_squad_details_local_price_on_the_wire() -> None:
    from app.cabinet.routes import admin_remnawave

    service = _ns(is_configured=True, get_squad_details=AsyncMock(return_value={'uuid': 'u1', 'name': 'S'}))

    with (
        patch.object(admin_remnawave, '_get_service', lambda: service),
        patch.object(admin_remnawave, 'get_server_squad_by_uuid', AsyncMock(return_value=_server())),
        patch.object(admin_remnawave, 'count_active_users_for_squad', AsyncMock(return_value=0)),
    ):
        response = await admin_remnawave.get_squad_details('u1', admin=ADMIN, db=AsyncMock())

    assert response.price_kopeks == WIRE


# ── admin_coupons ─────────────────────────────────────────────────────────────


def _batch(**overrides) -> SimpleNamespace:
    base = {
        'id': 5,
        'name': 'Partner',
        'tariff_id': 3,
        'tariff': _ns(name='Basic'),
        'period_days': 30,
        'coupons_total': 5,
        'wholesale_price_kopeks': TOMAN,
        'valid_until': None,
        'is_revoked': False,
        'created_at': NOW,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_coupon_batch_wholesale_price_on_the_wire() -> None:
    from app.cabinet.routes.admin_coupons import _serialize_batch

    assert _serialize_batch(_batch(), {}).wholesale_price_kopeks == WIRE


@pytest.mark.asyncio
async def test_create_coupon_batch_stores_toman(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.cabinet.routes import admin_coupons
    from app.cabinet.schemas.coupons import CouponBatchCreateRequest

    monkeypatch.setattr(type(settings), 'get_bot_username', lambda self: 'testbot')
    payload = CouponBatchCreateRequest(
        name='Partner', tariff_id=3, period_days=30, coupons_count=5, wholesale_price_kopeks=WIRE
    )

    with (
        patch.object(admin_coupons, 'get_tariff_by_id', AsyncMock(return_value=_ns(id=3, is_active=True))),
        patch.object(admin_coupons, 'create_coupon_batch', AsyncMock(return_value=_batch())) as create_mock,
        patch.object(admin_coupons, 'get_batch_coupon_tokens', AsyncMock(return_value=[])),
        patch.object(admin_coupons, 'get_batch_status_counts', AsyncMock(return_value={})),
    ):
        response = await admin_coupons.create_coupon_batch_endpoint(payload, admin=ADMIN, db=AsyncMock())

    assert create_mock.call_args.kwargs['wholesale_price_kopeks'] == TOMAN
    assert response.wholesale_price_kopeks == WIRE


# ── admin_promocodes (promo groups) ───────────────────────────────────────────


def _promo_group(**overrides) -> SimpleNamespace:
    base = {
        'id': 2,
        'name': 'VIP',
        'server_discount_percent': 0,
        'traffic_discount_percent': 0,
        'device_discount_percent': 0,
        'period_discounts': {},
        'auto_assign_total_spent_kopeks': TOMAN,
        'apply_discounts_to_addons': True,
        'is_default': False,
        'created_at': NOW,
        'updated_at': NOW,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_promo_group_auto_assign_threshold_on_the_wire() -> None:
    from app.cabinet.routes.admin_promocodes import _serialize_promo_group

    assert _serialize_promo_group(_promo_group()).auto_assign_total_spent_kopeks == WIRE
    assert (
        _serialize_promo_group(_promo_group(auto_assign_total_spent_kopeks=None)).auto_assign_total_spent_kopeks is None
    )


@pytest.mark.asyncio
async def test_create_promo_group_stores_toman_threshold() -> None:
    from app.cabinet.routes import admin_promocodes

    payload = admin_promocodes.PromoGroupCreateRequest(name='VIP', auto_assign_total_spent_kopeks=WIRE)

    with patch.object(admin_promocodes, 'create_promo_group', AsyncMock(return_value=_promo_group())) as create_mock:
        await admin_promocodes.create_promo_group_endpoint(payload, admin=ADMIN, db=AsyncMock())

    assert create_mock.call_args.kwargs['auto_assign_total_spent_kopeks'] == TOMAN


@pytest.mark.asyncio
async def test_update_promo_group_stores_toman_threshold_and_keeps_none() -> None:
    from app.cabinet.routes import admin_promocodes

    with (
        patch.object(admin_promocodes, 'get_promo_group_by_id', AsyncMock(return_value=_promo_group())),
        patch.object(admin_promocodes, 'update_promo_group', AsyncMock(return_value=_promo_group())) as update_mock,
        patch.object(admin_promocodes, 'count_promo_group_members', AsyncMock(return_value=0)),
    ):
        await admin_promocodes.update_promo_group_endpoint(
            2,
            admin_promocodes.PromoGroupUpdateRequest(auto_assign_total_spent_kopeks=WIRE),
            admin=ADMIN,
            db=AsyncMock(),
        )
        assert update_mock.call_args.kwargs['auto_assign_total_spent_kopeks'] == TOMAN

        await admin_promocodes.update_promo_group_endpoint(
            2, admin_promocodes.PromoGroupUpdateRequest(name='VIP2'), admin=ADMIN, db=AsyncMock()
        )
        assert update_mock.call_args.kwargs['auto_assign_total_spent_kopeks'] is None


# ── admin_payment_methods ─────────────────────────────────────────────────────


def _pm_config(**overrides) -> SimpleNamespace:
    base = {
        'method_id': 'c2c',
        'sort_order': 0,
        'is_enabled': True,
        'display_name': None,
        'description': None,
        'sub_options': None,
        'quick_amounts': [TOMAN, 2 * TOMAN],
        'min_amount_kopeks': TOMAN,
        'max_amount_kopeks': 10 * TOMAN,
        'user_type_filter': 'all',
        'first_topup_filter': 'any',
        'promo_group_filter_mode': 'all',
        'allowed_promo_groups': [],
        'open_url_direct': False,
        'created_at': NOW,
        'updated_at': NOW,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_payment_method_limits_and_quick_amounts_on_the_wire() -> None:
    from app.cabinet.routes.admin_payment_methods import _enrich_config

    defaults = {'c2c': {'default_display_name': 'Card', 'default_min': TOMAN, 'default_max': 10 * TOMAN}}

    response = _enrich_config(_pm_config(), defaults)

    assert response.min_amount_kopeks == WIRE
    assert response.max_amount_kopeks == 10 * WIRE
    assert response.quick_amounts == [WIRE, 2 * WIRE]
    assert response.default_min_amount_kopeks == WIRE
    assert response.default_max_amount_kopeks == 10 * WIRE


def test_payment_method_unset_limits_stay_none_and_defaults_are_scaled() -> None:
    from app.cabinet.routes.admin_payment_methods import _enrich_config
    from app.services.payment_method_config_service import DEFAULT_QUICK_AMOUNTS

    response = _enrich_config(_pm_config(quick_amounts=None, min_amount_kopeks=None, max_amount_kopeks=None), {})

    assert response.min_amount_kopeks is None
    assert response.max_amount_kopeks is None
    assert response.quick_amounts is None
    assert response.default_quick_amounts == [amount * 100 for amount in DEFAULT_QUICK_AMOUNTS]


@pytest.mark.asyncio
async def test_update_payment_method_stores_toman_limits_and_quick_amounts() -> None:
    from app.cabinet.routes import admin_payment_methods

    request = admin_payment_methods.PaymentMethodConfigUpdateRequest(
        min_amount_kopeks=WIRE, max_amount_kopeks=10 * WIRE, quick_amounts=[2 * WIRE, WIRE]
    )

    with (
        patch.object(admin_payment_methods, 'update_config', AsyncMock(return_value=_pm_config())) as update_mock,
        patch.object(admin_payment_methods, '_get_method_defaults', dict),
    ):
        await admin_payment_methods.update_payment_method('c2c', request, admin=ADMIN, db=AsyncMock())

    data = update_mock.call_args.args[2]
    assert data['min_amount_kopeks'] == TOMAN
    assert data['max_amount_kopeks'] == 10 * TOMAN
    assert data['quick_amounts'] == [TOMAN, 2 * TOMAN]


@pytest.mark.asyncio
async def test_update_payment_method_reset_flags_still_clear_the_columns() -> None:
    from app.cabinet.routes import admin_payment_methods

    request = admin_payment_methods.PaymentMethodConfigUpdateRequest(
        reset_min_amount=True, reset_max_amount=True, reset_quick_amounts=True
    )

    with (
        patch.object(admin_payment_methods, 'update_config', AsyncMock(return_value=_pm_config())) as update_mock,
        patch.object(admin_payment_methods, '_get_method_defaults', dict),
    ):
        await admin_payment_methods.update_payment_method('c2c', request, admin=ADMIN, db=AsyncMock())

    data = update_mock.call_args.args[2]
    assert data == {'quick_amounts': None, 'min_amount_kopeks': None, 'max_amount_kopeks': None}


# ── admin_wheel / wheel ───────────────────────────────────────────────────────


def _prize(**overrides) -> SimpleNamespace:
    base = {
        'id': 9,
        'config_id': 1,
        'prize_type': 'balance',
        'prize_value': TOMAN,
        'display_name': 'Cash',
        'emoji': '🎁',
        'color': '#3B82F6',
        'prize_value_kopeks': TOMAN,
        'sort_order': 0,
        'manual_probability': None,
        'is_active': True,
        'promo_balance_bonus_kopeks': TOMAN,
        'promo_subscription_days': 0,
        'promo_traffic_gb': 0,
        'created_at': NOW,
        'updated_at': NOW,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _spin(**overrides) -> SimpleNamespace:
    base = {
        'id': 4,
        'user_id': 5,
        'user': _ns(username='u'),
        'prize_id': 9,
        'prize': None,
        'payment_type': 'stars',
        'payment_amount': 1,
        'payment_value_kopeks': TOMAN,
        'prize_type': 'balance',
        'prize_value': TOMAN,
        'prize_display_name': 'Cash',
        'prize_value_kopeks': TOMAN,
        'is_applied': True,
        'created_at': NOW,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_admin_prizes_value_on_the_wire_and_promo_bonus_toman() -> None:
    from app.cabinet.routes import admin_wheel

    with (
        patch.object(admin_wheel, 'get_or_create_wheel_config', AsyncMock(return_value=_ns(id=1))),
        patch.object(admin_wheel, 'get_wheel_prizes', AsyncMock(return_value=[_prize()])),
    ):
        [prize] = await admin_wheel.get_prizes(admin=ADMIN, db=AsyncMock())

    assert prize.prize_value_kopeks == WIRE
    assert prize.promo_balance_bonus_kopeks == TOMAN


@pytest.mark.asyncio
async def test_admin_wheel_config_prizes_value_on_the_wire() -> None:
    from app.cabinet.routes import admin_wheel

    config = _ns(
        id=1,
        is_enabled=True,
        name='Wheel',
        spin_cost_stars=1,
        spin_cost_days=1,
        spin_cost_stars_enabled=True,
        spin_cost_days_enabled=False,
        rtp_percent=80,
        daily_spin_limit=3,
        min_subscription_days_for_day_payment=1,
        promo_prefix='W',
        promo_validity_days=7,
        created_at=NOW,
        updated_at=NOW,
    )

    with (
        patch.object(admin_wheel, 'get_or_create_wheel_config', AsyncMock(return_value=config)),
        patch.object(admin_wheel, 'update_wheel_config', AsyncMock(return_value=config)),
        patch.object(admin_wheel, 'get_wheel_prizes', AsyncMock(return_value=[_prize()])),
    ):
        listed = await admin_wheel.get_admin_wheel_config(admin=ADMIN, db=AsyncMock())
        updated = await admin_wheel.update_admin_wheel_config(
            admin_wheel.UpdateWheelConfigRequest(name='Wheel'), admin=ADMIN, db=AsyncMock()
        )

    assert listed.prizes[0].prize_value_kopeks == WIRE
    assert updated.prizes[0].prize_value_kopeks == WIRE


@pytest.mark.asyncio
async def test_create_prize_stores_toman_and_echoes_wire() -> None:
    from app.cabinet.routes import admin_wheel

    request = admin_wheel.CreatePrizeRequest(
        prize_type='balance_bonus', prize_value=TOMAN, display_name='Cash', prize_value_kopeks=WIRE
    )

    with (
        patch.object(admin_wheel, 'get_or_create_wheel_config', AsyncMock(return_value=_ns(id=1))),
        patch.object(admin_wheel, 'create_wheel_prize', AsyncMock(return_value=_prize())) as create_mock,
    ):
        response = await admin_wheel.create_prize(request, admin=ADMIN, db=AsyncMock())

    assert create_mock.call_args.kwargs['prize_value_kopeks'] == TOMAN
    assert response.prize_value_kopeks == WIRE


@pytest.mark.asyncio
async def test_update_prize_stores_toman_and_leaves_other_fields_alone() -> None:
    from app.cabinet.routes import admin_wheel

    with patch.object(admin_wheel, 'update_wheel_prize', AsyncMock(return_value=_prize())) as update_mock:
        await admin_wheel.update_prize(
            9, admin_wheel.UpdatePrizeRequest(prize_value_kopeks=WIRE, sort_order=2), admin=ADMIN, db=AsyncMock()
        )

    assert update_mock.call_args.kwargs == {'prize_value_kopeks': TOMAN, 'sort_order': 2}


@pytest.mark.asyncio
async def test_wheel_statistics_totals_and_top_wins_on_the_wire() -> None:
    from app.cabinet.routes import admin_wheel

    stats = {
        'total_spins': 1,
        'total_revenue_kopeks': TOMAN,
        'total_payout_kopeks': 2 * TOMAN,
        'actual_rtp_percent': 50.0,
        'configured_rtp_percent': 80,
        'spins_by_payment_type': {},
        'prizes_distribution': [],
        'top_wins': [{'user_id': 5, 'username': 'u', 'prize_display_name': 'Cash', 'prize_value_kopeks': TOMAN}],
        'period_from': None,
        'period_to': None,
    }

    with patch.object(admin_wheel.wheel_service, 'get_statistics', AsyncMock(return_value=stats)):
        response = await admin_wheel.get_statistics(date_from=None, date_to=None, admin=ADMIN, db=AsyncMock())

    assert response.total_revenue_kopeks == WIRE
    assert response.total_payout_kopeks == 2 * WIRE
    assert response.top_wins[0]['prize_value_kopeks'] == WIRE


@pytest.mark.asyncio
async def test_admin_spins_values_on_the_wire() -> None:
    from app.cabinet.routes import admin_wheel

    with patch.object(admin_wheel, 'get_all_spins', AsyncMock(return_value=([_spin()], 1))):
        response = await admin_wheel.get_all_spins_endpoint(
            user_id=None, date_from=None, date_to=None, page=1, per_page=50, admin=ADMIN, db=AsyncMock()
        )

    assert response.items[0].payment_value_kopeks == WIRE
    assert response.items[0].prize_value_kopeks == WIRE


@pytest.mark.asyncio
async def test_user_spin_history_prize_value_on_the_wire() -> None:
    from app.cabinet.routes import wheel

    with patch.object(wheel, 'get_user_spin_history', AsyncMock(return_value=([_spin()], 1))):
        response = await wheel.get_spin_history(page=1, per_page=20, user=_ns(id=5), db=AsyncMock())

    assert response.items[0].prize_value_kopeks == WIRE
