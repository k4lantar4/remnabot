from __future__ import annotations

import re

MAX_PURCHASE_NOTE_LEN = 500
BRAND_PREFIX_PATTERN = re.compile(r'^[A-Za-z0-9_-]{3,20}$')


def validate_brand_prefix(raw: str | None) -> str | None:
    value = (raw or '').strip()
    if not BRAND_PREFIX_PATTERN.fullmatch(value):
        return None
    return value
