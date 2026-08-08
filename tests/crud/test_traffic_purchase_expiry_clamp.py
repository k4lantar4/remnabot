"""Regression tests for TrafficPurchase expiry cleanup.

Bug scenario (production report, partner user):
  User has subscription with end_date = 2026-01-31.
  On 2026-01-25 user buys +20 GB addon → TrafficPurchase created with
  expires_at = now + 30 days = 2026-02-24 (beyond end_date!).
  On 2026-02-01 user renews and EXPLICITLY chooses 40 GB (pays for 40).
  Because the stale TrafficPurchase (20 GB, expires_at=2026-02-24) is still
  "active" (expires_at > now), renewal logic sums base=40 + purchased=20
  → subscription.traffic_limit_gb=60 without any extra charge.

We test two layers with mock databases (consistent with the rest of the
codebase — every other subscription/crud test is monkeypatch-mocked):

  1. ``_clamp_traffic_purchase_expiries`` — one-shot cleanup helper that
     clamps every TrafficPurchase.expires_at <= its subscription.end_date.
  2. ``add_subscription_traffic`` — new purchases MUST NOT be created with
     expires_at > subscription.end_date anymore (defence for the future).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog
from sqlalchemy import select

from app.database.crud.subscription import (
    _apply_base_limit_preserving_active_purchases,
    _clamp_traffic_purchase_expiries,
    add_subscription_traffic,
)
from app.database.models import Subscription, TrafficPurchase, User

logger = structlog.get_logger(__name__)


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers — build the tiny in-memory fixtures we need (no real DB, no alembic)
# ---------------------------------------------------------------------------


def _make_user() -> User:
    u = User()
    u.id = 99
    return u


def _make_sub(*, end_date: datetime | None, traffic_limit_gb: int = 100) -> Subscription:
    s = Subscription()
    s.id = 1
    s.user_id = 99
    s.tariff_id = 5
    s.end_date = end_date
    s.traffic_limit_gb = traffic_limit_gb
    s.purchased_traffic_gb = 0
    s.traffic_reset_at = None
    s.start_date = datetime.now(UTC) - timedelta(days=10)
    s.status = 'active'
    s.is_trial = False
    s.device_limit = 3
    s.short_id = '99'
    s.user_disabled = False
    s.autopay_period_days = 30
    s.last_revoke_at = None
    s.public_serial = 999
    return s


# ---------------------------------------------------------------------------
# Layer 2 (defence-in-depth): add_subscription_traffic must clamp new rows
# ---------------------------------------------------------------------------


async def test_add_subscription_traffic_clamps_expiry_to_end_date(monkeypatch) -> None:
    """Newly-created TrafficPurchase rows MUST honour subscription.end_date.

    Regression guard for the production bug where a top-up bought 5 days
    before period end leaked 25 days of purchased_gb into the NEXT renewal.

    We assert on the expires_at value that the ORM ``TrafficPurchase``
    instance receives before ``db.add`` is called (the monkeypatched
    add captures it).
    """
    # — Arrange: subscription ends in 5 days
    five_days_later = datetime.now(UTC) + timedelta(days=5)
    sub = _make_sub(end_date=five_days_later)

    captured_instances: list[TrafficPurchase] = []

    fake_db = MagicMock()
    fake_db.add = MagicMock(side_effect=lambda obj: captured_instances.append(obj))
    fake_db.commit = AsyncMock()
    fake_db.refresh = AsyncMock()

    # _lock_subscription_row is called inside add_subscription_traffic via
    # _apply_base_limit_preserving_active_purchases; avoid real SQL by no-oping it
    monkeypatch.setattr(
        'app.database.crud.subscription._lock_subscription_row', AsyncMock()
    )
    # Housekeeping select: return a result with .all() returning empty list
    empty_scalar = MagicMock()
    empty_scalar.scalars.return_value.all.return_value = []
    fake_db.execute = AsyncMock(return_value=empty_scalar)

    # — Act
    updated = await add_subscription_traffic(fake_db, sub, gb=20)

    # — Assert on captured TrafficPurchase
    assert captured_instances, 'add_subscription_traffic never db.add()ed a TrafficPurchase'
    created = next(
        (x for x in captured_instances if isinstance(x, TrafficPurchase)),
        None,
    )
    assert created is not None, 'No TrafficPurchase instance captured from db.add'
    assert created.expires_at <= five_days_later, (
        f'TrafficPurchase.expires_at={created.expires_at.isoformat()} leaks past '
        f'subscription.end_date={five_days_later.isoformat()} — clamp is broken'
    )
    # Purchased counter reflects the GB count regardless of the clamped expiry
    assert updated.purchased_traffic_gb == 20


async def test_add_subscription_traffic_keeps_expiry_when_end_date_is_null(
    monkeypatch,
) -> None:
    """If subscription.end_date is None (legacy / corner-case), keep the
    default 30-day lifetime and don't clamp (no frame of reference)."""
    now = datetime.now(UTC)
    sub = _make_sub(end_date=None)

    captured: list[TrafficPurchase] = []

    fake_db = MagicMock()
    fake_db.add = MagicMock(side_effect=lambda obj: captured.append(obj))
    fake_db.commit = AsyncMock()
    fake_db.refresh = AsyncMock()
    empty_scalar = MagicMock()
    empty_scalar.scalars.return_value.all.return_value = []
    fake_db.execute = AsyncMock(return_value=empty_scalar)
    monkeypatch.setattr(
        'app.database.crud.subscription._lock_subscription_row', AsyncMock()
    )

    await add_subscription_traffic(fake_db, sub, gb=10)

    created = next(x for x in captured if isinstance(x, TrafficPurchase))
    # Default lifetime = 30 days; allow a few seconds of drift for slow CI
    expected_lo = now + timedelta(days=29, hours=23, minutes=59)
    expected_hi = now + timedelta(days=30, seconds=10)
    assert expected_lo <= created.expires_at <= expected_hi, (
        f'unexpected expires_at={created.expires_at.isoformat()} '
        f'for end_date=None subscription (should be ≈ now+30d)'
    )


