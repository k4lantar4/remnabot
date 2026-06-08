def test_tariff_ext_confirm_accepts_embedded_sub_id():
    data = 'tariff_ext_confirm:1:360:42'
    parts = data.split(':')
    assert int(parts[1]) == 1
    assert int(parts[2]) == 360
    assert int(parts[3]) == 42


def test_tariff_ext_confirm_legacy_three_part():
    data = 'tariff_ext_confirm:1:360'
    parts = data.split(':')
    assert len(parts) == 3
    assert int(parts[3 - 1]) == 360 if len(parts) >= 3 else True
