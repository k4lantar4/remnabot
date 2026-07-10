"""Static guards for purchase-connect UX: fa keys and callback routing."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FA_PATH = ROOT / 'app' / 'localization' / 'locales' / 'fa.json'
PURCHASE_PATH = ROOT / 'app' / 'handlers' / 'subscription' / 'purchase.py'

CYRILLIC_RE = re.compile(r'[А-Яа-яЁё]')

CONNECT_CHOOSER_KEYS = (
    'CONNECT_CHOOSER_TITLE',
    'CONNECT_CHOOSER_BTN_SELF',
    'CONNECT_CHOOSER_BTN_CONFIG',
    'CONNECT_CONFIG_TITLE',
    'CONNECT_CONFIG_QR_HINT',
)

CONNECT_SHARE_KEYS = (
    'CONNECT_SHARE_TITLE',
    'CONNECT_SHARE_LINK_BLOCK',
    'CONNECT_SHARE_NOT_BOT_HINT',
    'CONNECT_SHARE_FORWARD_TEMPLATE',
    'CONNECT_SHARE_BTN_OPEN_BROWSER',
)

CONNECT_SELF_KEYS = ('CONNECT_SELF_TITLE',)

NEW_CONNECT_KEYS = CONNECT_CHOOSER_KEYS + CONNECT_SHARE_KEYS + CONNECT_SELF_KEYS

_FA = json.loads(FA_PATH.read_text(encoding='utf-8'))


@pytest.mark.parametrize('key', NEW_CONNECT_KEYS)
def test_connect_chooser_fa_keys_exist(key: str) -> None:
    assert key in _FA, f'Missing fa.json key: {key}'
    assert isinstance(_FA[key], str) and _FA[key].strip(), f'{key} must be a non-empty string'


def test_connect_share_not_bot_hint_present() -> None:
    assert 'CONNECT_SHARE_NOT_BOT_HINT' in _FA
    assert _FA['CONNECT_SHARE_NOT_BOT_HINT'].strip()


def test_subscription_connect_miniapp_message_shortened() -> None:
    """Dual-path essay removed — must not mention both miniapp and panel direct."""
    value = _FA['SUBSCRIPTION_CONNECT_MINIAPP_MESSAGE']
    has_miniapp = 'مینی‌اپ' in value
    has_panel_direct = 'لینک مستقیم پنل' in value
    assert not (has_miniapp and has_panel_direct), (
        'SUBSCRIPTION_CONNECT_MINIAPP_MESSAGE still contains the old dual-path essay'
    )


@pytest.mark.parametrize('key', NEW_CONNECT_KEYS)
def test_new_connect_keys_have_no_cyrillic(key: str) -> None:
    value = _FA[key]
    match = CYRILLIC_RE.search(value)
    assert match is None, f'{key} contains Cyrillic: {match.group()!r}'


def test_purchase_py_registers_connect_callback_paths() -> None:
    source = PURCHASE_PATH.read_text(encoding='utf-8')
    assert "F.data.startswith('sl_self:')" in source, (
        'purchase.py must register sl_self: callbacks for connect chooser self path'
    )
    assert "F.data.startswith('sl_config:')" in source, (
        'purchase.py must register sl_config: callbacks for config QR delivery'
    )
