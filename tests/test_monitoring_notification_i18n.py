"""Scheduled user notifications must not use bare Cyrillic message bodies."""

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.config import settings


APP = Path(__file__).resolve().parents[1] / 'app'
TARGETS = [
    APP / 'services' / 'monitoring_service.py',
    APP / 'services' / 'daily_subscription_service.py',
]
# f-string message bodies with Cyrillic — not texts.t fallbacks
BARE_MSG = re.compile(
    r"message\s*=\s*f['\"]{3}.*[А-Яа-яЁё]",
    re.DOTALL,
)
BARE_F = re.compile(
    r"message\s*=\s*\(\s*f['\"].*[А-Яа-яЁё]",
)


@pytest.fixture(autouse=True)
def _utc_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'TIMEZONE', 'UTC', raising=False)
    from app.utils.timezone import get_local_timezone

    get_local_timezone.cache_clear()


def test_no_bare_cyrillic_notification_bodies():
    offenders = []
    for path in TARGETS:
        text = path.read_text(encoding='utf-8')
        for i, line in enumerate(text.splitlines(), 1):
            if 'texts.t(' in line:
                continue
            if BARE_F.search(line) or ('message = f"""' in line or "message = f'''" in line):
                # flag only if block contains Cyrillic — scan next 15 lines
                block = '\n'.join(text.splitlines()[i - 1 : i + 14])
                if '[А-Яа-яЁё]' and __import__('re').search(r'[А-Яа-яЁё]', block):
                    if 'texts.t(' not in block:
                        offenders.append(f'{path.relative_to(APP.parent)}:{i}')
    assert not offenders, 'Bare Cyrillic notification bodies:\n' + '\n'.join(offenders)


def test_monitoring_user_notifications_use_jalali_helper():
    text = (APP / 'services' / 'monitoring_service.py').read_text(encoding='utf-8')
    assert 'format_user_datetime' in text
    assert 'format_local_datetime(subscription.end_date' not in text
    assert 'format_local_datetime(expires_at' not in text


def test_monitoring_expiring_end_date_is_jalali_for_fa() -> None:
    from app.utils.jalali_datetime import format_user_datetime

    dt = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)
    end_date = format_user_datetime(dt, language='fa', fmt='%d.%m.%Y %H:%M')
    assert end_date.startswith('18.04.1405')


def test_monitoring_notifications_use_subscription_card():
    for rel in ('services/monitoring_service.py', 'services/daily_subscription_service.py'):
        text = (APP / rel).read_text(encoding='utf-8')
        assert 'format_subscription_notify_card' in text
        assert 'subscription_card' in text
