"""Source-level contract for multi-account purchase pinning in
`app/handlers/subscription/tariff_purchase.py`.

Multi-account: new purchases create a new subscription unless
``target_subscription_id`` is pinned in FSM (renew / cart-restore).
``select_tariff_period`` must NOT auto-pin from tariff lookup.
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
    lines = source.splitlines(keepends=True)
    end_line = func.end_lineno or len(lines)
    return ''.join(lines[func.lineno - 1 : end_line])


def test_select_tariff_period_does_not_auto_pin_existing_sub() -> None:
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'select_tariff_period')
    body = _function_source(source, func)

    assert 'get_subscription_by_user_and_tariff' not in body, (
        'select_tariff_period must not auto-pin an existing subscription — '
        'menu_buy should create a new account unless renew flow sets target_subscription_id'
    )


def test_confirm_tariff_purchase_reads_target_subscription_id_from_fsm() -> None:
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'confirm_tariff_purchase')
    body = _function_source(source, func)

    assert 'target_subscription_id' in body
    assert 'get_subscription_by_id_for_user' in body
    assert 'should_extend_multi_tariff' in body
    assert 'get_subscription_by_user_and_tariff(' not in body, (
        'confirm_tariff_purchase must not fall back to tariff-level lookup — '
        'same-tariff rebuy creates a new account unless FSM pin is set'
    )


def test_should_extend_multi_tariff_helper_exists() -> None:
    source = TARIFF_PURCHASE_PATH.read_text(encoding='utf-8')
    assert 'def should_extend_multi_tariff(' in source
