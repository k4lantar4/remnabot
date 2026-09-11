"""Web API ``amount_rubles`` follows each transaction type's storage scale (F-030).

Balance-scale types (deposit, withdrawal, …) are stored Toman 1:1; catalog-scale
ones (subscription_payment) are ×100. A flat ÷100 made a 50,000-Toman deposit 500.
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
    ('tx_type', 'stored', 'expected'),
    [
        ('deposit', 50_000, 50_000.0),
        ('withdrawal', -30_000, -30_000.0),
        ('referral_reward', 20_000, 20_000.0),
        ('subscription_payment', 5_000_000, 50_000.0),
    ],
)
def test_amount_rubles_is_display_toman(tx_type: str, stored: int, expected: float) -> None:
    response = _serialize(_tx(tx_type, stored))

    assert response.amount_rubles == expected
    assert response.amount_kopeks == stored
