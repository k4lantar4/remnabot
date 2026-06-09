"""Inventory subscriptions whose panel_username cache is user_unknown_*.

Read-only — does not call RemnaWave API or mutate DB.

Usage:
  docker compose run --rm bot python tools/report_user_unknown_subscriptions.py
  docker compose run --rm bot python tools/report_user_unknown_subscriptions.py --json /tmp/user_unknown.json
  docker compose run --rm bot python tools/report_user_unknown_subscriptions.py --telegram-id 1713374557
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import func, select

from app.database.database import AsyncSessionLocal
from app.database.models import Subscription, User


def is_user_unknown_panel_username(name: str | None) -> bool:
    return (name or '').strip().startswith('user_unknown_')


async def collect_user_unknown_rows(
    *,
    telegram_id: int | None = None,
    limit: int | None = None,
) -> list[dict]:
    async with AsyncSessionLocal() as db:
        query = (
            select(
                Subscription.id,
                Subscription.remnawave_uuid,
                Subscription.remnawave_short_id,
                Subscription.panel_username,
                Subscription.traffic_limit_gb,
                Subscription.end_date,
                User.telegram_id,
                User.username,
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

    return [
        {
            'subscription_id': row.id,
            'telegram_id': row.telegram_id,
            'telegram_username': row.username,
            'remnawave_uuid': row.remnawave_uuid,
            'remnawave_short_id': row.remnawave_short_id,
            'panel_username': row.panel_username,
            'traffic_limit_gb': row.traffic_limit_gb,
            'end_date': row.end_date.isoformat() if row.end_date else None,
        }
        for row in rows
    ]


async def count_user_unknown_rows() -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.panel_username.like('user_unknown_%'))
        )
        return int(result.scalar_one())


async def main_async(
    *,
    telegram_id: int | None,
    limit: int | None,
    json_path: Path | None,
) -> None:
    rows = await collect_user_unknown_rows(telegram_id=telegram_id, limit=limit)
    total = await count_user_unknown_rows()
    payload = {'total_user_unknown': total, 'returned': len(rows), 'rows': rows}

    if json_path:
        json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'Wrote {len(rows)} rows (total={total}) to {json_path}')
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description='Report user_unknown_* subscription rows')
    parser.add_argument('--telegram-id', type=int, default=None)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--json', type=Path, default=None, dest='json_path')
    args = parser.parse_args()
    asyncio.run(
        main_async(
            telegram_id=args.telegram_id,
            limit=args.limit,
            json_path=args.json_path,
        )
    )


if __name__ == '__main__':
    main()
