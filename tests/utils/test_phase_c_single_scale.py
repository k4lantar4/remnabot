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
import re
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
    from app.utils import price_display

    assert not hasattr(price_display, 'catalog_price_in_toman')


def test_the_transaction_scale_list_is_gone() -> None:
    """The hand-maintained list was the bug surface: a new type on the wrong side rendered 100x off."""
    from app.utils import price_display

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
    [
        'deposit',
        'withdrawal',
        'refund',
        'failed_refund',
        'referral_reward',
        'poll_reward',
        'subscription_payment',
        'gift_payment',
    ],
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


#: Gateways that are disabled for Iran but kept in the tree for upstream mergeability. They charge in
#: rubles and their payment tables are excluded from revision 0115, so ``amount_kopeks / 100`` inside
#: them is a real ruble conversion and must stay. Phase C is about *our* Toman amounts.
RUBLE_GATEWAYS = (
    'yookassa',
    'platega',
    'lava',
    'cispay',
    'cloudpayments',
    'nalogo',
    'wata',
    'parity',
    'tabpay',
    'freekassa',
    'heleket',
    'mulenpay',
    'pal24',
    'jupiter',
    'donut',
    'kassa_ai',
    'riopay',
    'severpay',
    'paypear',
    'rollypay',
    'overpay',
    'aurapay',
    'etoplatezhi',
    'antilopay',
    'tribute',
    'apple',
)


#: ``x * percent / 100`` is arithmetic on a percentage, not a change of unit — the 100 is the
#: denominator of "per cent" and has nothing to do with kopeks. Same for basis points.
PERCENT_WORDS = ('percent', 'pct', 'bps', 'discount', 'commission', 'rate', 'ratio', 'share')

#: A name with one of these in it is an amount of money, whatever else it is called.
MONEY_WORDS = (
    'kopek',
    'price',
    'pricing',
    'amount',
    'balance',
    'toman',
    'cost',
    'total',
    'bonus',
    'spent',
    'revenue',
    'payout',
    'earning',
    'reward',
    'prize',
    'threshold',
    'value',
    'sum',
    'fee',
)

_IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def _is_money_name(name: str) -> bool:
    return any(word in name.lower() for word in MONEY_WORDS)


def _is_percentage_math(source: str) -> bool:
    """``x * percent / 100`` — but ``commission_amount / 100`` is an amount wearing a percent word.

    An identifier that is itself money (``commission_amount``, ``discount_value``) does not make
    the expression percentage arithmetic; only a percent word outside the money names does.
    """
    for identifier in _IDENTIFIER.findall(source):
        lowered = identifier.lower()
        if any(word in lowered for word in PERCENT_WORDS) and not _is_money_name(lowered):
            return True
    return False


def _percentage_numerators(tree: ast.AST) -> set[int]:
    """``(a - b) * 100 / a`` is a percentage: the ×100 is cancelled by the division beside it."""
    return {
        id(node.left)
        for node in ast.walk(tree)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv))
    }


def _is_ratio_times_hundred(node: ast.BinOp) -> bool:
    """``a / b * 100`` — a share rendered as a percentage, not a change of unit.

    The division already cancels the unit, so the operands may well be money (``paid / total``,
    ``total_payout / total_revenue``) without the ×100 meaning kopeks. Structure decides here;
    names cannot.
    """
    return isinstance(node.op, ast.Mult) and isinstance(node.left, ast.BinOp) and isinstance(node.left.op, ast.Div)


def _is_ruble_gateway(path: Path) -> bool:
    return any(name in path.name.lower() for name in RUBLE_GATEWAYS)


