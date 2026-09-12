"""Pricing and price display, on one scale.

This module centralises:
- price calculation with all applicable discounts (promo groups, promo offers)
- consistent price-button and price-text formatting across every flow

It no longer converts between scales. Before Phase C, catalog prices were stored as ``price_kopeks``
(Toman x100) while balances were Toman 1:1, and the helpers here translated between the two; getting
the direction wrong at any hop rendered or charged 100x off, which is what remnabot #32…#56 kept
fixing one site at a time. Revision ``0115`` divided the catalog columns by 100, so a price and a
balance are now the same kind of number and comparing them is plain arithmetic.

``user_can_afford`` and ``missing_toman`` survive as one-line helpers on purpose: they give the
comparison a name to grep for, and they keep their call sites unchanged across the migration.

The one boundary that still speaks the old scale is the HTTP contract the cabinet consumes; it lives
in :mod:`app.utils.wire_scale` and nowhere else.
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import structlog

from app.config import settings
from app.database.models import User


logger = structlog.get_logger(__name__)

# Ceiling on one admin balance edit (bot and cabinet), in stored Toman. Kept equal to the
# stored delta the old ruble-input path allowed (100,000 × 100), so the maximum credit is unchanged.
ADMIN_BALANCE_EDIT_MAX_TOMAN = 10_000_000


def display_balance_from_storage(amount_toman: int) -> float:
    """API ``balance_rubles``: the stored integer is Toman 1:1."""
    return float(amount_toman)


def storage_sum_to_display_toman(raw_sum: int) -> int:
    """Display Toman for a summed amount. Since Phase C the sum is already Toman — only |x|."""
    return abs(int(raw_sum or 0))


def display_transaction_amount_from_storage(amount_kopeks: int) -> float:
    """User-facing ``amount_rubles`` for a transaction row, sign preserved.

    Before Phase C this had to know the transaction type, because catalog charges were stored x100
    and balance movements 1:1. Revision ``0115`` put every row on the Toman scale, so the type
    decides nothing and the hand-maintained list of "balance-scale types" is gone.
    """
    return float(amount_kopeks)


def user_can_afford(balance_toman: int, price_toman: int) -> bool:
    """True when the stored balance covers the price. Both sides are Toman since Phase C."""
    return int(balance_toman or 0) >= int(price_toman or 0)


def missing_toman(balance_toman: int, price_toman: int) -> int:
    """Toman shortfall of a balance against a price; 0 when affordable."""
    return max(0, int(price_toman or 0) - int(balance_toman or 0))


def render_addon_insufficient_funds(texts, *, price_toman: int, balance_toman: int) -> tuple[str, int]:
    """Persian/HTML insufficient-funds copy with the Toman shortfall for a C2C top-up."""
    shortfall = missing_toman(balance_toman, price_toman)
    message = texts.t(
        'ADDON_INSUFFICIENT_FUNDS_MESSAGE',
        (
            '⚠️ <b>Недостаточно средств</b>\n\n'
            'Стоимость услуги: {required}\n'
            'На балансе: {balance}\n'
            'Не хватает: {missing}\n\n'
            'Выберите способ пополнения. Сумма подставится автоматически.'
        ),
    ).format(
        required=texts.format_balance(price_toman, round_kopeks=False),
        balance=texts.format_balance(balance_toman, round_kopeks=False),
        missing=texts.format_balance(shortfall, round_kopeks=False),
    )
    return message, shortfall


_PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
_ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
_CURRENCY_SUFFIX_RE = re.compile(r'(?i)(تومان|toman|rial|₽)\s*$')


def normalize_display_amount_text(raw: str) -> str:
    """Normalize user-typed balance/top-up text (fa digits, separators, suffixes)."""
    text = raw.strip().translate(_PERSIAN_DIGITS).translate(_ARABIC_DIGITS)
    text = _CURRENCY_SUFFIX_RE.sub('', text).strip()
    text = text.replace('\u066c', '').replace(' ', '').replace(',', '')
    # European thousands: 10.000 → 10000 (single dot, exactly 3 fractional digits)
    if re.fullmatch(r'-?\d+\.\d{3}', text):
        text = text.replace('.', '')
    return text


def balance_from_display_amount(amount: float | Decimal | str) -> int:
    """
    Convert admin/display input to balance_kopeks (Toman integer, ROUND_HALF_UP).

    Preserves sign (e.g. -50 display → -50 stored).
    """
    if isinstance(amount, str):
        amount = normalize_display_amount_text(amount)
        if not amount:
            raise ValueError('Invalid display amount')
    try:
        decimal_amount = Decimal(str(amount))
    except InvalidOperation as exc:
        raise ValueError('Invalid display amount') from exc
    sign = -1 if decimal_amount < 0 else 1
    decimal_amount = abs(decimal_amount)
    try:
        decimal_amount = decimal_amount.quantize(Decimal(1), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError('Invalid display amount') from exc
    toman = int(decimal_amount.to_integral_value(rounding=ROUND_HALF_UP))
    return sign * toman


@dataclass
class PriceInfo:
    """Container for pricing information with discounts."""

    base_price: int  # Original price without any discounts (kopeks)
    final_price: int  # Final price after all discounts (kopeks)
    discount_percent: int  # Total discount percentage

    @property
    def has_discount(self) -> bool:
        """Check if there's any discount applied."""
        return self.base_price > self.final_price and self.discount_percent > 0

    @property
    def discount_value(self) -> int:
        """Get the absolute discount value in kopeks."""
        return self.base_price - self.final_price


