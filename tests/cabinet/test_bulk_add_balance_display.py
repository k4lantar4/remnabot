from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import app.cabinet.routes.admin_bulk_actions as bulk
from app.cabinet.schemas.bulk_actions import BulkActionParams


@pytest.mark.asyncio
async def test_do_add_balance_uses_amount_display() -> None:
    user = SimpleNamespace(id=7, username='alice')
    params = BulkActionParams(amount_display=250, balance_description='manual top-up')
    db = AsyncMock()

    with patch.object(bulk, 'add_user_balance', new_callable=AsyncMock, return_value=True) as add_balance:
        result = await bulk._do_add_balance(db, user, params, dry_run=False)

    assert result.success is True
    add_balance.assert_awaited_once()
    assert add_balance.await_args.kwargs['amount_kopeks'] == 250


def test_require_amount_kopeks_from_display() -> None:
    params = BulkActionParams(amount_display=100)
    assert bulk._require_amount_kopeks(params) == 100
