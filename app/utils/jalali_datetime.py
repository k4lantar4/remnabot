"""Language-aware datetime formatting with Jalali calendar for fa users."""

from __future__ import annotations

from datetime import datetime

import jdatetime

from app.utils.timezone import format_local_datetime, to_local_datetime


def is_jalali_language(language: str | None) -> bool:
    code = (language or '').split('-')[0].lower()
    return code == 'fa'


def format_user_datetime(
    dt: datetime | None,
    *,
    language: str = 'ru',
    fmt: str = '%d.%m.%Y',
    na_placeholder: str = 'N/A',
) -> str:
    if dt is None:
        return na_placeholder

    if not is_jalali_language(language):
        return format_local_datetime(dt, fmt=fmt, na_placeholder=na_placeholder)

    localized = to_local_datetime(dt)
    if localized is None:
        return na_placeholder

    naive_local = localized.replace(tzinfo=None)
    jalali_dt = jdatetime.datetime.fromgregorian(datetime=naive_local)
    return jalali_dt.strftime(fmt)
