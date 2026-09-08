"""My Subscriptions must paginate; dumping every row overflows Telegram captions.

M6-T5: admin 1713374557 has 116 subscriptions. show_my_subscriptions sent them
all into a logo-mode photo caption → TelegramBadRequest message/caption too long.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.handlers.subscription.my_subscriptions import (
    MY_SUBS_PAGE_SIZE,
    _build_subscription_detail_keyboard,
    _build_subscriptions_keyboard,
    _format_subscription_line,
    paginate_items,
    parse_my_subs_page,
    receive_my_subs_search,
)
from app.utils.subscription_list_display import format_subscription_list_line


def _fake_sub(i: int):
    return SimpleNamespace(
        id=i,
        tariff=SimpleNamespace(name=f'Tariff {i}'),
        actual_status='active',
        traffic_limit_gb=10,
        traffic_used_gb=1.0,
        device_limit=1,
        end_date=datetime(2026, 12, 1, tzinfo=UTC),
    )


def test_parse_my_subs_page_defaults_and_ms_pg() -> None:
    assert parse_my_subs_page('my_subscriptions') == 1
    assert parse_my_subs_page('menu_subscription') == 1
    assert parse_my_subs_page('ms_pg:3') == 3
    assert parse_my_subs_page('ms_pg:0') == 1
    assert parse_my_subs_page('ms_pg:nope') == 1


def test_paginate_116_subscriptions_fits_page_size() -> None:
    items = [_fake_sub(i) for i in range(116)]
    page_items, page, total_pages = paginate_items(items, 1, MY_SUBS_PAGE_SIZE)
    assert page == 1
    assert total_pages == 24
    assert len(page_items) == MY_SUBS_PAGE_SIZE
    last, last_page, _ = paginate_items(items, 99, MY_SUBS_PAGE_SIZE)
    assert last_page == 24
    assert len(last) == 1


def test_list_source_has_no_hardcoded_cyrillic() -> None:
    src = Path('app/handlers/subscription/my_subscriptions.py').read_text(encoding='utf-8')
    for needle in ('Устройства', 'Мои подписки', 'Трафик:', 'Назад'):
        assert needle not in src, needle


def test_page_caption_uses_helper_and_fits() -> None:
    items = [_fake_sub(i) for i in range(5)]
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)

    class T:
        language = 'fa'

        def t(self, key, default=None):
            return default or key

    lines = ['title\n']
    for idx, sub in enumerate(items, 1):
        lines.append(format_subscription_list_line(sub, idx, T(), 'fa', user))
    assert len('\n'.join(lines)) <= 1024


def test_page_caption_fits_telegram_limit() -> None:
    items = [_fake_sub(i) for i in range(116)]
    page_items, _, total_pages = paginate_items(items, 1, MY_SUBS_PAGE_SIZE)
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)

    class T:
        language = 'fa'

        def t(self, key, default=None):
            return default or key

    title = T().t('MY_SUB_LIST_TITLE')
    lines = [f'{title} (1/{total_pages})\n']
    for idx, sub in enumerate(page_items, 1):
        lines.append(format_subscription_list_line(sub, idx, T(), 'fa', user))
        lines.append('')
    text = '\n'.join(lines)
    assert len(text) <= 1024


def test_keyboard_keeps_buy_and_does_not_dump_all_rows() -> None:
    page_items = [_fake_sub(i) for i in range(1, 6)]
    keyboard = _build_subscriptions_keyboard(
        page_items,
        'fa',
        gift_enabled=False,
        page=1,
        total_pages=24,
    )
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert 'menu_buy' in callbacks
    assert 'ms_pg:2' in callbacks
    assert 'ms_pg:1' not in callbacks
    assert len(callbacks) < 20
    assert all(cb != 'sm:100' for cb in callbacks)


def test_keyboard_includes_search_and_keeps_gift() -> None:
    page_items = [_fake_sub(i) for i in range(1, 3)]
    keyboard = _build_subscriptions_keyboard(
        page_items,
        'fa',
        gift_enabled=True,
        page=1,
        total_pages=1,
        show_search=True,
    )
    callbacks = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert 'my_subs_search' in callbacks
    assert 'subscription_gift' in callbacks


def _detail_callbacks(keyboard) -> list[str]:
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def test_detail_keyboard_shows_disable_when_active() -> None:
    sub = SimpleNamespace(actual_status='active', user_disabled=False)
    keyboard = _build_subscription_detail_keyboard(sub_id=42, sub=sub)
    callbacks = _detail_callbacks(keyboard)
    assert 'sub_disable:42' in callbacks
    assert 'sub_enable:42' not in callbacks


def test_detail_keyboard_shows_enable_when_user_disabled() -> None:
    sub = SimpleNamespace(actual_status='disabled', user_disabled=True)
    keyboard = _build_subscription_detail_keyboard(sub_id=42, sub=sub)
    callbacks = _detail_callbacks(keyboard)
    assert 'sub_enable:42' in callbacks
    assert 'sub_disable:42' not in callbacks


def test_pause_uses_confirm_then_execute() -> None:
    src = Path('app/handlers/subscription/my_subscriptions.py').read_text(encoding='utf-8')
    assert 'sub_disable_yes:' in src
    assert 'MY_SUB_DISABLE_CONFIRM' in src
    assert 'handle_subscription_user_disable_execute' in src
    purchase = Path('app/handlers/subscription/purchase.py').read_text(encoding='utf-8')
    assert "startswith('sub_disable_yes:')" in purchase


def test_render_detail_does_not_call_expire_all() -> None:
    src = Path('app/handlers/subscription/my_subscriptions.py').read_text(encoding='utf-8')
    assert 'db.expire_all()' not in src
    assert '_render_subscription_detail' in src


def test_list_order_keeps_user_disabled_with_active() -> None:
    """Paused (user_disabled) rows must not sink to the expired tier."""
    src = Path('app/database/crud/subscription.py').read_text(encoding='utf-8')
    assert 'async def get_all_subscriptions_by_user_id' in src
    assert 'Subscription.user_disabled.is_(True), 0)' in src


async def test_receive_my_subs_search_escapes_query_and_rerenders() -> None:
    message = SimpleNamespace(
        text='<script>alert(1)</script>',
        answer=AsyncMock(),
    )
    db_user = SimpleNamespace(id=1, language='fa', is_partner=False, panel_brand_prefix=None)
    state = SimpleNamespace(
        update_data=AsyncMock(),
        set_state=AsyncMock(),
        get_data=AsyncMock(return_value={'my_subs_search_query': '<script>alert(1)</script>'}),
    )
    with patch(
        'app.handlers.subscription.my_subscriptions.show_my_subscriptions',
        new_callable=AsyncMock,
    ) as show_mock:
        await receive_my_subs_search(message, db_user, AsyncMock(), state)

    state.update_data.assert_awaited_once_with(my_subs_search_query='<script>alert(1)</script>')
    state.set_state.assert_awaited_once_with(None)
    message.answer.assert_awaited_once()
    confirm_text = message.answer.await_args.args[0]
    assert '&lt;script&gt;' in confirm_text
    assert '<script>' not in confirm_text
    show_mock.assert_awaited_once()
    fake_callback = show_mock.await_args.args[0]
    assert fake_callback.data == 'my_subscriptions'
    assert fake_callback.message is message
