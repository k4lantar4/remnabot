"""CABINET_EMAIL_AUTH_ENABLED closes email login entirely, not just the button.

Adapted from upstream 23a58172 + fdebcad1. Before: the flag only hid the button in
the cabinet, while /email/register/standalone, /email/login and the other
email/password routes accepted direct requests (scripts registered throwaway
addresses and took trials). And the admin toggle writes a row to system_settings
that ``settings`` in memory never sees, so even an honest env check would disagree
with what the admin sees.

Invariant: one resolver (the DB row beats the environment, parsed like the settings
editor parses it) and one gate first thing in every email/password route — before
the rate limiter, before Redis and before the users table.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.database.models import SystemSetting
from tests.fixtures.sqlite_memory import memory_session


AUTH_FILE = Path(__file__).resolve().parents[2] / 'app' / 'cabinet' / 'routes' / 'auth.py'


class Reached(Exception):
    """Sentinel: the handler passed the gate and reached the rate limiter."""


def _db_without_row():
    """A session with no flag row: the resolver falls back to settings."""
    return SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)))


# --------------------------------------------------------------------------- resolver


async def test_db_row_overrides_env(monkeypatch):
    from app.cabinet.auth import email_auth_gate as gate

    async with memory_session(monkeypatch, [SystemSetting.__table__]) as db:
        monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', True)
        db.add(SystemSetting(key=gate.EMAIL_AUTH_ENABLED_KEY, value='false'))
        await db.commit()
        assert await gate.is_email_auth_enabled(db) is False

        monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', False)
        row = (
            await db.execute(select(SystemSetting).where(SystemSetting.key == gate.EMAIL_AUTH_ENABLED_KEY))
        ).scalar_one()
        row.value = 'True'
        await db.commit()
        assert await gate.is_email_auth_enabled(db) is True


async def test_env_applies_when_no_db_row(monkeypatch):
    from app.cabinet.auth import email_auth_gate as gate

    async with memory_session(monkeypatch, [SystemSetting.__table__]) as db:
        monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', False)
        assert await gate.is_email_auth_enabled(db) is False
        monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', True)
        assert await gate.is_email_auth_enabled(db) is True


async def test_require_raises_403_with_machine_code(monkeypatch):
    from app.cabinet.auth import email_auth_gate as gate

    monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', False)
    with pytest.raises(HTTPException) as denied:
        await gate.require_email_auth_enabled(_db_without_row())
    assert denied.value.status_code == 403
    assert denied.value.detail['code'] == gate.EMAIL_AUTH_DISABLED_CODE == 'email_auth_disabled'

    monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', True)
    assert await gate.require_email_auth_enabled(_db_without_row()) is None


@pytest.mark.parametrize(
    ('stored', 'expected'),
    [('true', True), ('True', True), ('1', True), ('yes', True), ('false', False), ('0', False), ('no', False)],
)
async def test_db_value_parsed_like_settings_editor(monkeypatch, stored, expected):
    """The admin toggle writes 'true', the settings editor and the .env-to-DB import write raw '1'."""
    from app.cabinet.auth import email_auth_gate as gate

    async with memory_session(monkeypatch, [SystemSetting.__table__]) as db:
        monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', not expected)
        db.add(SystemSetting(key=gate.EMAIL_AUTH_ENABLED_KEY, value=stored))
        await db.commit()
        assert await gate.is_email_auth_enabled(db) is expected


async def test_garbage_db_value_falls_back_to_env(monkeypatch):
    from app.cabinet.auth import email_auth_gate as gate

    async with memory_session(monkeypatch, [SystemSetting.__table__]) as db:
        db.add(SystemSetting(key=gate.EMAIL_AUTH_ENABLED_KEY, value='maybe'))
        await db.commit()
        monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', False)
        assert await gate.is_email_auth_enabled(db) is False
        monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', True)
        assert await gate.is_email_auth_enabled(db) is True


# --------------------------------------------------------------------------- routes

GATED_HANDLERS = (
    'register_email',
    'verify_email_merge',
    'register_email_standalone',
    'verify_email',
    'resend_verification',
    'login_email',
    'forgot_password',
    'reset_password',
)


def _call(handler_name: str, db):
    """Call the real handler with dummies: before the gate it touches none of them."""
    from app.cabinet.routes import auth

    handler = getattr(auth, handler_name)
    if handler_name == 'resend_verification':
        return handler(user=object(), db=db)
    kwargs = {'request': object(), 'raw_request': object(), 'db': db}
    if handler_name in {'register_email', 'verify_email_merge'}:
        kwargs['user'] = object()
    return handler(**kwargs)


@pytest.mark.parametrize('handler_name', GATED_HANDLERS)
async def test_handler_refuses_before_touching_anything(monkeypatch, handler_name):
    from app.cabinet.auth import email_auth_gate as gate
    from app.cabinet.routes import auth

    monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', False)

    async def rate_limit_must_not_run(*_args, **_kwargs):
        raise AssertionError('the gate must come before the rate limiter: disabled login must not touch Redis')

    monkeypatch.setattr(auth.RateLimitCache, 'is_ip_rate_limited', rate_limit_must_not_run)
    db = _db_without_row()

    with pytest.raises(HTTPException) as denied:
        await _call(handler_name, db)

    assert denied.value.status_code == 403
    assert denied.value.detail['code'] == gate.EMAIL_AUTH_DISABLED_CODE
    # the only database access is reading the flag row
    assert db.execute.await_count == 1


@pytest.mark.parametrize('handler_name', ('register_email_standalone', 'login_email'))
async def test_handler_proceeds_when_enabled(monkeypatch, handler_name):
    from app.cabinet.auth import email_auth_gate as gate
    from app.cabinet.routes import auth

    monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', True)

    async def reached(*_args, **_kwargs):
        raise Reached

    monkeypatch.setattr(auth.RateLimitCache, 'is_ip_rate_limited', reached)
    monkeypatch.setattr(auth, 'get_client_ip', lambda _request: '127.0.0.1')

    with pytest.raises(Reached):
        await _call(handler_name, _db_without_row())


# --------------------------------------------------------------------------- guard

UNGATED_EMAIL_ROUTES = {
    # changing the email of a user who is already signed in is profile, not email login
    '/email/change',
    '/email/change/verify',
    '/email/change/cancel',
    '/email/change/status',
}


def _route_bodies(source: str) -> dict[str, str]:
    bodies: dict[str, str] = {}
    for match in re.finditer(r"@router\.(?:post|get)\('([^']+)'", source):
        start = match.start()
        nxt = source.find('@router.', match.end())
        bodies[match.group(1)] = source[start : nxt if nxt > 0 else len(source)]
    return bodies


def test_every_email_and_password_route_is_gated():
    """A new /email/* or /password/* route without the gate is a red test, not a hole in prod."""
    bodies = _route_bodies(AUTH_FILE.read_text(encoding='utf-8'))
    subject = {
        path: body
        for path, body in bodies.items()
        if (path.startswith('/email/') or path.startswith('/password/')) and path not in UNGATED_EMAIL_ROUTES
    }
    assert len(subject) == len(GATED_HANDLERS), sorted(subject)
    for path, body in subject.items():
        gate_at = body.find('await require_email_auth_enabled(db)')
        assert gate_at > 0, f'{path}: no email-login gate'
        limiter_at = body.find('RateLimitCache')
        assert limiter_at < 0 or gate_at < limiter_at, f'{path}: the gate must come before the rate limiter'


# --------------------------------------------------------------------------- provider list


async def test_linked_providers_follow_the_same_switch(monkeypatch):
    """The sign-in methods list in the profile reads the same switch as the UI and the routes."""
    from app.cabinet.auth import email_auth_gate as gate
    from app.cabinet.routes import account_linking

    async with memory_session(monkeypatch, [SystemSetting.__table__]) as db:
        monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', True)
        db.add(SystemSetting(key=gate.EMAIL_AUTH_ENABLED_KEY, value='false'))
        await db.commit()
        assert 'email' not in await account_linking._get_active_providers(db)

        row = (
            await db.execute(select(SystemSetting).where(SystemSetting.key == gate.EMAIL_AUTH_ENABLED_KEY))
        ).scalar_one()
        row.value = 'true'
        await db.commit()
        assert 'email' in await account_linking._get_active_providers(db)


async def test_public_branding_flag_uses_the_same_resolver(monkeypatch):
    """GET /branding/email-auth used `== 'true'` and read a stored '1' as disabled."""
    from app.cabinet.auth import email_auth_gate as gate
    from app.cabinet.routes import branding

    async with memory_session(monkeypatch, [SystemSetting.__table__]) as db:
        monkeypatch.setattr(gate.settings, 'CABINET_EMAIL_AUTH_ENABLED', False)
        db.add(SystemSetting(key=gate.EMAIL_AUTH_ENABLED_KEY, value='1'))
        await db.commit()
        assert (await branding.get_email_auth_enabled(db=db)).enabled is True
