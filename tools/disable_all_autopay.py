"""Bulk-reset subscriptions.autopay_enabled to false.

Usage:
  docker compose run --rm bot python tools/disable_all_autopay.py
  docker compose run --rm bot python tools/disable_all_autopay.py --execute
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import func, select, update

from app.database.database import AsyncSessionLocal
from app.database.models import Subscription


async def count_enabled_autopay_rows(db) -> int:
    result = await db.execute(
        select(func.count()).select_from(Subscription).where(Subscription.autopay_enabled.is_(True))
    )
    return int(result.scalar_one())


async def disable_all_autopay(*, execute: bool) -> int:
    async with AsyncSessionLocal() as db:
        count = await count_enabled_autopay_rows(db)
        if execute and count > 0:
            await db.execute(
                update(Subscription)
                .where(Subscription.autopay_enabled.is_(True))
                .values(autopay_enabled=False)
            )
            await db.commit()
        return count


async def main_async(*, execute: bool) -> None:
    count = await disable_all_autopay(execute=execute)
    if execute:
        remaining = await disable_all_autopay(execute=False)
        print(f'Updated {count} subscription(s); remaining autopay_enabled=true: {remaining}')
    else:
        print(f'Dry run: {count} subscription(s) would be updated (pass --execute to apply)')


def main() -> None:
    parser = argparse.ArgumentParser(description='Bulk-disable subscriptions.autopay_enabled')
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Apply UPDATE; default is dry-run count only',
    )
    args = parser.parse_args()
    asyncio.run(main_async(execute=args.execute))


if __name__ == '__main__':
    main()
