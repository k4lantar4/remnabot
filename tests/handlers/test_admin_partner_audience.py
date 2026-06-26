"""Admin partner audience targeting for broadcast, polls, and pinned messages."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.database.models import PartnerStatus, User, UserStatus


def _make_user(*, user_id: int, telegram_id: int | None, partner_status: str) -> User:
    user = MagicMock(spec=User)
    user.id = user_id
    user.telegram_id = telegram_id
    user.partner_status = partner_status
    user.status = UserStatus.ACTIVE.value
    return user


@pytest.mark.asyncio
async def test_get_approved_partner_users_filters_status_and_telegram():
    partner = _make_user(user_id=1, telegram_id=111, partner_status=PartnerStatus.APPROVED.value)
    scalars = MagicMock()
    scalars.all.return_value = [partner]
    result = MagicMock()
    result.scalars.return_value = scalars
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    from app.database.crud.user import get_approved_partner_users

    users = await get_approved_partner_users(db, telegram_only=True)
    assert [u.id for u in users] == [1]
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_approved_partner_users():
    result = MagicMock()
    result.scalar.return_value = 5
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    from app.database.crud.user import count_approved_partner_users

    assert await count_approved_partner_users(db, telegram_only=True) == 5


@pytest.mark.asyncio
async def test_get_target_users_count_partners(monkeypatch):
    from app.handlers.admin import messages as mod

    async def fake_count(db, telegram_only=True):
        return 3

    monkeypatch.setattr(
        'app.database.crud.user.count_approved_partner_users',
        fake_count,
    )
    assert await mod.get_target_users_count(AsyncMock(), 'partners') == 3


@pytest.mark.asyncio
async def test_get_target_users_partners(monkeypatch):
    from app.handlers.admin import messages as mod

    partner = _make_user(user_id=7, telegram_id=777, partner_status=PartnerStatus.APPROVED.value)

    async def fake_users(db, telegram_only=True):
        return [partner]

    monkeypatch.setattr(
        'app.database.crud.user.get_approved_partner_users',
        fake_users,
    )
    users = await mod.get_target_users(AsyncMock(), 'partners')
    assert [u.id for u in users] == [7]


@pytest.mark.asyncio
async def test_resolve_pinned_recipient_telegram_ids_partners(monkeypatch):
    from app.services import pinned_message_service as svc

    partner = _make_user(user_id=2, telegram_id=999, partner_status=PartnerStatus.APPROVED.value)

    async def fake_partners(db, telegram_only=True):
        return [partner]

    monkeypatch.setattr(
        'app.database.crud.user.get_approved_partner_users',
        fake_partners,
    )

    ids = await svc._resolve_pinned_recipient_telegram_ids(AsyncMock(), target='partners')
    assert ids == [999]
