"""Bot admin campaign screen: revenue is a Toman sum, so it is formatted as a balance.

``get_campaign_statistics`` counts real deposits as campaign revenue — balance scale,
Toman 1:1. ``format_price`` divides by 100 (catalog scale), which showed 50,000 Toman
of deposits as 500. The first payment is a subscription price (catalog) and keeps
``format_price``.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.handlers.admin import campaigns as m
from app.localization.texts import get_texts


def _unwrap(func):
    while hasattr(func, '__wrapped__'):
        func = func.__wrapped__
    return func


async def test_campaign_detail_formats_deposit_revenue_as_toman_balance(monkeypatch):
    stats = {
        'registrations': 1,
        'balance_issued': 5_000,
        'subscription_issued': 0,
        'last_registration': None,
        'total_revenue_kopeks': 50_000,
        'total_revenue_toman': 50_000,
        'avg_revenue_per_user_kopeks': 50_000,
        'avg_revenue_per_user_toman': 50_000,
        'avg_first_payment_kopeks': 1_000_000,
        'avg_first_payment_toman': 10_000,
        'trial_users_count': 0,
        'active_trials_count': 0,
        'conversion_count': 1,
        'paid_users_count': 1,
        'conversion_rate': 100.0,
        'trial_conversion_rate': 0.0,
    }
    campaign = SimpleNamespace(id=10, start_parameter='camp10', is_active=True)
    monkeypatch.setattr(m, 'get_campaign_by_id', AsyncMock(return_value=campaign))
    monkeypatch.setattr(m, 'get_campaign_statistics', AsyncMock(return_value=stats))
    monkeypatch.setattr(m, '_get_bot_deep_link', AsyncMock(return_value='https://t.me/bot?start=camp10'))
    monkeypatch.setattr(m, '_format_campaign_summary', MagicMock(return_value='SUMMARY'))
    monkeypatch.setattr(m, 'get_campaign_management_keyboard', MagicMock(return_value='KB'))

    callback = SimpleNamespace(
        data='admin_campaign_manage_10',
        message=SimpleNamespace(edit_text=AsyncMock()),
        answer=AsyncMock(),
    )
    db_user = SimpleNamespace(language='fa')

    await _unwrap(m.show_campaign_detail)(callback, db_user, AsyncMock())

    text = callback.message.edit_text.await_args.args[0]
    texts = get_texts('fa')
    assert f'<b>{texts.format_balance(50_000)}</b>' in text.split('Доход:')[1].split('\n')[0]
    assert f'<b>{texts.format_balance(50_000)}</b>' in text.split('Средний доход на пользователя:')[1].split('\n')[0]
    assert f'<b>{texts.format_price(1_000_000)}</b>' in text.split('Средний первый платеж:')[1].split('\n')[0]


def test_no_bot_handler_formats_campaign_revenue_as_a_catalog_price():
    """Both bot screens that show campaign stats (campaign card, admin user stats) use the Toman fields."""
    handlers_dir = Path(__file__).resolve().parents[2] / 'app' / 'handlers'
    pattern = re.compile(r'format_price\([^)]*(total_revenue_kopeks|avg_revenue_per_user_kopeks)')
    offenders = [
        f'{path}:{lineno}'
        for path in sorted(handlers_dir.rglob('*.py'))
        for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1)
        if pattern.search(line)
    ]
    assert offenders == []
