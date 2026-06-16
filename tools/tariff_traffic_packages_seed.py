"""Seed tariff purchase traffic_topup_packages for split-pricing flow.

Default package ladder: 30, 40, 50, 100, 200 GB at 10,000 Toman/GB
(catalog kopeks = gb × 1_000_000).

Usage:
    python -m tools.tariff_traffic_packages_seed              # dry-run
    python -m tools.tariff_traffic_packages_seed --execute --i-understand
    python -m tools.tariff_traffic_packages_seed --tariff-id 2 --execute --i-understand
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

PACKAGE_GBS = (30, 40, 50, 100, 200)
KOPEKS_PER_GB = 1_000_000  # 10,000 Toman display per GB (÷100 in format_price)


def build_packages() -> dict[str, int]:
    return {str(gb): gb * KOPEKS_PER_GB for gb in PACKAGE_GBS}


async def _run(execute: bool, tariff_id: int | None) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings
    from app.database.models import Tariff

    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    packages = build_packages()
    min_gb = min(PACKAGE_GBS)
    max_gb = max(PACKAGE_GBS)

    try:
        async with factory() as session:
            stmt = select(Tariff).where(Tariff.is_active.is_(True))
            if tariff_id is not None:
                stmt = stmt.where(Tariff.id == tariff_id)
            result = await session.execute(stmt)
            tariffs = list(result.scalars().all())

            if not tariffs:
                print('No matching tariffs found.')
                return

            print(f'Package ladder: {PACKAGE_GBS} GB')
            for gb, price in sorted((int(k), v) for k, v in packages.items()):
                print(f'  {gb} GB -> {price:,} kopeks ({price // 100:,} Toman display)')

            for tariff in tariffs:
                if not tariff.can_purchase_custom_traffic():
                    print(f'\n[tariff {tariff.id}] skip — custom traffic disabled')
                    continue

                old = dict(tariff.traffic_topup_packages or {})
                print(f'\n[tariff {tariff.id}] {tariff.name}')
                print(f'  old packages: {old}')
                print(f'  new packages: {packages}')
                print(f'  min_traffic_gb: {tariff.min_traffic_gb} -> {min_gb}')
                print(f'  max_traffic_gb: {tariff.max_traffic_gb} -> {max_gb}')

                if execute:
                    tariff.traffic_topup_packages = packages
                    tariff.min_traffic_gb = min_gb
                    tariff.max_traffic_gb = max_gb
                    if not tariff.traffic_price_per_gb_kopeks:
                        tariff.traffic_price_per_gb_kopeks = KOPEKS_PER_GB

            if execute:
                await session.commit()
                print('\nApplied.')
            else:
                print('\nDry-run only. Re-run with --execute --i-understand to apply.')
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description='Seed tariff traffic_topup_packages ladder')
    parser.add_argument('--execute', action='store_true', help='Write changes to DB')
    parser.add_argument('--i-understand', action='store_true', help='Required with --execute')
    parser.add_argument('--tariff-id', type=int, default=None, help='Limit to one tariff id')
    args = parser.parse_args()

    if args.execute and not args.i_understand:
        parser.error('--execute requires --i-understand')

    asyncio.run(_run(execute=args.execute, tariff_id=args.tariff_id))


if __name__ == '__main__':
    main()
