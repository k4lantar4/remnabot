"""Cabinet admin C2C receipt review — list, search, stats and detail over a real (SQLite) session.

Requests go through the real router so ``response_model`` serialisation is exercised; only the RBAC
closure is bypassed, and a separate test pins which permission every route demands.
"""

from __future__ import annotations

import contextlib
import inspect
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.cabinet.dependencies import get_cabinet_db
from app.cabinet.routes import admin_c2c_receipts as route, media as media_route
from app.database.models import C2cReceipt, C2cReceiptStatus, Transaction, User
from tests.fixtures.sqlite_memory import memory_session


TABLES = (User.__table__, Transaction.__table__, C2cReceipt.__table__)
NOW = datetime.now(UTC).replace(microsecond=0)
FILE_ID = 'AgACAgQAAxkBAAIBc2Mfile_id_1234567890'
ADMIN = SimpleNamespace(id=1, telegram_id=777, username='boss')


def _is_permission_closure(call) -> bool:
    return getattr(call, '__name__', '') == 'dependency' and getattr(call, '__module__', '').endswith(
        'cabinet.dependencies'
    )


async def _seed(db) -> None:
    db.add(User(id=1, telegram_id=777, username='boss', first_name='Owner', language='fa'))
    db.add(
        User(
            id=10,
            telegram_id=1001,
            username='alice',
            first_name='Ali',
            last_name='Rezaei',
            email='ali@example.com',
            language='fa',
            balance_kopeks=40_000,
        )
    )
    db.add(User(id=11, telegram_id=2002, username='bob', first_name='Bob', language='fa'))
    db.add(
        C2cReceipt(
            id=1,
            user_id=10,
            amount_kopeks=250_000,
            status=C2cReceiptStatus.PENDING.value,
            receipt_type='photo',
            receipt_file_id=FILE_ID,
            receipt_text='paid from Mellat',
            card_index=0,
            card_label='Melli',
            created_at=NOW - timedelta(hours=3),
            updated_at=NOW - timedelta(hours=3),
            expires_at=NOW + timedelta(hours=21),
        )
    )
    db.add(
        C2cReceipt(
            id=2,
            user_id=11,
            amount_kopeks=100_000,
            approved_amount_kopeks=90_000,
            status=C2cReceiptStatus.APPROVED.value,
            receipt_type='text',
            receipt_text='ref 123456',
            card_index=1,
            card_label='Old card',
            reviewed_by_user_id=1,
            reviewed_via='cabinet',
            created_at=NOW - timedelta(hours=2),
            updated_at=NOW - timedelta(hours=2),
            processed_at=NOW - timedelta(minutes=100),
        )
    )
    db.add(
        C2cReceipt(
            id=3,
            user_id=10,
            amount_kopeks=500_000,
            status=C2cReceiptStatus.REJECTED.value,
            receipt_type='photo',
            receipt_file_id=FILE_ID,
            card_index=0,
            card_label='Melli',
            reviewed_by_telegram_id=777,
            rejection_reason_key='amt_mismatch',
            rejection_reason='amt_mismatch',
            created_at=NOW - timedelta(hours=1),
            updated_at=NOW - timedelta(hours=1),
            processed_at=NOW - timedelta(minutes=30),
        )
    )
    await db.commit()


@contextlib.asynccontextmanager
async def _client(monkeypatch):
    cards = [{'label': 'Melli', 'number': '6037991234560001', 'holder': 'Owner'}]
    monkeypatch.setattr(route, 'get_card_by_index', lambda index: cards[index] if 0 <= index < len(cards) else None)
    async with memory_session(monkeypatch, TABLES) as db:
        await _seed(db)
        app = FastAPI()
        app.include_router(route.router, prefix='/cabinet')
        app.include_router(media_route.router, prefix='/cabinet')
        app.dependency_overrides[get_cabinet_db] = lambda: db
        for candidate in route.router.routes:
            for dependant in candidate.dependant.dependencies:
                if _is_permission_closure(dependant.call):
                    app.dependency_overrides[dependant.call] = lambda: ADMIN
        with TestClient(app) as http:
            yield http


def _ids(response) -> list[int]:
    assert response.status_code == 200, response.text
    return [item['id'] for item in response.json()['items']]


@pytest.mark.asyncio
async def test_status_filters_return_their_rows_newest_first(monkeypatch):
    async with _client(monkeypatch) as http:
        assert _ids(http.get('/cabinet/admin/c2c-receipts')) == [3, 2, 1]
        assert _ids(http.get('/cabinet/admin/c2c-receipts?status=all')) == [3, 2, 1]
        assert _ids(http.get('/cabinet/admin/c2c-receipts?status=pending')) == [1]
        assert _ids(http.get('/cabinet/admin/c2c-receipts?status=approved')) == [2]
        assert _ids(http.get('/cabinet/admin/c2c-receipts?status=rejected')) == [3]
        assert _ids(http.get('/cabinet/admin/c2c-receipts?status=expired')) == []
        assert http.get('/cabinet/admin/c2c-receipts?status=bogus').status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('search', 'expected'),
    [
        ('alice', [3, 1]),
        ('@bob', [2]),
        ('ALI@EXAMPLE', [3, 1]),
        ('Rezaei', [3, 1]),
        ('2002', [2]),
        ('#2', [2]),
        ('500,000', [3]),
        ('nobody', []),
    ],
)
async def test_search_matches_user_and_receipt_fields(monkeypatch, search, expected):
    async with _client(monkeypatch) as http:
        assert _ids(http.get('/cabinet/admin/c2c-receipts', params={'search': search})) == expected


