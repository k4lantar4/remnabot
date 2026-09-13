"""Success responses of cabinet purchases put the charged amount on the wire scale.

The cabinet reads every ``*_kopeks`` price field on the catalog wire scale (x100, or Toman 1:1 under
``X-Amount-Scale: toman``). The renew / traffic / countries / devices / tariff-switch / tariff-purchase
success bodies used to return the stored Toman bare, so a result screen that rendered them would show
the amount 100x too small. Each body now goes through ``paid_result_fields`` (the charged amount on the
wire plus ``amount_paid_toman`` and the subscription it applied to), and every discount field next to it
through ``wire_catalog_kopeks``. ``balance_kopeks`` / ``new_balance_kopeks`` stay Toman, like everywhere.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.cabinet.routes.subscription_modules import devices, purchase, renewal, servers, tariff_switch, traffic
from app.cabinet.routes.subscription_modules.helpers import paid_result_fields
from app.utils.wire_scale import TOMAN_WIRE, reset_wire_scale, use_wire_scale


_END = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def test_paid_result_fields_scale_the_amount_and_name_the_subscription() -> None:
    fields = paid_result_fields(10_000, subscription=SimpleNamespace(id=42, end_date=_END), tariff_name='Pro')

    assert fields == {
        'amount_paid_kopeks': 1_000_000,
        'amount_paid_toman': 10_000,
        'subscription_id': 42,
        'new_end_date': _END.isoformat(),
        'tariff_name': 'Pro',
    }


def test_paid_result_fields_follow_the_negotiated_toman_scale() -> None:
    token = use_wire_scale(TOMAN_WIRE)
    try:
        fields = paid_result_fields(
            10_000, subscription=SimpleNamespace(id=1, end_date=None), amount_key='charged_kopeks'
        )
    finally:
        reset_wire_scale(token)

    assert fields['charged_kopeks'] == 10_000
    assert fields['amount_paid_toman'] == 10_000
    assert fields['new_end_date'] is None
    assert 'amount_paid_kopeks' not in fields


# Endpoint → (module, how many success bodies it builds, amount fields that must be wire-scaled).
_ENDPOINTS = {
    'renew_subscription': (renewal, 1, {'promo_discount_amount_kopeks', 'original_price_kopeks'}),
    'purchase_traffic': (traffic, 1, {'discount_kopeks', 'base_price_kopeks'}),
    'switch_traffic_package': (traffic, 1, set()),
    'update_countries': (servers, 1, set()),
    'purchase_devices_legacy': (devices, 1, {'discount_kopeks', 'base_price_kopeks'}),
    'switch_tariff': (tariff_switch, 2, {'discount_kopeks', 'base_charged_kopeks'}),
    'purchase_tariff': (
        purchase,
        1,
        {
            'original_price_kopeks',
            'discount_amount_kopeks',
            'promo_offer_discount_amount_kopeks',
            'price_before_promo_offer_kopeks',
        },
    ),
}

_BARE_AMOUNT_KEYS = {'amount_paid_kopeks', 'charged_kopeks', 'charged_amount'}


def _function_node(module, name: str) -> ast.AsyncFunctionDef:
    tree = ast.parse(inspect.getsource(module))
    return next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == name)


def _is_call_to(node: ast.AST, func_name: str) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == func_name


def _success_bodies(fn: ast.AST) -> list[ast.Dict]:
    """Dict literals that spread ``**paid_result_fields(...)`` — the success bodies (402 details don't)."""
    return [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Dict)
        and any(
            key is None and _is_call_to(value, 'paid_result_fields')
            for key, value in zip(node.keys, node.values, strict=True)
        )
    ]


def _assigned_amounts(fn: ast.AST, bodies: list[ast.Dict]):
    """Yield (key, value) for each string key of a success body and each ``response['key'] = value``."""
    for body in bodies:
        for key, value in zip(body.keys, body.values, strict=True):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                yield key.value, value
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == 'response'
                    and isinstance(target.slice, ast.Constant)
                ):
                    yield target.slice.value, node.value


@pytest.mark.parametrize('endpoint', sorted(_ENDPOINTS))
def test_success_body_puts_every_amount_on_the_wire_scale(endpoint: str) -> None:
    module, bodies, discount_keys = _ENDPOINTS[endpoint]
    fn = _function_node(module, endpoint)

    success_bodies = _success_bodies(fn)
    assert len(success_bodies) == bodies, f'{endpoint}: every success body spreads **paid_result_fields(...)'

    for key, value in _assigned_amounts(fn, success_bodies):
        if key in _BARE_AMOUNT_KEYS:
            pytest.fail(f'{endpoint}: {key!r} is set directly; paid_result_fields owns it')
        if key in discount_keys:
            assert _is_call_to(value, 'wire_catalog_kopeks'), f'{endpoint}: {key!r} must go through wire_catalog_kopeks'
