"""Seed zero tariff period_prices from env/fallback ladder.

Dry-run by default:
    python -m tools.tariff_period_price_seed

Apply changes:
    python -m tools.tariff_period_price_seed --execute
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database.models import Tariff
from app.utils.pricing_utils import calculate_months_from_days

FALLBACK_LADDER: dict[int, int] = {
    14: 10_000,
    30: 20_000,
    60: 38_000,
    90: 55_000,
    180: 105_000,
    360: 200_000,
}

PERIOD_ENV_FIELDS: dict[int, str] = {
    14: 'PRICE_14_DAYS',
    30: 'PRICE_30_DAYS',
    60: 'PRICE_60_DAYS',
    90: 'PRICE_90_DAYS',
    180: 'PRICE_180_DAYS',
    360: 'PRICE_360_DAYS',
}


def _resolve_seed_price(days: int) -> tuple[int, str]:
    env_field = PERIOD_ENV_FIELDS.get(days)
    if env_field:
        env_price = int(getattr(settings, env_field, 0) or 0)
        if env_price > 0:
            return env_price, f'settings.{env_field}'

    ladder = FALLBACK_LADDER.get(days)
    if ladder is not None:
        return ladder, 'fallback.ladder'

    monthly = int(getattr(settings, 'DEFAULT_PERIOD_PRICE_PER_MONTH', 20000) or 20000)
    monthly = max(1, monthly)
    return monthly * calculate_months_from_days(days), 'fallback.monthly'


def _seed_period_prices(period_prices: dict[str, int]) -> tuple[dict[str, int], list[dict[str, str | int]]]:
    updated = {str(k): int(v) for k, v in (period_prices or {}).items()}
    changes: list[dict[str, str | int]] = []
    for period_key, value in list(updated.items()):
        days = int(period_key)
        if value != 0:
            continue
        seeded, source = _resolve_seed_price(days)
        updated[period_key] = seeded
        changes.append({'days': days, 'old': value, 'new': seeded, 'source': source})
    return updated, changes


async def _run(execute: bool) -> int:
    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    changed_tariffs = 0
    changed_periods = 0
    try:
        async with factory() as db:
            result = await db.execute(select(Tariff).order_by(Tariff.id))
            tariffs = result.scalars().all()

            print('=== Tariff period price seed ===')
            for tariff in tariffs:
                seeded_prices, changes = _seed_period_prices(dict(tariff.period_prices or {}))
                if not changes:
                    continue
                changed_tariffs += 1
                changed_periods += len(changes)
                print(f'- Tariff #{tariff.id} {tariff.name}:')
                for item in changes:
                    print(
                        f'  {item["days"]}d: {item["old"]} -> {item["new"]} ({item["source"]})'
                    )
                if execute:
                    tariff.period_prices = seeded_prices

            if execute and changed_tariffs > 0:
                await db.commit()
                print('\nApplied DB updates.')
            else:
                print('\nDry-run only. Re-run with --execute to apply.')

            smoke_price, smoke_source = _resolve_seed_price(60)
            print(
                f'Smoke hint: 10GB package + 60d ~= package_price + {smoke_price} ({smoke_source}).'
            )
    finally:
        await engine.dispose()

    print(f'Updated tariffs: {changed_tariffs}, seeded periods: {changed_periods}')
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description='Seed zero tariff period_prices from env/fallback ladder')
    parser.add_argument('--execute', action='store_true', help='Write seeded period prices to DB')
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(execute=args.execute)))


if __name__ == '__main__':
    main()
