"""Read-only post-migration tariff audit.

Usage:
    python -m tools.tariff_audit          # reads live DB
    python -m tools.tariff_audit --json   # machine-readable output

Pure function ``build_tariff_audit_report(rows)`` is tested independently
and accepts a list of dicts so it can be unit-tested without a DB connection.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


BASIC = '66edb525-13d4-45f0-b7a6-c62578f4021c'
PREMIUM = '825696b5-348b-4e84-b71e-d91f21c399a2'

PLACEHOLDER_NAMES = {'premium', 'basic', 'стандартный'}
REQUIRED_TARIFF_IDS = {1, 2, 3}


def build_tariff_audit_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure-function audit over a list of tariff row dicts.

    Each dict must have: id, name, allowed_squads (list[str]), is_active.
    """
    by_id: dict[int, dict] = {r['id']: r for r in rows}
    found_ids = set(by_id.keys())
    missing_ids = sorted(REQUIRED_TARIFF_IDS - found_ids)

    t1 = by_id.get(1)
    t1_squads = set(t1['allowed_squads'] or []) if t1 else set()
    t1_missing_premium = PREMIUM not in t1_squads
    t1_missing_basic = BASIC not in t1_squads

    placeholder_ids = [
        r['id'] for r in rows
        if (r.get('name') or '').strip().lower() in PLACEHOLDER_NAMES
    ]

    all_ok = (
        not missing_ids
        and not t1_missing_premium
        and not t1_missing_basic
        and not placeholder_ids
    )

    return {
        'tariff_count': len(rows),
        'found_ids': sorted(found_ids),
        'missing_tariff_ids': missing_ids,
        'tariff_1_missing_premium_squad': t1_missing_premium,
        'tariff_1_missing_basic_squad': t1_missing_basic,
        'placeholder_name_ids': placeholder_ids,
        'all_ok': all_ok,
        'tariffs': [
            {
                'id': r['id'],
                'name': r.get('name'),
                'is_active': r.get('is_active'),
                'allowed_squads': r.get('allowed_squads') or [],
                'show_in_gift': r.get('show_in_gift'),
                'tier_level': r.get('tier_level'),
                'display_order': r.get('display_order'),
            }
            for r in sorted(rows, key=lambda x: x['id'])
        ],
    }


async def _fetch_tariff_rows(db: AsyncSession) -> list[dict[str, Any]]:
    from app.database.models import Tariff  # local import to avoid side effects in tests

    result = await db.execute(select(Tariff).order_by(Tariff.id))
    tariffs = result.scalars().all()
    return [
        {
            'id': t.id,
            'name': t.name,
            'is_active': t.is_active,
            'allowed_squads': list(t.allowed_squads or []),
            'show_in_gift': t.show_in_gift,
            'tier_level': t.tier_level,
            'display_order': t.display_order,
        }
        for t in tariffs
    ]


async def _run(as_json: bool) -> dict[str, Any]:
    from app.config import settings  # local import to avoid side effects in tests

    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            rows = await _fetch_tariff_rows(session)
    finally:
        await engine.dispose()

    report = build_tariff_audit_report(rows)

    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)

    return report


def _print_report(report: dict[str, Any]) -> None:
    status = '✅ ALL OK' if report['all_ok'] else '❌ ISSUES FOUND'
    print(f'\n=== Tariff Audit Report === {status}')
    print(f"Tariffs in DB: {report['tariff_count']}  (ids: {report['found_ids']})")

    if report['missing_tariff_ids']:
        print(f"  ⚠️  Missing tariff ids: {report['missing_tariff_ids']}")

    if report['tariff_1_missing_premium_squad']:
        print(f'  ⚠️  Tariff #1 missing PREMIUM squad ({PREMIUM})')

    if report['tariff_1_missing_basic_squad']:
        print(f'  ⚠️  Tariff #1 missing BASIC squad ({BASIC})')

    if report['placeholder_name_ids']:
        print(f"  ⚠️  Placeholder names on tariff ids: {report['placeholder_name_ids']}")

    print()
    header = f"{'ID':>4}  {'Name':<20}  {'Active':<6}  {'SiG':<4}  {'Tier':<4}  Squads"
    print(header)
    print('-' * 80)
    for t in report['tariffs']:
        squads_short = ', '.join(
            ('BASIC' if s == BASIC else 'PREMIUM' if s == PREMIUM else s[:8])
            for s in t['allowed_squads']
        )
        print(
            f"{t['id']:>4}  {(t['name'] or ''):<20}  {str(t['is_active']):<6}  "
            f"{str(t['show_in_gift']):<4}  {str(t['tier_level']):<4}  {squads_short}"
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description='Post-migration tariff audit (read-only)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    report = asyncio.run(_run(as_json=args.json))
    sys.exit(0 if report['all_ok'] else 1)


if __name__ == '__main__':
    main()
