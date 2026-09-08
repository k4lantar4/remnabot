"""M6-T1 G9-strings: FA fallback regression gate.

remnabot has no tests/localization/test_fa_fallback.py; this file is the named
gate. It locks production FA behavior ported in M4-T7:

- Known FA keys resolve to Persian (not Cyrillic).
- Missing FA key → en → ru.
- English digits (0-9) where required: formatters + ported C2C strings.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.localization.loader import clear_locale_cache
from app.localization.texts import Texts, get_texts

_CYRILLIC = re.compile(r'[А-Яа-яЁё]')
_PERSIAN_LETTER = re.compile(r'[\u0600-\u06FF]')
_PERSIAN_DIGIT = re.compile(r'[۰-۹]')
_ASCII_DIGIT = re.compile(r'[0-9]')

_LOCALES_DIR = Path(__file__).resolve().parents[2] / 'app' / 'localization' / 'locales'

# Production-visible keys that must stay Persian after the remnabot port.
_KNOWN_FA = {
    'MAIN_MENU': 'اشتراک',
    'PAYMENT_C2C': 'کارت به کارت',
    'C2C_ENTER_AMOUNT': 'مبلغ شارژ',
    'WELCOME_FALLBACK': 'خوش آمدید',
}


@pytest.fixture(autouse=True)
def clear_cached_locales():
    clear_locale_cache()
    yield
    clear_locale_cache()


def _patch_locale_dirs(monkeypatch, tmp_path):
    fa_dir = tmp_path / 'locales'
    fa_dir.mkdir()
    monkeypatch.setattr('app.localization.loader._DEFAULT_LOCALES_DIR', fa_dir)
    monkeypatch.setattr('app.localization.loader._resolve_user_locales_dir', lambda: fa_dir)
    clear_locale_cache()
    return fa_dir


def test_known_fa_keys_resolve_to_persian():
    texts = get_texts('fa')
    for key, needle in _KNOWN_FA.items():
        value = texts.t(key)
        assert isinstance(value, str), key
        assert needle in value, f'{key} missing Persian needle {needle!r}: {value!r}'
        assert _PERSIAN_LETTER.search(value), f'{key} has no Persian letters: {value!r}'
        assert not _CYRILLIC.search(value), f'{key} leaked Cyrillic: {value!r}'


def test_missing_fa_key_falls_back_en_then_ru(monkeypatch, tmp_path):
    fa_dir = _patch_locale_dirs(monkeypatch, tmp_path)
    (fa_dir / 'fa.json').write_text(
        '{"KNOWN_FA_KEY": "فارسی"}',
        encoding='utf-8',
    )
    (fa_dir / 'en.json').write_text(
        '{"ONLY_IN_EN": "English only", "IN_BOTH_EN_RU": "English wins"}',
        encoding='utf-8',
    )
    (fa_dir / 'ru.json').write_text(
        '{"ONLY_IN_RU": "Только RU", "IN_BOTH_EN_RU": "Russian loses"}',
        encoding='utf-8',
    )

    texts = Texts('fa')
    assert texts.t('KNOWN_FA_KEY') == 'فارسی'
    assert texts.t('ONLY_IN_EN') == 'English only'
    assert texts.t('IN_BOTH_EN_RU') == 'English wins'
    assert texts.t('ONLY_IN_RU') == 'Только RU'
    assert texts.t('TOTALLY_MISSING') == 'TOTALLY_MISSING'


def test_format_price_and_balance_use_english_digits():
    texts = get_texts('fa')
    price = texts.format_price(12_015_200)
    balance = texts.format_balance(120_152)

    for label, value in (('format_price', price), ('format_balance', balance)):
        assert 'تومان' in value, f'{label} missing تومان: {value!r}'
        assert _ASCII_DIGIT.search(value), f'{label} missing English digits: {value!r}'
        assert not _PERSIAN_DIGIT.search(value), f'{label} used Persian digits: {value!r}'
        assert ',' in value, f'{label} missing fa thousands grouping: {value!r}'


def test_ported_c2c_fa_keys_use_english_digits():
    fa = json.loads((_LOCALES_DIR / 'fa.json').read_text(encoding='utf-8'))
    offenders = []
    for key, value in fa.items():
        if not (key.startswith('C2C_') or key == 'PAYMENT_C2C'):
            continue
        if isinstance(value, str) and _PERSIAN_DIGIT.search(value):
            offenders.append(f'{key}: {value[:80]}')
    assert not offenders, (
        'Persian digits in ported C2C fa keys (amounts must use 0-9):\n'
        + '\n'.join(offenders)
    )
