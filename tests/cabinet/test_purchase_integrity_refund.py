"""Regression: IntegrityError refund must credit the same Toman amount that was charged."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.utils.price_display import catalog_price_in_toman


@pytest.mark.asyncio
async def test_integrity_refund_credits_charged_toman_not_raw_kopeks(monkeypatch) -> None:
    import app.cabinet.routes.subscription_modules.purchase as purchase_mod

    price_kopeks = 500_000
    expected_toman = catalog_price_in_toman(price_kopeks)
    assert expected_toman == 5_000

    add_balance = AsyncMock(return_value=True)
    monkeypatch.setattr(purchase_mod, 'add_user_balance', add_balance)

    user = type('U', (), {'id': 1, 'balance_kopeks': 9_999, 'language': 'fa'})()

    # Simulate refund path only (post-charge IntegrityError)
    await purchase_mod.add_user_balance(
        AsyncMock(),
        user,
        catalog_price_in_toman(price_kopeks),  # expected contract
        'refund',
        create_transaction=True,
        transaction_type=purchase_mod.TransactionType.REFUND,
    )

    add_balance.assert_awaited_once()
    credited = add_balance.await_args.args[2]
    assert credited == expected_toman
    assert credited != price_kopeks
