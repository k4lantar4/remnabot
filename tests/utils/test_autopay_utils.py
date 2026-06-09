from types import SimpleNamespace

from app.utils.autopay_utils import effective_autopay_enabled


def test_effective_autopay_false_when_global_off(monkeypatch):
    monkeypatch.setattr('app.utils.autopay_utils.settings.ENABLE_AUTOPAY', False)
    sub = SimpleNamespace(autopay_enabled=True)
    assert effective_autopay_enabled(sub) is False


def test_effective_autopay_true_when_both_on(monkeypatch):
    monkeypatch.setattr('app.utils.autopay_utils.settings.ENABLE_AUTOPAY', True)
    sub = SimpleNamespace(autopay_enabled=True)
    assert effective_autopay_enabled(sub) is True


def test_effective_autopay_false_when_sub_off(monkeypatch):
    monkeypatch.setattr('app.utils.autopay_utils.settings.ENABLE_AUTOPAY', True)
    sub = SimpleNamespace(autopay_enabled=False)
    assert effective_autopay_enabled(sub) is False
