"""The bulk «add balance» action credits the Toman the owner typed, 1:1 (FINDINGS F-068).

``users.balance_kopeks`` is Toman 1:1 and ``add_user_balance`` credits its argument unchanged, so
the amount that reaches it must be the typed Toman — never the typed Toman x100. The single-user
editor already does this through ``amount_display`` (``admin_users.update_user_balance``); the bulk
action gets the same field, while the legacy ``amount_kopeks`` keeps meaning the raw storage amount
so an already-open admin tab keeps working.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

import app.cabinet.routes.admin_bulk_actions as bulk
from app.cabinet.schemas.bulk_actions import BulkActionParams, BulkActionType
from app.config import settings


TYPED_TOMAN = 50_000


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=7, username='owner', balance_kopeks=0)


def _capture_credit(monkeypatch) -> list[int]:
    credited: list[int] = []

    async def fake_add_user_balance(*, db, user, amount_kopeks, **kwargs):
        credited.append(amount_kopeks)
        return True

    monkeypatch.setattr(bulk, 'add_user_balance', fake_add_user_balance)
    return credited


@pytest.mark.asyncio
async def test_amount_display_credits_the_typed_toman_one_to_one(monkeypatch) -> None:
    credited = _capture_credit(monkeypatch)

    result = await bulk._do_add_balance(
        AsyncMock(), _user(), BulkActionParams(amount_display=TYPED_TOMAN), dry_run=False
    )

    assert credited == [TYPED_TOMAN]
    assert result.success is True


@pytest.mark.asyncio
async def test_legacy_amount_kopeks_still_credits_the_raw_storage_amount(monkeypatch) -> None:
    """Backward compatibility: the field an open admin tab still sends keeps its meaning."""
    credited = _capture_credit(monkeypatch)

    await bulk._do_add_balance(AsyncMock(), _user(), BulkActionParams(amount_kopeks=TYPED_TOMAN), dry_run=False)

    assert credited == [TYPED_TOMAN]


@pytest.mark.asyncio
async def test_messages_report_toman_and_never_rubles(monkeypatch) -> None:
    _capture_credit(monkeypatch)
    params = BulkActionParams(amount_display=TYPED_TOMAN)

    dry = await bulk._do_add_balance(AsyncMock(), _user(), params, dry_run=True)
    done = await bulk._do_add_balance(AsyncMock(), _user(), params, dry_run=False)

    expected = settings.format_balance(TYPED_TOMAN)
    for message in (dry.message, done.message):
        assert expected in message
        assert '₽' not in message


def test_both_amount_fields_together_are_refused() -> None:
    with pytest.raises(HTTPException) as excinfo:
        bulk._resolve_balance_amount_toman(BulkActionParams(amount_display=TYPED_TOMAN, amount_kopeks=TYPED_TOMAN))

    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
async def test_add_balance_without_an_amount_is_refused() -> None:
    with pytest.raises(HTTPException) as excinfo:
        await bulk._validate_and_prepare(MagicMock(), BulkActionType.ADD_BALANCE, BulkActionParams())

    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
async def test_a_typed_amount_is_validated_before_the_batch_runs(monkeypatch) -> None:
    """``_validate_and_prepare`` accepts the new field, so the batch is not rejected up front."""
    assert (
        await bulk._validate_and_prepare(
            MagicMock(), BulkActionType.ADD_BALANCE, BulkActionParams(amount_display=TYPED_TOMAN)
        )
        is None
    )
