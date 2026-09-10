"""Miniapp history: balance-scale transactions are Toman 1:1, catalog ones ÷100."""

from datetime import UTC, datetime
from types import SimpleNamespace

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


def test_subscription_payment_stays_catalog_scale() -> None:
    item = _serialize_transaction(_tx('subscription_payment', -1_000_000, 'balance'))

    assert item.amount_rubles == -10_000
