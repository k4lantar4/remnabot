"""Helpers for renew vs create when a catalog tariff was replaced/deactivated."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.subscription import get_subscription_by_id_for_user
from app.database.crud.tariff import get_tariff_by_id


async def resolve_renewal_target_subscription(
    db: AsyncSession,
    *,
    user_id: int,
    pinned_subscription_id: int | None,
    requested_tariff_id: int,
):
    """Return the subscription that should be *extended* for this checkout.

    Multi-tariff purchase intentionally creates a new account when the user
    buys an active tariff without a renew pin. Renew flows pin
    ``target_subscription_id`` / ``subscription_id``.

    When the pinned row's ``tariff_id`` differs from the tariff being paid for:
    - old tariff missing or **inactive** → keep the pin (migrate-renew after
      catalog replacement, e.g. deactivated tariff 4 → active tariff 9)
    - old tariff still **active** → drop the pin (second account / other plan)
    """
    if not pinned_subscription_id:
        return None

    sub = await get_subscription_by_id_for_user(db, int(pinned_subscription_id), user_id)
    if not sub:
        return None

    if sub.tariff_id == requested_tariff_id:
        return sub

    # Legacy row with no tariff: renew picker is upgrading onto a tariff.
    if not sub.tariff_id:
        return sub

    old_tariff = await get_tariff_by_id(db, sub.tariff_id)
    if old_tariff is None or not old_tariff.is_active:
        return sub

    return None
