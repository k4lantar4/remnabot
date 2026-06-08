from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from tools.migration.config import MIGRATION_BACKUPS_ROOT, ROOKARI_DB_PATH, XUI_BACKUP_DIR_FALLBACK, XUI_BACKUP_DIR_PRIMARY


class BackupGateError(RuntimeError):
    pass


def verify_backup_dir(path: Path) -> None:
    if not path.is_dir():
        raise BackupGateError(f'backup dir not found: {path}')
    checksums = path / 'SHA256SUMS'
    if not checksums.is_file():
        raise BackupGateError(f'SHA256SUMS missing in {path}')


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def create_backup(
    *,
    rookari_db: Path = ROOKARI_DB_PATH,
    xui_backup: Path | None = None,
    dest: Path | None = None,
    include_pg_dump: bool = True,
) -> Path:
    ts = datetime.now(UTC).strftime('%Y%m%d-%H%M%S')
    if dest is None:
        dest = MIGRATION_BACKUPS_ROOT / ts
    dest.mkdir(parents=True, exist_ok=True)

    if rookari_db.is_file():
        shutil.copy2(rookari_db, dest / rookari_db.name)
    primary_dir = xui_backup if xui_backup is not None else XUI_BACKUP_DIR_PRIMARY
    if primary_dir.is_dir():
        shutil.copytree(primary_dir, dest / 'xui_bcp_primary', dirs_exist_ok=True)
    if xui_backup is None and XUI_BACKUP_DIR_FALLBACK.is_dir():
        shutil.copytree(XUI_BACKUP_DIR_FALLBACK, dest / 'xui_bcp_fallback', dirs_exist_ok=True)

    env_path = Path('/opt/bot-remnawave/.env')
    if env_path.is_file():
        shutil.copy2(env_path, dest / 'bot.env.snapshot')

    if include_pg_dump:
        db_url = os.environ.get('DATABASE_URL', '')
        if db_url.startswith('postgresql'):
            try:
                result = subprocess.run(
                    ['pg_dump', db_url.replace('+asyncpg', '')],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                (dest / 'pg_remnawave_bot.sql.gz').write_bytes(result.stdout)
            except (FileNotFoundError, subprocess.CalledProcessError):
                (dest / 'pg_dump.skipped').write_text('pg_dump unavailable\n', encoding='utf-8')

    lines: list[str] = []
    for item in sorted(dest.iterdir()):
        if item.name == 'SHA256SUMS':
            continue
        if item.is_file():
            lines.append(f'{_sha256_file(item)}  {item.name}\n')

    (dest / 'SHA256SUMS').write_text(''.join(lines), encoding='utf-8')
    MIGRATION_BACKUPS_ROOT.mkdir(parents=True, exist_ok=True)
    (MIGRATION_BACKUPS_ROOT / 'LATEST').write_text(str(dest) + '\n', encoding='utf-8')
    return dest


def require_backup_gate() -> Path:
    raw = os.environ.get('MIGRATION_BACKUP_DIR', '').strip()
    if not raw:
        raise BackupGateError('MIGRATION_BACKUP_DIR is required for --execute')
    path = Path(raw)
    verify_backup_dir(path)
    return path
