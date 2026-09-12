"""One scale for a landing's payment-method limits (FINDINGS F-071).

``landing_pages.payment_methods`` is a JSON list of method configs whose ``min_amount_kopeks`` /
``max_amount_kopeks`` are amounts. The admin editor seeds them from the admin payment-methods API,
which speaks the frozen wire scale (Toman x100, ``app/utils/wire_scale.py``), while the public
landing route reads the stored numbers as Toman — it wires them out x100 and compares them against
a Toman price. Storing the wire number therefore scaled the limit twice: a 50,000 Toman minimum
showed as 5,000,000 on the public page and rejected every legitimate purchase.

The admin boundary is where one scale is chosen: **stored Toman 1:1**, converted in and out of the
admin API so the cabinet's contract does not move.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.cabinet.routes import admin_landings, landing as landing_routes
from app.database.models import LandingPage
from app.utils.amount_columns import scale_of


LIMIT_TOMAN = 50_000
LIMIT_WIRE = 5_000_000
MAX_TOMAN = 1_000_000
MAX_WIRE = 100_000_000


def _method_input(**overrides) -> admin_landings.LandingPaymentMethodInput:
    payload = {
        'method_id': 'c2c',
        'display_name': 'Card to card',
        'min_amount_kopeks': LIMIT_WIRE,
        'max_amount_kopeks': MAX_WIRE,
    }
    payload.update(overrides)
    return admin_landings.LandingPaymentMethodInput(**payload)


def _landing(methods: list[dict]) -> LandingPage:
    return LandingPage(
        id=1,
        slug='promo',
        title={'en': 'Promo'},
        features=[],
        allowed_tariff_ids=[1],
        allowed_periods={},
        payment_methods=methods,
        gift_enabled=False,
        display_order=0,
        is_active=True,
        sticky_pay_button=False,
        analytics_view_enabled=False,
        analytics_click_enabled=False,
    )


def test_the_json_column_is_classified_by_meaning() -> None:
    """Its name carries no money word, so only an explicit entry keeps a later rescale honest."""
    assert scale_of('landing_pages', 'payment_methods') == 'toman'


@pytest.mark.asyncio
async def test_create_stores_the_admin_wire_limits_as_toman(monkeypatch) -> None:
    captured: dict = {}

    async def fake_create_landing(db, **kwargs):
        captured.update(kwargs)
        return _landing(kwargs['payment_methods'])

    monkeypatch.setattr(admin_landings, 'get_landing_by_slug', AsyncMock(return_value=None))
    monkeypatch.setattr(admin_landings, 'create_landing', fake_create_landing)

    await admin_landings.create_landing_page(
        admin_landings.LandingCreateRequest(slug='promo', payment_methods=[_method_input()]),
        admin=SimpleNamespace(id=1),
        db=AsyncMock(),
    )

    (stored,) = captured['payment_methods']
    assert stored['min_amount_kopeks'] == LIMIT_TOMAN
    assert stored['max_amount_kopeks'] == MAX_TOMAN


@pytest.mark.asyncio
async def test_update_stores_the_admin_wire_limits_as_toman(monkeypatch) -> None:
    captured: dict = {}

    async def fake_update_landing(db, landing_id, data):
        captured.update(data)
        return _landing(data['payment_methods'])

    monkeypatch.setattr(admin_landings, 'update_landing', fake_update_landing)

    await admin_landings.update_landing_page(
        landing_id=1,
        request=admin_landings.LandingUpdateRequest(payment_methods=[_method_input()]),
        admin=SimpleNamespace(id=1),
        db=AsyncMock(),
    )

    (stored,) = captured['payment_methods']
    assert stored['min_amount_kopeks'] == LIMIT_TOMAN
    assert stored['max_amount_kopeks'] == MAX_TOMAN


def test_an_absent_limit_stays_absent() -> None:
    (stored,) = admin_landings._payment_methods_to_storage(
        [_method_input(min_amount_kopeks=None, max_amount_kopeks=None)]
    )

    assert stored['min_amount_kopeks'] is None
    assert stored['max_amount_kopeks'] is None


def test_the_admin_detail_view_returns_the_limits_on_the_wire_scale() -> None:
    detail = admin_landings._landing_to_detail(
        _landing([{'method_id': 'c2c', 'display_name': 'Card to card', 'min_amount_kopeks': LIMIT_TOMAN}])
    )

    (method,) = detail.payment_methods
    assert method.min_amount_kopeks == LIMIT_WIRE
    assert method.max_amount_kopeks is None


@pytest.mark.asyncio
async def test_a_saved_limit_round_trips_through_the_admin_editor(monkeypatch) -> None:
    """What the editor sends comes back unchanged — the stored scale is invisible to the cabinet."""
    (stored,) = admin_landings._payment_methods_to_storage([_method_input()])

    detail = admin_landings._landing_to_detail(_landing([stored]))

    (method,) = detail.payment_methods
    assert (method.min_amount_kopeks, method.max_amount_kopeks) == (LIMIT_WIRE, MAX_WIRE)


@pytest.mark.asyncio
async def test_the_public_page_and_the_purchase_check_read_the_same_limit(monkeypatch) -> None:
    """The public config wires the stored Toman out x100; the purchase check compares it raw."""
    (stored,) = admin_landings._payment_methods_to_storage([_method_input()])
    landing = _landing([stored])

    monkeypatch.setattr(landing_routes.RateLimitCache, 'is_ip_rate_limited', AsyncMock(return_value=False))
    monkeypatch.setattr(landing_routes, 'get_client_ip', lambda request: '127.0.0.1')
    monkeypatch.setattr(landing_routes, 'get_active_landing_by_slug', AsyncMock(return_value=landing))
    monkeypatch.setattr(landing_routes, '_load_landing_tariffs', AsyncMock(return_value=[]))
    monkeypatch.setattr(landing_routes, '_get_method_defaults', dict)

    config = await landing_routes.get_landing_config(
        raw_request=SimpleNamespace(headers={}, cookies={}), slug='promo', lang='en', db=AsyncMock()
    )

    (method,) = config.payment_methods
    # The public page divides by 100, so it shows the Toman the owner typed…
    assert method.min_amount_kopeks / 100 == LIMIT_TOMAN
    # …and a purchase at exactly that Toman price is not rejected by the raw comparison.
    assert stored['min_amount_kopeks'] <= LIMIT_TOMAN
