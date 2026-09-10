"""End-to-end check of the email-login gate through a real FastAPI app.

Adapted from upstream fdebcad1. The unit tests call handlers directly with dummies;
here the request goes through the router, dependencies and a session to a real
(in-memory) database — like the curl from the bug report.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cabinet.auth import email_auth_gate as gate
from app.cabinet.dependencies import get_cabinet_db
from app.cabinet.routes.auth import router as auth_router
from app.database.models import SystemSetting, User
from tests.fixtures.sqlite_memory import memory_session


TABLES = (SystemSetting.__table__, User.__table__)

REGISTER_BODY = {
    'email': 'test@example.org',
    'password': 'Str0ng-Passw0rd!',
    'first_name': 'Test',
    'accepted_legal_documents': ['public_offer', 'privacy_policy'],
}
LOGIN_BODY = {'email': 'test@example.org', 'password': 'Str0ng-Passw0rd!'}


def _app(db: AsyncSession) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router, prefix='/cabinet')

    async def _db() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_cabinet_db] = _db
    return app


async def _set_flag(db: AsyncSession, value: str) -> None:
    db.add(SystemSetting(key=gate.EMAIL_AUTH_ENABLED_KEY, value=value))
    await db.commit()


async def _users_count(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(User))).scalar_one()


async def test_disabled_in_admin_refuses_register_and_login_over_http(monkeypatch):
    """The admin turned email login off (DB row) while the environment says on: both
    requests from the report get 403 with the machine code and no user is created."""
    async with memory_session(monkeypatch, TABLES) as db:
        monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', True)
        await _set_flag(db, 'false')

        async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url='http://cabinet') as client:
            register = await client.post('/cabinet/auth/email/register/standalone', json=REGISTER_BODY)
            login = await client.post('/cabinet/auth/email/login', json=LOGIN_BODY)

        assert register.status_code == 403, register.text
        assert register.json()['detail']['code'] == gate.EMAIL_AUTH_DISABLED_CODE
        assert login.status_code == 403, login.text
        assert login.json()['detail']['code'] == gate.EMAIL_AUTH_DISABLED_CODE
        assert await _users_count(db) == 0


async def test_enabled_in_admin_lets_request_through_the_gate(monkeypatch):
    """The other side: 'true' in the DB with the environment off — the request passes the
    gate and hits the ordinary password check (401), not a 403."""
    from app.cabinet.routes import auth

    async def not_limited(*_args, **_kwargs):
        return False

    async with memory_session(monkeypatch, TABLES) as db:
        monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', False)
        monkeypatch.setattr(auth.RateLimitCache, 'is_ip_rate_limited', not_limited)
        await _set_flag(db, 'true')

        async with AsyncClient(transport=ASGITransport(app=_app(db)), base_url='http://cabinet') as client:
            login = await client.post('/cabinet/auth/email/login', json=LOGIN_BODY)

        assert login.status_code == 401, login.text
        assert login.json()['detail'] == 'Invalid email or password'
