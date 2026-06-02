"""POC bootstrap for card-to-card smoke testing.

End-to-end path (production handlers):
  balance → Card-to-Card → amount → receipt photo/text → admin approve.

All handlers are registered via ``register_c2c_plugin``; this module only
exposes helpers for automated smoke checks.
"""

from __future__ import annotations

from app.config import settings


def is_c2c_smoke_ready() -> bool:
    """Return True when C2C can be exercised in a smoke test."""
    return settings.is_c2c_enabled() and settings.get_c2c_admin_chat_id() is not None
