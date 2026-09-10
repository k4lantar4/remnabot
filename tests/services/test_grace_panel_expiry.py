"""The grace reconciler no longer rewrites the panel end date of a disabled subscription.

Adapted from upstream 664ecea7. The reconciler brings the panel back to billing
reality every minute and, for a disabled target, used to send "now + 1 minute" —
so right after a full sync marked expired subscriptions as grace candidates, the
panel showed "expired a minute ago" again. A disabled target now carries no date:
access is closed by the status and the panel keeps the real end date.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.external.remnawave_api import UserStatus
from app.services.grace_access_runtime import (
    _build_billing_target,
    _build_restore_target,
    _PanelTarget,
    _serialize_panel_target,
)
from app.services.grace_access_service import GraceBillingState, GracePanelSnapshot


NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
PAST = NOW - timedelta(days=30)
FUTURE = NOW + timedelta(days=30)


def _billing_state(**overrides) -> GraceBillingState:
    base = dict(
        subscription_id=1,
        remnawave_id=42,
        status='expired',
        user_status='active',
        end_at=PAST,
        traffic_limit_bytes=0,
        used_traffic_bytes=0,
        squad_uuids=(),
        external_squad_uuid=None,
        device_limit=None,
    )
    base.update(overrides)
    return GraceBillingState(**base)


def test_billing_target_leaves_the_date_alone_for_disabled():
    target = _build_billing_target(_billing_state(), now=NOW)

    assert target.status == UserStatus.DISABLED
    assert target.expire_at is None


def test_billing_target_keeps_the_real_date_for_a_live_subscription():
    target = _build_billing_target(_billing_state(status='active', end_at=FUTURE), now=NOW)

    assert target.expire_at == FUTURE


def test_restore_target_leaves_the_date_alone_for_disabled():
    snapshot = GracePanelSnapshot(
        remnawave_id=42,
        status='expired',
        expire_at=PAST,
        traffic_limit_bytes=0,
        used_traffic_bytes=0,
        squad_uuids=(),
        external_squad_uuid=None,
        traffic_is_known=True,
        last_traffic_reset_at=None,
    )

    assert _build_restore_target(snapshot, now=NOW).expire_at is None


def test_payload_without_a_date_does_not_carry_it_over_from_the_base():
    """The base set was built for another transition; a date left in it would overwrite the real one."""
    target = _PanelTarget(
        status=UserStatus.DISABLED,
        expire_at=None,
        traffic_limit_bytes=0,
        squad_uuids=(),
        external_squad_uuid=None,
        device_limit=None,
    )

    payload = _serialize_panel_target(42, target, base_kwargs={'expire_at': NOW})

    assert 'expire_at' not in payload
    assert payload['status'] == UserStatus.DISABLED


def test_payload_with_a_date_still_sends_it():
    target = _PanelTarget(
        status=UserStatus.ACTIVE,
        expire_at=FUTURE,
        traffic_limit_bytes=0,
        squad_uuids=(),
        external_squad_uuid=None,
        device_limit=None,
    )

    assert _serialize_panel_target(42, target)['expire_at'] == FUTURE
