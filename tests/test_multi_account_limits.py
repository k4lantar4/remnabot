import pytest
from unittest.mock import MagicMock

from app.config import settings


def test_partner_has_unlimited_subscriptions():
    user = MagicMock(is_partner=True)
    assert settings.get_max_active_subscriptions_for_user(user) >= 999_999


def test_regular_user_uses_config_cap():
    user = MagicMock(is_partner=False)
    settings.MAX_ACTIVE_SUBSCRIPTIONS = 50
    assert settings.get_max_active_subscriptions_for_user(user) == 50
