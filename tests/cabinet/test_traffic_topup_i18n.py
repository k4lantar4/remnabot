"""Traffic add-on descriptions and errors follow the user's language (F-041).

The cabinet wrote «Докупка N ГБ трафика» into every fa user's balance history and answered the
save-cart flow with Russian errors.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

import app.database.crud.user as user_crud
from app.cabinet.routes.subscription_modules import traffic as traffic_route
from app.database.models import PromoGroup, Subscription, User


def _make_user(language: str, traffic_discount_percent: int = 0) -> User:
    pg = PromoGroup(
        name='Test promo group',
        traffic_discount_percent=traffic_discount_percent,
        server_discount_percent=0,
        device_discount_percent=0,
        apply_discounts_to_addons=True,
        is_default=False,
    )
    user = User(id=1, telegram_id=123, balance_kopeks=1_000_000, language=language)
    user.promo_group = pg
    user.user_promo_groups = []
    return user


def _make_subscription(*, is_trial: bool = False) -> Subscription:
    sub = Subscription(
        id=10,
        user_id=1,
        status='trial' if is_trial else 'active',
        is_trial=is_trial,
        traffic_limit_gb=200,
        tariff_id=None,
    )
    sub.end_date = datetime.now(UTC) + timedelta(days=30)
    return sub


@pytest.fixture
def classic_mode(monkeypatch):
    settings_cls = type(traffic_route.settings)
    monkeypatch.setattr(settings_cls, 'is_tariffs_mode', lambda self: False)
    monkeypatch.setattr(settings_cls, 'is_traffic_topup_enabled', lambda self: True)
    monkeypatch.setattr(
        settings_cls,
        'get_traffic_topup_packages',
        lambda self: [{'gb': 10, 'price': 10000, 'enabled': True}],
    )


def _serve_subscription(monkeypatch, sub: Subscription) -> None:
    async def _fake_resolve(db, user, subscription_id):
        return sub

    monkeypatch.setattr(traffic_route, 'resolve_subscription', _fake_resolve)


@pytest.fixture
def captured_charge(monkeypatch):
    """Record the balance-history description and stop right after the charge."""
    captured: dict[str, str] = {}

    async def _fake_lock(db, user_id):
        return captured['user']

    async def _fake_subtract(db, user, amount, description, *args, **kwargs):
        captured['description'] = description
        return False  # purchase_traffic answers «Failed to charge balance» and stops

    monkeypatch.setattr(user_crud, 'lock_user_for_pricing', _fake_lock)
    monkeypatch.setattr(traffic_route, 'subtract_user_balance', _fake_subtract)
    return captured


async def _buy_10_gb(user: User, captured: dict) -> str:
    captured['user'] = user
    with pytest.raises(HTTPException):
        await traffic_route.purchase_traffic(
            request=traffic_route.TrafficPurchaseRequest(gb=10), user=user, db=object(), subscription_id=None
        )
    return captured['description']


@pytest.mark.asyncio
async def test_fa_balance_history_description(monkeypatch, classic_mode, captured_charge):
    _serve_subscription(monkeypatch, _make_subscription())
    assert await _buy_10_gb(_make_user('fa'), captured_charge) == 'خرید 10 گیگ ترافیک اضافه'


@pytest.mark.asyncio
async def test_fa_balance_history_description_with_discount(monkeypatch, classic_mode, captured_charge):
    _serve_subscription(monkeypatch, _make_subscription())
    user = _make_user('fa', traffic_discount_percent=20)
    assert await _buy_10_gb(user, captured_charge) == 'خرید 10 گیگ ترافیک اضافه (20% تخفیف)'


@pytest.mark.asyncio
async def test_ru_balance_history_description_unchanged(monkeypatch, classic_mode, captured_charge):
    _serve_subscription(monkeypatch, _make_subscription())
    assert await _buy_10_gb(_make_user('ru'), captured_charge) == 'Докупка 10 ГБ трафика'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('language', 'expected'),
    [
        ('fa', 'در دوره‌ی آزمایشی خرید ترافیک اضافه ممکن نیست'),
        ('ru', 'Докупка трафика недоступна на пробном периоде'),
    ],
)
async def test_save_cart_trial_error_in_user_language(monkeypatch, classic_mode, language, expected):
    _serve_subscription(monkeypatch, _make_subscription(is_trial=True))

    with pytest.raises(HTTPException) as exc_info:
        await traffic_route.save_traffic_cart(
            request=traffic_route.TrafficPurchaseRequest(gb=10),
            user=_make_user(language),
            db=object(),
            subscription_id=None,
        )

    assert exc_info.value.detail == expected


@pytest.mark.asyncio
async def test_save_cart_description_in_user_language(monkeypatch, classic_mode):
    _serve_subscription(monkeypatch, _make_subscription())
    saved: dict = {}

    async def _fake_save(user_id, cart_data):
        saved.update(cart_data)

    monkeypatch.setattr(traffic_route.user_cart_service, 'save_user_cart', _fake_save)

    await traffic_route.save_traffic_cart(
        request=traffic_route.TrafficPurchaseRequest(gb=10), user=_make_user('fa'), db=object(), subscription_id=None
    )

    assert saved['description'] == 'خرید 10 گیگ ترافیک اضافه'
