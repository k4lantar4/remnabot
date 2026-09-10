"""A failed recurring-subscription lookup must not poison the caller's transaction.

``cancel_platega_recurring_for_subscription_safe`` / ``cancel_lava_recurring_for_subscription_safe``
run inside other transactions (subscription dedup, admin deletion, account merge, tariff
switch, ...). Their lookup queries ``platega_subscriptions`` / ``lava_subscriptions``, tables
our fork never created (upstream's migrations for them were archived, not grafted). On
Postgres the failed SELECT aborts the whole transaction; the helper swallowed the error, so
the caller's next statement died with ``InFailedSQLTransactionError`` — the startup dedup pass
failed on every start this way. SQLite does not abort, so the session below mimics Postgres.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import text


class _Aborted(Exception):
    """Stands in for asyncpg's InFailedSQLTransactionError."""


class _Savepoint:
    def __init__(self, session: _PostgresLikeSession) -> None:
        self._session = session
        self._aborted_before = False

    async def __aenter__(self):
        self._aborted_before = self._session.aborted
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            # ROLLBACK TO SAVEPOINT: the failure is undone, the outer transaction lives on.
            self._session.aborted = self._aborted_before
        return False


class _PostgresLikeSession:
    """The first statement fails (missing table) and, like Postgres, aborts the transaction."""

    def __init__(self) -> None:
        self.aborted = False
        self.statements = 0

    async def execute(self, statement, *args, **kwargs):
        if self.aborted:
            raise _Aborted('current transaction is aborted, commands ignored until end of transaction block')
        self.statements += 1
        if self.statements == 1:
            self.aborted = True
            raise RuntimeError('relation does not exist')
        return MagicMock()

    def begin_nested(self) -> _Savepoint:
        return _Savepoint(self)

    async def commit(self) -> None:
        if self.aborted:
            raise _Aborted('commit on an aborted transaction')


@pytest.mark.asyncio
async def test_platega_cancel_leaves_the_transaction_usable():
    from app.services.payment.platega import cancel_platega_recurring_for_subscription_safe

    db = _PostgresLikeSession()
    await cancel_platega_recurring_for_subscription_safe(db, 86884, commit=False)

    await db.execute(text('SELECT 1'))  # the caller's next statement must still run


@pytest.mark.asyncio
async def test_lava_cancel_leaves_the_transaction_usable():
    from app.services.payment.lava import cancel_lava_recurring_for_subscription_safe

    db = _PostgresLikeSession()
    await cancel_lava_recurring_for_subscription_safe(db, 86884, commit=False)

    await db.execute(text('SELECT 1'))
