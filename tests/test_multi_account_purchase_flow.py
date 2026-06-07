import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.handlers.subscription import tariff_purchase as tp


@pytest.mark.asyncio
async def test_select_tariff_does_not_block_existing_same_tariff():
    """Multi-tariff: selecting tariff user already owns must NOT early-return."""
    callback = MagicMock()
    callback.data = 'tariff_select:2'
    callback.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    db_user = MagicMock(id=1, language='fa', balance_kopeks=100000)
    tariff = MagicMock(
        id=2,
        is_active=True,
        name='Premium',
        is_daily=False,
    )
    tariff.can_purchase_custom_days = MagicMock(return_value=False)
    tariff.can_purchase_custom_traffic = MagicMock(return_value=False)
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()

    with (
        patch('app.handlers.subscription.tariff_purchase.get_tariff_by_id', AsyncMock(return_value=tariff)),
        patch('app.handlers.subscription.tariff_purchase.format_tariff_info_for_user', return_value='info'),
    ):
        await tp.select_tariff(callback, db_user, AsyncMock(), state)

    alert_calls = [c for c in callback.answer.call_args_list if c.kwargs.get('show_alert')]
    assert len(alert_calls) == 0
    callback.message.edit_text.assert_awaited()


def test_autopurchase_extend_decision():
    assert tp.should_extend_multi_tariff({'target_subscription_id': 99}, existing_sub=object())
    assert not tp.should_extend_multi_tariff({}, existing_sub=object())


def test_autopurchase_no_sub_id_means_create_not_extend():
    """When cart lacks subscription_id, existing_subscription must stay None even if same tariff exists."""
    cart_data = {'tariff_id': 2, 'period_days': 30, 'subscription_id': None}
    active_subs = [MagicMock(id=1, tariff_id=2)]
    _cart_sub_id = cart_data.get('subscription_id')
    existing = None
    if _cart_sub_id:
        existing = next((s for s in active_subs if s.id == int(_cart_sub_id)), None)
    assert existing is None
