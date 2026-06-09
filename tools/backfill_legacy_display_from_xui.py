"""Backfill subscriptions.panel_username from x-ui backup (display cache only).

Does not rename RemnaWave panel users.

Usage:
  python tools/backfill_legacy_display_from_xui.py
  python tools/backfill_legacy_display_from_xui.py --execute
  python tools/backfill_legacy_display_from_xui.py --dry-run --telegram-id 1713374557
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import structlog
from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.database.models import Subscription, User
from app.utils.legacy_display_match import (
    DbDisplayCandidate,
    format_panel_username,
    is_unknown_panel_username,
    legacy_candidates_from_cohorts,
    match_legacy_display_assignments,
)
from tools.migration.extract_rookari import parse_rookari_tables
from tools.migration.extract_xui import extract_all_xui_clients
from tools.migration.join_filter import build_migration_cohorts

logger = structlog.get_logger(__name__)


def load_legacy_candidates():
    xui_clients = extract_all_xui_clients()
    bot_users, config_stats, sellers = parse_rookari_tables()
    subscribers, _, _ = build_migration_cohorts(xui_clients, bot_users, config_stats, sellers)
    return legacy_candidates_from_cohorts(subscribers)


async def load_db_candidates(
    *,
    telegram_id: int | None,
    limit: int | None,
) -> list[DbDisplayCandidate]:
    async with AsyncSessionLocal() as db:
        query = (
            select(
                Subscription.id,
                Subscription.traffic_limit_gb,
                Subscription.tariff_id,
                Subscription.end_date,
                Subscription.panel_username,
                User.telegram_id,
            )
            .join(User, User.id == Subscription.user_id)
            .where(Subscription.panel_username.like('user_unknown_%'))
            .order_by(Subscription.id)
        )
        if telegram_id is not None:
            query = query.where(User.telegram_id == telegram_id)
        if limit is not None:
            query = query.limit(limit)
        rows = (await db.execute(query)).all()

    candidates: list[DbDisplayCandidate] = []
    for row in rows:
        panel_username = (row.panel_username or '').strip()
        if not is_unknown_panel_username(panel_username):
            continue
        candidates.append(
            DbDisplayCandidate(
                subscription_id=row.id,
                telegram_id=row.telegram_id,
                tariff_id=row.tariff_id,
                traffic_limit_gb=row.traffic_limit_gb,
                end_date=row.end_date,
                panel_username=panel_username,
            )
        )
    return candidates


async def backfill(
    *,
    dry_run: bool,
    end_date_slop_days: float,
    telegram_id: int | None,
    limit: int | None,
    report_unmatched: Path | None,
) -> dict[str, int | list]:
    stats: dict[str, int | list] = {
        'legacy_candidates': 0,
        'db_candidates': 0,
        'matched': 0,
        'unmatched': 0,
        'updated': 0,
    }

    legacy_candidates = load_legacy_candidates()
    stats['legacy_candidates'] = len(legacy_candidates)

    db_candidates = await load_db_candidates(telegram_id=telegram_id, limit=limit)
    stats['db_candidates'] = len(db_candidates)

    assignments, unmatched_db, _unused_legacy = match_legacy_display_assignments(
        legacy_candidates,
        db_candidates,
        end_date_slop_days=end_date_slop_days,
    )
    stats['matched'] = len(assignments)
    stats['unmatched'] = len(unmatched_db)

    if report_unmatched is not None:
        payload = [
            {
                'subscription_id': row.subscription_id,
                'telegram_id': row.telegram_id,
                'tariff_id': row.tariff_id,
                'traffic_limit_gb': row.traffic_limit_gb,
                'end_date': row.end_date.isoformat(),
                'panel_username': row.panel_username,
            }
            for row in unmatched_db
        ]
        report_unmatched.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        stats['report_unmatched_path'] = str(report_unmatched)

    if not assignments:
        return stats

    assignment_by_id = {sub_id: email for sub_id, email in assignments}

    async with AsyncSessionLocal() as db:
        subs = (
            await db.execute(select(Subscription).where(Subscription.id.in_(assignment_by_id.keys())))
        ).scalars().all()
        for sub in subs:
            source_email = assignment_by_id[sub.id]
            new_name = format_panel_username(source_email)
            logger.info(
                'backfill legacy panel_username',
                subscription_id=sub.id,
                old_panel_username=sub.panel_username,
                panel_username=new_name,
                dry_run=dry_run,
            )
            if not dry_run:
                sub.panel_username = new_name
                stats['updated'] = int(stats['updated']) + 1
            else:
                stats['updated'] = int(stats['updated']) + 1

        if not dry_run:
            await db.commit()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description='Backfill panel_username from x-ui backup')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Preview only (default)')
    parser.add_argument('--execute', action='store_true', help='Write changes to DB')
    parser.add_argument('--end-date-slop-days', type=float, default=21)
    parser.add_argument('--telegram-id', type=int, default=None)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--report-unmatched', type=Path, default=None)
    args = parser.parse_args()

    dry_run = not args.execute
    stats = asyncio.run(
        backfill(
            dry_run=dry_run,
            end_date_slop_days=args.end_date_slop_days,
            telegram_id=args.telegram_id,
            limit=args.limit,
            report_unmatched=args.report_unmatched,
        )
    )
    print(stats)


if __name__ == '__main__':
    main()
