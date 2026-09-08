from __future__ import annotations

from typing import Any


def should_extend_multi_tariff(
    state_data: dict,
    *,
    existing_sub: Any,
    renew_only: bool = False,
) -> bool:
    pinned = state_data.get('target_subscription_id')
    if pinned and existing_sub:
        return True
    if renew_only:
        active = state_data.get('active_subscription_id')
        return bool(active and existing_sub and getattr(existing_sub, 'id', None) == active)
    return False
