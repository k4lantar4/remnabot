"""Admin dashboard money on the Toman scale.

Deposits (C2C/manual) are stored Toman 1:1, subscription_payment ×100. Every
``*_rubles`` / ``*_toman`` field the dashboard reads must be display Toman.
"""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.cabinet.routes.admin_stats import get_recent_payments
from app.database.crud.transaction import (
    display_toman_from_type_sums,
    get_revenue_by_period,
    get_transactions_statistics,
)


NOW = datetime(2026, 9, 10, 18, 0, tzinfo=UTC)


def test_type_sums_no_longer_convert_per_type() -> None:
    """Both rows are Toman since revision 0115, so the sum is |deposit| + |payment|."""
    rows = [('deposit', 1_000_000), ('subscription_payment', -1_000_000)]

    assert display_toman_from_type_sums(rows) == 2_000_000


def test_type_sums_empty_is_zero() -> None:
    assert display_toman_from_type_sums([]) == 0


def _result(*, rows=None, scalars=None, scalar=None) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows or []
    result.__iter__.side_effect = lambda: iter(rows or [])
    result.scalars.return_value.all.return_value = scalars or []
    result.scalar.return_value = scalar
    return result


async def test_revenue_chart_has_toman_per_day() -> None:
    day = date(2026, 9, 10)
    rows = [
        SimpleNamespace(date=day, type='deposit', amount=5_000_000),
        SimpleNamespace(date=day, type='subscription_payment', amount=1_000_000),
    ]  # both Toman
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_result(rows=rows))

    data = await get_revenue_by_period(db, days=30)

    assert data == [{'date': day, 'amount_kopeks': 6_000_000, 'amount_toman': 6_000_000}]


async def test_transactions_statistics_has_toman_expenses_profit_and_methods() -> None:
    """A 50,000-Toman deposit + a 100,000-Toman subscription payment, both via card (F-015)."""
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _result(rows=[('deposit', 50_000), ('subscription_payment', 100_000)]),  # income
            _result(scalar=20_000),  # withdrawals
            _result(scalar=100_000),  # subscription income
            _result(rows=[]),  # by type
            _result(  # by payment method
                rows=[
                    SimpleNamespace(payment_method='card', type='deposit', count=1, total_amount=50_000),
                    SimpleNamespace(
                        payment_method='card', type='subscription_payment', count=1, total_amount=100_000
                    ),
                ]
            ),
            _result(scalar=0),  # today count
            _result(rows=[]),  # today income
        ]
    )

    stats = await get_transactions_statistics(db, start_date=NOW, end_date=NOW)

    totals = stats['totals']
    assert totals['income_toman'] == 150_000
    assert totals['expenses_toman'] == 20_000
    assert totals['profit_toman'] == 130_000
    assert stats['by_payment_method']['card'] == {'count': 2, 'amount': 150_000, 'amount_toman': 150_000}
    # The raw keys stay in the payload for the cabinet / web API; since Phase C they carry the same
    # Toman as their *_toman twins, because there is no second scale left to convert from.
    assert totals['income_kopeks'] == 150_000
    assert totals['profit_kopeks'] == 130_000


async def test_recent_payments_amounts_and_totals_in_toman() -> None:
    deposit = SimpleNamespace(
        id=10,
        user_id=7833,
        amount_kopeks=50_000,
        type='deposit',
        payment_method='c2c',
        description='واریز کارت‌به‌کارت',
        created_at=NOW,
        is_completed=True,
    )
    purchase = SimpleNamespace(
        id=11,
        user_id=7833,
        amount_kopeks=-10_000,
        type='subscription_payment',
        payment_method='balance',
        description='روزانه',
        created_at=NOW,
        is_completed=True,
    )
    user_row = SimpleNamespace(
        id=7833, telegram_id=6371108688, username=None, first_name='Ali', last_name=None, email=None
    )
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _result(scalars=[deposit, purchase]),
            _result(rows=[user_row]),
            _result(scalar=2),
            _result(rows=[('deposit', 50_000)]),
            _result(rows=[('deposit', 1_050_000), ('subscription_payment', 200_000)]),
        ]
    )

    response = await get_recent_payments(limit=50, admin=SimpleNamespace(id=433), db=db)

    by_id = {p.id: p for p in response.payments}
    assert by_id[10].amount_rubles == 50_000
    assert by_id[11].amount_rubles == 10_000
    assert response.total_today_toman == 50_000
    # 1,050,000 deposit + 200,000 subscription payment, both Toman since revision 0115.
    assert response.total_week_toman == 1_250_000
    assert response.total_today_kopeks == 50_000
    assert response.total_week_kopeks == 1_250_000
