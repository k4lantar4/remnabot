from __future__ import annotations

from types import SimpleNamespace

from app.utils.subscription_display import subscription_account_label


class _Texts:
    language = 'fa'

    def t(self, key: str, default: str) -> str:
        return default


def test_subscription_account_label_uses_panel_username_when_set() -> None:
    sub = SimpleNamespace(
        panel_username='Germany(2)-134500',
        account_sequence=2,
        tariff=SimpleNamespace(name='Germany'),
    )
    assert subscription_account_label(sub, _Texts()) == 'Germany(2)-134500'


def test_subscription_account_label_falls_back_to_tariff_seq() -> None:
    sub = SimpleNamespace(
        panel_username=None,
        account_sequence=2,
        tariff=SimpleNamespace(name='Germany'),
    )
    label = subscription_account_label(sub, _Texts())
    assert label == 'Germany #2'


def test_subscription_account_label_empty_panel_username_falls_back() -> None:
    sub = SimpleNamespace(
        panel_username='',
        account_sequence=1,
        tariff=None,
    )
    label = subscription_account_label(sub, _Texts())
    assert label == 'Подписка #1'
