"""Pending CryptoBot / Stars records carry plain Toman, independent of any request's wire scale."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.database.models import PaymentMethod
from app.services import payment_verification_service as pvs
from app.services.payment_verification_service import _parse_cryptobot_amount
from app.utils.toman_rates import build_toman_topup_payload
from app.utils.wire_scale import CATALOG_WIRE, TOMAN_WIRE, reset_wire_scale, use_wire_scale


@pytest.mark.parametrize('scale', [CATALOG_WIRE, TOMAN_WIRE])
def test_toman_payload_amount_is_plain_toman_on_any_scale(scale):
    payment = SimpleNamespace(payload=build_toman_topup_payload(42, 200_000))
    token = use_wire_scale(scale)
    try:
        assert _parse_cryptobot_amount(payment) == (200_000, True)
    finally:
        reset_wire_scale(token)


def test_legacy_cabinet_payload_is_not_toman():
    assert _parse_cryptobot_amount(SimpleNamespace(payload='cabinet_topup_42_5000000')) == (5_000_000, False)


def test_guest_json_payload_is_zero():
    assert _parse_cryptobot_amount(SimpleNamespace(payload='{"purpose": "guest_purchase"}')) == (0, False)


def test_build_record_keeps_the_toman_flag():
    payment = SimpleNamespace(id=3, user=SimpleNamespace(id=42), created_at=datetime(2026, 9, 13, tzinfo=UTC))

    record = pvs._build_record(
        PaymentMethod.TELEGRAM_STARS,
        payment,
        identifier='x',
        amount_kopeks=51_800,
        status='paid',
        is_paid=True,
        amount_is_toman=True,
    )

    assert record.amount_kopeks == 51_800
    assert record.amount_is_toman is True


async def test_stars_deposit_record_is_plain_toman(monkeypatch):
    """Stars records come from DEPOSIT transactions, which are Toman 1:1."""
    transaction = SimpleNamespace(
        id=9,
        external_id='charge-1',
        amount_kopeks=51_800,
        is_completed=True,
        payment_method=PaymentMethod.TELEGRAM_STARS.value,
        user=SimpleNamespace(id=42),
    )

    class _Db:
        async def get(self, _model, _id):
            return transaction

        async def refresh(self, _obj, attribute_names=None):
            return None

    captured = {}

    def _build(method, payment, **kwargs):
        captured.update(kwargs)
        return kwargs

    monkeypatch.setattr(pvs, '_build_record', _build)
    await pvs.get_payment_record(_Db(), PaymentMethod.TELEGRAM_STARS, 9)
    assert captured['amount_kopeks'] == 51_800
    assert captured['amount_is_toman'] is True
