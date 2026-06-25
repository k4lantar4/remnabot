"""Tests for RemnaWave panel identity helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import settings
from app.utils.remnawave_panel_identity import (
    PANEL_NOTE_DELIMITER,
    build_panel_description,
    build_subscription_panel_username,
    parse_purchase_note_from_panel_description,
    resolve_remnawave_panel_description,
    validate_brand_prefix,
)


def test_build_description_appends_note() -> None:
    result = build_panel_description(
        auto_description='Bot user: Ali @ali',
        purchase_note='فروشگاه موبایل',
    )
    assert result.endswith('فروشگاه موبایل')
    assert PANEL_NOTE_DELIMITER in result


def test_build_description_without_note() -> None:
    auto = 'Bot user: Ali'
    assert build_panel_description(auto_description=auto, purchase_note=None) == auto
    assert build_panel_description(auto_description=auto, purchase_note='   ') == auto


def test_parse_description_extracts_note() -> None:
    full = 'Bot user: Ali\n---\nفروشگاه موبایل'
    assert parse_purchase_note_from_panel_description(full) == 'فروشگاه موبایل'


def test_parse_description_returns_none_without_delimiter() -> None:
    assert parse_purchase_note_from_panel_description('Bot user: Ali') is None
    assert parse_purchase_note_from_panel_description(None) is None


def test_resolve_remnawave_panel_description_merges_subscription_note() -> None:
    user = SimpleNamespace(
        full_name='Ali',
        username='ali',
        telegram_id=123,
        email=None,
        id=1,
    )
    subscription = SimpleNamespace(purchase_note='Partner shop note')
    result = resolve_remnawave_panel_description(settings, user=user, subscription=subscription)
    assert 'Partner shop note' in result
    assert PANEL_NOTE_DELIMITER in result


def test_brand_prefix_username() -> None:
    user = SimpleNamespace(
        full_name='Partner',
        username='partner',
        telegram_id=999,
        email=None,
        id=5,
        panel_brand_prefix='Mobile_x_shop',
        is_partner=True,
        partner_status='approved',
    )
    result = build_subscription_panel_username(settings, user, suffix='_1042')
    assert result.startswith('Mobile_x_shop_')
    assert result.endswith('1042')
    assert len(result) <= settings.REMNAWAVE_USERNAME_MAX_LENGTH


def test_no_prefix_falls_back_to_template() -> None:
    user = SimpleNamespace(
        full_name='User',
        username='user1',
        telegram_id=111,
        email=None,
        id=2,
        panel_brand_prefix=None,
        is_partner=False,
        partner_status='none',
    )
    expected = settings.build_remnawave_subscription_username(
        full_name=user.full_name,
        username=user.username,
        telegram_id=user.telegram_id,
        email=user.email,
        user_id=user.id,
        suffix='_xyz',
    )
    assert build_subscription_panel_username(settings, user, suffix='_xyz') == expected


def test_validate_brand_prefix() -> None:
    assert validate_brand_prefix('Mobile_x_shop') == 'Mobile_x_shop'
    assert validate_brand_prefix('ab') is None
    assert validate_brand_prefix('bad space') is None
