"""One-shot post-migration tariff configuration.

SAFE by default: dry-run only.  Pass --execute --i-understand to write to DB.

Usage:
    python -m tools.tariff_post_migration_apply           # dry-run
    python -m tools.tariff_post_migration_apply --execute --i-understand

Target DB state:
    id=1  استاندارد  both squads  show_in_gift=True  tier=1  order=0
    id=2  پریمیوم    premium only  show_in_gift=False tier=2  order=2
    id=3  پایه       basic only    show_in_gift=False tier=1  order=1
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any


BASIC = '66edb525-13d4-45f0-b7a6-c62578f4021c'
PREMIUM = '825696b5-348b-4e84-b71e-d91f21c399a2'

TARGETS: dict[int, dict[str, Any]] = {
    1: {
        'name': 'استاندارد',
        'allowed_squads': [BASIC, PREMIUM],
        'show_in_gift': True,
        'display_order': 0,
        'tier_level': 1,
    },
    2: {
        'name': 'پریمیوم',
        'allowed_squads': [PREMIUM],
        'show_in_gift': False,
        'display_order': 2,
        'tier_level': 2,
    },
    3: {
        'name': 'پایه',
        'allowed_squads': [BASIC],
        'show_in_gift': False,
        'display_order': 1,
        'tier_level': 1,
    },
}


def build_tariff_updates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pure function: given current tariff rows, return patch dicts.

    Each patch dict contains the full target state plus a ``changed`` bool
    indicating whether any field differs from the current row.
    """
    by_id = {r['id']: r for r in rows}
    patches = []
    for tariff_id, target in TARGETS.items():
        current = by_id.get(tariff_id)
        patch: dict[str, Any] = {'id': tariff_id, **target}

        if current is None:
            patch['changed'] = True
            patch['error'] = f'Tariff id={tariff_id} not found in DB'
        else:
            changed = (
                current.get('name') != target['name']
                or sorted(current.get('allowed_squads') or []) != sorted(target['allowed_squads'])
                or current.get('show_in_gift') != target['show_in_gift']
                or current.get('display_order') != target['display_order']
                or current.get('tier_level') != target['tier_level']
            )
            patch['changed'] = changed

        patches.append(patch)
    return patches


async def _fetch_tariff_rows(db) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from app.database.models import Tariff

    result = await db.execute(select(Tariff).where(Tariff.id.in_(TARGETS.keys())).order_by(Tariff.id))
    tariffs = result.scalars().all()
    return [
        {
            'id': t.id,
            'name': t.name,
            'allowed_squads': list(t.allowed_squads or []),
            'show_in_gift': t.show_in_gift,
            'tier_level': t.tier_level,
            'display_order': t.display_order,
        }
        for t in tariffs
    ]


async def _apply_patches(db, patches: list[dict[str, Any]]) -> None:
    from sqlalchemy import select

    from app.database.models import Tariff

    for patch in patches:
        if patch.get('error'):
            print(f"  ❌ SKIP id={patch['id']}: {patch['error']}")
            continue
        if not patch['changed']:
            print(f"  ✅ id={patch['id']} already correct — skip")
            continue

        result = await db.execute(select(Tariff).where(Tariff.id == patch['id']))
        tariff = result.scalar_one_or_none()
        if tariff is None:
            print(f"  ❌ SKIP id={patch['id']}: not found during apply")
            continue

        tariff.name = patch['name']
        tariff.allowed_squads = patch['allowed_squads']
        tariff.show_in_gift = patch['show_in_gift']
        tariff.display_order = patch['display_order']
        tariff.tier_level = patch['tier_level']
        print(f"  ✏️  id={patch['id']} → name={patch['name']!r}, squads={[_squad_label(s) for s in patch['allowed_squads']]}, show_in_gift={patch['show_in_gift']}, tier={patch['tier_level']}")

    await db.commit()


def _squad_label(uuid: str) -> str:
    if uuid == BASIC:
        return 'BASIC'
    if uuid == PREMIUM:
        return 'PREMIUM'
    return uuid[:8]


def _print_dry_run(patches: list[dict[str, Any]]) -> None:
    print('\n=== DRY RUN — no DB changes ===')
    for p in patches:
        marker = '✏️ ' if p['changed'] else '✅'
        squads_label = [_squad_label(s) for s in p['allowed_squads']]
        print(
            f"  {marker} id={p['id']}: name={p['name']!r}  squads={squads_label}"
            f"  show_in_gift={p['show_in_gift']}  tier={p['tier_level']}  order={p['display_order']}"
            + (f"  [NO CHANGE]" if not p['changed'] else f"  [WILL UPDATE]")
            + (f"  ⚠️  {p['error']}" if p.get('error') else '')
        )
    changed = [p for p in patches if p['changed']]
    print(f"\n{len(changed)}/{len(patches)} tariff(s) need updating.")
    if changed:
        print("Re-run with --execute --i-understand to apply.\n")
    else:
        print("Nothing to do.\n")


async def _run(execute: bool) -> bool:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings

    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            rows = await _fetch_tariff_rows(session)
            patches = build_tariff_updates(rows)

            if not execute:
                _print_dry_run(patches)
            else:
                print('\n=== EXECUTING tariff updates ===')
                await _apply_patches(session, patches)
                print('Done. Re-run audit to verify.')
    finally:
        await engine.dispose()

    return all(not p.get('error') for p in patches)


def main() -> None:
    parser = argparse.ArgumentParser(description='Post-migration tariff apply (dry-run by default)')
    parser.add_argument('--execute', action='store_true', help='Apply changes to DB (requires --i-understand)')
    parser.add_argument('--i-understand', dest='confirmed', action='store_true', help='Confirm destructive operation')
    args = parser.parse_args()

    if args.execute and not args.confirmed:
        print('ERROR: --execute requires --i-understand flag to confirm DB writes.')
        sys.exit(2)

    ok = asyncio.run(_run(execute=args.execute))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
