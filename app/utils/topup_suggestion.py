"""Top-up amount suggestion helpers for cart-context balance flows."""

from __future__ import annotations

import math
from typing import Any

TOPUP_SUGGESTION_STEP_TOMAN = 1000


def suggest_topup_amount_toman(missing_toman: int, *, step: int = TOPUP_SUGGESTION_STEP_TOMAN) -> int:
    """Round missing balance up to the nearest step (default 1000 Toman)."""
    missing = max(0, int(missing_toman or 0))
    if missing == 0:
        return 0
    return math.ceil(missing / step) * step


def effective_c2c_topup_amount(missing_or_suggested_toman: int) -> int:
    """Round up to suggestion step, then enforce C2C minimum deposit."""
    from app.config import settings

    rounded = suggest_topup_amount_toman(missing_or_suggested_toman)
    if rounded == 0:
        return 0
    return max(rounded, settings.C2C_MIN_AMOUNT_KOPEKS)


def build_cart_topup_metadata(*, missing_toman: int, **cart_fields: Any) -> dict[str, Any]:
    """Attach standard cart fields for insufficient-balance → top-up → resume flows."""
    suggested = suggest_topup_amount_toman(missing_toman)
    return {
        **cart_fields,
        'saved_cart': True,
        'return_to_cart': True,
        'missing_amount': missing_toman,
        'suggested_topup_amount': suggested,
    }


def resolve_suggested_topup_from_cart(cart_data: dict[str, Any] | None) -> int:
    """Return rounded top-up suggestion from saved cart metadata."""
    if not cart_data:
        return 0
    suggested = cart_data.get('suggested_topup_amount')
    if suggested:
        return int(suggested)
    missing = int(cart_data.get('missing_amount') or 0)
    return suggest_topup_amount_toman(missing)


def format_topup_suggestion_line(texts, missing_toman: int) -> str:
    """One-line hint showing the 1000-Toman-rounded charge suggestion."""
    suggested = suggest_topup_amount_toman(missing_toman)
    return texts.t(
        'TOPUP_SUGGESTED_AMOUNT_LINE',
        '💡 Suggested top-up: {suggested} (rounded up to 1,000)',
    ).format(suggested=texts.format_balance(suggested, round_kopeks=False))
