"""Tests for fa Jalali date formatting."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _utc_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'TIMEZONE', 'UTC', raising=False)
    from app.utils.timezone import get_local_timezone

    get_local_timezone.cache_clear()


def test_fa_formats_jalali_date() -> None:
    from app.utils.jalali_datetime import format_user_datetime

    dt = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
    assert format_user_datetime(dt, language='fa', fmt='%d.%m.%Y') == '18.04.1405'


def test_ru_keeps_gregorian_date() -> None:
    from app.utils.jalali_datetime import format_user_datetime

    dt = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
    assert format_user_datetime(dt, language='ru', fmt='%d.%m.%Y') == '09.07.2026'


def test_none_returns_placeholder() -> None:
    from app.utils.jalali_datetime import format_user_datetime

    assert format_user_datetime(None, language='fa') == 'N/A'
    assert format_user_datetime(None, language='fa', na_placeholder='—') == '—'


def test_is_jalali_language() -> None:
    from app.utils.jalali_datetime import is_jalali_language

    assert is_jalali_language('fa') is True
    assert is_jalali_language('fa-IR') is True
    assert is_jalali_language('ru') is False
    assert is_jalali_language('en') is False
