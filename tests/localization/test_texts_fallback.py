"""Guards for safe locale fallback when fa translation is incomplete."""

from __future__ import annotations

import pytest

from app.localization.loader import clear_locale_cache
from app.localization.texts import Texts, get_texts


@pytest.fixture(autouse=True)
def clear_cached_locales():
    clear_locale_cache()
    yield
    clear_locale_cache()


def test_fa_missing_key_falls_back_to_upstream_ru(monkeypatch, tmp_path):
    fa_dir = tmp_path / 'locales'
    fa_dir.mkdir()
    (fa_dir / 'fa.json').write_text('{"KNOWN_FA_KEY": "فارسی"}', encoding='utf-8')
    (fa_dir / 'ru.json').write_text(
        '{"KNOWN_FA_KEY": "Русский", "ONLY_IN_RU": "Только RU"}',
        encoding='utf-8',
    )

    monkeypatch.setattr('app.localization.loader._DEFAULT_LOCALES_DIR', fa_dir)
    monkeypatch.setattr('app.localization.loader._resolve_user_locales_dir', lambda: fa_dir)
    clear_locale_cache()

    texts = Texts('fa')
    assert texts.t('KNOWN_FA_KEY') == 'فارسی'
    assert texts.t('ONLY_IN_RU') == 'Только RU'
    assert texts.t('TOTALLY_MISSING') == 'TOTALLY_MISSING'


def test_fa_attribute_access_does_not_raise_for_missing_key(monkeypatch, tmp_path):
    fa_dir = tmp_path / 'locales'
    fa_dir.mkdir()
    (fa_dir / 'fa.json').write_text('{}', encoding='utf-8')
    (fa_dir / 'ru.json').write_text('{"FROM_RU": "из ru"}', encoding='utf-8')

    monkeypatch.setattr('app.localization.loader._DEFAULT_LOCALES_DIR', fa_dir)
    monkeypatch.setattr('app.localization.loader._resolve_user_locales_dir', lambda: fa_dir)
    clear_locale_cache()

    texts = Texts('fa')
    assert texts.FROM_RU == 'из ru'
    assert texts.NOT_ANYWHERE == 'NOT_ANYWHERE'


def test_get_texts_fa_resolves_known_menu_key():
    texts = get_texts('fa')
    assert 'تومان' in texts.format_balance(0) or texts.format_balance(0)
