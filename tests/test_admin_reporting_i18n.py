"""Admin summary reports must not ship bare Russian bodies or ruble symbols."""

import re
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest

from app.config import settings
from app.services.reporting_service import ReportPeriod, ReportingService, reporting_service


@pytest.fixture(autouse=True)
def _fa_default_language(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'DEFAULT_LANGUAGE', 'fa', raising=False)


@pytest.fixture(autouse=True)
def _mock_report_queries(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_totals(_session):
        return {'active_trials': 7, 'active_paid': 3314, 'open_tickets': 7}

    async def fake_stats(_session, _start_utc, _end_utc):
        return {
            'new_users': 5,
            'new_trials': 3,
            'new_paid_subscriptions': 38,
            'trial_to_paid_conversions': 0,
            'subscription_payments_count': 36,
            'subscription_payments_amount': 330_150_001,
            'deposits_count': 15,
            'deposits_amount': 2_600_000,
            'new_tickets': 0,
        }

    async def fake_top_referrers(_session, _start_utc, _end_utc, limit=5):
        return []

    async def fake_usage(_session):
        return {'active_paid_users': 585, 'never_connected_users': 0}

    monkeypatch.setattr(reporting_service, '_collect_current_totals', fake_totals)
    monkeypatch.setattr(reporting_service, '_collect_period_stats', fake_stats)
    monkeypatch.setattr(reporting_service, '_get_top_referrers', fake_top_referrers)
    monkeypatch.setattr(reporting_service, '_get_user_usage_stats', fake_usage)


@pytest.mark.asyncio
async def test_build_report_is_persian_not_russian():
    body = await reporting_service._build_report(
        ReportPeriod.DAILY,
        report_date=date(2026, 6, 25),
    )
    assert not re.search(r'[А-Яа-яЁё]{4,}', body), body[:300]
    assert '₽' not in body
    assert 'تومان' in body or 'گزارش' in body


def test_reporting_service_no_bare_cyrillic_blocks():
    text = Path('app/services/reporting_service.py').read_text(encoding='utf-8')
    assert "lines += ['🧭 <b>Итог" not in text


@pytest.mark.asyncio
async def test_deliver_report_retries_without_topic_on_bad_request(monkeypatch: pytest.MonkeyPatch):
    service = ReportingService()
    bot = MagicMock()
    bot.send_message = AsyncMock(
        side_effect=[TelegramBadRequest(method='sendMessage', message='thread not found'), None],
    )
    service.set_bot(bot)
    monkeypatch.setattr(settings, 'ADMIN_REPORTS_CHAT_ID', '-100123', raising=False)
    monkeypatch.setattr(settings, 'ADMIN_REPORTS_TOPIC_ID', 42, raising=False)

    await service.deliver_report('📊 test')

    assert bot.send_message.await_count == 2
    first_call = bot.send_message.await_args_list[0].kwargs
    second_call = bot.send_message.await_args_list[1].kwargs
    assert first_call.get('message_thread_id') == 42
    assert 'message_thread_id' not in second_call
