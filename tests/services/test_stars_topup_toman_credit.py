"""A paid Stars top-up credits the Toman its invoice promised, 1:1 into the Toman balance.

New invoices carry ``topup_toman_{uid}_{toman}_{ts}``. Legacy ``balance_*`` payloads (issued before
the Toman rate existed) keep their old handling.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.config import settings
from app.database.models import TransactionType
from app.services.payment import stars as stars_module
from app.services.payment_service import PaymentService
from app.utils.toman_rates import build_toman_topup_payload


class _Db:
    async def rollback(self) -> None:  # pragma: no cover - only on errors
        pass


@pytest.fixture
def harness(monkeypatch):
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_ENABLED', True, raising=False)
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_TOMAN_PER_STAR', 1850, raising=False)
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_RATE_RUB', 1.0, raising=False)

    created: list[dict[str, Any]] = []
    finalized: list[dict[str, Any]] = []

    async def _no_existing(*_a, **_k):
        return None

    async def _create_transaction(**kwargs):
        created.append(kwargs)
        return SimpleNamespace(**kwargs, id=1)

    async def _get_user(_db, user_id):
        return SimpleNamespace(id=user_id)

    monkeypatch.setattr(stars_module, 'get_transaction_by_external_id', _no_existing)
    monkeypatch.setattr(stars_module, 'create_transaction', _create_transaction)
    monkeypatch.setattr(stars_module, 'get_user_by_id', _get_user)

    service = PaymentService.__new__(PaymentService)  # type: ignore[call-arg]
    service.bot = None

    async def _finalize(**kwargs):
        finalized.append(kwargs)
        return True

    service._finalize_stars_balance_topup = _finalize  # type: ignore[method-assign]
    return SimpleNamespace(service=service, created=created, finalized=finalized)


async def _pay(harness, payload: str, stars: int) -> bool:
    return await harness.service.process_stars_payment(
        db=_Db(), user_id=42, stars_amount=stars, payload=payload, telegram_payment_charge_id='ch-1'
    )


async def test_toman_payload_credits_promised_toman(harness):
    assert await _pay(harness, build_toman_topup_payload(42, 51_800, nonce=1), stars=28)
    assert harness.created[0]['type'] == TransactionType.DEPOSIT
    assert harness.created[0]['amount_kopeks'] == 51_800
    assert harness.finalized[0]['amount_kopeks'] == 51_800


async def test_toman_payload_million(harness):
    assert await _pay(harness, build_toman_topup_payload(42, 1_000_850, nonce=1), stars=541)
    assert harness.created[0]['amount_kopeks'] == 1_000_850


async def test_implausible_toman_payload_falls_back_to_stars_value(harness):
    # 28 stars are worth 51,800 T; a payload claiming 5,180,000 T is a bug, not a credit.
    assert await _pay(harness, build_toman_topup_payload(42, 5_180_000, nonce=1), stars=28)
    assert harness.created[0]['amount_kopeks'] == 51_800


async def test_toman_payload_survives_rate_removed_after_invoice(harness, monkeypatch):
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_TOMAN_PER_STAR', None, raising=False)
    assert await _pay(harness, build_toman_topup_payload(42, 51_800, nonce=1), stars=28)
    assert harness.created[0]['amount_kopeks'] == 51_800


async def test_unrecognized_payload_credits_stars_at_toman_rate(harness):
    assert await _pay(harness, 'admin_stars_test_42_1757000000', stars=1)
    assert harness.created[0]['amount_kopeks'] == 1_850


async def test_legacy_balance_payload_keeps_old_handling(harness):
    # Issued before the Toman rate: payload amount (within 20% of stars x RUB rate x 100) wins.
    assert await _pay(harness, 'balance_42_15000', stars=150)
    assert harness.created[0]['amount_kopeks'] == 15_000


async def test_finalize_passes_the_referral_base_in_toman(monkeypatch):
    """process_referral_topup takes Toman 1:1 since Phase C: a 51,800 T credit is 51,800 there."""
    captured: dict[str, Any] = {}

    async def _referral(db, user_id, amount, bot):
        captured['amount'] = amount

    from app.services import referral_service

    monkeypatch.setattr(referral_service, 'process_referral_topup', _referral)

    async def _lock(db, user):
        return user

    import app.database.crud.user as user_crud

    monkeypatch.setattr(user_crud, 'lock_user_for_update', _lock)

    async def _emit(*_a, **_k):
        return None

    monkeypatch.setattr(stars_module, 'emit_transaction_side_effects', _emit)

    from app.services.payment import common

    async def _cart(*_a, **_k):
        return False

    monkeypatch.setattr(common, 'send_cart_notification_after_topup', _cart)

    user = SimpleNamespace(
        id=42,
        telegram_id=111,
        balance_kopeks=10_000,
        has_made_first_topup=True,
        referred_by_id=7,
        updated_at=None,
        subscription=None,
        get_primary_promo_group=lambda: None,
    )

    class _Session:
        async def commit(self):
            pass

        async def refresh(self, _obj):
            pass

    service = PaymentService.__new__(PaymentService)  # type: ignore[call-arg]
    service.bot = None
    monkeypatch.setattr(stars_module, 'format_referrer_info', lambda _u: '')

    ok = await service._finalize_stars_balance_topup(
        db=_Session(),
        user=user,
        transaction=SimpleNamespace(description='d'),
        amount_kopeks=51_800,
        stars_amount=28,
        telegram_payment_charge_id='ch-1',
    )
    assert ok is True
    assert user.balance_kopeks == 61_800
    assert captured['amount'] == 51_800
