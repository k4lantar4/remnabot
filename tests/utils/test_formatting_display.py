import pytest

from app.utils.formatting import format_period
from app.utils.pricing_utils import format_period_description


@pytest.mark.parametrize(
    ('days', 'expected'),
    [(1, '1 روز'), (3, '3 روز'), (30, '1 ماه'), (90, '3 ماه')],
)
def test_format_period_fa(days: int, expected: str) -> None:
    assert format_period(days, language='fa') == expected


def test_format_period_description_fa_not_russian() -> None:
    assert format_period_description(30, 'fa') == '1 ماه'
    assert 'месяц' not in format_period_description(30, 'fa')
    assert format_period_description(14, 'fa') == '14 روز'


def test_format_period_ru_unchanged() -> None:
    assert format_period(30, language='ru') == '30 дней'
    assert format_period_description(30, 'ru') == '1 месяц'
