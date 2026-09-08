from datetime import UTC, datetime
from types import SimpleNamespace

from app.utils.subscription_list_display import (
    filter_subscriptions_by_query,
    format_subscription_list_line,
    subscription_list_identity,
)


class DummyTexts:
    language = 'fa'

    def t(self, key, default=None):
        return {
            'MY_SUB_ACCOUNT_LABEL': '{tariff} #{seq}',
            'MY_SUB_DEFAULT_NAME': 'اشتراک',
            'MY_SUB_TRAFFIC_LINE': '   📊 ترافیک: {traffic}',
            'MY_SUB_DEVICES_LINE': '   👥 تعداد کاربر: {devices}',
            'MY_SUB_DEVICES_COUNT_SHORT': '{count} کاربر',
            'MY_SUB_UNTIL_LINE': '   📅 تا: {end_date}',
            'MY_SUB_STATUS_EXPIRED': ' (منقضی)',
            'MY_SUB_STATUS_DISABLED': ' (غیرفعال)',
            'MY_SUB_STATUS_LIMITED': ' (اتمام حجم)',
            'MY_SUB_STATUS_USER_DISABLED': ' (متوقف)',
        }.get(key, default or key)


def _sub(**kwargs):
    base = dict(
        id=1,
        tariff=SimpleNamespace(name='تانل شده (همه نت ها)'),
        actual_status='active',
        traffic_limit_gb=50,
        traffic_used_gb=31.6,
        device_limit=5,
        end_date=datetime(2026, 7, 9, tzinfo=UTC),
        remnawave_short_id='67258',
        purchase_note=None,
        panel_username=None,
        account_sequence=1,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_identity_uses_panel_username() -> None:
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='Moonvpn')
    sub = _sub(panel_username='mobile_x_1001', account_sequence=2)
    assert subscription_list_identity(sub, user, DummyTexts()) == 'mobile_x_1001'


def test_identity_strips_user_unknown() -> None:
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)
    sub = _sub(panel_username='user_unknown_abc', account_sequence=3)
    assert subscription_list_identity(sub, user, DummyTexts()) == 'تانل شده (همه نت ها) #3'


def test_identity_falls_back_to_tariff_seq() -> None:
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='Moonvpn')
    sub = _sub(panel_username=None, account_sequence=4)
    assert subscription_list_identity(sub, user, DummyTexts()) == 'تانل شده (همه نت ها) #4'


def test_identity_never_brand_serial() -> None:
    user = SimpleNamespace(is_partner=True, panel_brand_prefix='Moonvpn')
    sub = _sub(panel_username=None, remnawave_short_id='67258', account_sequence=1)
    assert 'Moonvpn_67258' not in subscription_list_identity(sub, user, DummyTexts())


def test_line_is_jalali_fa_and_not_cyrillic() -> None:
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)
    line = format_subscription_list_line(
        _sub(panel_username='mobile_x_1001', account_sequence=1),
        1,
        DummyTexts(),
        'fa',
        user,
    )
    assert '18.04.1405' in line
    assert 'کاربر' in line
    assert 'Moonvpn_67258' not in line
    assert 'mobile_x_1001' in line


def test_search_matches_username_and_id() -> None:
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)
    subs = [
        _sub(id=1, panel_username='mobile_x_1001', account_sequence=1),
        _sub(id=2, panel_username='mobile_x_1002', remnawave_short_id='1159', tariff=SimpleNamespace(name='دیگر'), account_sequence=2),
    ]
    hit = filter_subscriptions_by_query(subs, 'mobile_x_1001', DummyTexts(), user)
    assert [s.id for s in hit] == [1]
    hit_id = filter_subscriptions_by_query(subs, '2', DummyTexts(), user)
    assert [s.id for s in hit_id] == [2]


def test_line_marks_user_disabled_pause() -> None:
    user = SimpleNamespace(is_partner=False, panel_brand_prefix=None)
    line = format_subscription_list_line(
        _sub(actual_status='disabled', user_disabled=True),
        1,
        DummyTexts(),
        'fa',
        user,
    )
    assert '⏸' in line
    assert 'متوقف' in line
