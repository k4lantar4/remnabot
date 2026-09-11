"""Bot admin income statistics in Toman (F-015).

A 50,000-Toman deposit is stored 50_000, a 50,000-Toman subscription payment
5_000_000. Summing the raw values and running them through ``format_price`` (÷100)
showed the deposit 100x too small; the screens must print the ``*_toman`` sums with
``format_balance``.
"""

import inspect
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.handlers.admin import statistics


def _callback(data: str) -> SimpleNamespace:
    return SimpleNamespace(data=data, message=SimpleNamespace(edit_text=AsyncMock()), answer=AsyncMock())


def _stats() -> dict:
    return {
        'totals': {
            'income_kopeks': 5_050_000,
            'income_toman': 100_000,
            'expenses_kopeks': 20_000,
            'expenses_toman': 20_000,
            'profit_kopeks': 5_030_000,
            'profit_toman': 80_000,
            'subscription_income_kopeks': 5_000_000,
            'subscription_income_toman': 50_000,
        },
        'today': {'transactions_count': 2, 'income_kopeks': 5_050_000, 'income_toman': 100_000},
        'by_type': {
            'deposit': {'count': 1, 'amount': 50_000},
            'subscription_payment': {'count': 1, 'amount': 5_000_000},
        },
        'by_payment_method': {'c2c': {'count': 2, 'amount': 5_050_000, 'amount_toman': 100_000}},
    }


def _rendered(callback: SimpleNamespace) -> str:
    return callback.message.edit_text.await_args.args[0]


@pytest.mark.asyncio
async def test_revenue_screen_prints_toman(monkeypatch):
    monkeypatch.setattr(statistics, 'get_transactions_statistics', AsyncMock(return_value=_stats()))
    callback = _callback('admin_stats_revenue')

    await inspect.unwrap(statistics.show_revenue_statistics)(callback, db_user=SimpleNamespace(language='ru'), db=None)

    text = _rendered(callback)
    for toman in (100_000, 20_000, 80_000, 50_000):
        assert settings.format_balance(toman) in text
    assert f'c2c: 2 ({settings.format_balance(100_000)})' in text
    assert settings.format_price(5_050_000) not in text


@pytest.mark.asyncio
async def test_summary_screen_income_and_arpu_in_toman(monkeypatch):
    user_stats = {'total_users': 10, 'active_users': 4, 'new_month': 1}
    sub_stats = {'active_subscriptions': 3, 'paid_subscriptions': 2, 'purchased_month': 1}
    monkeypatch.setattr(
        statistics, 'UserService', lambda: SimpleNamespace(get_user_statistics=AsyncMock(return_value=user_stats))
    )
    monkeypatch.setattr(statistics, 'get_subscriptions_statistics', AsyncMock(return_value=sub_stats))
    monkeypatch.setattr(statistics, 'get_transactions_statistics', AsyncMock(return_value=_stats()))
    callback = _callback('admin_stats_summary')

    await inspect.unwrap(statistics.show_summary_statistics)(callback, db_user=SimpleNamespace(language='ru'), db=None)

    text = _rendered(callback)
    assert settings.format_balance(100_000) in text
    assert f'ARPU: {settings.format_balance(25_000)}' in text


@pytest.mark.asyncio
async def test_revenue_by_period_sums_toman(monkeypatch):
    rows = [
        {'date': date(2026, 9, 10), 'amount_kopeks': 5_050_000, 'amount_toman': 100_000},
        {'date': date(2026, 9, 11), 'amount_kopeks': 20_000, 'amount_toman': 20_000},
    ]
    monkeypatch.setattr(statistics, 'get_revenue_by_period', AsyncMock(return_value=rows))
    callback = _callback('admin_revenue_month')

    await inspect.unwrap(statistics.show_revenue_by_period)(callback, db_user=SimpleNamespace(language='ru'), db=None)

    text = _rendered(callback)
    assert settings.format_balance(120_000) in text
    assert settings.format_balance(60_000) in text
    assert f'10.09: {settings.format_balance(100_000)}' in text
    assert settings.format_price(5_070_000) not in text
