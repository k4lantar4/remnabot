import pytest

from app.config import settings
from app.localization import user_language


@pytest.fixture(autouse=True)
def reset_language_settings(monkeypatch):
    monkeypatch.setattr(settings, 'LANGUAGE_SELECTION_ENABLED', True, raising=False)
    monkeypatch.setattr(settings, 'DEFAULT_LANGUAGE', 'fa', raising=False)


def test_resolve_user_facing_language_honors_stored_when_selection_enabled(monkeypatch):
    monkeypatch.setattr(settings, 'LANGUAGE_SELECTION_ENABLED', True, raising=False)
    assert user_language.resolve_user_facing_language('en') == 'en'
    assert user_language.resolve_user_facing_language('en-US') == 'en'


def test_resolve_user_facing_language_forces_default_when_selection_disabled(monkeypatch):
    monkeypatch.setattr(settings, 'LANGUAGE_SELECTION_ENABLED', False, raising=False)
    monkeypatch.setattr(settings, 'DEFAULT_LANGUAGE', 'fa', raising=False)

    assert user_language.resolve_user_facing_language('en') == 'fa'
    assert user_language.resolve_user_facing_language('ru') == 'fa'


def test_apply_forced_user_language_updates_user_row(monkeypatch):
    monkeypatch.setattr(settings, 'LANGUAGE_SELECTION_ENABLED', False, raising=False)
    monkeypatch.setattr(settings, 'DEFAULT_LANGUAGE', 'fa', raising=False)

    class FakeUser:
        language = 'en'

    user = FakeUser()
    changed = user_language.apply_forced_user_language(user)

    assert changed is True
    assert user.language == 'fa'


def test_apply_forced_user_language_noop_when_selection_enabled(monkeypatch):
    monkeypatch.setattr(settings, 'LANGUAGE_SELECTION_ENABLED', True, raising=False)

    class FakeUser:
        language = 'en'

    user = FakeUser()
    changed = user_language.apply_forced_user_language(user)

    assert changed is False
    assert user.language == 'en'
