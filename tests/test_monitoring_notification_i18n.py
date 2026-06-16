"""Scheduled user notifications must not use bare Cyrillic message bodies."""

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'app'
TARGETS = [
    APP / 'services' / 'monitoring_service.py',
    APP / 'services' / 'daily_subscription_service.py',
]
# f-string message bodies with Cyrillic — not texts.t fallbacks
BARE_MSG = re.compile(
    r"message\s*=\s*f['\"]{3}.*[А-Яа-яЁё]",
    re.DOTALL,
)
BARE_F = re.compile(
    r"message\s*=\s*\(\s*f['\"].*[А-Яа-яЁё]",
)


def test_no_bare_cyrillic_notification_bodies():
    offenders = []
    for path in TARGETS:
        text = path.read_text(encoding='utf-8')
        for i, line in enumerate(text.splitlines(), 1):
            if 'texts.t(' in line:
                continue
            if BARE_F.search(line) or (
                'message = f"""' in line or "message = f'''" in line
            ):
                # flag only if block contains Cyrillic — scan next 15 lines
                block = '\n'.join(text.splitlines()[i - 1 : i + 14])
                if '[А-Яа-яЁё]' and __import__('re').search(r'[А-Яа-яЁё]', block):
                    if 'texts.t(' not in block:
                        offenders.append(f'{path.relative_to(APP.parent)}:{i}')
    assert not offenders, 'Bare Cyrillic notification bodies:\n' + '\n'.join(offenders)
