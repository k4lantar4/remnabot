from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.config import Settings
from app.utils.subscription_display import format_subscription_notify_card, format_subscription_notify_context


class FakeTexts:
    language = 'fa'

    def t(self, key: str, fallback: str = '', **kwargs) -> str:
        return fallback.format(**kwargs) if kwargs else fallback


def test_format_subscription_notify_card_includes_username_traffic_validity():
    subscription = SimpleNamespace(
        panel_username='Moji_5001',
        tariff=SimpleNamespace(name='Mobile'),
        account_sequence=1,
        traffic_limit_gb=50,
        traffic_used_gb=12.5,
        end_date=datetime.now(UTC) + timedelta(days=3),
        days_left=3,
        purchase_note='',
        remnawave_short_id='',
    )
    user = SimpleNamespace(is_partner=False, language='fa')
    texts = FakeTexts()

    ctx = format_subscription_notify_card(subscription, user, texts, language='fa')

    assert 'Moji_5001' in ctx['subscription_card']
    assert '12.5' in ctx['subscription_card']
    assert '👤' in ctx['subscription_card']


def test_format_subscription_notify_context_wraps_card():
    subscription = SimpleNamespace(
        panel_username='client-abc',
        tariff=SimpleNamespace(name='Pro'),
        account_sequence=1,
        traffic_limit_gb=0,
        traffic_used_gb=0,
        end_date=datetime.now(UTC) + timedelta(days=1),
        days_left=1,
        purchase_note='فروشگاه مرکزی',
        remnawave_short_id='1001',
    )
    user = SimpleNamespace(is_partner=True, language='fa')
    texts = FakeTexts()

    ctx = format_subscription_notify_context(subscription, user, texts)

    assert ctx['subscription_card'] == ctx['subscription_line']
    assert 'client-abc' in ctx['subscription_card']
    assert 'فروشگاه مرکزی' in ctx['subscription_card']


def test_format_subscription_notify_card_always_shown_without_multi_tariff(monkeypatch):
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)
    subscription = SimpleNamespace(
        panel_username='Moji_5001',
        tariff=SimpleNamespace(name='X'),
        account_sequence=1,
        traffic_limit_gb=10,
        traffic_used_gb=1.0,
        end_date=datetime.now(UTC) + timedelta(days=5),
        days_left=5,
        purchase_note='',
        remnawave_short_id='',
    )
    user = SimpleNamespace(is_partner=False, language='fa')
    texts = FakeTexts()

    ctx = format_subscription_notify_card(subscription, user, texts, language='fa')

    assert 'Moji_5001' in ctx['subscription_card']
