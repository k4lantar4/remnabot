from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.utils.legacy_display_match import (
    DbDisplayCandidate,
    LegacyDisplayCandidate,
    candidates_match,
    format_panel_username,
    is_unknown_panel_username,
    match_legacy_display_assignments,
)
from tools.migration.models import MigrationSubscription
from app.utils.legacy_display_match import legacy_candidates_from_cohorts


def _dt(days: int = 0) -> datetime:
    return datetime(2026, 7, 9, tzinfo=UTC) + timedelta(days=days)


def test_single_legacy_and_db_row_match() -> None:
    legacy = [
        LegacyDisplayCandidate(
            telegram_id=1713374557,
            tariff_id=2,
            traffic_limit_gb=100,
            end_date=_dt(),
            source_email='Germany(2)-134500',
        )
    ]
    db_rows = [
        DbDisplayCandidate(
            subscription_id=1,
            telegram_id=1713374557,
            tariff_id=2,
            traffic_limit_gb=100,
            end_date=_dt(1),
            panel_username='user_unknown_abc',
        )
    ]
    assignments, unmatched, _ = match_legacy_display_assignments(legacy, db_rows)
    assert assignments == [(1, 'Germany(2)-134500')]
    assert unmatched == []


def test_two_rows_same_key_assign_by_end_date() -> None:
    legacy = [
        LegacyDisplayCandidate(100, 2, 50, _dt(0), 'Germany(2)-111'),
        LegacyDisplayCandidate(100, 2, 50, _dt(20), 'Germany(2)-222'),
    ]
    db_rows = [
        DbDisplayCandidate(10, 100, 2, 50, _dt(1), 'user_unknown_a'),
        DbDisplayCandidate(11, 100, 2, 50, _dt(19), 'user_unknown_b'),
    ]
    assignments, unmatched, _ = match_legacy_display_assignments(legacy, db_rows)
    assert sorted(assignments) == [(10, 'Germany(2)-111'), (11, 'Germany(2)-222')]
    assert unmatched == []


def test_is_unknown_panel_username_filters_backfill_targets() -> None:
    assert is_unknown_panel_username('user_unknown_abc') is True
    assert is_unknown_panel_username('@partner_shortid') is False
    assert is_unknown_panel_username('Germany(2)-134500') is False

    legacy = LegacyDisplayCandidate(1, 2, 100, _dt(), 'France(VIP)-128850')
    unknown_db = DbDisplayCandidate(1, 1, 2, 100, _dt(), 'user_unknown_x')
    assert candidates_match(legacy, unknown_db, end_date_slop_days=21)


def test_format_panel_username_truncates_to_64_chars() -> None:
    long_email = 'A' * 80
    assert len(format_panel_username(long_email)) == 64
    assert format_panel_username('  Germany(2)-134500  ') == 'Germany(2)-134500'


def test_legacy_candidates_from_cohorts_maps_source_email() -> None:
    cohort = MigrationSubscription(
        telegram_id=42,
        tariff_id=3,
        squad_keys=['s3'],
        end_date=_dt(5),
        remaining_bytes=1,
        traffic_limit_gb=200,
        old_emails=['VIP-1'],
        old_uuids=['uuid-1'],
        source_email='VIP-1',
    )
    legacy = legacy_candidates_from_cohorts([cohort])
    assert len(legacy) == 1
    assert legacy[0].source_email == 'VIP-1'
    assert legacy[0].traffic_limit_gb == 200


def test_end_date_outside_slop_does_not_match() -> None:
    legacy = [LegacyDisplayCandidate(1, 2, 100, _dt(0), 'Germany(2)-1')]
    db_rows = [DbDisplayCandidate(1, 1, 2, 100, _dt(30), 'user_unknown_a')]
    assignments, unmatched, _ = match_legacy_display_assignments(legacy, db_rows, end_date_slop_days=21)
    assert assignments == []
    assert len(unmatched) == 1
