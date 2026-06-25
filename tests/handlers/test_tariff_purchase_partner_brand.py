from __future__ import annotations

from types import SimpleNamespace

from app.handlers.subscription.tariff_purchase_partner import (
    append_brand_prefix_preview,
    build_partner_confirm_body,
    checkout_partner_options,
)


def test_checkout_partner_options_defaults_brand_on_when_set() -> None:
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='mobile_x')
    opts = checkout_partner_options(user, {})
    assert opts['use_brand_prefix'] is True
    assert opts['has_brand_prefix'] is True


def test_append_brand_preview_not_set() -> None:
    from app.localization.texts import get_texts

    texts = get_texts('fa')
    body = append_brand_prefix_preview('base', texts, None)
    assert 'هنوز انتخاب نشده' in body or 'not set' in body.lower()


def test_append_brand_preview_shows_prefix() -> None:
    from app.localization.texts import get_texts

    texts = get_texts('fa')
    body = append_brand_prefix_preview('base', texts, 'mobile_x')
    assert 'mobile_x' in body


def test_build_partner_confirm_body_includes_brand_for_partner() -> None:
    from app.localization.texts import get_texts

    texts = get_texts('fa')
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='mobile_x')
    body = build_partner_confirm_body('base confirm', texts, user, {})
    assert 'mobile_x' in body
    assert body.startswith('base confirm')
