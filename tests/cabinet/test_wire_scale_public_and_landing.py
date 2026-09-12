"""Wire-scale boundary for the public gift/landing config, the admin landing stats and the
pending-payment lookup.

Since revision 0115 every stored amount is Toman 1:1, but the cabinet still divides these JSON
fields by 100 (``formatPrice`` in ``GiftSubscription.tsx`` / ``QuickPurchase.tsx``,
``KOPEKS_DIVISOR`` in ``AdminLandingStats.tsx``). So a 990-Toman price must leave the backend as
``99000`` exactly once, at the response, while the ``price_label`` string keeps the Toman number.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cabinet.routes import admin_landings, balance as balance_routes, gift as gift_routes, landing as landing_routes
from app.database.models import LandingPage, PaymentMethod, Tariff
from app.services.payment_verification_service import PendingPayment
from app.utils.amount_columns import looks_like_money_column, scale_of


PRICE_TOMAN = 990
PRICE_WIRE = 99_000
ORIGINAL_TOMAN = 1_200
ORIGINAL_WIRE = 120_000
LIMIT_TOMAN = 50_000
LIMIT_WIRE = 5_000_000
BALANCE_TOMAN = 150_000
#: Unpersisted ``Tariff`` rows have no column defaults; the response model needs these ints.
_TARIFF_LIMITS = {'traffic_limit_gb': 100, 'device_limit': 1, 'tier_level': 1}


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        balance_kopeks=BALANCE_TOMAN,
        promo_group=None,
        promo_offer_discount_percent=0,
        promo_offer_discount_expires_at=None,
    )


# ── gift config ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gift_config_prices_are_wired_x100_and_labels_stay_toman(monkeypatch) -> None:
    offer = SimpleNamespace(
        tariff_id=1,
        tariff_name='Gold',
        tariff_description=None,
        traffic_limit_gb=100,
        device_limit=3,
        quotes=[
            SimpleNamespace(
                period_days=30,
                final_price_kopeks=PRICE_TOMAN,
                original_price_kopeks=ORIGINAL_TOMAN,
                discount_percent=17,
            ),
            SimpleNamespace(
                period_days=90,
                final_price_kopeks=2_500,
                original_price_kopeks=2_500,
                discount_percent=0,
            ),
        ],
    )
    monkeypatch.setattr(gift_routes, 'is_gift_enabled', AsyncMock(return_value=True))
    monkeypatch.setattr(gift_routes, 'list_gift_offers', AsyncMock(return_value=[offer]))
    monkeypatch.setattr(
        gift_routes,
        'get_enabled_methods_for_user',
        AsyncMock(
            return_value=[
                {'id': 'c2c', 'name': 'Card', 'min_amount_kopeks': LIMIT_TOMAN, 'max_amount_kopeks': None},
            ]
        ),
    )

    config = await gift_routes.get_gift_config(user=_user(), db=AsyncMock())

    discounted, plain = config.tariffs[0].periods
    assert discounted.price_kopeks == PRICE_WIRE
    assert discounted.original_price_kopeks == ORIGINAL_WIRE
    assert '990' in discounted.price_label and '99,000' not in discounted.price_label
    assert plain.price_kopeks == 250_000
    assert plain.original_price_kopeks is None

    (method,) = config.payment_methods
    assert method.min_amount_kopeks == LIMIT_WIRE
    assert method.max_amount_kopeks is None

    # Balance was Toman on the wire before Phase C and stays so.
    assert config.balance_kopeks == BALANCE_TOMAN


# ── public landing config ─────────────────────────────────────────────────────


def _scalars_result(items) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _landing(**overrides) -> LandingPage:
    landing = LandingPage(
        slug='promo',
        title={'en': 'Promo'},
        features=[],
        allowed_tariff_ids=[1],
        allowed_periods={},
        payment_methods=[],
        gift_enabled=True,
        sticky_pay_button=False,
        analytics_view_enabled=False,
        analytics_click_enabled=False,
    )
    for key, value in overrides.items():
        setattr(landing, key, value)
    return landing


@pytest.mark.asyncio
async def test_landing_tariff_prices_are_wired_x100_and_labels_stay_toman() -> None:
    tariff = Tariff(id=1, name='Gold', is_active=True, period_prices={'30': PRICE_TOMAN}, **_TARIFF_LIMITS)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalars_result([tariff]))

    (out,) = await landing_routes._load_landing_tariffs(db, _landing())

    (period,) = out.periods
    assert period.price_kopeks == PRICE_WIRE
    assert period.original_price_kopeks is None
    assert '990' in period.price_label and '99,000' not in period.price_label
    assert out.daily_price_kopeks == 0


@pytest.mark.asyncio
async def test_landing_discounted_price_and_original_are_both_wired() -> None:
    tariff = Tariff(id=1, name='Gold', is_active=True, period_prices={'30': ORIGINAL_TOMAN}, **_TARIFF_LIMITS)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalars_result([tariff]))
    discount = landing_routes.LandingDiscountInfo(percent=10, ends_at='2030-01-01T00:00:00+00:00')

    (out,) = await landing_routes._load_landing_tariffs(db, _landing(), discount)

    (period,) = out.periods
    assert period.original_price_kopeks == ORIGINAL_WIRE
    assert period.price_kopeks == 108_000  # 1200 Toman - 10% = 1080 Toman
    assert '1,080' in period.price_label and '108,000' not in period.price_label
    assert '1,200' in period.original_price_label


@pytest.mark.asyncio
async def test_landing_daily_price_is_wired() -> None:
    tariff = Tariff(
        id=1,
        name='Daily',
        is_active=True,
        is_daily=True,
        daily_price_kopeks=PRICE_TOMAN,
        period_prices={},
        **_TARIFF_LIMITS,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalars_result([tariff]))

    (out,) = await landing_routes._load_landing_tariffs(db, _landing())

    assert out.daily_price_kopeks == PRICE_WIRE
    assert out.periods[0].days == 1
    assert out.periods[0].price_kopeks == PRICE_WIRE


@pytest.mark.asyncio
async def test_landing_payment_method_limits_are_wired(monkeypatch) -> None:
    landing = _landing(
        payment_methods=[
            {'method_id': 'c2c', 'display_name': 'Card', 'min_amount_kopeks': LIMIT_TOMAN, 'max_amount_kopeks': None},
        ]
    )
    monkeypatch.setattr(landing_routes.RateLimitCache, 'is_ip_rate_limited', AsyncMock(return_value=False))
    monkeypatch.setattr(landing_routes, 'get_client_ip', lambda request: '127.0.0.1')
    monkeypatch.setattr(landing_routes, 'get_active_landing_by_slug', AsyncMock(return_value=landing))
    monkeypatch.setattr(landing_routes, '_load_landing_tariffs', AsyncMock(return_value=[]))
    monkeypatch.setattr(landing_routes, '_get_method_defaults', dict)

    config = await landing_routes.get_landing_config(
        raw_request=SimpleNamespace(headers={}, cookies={}), slug='promo', lang='en', db=AsyncMock()
    )

    (method,) = config.payment_methods
    assert method.min_amount_kopeks == LIMIT_WIRE
    assert method.max_amount_kopeks is None


# ── admin landing stats ───────────────────────────────────────────────────────


class _SequencedDb:
    """``execute`` hands back the prepared results in call order."""

    def __init__(self, results: list[MagicMock]) -> None:
        self._results = list(results)

    async def execute(self, _stmt):
        return self._results.pop(0)


def _one(row) -> MagicMock:
    result = MagicMock()
    result.one.return_value = row
    return result


def _all(rows) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    return result


@pytest.mark.asyncio
async def test_landing_stats_revenue_fields_are_wired(monkeypatch) -> None:
    today = datetime.now(UTC).date()
    revenue_toman = 2 * PRICE_TOMAN
    db = _SequencedDb(
        [
            _one(
                SimpleNamespace(
                    total_created=3,
                    total_successful=2,
                    total_revenue_kopeks=revenue_toman,
                    total_gifts=1,
                    total_gifts_claimed=0,
                )
            ),
            _all([SimpleNamespace(day=today, purchases=2, revenue_kopeks=revenue_toman, gifts=1)]),
            _all([]),
            _all([SimpleNamespace(tariff_id=1, tariff_name='Gold', purchases=2, revenue_kopeks=revenue_toman)]),
            _all([SimpleNamespace(method='c2c', purchases=2, revenue_kopeks=revenue_toman)]),
            _all([]),
        ]
    )
    monkeypatch.setattr(admin_landings, 'get_landing_by_id', AsyncMock(return_value=SimpleNamespace(id=1)))

    stats = await admin_landings.get_landing_stats(landing_id=1, admin=SimpleNamespace(id=1), db=db)

    assert stats.total_revenue_kopeks == 2 * PRICE_WIRE
    # The average is taken in Toman (1980 // 2 = 990) and only then put on the wire.
    assert stats.avg_purchase_kopeks == PRICE_WIRE
    assert stats.daily_stats[-1].date == today.isoformat()
    assert stats.daily_stats[-1].revenue_kopeks == 2 * PRICE_WIRE
    assert stats.daily_stats[0].revenue_kopeks == 0
    assert stats.tariff_stats[0].revenue_kopeks == 2 * PRICE_WIRE
    assert stats.payment_method_stats[0].revenue_kopeks == 2 * PRICE_WIRE


@pytest.mark.asyncio
async def test_landing_purchase_list_amount_is_wired(monkeypatch) -> None:
    count = MagicMock()
    count.scalar_one.return_value = 1
    row = SimpleNamespace(
        id=1,
        token='abcdefghijkl',
        contact_type='email',
        contact_value='a@b.c',
        is_gift=False,
        gift_recipient_type=None,
        gift_recipient_value=None,
        tariff_name='Gold',
        period_days=30,
        amount_kopeks=PRICE_TOMAN,
        currency='RUB',
        payment_method='c2c',
        status='paid',
        referrer=None,
        created_at=None,
        paid_at=None,
    )
    db = _SequencedDb([count, _all([row])])
    monkeypatch.setattr(admin_landings, 'get_landing_by_id', AsyncMock(return_value=SimpleNamespace(id=1)))

    page = await admin_landings.get_landing_purchases(
        landing_id=1, offset=0, limit=20, status_filter=None, admin=SimpleNamespace(id=1), db=db
    )

    assert page.total == 1
    assert page.items[0].amount_kopeks == PRICE_WIRE


# ── pending payments (balance.py) ─────────────────────────────────────────────


def _latest_payment_models() -> list[str]:
    """Model class names in ``get_latest_payment_by_method``'s method → model map."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(balance_routes.get_latest_payment_by_method)))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict) or not node.keys:
            continue
        if all(isinstance(k, ast.Attribute) and getattr(k.value, 'id', None) == 'PaymentMethod' for k in node.keys):
            return [v.id for v in node.values if isinstance(v, ast.Name)]
    raise AssertionError('model_map not found in get_latest_payment_by_method')


def test_latest_payment_lookup_reads_only_provider_currency_tables() -> None:
    """Why ``_record_to_response`` does not wire-scale ``amount_kopeks``.

    Every table the recent-payment lookup can read stores the gateway's own currency (ruble kopeks,
    crypto units), which ``TopUpResult.tsx`` divides by 100 into rubles. A Toman-scale table in this
    map would need ``wire_catalog_kopeks`` at the response; this pins that none is there.
    """
    from app.database import models

    names = _latest_payment_models()
    assert names, 'model_map is empty'
    for name in names:
        model = getattr(models, name)
        table = model.__tablename__
        for column in model.__table__.columns:
            if looks_like_money_column(column.name):
                assert scale_of(table, column.name) == 'provider', f'{table}.{column.name}'


def test_pending_payment_response_passes_provider_amount_through() -> None:
    record = PendingPayment(
        method=PaymentMethod.YOOKASSA,
        local_id=7,
        identifier='y-7',
        amount_kopeks=PRICE_WIRE,
        status='pending',
        is_paid=False,
        created_at=datetime.now(UTC),
        user=None,
        payment=SimpleNamespace(),
    )

    response = balance_routes._record_to_response(record)

    assert response.amount_kopeks == PRICE_WIRE
