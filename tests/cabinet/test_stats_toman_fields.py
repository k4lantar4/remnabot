"""Additive ``*_toman`` fields on the cabinet stats endpoints (wave 2, Task 5).

Transaction rows are stored on two scales: types in ``_BALANCE_SCALE_TRANSACTION_TYPES``
(deposit, withdrawal, refund, ...) hold Toman 1:1, the rest (subscription_payment,
gift_payment) hold the catalog scale, Toman x100. A raw SQL sum across both is
meaningless, so every money aggregate the cabinet charts gets a ``*_toman`` twin
normalized per row type. The old fields stay byte-for-byte as they were; the
frontend switches to the new ones in a separate PR.

Shared fixture: one catalog-scale row (subscription_payment 1,000,000 = 10,000 Toman)
and one balance-scale row (deposit 50,000 Toman). A mixed aggregate must say 60,000.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.crud.transaction import transaction_toman_sum
from app.database.models import (
    AdvertisingCampaign,
    AdvertisingCampaignRegistration,
    GuestPurchase,
    PartnerStatus,
    ReferralEarning,
    Subscription,
    SubscriptionConversion,
    Tariff,
    TrafficPurchase,
    Transaction,
    TransactionType,
    User,
)
from tests.fixtures.sqlite_memory import memory_session


pytestmark = pytest.mark.asyncio

TABLES = (
    User.__table__,
    Tariff.__table__,
    Subscription.__table__,
    SubscriptionConversion.__table__,
    TrafficPurchase.__table__,
    GuestPurchase.__table__,
    Transaction.__table__,
    AdvertisingCampaign.__table__,
    AdvertisingCampaignRegistration.__table__,
    ReferralEarning.__table__,
)

ADMIN = SimpleNamespace(id=999, telegram_id=999)

SUBSCRIPTION_CATALOG = 1_000_000  # catalog scale → 10,000 Toman
SUBSCRIPTION_TOMAN = 10_000
DEPOSIT_TOMAN = 50_000  # balance scale, 1:1
MIXED_TOMAN = SUBSCRIPTION_TOMAN + DEPOSIT_TOMAN  # 60,000

PARTNER_ID = 1
BUYER_ID = 2
CAMPAIGN_ID = 10


def _days_ago(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


def _user(user_id: int, **kwargs) -> User:
    return User(
        id=user_id,
        telegram_id=100 + user_id,
        username=f'user{user_id}',
        first_name=f'User{user_id}',
        language='fa',
        **kwargs,
    )


def _tx(user_id: int, tx_type: str, amount: int, *, days_ago: int = 2, method: str = 'c2c', description=None):
    return Transaction(
        user_id=user_id,
        type=tx_type,
        amount_kopeks=amount,
        payment_method=method,
        description=description,
        is_completed=True,
        created_at=_days_ago(days_ago),
    )


async def _seed_base(db) -> None:
    """Partner (1) invited buyer (2) through campaign 10; buyer paid twice."""
    db.add(_user(PARTNER_ID, partner_status=PartnerStatus.APPROVED.value))
    db.add(_user(BUYER_ID, referred_by_id=PARTNER_ID))
    await db.flush()
    db.add(
        AdvertisingCampaign(
            id=CAMPAIGN_ID,
            name='Campaign',
            start_parameter='camp10',
            bonus_type='balance',
            balance_bonus_kopeks=5_000,
            partner_user_id=PARTNER_ID,
            is_active=True,
        )
    )
    await db.flush()
    db.add(
        AdvertisingCampaignRegistration(
            campaign_id=CAMPAIGN_ID,
            user_id=BUYER_ID,
            bonus_type='balance',
            balance_bonus_kopeks=5_000,
            created_at=_days_ago(3),
        )
    )
    # create_transaction stores subscription_payment as a negative amount.
    db.add(_tx(BUYER_ID, TransactionType.SUBSCRIPTION_PAYMENT.value, -SUBSCRIPTION_CATALOG, description='Подписка'))
    db.add(_tx(BUYER_ID, TransactionType.DEPOSIT.value, DEPOSIT_TOMAN))
    await db.flush()


# ============ Helper ============


async def test_transaction_toman_sum_normalizes_each_row_by_type(monkeypatch):
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_base(db)

        total = (await db.execute(select(transaction_toman_sum()))).scalar()

    assert total == MIXED_TOMAN


# ============ Sales stats ============


async def test_sales_summary_revenue_toman_mixes_deposits_subscriptions_and_gifts(monkeypatch):
    from app.cabinet.routes import admin_sales_stats as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_base(db)
        db.add(_tx(BUYER_ID, TransactionType.DEPOSIT.value, 20_000, method='manual'))
        db.add(
            _tx(
                BUYER_ID,
                TransactionType.SUBSCRIPTION_PAYMENT.value,
                -700_000,
                method='balance',
                description='Докупка трафика 10 ГБ',
            )
        )
        db.add(
            GuestPurchase(
                token='gift-token',
                contact_type='telegram',
                contact_value='@friend',
                is_gift=True,
                period_days=30,
                amount_kopeks=300_000,  # catalog price of the gift → 3,000 Toman
                payment_method='c2c',
                status='delivered',
                paid_at=_days_ago(1),
            )
        )
        await db.flush()

        summary = await route.get_sales_summary(days=0, start_date=None, end_date=None, admin=ADMIN, db=db)

    assert summary.total_revenue_toman == MIXED_TOMAN + 3_000
    assert summary.manual_topup_toman == 20_000
    assert summary.addon_revenue_toman == 7_000
    # Old fields untouched.
    assert summary.total_revenue_kopeks == SUBSCRIPTION_CATALOG + DEPOSIT_TOMAN + 300_000
    assert summary.manual_topup_kopeks == 20_000
    assert summary.addon_revenue_kopeks == 700_000


async def test_sales_deposits_tab_toman_fields(monkeypatch):
    from app.cabinet.routes import admin_sales_stats as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_base(db)

        deposits = await route.get_deposits_stats(days=0, start_date=None, end_date=None, admin=ADMIN, db=db)

    assert deposits.total_amount_toman == MIXED_TOMAN
    assert deposits.avg_deposit_toman == MIXED_TOMAN // 2
    assert [(m.method, m.amount_toman) for m in deposits.by_method] == [('c2c', MIXED_TOMAN)]
    assert [d.amount_toman for d in deposits.daily] == [MIXED_TOMAN]
    assert [(d.method, d.amount_toman) for d in deposits.daily_by_method] == [('c2c', MIXED_TOMAN)]
    assert deposits.total_amount_kopeks == SUBSCRIPTION_CATALOG + DEPOSIT_TOMAN


async def test_sales_subscriptions_tab_toman_fields(monkeypatch):
    from app.cabinet.routes import admin_sales_stats as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_base(db)

        sales = await route.get_sales_stats(days=0, start_date=None, end_date=None, admin=ADMIN, db=db)

    assert sales.total_revenue_toman == SUBSCRIPTION_TOMAN
    assert sales.avg_order_toman == SUBSCRIPTION_TOMAN
    assert [d.revenue_toman for d in sales.daily] == [SUBSCRIPTION_TOMAN]
    assert sales.total_revenue_kopeks == SUBSCRIPTION_CATALOG


async def test_sales_renewals_tab_toman_fields(monkeypatch):
    from app.cabinet.routes import admin_sales_stats as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_base(db)
        db.add(
            _tx(BUYER_ID, TransactionType.SUBSCRIPTION_PAYMENT.value, -1_500_000, days_ago=1, description='Продление')
        )
        await db.flush()

        renewals = await route.get_renewals_stats(days=0, start_date=None, end_date=None, admin=ADMIN, db=db)

    assert renewals.total_revenue_toman == 25_000
    assert renewals.current_period.revenue_toman == 25_000
    assert renewals.previous_period.revenue_toman == 0
    assert renewals.total_revenue_kopeks == 2_500_000


async def test_sales_addons_tab_toman_fields(monkeypatch):
    from app.cabinet.routes import admin_sales_stats as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_base(db)
        db.add(_tx(BUYER_ID, TransactionType.SUBSCRIPTION_PAYMENT.value, -700_000, description='Докупка трафика 10 ГБ'))
        db.add(_tx(BUYER_ID, TransactionType.SUBSCRIPTION_PAYMENT.value, -300_000, description='Докупка 1 устройств'))
        await db.flush()

        addons = await route.get_addons_stats(days=0, start_date=None, end_date=None, admin=ADMIN, db=db)

    assert addons.addon_revenue_toman == 7_000
    assert addons.device_revenue_toman == 3_000
    assert addons.addon_revenue_kopeks == 700_000


# ============ Admin campaigns + dashboard ============


async def test_admin_campaign_stats_toman_fields(monkeypatch):
    from app.cabinet.routes import admin_campaigns as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_base(db)

        stats = await route.get_campaign_stats(campaign_id=CAMPAIGN_ID, admin=ADMIN, db=db)

    # Campaign revenue counts real deposits only → balance scale.
    assert stats.total_revenue_toman == DEPOSIT_TOMAN
    assert stats.avg_revenue_per_user_toman == DEPOSIT_TOMAN
    # First payment is the subscription payment → catalog scale.
    assert stats.avg_first_payment_toman == SUBSCRIPTION_TOMAN
    assert stats.balance_issued_toman == 5_000
    assert stats.total_revenue_kopeks == DEPOSIT_TOMAN


async def test_admin_campaign_stats_rubles_fields_are_display_toman(monkeypatch):
    """F-004: revenue sums deposits (balance scale), so its *_rubles must not divide by 100.

    The first payment is a subscription price (catalog scale) and keeps its ÷100.
    """
    from app.cabinet.routes import admin_campaigns as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_base(db)

        stats = await route.get_campaign_stats(campaign_id=CAMPAIGN_ID, admin=ADMIN, db=db)

    assert stats.total_revenue_rubles == DEPOSIT_TOMAN
    assert stats.avg_revenue_per_user_rubles == DEPOSIT_TOMAN
    assert stats.avg_first_payment_rubles == SUBSCRIPTION_TOMAN
    assert stats.balance_issued_rubles == 5_000


async def test_admin_campaign_list_and_overview_toman_fields(monkeypatch):
    from app.cabinet.routes import admin_campaigns as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_base(db)

        listing = await route.list_campaigns(offset=0, limit=50, include_inactive=True, admin=ADMIN, db=db)
        overview = await route.get_overview(admin=ADMIN, db=db)

    assert [c.total_revenue_toman for c in listing.campaigns] == [DEPOSIT_TOMAN]
    assert overview.total_balance_issued_toman == 5_000


async def test_admin_campaign_chart_data_toman_fields(monkeypatch):
    from app.cabinet.routes import admin_campaigns as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_base(db)

        chart = await route.get_campaign_chart_data(campaign_id=CAMPAIGN_ID, admin=ADMIN, db=db)

    assert chart.total_deposits_toman == DEPOSIT_TOMAN
    assert chart.total_spending_toman == SUBSCRIPTION_TOMAN
    assert sum(d.earnings_toman for d in chart.daily_stats) == DEPOSIT_TOMAN
    assert chart.period_comparison.current.earnings_toman == DEPOSIT_TOMAN
    assert chart.period_comparison.previous.earnings_toman == 0
    assert [r.total_earnings_toman for r in chart.top_registrations] == [DEPOSIT_TOMAN]
    assert chart.total_spending_kopeks == SUBSCRIPTION_CATALOG


async def test_admin_dashboard_top_campaigns_toman_fields(monkeypatch):
    from app.cabinet.routes import admin_stats as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_base(db)

        top = await route.get_top_campaigns(limit=10, admin=ADMIN, db=db)

    assert top.total_revenue_toman == DEPOSIT_TOMAN
    assert [c.total_revenue_toman for c in top.campaigns] == [DEPOSIT_TOMAN]
    assert [c.avg_revenue_per_user_toman for c in top.campaigns] == [DEPOSIT_TOMAN]


# ============ Referral network ============


async def _seed_network(db) -> None:
    await _seed_base(db)
    db.add(
        ReferralEarning(
            user_id=PARTNER_ID,
            referral_id=BUYER_ID,
            amount_kopeks=5_000,  # commission on a Toman top-up → Toman
            reason='referral_commission_topup',
            campaign_id=CAMPAIGN_ID,
            created_at=_days_ago(2),
        )
    )
    await db.flush()


@pytest.fixture
def no_rate_limit(monkeypatch):
    from app.cabinet.routes import admin_referral_network as route

    monkeypatch.setattr(route.RateLimitCache, 'is_rate_limited', AsyncMock(return_value=False))


async def test_referral_network_graph_toman_fields(monkeypatch, no_rate_limit):
    from app.cabinet.routes import admin_referral_network as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_network(db)

        graph = await route.get_referral_network(admin=ADMIN, db=db)

    users = {u.id: u for u in graph.users}
    assert users[PARTNER_ID].branch_revenue_toman == SUBSCRIPTION_TOMAN
    assert users[PARTNER_ID].personal_revenue_toman == 5_000
    assert users[BUYER_ID].personal_spent_toman == SUBSCRIPTION_TOMAN
    assert graph.total_subscription_revenue_toman == SUBSCRIPTION_TOMAN
    assert graph.total_earnings_toman == 5_000
    [campaign] = graph.campaigns
    assert campaign.total_revenue_toman == SUBSCRIPTION_TOMAN
    assert campaign.avg_check_toman == SUBSCRIPTION_TOMAN
    assert users[BUYER_ID].personal_spent_kopeks == SUBSCRIPTION_CATALOG


async def test_referral_network_user_and_campaign_detail_toman_fields(monkeypatch, no_rate_limit):
    from app.cabinet.routes import admin_referral_network as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_network(db)

        partner = await route.get_network_user_detail(user_id=PARTNER_ID, admin=ADMIN, db=db)
        buyer = await route.get_network_user_detail(user_id=BUYER_ID, admin=ADMIN, db=db)
        campaign = await route.get_network_campaign_detail(campaign_id=CAMPAIGN_ID, admin=ADMIN, db=db)
        found = await route.search_referral_network(q='camp10', admin=ADMIN, db=db)

    assert partner.branch_revenue_toman == SUBSCRIPTION_TOMAN
    assert partner.personal_revenue_toman == 5_000
    assert buyer.personal_spent_toman == SUBSCRIPTION_TOMAN
    assert campaign.total_revenue_toman == SUBSCRIPTION_TOMAN
    assert campaign.avg_check_toman == SUBSCRIPTION_TOMAN
    assert [c.total_revenue_toman for c in found.campaigns] == [SUBSCRIPTION_TOMAN]


# ============ Admin users ============


async def test_admin_user_total_spent_toman(monkeypatch):
    from app.cabinet.routes import admin_users as route
    from app.database.crud.user import get_users_spending_stats

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_base(db)

        stats = await get_users_spending_stats(db, [BUYER_ID])
        buyer = (
            await db.execute(
                select(User)
                .options(selectinload(User.subscriptions), selectinload(User.promo_group))
                .where(User.id == BUYER_ID)
            )
        ).scalar_one()
        item = route._build_user_list_item(buyer, stats)

    # Only subscription payments count as spending → catalog scale; the deposit is excluded.
    assert stats[BUYER_ID]['total_spent_toman'] == SUBSCRIPTION_TOMAN
    assert item.total_spent_toman == SUBSCRIPTION_TOMAN
    assert item.total_spent_kopeks == SUBSCRIPTION_CATALOG


# ============ Partner campaign stats (DailyChart / PeriodComparison) ============


async def test_partner_campaign_stats_toman_fields(monkeypatch):
    from app.cabinet.routes import partner_application as route

    async with memory_session(monkeypatch, TABLES) as db:
        await _seed_network(db)
        partner = await db.get(User, PARTNER_ID)

        stats = await route.get_campaign_stats(campaign_id=CAMPAIGN_ID, user=partner, db=db)

    # ReferralEarning holds commissions on Toman top-ups → balance scale.
    assert stats.earnings_toman == 5_000
    assert stats.earnings_week_toman == 5_000
    assert stats.earnings_month_toman == 5_000
    assert stats.earnings_today_toman == 0
    assert sum(d.earnings_toman for d in stats.daily_stats) == 5_000
    assert stats.period_comparison.current.earnings_toman == 5_000
    assert stats.period_comparison.previous.earnings_toman == 0
    assert [r.total_earnings_toman for r in stats.top_referrals] == [5_000]
    assert stats.earnings_kopeks == 5_000
