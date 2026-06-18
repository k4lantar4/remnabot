"""Tests for my subscriptions detail view formatting."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.handlers.subscription.my_subscriptions import _format_detail_time_remaining
from app.localization.texts import get_texts


def _make_sub(*, end_date: datetime | None, status: str = 'active', is_trial: bool = False):
    return SimpleNamespace(
        end_date=end_date,
        status=status,
        is_trial=is_trial,
        actual_status='expired' if end_date and end_date <= datetime.now(UTC) else 'active',
    )


def test_format_detail_time_remaining_days_and_hours_fa() -> None:
    texts = get_texts('fa')
    end = datetime.now(UTC) + timedelta(days=56, hours=4, minutes=30)
    sub = _make_sub(end_date=end)

    result = _format_detail_time_remaining(sub, texts)

    assert result == '⏳ 56 روز و 4 ساعت دیگر'


def test_format_detail_time_remaining_days_only_fa() -> None:
    texts = get_texts('fa')
    end = datetime.now(UTC) + timedelta(days=10, minutes=15)
    sub = _make_sub(end_date=end)

    result = _format_detail_time_remaining(sub, texts)

    assert result == '⏳ 10 روز دیگر'


def test_format_detail_time_remaining_hours_only_fa() -> None:
    texts = get_texts('fa')
    end = datetime.now(UTC) + timedelta(hours=3, minutes=20)
    sub = _make_sub(end_date=end)

    result = _format_detail_time_remaining(sub, texts)

    assert result == '⏳ 3 ساعت دیگر'


def test_format_detail_time_remaining_minutes_fa() -> None:
    texts = get_texts('fa')
    end = datetime.now(UTC) + timedelta(minutes=45)
    sub = _make_sub(end_date=end)

    result = _format_detail_time_remaining(sub, texts)

    minutes = int(result.split()[0])
    assert 44 <= minutes <= 45
    assert result.endswith('دقیقه')


def test_format_detail_time_remaining_expired_fa() -> None:
    texts = get_texts('fa')
    end = datetime.now(UTC) - timedelta(hours=1)
    sub = _make_sub(end_date=end)

    result = _format_detail_time_remaining(sub, texts)

    assert result == 'منقضی شده'


def test_format_detail_time_remaining_no_end_date_fa() -> None:
    texts = get_texts('fa')
    sub = _make_sub(end_date=None)
    sub.actual_status = 'expired'

    result = _format_detail_time_remaining(sub, texts)

    assert result == 'منقضی شده'
