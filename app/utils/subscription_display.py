from __future__ import annotations

import html
from typing import Any


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


def format_subscription_notify_context(subscription: Any, user: Any, texts: Any) -> dict[str, str]:
    """Build subscription identity block for user notifications (multi-sub / partner)."""
    from app.config import settings

    account = subscription_account_label(subscription, texts)
    lines: list[str] = []

    note = (getattr(subscription, 'purchase_note', None) or '').strip()
    serial = (getattr(subscription, 'remnawave_short_id', '') or '').strip()
    show_identity = settings.is_multi_tariff_enabled() or bool(note) or (
        getattr(user, 'is_partner', False) and serial.isdigit()
    )

    if show_identity:
        lines.append(
            texts.t('NOTIFY_SUBSCRIPTION_LINE', '🔢 Подписка: <b>{account}</b>').format(
                account=html.escape(account)
            )
        )

    if getattr(user, 'is_partner', False) and serial.isdigit():
        lines.append(
            texts.t('MY_SUB_LIST_PUBLIC_SERIAL', 'شماره {serial}').format(serial=html.escape(serial))
        )

    if note:
        trimmed = note if len(note) <= 80 else note[:80] + '…'
        lines.append(
            texts.t('MY_SUB_DETAIL_PURCHASE_NOTE', '📝 Note: {note}').format(note=html.escape(trimmed))
        )

    subscription_line = '\n'.join(lines)
    if subscription_line:
        subscription_line = '\n' + subscription_line

    tariff_name = ''
    if getattr(subscription, 'tariff', None):
        tariff_name = subscription.tariff.name

    return {
        'account': account,
        'subscription_line': subscription_line,
        'tariff_name': tariff_name,
    }
