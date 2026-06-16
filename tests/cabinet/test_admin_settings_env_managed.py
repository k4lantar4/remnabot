from __future__ import annotations

from unittest.mock import patch

from app.cabinet.routes import admin_settings
from app.services.system_settings_service import bot_configuration_service


def test_serialize_definition_marks_env_managed(monkeypatch) -> None:
    bot_configuration_service.initialize_definitions()
    definition = bot_configuration_service.get_definition('DEFAULT_DEVICE_LIMIT')

    env_keys = set(bot_configuration_service._env_override_keys)
    env_keys.add('DEFAULT_DEVICE_LIMIT')
    monkeypatch.setattr(bot_configuration_service, '_env_override_keys', env_keys)

    with (
        patch.object(
            bot_configuration_service,
            'get_current_value',
            return_value=0,
        ),
        patch.object(
            bot_configuration_service,
            'get_original_value',
            return_value=1,
        ),
        patch.object(
            bot_configuration_service,
            'has_override',
            return_value=False,
        ),
        patch.object(
            bot_configuration_service,
            'get_choice_options',
            return_value=[],
        ),
        patch.object(
            bot_configuration_service,
            'get_setting_guidance',
            return_value={},
        ),
    ):
        serialized = admin_settings._serialize_definition(definition)

    assert serialized.managed_by_env is True
    assert serialized.read_only is True
    assert serialized.key == 'DEFAULT_DEVICE_LIMIT'


def test_serialize_definition_env_managed_false_when_not_in_env(monkeypatch) -> None:
    bot_configuration_service.initialize_definitions()
    definition = bot_configuration_service.get_definition('SUPPORT_MENU_ENABLED')
    monkeypatch.setattr(bot_configuration_service, '_env_override_keys', set())

    with (
        patch.object(
            bot_configuration_service,
            'get_current_value',
            return_value=True,
        ),
        patch.object(
            bot_configuration_service,
            'get_original_value',
            return_value=True,
        ),
        patch.object(
            bot_configuration_service,
            'has_override',
            return_value=False,
        ),
        patch.object(
            bot_configuration_service,
            'get_choice_options',
            return_value=[],
        ),
        patch.object(
            bot_configuration_service,
            'get_setting_guidance',
            return_value={},
        ),
    ):
        serialized = admin_settings._serialize_definition(definition)

    assert serialized.managed_by_env is False
    assert serialized.read_only is False
