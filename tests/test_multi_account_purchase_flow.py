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
