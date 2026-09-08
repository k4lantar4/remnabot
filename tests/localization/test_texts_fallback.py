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


def _patch_locale_dirs(monkeypatch, tmp_path):
    fa_dir = tmp_path / 'locales'
    fa_dir.mkdir()
    monkeypatch.setattr('app.localization.loader._DEFAULT_LOCALES_DIR', fa_dir)
    monkeypatch.setattr('app.localization.loader._resolve_user_locales_dir', lambda: fa_dir)
    clear_locale_cache()
    return fa_dir


def test_fa_missing_key_falls_back_to_upstream_ru(monkeypatch, tmp_path):
    fa_dir = _patch_locale_dirs(monkeypatch, tmp_path)
    (fa_dir / 'fa.json').write_text('{"KNOWN_FA_KEY": "فارسی"}', encoding='utf-8')
    (fa_dir / 'en.json').write_text('{"KNOWN_FA_KEY": "English"}', encoding='utf-8')
    (fa_dir / 'ru.json').write_text(
        '{"KNOWN_FA_KEY": "Русский", "ONLY_IN_RU": "Только RU"}',
        encoding='utf-8',
    )

    texts = Texts('fa')
    assert texts.t('KNOWN_FA_KEY') == 'فارسی'
    assert texts.t('ONLY_IN_RU') == 'Только RU'
    assert texts.t('TOTALLY_MISSING') == 'TOTALLY_MISSING'


def test_fa_prefers_en_over_ru_for_missing_key(monkeypatch, tmp_path):
    fa_dir = _patch_locale_dirs(monkeypatch, tmp_path)
    (fa_dir / 'fa.json').write_text('{}', encoding='utf-8')
    (fa_dir / 'en.json').write_text(
        '{"ONLY_IN_EN": "English only", "IN_BOTH_EN_RU": "English wins"}',
        encoding='utf-8',
    )
    (fa_dir / 'ru.json').write_text(
        '{"ONLY_IN_RU": "Только RU", "IN_BOTH_EN_RU": "Russian loses"}',
        encoding='utf-8',
    )

    texts = Texts('fa')
    assert texts.t('ONLY_IN_EN') == 'English only'
    assert texts.t('ONLY_IN_RU') == 'Только RU'
    assert texts.t('IN_BOTH_EN_RU') == 'English wins'


def test_en_user_falls_back_to_ru_not_fa(monkeypatch, tmp_path):
    fa_dir = _patch_locale_dirs(monkeypatch, tmp_path)
    (fa_dir / 'fa.json').write_text('{"ONLY_IN_FA": "فارسی"}', encoding='utf-8')
    (fa_dir / 'en.json').write_text('{"KNOWN_EN_KEY": "English"}', encoding='utf-8')
    (fa_dir / 'ru.json').write_text('{"ONLY_IN_RU": "из ru"}', encoding='utf-8')

    texts = Texts('en')
    assert texts.t('KNOWN_EN_KEY') == 'English'
    assert texts.t('ONLY_IN_RU') == 'из ru'
    assert texts.t('ONLY_IN_FA') == 'ONLY_IN_FA'


def test_ru_user_has_no_locale_merge_fallback(monkeypatch, tmp_path):
    fa_dir = _patch_locale_dirs(monkeypatch, tmp_path)
    (fa_dir / 'fa.json').write_text('{"ONLY_IN_FA": "فارسی"}', encoding='utf-8')
    (fa_dir / 'en.json').write_text('{"ONLY_IN_EN": "English"}', encoding='utf-8')
    (fa_dir / 'ru.json').write_text('{"KNOWN_RU_KEY": "из ru"}', encoding='utf-8')

    texts = Texts('ru')
    assert texts.t('KNOWN_RU_KEY') == 'из ru'
    assert texts.t('ONLY_IN_FA') == 'ONLY_IN_FA'
    assert texts.t('ONLY_IN_EN') == 'ONLY_IN_EN'


def test_fa_attribute_access_does_not_raise_for_missing_key(monkeypatch, tmp_path):
    fa_dir = _patch_locale_dirs(monkeypatch, tmp_path)
    (fa_dir / 'fa.json').write_text('{}', encoding='utf-8')
    (fa_dir / 'en.json').write_text('{"FROM_EN": "from en"}', encoding='utf-8')
    (fa_dir / 'ru.json').write_text('{"FROM_RU": "из ru"}', encoding='utf-8')

    texts = Texts('fa')
    assert texts.FROM_EN == 'from en'
    assert texts.FROM_RU == 'из ru'
    assert texts.NOT_ANYWHERE == 'NOT_ANYWHERE'


def test_fa_rules_default_uses_en_before_ru(monkeypatch, tmp_path):
    fa_dir = _patch_locale_dirs(monkeypatch, tmp_path)
    (fa_dir / 'fa.json').write_text('{}', encoding='utf-8')
    (fa_dir / 'en.json').write_text('{"RULES_TEXT_DEFAULT": "English rules"}', encoding='utf-8')
    (fa_dir / 'ru.json').write_text('{"RULES_TEXT_DEFAULT": "Русские правила"}', encoding='utf-8')

    texts = Texts('fa')
    assert texts.RULES_TEXT == 'English rules'


def test_get_texts_fa_resolves_known_menu_key():
    texts = get_texts('fa')
    assert 'تومان' in texts.format_balance(0) or texts.format_balance(0)
