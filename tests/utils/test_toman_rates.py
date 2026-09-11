"""Toman quotes for Telegram Stars and CryptoBot top-ups (fixed admin-set rates)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.config import settings
from app.utils import toman_rates


@pytest.fixture
def stars_rate(monkeypatch):
    def _set(value):
        monkeypatch.setattr(settings, 'TELEGRAM_STARS_ENABLED', True, raising=False)
        monkeypatch.setattr(settings, 'TELEGRAM_STARS_TOMAN_PER_STAR', value, raising=False)

    return _set


@pytest.fixture
def usdt_rate(monkeypatch):
    def _set(value, asset='USDT'):
        monkeypatch.setattr(settings, 'CRYPTOBOT_TOMAN_PER_USDT', value, raising=False)
        monkeypatch.setattr(settings, 'CRYPTOBOT_DEFAULT_ASSET', asset, raising=False)

    return _set


# ---- settings -------------------------------------------------------------


@pytest.mark.parametrize('raw', [None, 0, -5, 'abc'])
def test_stars_rate_unset_or_invalid_is_none(monkeypatch, raw):
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_TOMAN_PER_STAR', raw, raising=False)
    assert settings.get_stars_toman_per_star() is None


def test_stars_rate_blank_env_line_is_unset():
    from app.config import Settings

    assert Settings.blank_stars_toman_per_star_is_unset('  ') is None


def test_stars_rate_is_decimal(monkeypatch):
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_TOMAN_PER_STAR', 1850.5, raising=False)
    assert settings.get_stars_toman_per_star() == Decimal('1850.5')


# ---- Stars ----------------------------------------------------------------


def test_stars_quote_rounds_stars_up_and_credits_stars_times_rate(stars_rate):
    stars_rate(1850)
    quote = toman_rates.quote_stars_for_toman(50_000)
    # 50,000 / 1,850 = 27.03 → 28 stars; the user is credited what 28 stars are worth.
    assert quote.stars == 28
    assert quote.credit_toman == 51_800


def test_stars_quote_exact_multiple(stars_rate):
    stars_rate(2000)
    quote = toman_rates.quote_stars_for_toman(1_000_000)
    assert quote.stars == 500
    assert quote.credit_toman == 1_000_000


def test_stars_quote_without_rate_is_refused(stars_rate):
    stars_rate(None)
    with pytest.raises(toman_rates.TomanRateUnavailable):
        toman_rates.quote_stars_for_toman(50_000)


def test_stars_quote_refused_when_stars_disabled(monkeypatch, stars_rate):
    stars_rate(2000)
    monkeypatch.setattr(settings, 'TELEGRAM_STARS_ENABLED', False, raising=False)
    assert toman_rates.is_stars_toman_ready() is False
    with pytest.raises(toman_rates.TomanRateUnavailable):
        toman_rates.quote_stars_for_toman(50_000)


def test_stars_limits_are_telegram_star_bounds_times_rate(stars_rate):
    stars_rate(1850)
    assert toman_rates.stars_topup_limits_toman() == (1_850, 18_500_000)


def test_stars_to_toman_floors(stars_rate):
    stars_rate(Decimal('1850.5'))
    assert toman_rates.stars_to_toman(3) == 5_551


# ---- CryptoBot ------------------------------------------------------------


def test_usdt_quote_rounds_up_to_cent(usdt_rate):
    usdt_rate(95_000)
    # 50,000 / 95,000 = 0.5263… → 0.53 USDT; the balance is credited the requested 50,000.
    assert toman_rates.quote_usdt_for_toman(50_000) == Decimal('0.53')


def test_usdt_quote_large_amount(usdt_rate):
    usdt_rate(100_000)
    assert toman_rates.quote_usdt_for_toman(1_000_000) == Decimal('10.00')


def test_usdt_quote_refused_for_non_usdt_asset(usdt_rate):
    usdt_rate(95_000, asset='TON')
    assert toman_rates.is_cryptobot_toman_ready() is False
    with pytest.raises(toman_rates.TomanRateUnavailable):
        toman_rates.quote_usdt_for_toman(50_000)


def test_usdt_quote_refused_without_rate(usdt_rate):
    usdt_rate(None)
    with pytest.raises(toman_rates.TomanRateUnavailable):
        toman_rates.quote_usdt_for_toman(50_000)


def test_cryptobot_limits_are_usdt_bounds_times_rate(usdt_rate):
    usdt_rate(95_000)
    assert toman_rates.cryptobot_topup_limits_toman() == (95_000, 95_000_000)


# ---- payload --------------------------------------------------------------


def test_payload_round_trip():
    payload = toman_rates.build_toman_topup_payload(42, 51_800, nonce=1_757_000_000)
    assert payload == 'topup_toman_42_51800_1757000000'
    parsed = toman_rates.parse_toman_topup_payload(payload)
    assert parsed == toman_rates.TomanTopupPayload(user_id=42, toman=51_800)


def test_payload_without_nonce():
    payload = toman_rates.build_toman_topup_payload(7, 50_000)
    assert toman_rates.parse_toman_topup_payload(payload) == toman_rates.TomanTopupPayload(user_id=7, toman=50_000)


@pytest.mark.parametrize(
    'legacy',
    [
        'balance_topup_5000000',
        'balance_42_5000000',
        'balance_topup_42_5000000_1757000000',
        'cabinet_topup_42_5000000',
        'topup_toman_42_0',
        'topup_toman_x_100',
        '',
        None,
    ],
)
def test_legacy_or_bogus_payloads_are_not_toman(legacy):
    assert toman_rates.parse_toman_topup_payload(legacy) is None
