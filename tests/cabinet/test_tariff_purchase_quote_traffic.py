"""Cabinet tariff-purchase-quote: custom traffic only when traffic_gb is sent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cabinet.routes.subscription_modules import purchase as purchase_route
from app.cabinet.schemas.subscription import TariffPurchaseQuoteRequest
from app.database.models import Tariff, User
from app.services.pricing_engine import RenewalPricing


class _FakeTariff:
    id = 2
    is_active = True
    traffic_limit_gb = 1
    min_traffic_gb = 1
    max_traffic_gb = 200
    custom_traffic_enabled = True
    traffic_price_per_gb_kopeks = 1_000_000
    period_prices = {'30': 900_000}
    device_limit = 1
    device_price_kopeks = 0
    is_daily = False

    def can_purchase_custom_traffic(self) -> bool:
        return True

    def can_purchase_custom_days(self) -> bool:
        return False

    def get_price_for_custom_days(self, days: int):
        return None

    def is_available_for_promo_group(self, promo_group_id):
        return True

    def get_traffic_topup_packages(self):
        return {30: 30_000_000, 50: 50_000_000}


@pytest.fixture
def tariffs_mode(monkeypatch):
    settings_cls = type(purchase_route.settings)
    monkeypatch.setattr(settings_cls, 'is_tariffs_mode', lambda self: True)
    monkeypatch.setattr(settings_cls, 'is_multi_tariff_enabled', lambda self: False)

    monkeypatch.setattr(purchase_route, 'get_tariff_by_id', AsyncMock(return_value=_FakeTariff()))
    import app.database.crud.user as user_crud

    monkeypatch.setattr(user_crud, 'lock_user_for_pricing', AsyncMock(return_value=User(id=1, telegram_id=1)))
    monkeypatch.setattr(purchase_route, 'get_subscription_by_user_id', AsyncMock(return_value=None))

    captured: dict = {}

    async def _fake_calculate(tariff, period_days, *, device_limit=None, custom_traffic_gb=None, user=None):
        captured['custom_traffic_gb'] = custom_traffic_gb
        return RenewalPricing(
            base_price=900_000,
            servers_price=0,
            traffic_price=0 if custom_traffic_gb is None else 30_000_000,
            devices_price=0,
            promo_group_discount=0,
            promo_offer_discount=0,
            final_total=900_000 if custom_traffic_gb is None else 30_900_000,
            period_days=period_days,
            is_tariff_mode=True,
            breakdown={
                'period_kopeks': 900_000,
                'traffic_kopeks': 0 if custom_traffic_gb is None else 30_000_000,
                'period_price_source': 'tariff.period_prices',
                'traffic_source': 'none' if custom_traffic_gb is None else 'package',
            },
        )

    engine = MagicMock()
    engine.calculate_tariff_purchase_price = AsyncMock(side_effect=_fake_calculate)
    monkeypatch.setattr(purchase_route, 'pricing_engine', engine)
    return captured


@pytest.mark.asyncio
async def test_quote_without_traffic_gb_uses_fixed_traffic(tariffs_mode):
    """Toggle OFF: omitting traffic_gb must not charge custom traffic."""
    request = TariffPurchaseQuoteRequest(tariff_id=2, period_days=30, traffic_gb=None)

    result = await purchase_route.tariff_purchase_quote(request=request, user=User(id=1), db=object())

    assert tariffs_mode['custom_traffic_gb'] is None
    assert result['traffic_kopeks'] == 0
    assert result['final_total'] == 900_000


@pytest.mark.asyncio
async def test_quote_with_traffic_gb_charges_custom_traffic(tariffs_mode):
    request = TariffPurchaseQuoteRequest(tariff_id=2, period_days=30, traffic_gb=30)

    result = await purchase_route.tariff_purchase_quote(request=request, user=User(id=1), db=object())

    assert tariffs_mode['custom_traffic_gb'] == 30
    assert result['traffic_kopeks'] == 30_000_000
    assert result['final_total'] == 30_900_000
