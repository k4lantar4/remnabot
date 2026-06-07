from app.handlers.subscription.common import _SUB_ID_CALLBACK_PREFIXES


def test_resolve_does_not_treat_tariff_ext_confirm_period_as_sub_id():
    prefixes_skip_last_int = ('tariff_ext_confirm', 'tariff_confirm', 'tariff_extend', 'tariff_select')
    data = 'tariff_ext_confirm:1:30'
    prefix = data.split(':')[0]
    assert prefix in prefixes_skip_last_int
    assert prefix not in _SUB_ID_CALLBACK_PREFIXES


def test_subscription_scoped_prefixes_include_se_and_st():
    assert 'se' in _SUB_ID_CALLBACK_PREFIXES
    assert 'st' in _SUB_ID_CALLBACK_PREFIXES
    assert 'sm' in _SUB_ID_CALLBACK_PREFIXES
