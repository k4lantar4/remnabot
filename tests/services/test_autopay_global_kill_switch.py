from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.monitoring_service import MonitoringService


@pytest.mark.asyncio
async def test_process_autopayments_skips_when_global_autopay_disabled(monkeypatch):
    monkeypatch.setattr('app.services.monitoring_service.settings.ENABLE_AUTOPAY', False)

    db = AsyncMock()
    service = MonitoringService()

    await service._process_autopayments(db)

    db.execute.assert_not_called()
