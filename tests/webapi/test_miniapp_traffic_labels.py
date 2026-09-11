"""Miniapp traffic labels follow the user's language (F-040).

_format_traffic_limit_label hard-coded «ГБ» / «♾️ Безлимит» and _format_limit_label hard-coded
English, whatever the user's language.
"""

import pytest

from app.webapi.routes.miniapp import _format_limit_label, _format_traffic_limit_label


@pytest.mark.parametrize(
    ('traffic_gb', 'language', 'expected'),
    [
        (50, 'fa', '50 گیگ'),
        (0, 'fa', '♾️ نامحدود'),
        (50, 'ru', '50 ГБ'),
        (0, 'ru', '♾️ Безлимит'),
        (50, 'en', '50 GB'),
    ],
)
def test_tariff_traffic_label(traffic_gb, language, expected):
    assert _format_traffic_limit_label(traffic_gb, language) == expected


@pytest.mark.parametrize(
    ('limit', 'language', 'expected'),
    [
        (50, 'fa', '50 گیگ'),
        (0, 'fa', 'نامحدود'),
        (None, 'fa', 'نامحدود'),
        (50, 'en', '50 GB'),
        (None, 'en', 'Unlimited'),
        (50, 'ru', '50 ГБ'),
    ],
)
def test_subscription_traffic_limit_label(limit, language, expected):
    assert _format_limit_label(limit, language) == expected
