"""Purchase confirmation message formatting."""

from __future__ import annotations

import html
from typing import TYPE_CHECKING

from app.utils.formatting import format_period, format_price_kopeks, format_traffic
from app.utils.price_display import catalog_price_in_toman


if TYPE_CHECKING:
    from app.database.models import Tariff
    from app.localization.texts import Texts
    from app.services.pricing_engine import RenewalPricing


def format_tariff_purchase_confirm_text(
    texts: Texts,
    *,
    tariff: Tariff,
    traffic_gb: int,
    period_days: int,
    result: RenewalPricing,
    balance_kopeks: int,
    language: str,
    user=None,
) -> str:
    """Build pre-invoice purchase confirmation with separate pricing lines."""
    parts = [
        texts.t('TARIFF_PURCHASE_CONFIRM_HEADER', '✅ <b>Подтверждение покупки</b>\n\n'),
        texts.t(
            'TARIFF_PURCHASE_CONFIRM_BODY',
            '📦 Тариф: <b>{name}</b>\n📊 Трафик: {traffic}\n📱 Устройств: {devices}\n📅 Период: {period}\n',
        ).format(
            name=html.escape(tariff.name),
            traffic=format_traffic(traffic_gb, language),
            devices=tariff.device_limit,
            period=format_period(period_days, language),
        ),
        texts.t('TARIFF_PURCHASE_CONFIRM_SUBTOTAL', '💵 Сумма: {amount}').format(
            amount=format_price_kopeks(result.original_total, language=language),
        ),
    ]
    period_kopeks = int(result.breakdown.get('period_kopeks', result.base_price) or 0)
    raw_traffic_kopeks = int(result.breakdown.get('traffic_kopeks', result.traffic_price) or 0)
    if user is not None and raw_traffic_kopeks > 0:
        from app.services.pricing_engine import PricingEngine

        traffic_kopeks, _, _ = PricingEngine.calculate_traffic_discount(
            raw_traffic_kopeks, user, period_days
        )
    else:
        traffic_kopeks = int(result.traffic_price or raw_traffic_kopeks)
    parts.append(
        texts.t('TARIFF_PURCHASE_CONFIRM_PERIOD_LINE', '📅 Период: {amount}').format(
            amount=format_price_kopeks(period_kopeks, language=language),
        )
    )
    parts.append(
        texts.t('TARIFF_PURCHASE_CONFIRM_TRAFFIC_LINE', '📊 Трафик: {amount}').format(
            amount=format_price_kopeks(traffic_kopeks, language=language),
        )
    )

    total_discount = result.promo_group_discount + result.promo_offer_discount
    if total_discount > 0 and result.original_total > 0:
        discount_percent = round(total_discount * 100 / result.original_total)
        parts.append(
            texts.t('TARIFF_PURCHASE_CONFIRM_DISCOUNT', '🎁 Скидка: {percent}% (−{amount})').format(
                percent=discount_percent,
                amount=format_price_kopeks(total_discount, language=language),
            )
        )

    parts.append(
        texts.t('TARIFF_PURCHASE_CONFIRM_TOTAL', '💰 <b>Итого: {amount}</b>').format(
            amount=format_price_kopeks(result.final_total, language=language),
        )
    )

    price_toman = catalog_price_in_toman(result.final_total)
    parts.append('')
    parts.append(
        texts.t(
            'TARIFF_PURCHASE_CONFIRM_BALANCE',
            '💳 Ваш баланс: {balance}\nПосле оплаты: {after}',
        ).format(
            balance=texts.format_balance(balance_kopeks, round_kopeks=False),
            after=texts.format_balance(balance_kopeks - price_toman, round_kopeks=False),
        )
    )

    return '\n'.join(parts)
