from app.handlers.subscription.tariff_purchase import (
    _parse_tariff_ext_confirm_callback,
    _parse_tariff_extend_callback,
    get_tariff_extend_confirm_keyboard,
)


def test_parse_tariff_extend_legacy_period_only():
    assert _parse_tariff_extend_callback('tariff_extend:1:360') == (1, 360, None)


def test_parse_tariff_extend_with_sub_id():
    assert _parse_tariff_extend_callback('tariff_extend:1:360:42') == (1, 360, 42)


def test_parse_tariff_extend_back_to_period_picker():
    assert _parse_tariff_extend_callback('tariff_extend:1') == (1, None, None)


def test_parse_tariff_ext_confirm_with_sub_id():
    assert _parse_tariff_ext_confirm_callback('tariff_ext_confirm:1:360:42') == (1, 360, 42)


def test_parse_tariff_ext_confirm_legacy():
    assert _parse_tariff_ext_confirm_callback('tariff_ext_confirm:1:360') == (1, 360, None)


def test_confirm_keyboard_embeds_sub_id():
    kb = get_tariff_extend_confirm_keyboard(1, 360, 'fa', subscription_id=42)
    confirm_btn = kb.inline_keyboard[0][0]
    back_btn = kb.inline_keyboard[1][0]
    assert confirm_btn.callback_data == 'tariff_ext_confirm:1:360:42'
    assert back_btn.callback_data == 'se:42'
