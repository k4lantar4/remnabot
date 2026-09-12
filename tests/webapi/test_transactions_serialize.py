"""Web API ``amount_rubles`` is the stored number, whatever the transaction type.

This test was written for F-030, when ``amount_rubles`` had to follow each type's storage scale:
deposits were Toman 1:1 while subscription payments were ×100, and a flat ÷100 turned a
50,000-Toman deposit into 500. Revision ``0115`` put every row on the Toman scale, so the rule it
guards is now the simple one — no type decides anything, and no division happens.

The 100x shapes are asserted explicitly, because getting them back is the regression that matters.
"""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.webapi.routes.transactions import _serialize


NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


def _tx(tx_type: str, amount: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        user_id=2,
        type=tx_type,
        amount_kopeks=amount,
        description='test',
        payment_method='c2c',
        external_id=None,
        is_completed=True,
        created_at=NOW,
        completed_at=NOW,
    )


@pytest.mark.parametrize(
    ('tx_type', 'stored'),
    [
        ('deposit', 50_000),
        ('withdrawal', -30_000),
        ('referral_reward', 20_000),
        ('subscription_payment', -50_000),
        ('gift_payment', -24_000),
    ],
)
def test_amount_rubles_is_the_stored_toman(tx_type: str, stored: int) -> None:
    response = _serialize(_tx(tx_type, stored))

    assert response.amount_rubles == float(stored)
    assert response.amount_kopeks == stored


def test_no_type_is_divided_by_a_hundred() -> None:
    """The bug this file exists for: a 50,000-Toman row rendering as 500."""
    for tx_type in ('deposit', 'subscription_payment'):
        response = _serialize(_tx(tx_type, 50_000))
        assert response.amount_rubles == 50_000.0
        assert response.amount_rubles != 500.0
