"""The purchase and renewal paths decide affordability through the named helpers, not inline.

This file greps the source rather than exercising the endpoints, because what it protects is a
habit: every one of remnabot #32…#56 started as someone comparing ``user.balance_kopeks`` with a
price directly at a new call site.

Before Phase C it also asserted that each charge went through ``catalog_price_in_toman``. That
helper is gone — revision ``0115`` put storage on one scale, so there is nothing to convert and the
amount passed to the charge is the price itself. The remaining rule is the durable one: use
``user_can_afford`` and ``calculate_missing_amount``, never an inline ``<`` against the balance.
"""

import re
from pathlib import Path


PURCHASE = Path('app/cabinet/routes/subscription_modules/purchase.py')
RENEWAL = Path('app/cabinet/routes/subscription_modules/renewal.py')
TARIFF_PURCHASE = Path('app/handlers/subscription/tariff_purchase.py')

#: ``balance_kopeks < price`` / ``balance >= price`` written out by hand.
INLINE_COMPARISON = re.compile(r'balance\w*\s*[<>]=?\s*\w*(price|total|cost)', re.IGNORECASE)


def test_cabinet_purchase_and_renewal_use_the_affordability_helpers() -> None:
    purchase = PURCHASE.read_text(encoding='utf-8')
    renewal = RENEWAL.read_text(encoding='utf-8')

    assert 'user_can_afford(user.balance_kopeks, price_kopeks)' in purchase
    assert 'calculate_missing_amount(user.balance_kopeks, price_kopeks)' in purchase

    assert 'user_can_afford(user.balance_kopeks, price_kopeks)' in renewal
    assert 'calculate_missing_amount(user.balance_kopeks, price_kopeks)' in renewal
    assert 'charge_balance_amount=price_kopeks' in renewal


def test_tariff_purchase_uses_the_affordability_helper() -> None:
    text = TARIFF_PURCHASE.read_text(encoding='utf-8')

    assert 'not user_can_afford(user_balance, final_price)' in text
    assert 'if final_price > 0 and user_balance < final_price:' not in text


def test_no_path_compares_a_balance_with_a_price_inline() -> None:
    offenders: list[str] = []

    for path in (PURCHASE, RENEWAL, TARIFF_PURCHASE):
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
            if INLINE_COMPARISON.search(line):
                offenders.append(f'{path.name}:{number}: {line.strip()}')

    assert offenders == [], 'compare through user_can_afford instead:\n' + '\n'.join(offenders)
