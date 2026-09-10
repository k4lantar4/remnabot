"""The locale seeder only needs write access when it actually has something to copy.

``ensure_locale_templates`` copies the baked ru/en/fa templates into ``LOCALES_PATH`` when
they are missing. It probed the directory for write access first, on every start, so a
fully populated, git-tracked ``locales/`` mounted from a root-owned host directory logged
"Locale directory is not writable" (with a traceback) each time although nothing was to be
written.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.localization import loader


def _probe_must_not_run(directory):
    raise AssertionError(f'write probe ran for {directory} although nothing needed copying')


def test_populated_directory_is_not_probed(tmp_path, monkeypatch):
    for code in ('ru', 'en', 'fa'):
        (tmp_path / f'{code}.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(settings, 'LOCALES_PATH', str(tmp_path))
    monkeypatch.setattr(loader, '_directory_is_writable', _probe_must_not_run)

    loader.ensure_locale_templates()

    assert sorted(p.name for p in tmp_path.iterdir()) == ['en.json', 'fa.json', 'ru.json']


def test_missing_locale_is_still_copied(tmp_path, monkeypatch):
    for code in ('ru', 'en'):
        (tmp_path / f'{code}.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(settings, 'LOCALES_PATH', str(tmp_path))

    loader.ensure_locale_templates()

    assert (tmp_path / 'fa.json').read_bytes() == (loader._DEFAULT_LOCALES_DIR / 'fa.json').read_bytes()


def test_empty_directory_is_seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'LOCALES_PATH', str(tmp_path))

    loader.ensure_locale_templates()

    for code in ('ru', 'en', 'fa'):
        assert (tmp_path / f'{code}.json').exists()


@pytest.mark.parametrize('writable', [False])
def test_unwritable_directory_with_missing_locale_still_warns(tmp_path, monkeypatch, writable):
    """The warning stays meaningful: it fires only when a copy is needed and impossible."""
    calls = []
    monkeypatch.setattr(settings, 'LOCALES_PATH', str(tmp_path))
    monkeypatch.setattr(loader, '_directory_is_writable', lambda d: calls.append(d) or writable)

    loader.ensure_locale_templates()

    assert calls == [tmp_path]
    assert not any(tmp_path.iterdir())
