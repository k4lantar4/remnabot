from __future__ import annotations

import json
import os
from pathlib import Path

ROOKARI_DB_PATH = Path('/opt/rookari_db.json')
XUI_BACKUP_DIR_PRIMARY = Path('/opt/old_bot/bcp/2026-02-28_19-00')
XUI_BACKUP_DIR_FALLBACK = Path('/opt/old_bot/bcp/2026-02-28_08-00')
# Primary evening backup; extract_xui falls back to morning folder per server when needed.
XUI_BACKUP_DIR = XUI_BACKUP_DIR_PRIMARY
SQUAD_UUIDS_PATH = Path(__file__).parent / 'squad_uuids.json'
MIGRATION_BACKUPS_ROOT = Path('/opt/migration-backups')
MIGRATION_OUTPUT_DIR = Path('/tmp/migration-output')

OLD_SERVER_TO_SQUAD_KEY: dict[int, str] = {
    11: 'merged-small',
    17: 'merged-small',
    40: 'merged-small',
    46: 'merged-small',
    14: 's3',
    18: 's4',
    19: 's5',
    22: 's5-alt',
    24: 's10',
    30: 's8',
    37: 's4',
    57: 's100',
}

SERVER_VIP: dict[int, int] = {
    11: 20,
    14: 20,
    17: 1,
    18: 20,
    19: 20,
    22: 20,
    24: 20,
    30: 20,
    40: 1,
    46: 1,
    37: 20,
    57: 20,
}

SKIP_SERVER_IDS = {56}
BATCH_SIZE = 500
REMNAWAVE_CONCURRENCY = 8


def squad_key_for_server(server_id: int) -> str:
    if server_id in SKIP_SERVER_IDS:
        raise ValueError(f'server {server_id} is skipped')
    key = OLD_SERVER_TO_SQUAD_KEY.get(server_id)
    if not key:
        raise ValueError(f'no squad mapping for server {server_id}')
    return key


def vip_to_tariff_id(vip: int) -> int:
    return 3 if vip == 1 else 2


def load_squad_uuids() -> dict[str, str]:
    path = SQUAD_UUIDS_PATH
    if not path.is_file():
        example = Path(__file__).parent / 'squad_uuids.json.example'
        if example.is_file():
            path = example
        else:
            return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    return {k: v for k, v in data.items() if not k.startswith('_')}


def squad_uuid_for_server(server_id: int) -> str:
    key = squad_key_for_server(server_id)
    uuids = load_squad_uuids()
    if key not in uuids:
        raise KeyError(f'squad key {key!r} missing from squad_uuids.json')
    return uuids[key]


def get_migration_backup_dir() -> Path | None:
    raw = os.environ.get('MIGRATION_BACKUP_DIR', '').strip()
    return Path(raw) if raw else None


def backup_anchor_iso() -> str:
    from tools.migration.proration import BACKUP_ANCHOR
    return BACKUP_ANCHOR.isoformat().replace('+00:00', 'Z')


def migration_backup_dir() -> Path | None:
    return get_migration_backup_dir()
