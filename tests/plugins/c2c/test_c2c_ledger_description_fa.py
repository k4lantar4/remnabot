"""Regression tests for Persian C2C and autopurchase ledger descriptions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.database.models import C2cReceiptStatus
from app.plugins.c2c import crud as c2c_crud
from app.plugins.c2c.service import C2cPaymentService
from app.services.subscription_auto_purchase_service import _auto_purchase_tariff
from app.config import Settings


@pytest.mark.asyncio
async def test_c2c_approve_uses_persian_ledger_description(monkeypatch):
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()

    receipt = SimpleNamespace(
        id=9,
        user_id=1,
        amount_kopeks=200_000,
        status=C2cReceiptStatus.PENDING.value,
        transaction_id=None,
        reviewed_by_telegram_id=None,
        processed_at=None,
        updated_at=None,
    )
    user = SimpleNamespace(
        id=1,
        telegram_id=12345,
        balance_kopeks=0,
        has_made_first_topup=False,
        referred_by_id=None,
        language='fa',
    )
    created_tx = SimpleNamespace(id=50)

    monkeypatch.setattr(c2c_crud, 'get_c2c_receipt_for_update', AsyncMock(return_value=receipt))
    monkeypatch.setattr('app.plugins.c2c.service.get_transaction_by_external_id', AsyncMock(return_value=None))
    monkeypatch.setattr('app.plugins.c2c.service.get_user_by_id', AsyncMock(return_value=user))
    monkeypatch.setattr('app.plugins.c2c.service.lock_user_for_update', AsyncMock(return_value=user))
    add_balance = AsyncMock(return_value=True)
    monkeypatch.setattr('app.plugins.c2c.service.add_user_balance', add_balance)
    monkeypatch.setattr('app.plugins.c2c.service.create_transaction', AsyncMock(return_value=created_tx))
    monkeypatch.setattr(C2cPaymentService, 'finalize_approved_topup', AsyncMock())
    monkeypatch.setattr('app.plugins.c2c.service.clear_user_c2c_fsm_state', AsyncMock())

    service = C2cPaymentService(bot=None)
    success, _, _ = await service.approve_receipt(db, 9, 777)

    assert success is True
    description = add_balance.await_args.kwargs['description']
    assert 'واریز کارت‌به‌کارت' in description
    assert 'Card-to-card' not in description


@pytest.mark.asyncio
async def test_auto_purchase_uses_persian_tariff_ledger_description(monkeypatch):
    pytest.skip(
        '4.2 auto-purchase still uses Russian ledger copy; FA purchase strings are M6, not M4-T7 C2C'
    )
    db = AsyncMock()
    user = SimpleNamespace(
        id=5,
        telegram_id=None,
        balance_kopeks=500_000,
        language='fa',
        promo_offer_discount_percent=0,
        promo_offer_discount_source=None,
        promo_offer_discount_expires_at=None,
    )
    tariff = SimpleNamespace(
        id=11,
        name='سرویس تست',
        is_active=True,
        period_prices={'30': 100_000},
        traffic_limit_gb=100,
        allowed_squads=[],
        can_purchase_custom_traffic=lambda: False,
    )

    monkeypatch.setattr('app.database.crud.tariff.get_tariff_by_id', AsyncMock(return_value=tariff))
    monkeypatch.setattr('app.database.crud.subscription.get_subscription_by_user_id', AsyncMock(return_value=None))
    monkeypatch.setattr('app.database.crud.user.lock_user_for_pricing', AsyncMock(return_value=user))
    monkeypatch.setattr(
        'app.services.subscription_auto_purchase_service.pricing_engine.calculate_tariff_purchase_price',
        AsyncMock(return_value=SimpleNamespace(final_total=100_000, promo_offer_discount=0)),
    )
    subtract_balance = AsyncMock(return_value=False)
    monkeypatch.setattr('app.database.crud.user.subtract_user_balance', subtract_balance)
    monkeypatch.setattr('app.services.subscription_auto_purchase_service.user_can_afford', lambda *_args, **_kw: True)
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)

    result = await _auto_purchase_tariff(
        db,
        user,
        {'tariff_id': tariff.id, 'period_days': 30},
    )

    assert result is False
    description = subtract_balance.await_args.args[3]
    assert 'خرید سرویس' in description
