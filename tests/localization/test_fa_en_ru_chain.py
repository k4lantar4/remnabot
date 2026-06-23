"""Static guard: fa users should not see Cyrillic when en has the key."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.localization.texts import Texts, clear_locale_cache

_CYRILLIC = re.compile(r'[А-Яа-яЁё]')
_LOCALES_DIR = Path(__file__).resolve().parents[2] / 'app' / 'localization' / 'locales'


@pytest.fixture(autouse=True)
def clear_cached_locales():
    clear_locale_cache()
    yield
    clear_locale_cache()


def _load_locale(name: str) -> dict[str, str]:
    path = _LOCALES_DIR / f'{name}.json'
    return json.loads(path.read_text(encoding='utf-8'))


def test_en_keys_resolve_before_ru_for_fa_users():
    """Keys present in en but absent in fa must not surface Russian via fallback."""
    fa_keys = set(_load_locale('fa'))
    en_locale = _load_locale('en')
    ru_locale = _load_locale('ru')

    en_only_vs_fa = {k for k in en_locale if k not in fa_keys and k in ru_locale}
    if not en_only_vs_fa:
        pytest.skip('no shared en+ru keys missing from fa to sample')

    texts = Texts('fa')
    cyrillic_from_ru = []
    for key in sorted(en_only_vs_fa):
        value = texts.t(key)
        if isinstance(value, str) and _CYRILLIC.search(value):
            cyrillic_from_ru.append(key)

    assert not cyrillic_from_ru, (
        'fa fallback returned Cyrillic for keys available in en: '
        + ', '.join(cyrillic_from_ru[:10])
    )
