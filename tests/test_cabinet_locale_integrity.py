"""Cabinet locale guards — missing fa keys fall back to Russian in the UI."""

import json
import re
from pathlib import Path

import pytest

CABINET_LOCALES = Path(__file__).resolve().parents[1] / 'cabinet' / 'src' / 'locales'
CYRILLIC_RE = re.compile(r'[А-Яа-яЁё]')
# User-visible namespaces — admin.* excluded from Cyrillic scan
USER_PREFIXES = (
    'subscription.', 'gift.', 'dashboard.', 'notifications.', 'resetPassword.',
    'balance.', 'support.', 'landing.', 'wheel.', 'promo.', 'news.', 'banSystem.',
)


def _flatten(d: dict, prefix: str = '') -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        key = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


@pytest.fixture(scope='module')
def cabinet_locales():
    ru = json.loads((CABINET_LOCALES / 'ru.json').read_text(encoding='utf-8'))
    fa = json.loads((CABINET_LOCALES / 'fa.json').read_text(encoding='utf-8'))
    return {'ru': _flatten(ru), 'fa': _flatten(fa)}


def test_cabinet_fa_has_all_ru_keys(cabinet_locales):
    ru_keys = set(cabinet_locales['ru'])
    fa_keys = set(cabinet_locales['fa'])
    missing = sorted(ru_keys - fa_keys)
    assert not missing, (
        f'fa.json missing {len(missing)} keys vs ru (UI falls back to Russian). '
        f'First 20: {missing[:20]}'
    )


def test_cabinet_user_fa_has_no_cyrillic(cabinet_locales):
    problems = []
    for key, val in cabinet_locales['fa'].items():
        if key.startswith('admin.'):
            continue
        if not any(key.startswith(p) for p in USER_PREFIXES):
            continue
        if isinstance(val, str) and CYRILLIC_RE.search(val):
            problems.append(f'{key}: {val[:60]}')
    assert not problems, 'Cyrillic in user-facing cabinet fa:\n' + '\n'.join(problems[:20])
