from __future__ import annotations

from typing import Any

from app.utils.jalali_datetime import format_user_datetime


def _status_emoji(sub: Any) -> str:
    if bool(getattr(sub, 'user_disabled', False)):
        return '⏸'
    actual = getattr(sub, 'actual_status', None)
    if actual in ('active', 'trial'):
        return '🟢'
    if actual == 'limited':
        return '🟡'
    return '🔴'


def _status_label(sub: Any, texts: Any) -> str:
    if bool(getattr(sub, 'user_disabled', False)):
        return texts.t('MY_SUB_STATUS_USER_DISABLED', ' (خاموش شده)')
    actual = getattr(sub, 'actual_status', None)
    if actual == 'expired':
        return texts.t('MY_SUB_STATUS_EXPIRED', ' (Истекла)')
    if actual == 'disabled':
        return texts.t('MY_SUB_STATUS_DISABLED', ' (Отключена)')
    if actual == 'limited':
        return texts.t('MY_SUB_STATUS_LIMITED', ' (Лимит)')
    return ''


USER_UNKNOWN_PREFIX = 'user_unknown_'


def subscription_list_identity(sub: Any, user: Any, texts: Any) -> str:
    del user  # identity A does not use partner brand
    panel = (getattr(sub, 'panel_username', None) or '').strip()
    if panel.startswith(USER_UNKNOWN_PREFIX):
        panel = ''
    if panel:
        return panel
    tariff = getattr(sub, 'tariff', None)
    tariff_name = (
        str(getattr(tariff, 'name', None))
        if tariff and getattr(tariff, 'name', None)
        else texts.t('MY_SUB_DEFAULT_NAME', 'Подписка')
    )
    seq = getattr(sub, 'account_sequence', 1) or 1
    return texts.t('MY_SUB_ACCOUNT_LABEL', '{tariff} #{seq}').format(tariff=tariff_name, seq=seq)


def format_subscription_list_line(
    sub: Any,
    idx: int,
    texts: Any,
    language: str,
    user: Any,
) -> str:
    name = subscription_list_identity(sub, user, texts)
    emoji = _status_emoji(sub)
    label = _status_label(sub, texts)
    if getattr(sub, 'traffic_limit_gb', 0) == 0:
        traffic = '∞'
    else:
        used = f'{sub.traffic_used_gb:.1f}' if getattr(sub, 'traffic_used_gb', None) else '0'
        traffic = f'{used}/{sub.traffic_limit_gb} GB'
    devices = ''
    if getattr(sub, 'device_limit', None) is not None:
        count = texts.t('MY_SUB_DEVICES_COUNT_SHORT', '{count} устр.').format(count=sub.device_limit)
        devices = count
    end_date = (
        format_user_datetime(sub.end_date, language=language, fmt='%d.%m.%Y') if getattr(sub, 'end_date', None) else '—'
    )
    parts = [f'{emoji} <b>{idx}. {name}</b>{label}']
    parts.append(texts.t('MY_SUB_TRAFFIC_LINE', '   📊 Трафик: {traffic}').format(traffic=traffic))
    if devices:
        parts.append(texts.t('MY_SUB_DEVICES_LINE', '   📱 Устройства: {devices}').format(devices=devices))
    parts.append(texts.t('MY_SUB_UNTIL_LINE', '   📅 До: {end_date}').format(end_date=end_date))
    return '\n'.join(parts)


def _matches(sub: Any, query: str, texts: Any, user: Any) -> bool:
    q = (query or '').strip().lower()
    if not q:
        return True
    identity = subscription_list_identity(sub, user, texts).lower()
    if q in identity:
        return True
    panel = (getattr(sub, 'panel_username', None) or '').strip().lower()
    if panel and q in panel:
        return True
    if q in str(getattr(sub, 'id', '')):
        return True
    serial = (getattr(sub, 'remnawave_short_id', '') or '').strip().lower()
    if serial and q == serial:
        return True
    note = (getattr(sub, 'purchase_note', None) or '').strip().lower()
    if note and q in note:
        return True
    tariff = getattr(sub, 'tariff', None)
    tariff_name = (getattr(tariff, 'name', None) or '').strip().lower()
    return bool(tariff_name and q in tariff_name)


def filter_subscriptions_by_query(
    subscriptions: list,
    query: str,
    texts: Any,
    user: Any,
) -> list:
    q = (query or '').strip()
    if not q:
        return list(subscriptions)
    return [s for s in subscriptions if _matches(s, q, texts, user)]
