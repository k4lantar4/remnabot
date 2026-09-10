"""Cabinet admin balance edit + admin transaction amounts on the Toman balance scale.

``users.balance_kopeks`` stores Toman 1:1 (Phase B). The admin «مبلغ به تومان»
form must credit exactly the entered Toman (``amount_display``), and every
admin surface must render balance-scale transactions (deposit, withdrawal …)
1:1 while catalog-scale ones (subscription_payment) stay ÷100.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from app.cabinet.routes.admin_users import (
    _activity_sources,
    _serialize_admin_transaction,
    update_user_balance,
)
from app.cabinet.schemas.users import UpdateBalanceRequest


NOW = datetime(2026, 9, 10, 18, 0, tzinfo=UTC)


def _tx(tx_type: str, amount: int, **extra) -> SimpleNamespace:
    base = {
        'id': 1,
        'type': tx_type,
        'amount_kopeks': amount,
        'description': 'مفتی',
        'payment_method': 'manual',
        'is_completed': True,
        'created_at': NOW,
    }
    base.update(extra)
    return SimpleNamespace(**base)


# ── UpdateBalanceRequest contract ─────────────────────────────────────────


def test_request_accepts_display_toman() -> None:
    req = UpdateBalanceRequest(amount_display=200_000, description='مفتی')
    assert req.amount_display == 200_000
    assert req.amount_kopeks is None


def test_request_keeps_legacy_storage_amount() -> None:
    req = UpdateBalanceRequest(amount_kopeks=1_000_000)
    assert req.amount_kopeks == 1_000_000
    assert req.amount_display is None


@pytest.mark.parametrize('payload', [{}, {'amount_kopeks': 100, 'amount_display': 100}])
def test_request_requires_exactly_one_amount(payload) -> None:
    with pytest.raises(ValidationError):
        UpdateBalanceRequest(**payload)


# ── update_user_balance credits the entered Toman 1:1 ─────────────────────


async def _call_update(request: UpdateBalanceRequest, balance: int = 0):
    user = SimpleNamespace(id=7833, balance_kopeks=balance)
    db = AsyncMock()
    add = AsyncMock(return_value=True)
    subtract = AsyncMock(return_value=True)
    with (
        patch('app.cabinet.routes.admin_users.get_user_by_id', AsyncMock(return_value=user)),
        patch('app.cabinet.routes.admin_users.add_user_balance', add),
        patch('app.cabinet.routes.admin_users.subtract_user_balance', subtract),
    ):
        response = await update_user_balance(user_id=7833, request=request, admin=SimpleNamespace(id=433), db=db)
    return response, add, subtract


async def test_display_topup_credits_exact_toman() -> None:
    _, add, subtract = await _call_update(UpdateBalanceRequest(amount_display=200_000, description='مفتی'))

    add.assert_awaited_once()
    assert add.await_args.kwargs['amount_kopeks'] == 200_000
    subtract.assert_not_awaited()


async def test_display_deduction_debits_exact_toman() -> None:
    _, add, subtract = await _call_update(UpdateBalanceRequest(amount_display=-50_000), balance=1_000_000)

    subtract.assert_awaited_once()
    assert subtract.await_args.kwargs['amount_kopeks'] == 50_000
    add.assert_not_awaited()


async def test_legacy_storage_amount_still_applied_one_to_one() -> None:
    _, add, _ = await _call_update(UpdateBalanceRequest(amount_kopeks=1_000_000))

    assert add.await_args.kwargs['amount_kopeks'] == 1_000_000


async def test_response_message_has_no_ruble_scale() -> None:
    response, _, _ = await _call_update(UpdateBalanceRequest(amount_display=50_000), balance=1_000_000)

    assert '₽' not in response.message
    assert '10000.00' not in response.message


# ── admin transaction rows (user detail + Balance tab list) ───────────────


def test_admin_deposit_row_is_toman_one_to_one() -> None:
    item = _serialize_admin_transaction(_tx('deposit', 1_000_000, payment_method='c2c'))

    assert item.amount_kopeks == 1_000_000
    assert item.amount_rubles == 1_000_000


def test_admin_manual_withdrawal_row_is_negative_toman() -> None:
    item = _serialize_admin_transaction(_tx('withdrawal', 50_000))

    assert item.amount_kopeks == -50_000
    assert item.amount_rubles == -50_000


def test_admin_subscription_payment_row_stays_catalog_scale() -> None:
    item = _serialize_admin_transaction(_tx('subscription_payment', -1_000_000, payment_method='balance'))

    assert item.amount_kopeks == -1_000_000
    assert item.amount_rubles == -10_000


# ── activity timeline exposes display Toman for transactions ──────────────


def _transaction_mapper():
    return _activity_sources(1)['transaction'][3]


def test_activity_deposit_has_toman_amount() -> None:
    item = _transaction_mapper()(_tx('deposit', 50_000, payment_method='c2c'))

    assert item.amount_kopeks == 50_000
    assert item.amount_toman == 50_000


def test_activity_subscription_payment_has_toman_amount() -> None:
    item = _transaction_mapper()(_tx('subscription_payment', -1_000_000, payment_method='balance'))

    assert item.amount_toman == -10_000


def test_activity_non_transaction_sources_leave_toman_unset() -> None:
    wheel = SimpleNamespace(
        prize_type='balance',
        prize_display_name='x',
        prize_value_kopeks=5_000,
        created_at=NOW,
    )
    item = _activity_sources(1)['wheel_spin'][3](wheel)

    assert item.amount_toman is None