def _model_offenders() -> list[str]:
    """``models.py`` is resolved properly: each ``self.<col> / 100`` is asked about by name.

    A property dividing by 100 is correct exactly when its column still holds a payment provider's
    own currency. ``amount_columns.py`` is the authority on that — the same classification revision
    0115 migrated by — so the guard consults it instead of guessing from the file name.
    """
    from app.utils.amount_columns import looks_like_money_column, scale_of

    path = APP_ROOT / 'database' / 'models.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    ratios = _percentage_numerators(tree)
    offenders: list[str] = []

    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        table = None
        for stmt in cls.body:
            if isinstance(stmt, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == '__tablename__' for t in stmt.targets
            ):
                table = ast.literal_eval(stmt.value)
        if not table or any(name in cls.name.lower() for name in RUBLE_GATEWAYS):
            continue

        for node in ast.walk(cls):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mult)):
                continue
            if not (isinstance(node.right, ast.Constant) and node.right.value == 100):
                continue
            if _is_percentage_math(ast.unparse(node)) or id(node) in ratios or _is_ratio_times_hundred(node):
                continue
            columns = [
                a.attr
                for a in ast.walk(node.left)
                if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) and a.value.id == 'self'
            ]
            if not columns or not looks_like_money_column(columns[0]):
                continue
            scale = scale_of(table, columns[0])
            if scale == 'provider':
                continue
            offenders.append(f'models.py:{node.lineno}: {cls.name}.{columns[0]} is {scale}, not provider currency')

    return offenders


def _scaling_literals(path: Path) -> list[str]:
    """``x // 100`` / ``x * 100`` on something that looks like money, outside the wire boundary."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    ratios = _percentage_numerators(tree)
    hits: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, (ast.FloorDiv, ast.Mult, ast.Div)):
            continue
        if not (isinstance(node.right, ast.Constant) and node.right.value == 100):
            continue
        source = ast.unparse(node.left)
        if not _is_money_name(source):
            continue
        # A ruble gateway's own settings and columns keep ruble-kopek semantics wherever they appear.
        if any(name in source.lower() for name in RUBLE_GATEWAYS):
            continue
        if _is_percentage_math(ast.unparse(node)) or id(node) in ratios or _is_ratio_times_hundred(node):
            continue
        hits.append(f'{path.relative_to(APP_ROOT)}:{node.lineno}: {ast.unparse(node)}')

    return hits


def test_no_helper_hides_a_scale_factor_in_a_default_argument() -> None:
    """A literal 100 in a signature is the same bug wearing a disguise.

    ``admin_campaigns._safe_div(value, divisor=100)`` was exactly this: the division read as
    ``value / divisor``, so scanning for ``/ 100`` never saw it, and every campaign amount would have
    rendered 100x too small after the rescale. Catching the shape, not just the expression, is what
    stops it coming back through a new helper.
    """
    offenders: list[str] = []

    for path in sorted(APP_ROOT.rglob('*.py')):
        if path.name == 'wire_scale.py' or _is_ruble_gateway(path):
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            args = node.args
            defaults = list(zip(args.args[len(args.args) - len(args.defaults) :], args.defaults, strict=False))
            defaults += list(zip(args.kwonlyargs, args.kw_defaults, strict=False))
            for arg, default in defaults:
                if not isinstance(default, ast.Constant) or default.value != 100:
                    continue
                if not any(w in arg.arg.lower() for w in ('divisor', 'factor', 'scale', 'multiplier')):
                    continue
                offenders.append(f'{path.relative_to(APP_ROOT)}:{node.lineno}: {node.name}({arg.arg}=100)')

    assert offenders == [], 'scale factor hidden in a default argument:\n' + '\n'.join(offenders)


def test_no_amount_is_scaled_by_100_outside_the_wire_boundary() -> None:
    """After Phase C the only scale hop left in the backend is the frozen HTTP contract.

    ``app/utils/wire_scale.py`` owns that boundary, and the disabled ruble gateways keep converting
    their own currency. Anything else dividing or multiplying an amount by 100 means two scales are
    back in the codebase — the exact class of bug Phase C removed.
    """
    offenders = _model_offenders()

    for path in sorted(APP_ROOT.rglob('*.py')):
        if path.name in ('wire_scale.py', 'models.py') or _is_ruble_gateway(path):
            continue
        offenders.extend(_scaling_literals(path))

    assert offenders == [], 'amounts scaled by 100 outside wire_scale.py:\n' + '\n'.join(offenders)
