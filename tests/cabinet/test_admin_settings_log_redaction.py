from __future__ import annotations

import pytest

from app.cabinet.routes import admin_settings


@pytest.mark.parametrize(
    'key',
    [
        'BOT_TOKEN',
        'YOOKASSA_SECRET_KEY',
        'ADMIN_API_PASSWORD',
        'CRYPTOBOT_API_KEY',
    ],
)
def test_is_sensitive_setting_key(key: str) -> None:
    assert admin_settings._is_sensitive_setting_key(key) is True


@pytest.mark.parametrize(
    'key',
    [
        'DEFAULT_DEVICE_LIMIT',
        'SUPPORT_MENU_ENABLED',
        'TRAFFIC_PACKAGES',
    ],
)
def test_is_sensitive_setting_key_non_secret(key: str) -> None:
    assert admin_settings._is_sensitive_setting_key(key) is False
