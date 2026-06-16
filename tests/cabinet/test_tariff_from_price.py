"""Cabinet tariff list: from_price includes minimum traffic when custom traffic enabled."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.cabinet.routes.subscription_modules.purchase import _build_tariff_response
from app.database.models import Tariff, User


class _TariffWithCustomTraffic:
    id = 2
    name = 'Test'
    description = None
    tier_level = 1
    traffic_limit_gb = 1
    device_limit = 1
    device_price_kopeks = 0
    allowed_squads = []
    is_active = True
    custom_days_enabled = False
    price_per_day_kopeks = 0
    min_days = 1
    max_days = 365
    custom_traffic_enabled = True
    traffic_price_per_gb_kopeks = 1_000_000
    min_traffic_gb = 1
    max_traffic_gb = 200
    traffic_topup_enabled = True
    max_topup_traffic_gb = 200
    traffic_reset_mode = 'NO_RESET'
    is_daily = False
    daily_price_kopeks = 0
    period_prices = {'30': 900_000}

    def can_purchase_custom_traffic(self) -> bool:
        return True

    def get_traffic_topup_packages(self):
        return {30: 30_000_000}


@pytest.mark.asyncio
async def test_from_price_includes_min_traffic(monkeypatch):
    monkeypatch.setattr(
        'app.cabinet.routes.subscription_modules.purchase.get_server_squad_by_uuid',
        AsyncMock(return_value=None),
    )

    tariff = _TariffWithCustomTraffic()
    user = User(id=1, telegram_id=1)

    result = await _build_tariff_response(object(), tariff, language='fa', user=user)

    assert result['from_price_kopeks'] == 900_000 + 1_000_000
    assert 'from_price_label' in result
