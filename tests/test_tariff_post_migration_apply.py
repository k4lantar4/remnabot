"""Tests for tools/tariff_post_migration_apply.py — pure-function unit tests."""
from __future__ import annotations

from tools.tariff_post_migration_apply import build_tariff_updates

BASIC = '66edb525-13d4-45f0-b7a6-c62578f4021c'
PREMIUM = '825696b5-348b-4e84-b71e-d91f21c399a2'


def _make_rows():
    return [
        {'id': 1, 'name': 'Стандартный', 'allowed_squads': [BASIC], 'show_in_gift': False, 'tier_level': 1, 'display_order': 0},
        {'id': 2, 'name': 'Premium', 'allowed_squads': [PREMIUM], 'show_in_gift': False, 'tier_level': 1, 'display_order': 2},
        {'id': 3, 'name': 'Basic', 'allowed_squads': [BASIC], 'show_in_gift': False, 'tier_level': 1, 'display_order': 3},
    ]


def test_build_tariff_updates_returns_three_patches():
    patches = build_tariff_updates(_make_rows())
    assert len(patches) == 3
    ids = {p['id'] for p in patches}
    assert ids == {1, 2, 3}


def test_tariff_1_gets_both_squads():
    patches = build_tariff_updates(_make_rows())
    t1 = next(p for p in patches if p['id'] == 1)
    assert BASIC in t1['allowed_squads']
    assert PREMIUM in t1['allowed_squads']


def test_tariff_1_persian_name():
    patches = build_tariff_updates(_make_rows())
    t1 = next(p for p in patches if p['id'] == 1)
    assert t1['name'] == 'استاندارد'


def test_tariff_2_persian_name_and_premium_only():
    patches = build_tariff_updates(_make_rows())
    t2 = next(p for p in patches if p['id'] == 2)
    assert t2['name'] == 'پریمیوم'
    assert t2['allowed_squads'] == [PREMIUM]
    assert t2['show_in_gift'] is False
    assert t2['tier_level'] == 2


def test_tariff_3_persian_name_and_basic_only():
    patches = build_tariff_updates(_make_rows())
    t3 = next(p for p in patches if p['id'] == 3)
    assert t3['name'] == 'پایه'
    assert t3['allowed_squads'] == [BASIC]
    assert t3['show_in_gift'] is False
    assert t3['tier_level'] == 1


def test_tariff_1_show_in_gift_true():
    patches = build_tariff_updates(_make_rows())
    t1 = next(p for p in patches if p['id'] == 1)
    assert t1['show_in_gift'] is True


def test_no_patch_if_already_correct():
    """Rows that already match target produce empty diff fields (still included for idempotency)."""
    already_correct = [
        {'id': 1, 'name': 'استاندارد', 'allowed_squads': [BASIC, PREMIUM], 'show_in_gift': True, 'tier_level': 1, 'display_order': 0},
        {'id': 2, 'name': 'پریمیوم', 'allowed_squads': [PREMIUM], 'show_in_gift': False, 'tier_level': 2, 'display_order': 2},
        {'id': 3, 'name': 'پایه', 'allowed_squads': [BASIC], 'show_in_gift': False, 'tier_level': 1, 'display_order': 1},
    ]
    patches = build_tariff_updates(already_correct)
    for p in patches:
        assert p['changed'] is False
