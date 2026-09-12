"""Stars and CryptoBot are only offered once their fixed Toman rate is set; limits follow the rate."""

from __future__ import annotations

import pytest

from app.config import settings
from app.services.payment_method_config_service import _get_method_defaults


@pytest.fixture
def stars_on(monkeypatch):
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_ENABLED', True, raising=False)


@pytest.fixture
def cryptobot_on(monkeypatch):
    monkeypatch.setattr(settings, 'CRYPTOBOT_ENABLED', True, raising=False)
    monkeypatch.setattr(settings, 'CRYPTOBOT_API_TOKEN', '1:test', raising=False)
    monkeypatch.setattr(settings, 'CRYPTOBOT_DEFAULT_ASSET', 'USDT', raising=False)


def test_stars_not_configured_without_toman_rate(monkeypatch, stars_on):
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_TOMAN_PER_STAR', None, raising=False)
    assert _get_method_defaults()['telegram_stars']['is_configured'] is False


def test_stars_limits_on_cabinet_scale(monkeypatch, stars_on):
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_TOMAN_PER_STAR', 1850, raising=False)
    stars = _get_method_defaults()['telegram_stars']
    assert stars['is_configured'] is True
    # The limits are stored Toman since revision 0115: 1 star = 1,850 T, 10,000 stars = 18,500,000 T.
    assert stars['default_min'] == 1_850
    assert stars['default_max'] == 18_500_000


def test_cryptobot_not_configured_without_toman_rate(monkeypatch, cryptobot_on):
    monkeypatch.setattr(settings, 'CRYPTOBOT_TOMAN_PER_USDT', None, raising=False)
    assert _get_method_defaults()['cryptobot']['is_configured'] is False


def test_cryptobot_not_configured_for_non_usdt_asset(monkeypatch, cryptobot_on):
    monkeypatch.setattr(settings, 'CRYPTOBOT_TOMAN_PER_USDT', 95_000, raising=False)
    monkeypatch.setattr(settings, 'CRYPTOBOT_DEFAULT_ASSET', 'TON', raising=False)
    assert _get_method_defaults()['cryptobot']['is_configured'] is False


def test_cryptobot_limits_on_cabinet_scale(monkeypatch, cryptobot_on):
    monkeypatch.setattr(settings, 'CRYPTOBOT_TOMAN_PER_USDT', 95_000, raising=False)
    crypto = _get_method_defaults()['cryptobot']
    assert crypto['is_configured'] is True
    # 1..1,000 USDT x 95,000 T, stored as Toman.
    assert crypto['default_min'] == 95_000
    assert crypto['default_max'] == 95_000_000
