from types import SimpleNamespace

from app.custom.identity.panel_username import cache_panel_username
from app.custom.identity.persist import persist_identity


def test_cache_writes_trimmed_username() -> None:
    sub = SimpleNamespace(panel_username=None)
    cache_panel_username(sub, SimpleNamespace(username='  mobile_x_1001  '))
    assert sub.panel_username == 'mobile_x_1001'


def test_cache_skips_empty() -> None:
    sub = SimpleNamespace(panel_username='keep')
    cache_panel_username(sub, SimpleNamespace(username='  '))
    assert sub.panel_username == 'keep'


def test_persist_identity_does_not_write_username() -> None:
    sub = SimpleNamespace(remnawave_id=None, panel_username=None)
    persist_identity(subscription=sub, panel_user=SimpleNamespace(id=99, username='x'))
    assert sub.remnawave_id == 99
    assert sub.panel_username is None
