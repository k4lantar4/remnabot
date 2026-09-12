"""Admin money screens must speak the frozen catalog wire scale, not raw Toman.

Phase C (revision ``0115``) put every stored amount on Toman 1:1, while the HTTP contract stayed on
the old ``*_kopeks`` x100 scale because the cabinet still divides by 100 (``app/utils/wire_scale.py``).
Two admin responses were left sending a raw Toman number into a field the cabinet scales:

* ``GET /cabinet/admin/payments`` — ``amount_rubles`` is printed as-is by ``AdminPayments.tsx``,
  but ``PendingPayment.amount_kopeks`` is already on the wire scale, so it rendered 100x too big.
* ``GET /cabinet/admin/users/{id}/activity`` — only the transaction mapper filled ``amount_toman``;
  every other source fell back to the cabinet's ÷100 reading of ``amount_kopeks`` and rendered
  1/100 of the real amount.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.cabinet.routes.admin_payments import _record_to_response
from app.cabinet.routes.admin_users import _activity_sources
from app.cabinet.schemas.traffic import UserTrafficEnrichment
from app.database.models import PaymentMethod
from app.services.payment_verification_service import PendingPayment


NOW = datetime(2026, 9, 12, tzinfo=UTC)


# ── payments list ─────────────────────────────────────────────────────────────


def _pending(amount_kopeks: int) -> PendingPayment:
    return PendingPayment(
        method=PaymentMethod.TELEGRAM_STARS,
        local_id=1,
        identifier='tx-1',
        amount_kopeks=amount_kopeks,
        status='pending',
        is_paid=False,
        created_at=NOW,
        user=SimpleNamespace(id=1, telegram_id=42, username='u', email=None),
        payment=None,
    )


def test_pending_payment_amount_rubles_is_display_toman() -> None:
    """50,000 Toman arrives as 5,000,000 on the wire and must be printed as 50,000."""
    response = _record_to_response(_pending(5_000_000))

    assert response.amount_kopeks == 5_000_000  # wire scale, unchanged
    assert response.amount_rubles == 50_000


def test_pending_payment_amount_rubles_keeps_small_amounts() -> None:
    assert _record_to_response(_pending(100)).amount_rubles == 1
    assert _record_to_response(_pending(0)).amount_rubles == 0


# ── activity timeline ─────────────────────────────────────────────────────────


def _mapper(source: str):
    return _activity_sources(1)[source][3]


AMOUNT_SOURCES = {
    'event': SimpleNamespace(event_type='purchase', message='buy', amount_kopeks=50_000, occurred_at=NOW, extra=None),
    'wheel_spin': SimpleNamespace(
        prize_type='balance', prize_display_name='prize', prize_value_kopeks=50_000, created_at=NOW
    ),
    'poll': SimpleNamespace(reward_given=True, reward_amount_kopeks=50_000, completed_at=NOW),
    'gift_sent': SimpleNamespace(
        status='paid', gift_recipient_value='x', amount_kopeks=50_000, paid_at=NOW, created_at=NOW
    ),
    'gift_received': SimpleNamespace(status='paid', amount_kopeks=50_000, delivered_at=NOW, created_at=NOW),
    'referral_earning': SimpleNamespace(reason='purchase', amount_kopeks=50_000, created_at=NOW),
    'withdrawal': SimpleNamespace(status='pending', amount_kopeks=50_000, created_at=NOW),
}


@pytest.mark.parametrize('source', sorted(AMOUNT_SOURCES))
def test_every_activity_source_reports_display_toman(source: str) -> None:
    """Without ``amount_toman`` the cabinet divides ``amount_kopeks`` by 100 (adminBalance.ts)."""
    item = _mapper(source)(AMOUNT_SOURCES[source])

    assert item.amount_toman == 50_000, f'{source} would render as 500 Toman'


def test_poll_without_reward_reports_no_amount() -> None:
    item = _mapper('poll')(SimpleNamespace(reward_given=False, reward_amount_kopeks=50_000, completed_at=NOW))

    assert item.amount_kopeks is None
    assert item.amount_toman is None


def test_transaction_mapper_still_reports_toman() -> None:
    item = _mapper('transaction')(
        SimpleNamespace(
            type='deposit',
            description='topup',
            amount_kopeks=50_000,
            created_at=NOW,
            payment_method='manual',
            is_completed=True,
        )
    )

    assert item.amount_toman == 50_000


# ── traffic usage ─────────────────────────────────────────────────────────────


def test_traffic_enrichment_carries_a_toman_twin() -> None:
    """``total_spent_kopeks`` is a Toman sum the cabinet divides; the twin is what it must read."""
    enrichment = UserTrafficEnrichment(total_spent_kopeks=50_000, total_spent_toman=50_000)

    assert enrichment.total_spent_toman == 50_000
