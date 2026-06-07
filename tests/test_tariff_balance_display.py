from app.utils.price_display import catalog_price_in_toman, user_can_afford


def test_user_can_afford_945k_toman_vs_10k_catalog_price():
    assert user_can_afford(945_000, 1_000_000) is True


def test_missing_toman():
    assert max(0, catalog_price_in_toman(1_000_000) - 9_450) == 550  # not 990550 from kopeks−toman mix


def test_affordance_helper_labels():
    from app.handlers.subscription.tariff_purchase import _affordance_context
    from app.localization.texts import get_texts

    texts = get_texts('fa')
    ctx = _affordance_context(texts, 945_000, 1_000_000)
    assert ctx['can_afford'] is True
    assert '945' in ctx['balance_label'] or '945000' in ctx['balance_label'].replace('\u066c', '')
