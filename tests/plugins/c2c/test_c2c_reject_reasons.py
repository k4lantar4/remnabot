"""Tests for C2C structured reject reason catalog."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.plugins.c2c.reject_reasons import (
    C2C_REJECT_REASONS,
    get_reject_reason_codes,
    resolve_user_reject_reason_text,
)


@pytest.fixture
def fa_texts():
  from app.localization.texts import get_texts

  return get_texts('fa')


def test_each_code_resolves_except_silent(fa_texts):
    for code in get_reject_reason_codes():
        text = resolve_user_reject_reason_text(code, fa_texts)
        if code == 'silent':
            assert text is None
        else:
            assert text
            assert len(text.strip()) > 0


def test_catalog_matches_expected_keys():
    assert set(C2C_REJECT_REASONS.keys()) == {
        'amt_mismatch',
        'unclear',
        'wrong_card',
        'duplicate',
        'expired',
        'silent',
    }
