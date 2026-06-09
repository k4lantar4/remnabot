"""Backfill subscriptions.panel_username from RemnaWave panel (read-only).

Usage:
  docker compose run --rm bot python tools/backfill_panel_usernames.py
  docker compose run --rm bot python tools/backfill_panel_usernames.py --dry-run
  docker compose run --rm bot python tools/backfill_panel_usernames.py --limit 100
"""
from __future__ import annotations

import argparse
import asyncio

import structlog
from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.database.models import Subscription
from app.services.remnawave_service import RemnaWaveService

logger = structlog.get_logger(__name__)


async def backfill(*, dry_run: bool, limit: int | None) -> dict[str, int]:
    stats = {'candidates': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
    service = RemnaWaveService()
    if not service.is_configured:
        raise RuntimeError('RemnaWave API not configured')

    async with AsyncSessionLocal() as db:
        q = (
            select(Subscription)
            .where(Subscription.remnawave_uuid.is_not(None))
            .where((Subscription.panel_username.is_(None)) | (Subscription.panel_username == ''))
            .order_by(Subscription.id)
        )
        if limit:
            q = q.limit(limit)
        subs = (await db.execute(q)).scalars().all()
        stats['candidates'] = len(subs)

        async with service.get_api_client() as api:
            for sub in subs:
                try:
                    panel_user = await api.get_user_by_uuid(sub.remnawave_uuid)
                    if not panel_user or not panel_user.username:
                        stats['skipped'] += 1
                        continue
                    name = panel_user.username.strip()[:64]
                    if not name:
                        stats['skipped'] += 1
                        continue
                    logger.info(
                        'backfill panel_username',
                        subscription_id=sub.id,
                        panel_username=name,
                        dry_run=dry_run,
                    )
                    if not dry_run:
                        sub.panel_username = name
                        stats['updated'] += 1
                    else:
                        stats['updated'] += 1
                except Exception as exc:
                    logger.warning('backfill failed', subscription_id=sub.id, error=str(exc))
                    stats['errors'] += 1

        if not dry_run:
            await db.commit()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=None)
    args = parser.parse_args()
    stats = asyncio.run(backfill(dry_run=args.dry_run, limit=args.limit))
    print(stats)


if __name__ == '__main__':
    main()
