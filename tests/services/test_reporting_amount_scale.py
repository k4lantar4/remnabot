"""Admin reporting and stats must use type-aware amount scale."""

from app.utils.price_display import (
    format_transaction_amount_for_display,
    storage_sum_to_display_toman,
)


class _FakeFormatters:
    @staticmethod
    def format_balance(amount: int) -> str:
        return f'{amount:,} تومان'

    @staticmethod
    def format_price(kopeks: int) -> str:
        return f'{kopeks // 100:,} تومان'


def test_deposit_display_toman_not_divided_again() -> None:
    raw = 1_000_000
    display = storage_sum_to_display_toman(raw, 'deposit')
    formatted = format_transaction_amount_for_display(
        raw, 'deposit', _FakeFormatters.format_balance, _FakeFormatters.format_price
    )
    assert display == 1_000_000
    assert formatted == '1,000,000 تومان'
    assert _FakeFormatters.format_price(raw) == '10,000 تومان'


def test_subscription_payment_catalog_kopeks_display() -> None:
    raw = 500_000
    display = storage_sum_to_display_toman(raw, 'subscription_payment')
    formatted = format_transaction_amount_for_display(
        raw, 'subscription_payment', _FakeFormatters.format_balance, _FakeFormatters.format_price
    )
    assert display == 5_000
    assert formatted == '5,000 تومان'


def test_mixed_income_display_toman_total() -> None:
    deposit_raw = 1_000_000
    sub_raw = 500_000
    total = storage_sum_to_display_toman(deposit_raw, 'deposit') + storage_sum_to_display_toman(
        sub_raw, 'subscription_payment'
    )
    assert total == 1_005_000
