"""Cabinet 402 insufficient-balance messages are rendered in the user's language (F-009).

The traffic top-up sheet shows ``detail.message`` verbatim, so a hard-coded Russian f-string reached
Persian users as «Недостаточно средств. Не хватает …». Every insufficient-funds 402 of the cabinet
subscription routes now uses ``CABINET_INSUFFICIENT_BALANCE`` like ``servers.py`` already did; the
``code`` / ``missing_amount`` fields the frontend reads stay unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import HTTPException

from tests.fixtures.sqlite_memory import memory_session
from tests.services.test_addon_toman_scale import (  # noqa: F401 - _isolate is an autouse fixture
    TABLES,
    TRAFFIC_10GB_TOMAN,
    _isolate,
    _seed,
)


ROOT = Path(__file__).resolve().parents[2]
CYRILLIC = re.compile('[А-Яа-яЁё]')
ROUTE_FILES = [
    ROOT / 'app/cabinet/routes/subscription_modules/traffic.py',
    ROOT / 'app/cabinet/routes/subscription_modules/renewal.py',
    ROOT / 'app/cabinet/routes/subscription_modules/purchase.py',
]


@pytest.mark.asyncio
async def test_traffic_topup_shortfall_message_is_persian_for_fa_user(monkeypatch):
    import app.cabinet.routes.subscription_modules.traffic as cabinet_traffic
    from app.cabinet.schemas.subscription import TrafficPurchaseRequest

    async with memory_session(monkeypatch, TABLES) as db:
        user = await _seed(db, balance_toman=10_000)

        with pytest.raises(HTTPException) as caught:
            await cabinet_traffic.purchase_traffic(
                request=TrafficPurchaseRequest(gb=10), user=user, db=db, subscription_id=None
            )

    detail = caught.value.detail
    assert caught.value.status_code == 402
    assert detail['code'] == 'insufficient_funds'
    assert detail['missing_amount'] == TRAFFIC_10GB_TOMAN - 10_000
    assert not CYRILLIC.search(detail['message']), detail['message']
    assert '₽' not in detail['message']
    assert 'کسری' in detail['message']
    assert '20,000' in detail['message'] or '20000' in detail['message'], detail['message']


@pytest.mark.parametrize('path', ROUTE_FILES, ids=lambda p: p.name)
def test_no_hard_coded_russian_insufficient_funds_message(path):
    source = path.read_text(encoding='utf-8')
    assert 'Недостаточно средств' not in source
