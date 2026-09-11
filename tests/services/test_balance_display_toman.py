"""The wallet balance is shown in Toman, not divided by 100.

``User.balance_kopeks`` holds raw Toman since Phase B, and ``settings.format_balance`` shows it 1:1.
``settings.format_price`` is the catalog formatter (price_kopeks / 100). Cabinet and miniapp
``balance_label`` fields, bot screens and admin notifications passed the balance to
``format_price``, so a 150,000-Toman wallet read «1,500 تومان».

Presentation only: no charge, credit or stored scale changes here (that is Phase C).
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.config import Settings, settings
from app.database.models import Base, Subscription, SubscriptionStatus, Tariff, User
from tests.fixtures.sqlite_memory import memory_session


ROOT = Path(__file__).resolve().parents[2]
TABLES = list(Base.metadata.sorted_tables)

BALANCE_TOMAN = 150_000
BALANCE_LABEL = settings.format_balance(BALANCE_TOMAN)  # «150,000 تومان»

GUARDED = [
    ROOT / 'app' / 'cabinet' / 'routes',
    ROOT / 'app' / 'webapi',
    ROOT / 'app' / 'services' / 'subscription_purchase_service.py',
]


def _format_price_on_balance() -> list[str]:
    """Every ``*.format_price(<expr mentioning a balance>)`` call in the guarded modules."""
    files: list[Path] = []
    for root in GUARDED:
        files.extend([root] if root.is_file() else sorted(root.rglob('*.py')))

    hits: list[str] = []
    for path in files:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'format_price'
                and node.args
                and 'balance' in ast.unparse(node.args[0]).lower()
            ):
                hits.append(f'{path.relative_to(ROOT)}:{node.lineno}: {ast.unparse(node.args[0])}')
    return hits


def test_no_balance_is_formatted_as_a_catalog_price():
    assert _format_price_on_balance() == []


def test_the_guard_sees_the_balance_labels():
    """Keep the guard honest: it must be scanning code that formats balances at all."""
    source = (ROOT / 'app' / 'cabinet' / 'routes' / 'subscription_modules' / 'daily.py').read_text(encoding='utf-8')
    assert "'balance_label': settings.format_balance(user.balance_kopeks)" in source


# ---------------------------------------------------------------- cabinet / miniapp daily pause


def _daily_rows() -> list:
    now = datetime.now(UTC)
    return [
        User(
            id=1,
            telegram_id=1001,
            first_name='U',
            language='fa',
            status='active',
            balance_kopeks=BALANCE_TOMAN,
            remnawave_id=9001,
        ),
        Tariff(
            id=1,
            name='daily',
            description='',
            is_active=True,
            is_daily=True,
            daily_price_kopeks=500_000,  # catalog: 5,000 Toman a day
            period_prices={},
            traffic_limit_gb=100,
            traffic_reset_mode='NO_RESET',
            device_limit=1,
            max_device_limit=10,
            device_price_kopeks=100,
            allowed_squads=['squad-1'],
            display_order=1,
        ),
        Subscription(
            id=10,
            remnawave_short_id='day1',
            remnawave_id=9001,
            user_id=1,
            status=SubscriptionStatus.ACTIVE.value,
            is_trial=False,
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(hours=20),
            updated_at=now - timedelta(hours=1),
            traffic_limit_gb=100,
            traffic_used_gb=1.0,
            purchased_traffic_gb=0,
            device_limit=1,
            tariff_id=1,
            connected_squads=['squad-1'],
            is_daily_paused=False,
        ),
    ]


@pytest.fixture
def _single_tariff(monkeypatch):
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: False)
    monkeypatch.setattr(Settings, 'is_tariffs_mode', lambda self: True)


@pytest.mark.asyncio
async def test_cabinet_daily_pause_labels_the_toman_balance(monkeypatch, _single_tariff):
    from app.cabinet.routes.subscription_modules import daily

    async with memory_session(monkeypatch, TABLES) as db:
        db.add_all(_daily_rows())
        await db.commit()
        user = await db.get(User, 1)

        response = await daily.toggle_subscription_pause(user=user, db=db, subscription_id=None)

    assert response['is_paused'] is True
    assert response['balance_kopeks'] == BALANCE_TOMAN
    assert response['balance_label'] == BALANCE_LABEL


@pytest.mark.asyncio
async def test_miniapp_daily_pause_labels_the_toman_balance(monkeypatch, _single_tariff):
    from app.database.crud.user import lock_user_for_pricing
    from app.webapi.routes import miniapp
    from app.webapi.schemas.miniapp import MiniAppDailySubscriptionToggleRequest

    async with memory_session(monkeypatch, TABLES) as db:
        db.add_all(_daily_rows())
        await db.commit()
        # _authorize_miniapp_user hands over the user with subscriptions loaded
        user = await lock_user_for_pricing(db, 1)

        monkeypatch.setattr(miniapp, '_authorize_miniapp_user', AsyncMock(return_value=user))

        response = await miniapp.toggle_daily_subscription_pause_endpoint(
            MiniAppDailySubscriptionToggleRequest(init_data='init'), db=db
        )

    assert response.balance_label == BALANCE_LABEL
