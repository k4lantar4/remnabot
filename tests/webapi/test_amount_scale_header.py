"""Phase C-2: ``X-Amount-Scale: toman`` switches a whole request to Toman 1:1, through real routes.

The cabinet opts in path by path, so the same route must answer on both scales: Toman when the
header asks for it, the old x100 otherwise (the miniapp and unconverted cabinet screens send nothing).
The response echoes the scale it used so the cabinet can refuse a mismatch instead of rendering 100x.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.cabinet.dependencies import get_cabinet_db, get_current_cabinet_user
from app.cabinet.routes import balance as balance_routes
from app.config import settings
from app.plugins.c2c import cabinet as c2c_cabinet
from app.utils.wire_scale import CATALOG_WIRE, TOMAN_WIRE, current_wire_scale, wire_catalog_kopeks
from app.webapi.middleware import AmountScaleMiddleware


TOMAN = {'X-Amount-Scale': 'toman'}
CARD = {'label': 'Melli', 'number': '6037000000000001', 'holder': 'Ali'}
C2C_METHOD = {
    'id': 'c2c',
    'name': 'کارت به کارت',
    'description': None,
    'min_amount_kopeks': 100_000,
    'max_amount_kopeks': 10_000_000,
    'options': None,
    'quick_amounts': [250_000],
    'sort_order': 0,
    'open_url_direct': False,
}


def _receipt(amount_toman: int):
    return SimpleNamespace(
        id=7,
        status='pending',
        amount_kopeks=amount_toman,
        card_index=0,
        card_label='Melli',
        expires_at=None,
    )


@pytest.fixture
def client(monkeypatch):
    user = SimpleNamespace(id=42, telegram_id=111, language='en', restriction_topup=False)
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar=lambda: True)))
    monkeypatch.setattr(balance_routes, 'get_enabled_methods_for_user', AsyncMock(return_value=[C2C_METHOD]))
    monkeypatch.setattr(settings, 'C2C_GUIDE_TEXT', 'Send the exact amount.', raising=False)

    started: list[int] = []

    async def start(_db, _user, amount_toman):
        started.append(amount_toman)
        return _receipt(amount_toman)

    monkeypatch.setattr(c2c_cabinet, 'start_cabinet_receipt', start)
    monkeypatch.setattr(c2c_cabinet, 'card_for_receipt', lambda _receipt: CARD)

    app = FastAPI()
    app.include_router(balance_routes.router, prefix='/cabinet')
    app.add_middleware(AmountScaleMiddleware)
    app.dependency_overrides[get_current_cabinet_user] = lambda: user
    app.dependency_overrides[get_cabinet_db] = lambda: db

    with TestClient(app) as test_client:
        test_client.started = started
        yield test_client


def test_payment_methods_are_toman_with_the_header(client):
    response = client.get('/cabinet/balance/payment-methods', headers=TOMAN)

    assert response.status_code == 200
    method = response.json()[0]
    assert (method['min_amount_kopeks'], method['max_amount_kopeks'], method['quick_amounts']) == (
        100_000,
        10_000_000,
        [250_000],
    )
    assert response.headers['X-Amount-Scale'] == TOMAN_WIRE
    assert 'X-Amount-Scale' in response.headers['Vary']


def test_payment_methods_stay_x100_without_the_header(client):
    response = client.get('/cabinet/balance/payment-methods')

    method = response.json()[0]
    assert (method['min_amount_kopeks'], method['max_amount_kopeks'], method['quick_amounts']) == (
        10_000_000,
        1_000_000_000,
        [25_000_000],
    )
    assert response.headers['X-Amount-Scale'] == CATALOG_WIRE


def test_c2c_session_reads_a_toman_request_as_toman(client):
    response = client.post('/cabinet/balance/c2c/session', json={'amount_kopeks': 150_000}, headers=TOMAN)

    assert response.status_code == 200, response.text
    assert client.started == [150_000]
    assert response.json()['amount_kopeks'] == 150_000
    assert response.json()['amount_toman'] == 150_000
    assert response.headers['X-Amount-Scale'] == TOMAN_WIRE


def test_c2c_session_reads_an_unmarked_request_as_x100(client):
    response = client.post('/cabinet/balance/c2c/session', json={'amount_kopeks': 15_000_000})

    assert response.status_code == 200, response.text
    assert client.started == [150_000]
    assert response.json()['amount_kopeks'] == 15_000_000
    assert response.json()['amount_toman'] == 150_000


def test_the_per_method_minimum_applies_on_the_toman_scale(client):
    # 50,000 Toman is below C2C's 100,000 minimum; under the old x100 reading it would be 500 Toman.
    response = client.post('/cabinet/balance/c2c/session', json={'amount_kopeks': 50_000}, headers=TOMAN)

    assert response.status_code == 400
    assert client.started == []


def test_the_scale_does_not_outlive_the_request(client):
    client.get('/cabinet/balance/payment-methods', headers=TOMAN)

    assert current_wire_scale() == CATALOG_WIRE


def test_the_web_api_app_negotiates_the_scale_and_lets_the_cabinet_send_and_read_it():
    from fastapi.middleware.cors import CORSMiddleware

    from app.webapi.app import create_web_api_app

    middleware = create_web_api_app().user_middleware
    assert AmountScaleMiddleware in [entry.cls for entry in middleware]
    cors = next(entry for entry in middleware if entry.cls is CORSMiddleware)
    assert 'X-Amount-Scale' in cors.kwargs['allow_headers']
    assert cors.kwargs['expose_headers'] == ['X-Amount-Scale']


@pytest.mark.asyncio
async def test_interleaved_requests_keep_their_own_scale():
    both_inside = asyncio.Event()
    inside = 0

    async def endpoint():
        nonlocal inside
        inside += 1
        if inside == 2:
            both_inside.set()
        await asyncio.wait_for(both_inside.wait(), timeout=5)
        return {'amount': wire_catalog_kopeks(1_000)}

    app = FastAPI()
    app.get('/amount')(endpoint)
    app.add_middleware(AmountScaleMiddleware)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as http:
        toman, catalog = await asyncio.gather(http.get('/amount', headers=TOMAN), http.get('/amount'))

    assert toman.json() == {'amount': 1_000}
    assert catalog.json() == {'amount': 100_000}
