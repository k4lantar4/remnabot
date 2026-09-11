"""Pending CryptoBot / Stars payments report their amount on the top-up scale (Toman x100)."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.payment_verification_service import _parse_cryptobot_amount_kopeks
from app.utils.toman_rates import build_toman_topup_payload


def test_toman_payload_amount_is_reported_on_topup_scale():
    payment = SimpleNamespace(payload=build_toman_topup_payload(42, 200_000))
    # The cabinet renders amount_rubles = amount_kopeks / 100 → 200,000 Toman.
    assert _parse_cryptobot_amount_kopeks(payment) == 20_000_000


def test_legacy_cabinet_payload_unchanged():
    assert _parse_cryptobot_amount_kopeks(SimpleNamespace(payload='cabinet_topup_42_5000000')) == 5_000_000


def test_guest_json_payload_is_zero():
    assert _parse_cryptobot_amount_kopeks(SimpleNamespace(payload='{"purpose": "guest_purchase"}')) == 0


async def test_stars_deposit_record_is_reported_on_topup_scale(monkeypatch):
    """Stars records come from DEPOSIT transactions (Toman 1:1); records carry Toman x100."""
    from app.database.models import PaymentMethod
    from app.services import payment_verification_service as pvs

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
    assert captured['amount_kopeks'] == 5_180_000
