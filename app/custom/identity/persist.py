"""Persist Remnawave 3.x numeric user id onto bot User and/or Subscription.

M3-ID: panel identity is ``users.id`` (former ``t_id``). ``users.uuid`` is gone
and uuid user-lookup routes 404. This seam writes ``.id`` only. It does
not look up by uuid and must not grow ``resolve_remnawave_id(uuid=...)``.

Two write paths (multi-tariff vs legacy single):

* ``Subscription.remnawave_id`` — per-subscription panel account
* ``User.remnawave_id`` — shared panel account in single-tariff mode
"""

from __future__ import annotations

from typing import Any

from app.external.remnawave_api import coerce_panel_user_id


def persist_identity(
    *,
    user: Any | None = None,
    subscription: Any | None = None,
    panel_user: Any | None = None,
    panel_id: Any = None,
) -> int:
    """Write a coerced panel ``users.id`` onto ``user`` and/or ``subscription``.

    Provide ``panel_user`` (reads ``.id`` only) and/or ``panel_id``. At least
    one write target is required.
    """
    if user is None and subscription is None:
        raise ValueError('persist_identity requires user and/or subscription')
    if panel_id is None:
        panel_id = getattr(panel_user, 'id', None)
    resolved = coerce_panel_user_id(panel_id)
    if subscription is not None:
        subscription.remnawave_id = resolved
    if user is not None:
        user.remnawave_id = resolved
    return resolved
