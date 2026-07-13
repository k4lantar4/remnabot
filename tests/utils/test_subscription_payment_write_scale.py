"""Regression: subscription_payment ledger rows must store catalog kopeks, not Toman."""

from app.utils.price_display import display_transaction_amount_from_storage


def test_subscription_payment_catalog_kopeks_display() -> None:
    price_kopeks = 500_000
    charge_toman = price_kopeks // 100
    assert charge_toman == 5_000
    assert display_transaction_amount_from_storage(price_kopeks, 'subscription_payment') == 5_000.0


def test_toman_stored_row_shows_100x_too_small() -> None:
    """Documents bug when create_transaction stores Toman instead of price_kopeks."""
    wrong_stored = 5_000
    assert display_transaction_amount_from_storage(wrong_stored, 'subscription_payment') == 50.0
