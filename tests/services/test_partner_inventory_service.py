from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.services.partner_inventory_service import (
    NEAR_EXPIRY_DAYS,
    is_device_online,
    summarize_subscription_inventory,
)


def _sub(*, status: str, end_date: datetime | None, is_trial: bool = False):
    return SimpleNamespace(
        status=status,
        end_date=end_date,
        is_trial=is_trial,
        actual_status=status if status != 'active' else ('trial' if is_trial else 'active'),
        days_left=max(
            0,
            (end_date - datetime.now(UTC)).days if end_date and end_date > datetime.now(UTC) else 0,
        ),
    )


def test_summarize_subscription_inventory_buckets():
    now = datetime.now(UTC)
    subs = [
        _sub(status='active', end_date=now + timedelta(days=30)),
        _sub(status='active', end_date=now + timedelta(days=3)),
        _sub(status='expired', end_date=now - timedelta(days=1)),
        _sub(status='trial', end_date=now + timedelta(days=10), is_trial=True),
    ]
    # Patch actual_status/days_left for realistic model behavior
    subs[0].actual_status = 'active'
    subs[0].days_left = 30
    subs[1].actual_status = 'active'
    subs[1].days_left = 3
    subs[2].actual_status = 'expired'
    subs[2].days_left = 0
    subs[3].actual_status = 'trial'
    subs[3].days_left = 10

    result = summarize_subscription_inventory(subs)
    assert result.total == 4
    assert result.active == 3
    assert result.expired == 1
    assert result.near_expiry == 1


def test_is_device_online_within_window():
    now = datetime.now(UTC)
    recent = (now - timedelta(minutes=5)).isoformat()
    stale = (now - timedelta(minutes=30)).isoformat()
    assert is_device_online(recent, now=now) is True
    assert is_device_online(stale, now=now) is False


def test_near_expiry_constant():
    assert NEAR_EXPIRY_DAYS == 7


def test_subscription_spent_uses_catalog_scale_div_100():
    from app.database.models import TransactionType
    from app.utils.price_display import storage_sum_to_display_toman

    # Catalog-scale subscription debits: stored kopeks ÷ 100 → Toman
    assert storage_sum_to_display_toman(664_000_000, TransactionType.SUBSCRIPTION_PAYMENT.value) == 6_640_000
