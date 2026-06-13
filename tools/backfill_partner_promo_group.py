#!/usr/bin/env python3
"""One-off ops: assign PromoGroup «شرکا» to approved partners missing M2M row.

Dry-run by default. Pass --execute to apply.

Usage:
    docker compose run --rm bot python tools/backfill_partner_promo_group.py
    docker compose run --rm bot python tools/backfill_partner_promo_group.py --execute
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import func, select

from app.database.crud.user_promo_group import add_user_to_promo_group
from app.database.database import AsyncSessionLocal
from app.database.models import PartnerStatus, PromoGroup, User, UserPromoGroup

PARTNER_PROMO_GROUP_NAME = 'شرکا'


async def _count_coverage(db) -> tuple[int, int]:
    approved = await db.scalar(
        select(func.count()).select_from(User).where(User.partner_status == PartnerStatus.APPROVED.value)
    )
    with_group = await db.scalar(
        select(func.count())
        .select_from(UserPromoGroup)
        .join(User, UserPromoGroup.user_id == User.id)
        .join(PromoGroup, UserPromoGroup.promo_group_id == PromoGroup.id)
        .where(
            User.partner_status == PartnerStatus.APPROVED.value,
            PromoGroup.name == PARTNER_PROMO_GROUP_NAME,
        )
    )
    return int(approved or 0), int(with_group or 0)


async def main(execute: bool) -> None:
    async with AsyncSessionLocal() as db:
        partner_group = await db.scalar(select(PromoGroup).where(PromoGroup.name == PARTNER_PROMO_GROUP_NAME))
        if not partner_group:
            print(f'❌ PromoGroup «{PARTNER_PROMO_GROUP_NAME}» not found')
            return

        approved_before, with_group_before = await _count_coverage(db)
        print(f'Before: approved={approved_before} with_{PARTNER_PROMO_GROUP_NAME}={with_group_before}')

        missing_users = (
            await db.scalars(
                select(User.id)
                .where(User.partner_status == PartnerStatus.APPROVED.value)
                .where(
                    ~User.id.in_(
                        select(UserPromoGroup.user_id).where(UserPromoGroup.promo_group_id == partner_group.id)
                    )
                )
            )
        ).all()

        print(f'Missing M2M rows: {len(missing_users)}')
        if not missing_users:
            print('✅ Nothing to backfill')
            return

        if not execute:
            print('Dry-run only. Re-run with --execute to assign group.')
            return

        for user_id in missing_users:
            await add_user_to_promo_group(
                db,
                user_id,
                partner_group.id,
                assigned_by='audit_backfill',
                commit=False,
            )
        await db.commit()

        approved_after, with_group_after = await _count_coverage(db)
        print(f'After: approved={approved_after} with_{PARTNER_PROMO_GROUP_NAME}={with_group_after}')
        print(f'✅ Backfilled {len(missing_users)} users')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backfill partner promo group M2M assignments')
    parser.add_argument('--execute', action='store_true', help='Apply changes (default: dry-run)')
    args = parser.parse_args()
    asyncio.run(main(execute=args.execute))
