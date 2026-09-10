"""Grace startup tolerates the deferred ``grace_access_sessions`` table only while grace is off.

0111 defers the table on the remnabot lineage. With ``GRACE_ACCESS_MODE=false`` there are no
sessions to count, so startup must not fail (and log ``critical``) on every boot; any other mode
genuinely needs the table and must keep failing loudly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.services.grace_access_runtime import GraceAccessRuntime
from app.services.grace_access_service import GraceAccessMode


@pytest.mark.asyncio
async def test_disabled_start_tolerates_deferred_sessions_table(monkeypatch) -> None:
    runtime = GraceAccessRuntime()
    monkeypatch.setattr(settings, 'GRACE_ACCESS_MODE', 'false')
    monkeypatch.setattr(runtime, '_sessions_table_exists', AsyncMock(return_value=False), raising=False)
    open_count = AsyncMock(side_effect=AssertionError('open_count must not query a deferred table'))
    monkeypatch.setattr(runtime, 'open_count', open_count)

    await runtime.start()

    assert runtime.mode is GraceAccessMode.DISABLED
    open_count.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_disabled_start_still_fails_without_sessions_table(monkeypatch) -> None:
    runtime = GraceAccessRuntime()
    monkeypatch.setattr(settings, 'GRACE_ACCESS_MODE', 'drain')
    monkeypatch.setattr(runtime, '_sessions_table_exists', AsyncMock(return_value=False), raising=False)
    monkeypatch.setattr(
        runtime,
        'open_count',
        AsyncMock(side_effect=RuntimeError('relation "grace_access_sessions" does not exist')),
    )

    with pytest.raises(RuntimeError, match='does not exist'):
        await runtime.start()

    assert runtime.mode is GraceAccessMode.DISABLED
