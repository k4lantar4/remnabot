"""The bot and the cabinet produce the resolved group post through one shared module."""

from __future__ import annotations

from app.plugins.c2c import decision
from app.plugins.c2c.handlers import admin as bot_admin


def test_bot_handlers_use_the_shared_decision_helpers():
    assert bot_admin.sync_c2c_group_admin_message is decision.sync_group_admin_message
    assert bot_admin._resolved_receipt_message is decision.resolved_receipt_message
