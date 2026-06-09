from __future__ import annotations

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
