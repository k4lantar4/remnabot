"""Pending-payment responses apply the wire scale at the route, never inside the shared service.

Stars and Toman CryptoBot records carry plain Toman (``amount_is_toman``), because the service is also
used by the Telegram admin bot, which has no request and so no ``X-Amount-Scale``. The cabinet
routes turn that into ``amount_kopeks`` on the negotiated scale; ``amount_rubles`` is display Toman on
both scales (F-087). Deferred ruble-gateway records keep their provider amount and the old contract.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.cabinet.routes import admin_payments, balance
from app.database.models import PaymentMethod
from app.services.payment_verification_service import PendingPayment
from app.utils.wire_scale import TOMAN_WIRE, reset_wire_scale, use_wire_scale


NOW = datetime(2026, 9, 12, tzinfo=UTC)
ROUTES = pytest.mark.parametrize('route', [balance, admin_payments], ids=['user', 'admin'])


def _pending(method: PaymentMethod, amount: int, *, is_toman: bool = True) -> PendingPayment:
    return PendingPayment(
        method=method,
        local_id=1,
        identifier='tx-1',
        amount_kopeks=amount,
        status='pending',
        is_paid=False,
        created_at=NOW,
        user=SimpleNamespace(id=1, telegram_id=42, username='u', email=None),
        payment=None,
        amount_is_toman=is_toman,
    )


@pytest.fixture
def toman_request():
    token = use_wire_scale(TOMAN_WIRE)
    yield
    reset_wire_scale(token)


def test_record_amount_toman_is_the_stored_toman() -> None:
    assert _pending(PaymentMethod.TELEGRAM_STARS, 50_000).amount_toman == 50_000
    assert _pending(PaymentMethod.CRYPTOBOT, 1_000_000).amount_toman == 1_000_000


def test_record_amount_toman_ignores_the_request_scale(toman_request) -> None:
    assert _pending(PaymentMethod.TELEGRAM_STARS, 50_000).amount_toman == 50_000


@ROUTES
@pytest.mark.parametrize(
    ('method', 'toman'),
    [(PaymentMethod.TELEGRAM_STARS, 50_000), (PaymentMethod.CRYPTOBOT, 1_000_000)],
)
def test_without_the_header_amount_kopeks_is_the_catalog_wire(route, method, toman) -> None:
    response = route._record_to_response(_pending(method, toman))

    assert response.amount_kopeks == toman * 100  # TopUpResult.tsx still divides by 100
    assert response.amount_rubles == toman


@ROUTES
def test_with_the_header_amount_kopeks_is_toman(route, toman_request) -> None:
    response = route._record_to_response(_pending(PaymentMethod.TELEGRAM_STARS, 50_000))

    assert response.amount_kopeks == 50_000
    assert response.amount_rubles == 50_000


@ROUTES
def test_ruble_gateway_record_keeps_its_provider_amount(route) -> None:
    response = route._record_to_response(_pending(PaymentMethod.MULENPAY, 100_000, is_toman=False))

    assert response.amount_kopeks == 100_000
    assert response.amount_rubles == 1_000
