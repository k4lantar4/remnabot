from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from tools.migration.models import MigrationSubscription

SECONDS_PER_DAY = 86400


@dataclass(frozen=True)
class LegacyDisplayCandidate:
    telegram_id: int
    tariff_id: int
    traffic_limit_gb: int
    end_date: datetime
    source_email: str


@dataclass(frozen=True)
class DbDisplayCandidate:
    subscription_id: int
    telegram_id: int
    tariff_id: int
    traffic_limit_gb: int
    end_date: datetime
    panel_username: str


def is_unknown_panel_username(panel_username: str | None) -> bool:
    return (panel_username or '').strip().startswith('user_unknown_')


def format_panel_username(source_email: str) -> str:
    return source_email.strip()[:64]


def legacy_candidates_from_cohorts(subscribers: list[MigrationSubscription]) -> list[LegacyDisplayCandidate]:
    return [
        LegacyDisplayCandidate(
            telegram_id=sub.telegram_id,
            tariff_id=sub.tariff_id,
            traffic_limit_gb=sub.traffic_limit_gb,
            end_date=sub.end_date,
            source_email=sub.source_email,
        )
        for sub in subscribers
    ]


def _normalize_dt(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def end_date_delta_days(left: datetime, right: datetime) -> float:
    left_norm = _normalize_dt(left)
    right_norm = _normalize_dt(right)
    return abs((left_norm - right_norm).total_seconds()) / SECONDS_PER_DAY


def candidates_match(
    legacy: LegacyDisplayCandidate,
    db_row: DbDisplayCandidate,
    *,
    end_date_slop_days: float,
) -> bool:
    if legacy.telegram_id != db_row.telegram_id:
        return False
    if legacy.tariff_id != db_row.tariff_id:
        return False
    if legacy.traffic_limit_gb != db_row.traffic_limit_gb:
        return False
    return end_date_delta_days(legacy.end_date, db_row.end_date) <= end_date_slop_days


def match_legacy_display_assignments(
    legacy_candidates: list[LegacyDisplayCandidate],
    db_candidates: list[DbDisplayCandidate],
    *,
    end_date_slop_days: float = 21,
) -> tuple[list[tuple[int, str]], list[DbDisplayCandidate], list[LegacyDisplayCandidate]]:
    """Greedy one-to-one match: each source_email used at most once."""
    options_by_sub: dict[int, list[tuple[LegacyDisplayCandidate, float]]] = {}
    for db_row in db_candidates:
        options: list[tuple[LegacyDisplayCandidate, float]] = []
        for legacy in legacy_candidates:
            if not candidates_match(legacy, db_row, end_date_slop_days=end_date_slop_days):
                continue
            delta = end_date_delta_days(legacy.end_date, db_row.end_date)
            options.append((legacy, delta))
        options_by_sub[db_row.subscription_id] = sorted(options, key=lambda item: item[1])

    used_emails: set[str] = set()
    assignments: list[tuple[int, str]] = []
    unmatched_db: list[DbDisplayCandidate] = []

    for db_row in sorted(db_candidates, key=lambda row: len(options_by_sub[row.subscription_id])):
        best_legacy: LegacyDisplayCandidate | None = None
        best_delta: float | None = None
        for legacy, delta in options_by_sub[db_row.subscription_id]:
            if legacy.source_email in used_emails:
                continue
            if best_legacy is None or delta < best_delta:
                best_legacy = legacy
                best_delta = delta
        if best_legacy is None:
            unmatched_db.append(db_row)
            continue
        used_emails.add(best_legacy.source_email)
        assignments.append((db_row.subscription_id, best_legacy.source_email))

    unused_legacy = [legacy for legacy in legacy_candidates if legacy.source_email not in used_emails]
    return assignments, unmatched_db, unused_legacy
