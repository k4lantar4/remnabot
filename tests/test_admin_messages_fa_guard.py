"""Static guards: admin broadcast fa keys must not contain Cyrillic values."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FA_PATH = ROOT / 'app' / 'localization' / 'locales' / 'fa.json'
ADMIN_PY = ROOT / 'app' / 'keyboards' / 'admin.py'

CYRILLIC_RE = re.compile(r'[А-Яа-яЁё]')

_FA = json.loads(FA_PATH.read_text(encoding='utf-8'))
GUARD_PREFIXES = ('ADMIN_MSG_', 'ADMIN_BROADCAST_')


def _guard_keys() -> list[str]:
    return sorted(k for k in _FA if k.startswith(GUARD_PREFIXES))


@pytest.mark.parametrize('key', _guard_keys())
def test_admin_messages_fa_values_have_no_cyrillic(key: str) -> None:
    value = _FA[key]
    assert isinstance(value, str) and value.strip(), f'{key} must be a non-empty string'
    match = CYRILLIC_RE.search(value)
    assert match is None, f'{key} contains Cyrillic: {match.group()!r}'


def test_broadcast_button_toggle_preserves_leading_emoji() -> None:
    """Selected broadcast buttons must keep emoji prefixes (e.g. 💎 خرید سرویس)."""
    source = ADMIN_PY.read_text(encoding='utf-8')
    assert 'removeprefix' in source
    assert 'split(" ", 1)[1]' not in source
