from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import Any

from app.utils.formatters import format_days_declension
from app.utils.formatting import format_traffic
from app.utils.jalali_datetime import format_user_datetime


def subscription_account_label(subscription: Any, texts: Any) -> str:
    """User-facing subscription label.

    Legacy migrated subs: show cached RemnaWave panel username (e.g. Germany(2)-134500).
    New subs: fall back to {tariff} #{account_sequence}.
    """
    panel_username = (getattr(subscription, 'panel_username', None) or '').strip()
    if panel_username.startswith('user_unknown_'):
        panel_username = ''
    if panel_username:
        return panel_username

    tariff_name = (
        subscription.tariff.name
        if getattr(subscription, 'tariff', None)
        else texts.t('MY_SUB_DEFAULT_NAME', 'Подписка')
    )
    seq = getattr(subscription, 'account_sequence', 1) or 1
    return texts.t('MY_SUB_ACCOUNT_LABEL', '{tariff} #{seq}').format(tariff=tariff_name, seq=seq)


def _format_notify_traffic(subscription: Any, texts: Any, language: str) -> str:
    limit = int(getattr(subscription, 'traffic_limit_gb', 0) or 0)
    if limit == 0:
        traffic = '∞'
    else:
        used = float(getattr(subscription, 'traffic_used_gb', 0) or 0)
        traffic = f'{used:.1f}/{format_traffic(limit, language)}'
    return texts.t('NOTIFY_TRAFFIC_LINE', 'حجم: {traffic}').format(traffic=traffic)


def _format_notify_validity(subscription: Any, texts: Any, language: str) -> str:
    end_date = getattr(subscription, 'end_date', None)
    if not end_date:
        return texts.t('NOTIFY_VALIDITY_UNKNOWN', 'اعتبار: —')

    formatted_date = format_user_datetime(end_date, language=language, fmt='%d.%m.%Y')
    now = datetime.now(UTC)
    end_aware = end_date if end_date.tzinfo else end_date.replace(tzinfo=UTC)
    days_left = int(getattr(subscription, 'days_left', 0) or 0)

    if end_aware <= now or days_left <= 0:
        return texts.t('NOTIFY_VALIDITY_EXPIRED', 'منقضی شده: {end_date}').format(end_date=formatted_date)

    days_text = format_days_declension(days_left, language)
    return texts.t('NOTIFY_VALIDITY_LINE', 'اعتبار: {end_date} ({days_left})').format(
        end_date=formatted_date,
        days_left=days_text,
    )


def _format_notify_extras(subscription: Any, user: Any, texts: Any) -> str:
    parts: list[str] = []
    serial = (getattr(subscription, 'remnawave_short_id', '') or '').strip()
    if getattr(user, 'is_partner', False) and serial.isdigit():
        parts.append(
            texts.t('MY_SUB_LIST_PUBLIC_SERIAL', 'شماره {serial}').format(serial=html.escape(serial))
        )
    note = (getattr(subscription, 'purchase_note', None) or '').strip()
    if note:
        trimmed = note if len(note) <= 60 else note[:60] + '…'
        parts.append(
            texts.t('MY_SUB_DETAIL_PURCHASE_NOTE', '📝 یادداشت: {note}').format(note=html.escape(trimmed))
        )
    if not parts:
        return ''
    return '\n' + '\n'.join(parts)


def format_subscription_notify_card(
    subscription: Any,
    user: Any,
    texts: Any,
    *,
    language: str | None = None,
) -> dict[str, str]:
    """Compact subscription identity block for user notifications."""
    lang = language or getattr(user, 'language', None) or getattr(texts, 'language', 'ru') or 'ru'
    account = subscription_account_label(subscription, texts)
    traffic_line = _format_notify_traffic(subscription, texts, lang)
    validity_line = _format_notify_validity(subscription, texts, lang)
    extras = _format_notify_extras(subscription, user, texts)

    subscription_card = texts.t(
        'NOTIFY_SUBSCRIPTION_CARD',
        '👤 <b>{account}</b>\n📊 {traffic_line}\n📅 {validity_line}{extras}',
    ).format(
        account=html.escape(account),
        traffic_line=traffic_line,
        validity_line=validity_line,
        extras=extras,
    )
    subscription_card = '\n' + subscription_card

    tariff_name = ''
    if getattr(subscription, 'tariff', None):
        tariff_name = subscription.tariff.name

    return {
        'account': account,
        'subscription_card': subscription_card,
        'tariff_name': tariff_name,
    }


def format_subscription_notify_context(subscription: Any, user: Any, texts: Any) -> dict[str, str]:
    """Backward-compatible wrapper — prefer subscription_card."""
    lang = getattr(user, 'language', None) or getattr(texts, 'language', 'ru') or 'ru'
    ctx = format_subscription_notify_card(subscription, user, texts, language=lang)
    return {
        'account': ctx['account'],
        'subscription_line': ctx['subscription_card'],
        'subscription_card': ctx['subscription_card'],
        'tariff_name': ctx['tariff_name'],
    }
