from app.utils.price_display import display_balance_from_storage


def test_balance_scale_earnings_display_not_divided_by_100() -> None:
    total_earnings = 12_500
    correct = display_balance_from_storage(total_earnings)
    wrong = total_earnings / 100
    assert correct == 12_500.0
    assert wrong == 125.0
    assert correct != wrong


def test_referral_info_rubles_fields_use_display_helper() -> None:
    """Document expected mapping for get_referral_info response builder."""
    total_earnings = 12_500
    available = 8_000
    assert display_balance_from_storage(total_earnings) == 12_500.0
    assert float(available) == 8_000.0
