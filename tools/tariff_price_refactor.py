"""Recalculate tariff catalog prices for 10000 Toman/GB production scale.

SAFE by default: dry-run only. Pass --execute --i-understand to write to DB.

Pricing model:
- Base unit: 10000 Toman per GB per 30-day month (stored as 1_000_000 kopeks/GB/month).
- custom_traffic_enabled=true; period_prices all 0 (price = GB × per_gb × months).
- Traffic top-up packages: gb × 1_000_000 kopeks (linear per GB).
- traffic_price_per_gb_kopeks: 1_000_000 for all tariffs.
- Partner promo group «شرکا» with 50% traffic discount (created if missing).

Usage:
    python -m tools.tariff_price_refactor              # dry-run report
    python -m tools.tariff_price_refactor --execute --i-understand
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

PRICE_PER_GB_TOMAN = 10000
KOPEKS_PER_TOMAN = 100
PRICE_PER_GB_KOPEKS = PRICE_PER_GB_TOMAN * KOPEKS_PER_TOMAN  # 1_000_000
REFERENCE_PERIOD_DAYS = 30
PARTNER_PROMO_GROUP_NAME = 'شرکا'
PARTNER_TRAFFIC_DISCOUNT_PERCENT = 50
MIN_TRAFFIC_GB = 1


def display_toman(kopeks: int) -> int:
    return kopeks // KOPEKS_PER_TOMAN


def target_monthly_kopeks(traffic_gb: int) -> int:
    return max(0, traffic_gb) * PRICE_PER_GB_KOPEKS


def zero_period_prices(period_prices: dict[str, int]) -> dict[str, int]:
    """Set all period prices to 0 for custom-traffic-only pricing."""
    return {str(days): 0 for days in period_prices}


def recalc_traffic_topup_packages(packages: dict[str, int] | None) -> dict[str, int]:
    if not packages:
        return {}
    updated: dict[str, int] = {}
    for gb_str, _old_price in packages.items():
        gb = int(gb_str)
        if gb <= 0:
            continue
        updated[str(gb)] = gb * PRICE_PER_GB_KOPEKS
    return updated


def build_traffic_packages_env(enabled_map: dict[int, bool] | None = None) -> str:
    """Classic-mode TRAFFIC_PACKAGES_CONFIG entries (gb:price_kopeks:enabled)."""
    packages = [
        (5, False),
        (10, False),
        (25, False),
        (50, True),
        (100, True),
        (250, False),
        (500, False),
        (1000, True),
        (0, True),  # unlimited sentinel
    ]
    parts: list[str] = []
    for gb, default_enabled in packages:
        enabled = enabled_map.get(gb, default_enabled) if enabled_map else default_enabled
        if gb == 0:
            price = 10 * PRICE_PER_GB_KOPEKS
        else:
            price = gb * PRICE_PER_GB_KOPEKS
        parts.append(f'{gb}:{price}:{"true" if enabled else "false"}')
    return ','.join(parts)


def build_classic_period_env(period_prices: dict[str, int]) -> dict[str, int]:
    """Map DB period keys to .env PRICE_*_DAYS integers (all 0 for custom-traffic model)."""
    field_map = {
        '14': 'PRICE_14_DAYS',
        '30': 'PRICE_30_DAYS',
        '60': 'PRICE_60_DAYS',
        '90': 'PRICE_90_DAYS',
        '180': 'PRICE_180_DAYS',
        '360': 'PRICE_360_DAYS',
    }
    return {field: 0 for days, field in field_map.items() if days in period_prices}


def build_tariff_price_patches(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patches: list[dict[str, Any]] = []
    for row in rows:
        traffic_gb = int(row.get('traffic_limit_gb') or 0)
        old_period = {str(k): int(v) for k, v in (row.get('period_prices') or {}).items()}
        old_topup = {str(k): int(v) for k, v in (row.get('traffic_topup_packages') or {}).items()}

        new_period = zero_period_prices(old_period) if old_period else {'30': 0}
        new_topup = recalc_traffic_topup_packages(old_topup)
        new_per_gb = PRICE_PER_GB_KOPEKS

        changed = (
            new_period != old_period
            or new_topup != old_topup
            or int(row.get('traffic_price_per_gb_kopeks') or 0) != new_per_gb
            or not row.get('custom_traffic_enabled')
            or int(row.get('min_traffic_gb') or 0) != MIN_TRAFFIC_GB
        )

        patches.append(
            {
                'id': row['id'],
                'name': row['name'],
                'traffic_limit_gb': traffic_gb,
                'old_period_prices': old_period,
                'new_period_prices': new_period,
                'old_traffic_topup_packages': old_topup,
                'new_traffic_topup_packages': new_topup,
                'old_traffic_price_per_gb_kopeks': int(row.get('traffic_price_per_gb_kopeks') or 0),
                'new_traffic_price_per_gb_kopeks': new_per_gb,
                'old_custom_traffic_enabled': bool(row.get('custom_traffic_enabled')),
                'new_custom_traffic_enabled': True,
                'old_min_traffic_gb': int(row.get('min_traffic_gb') or 0),
                'new_min_traffic_gb': MIN_TRAFFIC_GB,
                'changed': changed,
            }
        )
    return patches


def build_env_recommendations(reference_period_prices: dict[str, int]) -> dict[str, Any]:
    classic = build_classic_period_env(reference_period_prices)
    return {
        'PRICE_*_DAYS': classic,
        'BASE_SUBSCRIPTION_PRICE': 0,
        'TRAFFIC_PACKAGES_CONFIG': build_traffic_packages_env(),
        'PRICE_TRAFFIC_UNLIMITED': 10 * PRICE_PER_GB_KOPEKS,
        'PRICE_PER_GB_KOPEKS': PRICE_PER_GB_KOPEKS,
    }


async def _fetch_tariff_rows(db) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from app.database.models import Tariff

    result = await db.execute(select(Tariff).order_by(Tariff.id))
    tariffs = result.scalars().all()
    return [
        {
            'id': t.id,
            'name': t.name,
            'traffic_limit_gb': t.traffic_limit_gb,
            'period_prices': dict(t.period_prices or {}),
            'traffic_topup_packages': dict(t.traffic_topup_packages or {}),
            'traffic_price_per_gb_kopeks': t.traffic_price_per_gb_kopeks,
            'custom_traffic_enabled': t.custom_traffic_enabled,
            'min_traffic_gb': t.min_traffic_gb,
        }
        for t in tariffs
    ]


async def _ensure_partner_promo_group(db, execute: bool) -> dict[str, Any]:
    from sqlalchemy import select

    from app.database.models import PromoGroup

    result = await db.execute(select(PromoGroup).where(PromoGroup.name == PARTNER_PROMO_GROUP_NAME))
    existing = result.scalar_one_or_none()
    if existing:
        info = {
            'action': 'exists',
            'id': existing.id,
            'name': existing.name,
            'traffic_discount_percent': existing.traffic_discount_percent,
        }
        print(f"  ✅ Partner promo group already exists: id={existing.id} ({existing.name}), traffic -{existing.traffic_discount_percent}%")
        return info

    if not execute:
        print(f"  ➕ Would create partner promo group «{PARTNER_PROMO_GROUP_NAME}» (traffic -{PARTNER_TRAFFIC_DISCOUNT_PERCENT}%)")
        return {'action': 'would_create', 'name': PARTNER_PROMO_GROUP_NAME, 'traffic_discount_percent': PARTNER_TRAFFIC_DISCOUNT_PERCENT}

    group = PromoGroup(
        name=PARTNER_PROMO_GROUP_NAME,
        traffic_discount_percent=PARTNER_TRAFFIC_DISCOUNT_PERCENT,
        is_default=False,
        apply_discounts_to_addons=True,
    )
    db.add(group)
    await db.flush()
    print(f"  ✏️  Created partner promo group id={group.id} ({group.name}), traffic -{group.traffic_discount_percent}%")
    return {'action': 'created', 'id': group.id, 'name': group.name, 'traffic_discount_percent': group.traffic_discount_percent}


async def _apply_patches(db, patches: list[dict[str, Any]]) -> None:
    from sqlalchemy import select

    from app.database.models import Tariff

    for patch in patches:
        if not patch['changed']:
            print(f"  ✅ id={patch['id']} ({patch['name']}) — already at target scale")
            continue

        result = await db.execute(select(Tariff).where(Tariff.id == patch['id']))
        tariff = result.scalar_one_or_none()
        if tariff is None:
            print(f"  ❌ SKIP id={patch['id']}: not found")
            continue

        tariff.period_prices = patch['new_period_prices']
        tariff.traffic_topup_packages = patch['new_traffic_topup_packages']
        tariff.traffic_price_per_gb_kopeks = patch['new_traffic_price_per_gb_kopeks']
        tariff.custom_traffic_enabled = patch['new_custom_traffic_enabled']
        tariff.min_traffic_gb = patch['new_min_traffic_gb']
        print(
            f"  ✏️  id={patch['id']} ({patch['name']}): "
            f"custom_traffic=true, per_gb={display_toman(patch['new_traffic_price_per_gb_kopeks']):,} تومان/GB, "
            f"period_prices→0"
        )

    await db.commit()


def _print_report(patches: list[dict[str, Any]], partner_info: dict[str, Any]) -> None:
    print('\n=== TARIFF PRICE REFACTOR (10000 Toman/GB) — DRY RUN ===\n')
    for p in patches:
        print(f"Tariff {p['id']}: {p['name']} — custom_traffic model")
        print(f"  custom_traffic_enabled: {p['old_custom_traffic_enabled']} → {p['new_custom_traffic_enabled']}")
        print(f"  traffic_price_per_gb: {display_toman(p['old_traffic_price_per_gb_kopeks']):,} → {display_toman(p['new_traffic_price_per_gb_kopeks']):,} تومان")
        print(f"  min_traffic_gb: {p['old_min_traffic_gb']} → {p['new_min_traffic_gb']}")
        for days in sorted(p['old_period_prices'], key=int):
            old_k = int(p['old_period_prices'][days])
            new_k = int(p['new_period_prices'][days])
            print(f"  period {days}d: {display_toman(old_k):,} → {display_toman(new_k):,} تومان ({old_k} → {new_k} kopeks)")
        if p['old_traffic_topup_packages']:
            print('  traffic top-up:')
            for gb, old_k in sorted(p['old_traffic_topup_packages'].items(), key=lambda x: int(x[0])):
                new_k = p['new_traffic_topup_packages'].get(gb, 0)
                print(f"    {gb} GB: {display_toman(old_k):,} → {display_toman(new_k):,} تومان")
        print()

    print('=== Partner promo group ===')
    if partner_info.get('action') == 'exists':
        print(f"  Already exists: id={partner_info['id']} ({partner_info['name']}), traffic -{partner_info['traffic_discount_percent']}%")
    else:
        print(f"  Would create: «{PARTNER_PROMO_GROUP_NAME}», traffic -{PARTNER_TRAFFIC_DISCOUNT_PERCENT}%")
    print()

    ref = patches[0]['new_period_prices'] if patches else {}
    env = build_env_recommendations(ref)
    print('=== Recommended .env updates (classic fallback / sync) ===')
    for key, val in env['PRICE_*_DAYS'].items():
        print(f"  {key}={val}")
    print(f"  BASE_SUBSCRIPTION_PRICE={env['BASE_SUBSCRIPTION_PRICE']}")
    print(f"  TRAFFIC_PACKAGES_CONFIG=\"{env['TRAFFIC_PACKAGES_CONFIG']}\"")
    print(f"  PRICE_TRAFFIC_UNLIMITED={env['PRICE_TRAFFIC_UNLIMITED']}")
    print()

    changed = [p for p in patches if p['changed']]
    print(f"{len(changed)}/{len(patches)} tariff(s) need updating.")
    if changed or partner_info.get('action') != 'exists':
        print('Re-run with --execute --i-understand to apply.\n')
    else:
        print('Nothing to do.\n')


async def _run(execute: bool) -> bool:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            rows = await _fetch_tariff_rows(session)
            patches = build_tariff_price_patches(rows)

            if not execute:
                partner_info = await _ensure_partner_promo_group(session, execute=False)
                _print_report(patches, partner_info)
            else:
                print('\n=== EXECUTING tariff price refactor ===')
                await _apply_patches(session, patches)
                await _ensure_partner_promo_group(session, execute=True)
                await session.commit()
                print('Done. Restart bot to refresh period price cache.\n')
    finally:
        await engine.dispose()

    return True


def main() -> None:
    parser = argparse.ArgumentParser(description='Tariff price refactor to 10000 Toman/GB (dry-run by default)')
    parser.add_argument('--execute', action='store_true', help='Apply changes to DB (requires --i-understand)')
    parser.add_argument('--i-understand', dest='confirmed', action='store_true', help='Confirm DB writes')
    args = parser.parse_args()

    if args.execute and not args.confirmed:
        print('ERROR: --execute requires --i-understand flag to confirm DB writes.')
        sys.exit(2)

    ok = asyncio.run(_run(execute=args.execute))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
