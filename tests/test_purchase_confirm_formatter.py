from unittest.mock import MagicMock

from app.services.pricing_engine import RenewalPricing
from app.utils.formatting import format_price_kopeks
from app.utils.purchase_confirm import format_tariff_purchase_confirm_text


def _make_tariff(name: str = 'Test Tariff', device_limit: int = 2):
    tariff = MagicMock()
    tariff.name = name
    tariff.device_limit = device_limit
    return tariff


def test_confirm_discount_and_total_on_separate_lines():
    texts = MagicMock()
    texts.t.side_effect = lambda key, fallback, **kwargs: fallback

    result = RenewalPricing(
        base_price=11_000_000,
        servers_price=0,
        traffic_price=11_000_000,
        devices_price=0,
        promo_group_discount=11_000_000,
        promo_offer_discount=0,
        final_total=11_000_000,
        period_days=30,
        is_tariff_mode=True,
    )

    message = format_tariff_purchase_confirm_text(
        texts,
        tariff=_make_tariff(),
        traffic_gb=11,
        period_days=30,
        result=result,
        balance_kopeks=500_000,
        language='fa',
    )

    discount_idx = message.index('🎁')
    total_idx = message.index('💰')
    assert discount_idx < total_idx
    assert '\n' in message[discount_idx:total_idx]
    assert '💰' not in message[discount_idx:total_idx]


def test_confirm_amounts_use_format_price_kopeks():
    texts = MagicMock()
    texts.t.side_effect = lambda key, fallback, **kwargs: fallback
    texts.format_balance.side_effect = lambda amount, **kwargs: f'{amount:,} تومان'

    original_total = 22_000_000
    discount_kopeks = 11_000_000
    final_total = 11_000_000

    result = RenewalPricing(
        base_price=original_total,
        servers_price=0,
        traffic_price=original_total,
        devices_price=0,
        promo_group_discount=discount_kopeks,
        promo_offer_discount=0,
        final_total=final_total,
        period_days=60,
        is_tariff_mode=True,
    )

    message = format_tariff_purchase_confirm_text(
        texts,
        tariff=_make_tariff(),
        traffic_gb=11,
        period_days=60,
        result=result,
        balance_kopeks=945_000,
        language='fa',
    )

    subtotal_label = format_price_kopeks(original_total, language='fa')
    discount_label = format_price_kopeks(discount_kopeks, language='fa')
    total_label = format_price_kopeks(final_total, language='fa')

    assert subtotal_label in message
    assert discount_label in message
    assert total_label in message
    assert str(original_total) not in message
    assert str(discount_kopeks) not in message
    assert str(final_total) not in message


def test_confirm_includes_period_and_traffic_lines_from_breakdown():
    texts = MagicMock()
    texts.t.side_effect = lambda key, fallback, **kwargs: fallback
    texts.format_balance.side_effect = lambda amount, **kwargs: f'{amount:,} تومان'

    result = RenewalPricing(
        base_price=9_000_000,
        servers_price=0,
        traffic_price=3_000_000,
        devices_price=0,
        promo_group_discount=0,
        promo_offer_discount=0,
        final_total=12_000_000,
        period_days=30,
        is_tariff_mode=True,
        breakdown={'period_kopeks': 8_000_000, 'traffic_kopeks': 4_000_000},
    )

    message = format_tariff_purchase_confirm_text(
        texts,
        tariff=_make_tariff(),
        traffic_gb=25,
        period_days=30,
        result=result,
        balance_kopeks=2_000_000,
        language='fa',
    )

    assert f'📅 Период: {format_price_kopeks(8_000_000, language="fa")}' in message
    assert f'📊 Трафик: {format_price_kopeks(3_000_000, language="fa")}' in message


def test_confirm_fa_price_lines_use_thousand_grouping(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, 'PRICE_DISPLAY_SUFFIX', ' تومان', raising=False)

    texts = MagicMock()
    texts.t.side_effect = lambda key, fallback, **kwargs: fallback
    texts.format_balance.side_effect = lambda amount, **kwargs: settings.format_balance(
        amount, language='fa', round_kopeks=False
    )

    result = RenewalPricing(
        base_price=60_000,
        servers_price=0,
        traffic_price=100_000_000,
        devices_price=0,
        promo_group_discount=10_006_000,
        promo_offer_discount=0,
        final_total=90_054_000,
        period_days=90,
        is_tariff_mode=True,
        breakdown={'period_kopeks': 60_000, 'traffic_kopeks': 100_000_000},
    )

    message = format_tariff_purchase_confirm_text(
        texts,
        tariff=_make_tariff(),
        traffic_gb=100,
        period_days=90,
        result=result,
        balance_kopeks=10_008_540,
        language='fa',
    )

    fa_sep = '\u066c'
    assert f'1{fa_sep}000{fa_sep}600' in message
    assert f'1{fa_sep}000{fa_sep}000' in message
    assert f'900{fa_sep}540' in message
    assert '1000000' not in message
    assert '1000600' not in message
    assert '900540' not in message
