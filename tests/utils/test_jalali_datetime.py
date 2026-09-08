from datetime import UTC, datetime

from app.utils.jalali_datetime import format_user_datetime, is_jalali_language


def test_fa_is_jalali_language() -> None:
    assert is_jalali_language('fa') is True
    assert is_jalali_language('ru') is False


def test_fa_converts_known_gregorian_anchor() -> None:
    # 2026-07-09 → 18.04.1405 (same anchor as production jalali tests)
    dt = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
    assert format_user_datetime(dt, language='fa', fmt='%d.%m.%Y') == '18.04.1405'


def test_ru_stays_gregorian() -> None:
    dt = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
    out = format_user_datetime(dt, language='ru', fmt='%d.%m.%Y')
    assert '1405' not in out
    assert '09.07.2026' in out or '07' in out