@pytest.mark.asyncio
async def test_date_range_and_pagination(monkeypatch):
    async with _client(monkeypatch) as http:
        since = (NOW - timedelta(minutes=150)).isoformat()
        assert _ids(http.get('/cabinet/admin/c2c-receipts', params={'date_from': since})) == [3, 2]

        page = http.get('/cabinet/admin/c2c-receipts?per_page=2&page=2')
        assert _ids(page) == [1]
        body = page.json()
        assert (body['total'], body['page'], body['per_page'], body['pages']) == (3, 2, 2, 2)


@pytest.mark.asyncio
async def test_stats_count_the_filtered_set(monkeypatch):
    async with _client(monkeypatch) as http:
        everything = http.get('/cabinet/admin/c2c-receipts/stats')
        alice = http.get('/cabinet/admin/c2c-receipts/stats', params={'search': 'alice'})

    assert everything.status_code == 200, everything.text
    assert everything.json() == {'total': 3, 'pending': 1, 'approved': 1, 'rejected': 1, 'expired': 0, 'cancelled': 0}
    assert alice.json() == {'total': 2, 'pending': 1, 'approved': 0, 'rejected': 1, 'expired': 0, 'cancelled': 0}


@pytest.mark.asyncio
async def test_items_carry_toman_amounts_user_and_reviewer(monkeypatch):
    async with _client(monkeypatch) as http:
        items = {item['id']: item for item in http.get('/cabinet/admin/c2c-receipts').json()['items']}

    approved = items[2]
    assert approved['amount_toman'] == 100_000
    assert approved['amount_kopeks'] == 10_000_000
    assert approved['approved_amount_toman'] == 90_000
    assert approved['has_receipt'] is True
    assert approved['reviewer'] == {'user_id': 1, 'telegram_id': None, 'label': 'boss', 'via': 'cabinet'}
    assert approved['user'] == {
        'id': 11,
        'telegram_id': 2002,
        'username': 'bob',
        'full_name': 'Bob',
        'email': None,
    }

    rejected = items[3]
    # Decided in the bot before 0119: only the telegram id is known, resolved to the admin's name.
    assert rejected['reviewer'] == {'user_id': None, 'telegram_id': 777, 'label': 'boss', 'via': None}
    assert rejected['rejection_reason_key'] == 'amt_mismatch'
    assert rejected['user']['full_name'] == 'Ali Rezaei'

    assert items[1]['reviewer'] == {'user_id': None, 'telegram_id': None, 'label': None, 'via': None}


@pytest.mark.asyncio
async def test_detail_signs_the_receipt_image_and_masks_the_card(monkeypatch):
    async with _client(monkeypatch) as http:
        photo = http.get('/cabinet/admin/c2c-receipts/1')
        text_only = http.get('/cabinet/admin/c2c-receipts/2')
        missing = http.get('/cabinet/admin/c2c-receipts/999')

    assert photo.status_code == 200, photo.text
    body = photo.json()
    assert body['receipt_media_file_id'] == FILE_ID
    assert media_route._verify_media_token(FILE_ID, body['receipt_media_token'])
    assert body['card_number_masked'] == '**** 0001'
    assert body['receipt_text'] == 'paid from Mellat'
    assert body['user_balance_toman'] == 40_000

    assert text_only.status_code == 200, text_only.text
    assert text_only.json()['receipt_media_file_id'] is None
    assert text_only.json()['receipt_media_token'] is None
    # The card at index 1 is no longer configured under that label: never show a different PAN.
    assert text_only.json()['card_number_masked'] is None

    assert missing.status_code == 404


def test_every_route_demands_the_payments_permission():
    demanded: dict[tuple[str, str], tuple[str, ...]] = {}
    for candidate in route.router.routes:
        closures = [d.call for d in candidate.dependant.dependencies if _is_permission_closure(d.call)]
        assert len(closures) == 1, candidate.path
        permissions = inspect.getclosurevars(closures[0]).nonlocals['permissions']
        for method in candidate.methods:
            demanded[(method, candidate.path)] = permissions

    reads = {key: value for key, value in demanded.items() if key[0] == 'GET'}
    writes = {key: value for key, value in demanded.items() if key[0] == 'POST'}
    assert reads and all(value == ('payments:read',) for value in reads.values()), reads
    assert all(value == ('payments:edit',) for value in writes.values()), writes
