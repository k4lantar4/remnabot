"""One reminder per user, not per subscription.

A user (or partner) holding many subscriptions used to get a separate Telegram message for every
subscription at every checkpoint. The monitoring and daily-charge services group the subscriptions
that hit a checkpoint with these helpers and send one digest; ``sent_notifications`` dedup rows stay
per subscription. Plan: ``docs/superpowers/plans/2026-09-12-user-notifications-and-flow-results.md``,
task 8 (rules R2.1-R2.8).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from aiogram.types import InlineKeyboardMarkup

from app.config import QuietHours, settings
from app.utils.jalali_datetime import format_user_datetime, is_jalali_language
from app.utils.miniapp_buttons import build_miniapp_or_callback_button
from app.utils.timezone import to_local_datetime


@dataclass(frozen=True)
class AutopayFailure:
    """A failed autopay charge waiting to be reported; primitives only, safe after a rollback."""

    subscription_id: int
    tariff_name: str | None
    end_date: datetime | None
    required: int
    is_final: bool


def collect_user_batches(items: Iterable[Any]) -> dict[int, list[Any]]:
    """Group subscriptions by ``user_id``, each group ordered by end date (soonest first)."""
    batches: dict[int, list[Any]] = {}
    for item in items:
        batches.setdefault(item.user_id, []).append(item)
    far_future = datetime.max.replace(tzinfo=None)
    for subs in batches.values():
        subs.sort(key=lambda s: s.end_date.replace(tzinfo=None) if s.end_date else far_future)
    return batches


def is_abandoned(subscription: Any, now: datetime, abandon_days: int) -> bool:
    """True once a subscription has been expired for more than ``abandon_days`` (R2.3)."""
    end_date = getattr(subscription, 'end_date', None)
    if end_date is None:
        return False
    return now - end_date > timedelta(days=abandon_days)


def pick_followup_subscription(subscriptions: Sequence[Any]) -> tuple[Any, int]:
    """The most recently expired subscription carries the follow-up series; the rest are counted (R2.4)."""
    latest = max(subscriptions, key=lambda s: s.end_date)
    return latest, len(subscriptions) - 1


def should_hold_for_quiet_hours(notice_type: str, now_utc: datetime, quiet: QuietHours) -> bool:
    """Whether a scheduled notice of ``notice_type`` waits for the end of the quiet window (R2.8).

    The window is local time (``settings.TIMEZONE``) and may cross midnight. A held notice is not
    queued: its dedup row / rate-limit key is simply not written, so the first cycle after the window
    picks it up again.
    """
    if not quiet.enabled or notice_type not in quiet.types or quiet.start == quiet.end:
        return False
    local_now = to_local_datetime(now_utc).time().replace(tzinfo=None)
    if quiet.start < quiet.end:
        return quiet.start <= local_now < quiet.end
    return local_now >= quiet.start or local_now < quiet.end


def tariff_label(subscription: Any) -> str:
    tariff = getattr(subscription, 'tariff', None)
    return tariff.name if tariff else f'#{subscription.id}'


def user_date(user: Any, dt: datetime | None) -> str:
    language = getattr(user, 'language', None) or settings.DEFAULT_LANGUAGE
    fmt = '%Y/%m/%d' if is_jalali_language(language) else '%d.%m.%Y'
    return format_user_datetime(dt, language=language, fmt=fmt, na_placeholder='—')


def _limited_lines(texts: Any, lines: list[str], limit: int) -> str:
    shown = lines[:limit]
    if len(lines) > limit:
        shown.append(texts.t('NOTIFY_DIGEST_MORE', '…and {count} more').format(count=len(lines) - limit))
    return '\n'.join(shown)


def _subscriptions_keyboard(texts: Any, *, topup_first: bool = False) -> InlineKeyboardMarkup:
    subscriptions = build_miniapp_or_callback_button(
        text=texts.t('NOTIFY_DIGEST_BTN_SUBSCRIPTIONS', '📱 My subscriptions'),
        callback_data='menu_subscription',
        cabinet_path='/subscriptions',
    )
    topup = build_miniapp_or_callback_button(
        text=texts.t('BALANCE_TOPUP', '💳 Top up balance'),
        callback_data='balance_topup',
    )
    rows = [[topup], [subscriptions]] if topup_first else [[subscriptions], [topup]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_expiring_digest(
    texts: Any,
    user: Any,
    subscriptions: Sequence[Any],
    quotes: dict[int, int | None],
    days: int,
    *,
    limit: int,
) -> tuple[str, InlineKeyboardMarkup]:
    """Several subscriptions reaching the same expiry checkpoint, in one message (R2.1, R2.2)."""
    from app.utils.formatters import format_days_declension

    lines = []
    for sub in subscriptions:
        price = quotes.get(sub.id)
        lines.append(
            texts.t('NOTIFY_DIGEST_LINE', '• {tariff} — until {end_date} — {price}').format(
                tariff=tariff_label(sub),
                end_date=user_date(user, sub.end_date),
                price=settings.format_price(price) if price is not None else '—',
            )
        )
    text = texts.t(
        'NOTIFY_DIGEST_EXPIRING',
        '⚠️ <b>{count} subscriptions expire within {days_text}</b>\n\n{lines}',
    ).format(
        count=len(subscriptions),
        days_text=format_days_declension(days, getattr(user, 'language', None) or settings.DEFAULT_LANGUAGE),
        lines=_limited_lines(texts, lines, limit),
    )
    return text, _subscriptions_keyboard(texts)


def build_expired_digest(
    texts: Any, user: Any, subscriptions: Sequence[Any], *, limit: int
) -> tuple[str, InlineKeyboardMarkup]:
    """Several subscriptions that expired in the same cycle, in one message (R2.1)."""
    lines = [
        texts.t('NOTIFY_DIGEST_LINE_NO_PRICE', '• {tariff} — {end_date}').format(
            tariff=tariff_label(sub), end_date=user_date(user, sub.end_date)
        )
        for sub in subscriptions
    ]
    text = texts.t('NOTIFY_DIGEST_EXPIRED', '⛔ <b>{count} subscriptions have expired</b>\n\n{lines}').format(
        count=len(subscriptions), lines=_limited_lines(texts, lines, limit)
    )
    return text, _subscriptions_keyboard(texts)


def other_expired_line(texts: Any, count: int) -> str:
    """Suffix for a follow-up that speaks for one subscription while others lapsed too (R2.4)."""
    if count <= 0:
        return ''
    return texts.t('NOTIFY_OTHER_EXPIRED', '\n\nYou have {count} other expired subscriptions too.').format(count=count)


def build_daily_charge_digest(texts: Any, charges: Sequence[tuple[str, int]], *, balance: int, limit: int) -> str:
    """One message per user per daily-charge run, listing each charged subscription (R2.7)."""
    lines = [
        texts.t('NOTIFY_DIGEST_DAILY_CHARGE_LINE', '• {tariff}: {amount}').format(
            tariff=name, amount=settings.format_price(amount)
        )
        for name, amount in charges
    ]
    return texts.t(
        'NOTIFY_DIGEST_DAILY_CHARGE',
        '💳 <b>Daily charge for {count} subscriptions</b>\n\n{lines}\n\nTotal: {total}\nBalance left: {balance}',
    ).format(
        count=len(charges),
        lines=_limited_lines(texts, lines, limit),
        total=settings.format_price(sum(amount for _, amount in charges)),
        balance=settings.format_balance(balance),
    )


def build_traffic_digest(texts: Any, items: Sequence[tuple[str, float, int, float]], *, limit: int) -> str:
    """Traffic warnings for several subscriptions of one user (R2.7)."""
    lines = [
        texts.t('NOTIFY_DIGEST_TRAFFIC_LINE', '• {tariff}: {used} / {limit} GB ({percent}%)').format(
            tariff=name, used=f'{used:.1f}', limit=traffic_limit, percent=f'{percent:.0f}'
        )
        for name, used, traffic_limit, percent in items
    ]
    return texts.t(
        'NOTIFY_DIGEST_TRAFFIC', '⚠️ <b>Traffic almost used up on {count} subscriptions</b>\n\n{lines}'
    ).format(count=len(items), lines=_limited_lines(texts, lines, limit))


def build_autopay_failed_digest(
    texts: Any, user: Any, failures: Sequence[AutopayFailure], *, balance: int, limit: int
) -> tuple[str, InlineKeyboardMarkup]:
    """Autopay failures of several subscriptions of one user, in one message (R2.1)."""
    lines = [
        texts.t('NOTIFY_DIGEST_LINE', '• {tariff} — until {end_date} — {price}').format(
            tariff=failure.tariff_name or f'#{failure.subscription_id}',
            end_date=user_date(user, failure.end_date),
            price=settings.format_price(failure.required),
        )
        for failure in failures
    ]
    text = texts.t(
        'NOTIFY_DIGEST_AUTOPAY_FAILED',
        '❌ <b>Autopay failed for {count} subscriptions</b>\n\n{lines}\n\nBalance: {balance}\nRequired: {required}',
    ).format(
        count=len(failures),
        lines=_limited_lines(texts, lines, limit),
        balance=settings.format_balance(balance),
        required=settings.format_price(sum(failure.required for failure in failures)),
    )
    return text, _subscriptions_keyboard(texts, topup_first=True)
