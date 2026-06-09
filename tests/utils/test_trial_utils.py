from unittest.mock import AsyncMock, patch

import pytest

from app.utils import trial_utils
from app.utils.trial_utils import is_trial_globally_available


@pytest.mark.asyncio
async def test_trial_globally_unavailable_when_duration_zero(monkeypatch):
    monkeypatch.setattr(trial_utils.settings, 'TRIAL_DURATION_DAYS', 0)
    db = AsyncMock()
    assert await is_trial_globally_available(db) is False


@pytest.mark.asyncio
async def test_trial_globally_available_classic_mode(monkeypatch):
    monkeypatch.setattr(trial_utils.settings, 'TRIAL_DURATION_DAYS', 3)
    monkeypatch.setattr(trial_utils.settings, 'SALES_MODE', 'classic')
    db = AsyncMock()
    assert await is_trial_globally_available(db) is True


@pytest.mark.asyncio
async def test_trial_globally_available_tariffs_mode_with_flagged_tariff(monkeypatch):
    monkeypatch.setattr(trial_utils.settings, 'TRIAL_DURATION_DAYS', 3)
    monkeypatch.setattr(trial_utils.settings, 'SALES_MODE', 'tariffs')
    db = AsyncMock()

    with patch('app.database.crud.tariff.get_trial_tariff', new_callable=AsyncMock, return_value=object()):
        assert await is_trial_globally_available(db) is True


@pytest.mark.asyncio
async def test_trial_globally_available_tariffs_mode_with_configured_tariff_id(monkeypatch):
    monkeypatch.setattr(trial_utils.settings, 'TRIAL_DURATION_DAYS', 3)
    monkeypatch.setattr(trial_utils.settings, 'SALES_MODE', 'tariffs')
    monkeypatch.setattr(trial_utils.settings, 'TRIAL_TARIFF_ID', 42)
    db = AsyncMock()
    configured_tariff = object()

    with (
        patch('app.database.crud.tariff.get_trial_tariff', new_callable=AsyncMock, return_value=None),
        patch('app.database.crud.tariff.get_tariff_by_id', new_callable=AsyncMock, return_value=configured_tariff),
    ):
        assert await is_trial_globally_available(db) is True


@pytest.mark.asyncio
async def test_trial_globally_unavailable_tariffs_mode_without_tariff(monkeypatch):
    monkeypatch.setattr(trial_utils.settings, 'TRIAL_DURATION_DAYS', 3)
    monkeypatch.setattr(trial_utils.settings, 'SALES_MODE', 'tariffs')
    monkeypatch.setattr(trial_utils.settings, 'TRIAL_TARIFF_ID', 0)
    db = AsyncMock()

    with patch('app.database.crud.tariff.get_trial_tariff', new_callable=AsyncMock, return_value=None):
        assert await is_trial_globally_available(db) is False


@pytest.mark.asyncio
async def test_trial_globally_unavailable_when_configured_tariff_missing(monkeypatch):
    monkeypatch.setattr(trial_utils.settings, 'TRIAL_DURATION_DAYS', 3)
    monkeypatch.setattr(trial_utils.settings, 'SALES_MODE', 'tariffs')
    monkeypatch.setattr(trial_utils.settings, 'TRIAL_TARIFF_ID', 99)
    db = AsyncMock()

    with (
        patch('app.database.crud.tariff.get_trial_tariff', new_callable=AsyncMock, return_value=None),
        patch('app.database.crud.tariff.get_tariff_by_id', new_callable=AsyncMock, return_value=None),
    ):
        assert await is_trial_globally_available(db) is False
