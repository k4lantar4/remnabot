"""Tests for C2C admin group receipt message builders."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from app.database.models import C2cReceiptStatus
from app.plugins.c2c.admin_messages import build_c2c_admin_receipt_body, build_c2c_resolved_keyboard
from app.plugins.c2c.constants import C2C_CALLBACK_RESOLVED_PREFIX


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=1, full_name='Test User', username='testuser', telegram_id=123456)


def _receipt(**overrides) -> SimpleNamespace:
    base = {
        'id': 42,
        'amount_kopeks': 500_000,
        'status': C2cReceiptStatus.PENDING.value,
        'card_label': 'Card A',
        'created_at': datetime(2026, 6, 21, 10, 30, tzinfo=UTC),
        'processed_at': None,
        'approved_amount_kopeks': None,
        'rejection_reason_key': None,
        'rejection_reason': None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_pending_body_includes_sent_at():
    body = build_c2c_admin_receipt_body(_receipt(), _user(), lang='fa')
    assert 'ارسال' in body or 'Sent' in body
    assert 'Test User' in body
    assert '500' in body


def test_resolved_approved_body_includes_credited_amount():
    receipt = _receipt(
        status=C2cReceiptStatus.APPROVED.value,
        processed_at=datetime(2026, 6, 21, 11, 0, tzinfo=UTC),
        approved_amount_kopeks=450_000,
    )
    body = build_c2c_admin_receipt_body(receipt, _user(), lang='fa', admin_label='admin1')
    assert 'تأیید' in body or 'Approved' in body
    assert 'admin1' in body
    assert '450' in body


def test_resolved_rejected_body_includes_reason():
    receipt = _receipt(
        status=C2cReceiptStatus.REJECTED.value,
        processed_at=datetime(2026, 6, 21, 11, 0, tzinfo=UTC),
        rejection_reason_key='unclear',
    )
    body = build_c2c_admin_receipt_body(receipt, _user(), lang='fa', admin_label='admin2')
    assert 'رد' in body or 'Rejected' in body
    assert 'admin2' in body
    assert 'نامشخص' in body or 'unclear' in body.lower()


def test_resolved_keyboard_single_button():
    approved_kb = build_c2c_resolved_keyboard(7, C2cReceiptStatus.APPROVED.value, lang='fa')
    rejected_kb = build_c2c_resolved_keyboard(7, C2cReceiptStatus.REJECTED.value, lang='fa')

    assert len(approved_kb.inline_keyboard) == 1
    assert len(approved_kb.inline_keyboard[0]) == 1
    assert approved_kb.inline_keyboard[0][0].callback_data == f'{C2C_CALLBACK_RESOLVED_PREFIX}7'

    assert len(rejected_kb.inline_keyboard) == 1
    assert rejected_kb.inline_keyboard[0][0].callback_data == f'{C2C_CALLBACK_RESOLVED_PREFIX}7'
