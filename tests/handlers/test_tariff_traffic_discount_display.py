from unittest.mock import MagicMock

from app.localization.texts import get_texts
from app.handlers.subscription import tariff_purchase as tp
from app.services.pricing_engine import RenewalPricing
from app.utils.purchase_confirm import format_tariff_purchase_confirm_text


from app.database.models import PartnerStatus


def test_discounted_traffic_display_wholesale_bps():
    user = MagicMock()
    user.wholesale_discount_bps = 5000
    user.partner_status = PartnerStatus.APPROVED.value

    final, pct = tp._discounted_traffic_display(50_000_000, user)
    assert final == 25_000_000
    assert pct == 50


def test_format_traffic_package_button_label_shows_discount():
    user = MagicMock()
    user.wholesale_discount_bps = 5000
    user.partner_status = PartnerStatus.APPROVED.value
    texts = get_texts('fa')

    label = tp._format_traffic_package_button_label(50, 50_000_000, texts, 'fa', user)
    assert '🔥−50%' in label
    assert '50' in label
    assert 'گیگ' in label


def test_confirm_traffic_line_uses_discounted_amount_for_wholesale(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, 'PRICE_DISPLAY_SUFFIX', ' تومان', raising=False)

    user = MagicMock()
    user.wholesale_discount_bps = 5000
    user.partner_status = PartnerStatus.APPROVED.value

    texts = MagicMock()
    texts.t.side_effect = lambda key, fallback, **kwargs: fallback
    texts.format_balance.side_effect = lambda amount, **kwargs: settings.format_balance(
        amount, language='fa', round_kopeks=False
    )

    result = RenewalPricing(
        base_price=60_000,
        servers_price=0,
        traffic_price=50_000_000,
        devices_price=0,
        promo_group_discount=25_000_030,
        promo_offer_discount=0,
        final_total=25_000_030,
        period_days=90,
        is_tariff_mode=True,
        breakdown={'period_kopeks': 60_000, 'traffic_kopeks': 50_000_000},
    )

    tariff = MagicMock()
    tariff.name = 'Multi'
    tariff.device_limit = 5

    message = format_tariff_purchase_confirm_text(
        texts,
        tariff=tariff,
        traffic_gb=50,
        period_days=90,
        result=result,
        balance_kopeks=10_000_000,
        language='fa',
        user=user,
    )

    fa_sep = '\u066c'
    assert f'250{fa_sep}000' in message
