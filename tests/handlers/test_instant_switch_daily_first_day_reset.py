"""Bot instant switch daily -> daily: the first day is paid, so the traffic counter resets.

``calculate_tariff_switch_cost`` returns ``upgrade_cost=0`` for daily -> daily, and
``confirm_instant_switch`` then charges the first day of the new daily tariff itself. The
reset decision (``should_reset_used_traffic``) was taken from ``upgrade_cost`` before that
charge, so the customer paid for a new day and carried the old usage against the new limit.
The decision must come from the amount actually charged.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import app.handlers.subscription.tariff_purchase as tp
from app.database.models import Tariff


DAILY_A = Tariff(
    id=21,
    name='daily A',
    is_active=True,
    is_daily=True,
    period_prices={},
    daily_price_kopeks=100_000,
    traffic_limit_gb=10,
    device_limit=1,
    allowed_squads=['squad-1'],
)

DAILY_B = Tariff(
    id=22,
    name='daily B',
    is_active=True,
    is_daily=True,
    period_prices={},
    daily_price_kopeks=150_000,
    traffic_limit_gb=20,
    device_limit=1,
    allowed_squads=['squad-1'],
)


class _FakePanelSync:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def update_remnawave_user(self, db, subscription, **kwargs):
        self.calls.append(kwargs)

    async def create_remnawave_user(self, db, subscription, **kwargs):
        self.calls.append(kwargs)


def _subscription() -> MagicMock:
    sub = MagicMock()
    sub.id = 1
    sub.tariff_id = DAILY_A.id
    sub.end_date = datetime.now(UTC) + timedelta(hours=5)
    sub.device_limit = 1
    sub.traffic_used_gb = 8.0
    sub.remnawave_id = 9001
    return sub


async def _switch(monkeypatch, *, reset_on_switch: bool):
    import app.database.crud.user as user_crud
    import app.services.pricing_engine as pricing_module
    import app.services.remnawave_service as remnawave_module
    from app.config import Settings

    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)
    monkeypatch.setattr(tp.settings, 'RESET_TRAFFIC_ON_TARIFF_SWITCH', reset_on_switch)
    monkeypatch.setattr(tp.settings, 'TARIFF_SWITCH_DOWNGRADE_ENABLED', True)
    monkeypatch.setattr(tp.settings, 'TARIFF_SWITCH_UPGRADE_ENABLED', True)

    async def fake_get_tariff(db, tariff_id):
        return {DAILY_A.id: DAILY_A, DAILY_B.id: DAILY_B}.get(tariff_id)

    monkeypatch.setattr(tp, 'get_tariff_by_id', fake_get_tariff)
    sub = _subscription()
    monkeypatch.setattr(tp, '_resolve_switch_subscription', AsyncMock(return_value=(sub, sub.id)))

    db_user = MagicMock()
    db_user.id = 1
    db_user.language = 'fa'
    db_user.balance_kopeks = 1_000_000
    db_user.remnawave_id = None
    monkeypatch.setattr(user_crud, 'lock_user_for_pricing', AsyncMock(return_value=db_user))

    # daily -> daily: nothing to pay for the switch itself; the first day is charged separately.
    monkeypatch.setattr(
        pricing_module.pricing_engine,
        'calculate_tariff_switch_cost',
        lambda *args, **kwargs: SimpleNamespace(upgrade_cost=0, is_upgrade=False, offer_discount_pct=0),
    )
    monkeypatch.setattr(
        pricing_module.pricing_engine,
        'calculate_tariff_purchase_price',
        AsyncMock(return_value=SimpleNamespace(final_total=150_000, breakdown={})),
    )

    charge = AsyncMock(return_value=True)
    monkeypatch.setattr(tp, 'subtract_user_balance', charge)
    monkeypatch.setattr(tp, 'create_transaction', AsyncMock())
    monkeypatch.setattr(tp, 'AdminNotificationService', MagicMock(return_value=AsyncMock()))
    panel = _FakePanelSync()
    monkeypatch.setattr(tp, 'SubscriptionService', lambda: panel)
    monkeypatch.setattr(remnawave_module, 'RemnaWaveService', MagicMock(side_effect=RuntimeError('no panel')))

    callback = MagicMock()
    callback.data = f'instant_sw_confirm:{DAILY_B.id}'
    callback.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    state = AsyncMock()
    state.get_data = AsyncMock(return_value={})

    await tp.confirm_instant_switch(callback, db_user, AsyncMock(), state)
    return charge, panel, sub


async def test_paid_first_day_resets_used_traffic(monkeypatch):
    charge, panel, sub = await _switch(monkeypatch, reset_on_switch=True)

    charge.assert_awaited_once()  # the first day of the new daily tariff was paid
    assert panel.calls, 'the panel was not synced'
    assert panel.calls[0]['reset_traffic'] is True
    assert sub.traffic_used_gb == 0.0


async def test_global_switch_off_still_wins(monkeypatch):
    charge, panel, sub = await _switch(monkeypatch, reset_on_switch=False)

    charge.assert_awaited_once()
    assert panel.calls[0]['reset_traffic'] is False
    assert sub.traffic_used_gb == 8.0
