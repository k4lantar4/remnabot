"""The one place the old catalog x100 scale still exists: the HTTP contract.

Phase C put the database and all backend logic on Toman 1:1. The cabinet frontend was deliberately
left alone in that plan — it still divides ``price_kopeks`` by 100 itself (``src/utils/catalogScale.ts``)
and still sends top-up amounts multiplied by 100 — so the JSON contract has to keep speaking the old
scale until the follow-up plan (Phase C-2) moves the frontend over field by field.

Rather than scatter ``* 100`` back through the route modules, every conversion at that boundary goes
through the two functions here. That makes the boundary greppable, keeps
``test_phase_c_single_scale.py::test_no_amount_is_scaled_by_100_outside_the_wire_boundary`` able to
assert that nothing *else* converts, and means Phase C-2 deletes one module instead of hunting call
sites.

Direction matters and the names say which is which:

- :func:`wire_catalog_kopeks` — outbound, Toman → what the client expects to divide by 100.
- :func:`toman_from_wire_catalog` — inbound, what the client sent → Toman.

Fields that were **already** Toman on the wire before Phase C (``amount_rubles``, ``balance_kopeks``,
``missing_amount``, every ``*_toman`` twin) do not belong here: they need no conversion in either
direction, and routing them through this module would reintroduce the 100x bug from the other side.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


CATALOG_WIRE_FACTOR = 100


def wire_catalog_kopeks(amount_toman: float) -> int:
    """Toman → the catalog-scale integer the cabinet still divides by 100 (outbound)."""
    try:
        decimal_amount = Decimal(str(amount_toman))
    except InvalidOperation as exc:
        raise ValueError('Invalid Toman amount') from exc

    sign = -1 if decimal_amount < 0 else 1
    scaled = (abs(decimal_amount) * CATALOG_WIRE_FACTOR).to_integral_value(rounding=ROUND_HALF_UP)
    return sign * int(scaled)


def toman_from_wire_catalog(amount_kopeks: int) -> int:
    """The catalog-scale integer a client sent → Toman (inbound).

    Floors the magnitude and keeps the sign, the same truncation the display layer applied before
    Phase C, so an amount that round-trips through the cabinet renders identically.
    """
    value = int(amount_kopeks or 0)
    sign = -1 if value < 0 else 1
    return sign * (abs(value) // CATALOG_WIRE_FACTOR)
