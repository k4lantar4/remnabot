from tools.migration.config import OLD_SERVER_TO_SQUAD_KEY, squad_key_for_server, vip_to_tariff_id


def test_small_servers_map_to_merged_key():
    for server_id in (11, 17, 40, 46):
        assert squad_key_for_server(server_id) == 'merged-small'


def test_vip_to_tariff_mapping():
    assert vip_to_tariff_id(1) == 3
    assert vip_to_tariff_id(20) == 2


def test_skip_servers_not_mapped():
    assert 37 in OLD_SERVER_TO_SQUAD_KEY
    assert 56 not in OLD_SERVER_TO_SQUAD_KEY
