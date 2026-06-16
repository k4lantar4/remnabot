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
