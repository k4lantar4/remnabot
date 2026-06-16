from app.utils.topup_suggestion import (
    TOPUP_SUGGESTION_STEP_TOMAN,
    build_cart_topup_metadata,
    suggest_topup_amount_toman,
)


def test_suggest_topup_amount_toman_rounds_up_to_1000() -> None:
    assert suggest_topup_amount_toman(550) == 1000
    assert suggest_topup_amount_toman(1000) == 1000
    assert suggest_topup_amount_toman(1001) == 2000
    assert suggest_topup_amount_toman(0) == 0


def test_build_cart_topup_metadata_includes_suggested_amount() -> None:
    cart = build_cart_topup_metadata(missing_toman=1550, cart_mode='purchase', total_price=5000)
    assert cart['missing_amount'] == 1550
    assert cart['suggested_topup_amount'] == 2000
    assert cart['saved_cart'] is True
    assert cart['return_to_cart'] is True
    assert cart['cart_mode'] == 'purchase'
    assert cart['total_price'] == 5000


def test_suggest_topup_respects_custom_step() -> None:
    assert suggest_topup_amount_toman(550, step=500) == 1000
    assert TOPUP_SUGGESTION_STEP_TOMAN == 1000
