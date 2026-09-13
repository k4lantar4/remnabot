"""``GET /cabinet/balance/pending-payments/{method}/latest`` reads each method's amount like the list path.

``CryptoBotPayment`` has no ``amount_kopeks`` column, so reading it there raised ``AttributeError``
and the route answered 500 for any CryptoBot invoice from the last hour (F-095).
"""

from __future__ import annotations

from types import SimpleNamespace

from app.cabinet.routes import balance
from app.database.models import CryptoBotPayment, PaymentMethod
from app.utils.toman_rates import build_toman_topup_payload


def _cryptobot(payload: str | None) -> CryptoBotPayment:
    return CryptoBotPayment(invoice_id='inv-1', amount='12.5', asset='USDT', status='active', payload=payload)


def test_cryptobot_toman_invoice_amount_is_its_toman_credit() -> None:
    payment = _cryptobot(build_toman_topup_payload(7, 50_000))

    assert balance._latest_payment_amount(PaymentMethod.CRYPTOBOT, payment) == (50_000, True)


def test_cryptobot_invoice_without_a_parsable_payload_does_not_raise() -> None:
    assert balance._latest_payment_amount(PaymentMethod.CRYPTOBOT, _cryptobot(None)) == (0, False)


def test_other_gateways_keep_their_amount_kopeks() -> None:
    payment = SimpleNamespace(amount_kopeks=100_000)

    assert balance._latest_payment_amount(PaymentMethod.MULENPAY, payment) == (100_000, False)
