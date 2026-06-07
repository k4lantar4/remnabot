from pathlib import Path

import pytest

from tools.migration.backup import BackupGateError, create_backup, verify_backup_dir


def test_verify_backup_dir_requires_checksums(tmp_path: Path):
    with pytest.raises(BackupGateError, match='SHA256SUMS'):
        verify_backup_dir(tmp_path)


def test_create_backup_writes_checksums(tmp_path: Path, monkeypatch):
    monkeypatch.setattr('tools.migration.backup.MIGRATION_BACKUPS_ROOT', tmp_path / 'backups-root')
    rookari = tmp_path / 'rookari_db.json'
    rookari.write_text('[]', encoding='utf-8')
    xui = tmp_path / 'xui'
    xui.mkdir()
    (xui / 'server14-test.db').write_bytes(b'')

    dest = create_backup(
        rookari_db=rookari,
        xui_backup=xui,
        dest=tmp_path / 'backup',
        include_pg_dump=False,
    )
    assert (dest / 'SHA256SUMS').is_file()
    verify_backup_dir(dest)
