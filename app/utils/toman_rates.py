"""Toman quotes for Telegram Stars and CryptoBot balance top-ups.

Our fork's balance is Toman 1:1 (``users.balance_kopeks``). Upstream quotes Stars with a ruble rate
and CryptoBot with a live USD→RUB rate; neither is a Toman rate. Per the owner's ruling, both
conversions use a fixed rate the admin sets by hand (``TELEGRAM_STARS_TOMAN_PER_STAR``,
``CRYPTOBOT_TOMAN_PER_USDT``) — no live exchange API. While a rate is unset the method is not
offered and every quote raises :class:`TomanRateUnavailable`.

Top-up invoices carry the Toman amount to credit in their payload
(``topup_toman_{user_id}_{toman}[_{nonce}]``), so the credit never depends on a rate that may
change between quote and payment. Payloads issued before this module (``balance_*``,
``cabinet_topup_*``) are not parsed here and keep their old handling.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from app.config import settings


# Telegram accepts 1..10,000 ⭐ per invoice; upstream's ruble defaults (1..10,000 ₽ at 1 ₽/⭐) were
# the same bounds, so the Toman limits are these bounds times the rate.
STARS_PER_INVOICE_MIN = 1
STARS_PER_INVOICE_MAX = 10_000

# Existing CryptoBot invoice bounds (miniapp renewal, upstream top-up): 1..1,000 USD(T).
CRYPTOBOT_USDT_MIN = Decimal(1)
CRYPTOBOT_USDT_MAX = Decimal(1000)
CRYPTOBOT_TOMAN_ASSET = 'USDT'

TOMAN_TOPUP_PAYLOAD_PREFIX = 'topup_toman'
_PAYLOAD_RE = re.compile(r'^topup_toman_(\d+)_(\d+)(?:_\d+)?$')

_CENT = Decimal('0.01')


class TomanRateUnavailable(ValueError):
    """The admin has not set a usable Toman rate for this method (or the method is off)."""


@dataclass(frozen=True, slots=True)
class StarsQuote:
    stars: int
    credit_toman: int


@dataclass(frozen=True, slots=True)
class TomanTopupPayload:
    user_id: int
    toman: int


# ---- Telegram Stars -------------------------------------------------------


def stars_toman_rate() -> Decimal | None:
    return settings.get_stars_toman_per_star()


def is_stars_toman_ready() -> bool:
    return bool(settings.TELEGRAM_STARS_ENABLED) and stars_toman_rate() is not None


def _require_stars_rate() -> Decimal:
    rate = stars_toman_rate()
    if not settings.TELEGRAM_STARS_ENABLED or rate is None:
        raise TomanRateUnavailable('Telegram Stars Toman rate is not configured')
    return rate


def stars_to_toman(stars: int) -> int:
    """Toman value of ``stars`` at the current rate, rounded down."""
    rate = stars_toman_rate()
    if rate is None:
        raise TomanRateUnavailable('Telegram Stars Toman rate is not configured')
    return int((Decimal(stars) * rate).to_integral_value(rounding=ROUND_FLOOR))


def quote_stars_for_toman(toman: int) -> StarsQuote:
    """Stars to charge for a ``toman`` top-up (rounded up) and the Toman those stars credit."""
    rate = _require_stars_rate()
    stars = max(STARS_PER_INVOICE_MIN, math.ceil(Decimal(toman) / rate))
    return StarsQuote(stars=stars, credit_toman=stars_to_toman(stars))


def stars_topup_limits_toman() -> tuple[int, int]:
    rate = _require_stars_rate()
    min_toman = math.ceil(rate * STARS_PER_INVOICE_MIN)
    max_toman = int((rate * STARS_PER_INVOICE_MAX).to_integral_value(rounding=ROUND_FLOOR))
    return min_toman, max(max_toman, min_toman)


# ---- CryptoBot ------------------------------------------------------------


def cryptobot_toman_rate() -> Decimal | None:
    """Toman per USDT, only while invoices are issued in USDT (the rate is meaningless otherwise)."""
    if (settings.CRYPTOBOT_DEFAULT_ASSET or '').strip().upper() != CRYPTOBOT_TOMAN_ASSET:
        return None
    return settings.get_cryptobot_toman_per_usdt()


def is_cryptobot_toman_ready() -> bool:
    return cryptobot_toman_rate() is not None


def _require_cryptobot_rate() -> Decimal:
    rate = cryptobot_toman_rate()
    if rate is None:
        raise TomanRateUnavailable('CryptoBot Toman-per-USDT rate is not configured (or asset is not USDT)')
    return rate


def quote_usdt_for_toman(toman: int) -> Decimal:
    """USDT invoice amount for a ``toman`` top-up, rounded up to 0.01 so the user never underpays."""
    rate = _require_cryptobot_rate()
    return (Decimal(toman) / rate).quantize(_CENT, rounding=ROUND_CEILING)


def cryptobot_topup_limits_toman() -> tuple[int, int]:
    rate = _require_cryptobot_rate()
    min_toman = max(1, math.ceil(rate * CRYPTOBOT_USDT_MIN))
    max_toman = int((rate * CRYPTOBOT_USDT_MAX).to_integral_value(rounding=ROUND_FLOOR))
    return min_toman, max(max_toman, min_toman)


# ---- Payload --------------------------------------------------------------


def build_toman_topup_payload(user_id: int, toman: int, *, nonce: int | None = None) -> str:
    payload = f'{TOMAN_TOPUP_PAYLOAD_PREFIX}_{int(user_id)}_{int(toman)}'
    if nonce is not None:
        payload = f'{payload}_{int(nonce)}'
    return payload


def parse_toman_topup_payload(payload: str | None) -> TomanTopupPayload | None:
    if not payload or not isinstance(payload, str):
        return None
    match = _PAYLOAD_RE.match(payload.strip())
    if not match:
        return None
    user_id, toman = int(match.group(1)), int(match.group(2))
    if toman <= 0:
        return None
    return TomanTopupPayload(user_id=user_id, toman=toman)
