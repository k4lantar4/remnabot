"""Cabinet card-to-card routes: thin HTTP edge over ``app.plugins.c2c.cabinet``.

The cabinet sends and receives amounts on the frozen x100 wire scale; the adapter and the
database speak Toman 1:1. These tests pin that the route converts once, in both directions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.cabinet.routes import balance as balance_routes
from app.cabinet.schemas.balance import (
    C2cCancelRequest,
    C2cReceiptSubmitRequest,
    C2cSessionRequest,
    PaymentMethodResponse,
)
from app.config import settings
from app.database.models import C2cReceiptStatus
from app.plugins.c2c import cabinet as c2c_cabinet


CARD = {'label': 'Melli', 'number': '6037000000000001', 'holder': 'Ali'}


def _user(**overrides):
    data = {'id': 42, 'telegram_id': 111, 'language': 'en', 'restriction_topup': False}
    data.update(overrides)
    return SimpleNamespace(**data)


def _receipt(**overrides):
    now = datetime.now(UTC)
    data = {
        'id': 7,
        'user_id': 42,
        'status': C2cReceiptStatus.PENDING.value,
        'amount_kopeks': 100_000,
        'approved_amount_kopeks': None,
        'rejection_reason': None,
        'receipt_type': None,
        'card_index': 0,
        'card_label': 'Melli',
        'created_at': now,
        'expires_at': now,
        'processed_at': None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.fixture
def c2c_env(monkeypatch):
    # Live limits: 100,000 - 10,000,000 Toman, serialised x100 by /payment-methods.
    method = PaymentMethodResponse(
        id='c2c', name='c2c', min_amount_kopeks=10_000_000, max_amount_kopeks=1_000_000_000, is_available=True
    )
    monkeypatch.setattr(balance_routes, 'get_payment_methods', AsyncMock(return_value=[method]))
    monkeypatch.setattr(c2c_cabinet, 'get_card_by_index', lambda index: CARD)
    monkeypatch.setattr(settings, 'C2C_GUIDE_TEXT', 'Send the exact amount.', raising=False)
    adapter = SimpleNamespace(
        start=AsyncMock(return_value=_receipt()),
        attach=AsyncMock(return_value=_receipt(receipt_type='photo')),
        current=AsyncMock(return_value=None),
        cancel=AsyncMock(return_value=_receipt(status=C2cReceiptStatus.CANCELLED.value)),
    )
    monkeypatch.setattr(c2c_cabinet, 'start_cabinet_receipt', adapter.start)
    monkeypatch.setattr(c2c_cabinet, 'attach_cabinet_receipt', adapter.attach)
    monkeypatch.setattr(c2c_cabinet, 'current_cabinet_receipt', adapter.current)
    monkeypatch.setattr(c2c_cabinet, 'cancel_cabinet_receipt', adapter.cancel)
    return adapter


# ---- session --------------------------------------------------------------


async def test_session_hands_toman_to_the_adapter_and_answers_on_both_scales(c2c_env):
    response = await balance_routes.start_c2c_session(
        C2cSessionRequest(amount_kopeks=10_000_000), user=_user(), db=object()
    )

    assert c2c_env.start.await_args.args[2] == 100_000
    assert response.amount_toman == 100_000
    assert response.amount_kopeks == 10_000_000
    assert response.card_number == CARD['number']
    assert response.card_holder == 'Ali'
    assert response.card_label == 'Melli'
    assert response.guide_text == 'Send the exact amount.'
    assert response.status == 'pending'


async def test_session_below_the_minimum_names_the_toman_limit(c2c_env):
    with pytest.raises(HTTPException) as exc:
        await balance_routes.start_c2c_session(C2cSessionRequest(amount_kopeks=9_999_900), user=_user(), db=object())

    assert exc.value.status_code == 400
    assert '100,000' in exc.value.detail
    c2c_env.start.assert_not_awaited()


async def test_session_when_c2c_is_not_offered_is_unavailable(c2c_env, monkeypatch):
    monkeypatch.setattr(balance_routes, 'get_payment_methods', AsyncMock(return_value=[]))

    with pytest.raises(HTTPException) as exc:
        await balance_routes.start_c2c_session(C2cSessionRequest(amount_kopeks=10_000_000), user=_user(), db=object())

    assert exc.value.status_code == 400
    c2c_env.start.assert_not_awaited()


async def test_session_for_a_restricted_user_is_forbidden(c2c_env):
    with pytest.raises(HTTPException) as exc:
        await balance_routes.start_c2c_session(
            C2cSessionRequest(amount_kopeks=10_000_000), user=_user(restriction_topup=True), db=object()
        )

    assert exc.value.status_code == 403


async def test_session_while_a_submitted_receipt_is_pending_is_a_conflict(c2c_env):
    c2c_env.start.side_effect = c2c_cabinet.C2cCabinetError(
        c2c_cabinet.ALREADY_SUBMITTED, receipt=_receipt(receipt_type='photo')
    )

    with pytest.raises(HTTPException) as exc:
        await balance_routes.start_c2c_session(C2cSessionRequest(amount_kopeks=10_000_000), user=_user(), db=object())

    assert exc.value.status_code == 409


# ---- receipt --------------------------------------------------------------


async def test_receipt_submission_returns_the_in_review_state(c2c_env):
    response = await balance_routes.submit_c2c_receipt(
        C2cReceiptSubmitRequest(receipt_id=7, media_file_id='AgACfile', media_type='photo', text='note'),
        user=_user(),
        db=object(),
    )

    kwargs = c2c_env.attach.await_args.kwargs
    assert c2c_env.attach.await_args.args[2] == 7
    assert kwargs == {'media_file_id': 'AgACfile', 'media_type': 'photo', 'text': 'note'}
    assert response.has_receipt is True
    assert response.status == 'pending'
    assert response.amount_toman == 100_000
    assert response.amount_kopeks == 10_000_000
    # Card details are only repeated while the user still has to transfer.
    assert response.card_number is None


@pytest.mark.parametrize(
    ('code', 'status_code'),
    [
        (c2c_cabinet.EMPTY, 400),
        (c2c_cabinet.NOT_FOUND, 404),
        (c2c_cabinet.ALREADY_SUBMITTED, 409),
        (c2c_cabinet.ADMIN_UNREACHABLE, 502),
        (c2c_cabinet.UNAVAILABLE, 400),
    ],
)
async def test_receipt_errors_map_to_http_statuses(c2c_env, code, status_code):
    c2c_env.attach.side_effect = c2c_cabinet.C2cCabinetError(code)

    with pytest.raises(HTTPException) as exc:
        await balance_routes.submit_c2c_receipt(
            C2cReceiptSubmitRequest(receipt_id=7, text='x'), user=_user(), db=object()
        )

    assert exc.value.status_code == status_code
    assert exc.value.detail


# ---- current / cancel -----------------------------------------------------


async def test_current_without_a_receipt_is_no_content(c2c_env):
    response = await balance_routes.get_current_c2c_receipt(receipt_id=None, user=_user(), db=object())

    assert response.status_code == 204


async def test_current_receipt_less_pending_repeats_the_card(c2c_env):
    c2c_env.current.return_value = _receipt()

    response = await balance_routes.get_current_c2c_receipt(receipt_id=None, user=_user(), db=object())

    assert response.has_receipt is False
    assert response.card_number == CARD['number']
    assert response.guide_text == 'Send the exact amount.'


async def test_current_by_id_reports_an_approval_in_toman(c2c_env):
    c2c_env.current.return_value = _receipt(
        status=C2cReceiptStatus.APPROVED.value, receipt_type='photo', approved_amount_kopeks=90_000
    )

    response = await balance_routes.get_current_c2c_receipt(receipt_id=7, user=_user(), db=object())

    assert c2c_env.current.await_args.kwargs == {'receipt_id': 7}
    assert response.status == 'approved'
    assert response.approved_amount_toman == 90_000


async def test_cancel_returns_the_cancelled_state(c2c_env):
    response = await balance_routes.cancel_c2c_receipt(C2cCancelRequest(receipt_id=7), user=_user(), db=object())

    assert c2c_env.cancel.await_args.args[2] == 7
    assert response.status == 'cancelled'
