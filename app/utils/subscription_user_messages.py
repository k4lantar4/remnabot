"""Shared user-facing subscription notification fragments."""

from __future__ import annotations


def format_user_tariff_line(texts, tariff_name: str | None) -> str:
    """Localized tariff/service line for Telegram user notifications."""
    if not tariff_name:
        return ''
    return texts.t('NOTIFY_TARIFF_LINE', '\n📦 Тариф: «{name}»').format(name=tariff_name)


def format_user_traffic_line(texts, traffic_gb: int, language: str) -> str:
    """Localized traffic/volume line for Telegram user notifications."""
    if not traffic_gb:
        return ''
    from app.utils.formatting import format_traffic

    traffic = format_traffic(traffic_gb, language)
    return texts.t('NOTIFY_TRAFFIC_LINE', '\n📊 Трафик: {traffic}').format(traffic=traffic)
