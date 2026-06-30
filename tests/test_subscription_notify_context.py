from types import SimpleNamespace

from app.utils.subscription_display import format_subscription_notify_context


class FakeTexts:
    def t(self, key: str, fallback: str = '', **kwargs) -> str:
        return fallback.format(**kwargs) if kwargs else fallback


def test_format_subscription_notify_context_includes_account_when_multi_tariff(monkeypatch):
    from app.config import Settings

    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)
    subscription = SimpleNamespace(
        panel_username='',
        tariff=SimpleNamespace(name='Mobile'),
        account_sequence=2,
        purchase_note='',
        remnawave_short_id='',
    )
    user = SimpleNamespace(is_partner=False, language='fa')
    texts = FakeTexts()

    ctx = format_subscription_notify_context(subscription, user, texts)

    assert 'Mobile #2' in ctx['account']
    assert 'Mobile #2' in ctx['subscription_line']
    assert ctx['tariff_name'] == 'Mobile'


def test_format_subscription_notify_context_includes_purchase_note():
    subscription = SimpleNamespace(
        panel_username='client-abc',
        tariff=SimpleNamespace(name='Pro'),
        account_sequence=1,
        purchase_note='فروشگاه مرکزی',
        remnawave_short_id='1001',
    )
    user = SimpleNamespace(is_partner=True, language='fa')
    texts = FakeTexts()

    ctx = format_subscription_notify_context(subscription, user, texts)

    assert 'client-abc' in ctx['subscription_line']
    assert 'فروشگاه مرکزی' in ctx['subscription_line']