# ---------------------------------------------------------------------------
# Layer 1 (one-shot migration helper): clamp all stale pre-existing rows
# ---------------------------------------------------------------------------


@dataclass
class _FakeTpRow:
    """Minimal stand-in for a row returned by the joined SQL query in the
    actual clamp helper. Field order matches the select(...) tuple."""

    id: int
    traffic_gb: int
    expires_at: datetime
    sub_id: int
    end_date: datetime | None


async def test_clamp_helper_updates_only_rows_past_end_date(monkeypatch) -> None:
    """``_clamp_traffic_purchase_expiries`` must:
      * clamp rows whose expires_at EXCEEDS end_date,
      * leave rows inside the boundary UNTOUCHED (idempotency),
      * skip rows where end_date IS NULL (classic mode, no frame of reference).

    We fake db.execute so the joined SELECT returns our hand-built tuple list,
    and track all UPDATE calls issued by the helper. Rows are plain tuples so
    the ``for tp_id, traffic_gb, tp_expires_at, sub_id, end_date in rows``
    unpack line works identically to real SQLAlchemy Row unpacking.
    """
    now = datetime.now(UTC)
    end_10d = now + timedelta(days=10)

    # Candidate rows — match field order EXACTLY with the helper's select(...):
    #   (TrafficPurchase.id, traffic_gb, expires_at, Subscription.id, end_date)
    row_a = (100, 20, now + timedelta(days=35), 1, end_10d)   # past end_date → clamp
    row_b = (101, 5,  now + timedelta(days=3),  1, end_10d)   # inside period   → NO TOUCH
    row_c = (102, 99, now + timedelta(days=365), 77, None)    # end_date=None → skip

    joined_result = MagicMock()
    joined_result.all.return_value = [row_a, row_b, row_c]
    fake_execute_results: list = [joined_result]
    update_calls = 0

    class _FakeConnection:
        """Minimal double: first execute() → joined select, later ones → UPDATE."""

        def execute(self, query, *a, **kw):
            nonlocal update_calls
            if fake_execute_results:
                return fake_execute_results.pop(0)
            update_calls += 1
            m = MagicMock()
            m.rowcount = 1
            return m

    fake_db = MagicMock()
    fake_db.execute = AsyncMock(side_effect=_FakeConnection().execute)
    fake_db.commit = AsyncMock()

    # — Act
    stats = await _clamp_traffic_purchase_expiries(fake_db, commit=True)

    # — Assert stats
    assert stats.rows_scanned == 3, 'helper must have seen all 3 candidate rows'
    assert stats.rows_updated == 1, (
        f'only row_A (expires past end_date) should update, got {stats.rows_updated}'
    )
    assert stats.total_gb_updated == 20
    assert stats.rows_skipped_end_date_null == 1  # row_c: end_date=None orphan
    # Exactly 1 UPDATE statement fired for the single clamped row
    assert update_calls == 1, f'expected 1 UPDATE, observed {update_calls}'
    # commit() must fire exactly once
    assert fake_db.commit.await_count == 1


async def test_clamp_helper_is_idempotent(monkeypatch) -> None:
    """If every row is already ≤ end_date → rows_updated=0 on first pass too.

    This is the same helper, but every fed row is now inside the boundary —
    which is exactly what happens on the SECOND run after rows were clamped
    down previously.
    """
    now = datetime.now(UTC)
    end_10d = now + timedelta(days=10)
    # Two rows, both already inside the period — field order: id, gb, expires, sub_id, end_date
    rows = [
        (10, 1, now + timedelta(days=2), 1, end_10d),
        (11, 2, now + timedelta(days=1), 1, end_10d),
    ]

    joined_result = MagicMock()
    joined_result.all.return_value = rows

    fake_db = MagicMock()
    # All executes: first one returns joined_result; UPDATE executes should
    # never fire (we assert on execute count later).
    fake_db.execute = AsyncMock(return_value=joined_result)
    fake_db.commit = AsyncMock()

    stats = await _clamp_traffic_purchase_expiries(fake_db, commit=True)

    assert stats.rows_scanned == 2
    assert stats.rows_updated == 0, 'idempotent — no rows required clamping'
    assert stats.total_gb_updated == 0
    assert stats.rows_skipped_end_date_null == 0
    # 1 execute for the select — 0 extra executes (= no UPDATE ever issued)
    assert fake_db.execute.await_count == 1
