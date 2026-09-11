"""Admin web API ``*_rubles`` fields carry display Toman (F-004).

``balance_kopeks`` and ``ReferralEarning.amount_kopeks`` hold Toman 1:1 (Phase B), so the
``*_rubles`` twins must equal them, not a hundredth of them — the same convention as
the cabinet's ``balance_rubles`` (``display_balance_from_storage``).
"""

from datetime import UTC, datetime
from types import SimpleNamespace

from app.webapi.routes.partners import _serialize_referral_item, _serialize_referrer
from app.webapi.routes.servers import _serialize_connected_user


def test_referrer_earned_rubles_are_toman() -> None:
    user = SimpleNamespace(
        id=1,
        telegram_id=101,
        username='partner',
        first_name='Partner',
        last_name=None,
        referral_code='ref1',
        referral_commission_percent=10,
        created_at=datetime.now(UTC),
        last_activity=None,
    )
    item = _serialize_referrer(
        user,
        {'invited_count': 3, 'active_referrals': 2, 'total_earned_kopeks': 1_000_000, 'month_earned_kopeks': 50_000},
    )

    assert item.total_earned_kopeks == 1_000_000
    assert item.total_earned_rubles == 1_000_000
    assert item.month_earned_kopeks == 50_000
    assert item.month_earned_rubles == 50_000


def test_referral_item_balance_and_earned_rubles_are_toman() -> None:
    item = _serialize_referral_item(
        {
            'id': 2,
            'telegram_id': 202,
            'full_name': 'Buyer',
            'created_at': datetime.now(UTC),
            'balance_kopeks': 50_000,
            'total_earned_kopeks': 1_000_000,
        }
    )

    assert item.balance_rubles == 50_000
    assert item.total_earned_rubles == 1_000_000


def test_server_connected_user_balance_rubles_is_toman() -> None:
    user = SimpleNamespace(
        id=3,
        telegram_id=303,
        username='u',
        first_name='U',
        last_name=None,
        status=SimpleNamespace(value='active'),
        balance_kopeks=1_000_000,
        subscription=None,
    )

    item = _serialize_connected_user(user)

    assert item.balance_kopeks == 1_000_000
    assert item.balance_rubles == 1_000_000