def calculate_user_price(user: User | None, base_price: int, period_days: int, category: str = 'period') -> PriceInfo:
    """
    Calculate final price for a user with all applicable discounts.

    Args:
        user: User object (None for base/default pricing from settings)
        base_price: Base price without discounts (kopeks)
        period_days: Subscription period in days
        category: Discount category ("period", "servers", "devices", "traffic")

    Returns:
        PriceInfo with base_price, final_price, and discount_percent

    Example:
        >>> user = get_user_from_db(123)
        >>> price_info = calculate_user_price(user, 100000, 30, 'period')
        >>> print(f'{price_info.base_price} -> {price_info.final_price} ({price_info.discount_percent}%)')
        100000 -> 80000 (20%)

        >>> # For base pricing (no user)
        >>> price_info = calculate_user_price(None, 100000, 30, 'period')
        >>> # Uses BASE_PROMO_GROUP_PERIOD_DISCOUNTS from settings
    """
    if not base_price or base_price <= 0:
        return PriceInfo(base_price=base_price or 0, final_price=base_price or 0, discount_percent=0)

    # Step 1: Wholesale partners bypass retail promo stack
    from app.services.pricing_engine import PricingEngine

    if user and PricingEngine.uses_wholesale_pricing(user):
        final_price, discount_value = PricingEngine.apply_wholesale_discount(base_price, user)
        discount_percent = PricingEngine.checkout_display_discount_percent(base_price, final_price)
        logger.debug(
            'calculate_user_price',
            telegram_id=user.telegram_id,
            base_price=base_price,
            final_price=final_price,
            wholesale_discount_bps=PricingEngine.get_wholesale_discount_bps(user),
            discount_percent=discount_percent,
            category=category,
            period_days=period_days,
        )
        return PriceInfo(base_price=base_price, final_price=final_price, discount_percent=discount_percent)

    # Step 2: Get promo group discount
    if user:
        group_discount = user.get_promo_discount(category, period_days)
    else:
        group_discount = settings.get_base_promo_group_period_discount(period_days)

    # Step 3: Get promo offer discount (stacking)
    promo_offer_discount = 0
    if user:
        from app.utils.promo_offer import get_user_active_promo_discount_percent

        promo_offer_discount = get_user_active_promo_discount_percent(user)

    # Apply both discounts sequentially via PricingEngine
    final_price, _, _ = PricingEngine.apply_stacked_discounts(base_price, group_discount, promo_offer_discount)

    # Effective combined discount percent
    if final_price < base_price:
        discount_percent = round((base_price - final_price) * 100 / base_price)
    else:
        discount_percent = 0

    logger.debug(
        'calculate_user_price',
        telegram_id=user.telegram_id if user else 'None',
        base_price=base_price,
        final_price=final_price,
        group_discount=group_discount,
        promo_offer_discount=promo_offer_discount,
        discount_percent=discount_percent,
        category=category,
        period_days=period_days,
    )

    return PriceInfo(base_price=base_price, final_price=final_price, discount_percent=discount_percent)


def format_price_button(
    period_label: str, price_info: PriceInfo, format_price_func, emphasize: bool = False, add_exclamation: bool = True
) -> str:
    """
    Format a price button text with unified discount display.

    Args:
        period_label: Label for the period (e.g., "30 дней", "1 месяц")
        price_info: PriceInfo object with pricing details
        format_price_func: Function to format price (usually texts.format_price)
        emphasize: Add fire emojis for emphasis (for best deals)
        add_exclamation: Add exclamation mark after discount percent

    Returns:
        Formatted button text

    Examples:
        With discount and price > 0:
            "📅 30 дней - 990₽ ➜ 693₽ (-30%)!"

        With final price = 0:
            "📅 30 дней"

        With emphasis:
            "🔥 📅 30 дней - 8990₽ ➜ 6293₽ (-30%)! 🔥"

        Without discount:
            "📅 30 дней - 990₽"
    """
    # Format button text differently if final price is 0
    if price_info.final_price == 0:
        button_text = f'📅 {period_label}'
    elif price_info.has_discount:
        exclamation = '!' if add_exclamation else ''
        button_text = (
            f'📅 {period_label} - '
            f'{format_price_func(price_info.base_price)} ➜ '
            f'{format_price_func(price_info.final_price)} '
            f'(-{price_info.discount_percent}%){exclamation}'
        )
    else:
        button_text = f'📅 {period_label} - {format_price_func(price_info.final_price)}'

    # Add emphasis for best deals
    if emphasize:
        button_text = f'🔥 {button_text} 🔥'

    logger.debug('Formatted button', button_text=button_text)
    return button_text


def format_price_text(period_label: str, price_info: PriceInfo, format_price_func) -> str:
    """
    Format a price for message text (not button) with unified discount display.

    Args:
        period_label: Label for the period (e.g., "30 дней")
        price_info: PriceInfo object with pricing details
        format_price_func: Function to format price (usually texts.format_price)

    Returns:
        Formatted price text for messages

    Examples:
        With discount:
            "📅 30 дней - 990₽ ➜ 693₽"

        Without discount:
            "📅 30 дней - 990₽"

        With zero price:
            "📅 30 дней"
    """
    if price_info.final_price == 0:
        return f'📅 {period_label}'
    if price_info.has_discount:
        return (
            f'📅 {period_label} - '
            f'{format_price_func(price_info.base_price)} ➜ '
            f'{format_price_func(price_info.final_price)}'
        )
    return f'📅 {period_label} - {format_price_func(price_info.final_price)}'
