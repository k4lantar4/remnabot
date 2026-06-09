"""No bare Russian restriction reason outside texts.t() fallback argument."""

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / 'app'
BARE = re.compile(
    r"getattr\(db_user,\s*'restriction_reason',\s*None\)\s*or\s*'Действие ограничено администратором'"
)
# texts.t(..., 'Действие...') as second arg is OK
ALLOWED = re.compile(r"texts\.t\(\s*'USER_RESTRICTION_DEFAULT_REASON'")


def test_no_bare_restriction_reason_hardcode():
    offenders = []
    for path in APP.rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        if BARE.search(text) and not ALLOWED.search(text):
            # allow if every match is inside texts.t fallback — simplify: flag file
            for i, line in enumerate(text.splitlines(), 1):
                if BARE.search(line) and 'texts.t(' not in line:
                    offenders.append(f'{path.relative_to(APP.parent)}:{i}')
    assert not offenders, 'Bare restriction hardcode:\n' + '\n'.join(offenders)
