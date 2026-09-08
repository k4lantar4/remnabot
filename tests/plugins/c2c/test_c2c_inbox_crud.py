"""Tests for C2C pending inbox CRUD helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database.models import C2cReceiptStatus
from app.plugins.c2c import crud as c2c_crud


def _mock_scalar_result(value):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _mock_scalars_result(items):
    scalars = MagicMock()
    scalars.all.return_value = items
    unique = MagicMock()
    unique.all.return_value = items
    scalars.unique.return_value = unique
    result = MagicMock()
    result.scalars.return_value = scalars
    return result


@pytest.mark.asyncio
async def test_count_pending_receipts():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_mock_scalar_result(3))

    count = await c2c_crud.count_pending_receipts(db)

    assert count == 3
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_pending_receipts_returns_pending_rows():
    pending = SimpleNamespace(
        id=1,
        user_id=10,
        amount_kopeks=50000,
        status=C2cReceiptStatus.PENDING.value,
        created_at=datetime.now(UTC),
        user=SimpleNamespace(full_name='Ali', telegram_id=12345),
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_mock_scalars_result([pending]))

    rows = await c2c_crud.list_pending_receipts(db, limit=10, offset=0)

    assert len(rows) == 1
    assert rows[0].status == C2cReceiptStatus.PENDING.value
    assert rows[0].id == 1
    db.execute.assert_awaited_once()


def test_is_reviewable_pending_receipt_requires_submission():
    draft = SimpleNamespace(
        status=C2cReceiptStatus.PENDING.value,
        receipt_type=None,
        admin_message_id=None,
    )
    submitted = SimpleNamespace(
        status=C2cReceiptStatus.PENDING.value,
        receipt_type='photo',
        admin_message_id=999,
    )
    assert c2c_crud.is_reviewable_pending_receipt(draft) is False
    assert c2c_crud.is_reviewable_pending_receipt(submitted) is True


@pytest.mark.asyncio
async def test_count_reviewable_pending_receipts():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_mock_scalar_result(1))

    count = await c2c_crud.count_reviewable_pending_receipts(db)

    assert count == 1
    db.execute.assert_awaited_once()


def test_resolve_stale_receipt_status():
    draft = SimpleNamespace(receipt_type=None, admin_message_id=None)
    notify_failed = SimpleNamespace(receipt_type='photo', admin_message_id=None)
    submitted = SimpleNamespace(receipt_type='photo', admin_message_id=123)

    assert c2c_crud.resolve_stale_receipt_status(draft) == C2cReceiptStatus.CANCELLED.value
    assert c2c_crud.resolve_stale_receipt_status(notify_failed) == C2cReceiptStatus.CANCELLED.value
    assert c2c_crud.resolve_stale_receipt_status(submitted) == C2cReceiptStatus.EXPIRED.value
