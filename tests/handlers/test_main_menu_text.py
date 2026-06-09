"""Tests for main menu text parity and multi-tariff preview cap."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.localization.texts import get_texts


def _make_subscription(sub_id: int, name: str = 'Tariff'):
    return SimpleNamespace(
        id=sub_id,
        tariff=SimpleNamespace(name=name),
        actual_status='active',
        end_date=datetime.now(UTC) + timedelta(days=30),
        is_active=True,
    )


class _TextsStub:
    language = 'en'

    def t(self, key: str, default: str = '', **kwargs) -> str:
        translations = {
            'MAIN_MENU_MULTI_MORE': '… and {count} more',
            'MY_SUB_DEFAULT_NAME': 'Subscription',
            'MY_SUB_STATUS_SUFFIX_UNTIL': ' — until {end_date} ({days} d.)',
            'SUB_STATUS_NONE': '❌ None',
        }
        template = translations.get(key, default)
        if kwargs:
            return template.format(**kwargs)
        return template


@pytest.mark.asyncio
async def test_multi_tariff_status_caps_preview_at_three() -> None:
    from app.handlers.menu import _get_multi_tariff_status

    subscriptions = [_make_subscription(i, f'Tariff {i}') for i in range(5)]
    user = SimpleNamespace(id=1, full_name='Test User')
    db = AsyncMock()
    texts = _TextsStub()

    with patch(
        'app.database.crud.subscription.get_all_subscriptions_by_user_id',
        new_callable=AsyncMock,
        return_value=subscriptions,
    ):
        status_text, _tariff_block = await _get_multi_tariff_status(user, texts, db)

    preview_lines = [line for line in status_text.split('\n') if '<b>' in line]
    assert len(preview_lines) == 3
    assert '… and 2 more' in status_text


def test_fa_main_menu_action_prompt_matches_template() -> None:
    texts = get_texts('fa')
    action_prompt = texts.t('MAIN_MENU_ACTION_PROMPT', '')
    assert action_prompt in texts.MAIN_MENU
