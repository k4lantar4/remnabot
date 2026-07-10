"""Guard fa subscription delivery terminology: config, not link."""

from __future__ import annotations

import json
import re
from pathlib import Path

_CYRILLIC = re.compile(r'[А-Яа-яЁё]')
_LOCALE_PATH = Path(__file__).resolve().parents[2] / 'app' / 'localization' / 'locales' / 'fa.json'

_SCOPED_CONFIG_KEYS = (
    'CONNECT_CHOOSER_BTN_SHARE',
    'MY_SUB_BTN_CONNECT_LINK',
    'MY_SUB_DETAIL_CONNECT_HINT',
    'MY_SUB_DETAIL_FIRST_CONNECT',
    'MY_SUB_DETAIL_ONBOARDING',
    'POST_PURCHASE_ONBOARDING',
    'SIMPLE_SUB_PAYMENT_CONNECT_HINT',
    'SUBSCRIPTION_IMPORT_LINK_SECTION',
    'TARIFF_CHANGE_SUCCESS',
    'TARIFF_DAILY_SUCCESS',
    'TARIFF_INSTANT_SWITCH_DAILY_SUCCESS',
    'TARIFF_INSTANT_SWITCH_SUCCESS',
    'TARIFF_PURCHASE_SUCCESS',
    'TARIFF_RENEW_SUCCESS',
    'TARIFF_SWITCH_DAILY_SUCCESS',
    'TARIFF_SWITCH_SUCCESS',
)


def _load_fa_locale() -> dict[str, str]:
    return json.loads(_LOCALE_PATH.read_text(encoding='utf-8'))


def test_scoped_delivery_keys_use_config_terminology():
    fa = _load_fa_locale()
    missing = [key for key in _SCOPED_CONFIG_KEYS if key not in fa]
    assert not missing, f'missing fa keys: {missing}'

    for key in _SCOPED_CONFIG_KEYS:
        value = fa[key]
        assert 'کانفیگ' in value, f'{key} should mention کانفیگ'
        assert 'لینک' not in value, f'{key} should not mention لینک'
        assert not _CYRILLIC.search(value), f'{key} should not contain Cyrillic text'
