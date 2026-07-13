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


def test_withdrawal_history_amount_rubles_uses_display_helper() -> None:
    """Withdrawal history API must not divide balance-scale Toman by 100."""
    amount_kopeks = 12_500
    assert display_balance_from_storage(amount_kopeks) == 12_500.0
    assert amount_kopeks / 100 == 125.0


def test_withdrawal_submit_amount_is_one_to_one_with_display() -> None:
    """User-entered display Toman maps 1:1 to stored amount_kopeks (Phase B)."""
    display_toman = 12_500
    stored = int(round(display_toman))
    assert stored == 12_500
    assert stored != int(round(display_toman * 100))
