from __future__ import annotations

from datetime import UTC, datetime

BACKUP_ANCHOR = datetime(2026, 2, 28, 8, 0, 0, tzinfo=UTC)


def normalize_expiry_unix(raw: int) -> int:
    if raw <= 0:
        return 0
    if raw > 10_000_000_000:
        return raw // 1000
    return raw


def remaining_seconds_at_anchor(expiry_unix_sec: int) -> float:
    expiry = datetime.fromtimestamp(expiry_unix_sec, tz=UTC)
    return (expiry - BACKUP_ANCHOR).total_seconds()


def is_expired_at_anchor(expiry_unix_sec: int) -> bool:
    return remaining_seconds_at_anchor(expiry_unix_sec) <= 0


def compute_end_date(expiry_unix_sec: int, migration_run: datetime) -> datetime:
    expiry = datetime.fromtimestamp(expiry_unix_sec, tz=UTC)
    remaining = expiry - BACKUP_ANCHOR
    if remaining.total_seconds() <= 0:
        return migration_run
    if migration_run.tzinfo is None:
        migration_run = migration_run.replace(tzinfo=UTC)
    return migration_run + remaining


def compute_remaining_traffic(total_bytes: int, up: int, down: int) -> tuple[int, int]:
    remaining = max(0, total_bytes - up - down)
    if remaining <= 0:
        return 0, 0
    limit_gb = max(1, (remaining + 1024**3 - 1) // (1024**3))
    return remaining, limit_gb
