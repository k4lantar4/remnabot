from __future__ import annotations

from datetime import datetime

from app.database.crud.referral import get_referral_statistics
from app.database.crud.subscription import get_subscriptions_statistics, get_trial_statistics
from app.database.crud.transaction import get_transactions_statistics
from app.database.crud.user import get_users_statistics

from fastapi import APIRouter, Depends, Security
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Subscription,
    SubscriptionStatus,
    Ticket,
    TicketStatus,
    Transaction,
    TransactionType,
    User,
    UserStatus,
)

from ..dependencies import get_db_session, require_api_token

router = APIRouter()


@router.get(
    "/overview",
    summary="Overall statistics",
    response_description="Aggregated metrics for users, subscriptions, support and payments",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "users": {
                            "total": 12345,
                            "active": 9876,
                            "blocked": 321,
                            "balance_toman": 1234567,
                        },
                        "subscriptions": {
                            "active": 4321,
                            "expired": 210,
                        },
                        "support": {
                            "open_tickets": 42,
                        },
                        "payments": {
                            "today_toman": 654321,
                        },
                    }
                }
            }
        }
    },
)
async def stats_overview(
    _: object = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    total_users = await db.scalar(select(func.count()).select_from(User)) or 0
    active_users = (
        await db.scalar(select(func.count()).select_from(User).where(User.status == UserStatus.ACTIVE.value)) or 0
    )
    blocked_users = (
        await db.scalar(select(func.count()).select_from(User).where(User.status == UserStatus.BLOCKED.value)) or 0
    )

    total_balance_toman = await db.scalar(select(func.coalesce(func.sum(User.balance_toman), 0))) or 0

    active_subscriptions = (
        await db.scalar(
            select(func.count())
            .select_from(Subscription)
            .where(
                Subscription.status == SubscriptionStatus.ACTIVE.value,
            )
        )
        or 0
    )

    expired_subscriptions = (
        await db.scalar(
            select(func.count())
            .select_from(Subscription)
            .where(
                Subscription.status == SubscriptionStatus.EXPIRED.value,
            )
        )
        or 0
    )

    pending_tickets = (
        await db.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.status.in_([TicketStatus.OPEN.value, TicketStatus.ANSWERED.value]))
        )
        or 0
    )

    today = datetime.utcnow().date()
    today_transactions = (
        await db.scalar(
            select(func.coalesce(func.sum(Transaction.amount_toman), 0)).where(
                func.date(Transaction.created_at) == today,
                Transaction.type == TransactionType.DEPOSIT.value,
            )
        )
        or 0
    )

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "blocked": blocked_users,
            "balance_toman": int(total_balance_toman),
        },
        "subscriptions": {
            "active": active_subscriptions,
            "expired": expired_subscriptions,
        },
        "support": {
            "open_tickets": pending_tickets,
        },
        "payments": {
            "today_toman": int(today_transactions),
        },
    }


