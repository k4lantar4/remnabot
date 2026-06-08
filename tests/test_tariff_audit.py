"""Tests for tools/tariff_audit.py — pure-function unit tests (no DB)."""
from __future__ import annotations

from tools.tariff_audit import build_tariff_audit_report

BASIC = '66edb525-13d4-45f0-b7a6-c62578f4021c'
PREMIUM = '825696b5-348b-4e84-b71e-d91f21c399a2'


def test_tariff_audit_reports_three_rows():
    report = build_tariff_audit_report([
        {'id': 1, 'name': 'Стандартный', 'allowed_squads': [BASIC], 'is_active': True},
        {'id': 2, 'name': 'Premium', 'allowed_squads': [PREMIUM], 'is_active': True},
        {'id': 3, 'name': 'Basic', 'allowed_squads': [BASIC], 'is_active': True},
    ])
    assert report['tariff_count'] == 3
    assert report['tariff_1_missing_premium_squad'] is True


def test_tariff_1_has_both_squads():
    report = build_tariff_audit_report([
        {'id': 1, 'name': 'استاندارد', 'allowed_squads': [BASIC, PREMIUM], 'is_active': True},
        {'id': 2, 'name': 'پریمیوم', 'allowed_squads': [PREMIUM], 'is_active': True},
        {'id': 3, 'name': 'پایه', 'allowed_squads': [BASIC], 'is_active': True},
    ])
    assert report['tariff_1_missing_premium_squad'] is False
    assert report['tariff_1_missing_basic_squad'] is False


def test_missing_tariff_rows():
    report = build_tariff_audit_report([
        {'id': 1, 'name': 'Стандартный', 'allowed_squads': [BASIC], 'is_active': True},
    ])
    assert report['tariff_count'] == 1
    assert report['missing_tariff_ids'] == [2, 3]


def test_placeholder_names_detected():
    report = build_tariff_audit_report([
        {'id': 1, 'name': 'Стандартный', 'allowed_squads': [BASIC, PREMIUM], 'is_active': True},
        {'id': 2, 'name': 'Premium', 'allowed_squads': [PREMIUM], 'is_active': True},
        {'id': 3, 'name': 'Basic', 'allowed_squads': [BASIC], 'is_active': True},
    ])
    assert 2 in report['placeholder_name_ids']
    assert 3 in report['placeholder_name_ids']


def test_persian_names_not_placeholders():
    report = build_tariff_audit_report([
        {'id': 1, 'name': 'استاندارد', 'allowed_squads': [BASIC, PREMIUM], 'is_active': True},
        {'id': 2, 'name': 'پریمیوم', 'allowed_squads': [PREMIUM], 'is_active': True},
        {'id': 3, 'name': 'پایه', 'allowed_squads': [BASIC], 'is_active': True},
    ])
    assert report['placeholder_name_ids'] == []


def test_all_ok_report():
    report = build_tariff_audit_report([
        {'id': 1, 'name': 'استاندارد', 'allowed_squads': [BASIC, PREMIUM], 'is_active': True},
        {'id': 2, 'name': 'پریمیوم', 'allowed_squads': [PREMIUM], 'is_active': True},
        {'id': 3, 'name': 'پایه', 'allowed_squads': [BASIC], 'is_active': True},
    ])
    assert report['all_ok'] is True
