import pytest
from decimal import Decimal

from app.config import settings
from app.utils.price_display import balance_from_display_amount, display_balance_from_storage


@pytest.mark.parametrize(
    ('toman', 'expected'),
    [
        (0, 0.0),
        (100, 100.0),
        (120152, 120152.0),
        (-50, -50.0),
    ],
)
def test_display_balance_from_storage(toman: int, expected: float) -> None:
    assert display_balance_from_storage(toman) == expected


@pytest.mark.parametrize(
    ('amount', 'expected_toman'),
    [
        (0, 0),
        (1, 1),
        (100, 100),
        (120152, 120152),
        (-50, -50),
        (99.6, 100),
        (100.4, 100),
    ],
)
def test_balance_from_display_amount(amount: float, expected_toman: int) -> None:
    assert balance_from_display_amount(amount) == expected_toman


def test_balance_from_display_amount_decimal() -> None:
    assert balance_from_display_amount(Decimal('100')) == 100


def test_format_balance_fa_grouping(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'PRICE_DISPLAY_SUFFIX', ' تومان', raising=False)
    assert settings.format_balance(1000, language='fa') == '1\u066c000 تومان'


def test_format_balance_en_grouping(monkeypatch) -> None:
    monkeypatch.setattr(settings, 'PRICE_DISPLAY_SUFFIX', ' تومان', raising=False)
    assert settings.format_balance(1000, language='en') == '1,000 تومان'
