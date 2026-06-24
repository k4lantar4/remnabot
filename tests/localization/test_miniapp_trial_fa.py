"""Miniapp trial message resolves to Persian for fa users."""

from __future__ import annotations

import re

from app.localization.texts import get_texts, clear_locale_cache

_CYRILLIC = re.compile(r'[А-Яа-яЁё]')


def test_miniapp_trial_activated_fa_has_no_cyrillic():
    clear_locale_cache()
    text = get_texts('fa').t('MINIAPP_TRIAL_ACTIVATED', 'Trial activated. Enjoy!')
    assert text
    assert not _CYRILLIC.search(text)
    clear_locale_cache()