@router.get(
    "/overview",
    summary="General statistics",
    response_description="Aggregated metrics for users, subscriptions, support, and payments",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "users": {
                            "total": 12345,
                            "active": 9876,
                            "blocked": 321,
                            "balance_toman": 1234567,
                        },
                        "subscriptions": {
                            "active": 4321,
                            "expired": 210,
                        },
                        "support": {
                            "open_tickets": 42,
                        },
                        "payments": {
                            "today_toman": 654321,
                        },
                    }
                }
            }
        }
    },
)
async def stats_overview(
    _: object = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    return await _get_overview(db)


@router.get(
    "/full",
    summary="Full statistics",
    response_description="Detailed metrics for users, subscriptions, payments, and referrals",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": {
                        "overview": {
                            "users": {
                                "total": 12345,
                                "active": 9876,
                                "blocked": 321,
                                "balance_toman": 1234567,
                            },
                            "subscriptions": {
                                "active": 4321,
                                "expired": 210,
                            },
                            "support": {
                                "open_tickets": 42,
                            },
                            "payments": {
                                "today_toman": 654321,
                            },
                        },
                        "users": {
                            "total_users": 12345,
                            "active_users": 9876,
                            "blocked_users": 321,
                            "new_today": 12,
                            "new_week": 345,
                            "new_month": 1234,
                        },
                        "subscriptions": {
                            "total_subscriptions": 9876,
                            "active_subscriptions": 8765,
                            "trial_subscriptions": 321,
                            "paid_subscriptions": 8444,
                            "purchased_today": 12,
                            "purchased_week": 210,
                            "purchased_month": 765,
                            "trial_to_paid_conversion": 42.5,
                            "renewals_count": 123,
                            "trial_statistics": {
                                "used_trials": 555,
                                "active_trials": 210,
                                "resettable_trials": 42,
                            },
                        },
                        "transactions": {
                            "period": {
                                "start_date": "2024-06-01T00:00:00Z",
                                "end_date": "2024-06-30T23:59:59Z",
                            },
                            "totals": {
                                "income_toman": 1234567,
                                "expenses_toman": 21000,
                                "profit_toman": 1213567,
                                "subscription_income_toman": 987654,
                            },
                            "today": {
                                "transactions_count": 42,
                                "income_toman": 654321,
                            },
                            "by_type": {
                                "deposit": {"count": 123, "amount": 1234567},
                                "withdrawal": {"count": 10, "amount": 21000},
                            },
                            "by_payment_method": {"card": {"count": 100, "amount": 1000000}},
                        },
                        "referrals": {
                            "users_with_referrals": 4321,
                            "active_referrers": 123,
                            "total_paid_toman": 765432,
                            "total_paid_rubles": 7654.32,
                            "today_earnings_toman": 12345,
                            "today_earnings_rubles": 123.45,
                            "week_earnings_toman": 23456,
                            "week_earnings_rubles": 234.56,
                            "month_earnings_toman": 34567,
                            "month_earnings_rubles": 345.67,
                            "top_referrers": [
                                {
                                    "user_id": 123456789,
                                    "display_name": "@testuser",
                                    "username": "testuser",
                                    "telegram_id": 123456789,
                                    "total_earned_toman": 54321,
                                    "referrals_count": 42,
                                }
                            ],
                        },
                    }
                }
            }
        }
    },
)
async def stats_full(
    _: object = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    overview = await _get_overview(db)

    users_stats = await get_users_statistics(db)
    subscriptions_stats = await get_subscriptions_statistics(db)
    trial_stats = await get_trial_statistics(db)
    transactions_stats = await get_transactions_statistics(db)
    referral_stats = await get_referral_statistics(db)

    transactions_totals = transactions_stats.get("totals", {})
    transactions_today = transactions_stats.get("today", {})

    transactions_totals = {
        **transactions_totals,
        "income_toman": transactions_totals.get("income_toman"),
        "expenses_toman": transactions_totals.get("expenses_toman"),
        "profit_toman": transactions_totals.get("profit_toman"),
        "subscription_income_toman": transactions_totals.get("subscription_income_toman"),
    }

    from app.config import settings

    transactions_today = {
        **transactions_today,
        "income_rubles": settings.toman_to_rubles(transactions_today.get("income_toman", 0)),
    }

    referral_stats = {
        **referral_stats,
        "total_paid_toman": referral_stats.get("total_paid_toman"),
        "today_earnings_toman": referral_stats.get("today_earnings_toman"),
        "week_earnings_toman": referral_stats.get("week_earnings_toman"),
        "month_earnings_toman": referral_stats.get("month_earnings_toman"),
    }

    return {
        "overview": overview,
        "users": users_stats,
        "subscriptions": {**subscriptions_stats, "trial_statistics": trial_stats},
        "transactions": {
            **transactions_stats,
            "totals": transactions_totals,
            "today": transactions_today,
        },
        "referrals": referral_stats,
    }
