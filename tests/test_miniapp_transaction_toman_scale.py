"""Miniapp history renders every transaction as the Toman it stores.

Before Phase C this file pinned the split: balance movements were Toman 1:1, catalog charges ÷100.
Revision ``0115`` removed the split, so a row's type no longer changes how it reads.
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.webapi.routes.miniapp import _serialize_transaction


def _tx(tx_type: str, amount: int, method: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        type=tx_type,
        amount_kopeks=amount,
        description=None,
        payment_method=method,
        external_id=None,
        is_completed=True,
        created_at=datetime(2026, 9, 10, tzinfo=UTC),
        completed_at=None,
    )


def test_c2c_deposit_shows_deposited_toman() -> None:
    item = _serialize_transaction(_tx('deposit', 50_000, 'c2c'))

    assert item.amount_kopeks == 50_000
    assert item.amount_rubles == 50_000


def test_manual_withdrawal_keeps_sign_and_toman() -> None:
    item = _serialize_transaction(_tx('withdrawal', -1_000_000, 'manual'))

    assert item.amount_rubles == -1_000_000


def test_a_subscription_payment_reads_like_a_deposit_of_the_same_size() -> None:
    """One scale: the charge for a 10,000-Toman tariff shows 10,000, not 100."""
    item = _serialize_transaction(_tx('subscription_payment', -10_000, 'balance'))

    assert item.amount_kopeks == -10_000
    assert item.amount_rubles == -10_000


@pytest.mark.parametrize(
    'tx_type',
    ['deposit', 'withdrawal', 'refund', 'referral_reward', 'subscription_payment', 'gift_payment'],
)
def test_the_type_no_longer_decides_a_scale(tx_type: str) -> None:
    item = _serialize_transaction(_tx(tx_type, 50_000, 'balance'))

    assert item.amount_rubles == 50_000
