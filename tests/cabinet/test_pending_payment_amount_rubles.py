"""F-087: the user's pending-payments response carries display Toman in ``amount_rubles``.

``PendingPayment.amount_kopeks`` is on the frozen x100 wire scale (``wire_scale.py``) because
``TopUpResult.tsx`` divides it by 100; ``amount_rubles`` is Toman everywhere else on the wire, as
the admin route already sends it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.cabinet.routes import admin_payments, balance
from app.database.models import PaymentMethod
from app.services.payment_verification_service import PendingPayment


NOW = datetime(2026, 9, 12, tzinfo=UTC)


def _pending(method: PaymentMethod, amount_kopeks: int) -> PendingPayment:
    return PendingPayment(
        method=method,
        local_id=1,
        identifier='tx-1',
        amount_kopeks=amount_kopeks,
        status='pending',
        is_paid=False,
        created_at=NOW,
        user=SimpleNamespace(id=1, telegram_id=42, username='u', email=None),
        payment=None,
    )


def test_record_amount_toman_reads_the_wire_amount() -> None:
    assert _pending(PaymentMethod.TELEGRAM_STARS, 5_000_000).amount_toman == 50_000
    assert _pending(PaymentMethod.CRYPTOBOT, 100_000_000).amount_toman == 1_000_000


@pytest.mark.parametrize(
    ('method', 'wire', 'toman'),
    [
        (PaymentMethod.TELEGRAM_STARS, 5_000_000, 50_000),
        (PaymentMethod.CRYPTOBOT, 100_000_000, 1_000_000),
    ],
)
def test_user_pending_payment_amount_rubles_is_display_toman(method, wire, toman) -> None:
    response = balance._record_to_response(_pending(method, wire))

    assert response.amount_kopeks == wire  # wire scale, unchanged for TopUpResult.tsx
    assert response.amount_rubles == toman


def test_user_and_admin_routes_agree_on_amount_rubles() -> None:
    record = _pending(PaymentMethod.TELEGRAM_STARS, 5_000_000)

    assert balance._record_to_response(record).amount_rubles == admin_payments._record_to_response(record).amount_rubles
