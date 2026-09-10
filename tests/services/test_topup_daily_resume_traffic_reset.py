"""The resume right after a top-up is a daily charge too, so it follows the reset policy.

``try_resume_disabled_daily_after_topup`` charges the daily fee for DISABLED / EXPIRED /
LIMITED daily subscriptions the moment the balance is topped up, then syncs the panel. It
hard-coded ``reset_traffic=False``: with ``RESET_TRAFFIC_ON_PAYMENT`` on, a LIMITED customer
paid and stayed limited, while the same resume in the cabinet reset the counter.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.database.models import Base, Subscription, SubscriptionStatus, Tariff, User
from tests.fixtures.sqlite_memory import memory_session


TABLES = list(Base.metadata.sorted_tables)


class _FakePanelSync:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def update_remnawave_user(self, db, subscription, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(id=9001, used_traffic_bytes=0)

    async def create_remnawave_user(self, db, subscription, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(id=9001, used_traffic_bytes=0)


def _rows() -> list:
    now = datetime.now(UTC)
    return [
        User(
            id=1,
            telegram_id=1001,
            first_name='U',
            language='fa',
            status='active',
            balance_kopeks=100_000,
            remnawave_id=9001,
        ),
        Tariff(
            id=1,
            name='daily',
            description='',
            is_active=True,
            is_daily=True,
            daily_price_kopeks=1000,
            traffic_limit_gb=100,
            traffic_reset_mode='NO_RESET',
            device_limit=1,
            allowed_squads=['squad-1'],
            display_order=1,
        ),
        Subscription(
            id=10,
            remnawave_short_id='day1',
            remnawave_id=9001,
            user_id=1,
            status=SubscriptionStatus.LIMITED.value,
            is_trial=False,
            is_daily_paused=False,
            start_date=now - timedelta(days=5),
            end_date=now + timedelta(hours=3),
            last_daily_charge_at=now - timedelta(hours=25),
            updated_at=now - timedelta(hours=1),
            traffic_limit_gb=100,
            traffic_used_gb=100.0,
            device_limit=1,
            tariff_id=1,
            connected_squads=['squad-1'],
        ),
    ]


async def _resume_after_topup(db, monkeypatch, *, reset_on_payment: bool):
    import app.cabinet.routes.websocket as websocket_module
    import app.services.subscription_auto_purchase_service as auto_module
    from app.config import Settings

    monkeypatch.setattr(settings, 'RESET_TRAFFIC_ON_PAYMENT', reset_on_payment)
    monkeypatch.setattr(settings, 'DEFAULT_TRAFFIC_RESET_STRATEGY', 'MONTH')
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)

    panel = _FakePanelSync()
    monkeypatch.setattr(auto_module, 'SubscriptionService', lambda: panel)
    monkeypatch.setattr(websocket_module, 'notify_user_subscription_renewed', AsyncMock())
    monkeypatch.setattr(auto_module, '_notify_email_user_auto_purchase', AsyncMock())

    db.add_all(_rows())
    await db.commit()
    user = await db.get(User, 1)

    resumed = await auto_module.try_resume_disabled_daily_after_topup(db, user, bot=None)
    return resumed, panel, await db.get(Subscription, 10)


@pytest.mark.asyncio
async def test_topup_resume_resets_traffic_when_enabled(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        resumed, panel, subscription = await _resume_after_topup(db, monkeypatch, reset_on_payment=True)

    assert resumed is True
    assert panel.calls, 'the panel was not synced'
    assert panel.calls[0]['reset_traffic'] is True
    assert subscription.traffic_used_gb == 0.0


@pytest.mark.asyncio
async def test_topup_resume_keeps_traffic_when_disabled(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        resumed, panel, subscription = await _resume_after_topup(db, monkeypatch, reset_on_payment=False)

    assert resumed is True
    assert panel.calls[0]['reset_traffic'] is False
    assert subscription.traffic_used_gb == 100.0
