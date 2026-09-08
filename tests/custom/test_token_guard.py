import hashlib

import pytest

from app.custom.safety.token_guard import (
    assert_not_production_token,
    token_fingerprint,
)


def test_token_fingerprint_is_first_16_hex_of_sha256() -> None:
    token = 'test-token'
    expected = hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]
    assert token_fingerprint(token) == expected


def test_assert_refuses_matching_fingerprint() -> None:
    token = 'prod-like'
    fp = token_fingerprint(token)
    with pytest.raises(RuntimeError, match='production BOT_TOKEN'):
        assert_not_production_token(token, fp, allow_override=False)


def test_assert_allows_override() -> None:
    token = 'prod-like'
    fp = token_fingerprint(token)
    assert_not_production_token(token, fp, allow_override=True)


def test_assert_passes_distinct_token() -> None:
    fp = token_fingerprint('production')
    assert_not_production_token('rehearsal', fp, allow_override=False)


def test_assert_passes_when_fingerprint_unset() -> None:
    assert_not_production_token('anything', None, allow_override=False)
    assert_not_production_token('anything', '', allow_override=False)
