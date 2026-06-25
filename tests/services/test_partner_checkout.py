from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.partner_checkout import (
    PartnerCheckoutValidationError,
    apply_partner_checkout_fields,
    sanitize_purchase_note,
)


def test_sanitize_purchase_note_trims_and_caps() -> None:
    assert sanitize_purchase_note('  hello  ') == 'hello'
    assert sanitize_purchase_note('') is None
    assert sanitize_purchase_note(None) is None
    assert len(sanitize_purchase_note('x' * 600)) == 500


@pytest.mark.asyncio
async def test_apply_ignores_fields_for_non_partner() -> None:
    db = AsyncMock()
    user = SimpleNamespace(is_partner=False, id=1, panel_brand_prefix=None)
    subscription = SimpleNamespace(purchase_note=None)

    use_brand = await apply_partner_checkout_fields(
        db,
        user,
        subscription,
        purchase_note='note',
        panel_brand_prefix='mob_x',
    )

    assert use_brand is False
    assert subscription.purchase_note is None
    db.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_partner_note_and_brand() -> None:
    db = AsyncMock()
    user = SimpleNamespace(is_partner=True, id=1, panel_brand_prefix=None)
    subscription = SimpleNamespace(purchase_note=None)

    with patch('app.services.partner_checkout.update_user', new_callable=AsyncMock) as mock_update:
        mock_update.return_value = SimpleNamespace(
            is_partner=True,
            panel_brand_prefix='mob_x',
        )
        use_brand = await apply_partner_checkout_fields(
            db,
            user,
            subscription,
            purchase_note='  customer-42 ',
            panel_brand_prefix='mob_x',
        )

    assert subscription.purchase_note == 'customer-42'
    assert use_brand is True
    db.flush.assert_awaited()
    mock_update.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_rejects_invalid_brand_prefix() -> None:
    db = AsyncMock()
    user = SimpleNamespace(is_partner=True, id=1, panel_brand_prefix=None)
    subscription = SimpleNamespace(purchase_note=None)

    with pytest.raises(PartnerCheckoutValidationError):
        await apply_partner_checkout_fields(
            db,
            user,
            subscription,
            purchase_note=None,
            panel_brand_prefix='ab',
        )


@pytest.mark.asyncio
async def test_apply_uses_existing_brand_when_prefix_not_sent() -> None:
    db = AsyncMock()
    user = SimpleNamespace(is_partner=True, id=1, panel_brand_prefix='saved_x')
    subscription = SimpleNamespace(purchase_note=None)

    use_brand = await apply_partner_checkout_fields(
        db,
        user,
        subscription,
        purchase_note='n',
        panel_brand_prefix=None,
    )

    assert use_brand is True
    assert subscription.purchase_note == 'n'
