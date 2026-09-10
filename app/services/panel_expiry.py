"""The ``expireAt`` the bot sends to the Remnawave panel.

One rule for every panel write point. Taken from upstream's
``app/services/panel_sync/expiry.py`` (39097eb9 + 7816e1e9, v4.8.0) including the
clock-skew correction of upstream dev 3513e1db — the rule only, not upstream's
``panel_sync`` package.

What the panel accepts (its own contract, identical in 3.0.0 and 3.4.3):

* ``POST /api/users`` (create) accepts ANY date, past included;
* ``PATCH /api/users`` (update) rejects a past date ("Expiration date cannot be in
  the past") — and judges "past" by the PANEL's clock, not the bot's.

Hence: send the real date wherever the panel takes it; where it doesn't, choose
between "leave the panel alone" and "clear it with the nearest allowed moment".
Access of an expired subscription is closed by the DISABLED status, never by the
date, so the date can stay truthful.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from app.external.remnawave_api import RemnaWaveAPIError, is_expire_in_past_error
from app.utils.timezone import panel_datetime_to_utc


logger = structlog.get_logger(__name__)

#: Nearest future used to clear the date of an expired subscription. One minute was
#: not enough: with the bot's clock three minutes behind the panel, the panel read
#: "now + 1 min" as past and rejected it (reproduced by upstream, 3513e1db).
MINIMUM_FUTURE = timedelta(minutes=5)

#: Second attempt when the panel still says "past" — the clocks are further apart
#: than usual, so this also logs a warning for the operator to fix NTP.
SKEW_RETRY_MARGIN = timedelta(minutes=15)

#: A panel date this close to "now" is our own clearing date. Without this window the
#: next sync would push it forward again — which is exactly the "expired a minute
#: ago" on every run this rule exists to stop. Wider than the retry margin, because
#: the retry date is ours too.
ALREADY_EXTINGUISHED = SKEW_RETRY_MARGIN + timedelta(minutes=4)


def panel_expire_at(
    end_date: datetime,
    *,
    is_active: bool,
    creating: bool,
    now: datetime | None = None,
    panel_current: datetime | None = None,
) -> datetime | None:
    """What to put into the panel's ``expireAt``; ``None`` means don't send the field.

    * end date in the future -> the end date itself, for live and blocked
      subscriptions alike;
    * create -> the real end date, even a past one;
    * update of an expired subscription -> depends on what the panel holds now
      (``panel_current``, ``None`` = unknown): past or unknown -> leave it; future
      -> clear it once with the nearest allowed moment.
    """
    moment = now or datetime.now(UTC)
    if is_active or panel_datetime_to_utc(end_date) > moment:
        return end_date
    if creating:
        return end_date
    return stale_panel_expire_at(panel_current, end_date=end_date, now=moment)


def stale_panel_expire_at(
    panel_current: datetime | None,
    *,
    end_date: datetime,
    now: datetime | None = None,
) -> datetime | None:
    """The date that clears a still-future panel date of an expired subscription.

    ``None`` — leave the panel alone. Only an already expired end date is ever
    cleared: a blocked user with time left keeps the real date they paid for.
    """
    if not isinstance(panel_current, datetime):
        # Unknown (or not a date at all): never guess, leave the panel alone.
        return None
    moment = now or datetime.now(UTC)
    if panel_datetime_to_utc(end_date) > moment:
        return None
    if panel_datetime_to_utc(panel_current) <= moment + ALREADY_EXTINGUISHED:
        # Either already past or our own clearing date: nothing to move.
        return None
    return moment + MINIMUM_FUTURE


async def update_panel_user_with_expiry(
    update: Callable[..., Awaitable[Any]],
    *,
    end_date: datetime | None,
    is_active: bool,
    panel_current: datetime | None = None,
    now: datetime | None = None,
    **update_kwargs: Any,
) -> Any:
    """PATCH a panel user with the expiry rule applied; returns the last panel response.

    ``update`` is the write call — ``api.update_user`` or a grace-safe wrapper around
    it — so the rule and the clock-skew fallback live here once instead of at every
    call site. Any ``expire_at`` in ``update_kwargs`` is replaced by the rule.

    ``panel_current`` is the panel's date if the caller already fetched the user. If
    it is unknown, the date is left out of the PATCH and the panel's answer decides
    whether a second, date-only PATCH has to clear a still-future date.
    """
    moment = now or datetime.now(UTC)
    kwargs = {key: value for key, value in update_kwargs.items() if key != 'expire_at'}
    decided_upfront = isinstance(panel_current, datetime)
    if end_date is not None:
        expire_at = panel_expire_at(
            end_date, is_active=is_active, creating=False, now=moment, panel_current=panel_current
        )
        if expire_at is not None:
            kwargs['expire_at'] = expire_at

    try:
        panel_user = await update(**kwargs)
    except RemnaWaveAPIError as error:
        if 'expire_at' not in kwargs or not is_expire_in_past_error(error):
            raise
        # The date rode in one request with the status and the panel rejected the
        # whole request: by its clock the date has passed. The status matters more —
        # send it without the date, then clear the date on its own below.
        logger.warning(
            'Panel rejected the expiry date as past; bot and panel clocks differ, sending status without it',
            panel_user_id=kwargs.get('user_id'),
            expire_at=kwargs['expire_at'],
        )
        kwargs.pop('expire_at')
        panel_user = await update(**kwargs)
        decided_upfront = False

    if decided_upfront or end_date is None:
        return panel_user
    extinguish_at = stale_panel_expire_at(getattr(panel_user, 'expire_at', None), end_date=end_date, now=moment)
    if extinguish_at is None:
        return panel_user
    try:
        return await update(user_id=kwargs['user_id'], expire_at=extinguish_at)
    except RemnaWaveAPIError as error:
        if not is_expire_in_past_error(error):
            raise
        retry_at = moment + SKEW_RETRY_MARGIN
        logger.warning(
            'Panel rejected the clearing date as past; bot clock is behind the panel, retrying with a wider margin',
            panel_user_id=kwargs['user_id'],
            rejected=extinguish_at,
            retry_at=retry_at,
        )
    try:
        return await update(user_id=kwargs['user_id'], expire_at=retry_at)
    except RemnaWaveAPIError as error:
        if not is_expire_in_past_error(error):
            raise
        # Upstream raises here. We don't: the status already reached the panel, and
        # several of our callers treat ANY exception from an update as "panel user is
        # missing" and create a new one — a duplicate account is far worse than a
        # stale date on a disabled subscription. An error log reaches the admin chat.
        logger.error(
            'Panel rejected the clearing date even with the retry margin; check bot/panel clock (NTP)',
            panel_user_id=kwargs['user_id'],
            rejected=retry_at,
        )
        return panel_user
