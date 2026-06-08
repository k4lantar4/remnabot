from pathlib import Path

from tools.migration.extract_xui import _candidate_db_paths, resolve_server_db_path


def test_candidate_db_paths_prefers_primary_over_fallback(tmp_path: Path):
    primary = tmp_path / '19-00'
    fallback = tmp_path / '08-00'
    primary.mkdir()
    fallback.mkdir()
    primary_file = primary / 'server37-2026-02-28_19-00.db'
    fallback_file = fallback / 'server37-2026-02-28_08-00.db'
    primary_file.write_bytes(b'sqlite')
    fallback_file.write_bytes(b'sqlite')

    paths = _candidate_db_paths(37, primary=primary, fallback=fallback)
    assert paths[0] == primary_file
    assert fallback_file in paths


def test_resolve_server_db_path_uses_fallback_when_primary_missing(tmp_path: Path):
    primary = tmp_path / '19-00'
    fallback = tmp_path / '08-00'
    primary.mkdir()
    fallback.mkdir()
    (primary / 'server37-2026-02-28_19-00.db').write_bytes(b'')
    fallback_file = fallback / 'server37-2026-02-28_08-00.db'
    fallback_file.write_bytes(b'sqlite')

    resolved = resolve_server_db_path(37, primary=primary, fallback=fallback)
    assert resolved == fallback_file
