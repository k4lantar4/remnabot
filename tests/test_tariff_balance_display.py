from app.utils.price_display import catalog_price_in_toman, user_can_afford


def test_user_can_afford_945k_toman_vs_10k_catalog_price():
    assert user_can_afford(945_000, 1_000_000) is True


def test_missing_toman():
    assert max(0, catalog_price_in_toman(1_000_000) - 9_450) == 550  # not 990550 from kopeks−toman mix
