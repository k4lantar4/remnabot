"""Source-level pin: cabinet ``/purchase-tariff`` with an empty pin (catalog /
``?intent=new``) must CREATE a new subscription, not silently extend an existing
row via tariff-level lookup.

Expired-trial reuse is only via pinned ``subscription_id`` from the detail
renew path (``get_subscription_by_id_for_user``), not catalog tariff lookup.
"""

from __future__ import annotations

import ast
from pathlib import Path


PURCHASE_PATH = (
    Path(__file__).resolve().parents[2] / 'app' / 'cabinet' / 'routes' / 'subscription_modules' / 'purchase.py'
)


def _find_async_function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f'async function {name!r} not found in cabinet purchase.py')


def _function_source(source: str, func: ast.AsyncFunctionDef) -> str:
    lines = source.splitlines(keepends=True)
    end_line = func.end_lineno or len(lines)
    return ''.join(lines[func.lineno - 1 : end_line])


def test_purchase_tariff_empty_pin_does_not_lookup_by_tariff() -> None:
    """Catalog / intent=new must not resolve an existing row by (user, tariff)."""
    source = PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'purchase_tariff')
    body = _function_source(source, func)
    assert body.find('get_subscription_by_user_and_tariff(') < 0, (
        'purchase_tariff must not call get_subscription_by_user_and_tariff when '
        'the cabinet catalog pin is empty — that silent-extends an existing row'
    )
    assert 'request.subscription_id is None' in body
    assert 'subscription = None' in body


def test_purchase_tariff_pinned_id_uses_ownership_lookup() -> None:
    source = PURCHASE_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    func = _find_async_function(tree, 'purchase_tariff')
    body = _function_source(source, func)
    assert 'get_subscription_by_id_for_user' in body
