from __future__ import annotations

import hashlib


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]


def assert_not_production_token(
    bot_token: str,
    prod_fingerprint: str | None,
    allow_override: bool,
) -> None:
    if not prod_fingerprint:
        return
    if allow_override:
        return
    if token_fingerprint(bot_token) == prod_fingerprint:
        raise RuntimeError(
            'Refusing to start: production BOT_TOKEN matches PRODUCTION_BOT_TOKEN_FINGERPRINT'
        )
