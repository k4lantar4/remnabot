"""The panel keeps the real end date of an expired subscription.

Rule from upstream 39097eb9 + 7816e1e9 (v4.8.0) with the clock-skew correction of
upstream dev 3513e1db: the panel accepts a past ``expireAt`` on create but rejects it
on update, and it judges "past" by ITS OWN clock. Before this, every write clamped an
expired subscription to "now + 1 minute", so the panel showed "expired a minute ago"
after each sync and the real end date was lost.
"""

from __future__ import annotations

import pathlib
import re
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.external.remnawave_api import RemnaWaveAPIError, is_expire_in_past_error
from app.services.panel_expiry import (
    ALREADY_EXTINGUISHED,
    MINIMUM_FUTURE,
    SKEW_RETRY_MARGIN,
    panel_expire_at,
    stale_panel_expire_at,
    update_panel_user_with_expiry,
)


NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
PAST = NOW - timedelta(days=30)
FUTURE = NOW + timedelta(days=30)


def _expire_in_past_error() -> RemnaWaveAPIError:
    # Shape captured by upstream from a live 3.4.3 panel.
    return RemnaWaveAPIError(
        'Validation failed',
        status_code=400,
        response_data={
            'message': 'Validation failed',
            'errors': [{'path': ['expireAt'], 'message': 'Expiration date cannot be in the past'}],
        },
    )


