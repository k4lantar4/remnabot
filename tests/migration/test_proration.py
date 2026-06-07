from datetime import UTC, datetime

from tools.migration.proration import (
    BACKUP_ANCHOR,
    compute_end_date,
    compute_remaining_traffic,
    is_expired_at_anchor,
    remaining_seconds_at_anchor,
)


def test_ninety_nine_day_subscription_has_seventy_three_days_at_anchor():
    # Plan example: bought 2026-02-02, 99-day life → expires 2026-05-12 08:00 UTC
    expiry = datetime(2026, 5, 12, 8, 0, 0, tzinfo=UTC)
    remaining = (expiry - BACKUP_ANCHOR).days
    assert remaining == 73


def test_compute_end_date_applies_remaining_from_migration_run():
    expiry_unix = int(datetime(2026, 5, 12, 8, 0, 0, tzinfo=UTC).timestamp())
    migration_run = datetime(2026, 6, 7, tzinfo=UTC)
    end = compute_end_date(expiry_unix, migration_run)
    assert end.date().isoformat() == '2026-08-19'


def test_compute_remaining_traffic_used_is_zero_in_new_db():
    total = 100 * 1024**3
    up = 10 * 1024**3
    down = 5 * 1024**3
    remaining, limit_gb = compute_remaining_traffic(total, up, down)
    assert remaining == 85 * 1024**3
    assert limit_gb == 85


def test_over_quota_returns_zero():
    total = 1000
    remaining, limit_gb = compute_remaining_traffic(total, 600, 500)
    assert remaining == 0
    assert limit_gb == 0


def test_expired_at_anchor():
    expired_unix = int(datetime(2026, 2, 1, tzinfo=UTC).timestamp())
    assert is_expired_at_anchor(expired_unix) is True
    assert remaining_seconds_at_anchor(expired_unix) <= 0
