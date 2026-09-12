"""Phase C gate: storage and backend logic speak Toman 1:1, everywhere.

Before Phase C the database carried two scales at once — balances in Toman 1:1 since Phase B, catalog
prices as ``price_kopeks`` (Toman x100) — and every hop that mixed them produced the same 100x bug
(remnabot #32…#56). Revision ``0115`` divides the catalog columns by 100, and this file pins what
that buys: the conversion helpers become identities, the two formatters become one, and comparing a
balance with a price is plain arithmetic again.

The numbers are the ones the whole Toman test suite already uses, so they can be compared across
files: a 150,000-Toman balance against a 200,000-Toman price is refused with a 50,000-Toman
shortfall, and a 250,000-Toman balance is debited exactly 200,000 — but now the *stored* price is
200,000 too, not 20,000,000.

What this file deliberately does **not** assert is the HTTP contract. The wire still speaks the old
catalog scale (the cabinet divides by 100 itself), and that boundary lives in
``app/utils/wire_scale.py`` with its own tests; here the point is that nothing *else* converts.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.config import settings
from app.utils.price_display import (
    display_balance_from_storage,
    display_transaction_amount_from_storage,
    missing_toman,
    storage_sum_to_display_toman,
    user_can_afford,
)


PRICE_TOMAN = 200_000
SHORT_BALANCE = 150_000
SHORTFALL_TOMAN = 50_000
RICH_BALANCE = 250_000
DEPOSIT_TOMAN = 50_000

APP_ROOT = Path(__file__).resolve().parents[2] / 'app'


@pytest.fixture
def toman_suffix(monkeypatch):
    monkeypatch.setattr(settings, 'PRICE_DISPLAY_SUFFIX', ' تومان', raising=False)


# ── one scale in storage ──────────────────────────────────────────────────────


def test_the_catalog_conversion_helper_is_gone() -> None:
    """``catalog_price_in_toman`` had 150 call sites; after 0115 there is nothing to convert."""
    import app.utils.price_display as price_display

    assert not hasattr(price_display, 'catalog_price_in_toman')


def test_the_transaction_scale_list_is_gone() -> None:
    """The hand-maintained list was the bug surface: a new type on the wrong side rendered 100x off."""
    import app.utils.price_display as price_display

    for name in (
        '_BALANCE_SCALE_TRANSACTION_TYPES',
        'BALANCE_SCALE_TRANSACTION_TYPES',
        'is_balance_scale_transaction',
    ):
        assert not hasattr(price_display, name), name


def test_affordability_compares_two_toman_numbers(toman_suffix) -> None:
    assert user_can_afford(SHORT_BALANCE, PRICE_TOMAN) is False
    assert user_can_afford(RICH_BALANCE, PRICE_TOMAN) is True
    assert user_can_afford(PRICE_TOMAN, PRICE_TOMAN) is True


def test_shortfall_is_the_plain_difference(toman_suffix) -> None:
    assert missing_toman(SHORT_BALANCE, PRICE_TOMAN) == SHORTFALL_TOMAN
    assert settings.format_balance(missing_toman(SHORT_BALANCE, PRICE_TOMAN)) == '50,000 تومان'
    assert missing_toman(RICH_BALANCE, PRICE_TOMAN) == 0


def test_shortfall_never_goes_negative() -> None:
    assert missing_toman(RICH_BALANCE, PRICE_TOMAN) == 0
    assert missing_toman(0, 0) == 0


# ── one formatter ─────────────────────────────────────────────────────────────


def test_the_two_formatters_agree_on_every_amount(toman_suffix) -> None:
    """``format_price`` vs ``format_balance`` was F-058's whole shape; they are one function now."""
    for amount in (0, 1, DEPOSIT_TOMAN, PRICE_TOMAN, 1_234_567):
        assert settings.format_price(amount) == settings.format_balance(amount)


def test_a_price_renders_as_its_stored_number(toman_suffix) -> None:
    assert settings.format_price(PRICE_TOMAN, language='fa') == '200,000 تومان'
    assert settings.format_balance(DEPOSIT_TOMAN, language='fa') == '50,000 تومان'


def test_negative_amounts_keep_their_sign(toman_suffix) -> None:
    assert settings.format_price(-PRICE_TOMAN, language='fa') == '-200,000 تومان'


# ── one transaction scale ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    'tx_type',
    ['deposit', 'withdrawal', 'refund', 'failed_refund', 'referral_reward', 'poll_reward', 'subscription_payment', 'gift_payment'],
)
def test_every_transaction_type_displays_its_stored_number(tx_type: str) -> None:
    """The type no longer decides a scale — that is the whole point of 0115."""
    assert display_transaction_amount_from_storage(PRICE_TOMAN) == float(PRICE_TOMAN)
    assert storage_sum_to_display_toman(PRICE_TOMAN) == PRICE_TOMAN


def test_a_subscription_charge_is_stored_and_shown_as_the_same_number(toman_suffix) -> None:
    """A 200,000-Toman purchase writes -200000, not -20000000, and reads back «200,000 تومان»."""
    stored_row = -PRICE_TOMAN

    assert display_transaction_amount_from_storage(stored_row) == float(-PRICE_TOMAN)
    assert storage_sum_to_display_toman(stored_row) == PRICE_TOMAN
    assert settings.format_balance(abs(stored_row), language='fa') == '200,000 تومان'


def test_a_deposit_is_unchanged_by_phase_c(toman_suffix) -> None:
    """Balance-scale rows were already Toman; 0115 must not have touched them."""
    assert display_transaction_amount_from_storage(DEPOSIT_TOMAN) == float(DEPOSIT_TOMAN)
    assert settings.format_balance(DEPOSIT_TOMAN, language='fa') == '50,000 تومان'


def test_balance_display_is_still_one_to_one() -> None:
    assert display_balance_from_storage(RICH_BALANCE) == float(RICH_BALANCE)


# ── the guard that replaces the hand-maintained list ──────────────────────────


def _scaling_literals(path: Path) -> list[str]:
    """``x // 100`` / ``x * 100`` on something that looks like money, outside the wire boundary."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    hits: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, (ast.FloorDiv, ast.Mult, ast.Div)):
            continue
        if not (isinstance(node.right, ast.Constant) and node.right.value == 100):
            continue
        source = ast.unparse(node.left)
        if any(word in source.lower() for word in ('kopek', 'price', 'amount', 'balance', 'toman', 'cost')):
            hits.append(f'{path.name}:{node.lineno}: {ast.unparse(node)}')

    return hits


def test_no_amount_is_scaled_by_100_outside_the_wire_boundary() -> None:
    """After Phase C the only ×100 left in the backend is the frozen HTTP contract."""
    allowed = {'wire_scale.py'}
    offenders: list[str] = []

    for path in sorted(APP_ROOT.rglob('*.py')):
        if path.name in allowed:
            continue
        offenders.extend(_scaling_literals(path))

    assert offenders == [], 'amounts scaled by 100 outside wire_scale.py:\n' + '\n'.join(offenders)
