"""A paid CryptoBot top-up credits the Toman recorded at invoice time, 1:1 into the Toman balance.

The webhook used to re-convert the paid USD through the live USD→RUB rate and add rubles x100 to the
Toman balance. Invoices with a ``topup_toman_*`` payload now credit exactly the quoted Toman; legacy
payloads keep their old path.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any

import pytest

from app.config import settings
from app.database.models import TransactionType
from app.services.payment import cryptobot as cryptobot_module
from app.services.payment_service import PaymentService
from app.utils.toman_rates import build_toman_topup_payload


class _Db:
    def __init__(self) -> None:
        self.commits = 0

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, _obj) -> None:
        pass


def _payment(payload: str, amount: str = '2.11') -> SimpleNamespace:
    return SimpleNamespace(
        status='active',
        user_id=42,
        payload=payload,
        amount=amount,
        amount_float=float(amount),
        asset='USDT',
        transaction_id=None,
        created_at=None,
        updated_at=None,
        paid_at=None,
    )


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.setattr(settings, 'CRYPTOBOT_TOMAN_PER_USDT', 95_000, raising=False)
    monkeypatch.setattr(settings, 'CRYPTOBOT_DEFAULT_ASSET', 'USDT', raising=False)

    state: dict[str, Any] = {'created': [], 'referral': [], 'user_notices': []}
    user = SimpleNamespace(
        id=42,
        telegram_id=111,
        language='fa',
        balance_kopeks=10_000,
        has_made_first_topup=True,
        referred_by_id=None,
        updated_at=None,
    )
    state['user'] = user

    crud = types.ModuleType('fake_cryptobot_crud')

    async def _by_invoice(_db, _invoice_id):
        return state['payment']

    async def _link(_db, _invoice_id, _tx_id):
        return None

    crud.get_cryptobot_payment_by_invoice_id = _by_invoice
    crud.get_cryptobot_payment_by_invoice_id_for_update = _by_invoice
    crud.link_cryptobot_payment_to_transaction = _link

    ps_module = types.ModuleType('fake_payment_service')

    async def _create_transaction(_db, **kwargs):
        state['created'].append(kwargs)
        return SimpleNamespace(id=5, **kwargs)

    async def _get_user(_db, _uid):
        return user

    ps_module.create_transaction = _create_transaction
    ps_module.get_user_by_id = _get_user

    real_import = cryptobot_module.import_module

    def _import(name):
        if name == 'app.database.crud.cryptobot':
            return crud
        if name == 'app.services.payment_service':
            return ps_module
        return real_import(name)

    monkeypatch.setattr(cryptobot_module, 'import_module', _import)

    async def _lock(_db, u):
        return u

    import app.database.crud.user as user_crud

    monkeypatch.setattr(user_crud, 'lock_user_for_update', _lock)

    import app.database.crud.transaction as tx_crud

    async def _emit(*_a, **_k):
        return None

    monkeypatch.setattr(tx_crud, 'emit_transaction_side_effects', _emit)

    from app.services import referral_service

    async def _referral(_db, user_id, amount, _bot):
        state['referral'].append(amount)

    monkeypatch.setattr(referral_service, 'process_referral_topup', _referral)

    from app.services.payment import common

    async def _cart(*_a, **_k):
        return False

    monkeypatch.setattr(common, 'send_cart_notification_after_topup', _cart)

    async def _usd_to_rub(_usd):
        raise AssertionError('Toman invoices must not touch the live USD→RUB converter')

    monkeypatch.setattr(cryptobot_module.currency_converter, 'usd_to_rub', _usd_to_rub)
    monkeypatch.setattr(settings, 'ENABLE_NOTIFICATIONS', True, raising=False)

    service = PaymentService.__new__(PaymentService)  # type: ignore[call-arg]
    service.bot = object()

    async def _keyboard(_user):
        return None

    async def _admin_notice(_ctx):
        return None

    async def _user_notice(payload):
        state['user_notices'].append(payload)

    service.build_topup_success_keyboard = _keyboard  # type: ignore[method-assign]
    service._deliver_admin_topup_notification = _admin_notice  # type: ignore[method-assign]
    service._deliver_user_topup_notification = _user_notice  # type: ignore[method-assign]
    state['service'] = service
    return state


def _webhook() -> dict[str, Any]:
    return {'update_type': 'invoice_paid', 'payload': {'invoice_id': '99', 'paid_at': '2026-09-11T10:00:00Z'}}


async def test_toman_invoice_credits_quoted_toman(harness):
    harness['payment'] = _payment(build_toman_topup_payload(42, 200_000), amount='2.11')

    assert await harness['service'].process_cryptobot_webhook(_Db(), _webhook()) is True

    assert harness['user'].balance_kopeks == 210_000
    created = harness['created'][0]
    assert created['type'] == TransactionType.DEPOSIT
    assert created['amount_kopeks'] == 200_000
    assert '₽' not in created['description']
    assert harness['referral'] == [20_000_000]
    notice = harness['user_notices'][0]
    assert '200,000' in notice.text
    assert '₽' not in notice.text and 'USD =' not in notice.text


async def test_toman_invoice_million(harness):
    harness['payment'] = _payment(build_toman_topup_payload(42, 1_000_000), amount='10.53')
    assert await harness['service'].process_cryptobot_webhook(_Db(), _webhook()) is True
    assert harness['user'].balance_kopeks == 1_010_000


async def test_toman_invoice_credit_ignores_rate_change_after_quote(harness, monkeypatch):
    harness['payment'] = _payment(build_toman_topup_payload(42, 200_000), amount='2.11')
    monkeypatch.setattr(settings, 'CRYPTOBOT_TOMAN_PER_USDT', 120_000, raising=False)
    assert await harness['service'].process_cryptobot_webhook(_Db(), _webhook()) is True
    assert harness['user'].balance_kopeks == 210_000


async def test_legacy_payload_keeps_usd_rub_path(harness, monkeypatch):
    harness['payment'] = _payment('cabinet_topup_42_5000000', amount='5.00')

    async def _usd_to_rub(usd):
        return usd * 90

    monkeypatch.setattr(cryptobot_module.currency_converter, 'usd_to_rub', _usd_to_rub)
    assert await harness['service'].process_cryptobot_webhook(_Db(), _webhook()) is True
    # Unchanged legacy math: ceil(5 x 90) x 100.
    assert harness['created'][0]['amount_kopeks'] == 45_000


def test_module_is_importable():
    assert 'app.services.payment.cryptobot' in sys.modules
