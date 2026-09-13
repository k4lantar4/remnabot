"""F-046: admin «reset subscription», «reset trial» and «disable» on one subscription.

The owner picks one of a user's subscriptions in the admin user card and presses
an action. Before this fix every action hit *all* of the user's subscriptions.
An optional ``subscription_id`` now scopes each action to the chosen one; it must
belong to the path user (404 otherwise). Without it the user-level behaviour stays
as it was (covered in ``tests/services/test_reset_subscription.py``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.cabinet.routes import admin_users
from app.cabinet.schemas.users import DisableUserRequest, ResetSubscriptionRequest, ResetTrialRequest
from app.config import Settings
from app.database.models import SubscriptionStatus


USER_ID = 1


def _sub(sub_id: int, *, tariff_id: int = 3, is_trial: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=sub_id,
        user_id=USER_ID,
        tariff_id=tariff_id,
        tariff=None,
        is_trial=is_trial,
        status=SubscriptionStatus.ACTIVE.value,
        end_date=datetime.now(UTC) + timedelta(days=30),
        remnawave_id=7000 + sub_id,
    )


def _user(subscriptions: list[SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(
        id=USER_ID,
        subscriptions=subscriptions,
        updated_at=None,
        remnawave_id=None,
        status='active',
    )


@pytest.fixture
def two_same_tariff(monkeypatch):
    """A user with two subscriptions of the same tariff (allowed since migration 0091)."""
    subs = [_sub(7), _sub(8)]
    user = _user(subs)
    monkeypatch.setattr(admin_users, 'get_user_by_id', AsyncMock(return_value=user))
    monkeypatch.setattr(Settings, 'is_multi_tariff_enabled', lambda self: True)

    async def owned(_db, subscription_id, user_id):
        for sub in subs:
            if sub.id == subscription_id and sub.user_id == user_id:
                return sub
        raise HTTPException(status_code=404, detail='Subscription not found for this user')

    monkeypatch.setattr(admin_users, '_get_owned_subscription_or_404', owned)
    return user


@pytest.fixture
def panel_calls(monkeypatch) -> list[int]:
    calls: list[int] = []

    class PanelService:
        async def disable_remnawave_user(self, panel_user_id, *, db):
            calls.append(panel_user_id)
            return True

    monkeypatch.setattr('app.services.subscription_service.SubscriptionService', PanelService)
    return calls


def _deletes(db) -> list:
    return [call.args[0] for call in db.execute.await_args_list if str(call.args[0]).startswith('DELETE')]


# --- reset-subscription ------------------------------------------------------


async def test_reset_subscription_with_id_deletes_only_that_subscription(monkeypatch, two_same_tariff, panel_calls):
    grace_checks: list[tuple[int, ...]] = []
    cancelled: list[int] = []

    async def ensure_no_open_grace(_db, subscription_ids):
        grace_checks.append(subscription_ids)

    async def cancel_recurrent(_db, subscription_id):
        cancelled.append(subscription_id)

    monkeypatch.setattr(
        'app.services.grace_access_runtime.ensure_no_open_grace_for_subscriptions', ensure_no_open_grace
    )
    monkeypatch.setattr('app.services.payment.platega.cancel_platega_recurring_for_subscription_safe', cancel_recurrent)
    monkeypatch.setattr('app.services.payment.lava.cancel_lava_recurring_for_subscription_safe', cancel_recurrent)
    db = AsyncMock()

    result = await admin_users.reset_user_subscription(
        USER_ID,
        ResetSubscriptionRequest(deactivate_in_panel=True),
        subscription_id=8,
        admin=SimpleNamespace(id=99),
        db=db,
    )

    assert result.success is True
    assert result.subscription_deleted is True
    assert grace_checks == [(8,), (8,)]
    assert cancelled == [8, 8]
    assert panel_calls == [7008]
    deletes = _deletes(db)
    assert len(deletes) == 2  # server rows of #8, then subscription #8 itself
    subscription_delete = deletes[-1]
    assert 'DELETE FROM subscriptions' in str(subscription_delete)
    assert 'subscriptions.id' in str(subscription_delete)
    assert 'subscriptions.user_id' not in str(subscription_delete)
    assert list(subscription_delete.compile().params.values()) == [8]
    for delete_statement in deletes:
        assert 7 not in delete_statement.compile().params.values()


async def test_reset_subscription_with_foreign_id_is_404_and_touches_nothing(two_same_tariff, panel_calls):
    db = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await admin_users.reset_user_subscription(
            USER_ID,
            ResetSubscriptionRequest(),
            subscription_id=999,
            admin=SimpleNamespace(id=99),
            db=db,
        )

    assert error.value.status_code == 404
    assert panel_calls == []
    assert _deletes(db) == []
    db.commit.assert_not_awaited()


# --- reset-trial -------------------------------------------------------------


async def test_reset_trial_with_id_wipes_only_that_trial(monkeypatch):
    subs = [_sub(7, is_trial=True), _sub(8, is_trial=True)]
    monkeypatch.setattr(admin_users, 'get_user_by_id', AsyncMock(return_value=_user(subs)))
    monkeypatch.setattr(admin_users, '_get_owned_subscription_or_404', AsyncMock(return_value=subs[1]))
    monkeypatch.setattr('app.database.crud.subscription.is_active_paid_subscription', lambda _s: False)
    wiped: list[list[int]] = []

    async def wipe(_db, subscriptions):
        wiped.append([s.id for s in subscriptions])
        return len(subscriptions)

    monkeypatch.setattr('app.database.crud.subscription.wipe_trial_subscriptions', wipe)

    result = await admin_users.reset_user_trial(
        USER_ID, ResetTrialRequest(), subscription_id=8, admin=SimpleNamespace(id=99), db=AsyncMock()
    )

    assert wiped == [[8]]
    assert result.subscription_deleted is True


async def test_reset_trial_with_id_of_paid_subscription_is_400(monkeypatch):
    subs = [_sub(7, is_trial=True), _sub(8, is_trial=False)]
    monkeypatch.setattr(admin_users, 'get_user_by_id', AsyncMock(return_value=_user(subs)))
    monkeypatch.setattr(admin_users, '_get_owned_subscription_or_404', AsyncMock(return_value=subs[1]))
    wipe = AsyncMock()
    monkeypatch.setattr('app.database.crud.subscription.wipe_trial_subscriptions', wipe)

    with pytest.raises(HTTPException) as error:
        await admin_users.reset_user_trial(
            USER_ID, ResetTrialRequest(), subscription_id=8, admin=SimpleNamespace(id=99), db=AsyncMock()
        )

    assert error.value.status_code == 400
    wipe.assert_not_awaited()


# --- disable -----------------------------------------------------------------


async def test_disable_with_id_deactivates_only_that_subscription_and_keeps_account(
    monkeypatch, two_same_tariff, panel_calls
):
    monkeypatch.setattr('app.services.rbac_bootstrap_service.is_protected_from_blocking', lambda _u: False)
    monkeypatch.setattr('app.database.crud.subscription.is_active_paid_subscription', lambda _s: True)
    deactivated: list[int] = []

    async def deactivate(_db, subscription, **_kw):
        deactivated.append(subscription.id)
        subscription.status = SubscriptionStatus.DISABLED.value
        return subscription

    monkeypatch.setattr('app.database.crud.subscription.deactivate_subscription', deactivate)

    result = await admin_users.disable_user(
        USER_ID, DisableUserRequest(), subscription_id=8, admin=SimpleNamespace(id=99), db=AsyncMock()
    )

    assert deactivated == [8]
    assert panel_calls == [7008]
    assert result.subscription_deactivated is True
    assert result.panel_deactivated is True
    assert result.user_blocked is False
    assert two_same_tariff.status == 'active'
    assert two_same_tariff.subscriptions[0].status == SubscriptionStatus.ACTIVE.value


async def test_disable_with_foreign_id_is_404(monkeypatch, two_same_tariff, panel_calls):
    monkeypatch.setattr('app.services.rbac_bootstrap_service.is_protected_from_blocking', lambda _u: False)

    with pytest.raises(HTTPException) as error:
        await admin_users.disable_user(
            USER_ID, DisableUserRequest(), subscription_id=999, admin=SimpleNamespace(id=99), db=AsyncMock()
        )

    assert error.value.status_code == 404
    assert panel_calls == []
    assert two_same_tariff.status == 'active'


def test_subscription_id_is_an_optional_query_param():
    import inspect

    for endpoint in (admin_users.reset_user_subscription, admin_users.reset_user_trial, admin_users.disable_user):
        assert inspect.signature(endpoint).parameters['subscription_id'].default is None
