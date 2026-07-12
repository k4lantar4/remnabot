"""Tests for subscription note PATCH API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.cabinet.routes.subscription_modules import multi_tariff
from app.services.partner_checkout import sanitize_purchase_note


def test_sanitize_purchase_note_caps_length() -> None:
    assert len(sanitize_purchase_note('x' * 600) or '') == 500


@pytest.mark.asyncio
async def test_update_subscription_note_sets_sanitized_value(monkeypatch: pytest.MonkeyPatch) -> None:
    subscription = SimpleNamespace(
        id=7,
        user_id=1,
        purchase_note=None,
        updated_at=None,
        actual_status='active',
        tariff=None,
        tariff_id=None,
        traffic_limit_gb=10,
        traffic_used_gb=0.0,
        device_limit=1,
        end_date=datetime.now(UTC) + timedelta(days=30),
        subscription_url=None,
        subscription_crypto_link=None,
        is_trial=False,
        is_daily_paused=False,
        connected_squads=[],
        account_sequence=1,
        panel_username=None,
        user_disabled=False,
    )
    user = SimpleNamespace(id=1)

    monkeypatch.setattr(
        multi_tariff,
        '_get_owned_subscription',
        AsyncMock(return_value=subscription),
    )
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    result = await multi_tariff.update_subscription_note(
        7,
        multi_tariff.PurchaseNoteUpdateRequest(purchase_note='  hello  '),
        user=user,
        db=db,
    )

    assert subscription.purchase_note == 'hello'
    assert result.purchase_note == 'hello'
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_subscription_note_rejects_foreign_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import HTTPException

    monkeypatch.setattr(
        multi_tariff,
        '_get_owned_subscription',
        AsyncMock(side_effect=HTTPException(status_code=404, detail='Subscription not found')),
    )

    with pytest.raises(HTTPException) as exc:
        await multi_tariff.update_subscription_note(
            99,
            multi_tariff.PurchaseNoteUpdateRequest(purchase_note='note'),
            user=SimpleNamespace(id=1),
            db=AsyncMock(),
        )
    assert exc.value.status_code == 404
