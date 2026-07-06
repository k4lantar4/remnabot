"""Tests for subscription user notification helpers."""

from __future__ import annotations

from types import SimpleNamespace

from app.utils.subscription_user_messages import format_user_tariff_line, format_user_traffic_line


def test_format_user_tariff_line_uses_notify_key():
    texts = SimpleNamespace()

    def _t(key, default=None, **kwargs):
        if key == 'NOTIFY_TARIFF_LINE':
            return '\n📦 سرویس: «{name}»'
        return default

    texts.t = _t
    line = format_user_tariff_line(texts, 'مستقیم | 9سرور همزمان')
    assert 'Тариф' not in line
    assert 'سرویس' in line
    assert 'مستقیم | 9سرور همزمان' in line


def test_format_user_tariff_line_empty_name():
    texts = SimpleNamespace(t=lambda key, default=None, **kw: default)
    assert format_user_tariff_line(texts, '') == ''
    assert format_user_tariff_line(texts, None) == ''


def test_format_user_traffic_line_uses_notify_key():
    texts = SimpleNamespace()

    def _t(key, default=None, **kwargs):
        if key == 'NOTIFY_TRAFFIC_LINE':
            return '\n📊 حجم: {traffic}'
        return default

    texts.t = _t
    line = format_user_traffic_line(texts, 40, 'fa')
    assert '40' in line
    assert 'حجم' in line


def test_format_user_traffic_line_zero_gb():
    texts = SimpleNamespace(t=lambda key, default=None, **kw: default)
    assert format_user_traffic_line(texts, 0, 'fa') == ''
