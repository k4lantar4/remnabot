"""The device line is dropped by its placeholder, not by its Russian text (F-037).

purchase.py removed «\\n📱 Устройства: {devices_used} / …» with a literal replace, which never
matched the fa template, so fa users saw an empty «دستگاه‌ها:  / 2» line.
"""

import pytest

from app.localization.texts import get_texts
from app.utils.template_lines import strip_template_line


def test_removes_middle_line():
    assert strip_template_line('a\nb {x}\nc', '{x}') == 'a\nc'


def test_removes_last_line():
    assert strip_template_line('a\nb {x} / {y}', '{x}') == 'a'


def test_removes_every_matching_line():
    assert strip_template_line('{x}\na\n{x} again\nb', '{x}') == 'a\nb'


def test_no_placeholder_leaves_template_unchanged():
    template = 'a\nb\n'
    assert strip_template_line(template, '{x}') == template


@pytest.mark.parametrize(
    'key',
    ['SUBSCRIPTION_OVERVIEW_TEMPLATE', 'SUBSCRIPTION_DAILY_OVERVIEW_TEMPLATE', 'SUBSCRIPTION_SETTINGS_OVERVIEW'],
)
@pytest.mark.parametrize('language', ['fa', 'ru', 'en'])
def test_real_templates_lose_the_device_line(language, key):
    template = get_texts(language).t(key)
    assert '{devices_used}' in template

    stripped = strip_template_line(template, '{devices_used}')

    assert '{devices_used}' not in stripped
    assert '{device_limit}' not in stripped
    assert '{devices_limit}' not in stripped
    if language == 'fa':
        assert 'دستگاه' not in stripped
    # the rest of the template keeps its placeholders and still formats
    assert stripped.count('\n') == template.count('\n') - 1
