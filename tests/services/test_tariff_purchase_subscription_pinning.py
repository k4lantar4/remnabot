"""Source-level pin for the FSM-driven subscription_id resolution in
`app/handlers/subscription/tariff_purchase.py::confirm_tariff_purchase`.

Background — the bug this defends against
-----------------------------------------
User report (2026-05-16): a user with two subscriptions of the same
tariff (one expired, one active) tries to renew the active one. Money
is deducted, log says "Тариф уже активен у пользователя", money gets
refunded, subscription is NOT extended. User has to re-try.

Root cause: ``confirm_tariff_purchase`` re-queried the target sub by
``(user_id, tariff_id)`` instead of using the EXACT subscription_id
the user clicked on at preview time. Under a race with a concurrent
panel webhook that briefly flips the active sub's status, the lookup
returns ``None`` → falls through to ``create_paid_subscription`` →
the partial UNIQUE ``uq_subscriptions_user_tariff_active`` raises
``IntegrityError`` → "Тариф уже активен" log + refund.

Fix shape:
  1. ``select_tariff_period`` (preview handler) reads
     ``target_subscription_id`` from FSM. If pinned, it loads that row
     via ``get_subscription_by_id_for_user`` for device pricing; if the
     pin is empty, ``_existing_sub`` is None (new row — never a
     tariff-level lookup).
  2. ``confirm_tariff_purchase`` loads by pin only via
     ``get_subscription_by_id_for_user`` (ownership-checked). Empty pin
     → create a new row. Never ``get_subscription_by_user_and_tariff``.

These tests pin the SOURCE-LEVEL contract — a full integration test
would need a real DB + Redis + aiogram FSM dispatcher, which is heavy.
The bug class is "drop the pin", which is grep-detectable.
"""

from __future__ import annotations

import ast
from pathlib import Path


TARIFF_PURCHASE_PATH = Path(__file__).resolve().parents[2] / 'app' / 'handlers' / 'subscription' / 'tariff_purchase.py'


def _find_async_function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f'async function {name!r} not found in tariff_purchase.py')


def _function_source(source: str, func: ast.AsyncFunctionDef) -> str:
    """Slice the literal source between the function's start and end lines.

    Used so we can grep ONLY inside the function body — assertions about
    "X must appear inside confirm_tariff_purchase" don't false-positive
    on identical names elsewhere in the file.
    """
    lines = source.splitlines(keepends=True)
    end_line = func.end_lineno or len(lines)
    return ''.join(lines[func.lineno - 1 : end_line])


# ---------------------------------------------------------------------------
# Preview handler must pin target_subscription_id.
# ---------------------------------------------------------------------------


def test_select_tariff_period_resolves_and_pins_target_subscription_id() -> None:
    """REGRESSION: ``select_tariff_period`` must honor the FSM pin.
    Pinned id → load that row for device pricing. Empty pin →
    ``_existing_sub = None`` (create a new row). Never look up by
    ``(user, tariff)``.
    """
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'select_tariff_period')
    body = _function_source(source, func)

    assert 'target_subscription_id' in body, (
        'select_tariff_period must read target_subscription_id from FSM — empty pin '
        'means create a new row, not look up by tariff'
    )
    assert 'get_subscription_by_id_for_user' in body, (
        'select_tariff_period must load a pinned subscription via '
        'get_subscription_by_id_for_user (IDOR-safe), not by (user, tariff)'
    )
    assert 'get_subscription_by_user_and_tariff' not in body, (
        'select_tariff_period must not look up by (user, tariff) when the pin is empty — '
        'that re-extends an existing row from catalog buy'
    )

    # Must store target_subscription_id in FSM. Pin the literal kwarg
    # name so a refactor that renames it (and breaks the confirm-side
    # reader) trips this test.
    assert 'target_subscription_id=' in body, (
        'select_tariff_period must write target_subscription_id into FSM state — '
        'confirm_tariff_purchase reads this key to pin the exact subscription user '
        'clicked on, avoiding the race that produced the "Тариф уже активен" bug'
    )


# ---------------------------------------------------------------------------
# Confirm handler must prefer the FSM-pinned id over tariff lookup.
# ---------------------------------------------------------------------------


def test_confirm_tariff_purchase_reads_target_subscription_id_from_fsm() -> None:
    """REGRESSION: ``confirm_tariff_purchase`` must load by FSM pin only.
    Empty pin → create a new row. Never ``get_subscription_by_user_and_tariff``.
    """
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'confirm_tariff_purchase')
    body = _function_source(source, func)

    assert 'target_subscription_id' in body, (
        'confirm_tariff_purchase must read target_subscription_id from FSM state to '
        'pin the exact subscription user confirmed on — without it, this handler '
        'races with concurrent panel webhooks and produces the duplicate-key bug'
    )

    # Must call the ownership-checked lookup, not the unscoped one.
    # ``get_subscription_by_id_for_user`` enforces ``Subscription.user_id == user_id``
    # which is the IDOR protection we want at the FSM-deserialization
    # boundary (the pinned id could in principle be stale or tampered).
    assert 'get_subscription_by_id_for_user' in body, (
        'confirm_tariff_purchase must look up the pinned subscription via '
        'get_subscription_by_id_for_user (IDOR-safe), not the unscoped variant'
    )

    assert 'should_extend_multi_tariff' in body, (
        'confirm_tariff_purchase must gate extend vs create on should_extend_multi_tariff '
        'so an empty pin never extends an existing row of the same tariff'
    )

    # Pin-only: the tariff-level CALL must be gone. A comment that names
    # the helper is allowed; a call with paren is the old fallback.
    fallback_call_idx = body.find('get_subscription_by_user_and_tariff(')
    assert fallback_call_idx < 0, (
        'confirm_tariff_purchase must not call get_subscription_by_user_and_tariff '
        'when the pin is empty — that re-extends an existing row from catalog buy'
    )


def test_confirm_tariff_purchase_guards_against_tariff_divergence() -> None:
    """If the FSM-pinned subscription's tariff_id no longer matches
    the confirm's tariff_id (admin swapped tariff between preview
    and confirm), we must fall back rather than extend a subscription
    of a different tariff with the new tariff's parameters.
    """
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'confirm_tariff_purchase')
    body = _function_source(source, func)

    # The divergence guard must compare tariff_ids. Pin the exact
    # pattern so a refactor that drops this check trips the test.
    assert 'tariff_id != tariff_id' in body or 'existing_sub.tariff_id != tariff_id' in body, (
        'confirm_tariff_purchase must guard against the pinned subscription '
        'pointing to a different tariff than the confirm carries — otherwise '
        'extending it with the wrong tariff parameters would corrupt state'
    )


# ---------------------------------------------------------------------------
# Negative-control: the buggy pattern must NOT remain. If anyone deletes
# the FSM-pin logic and reverts to "lookup by (user, tariff) only", these
# pins fail.
# ---------------------------------------------------------------------------


def test_confirm_tariff_purchase_does_not_use_only_tariff_lookup() -> None:
    """Pre-fix shape: confirm_tariff_purchase ran a single
    ``get_subscription_by_user_and_tariff`` call with no FSM-pinned
    override. Detect a regression to that shape.
    """
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'confirm_tariff_purchase')
    body = _function_source(source, func)

    # If `target_subscription_id` is absent, the fix has been removed.
    assert 'target_subscription_id' in body, (
        'confirm_tariff_purchase no longer pins the FSM target_subscription_id — '
        'this re-opens the race-condition bug fixed by commit handling the '
        'two-subscriptions-same-tariff renewal scenario'
    )
