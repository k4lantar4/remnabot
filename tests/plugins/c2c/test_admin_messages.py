"""Tests for C2C admin receipt message layout."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from types import SimpleNamespace

from app.database.models import C2cReceiptStatus
from app.plugins.c2c.admin_messages import C2C_MESSAGE_SEPARATOR, build_c2c_admin_receipt_body


def _user(*, telegram_id: int = 123456789):
    return SimpleNamespace(
        id=1,
        full_name='Test User',
        username='testuser',
        telegram_id=telegram_id,
    )


def _receipt(**overrides):
    defaults = {
        'id': 42,
        'amount_kopeks': 500_000,
        'status': C2cReceiptStatus.PENDING.value,
        'card_label': '6037991234567890',
        'created_at': datetime(2026, 6, 22, 14, 30, tzinfo=UTC),
        'processed_at': None,
        'approved_amount_kopeks': None,
        'rejection_reason': None,
        'rejection_reason_key': None,
        'receipt_text': None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_pending_body_wraps_telegram_id_in_code():
    body = build_c2c_admin_receipt_body(_receipt(), _user(), lang='ru')

    assert '<code>123456789</code>' in body


def test_footer_includes_time_pattern():
    body = build_c2c_admin_receipt_body(_receipt(), _user(), lang='ru')

    footer = body.split(C2C_MESSAGE_SEPARATOR, 1)[1]
    assert re.search(r'\d{2}:\d{2}', footer)


def test_header_footer_separated_by_separator():
    body = build_c2c_admin_receipt_body(_receipt(), _user(), lang='ru')

    assert C2C_MESSAGE_SEPARATOR in body
    header, rest = body.split('\n\n', 1)
    assert C2C_MESSAGE_SEPARATOR in rest
    assert C2C_MESSAGE_SEPARATOR not in header


def test_resolved_approve_includes_credited_line_in_footer_only():
    credited_kopeks = 500_000
    receipt = _receipt(
        status=C2cReceiptStatus.APPROVED.value,
        processed_at=datetime(2026, 6, 22, 15, 0, tzinfo=UTC),
        approved_amount_kopeks=credited_kopeks,
    )

    body = build_c2c_admin_receipt_body(receipt, _user(), lang='fa', admin_label='admin1')

    header, footer = body.split(C2C_MESSAGE_SEPARATOR, 1)
    footer_lines = [line for line in footer.split('\n') if line.strip()]
    header_lines = [line for line in header.split('\n') if line.strip()]
    credited_lines = [line for line in footer_lines if 'واریز' in line or 'Credited' in line]
    assert credited_lines
    assert not any('واریز' in line or 'Credited' in line for line in header_lines)
