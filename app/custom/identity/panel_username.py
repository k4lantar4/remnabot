from __future__ import annotations

from typing import Any


def cache_panel_username(subscription: Any, panel_user: Any) -> None:
    name = (getattr(panel_user, 'username', None) or '').strip()
    if not name:
        return
    subscription.panel_username = name[:64]
