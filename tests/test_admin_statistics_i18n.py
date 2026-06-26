"""Admin statistics panels must use full *_BODY templates in fa.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_FA = json.loads(
    (Path(__file__).resolve().parents[1] / 'app/localization/locales/fa.json').read_text(encoding='utf-8'),
)

_BODY_PLACEHOLDERS: dict[str, tuple[str, ...]] = {
    'ADMIN_STATS_USERS_BODY': (
        '{total}',
        '{active}',
        '{active_rate}',
        '{blocked}',
        '{today}',
        '{week}',
        '{month}',
        '{growth_rate}',
        '{updated}',
    ),
    'ADMIN_STATS_REVENUE_BODY': (
        '{month_income}',
        '{month_expenses}',
        '{month_profit}',
        '{month_subs}',
        '{today_count}',
        '{today_income}',
        '{all_income}',
        '{all_profit}',
    ),
    'ADMIN_STATS_REFERRALS_BODY': (
        '{with_refs}',
        '{active_refs}',
        '{total_paid}',
        '{today}',
        '{week}',
        '{month}',
        '{avg}',
    ),
    'ADMIN_STATS_SUMMARY_BODY': (
        '{users_total}',
        '{users_active}',
        '{users_month}',
        '{subs_active}',
        '{subs_paid}',
        '{conversion}',
        '{income}',
        '{arpu}',
        '{tx_count}',
        '{sales_month}',
        '{updated}',
    ),
}


def test_admin_stats_body_keys_exist_in_fa_json():
    missing = [key for key in _BODY_PLACEHOLDERS if key not in _FA]
    assert not missing, f'Missing fa.json keys: {missing}'


@pytest.mark.parametrize('key,placeholders', list(_BODY_PLACEHOLDERS.items()))
def test_admin_stats_body_templates_contain_placeholders(key: str, placeholders: tuple[str, ...]):
    value = _FA[key]
    assert isinstance(value, str)
    for placeholder in placeholders:
        assert placeholder in value, f'{key} missing {placeholder}'


def test_admin_stats_short_labels_remain_separate_from_bodies():
    for short_key in (
        'ADMIN_STATS_USERS',
        'ADMIN_STATS_REVENUE',
        'ADMIN_STATS_REFERRALS',
        'ADMIN_STATS_SUMMARY',
    ):
        body_key = f'{short_key}_BODY'
        assert short_key in _FA
        assert body_key in _FA
        assert _FA[short_key] != _FA[body_key]
        assert '{' not in _FA[short_key]
