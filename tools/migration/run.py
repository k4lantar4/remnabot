from __future__ import annotations

import argparse
import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

from tools.migration.audit_manifest import write_manifest
from tools.migration.backup import create_backup, require_backup_gate
from tools.migration.config import MIGRATION_OUTPUT_DIR, load_squad_uuids
from tools.migration.extract_rookari import parse_rookari_tables
from tools.migration.extract_xui import extract_all_xui_clients
from tools.migration.join_filter import build_migration_cohorts
from tools.migration.load_postgres import load_migration_data
from tools.migration.sync_remnawave import sync_all
from tools.migration.validate import validate_migration


@asynccontextmanager
async def get_db_session():
    engine = create_async_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _serialize_cohorts(subscribers, campaign_users, rejects):
    return {
        'subscribers': [asdict(s) for s in subscribers],
        'campaign_users': [asdict(c) for c in campaign_users],
        'rejects': [asdict(r) for r in rejects],
        'counts': {
            'subscriber_users': len({s.telegram_id for s in subscribers}),
            'subscriber_subscriptions': len(subscribers),
            'campaign_users': len(campaign_users),
            'rejects': len(rejects),
        },
    }


def cmd_backup(args: argparse.Namespace) -> None:
    dest = create_backup(dest=args.dest, include_pg_dump=not args.skip_pg_dump)
    print(dest)


async def cmd_extract(out_dir: Path) -> dict:
    migration_run = datetime.now(UTC)
    clients = extract_all_xui_clients()
    users, stats, sellers = parse_rookari_tables()
    subscribers, campaign_users, rejects = build_migration_cohorts(
        clients,
        users,
        stats,
        sellers,
        migration_run=migration_run,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    payload = _serialize_cohorts(subscribers, campaign_users, rejects)
    (out_dir / 'subscribers.json').write_text(
        json.dumps(payload['subscribers'], indent=2, default=str),
        encoding='utf-8',
    )
    (out_dir / 'campaign_users.json').write_text(
        json.dumps(payload['campaign_users'], indent=2, default=str),
        encoding='utf-8',
    )
    (out_dir / 'rejects.json').write_text(
        json.dumps(payload['rejects'], indent=2, default=str),
        encoding='utf-8',
    )
    write_manifest(
        out_dir / 'migration_manifest.json',
        subscribers,
        campaign_users,
        rejects,
        migration_run=migration_run,
    )
    print(json.dumps(payload['counts'], indent=2))
    return payload['counts']


async def cmd_load(execute: bool) -> dict:
    if execute:
        require_backup_gate()

    clients = extract_all_xui_clients()
    users, stats, sellers = parse_rookari_tables()
    subscribers, campaign_users, rejects = build_migration_cohorts(clients, users, stats, sellers)

    squad_uuids: dict[str, str] = {}
    try:
        squad_uuids = load_squad_uuids()
    except FileNotFoundError:
        if execute:
            raise

    async with get_db_session() as db:
        result = await load_migration_data(
            db,
            subscribers,
            campaign_users,
            sellers,
            squad_uuids,
            dry_run=not execute,
        )
    print(json.dumps(result, indent=2))
    return result


async def cmd_sync(execute: bool) -> dict:
    manifest = MIGRATION_OUTPUT_DIR / 'migration_manifest.json'
    async with get_db_session() as db:
        result = await sync_all(db, dry_run=not execute, manifest_path=manifest)
    print(json.dumps(result, indent=2))
    return result


async def cmd_validate() -> dict:
    async with get_db_session() as db:
        report = await validate_migration(db)
    print(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description='Rookari migration tool')
    sub = parser.add_subparsers(dest='cmd', required=True)

    backup_p = sub.add_parser('backup', help='Snapshot rookari_db, xui bcp, optional pg_dump')
    backup_p.add_argument('--dest', type=Path, default=None, help='Backup destination directory')
    backup_p.add_argument('--skip-pg-dump', action='store_true')

    extract_p = sub.add_parser('extract', help='Build subscriber/campaign/reject cohorts')
    extract_p.add_argument('-o', '--output', type=Path, default=MIGRATION_OUTPUT_DIR)

    load_p = sub.add_parser('load', help='Load cohorts into PostgreSQL')
    load_p.add_argument('--execute', action='store_true', help='Requires MIGRATION_BACKUP_DIR')

    sync_p = sub.add_parser('sync', help='Sync subscriptions to Remnawave panel')
    sync_p.add_argument('--execute', action='store_true')

    sub.add_parser('validate', help='Post-migration validation checks')

    args = parser.parse_args()

    if args.cmd == 'backup':
        cmd_backup(args)
    elif args.cmd == 'extract':
        asyncio.run(cmd_extract(args.output))
    elif args.cmd == 'load':
        asyncio.run(cmd_load(args.execute))
    elif args.cmd == 'sync':
        asyncio.run(cmd_sync(args.execute))
    elif args.cmd == 'validate':
        asyncio.run(cmd_validate())


if __name__ == '__main__':
    main()
