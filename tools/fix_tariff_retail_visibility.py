#!/usr/bin/env python3
"""Ops: remove tariff promo-group restrictions so active tariffs are visible to all users.

Discounts remain on PromoGroup (e.g. شرکا −50% traffic); this only clears tariff_promo_groups.

Dry-run by default. Pass --execute to apply.

Usage:
    docker compose run --rm bot python tools/fix_tariff_retail_visibility.py
    docker compose run --rm bot python tools/fix_tariff_retail_visibility.py --execute
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.crud.tariff import set_tariff_promo_groups
from app.database.database import AsyncSessionLocal
from app.database.models import Tariff


async def main(execute: bool) -> None:
    async with AsyncSessionLocal() as db:
        tariffs = (
            await db.scalars(
                select(Tariff)
                .options(selectinload(Tariff.allowed_promo_groups))
                .where(Tariff.is_active.is_(True))
                .order_by(Tariff.id)
            )
        ).all()

        restricted = [t for t in tariffs if t.allowed_promo_groups]
        print(f'Active tariffs: {len(tariffs)}, with promo restrictions: {len(restricted)}')
        for t in restricted:
            names = [(pg.id, pg.name) for pg in t.allowed_promo_groups]
            print(f'  id={t.id} name={t.name!r} allowed={names}')

        if not restricted:
            print('✅ No restricted tariffs — nothing to do')
            return

        if not execute:
            print('Dry-run only. Re-run with --execute to clear restrictions.')
            return

        for t in restricted:
            await set_tariff_promo_groups(db, t, [])
            print(f'  cleared id={t.id}')

        print(f'✅ Cleared restrictions on {len(restricted)} tariff(s)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Clear tariff promo-group visibility restrictions')
    parser.add_argument('--execute', action='store_true', help='Apply changes (default: dry-run)')
    args = parser.parse_args()
    asyncio.run(main(execute=args.execute))
