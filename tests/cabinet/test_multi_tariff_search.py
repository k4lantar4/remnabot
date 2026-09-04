from types import SimpleNamespace

from app.cabinet.routes.subscription_modules.multi_tariff import (
    _subscription_matches_search,
    _subscription_to_list_item,
)


def test_search_matches_username_and_id() -> None:
    sub = SimpleNamespace(
        id=82444,
        panel_username='mobile_x_1001',
        tariff=SimpleNamespace(name='Moon'),
        purchase_note=None,
    )
    assert _subscription_matches_search(sub, 'mobile_x') is True
    assert _subscription_matches_search(sub, '82444') is True
    assert _subscription_matches_search(sub, 'zzz') is False


def test_list_item_includes_identity_a_fields() -> None:
    sub = SimpleNamespace(
        id=1,
        actual_status='active',
        tariff_id=2,
        tariff=SimpleNamespace(name='Moon', is_daily=False),
        account_sequence=3,
        panel_username='mobile_x_1001',
        traffic_limit_gb=10,
        traffic_used_gb=1.0,
        device_limit=2,
        end_date=None,
        subscription_url=None,
        subscription_crypto_link=None,
        is_trial=False,
        is_daily_paused=False,
        autopay_enabled=False,
        connected_squads=[],
        purchase_note=None,
        user_disabled=False,
    )
    item = _subscription_to_list_item(sub)
    assert item.panel_username == 'mobile_x_1001'
    assert item.account_sequence == 3
