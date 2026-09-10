"""Daily-charge sites upstream's guards don't list.

Upstream 564fec3e routed three daily charges (scheduler, cabinet resume, Mini App resume)
through ``should_reset_traffic_on_daily_charge``. Two more paths charge the daily fee and
still hard-coded "never reset": the bot's resume button (which also resumes LIMITED
subscriptions) and the resume after a balance top-up. With ``RESET_TRAFFIC_ON_PAYMENT`` on,
the same paid resume reset the counter in the cabinet but left a LIMITED user limited in the bot.

Upstream 968687ce made ``PricingEngine.daily_group_price`` the one per-day price; every
recurring daily charge must use it rather than recomputing the group discount by hand.
"""

from __future__ import annotations

import ast

import pytest

from tests.services.test_daily_charge_reset_policy_guard import (
    DAILY_CHARGE_SITES,
    POLICY,
    ROOT,
    _find_function,
    _reset_traffic_arguments,
)


FORK_DAILY_CHARGE_SITES = {
    'app/handlers/subscription/purchase.py': 'handle_toggle_daily_subscription_pause',
    'app/services/subscription_auto_purchase_service.py': 'try_resume_disabled_daily_after_topup',
}


@pytest.mark.parametrize(('relative', 'function_name'), FORK_DAILY_CHARGE_SITES.items())
def test_fork_daily_charge_site_asks_the_policy(relative, function_name):
    func = _find_function(ROOT / relative, function_name)
    names = {node.id for node in ast.walk(func) if isinstance(node, ast.Name)}
    assert POLICY in names, f'{relative}:{function_name} does not ask {POLICY}()'

    arguments = _reset_traffic_arguments(func)
    assert arguments, f'{relative}:{function_name}: no panel sync with reset_traffic; guard is stale'
    assert any(not isinstance(value, ast.Constant) for value in arguments), (
        f'{relative}:{function_name}: every panel sync hard-codes reset_traffic'
    )
    constants = [value for value in arguments if isinstance(value, ast.Constant)]
    assert all(value.value is False for value in constants)
    # One constant is allowed: the squad follow-up PATCH right after creating the panel user.
    assert len(constants) <= 1


@pytest.mark.parametrize(
    ('relative', 'function_name'),
    list(DAILY_CHARGE_SITES.items()) + list(FORK_DAILY_CHARGE_SITES.items()),
)
def test_daily_charge_prices_through_daily_group_price(relative, function_name):
    func = _find_function(ROOT / relative, function_name)
    attrs = {node.attr for node in ast.walk(func) if isinstance(node, ast.Attribute)}
    assert 'daily_group_price' in attrs, f'{relative}:{function_name} recomputes the daily price by hand'
    assert 'get_discount_percent' not in attrs, f'{relative}:{function_name} still reads the group percent itself'