class FakePanel:
    """PATCH /api/users that, like the real panel, rejects a date <= its own clock."""

    def __init__(self, current: datetime | None, *, panel_now: datetime | None = None, error=None):
        self.current = current
        self.panel_now = panel_now
        self.error = error
        self.calls: list[dict] = []

    async def update(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.error is not None:
            raise self.error
        expire_at = kwargs.get('expire_at')
        if expire_at is not None:
            if self.panel_now is not None and expire_at <= self.panel_now:
                raise _expire_in_past_error()
            self.current = expire_at
        return SimpleNamespace(id=kwargs['user_id'], expire_at=self.current)


# ==================== the rule ====================


def test_margins_cover_ordinary_clock_skew():
    assert MINIMUM_FUTURE == timedelta(minutes=5)
    assert SKEW_RETRY_MARGIN == timedelta(minutes=15)
    # Our own retry date must also count as "already cleared", or the next sync moves it again.
    assert ALREADY_EXTINGUISHED > SKEW_RETRY_MARGIN


def test_live_subscription_keeps_its_own_date():
    assert panel_expire_at(FUTURE, is_active=True, creating=False, now=NOW) == FUTURE
    assert panel_expire_at(FUTURE, is_active=True, creating=True, now=NOW) == FUTURE


def test_blocked_but_not_expired_subscription_still_pushes_its_real_date():
    assert panel_expire_at(FUTURE, is_active=False, creating=False, now=NOW) == FUTURE
    assert panel_expire_at(FUTURE, is_active=False, creating=True, now=NOW) == FUTURE


def test_create_sends_the_real_date_even_if_it_has_passed():
    assert panel_expire_at(PAST, is_active=False, creating=True, now=NOW) == PAST


def test_update_of_expired_subscription_leaves_a_past_or_unknown_panel_date_alone():
    assert panel_expire_at(PAST, is_active=False, creating=False, now=NOW) is None
    assert (
        panel_expire_at(PAST, is_active=False, creating=False, now=NOW, panel_current=NOW - timedelta(days=3)) is None
    )


def test_update_of_expired_subscription_clears_a_future_panel_date_once():
    assert panel_expire_at(PAST, is_active=False, creating=False, now=NOW, panel_current=FUTURE) == NOW + MINIMUM_FUTURE


def test_our_own_clearing_date_is_not_moved_again():
    for already_ours in (NOW + MINIMUM_FUTURE, NOW + SKEW_RETRY_MARGIN):
        assert stale_panel_expire_at(already_ours, end_date=PAST, now=NOW) is None


def test_naive_panel_date_is_read_as_utc():
    naive_future = FUTURE.replace(tzinfo=None)
    assert (
        panel_expire_at(PAST, is_active=False, creating=False, now=NOW, panel_current=naive_future)
        == NOW + MINIMUM_FUTURE
    )


# ==================== the panel error ====================


def test_expire_in_past_error_is_recognised():
    assert is_expire_in_past_error(_expire_in_past_error())


def test_other_errors_are_not_mistaken_for_a_past_date():
    assert not is_expire_in_past_error(RemnaWaveAPIError('nf', status_code=404, response_data={'errorCode': 'A063'}))
    assert not is_expire_in_past_error(
        RemnaWaveAPIError(
            'Validation failed',
            status_code=400,
            response_data={'errors': [{'path': ['trafficLimitBytes'], 'message': 'Expected number'}]},
        )
    )
    assert not is_expire_in_past_error(RemnaWaveAPIError('boom', status_code=400, response_data=None))


# ==================== the shared update helper ====================


async def test_live_subscription_sends_its_date_in_one_request():
    panel = FakePanel(current=PAST)

    result = await update_panel_user_with_expiry(
        panel.update, end_date=FUTURE, is_active=True, now=NOW, user_id=7, status='ACTIVE'
    )

    assert panel.calls == [{'user_id': 7, 'status': 'ACTIVE', 'expire_at': FUTURE}]
    assert result.expire_at == FUTURE


async def test_expired_with_known_past_panel_date_sends_no_date():
    panel = FakePanel(current=NOW - timedelta(days=3))

    await update_panel_user_with_expiry(
        panel.update,
        end_date=PAST,
        is_active=False,
        panel_current=NOW - timedelta(days=3),
        now=NOW,
        user_id=7,
        status='DISABLED',
        expire_at=NOW + timedelta(minutes=1),  # a caller's stale value must not leak through
    )

    assert panel.calls == [{'user_id': 7, 'status': 'DISABLED'}]


async def test_expired_with_unknown_panel_date_clears_a_future_one_from_the_response():
    panel = FakePanel(current=FUTURE)

    result = await update_panel_user_with_expiry(
        panel.update, end_date=PAST, is_active=False, now=NOW, user_id=7, status='DISABLED'
    )

    assert panel.calls == [
        {'user_id': 7, 'status': 'DISABLED'},
        {'user_id': 7, 'expire_at': NOW + MINIMUM_FUTURE},
    ]
    assert result.expire_at == NOW + MINIMUM_FUTURE


async def test_expired_with_unknown_panel_date_leaves_a_past_one_alone():
    panel = FakePanel(current=NOW - timedelta(days=3))

    await update_panel_user_with_expiry(panel.update, end_date=PAST, is_active=False, now=NOW, user_id=7)

    assert len(panel.calls) == 1


async def test_three_minutes_of_skew_is_absorbed_by_the_margin():
    """Upstream's reproduction: bot clock 3 min behind the panel broke the 1-minute clamp."""
    panel = FakePanel(current=FUTURE, panel_now=NOW + timedelta(minutes=3))

    await update_panel_user_with_expiry(
        panel.update, end_date=PAST, is_active=False, panel_current=FUTURE, now=NOW, user_id=7, status='DISABLED'
    )

    assert panel.calls == [{'user_id': 7, 'status': 'DISABLED', 'expire_at': NOW + MINIMUM_FUTURE}]
    assert panel.current == NOW + MINIMUM_FUTURE


async def test_larger_skew_sends_status_first_then_clears_with_the_retry_margin():
    panel = FakePanel(current=FUTURE, panel_now=NOW + timedelta(minutes=8))

    result = await update_panel_user_with_expiry(
        panel.update, end_date=PAST, is_active=False, panel_current=FUTURE, now=NOW, user_id=7, status='DISABLED'
    )

    # The status must reach the panel even though the date was rejected with it.
    assert {'user_id': 7, 'status': 'DISABLED'} in panel.calls
    assert panel.calls[-1] == {'user_id': 7, 'expire_at': NOW + SKEW_RETRY_MARGIN}
    assert panel.current == result.expire_at == NOW + SKEW_RETRY_MARGIN


async def test_skew_beyond_the_retry_margin_keeps_the_status_and_does_not_raise():
    """Raising here would send our callers into "panel user missing -> create a duplicate"."""
    panel = FakePanel(current=FUTURE, panel_now=NOW + timedelta(minutes=20))

    result = await update_panel_user_with_expiry(
        panel.update, end_date=PAST, is_active=False, now=NOW, user_id=7, status='DISABLED'
    )

    assert panel.calls[0] == {'user_id': 7, 'status': 'DISABLED'}
    assert panel.calls[-1] == {'user_id': 7, 'expire_at': NOW + SKEW_RETRY_MARGIN}
    assert result.expire_at == FUTURE  # the date stays stale; the status already closed access


async def test_a_panel_value_that_is_not_a_date_counts_as_unknown():
    panel = FakePanel(current=FUTURE)

    await update_panel_user_with_expiry(
        panel.update, end_date=PAST, is_active=False, panel_current=object(), now=NOW, user_id=7
    )

    # Nothing guessed up front; the real answer of the panel decides.
    assert panel.calls == [{'user_id': 7}, {'user_id': 7, 'expire_at': NOW + MINIMUM_FUTURE}]


async def test_unrelated_errors_propagate_without_a_retry():
    error = RemnaWaveAPIError('nf', status_code=404, response_data={'errorCode': 'A063'})
    panel = FakePanel(current=FUTURE, error=error)

    with pytest.raises(RemnaWaveAPIError) as caught:
        await update_panel_user_with_expiry(
            panel.update, end_date=PAST, is_active=False, panel_current=FUTURE, now=NOW, user_id=7
        )

    assert caught.value is error
    assert len(panel.calls) == 1


async def test_subscription_without_end_date_sends_no_date():
    panel = FakePanel(current=FUTURE)

    await update_panel_user_with_expiry(panel.update, end_date=None, is_active=False, now=NOW, user_id=7)

    assert panel.calls == [{'user_id': 7}]


# ==================== guard: nobody computes the date by hand ====================

#: The old formula. Every copy of it is one more place that overwrites the real date.
OLD_FORMULA = re.compile(r'(now|current_time|datetime\.now\(UTC\))\s*\+\s*timedelta\(minutes=1\)')

#: Converted in its own step (the grace reconciler builds its own target). Must only shrink.
_NOT_YET_CONVERTED = frozenset({'app/services/grace_access_runtime.py'})


def test_nobody_clamps_the_panel_date_by_hand():
    offenders = [
        str(path)
        for path in sorted(pathlib.Path('app').rglob('*.py'))
        if str(path) not in _NOT_YET_CONVERTED and OLD_FORMULA.search(path.read_text('utf-8'))
    ]

    assert not offenders, f'panel end date clamped on the spot; use app/services/panel_expiry.py: {offenders}'
