"""Pure parsing and validation helpers for custom-traffic tariffs."""

from decimal import Decimal, InvalidOperation

from app.utils.price_display import normalize_display_amount_text


def parse_positive_toman(raw: str) -> int:
    """Parse a positive whole-Toman price without floating-point rounding.

    Since revision 0115 ``traffic_price_per_gb_kopeks`` holds Toman 1:1, so the typed number is the
    stored number. Input goes through the same normalizer as every other typed amount (Persian
    digits, thousands separators, a trailing currency word), and a fractional Toman is rejected
    rather than rounded away — at this scale it is a typo, not a precision.
    """
    try:
        toman = Decimal(normalize_display_amount_text(raw))
    except InvalidOperation as exc:
        raise ValueError('invalid price') from exc

    if not toman.is_finite() or toman <= 0:
        raise ValueError('price must be positive and finite')

    if toman != toman.to_integral_value():
        raise ValueError('price must be a whole number of Toman')

    return int(toman)


def parse_positive_gb(raw: str) -> int:
    """Parse a positive whole-number traffic amount in gigabytes."""
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise ValueError('traffic must be a whole number') from exc

    if value <= 0:
        raise ValueError('traffic must be positive')

    return value


def validate_custom_traffic_configuration(
    *,
    price_per_gb_kopeks: int | None,
    min_traffic_gb: int | None,
    max_traffic_gb: int | None,
) -> tuple[str, ...]:
    """Return user-facing validation errors for enabling custom traffic."""
    errors: list[str] = []

    if price_per_gb_kopeks is None:
        errors.append('не указана цена за 1 ГБ')
    elif price_per_gb_kopeks <= 0:
        errors.append('цена за 1 ГБ должна быть больше нуля')

    if min_traffic_gb is None:
        errors.append('не указан минимальный объём')
    elif min_traffic_gb <= 0:
        errors.append('минимальный объём должен быть больше нуля')

    if max_traffic_gb is None:
        errors.append('не указан максимальный объём')
    elif max_traffic_gb <= 0:
        errors.append('максимальный объём должен быть больше нуля')

    if (
        min_traffic_gb is not None
        and max_traffic_gb is not None
        and min_traffic_gb > 0
        and max_traffic_gb > 0
        and max_traffic_gb < min_traffic_gb
    ):
        errors.append('максимальный объём не может быть меньше минимального')

    return tuple(errors)
