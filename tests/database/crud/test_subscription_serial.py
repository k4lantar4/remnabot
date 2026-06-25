from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database.crud.subscription_serial import allocate_subscription_public_serial


def _mock_db_with_nextvals(*values: str):
    """Return AsyncSession mock whose execute().scalar_one() yields nextval results."""
    db = AsyncMock()
    results = [MagicMock(scalar_one=MagicMock(return_value=v)) for v in values]
    db.execute = AsyncMock(side_effect=results)
    return db


async def test_allocate_starts_at_1000():
    db = _mock_db_with_nextvals('1000')

    serial = await allocate_subscription_public_serial(db)

    assert serial == '1000'
    db.execute.assert_awaited_once()


async def test_allocate_increments_monotonically():
    db = _mock_db_with_nextvals('1000', '1001', '1002')

    first = await allocate_subscription_public_serial(db)
    second = await allocate_subscription_public_serial(db)
    third = await allocate_subscription_public_serial(db)

    assert first == '1000'
    assert second == '1001'
    assert third == '1002'
    assert db.execute.await_count == 3


async def test_allocate_returns_decimal_digits_only():
    db = _mock_db_with_nextvals('1042')

    serial = await allocate_subscription_public_serial(db)

    assert serial.isdigit()
    assert serial == '1042'


async def test_allocate_rejects_non_digit_serial():
    db = _mock_db_with_nextvals('abc123')

    with pytest.raises(RuntimeError, match='Invalid subscription public serial'):
        await allocate_subscription_public_serial(db)


async def test_allocate_rejects_serial_below_start(monkeypatch):
    monkeypatch.setattr('app.database.crud.subscription_serial.settings.SUBSCRIPTION_PUBLIC_SERIAL_START', 1000)
    db = _mock_db_with_nextvals('999')

    with pytest.raises(RuntimeError, match='below configured start'):
        await allocate_subscription_public_serial(db)
