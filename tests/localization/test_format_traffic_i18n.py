"""Traffic amounts are printed in the user's language (F-036).

Texts.format_traffic used to hard-code «ГБ / ТБ / безлимит», so a fa user saw Russian units on
every traffic line. ru output must stay exactly what it was.
"""

import pytest

from app.localization.texts import get_texts


@pytest.mark.parametrize(
    ('language', 'gb', 'is_limit', 'expected'),
    [
        ('fa', 50, True, '50 گیگ'),
        ('fa', 2048, True, '2.0 ترابایت'),
        ('fa', 0, True, '∞ (نامحدود)'),
        ('fa', 0, False, '0 گیگ'),
        ('ru', 50, True, '50 ГБ'),
        ('ru', 2048, True, '2.0 ТБ'),
        ('ru', 0, True, '∞ (безлимит)'),
        ('ru', 0, False, '0 ГБ'),
        ('en', 50, True, '50 GB'),
        ('en', 1536, True, '1.5 TB'),
        ('en', 0, True, '∞ (unlimited)'),
    ],
)
def test_format_traffic_uses_locale_units(language, gb, is_limit, expected):
    assert get_texts(language).format_traffic(gb, is_limit=is_limit) == expected


def test_fa_traffic_has_no_cyrillic():
    texts = get_texts('fa')
    for gb, is_limit in [(0, True), (0, False), (10, True), (5000, True)]:
        rendered = texts.format_traffic(gb, is_limit=is_limit)
        assert not any('Ѐ' <= ch <= 'ӿ' for ch in rendered), rendered
