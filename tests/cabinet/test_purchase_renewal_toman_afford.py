from pathlib import Path


PURCHASE = Path('app/cabinet/routes/subscription_modules/purchase.py')
RENEWAL = Path('app/cabinet/routes/subscription_modules/renewal.py')
TARIFF_PURCHASE = Path('app/handlers/subscription/tariff_purchase.py')


def test_cabinet_purchase_renewal_use_toman_affordability() -> None:
    purchase = PURCHASE.read_text(encoding='utf-8')
    renewal = RENEWAL.read_text(encoding='utf-8')
    assert 'user_can_afford(user.balance_kopeks, price_kopeks)' in purchase
    assert 'calculate_missing_amount(user.balance_kopeks, price_kopeks)' in purchase
    assert 'catalog_price_in_toman(price_kopeks)' in purchase
    assert 'charge_toman = catalog_price_in_toman(price_kopeks)' in purchase

    assert 'user_can_afford(user.balance_kopeks, price_kopeks)' in renewal
    assert 'calculate_missing_amount(user.balance_kopeks, price_kopeks)' in renewal
    assert 'charge_balance_amount=catalog_price_in_toman(price_kopeks)' in renewal


def test_tariff_purchase_charges_catalog_as_toman() -> None:
    text = TARIFF_PURCHASE.read_text(encoding='utf-8')
    assert 'catalog_price_in_toman(final_price)' in text
    assert 'not user_can_afford(user_balance, final_price)' in text
    assert 'if final_price > 0 and user_balance < final_price:' not in text
