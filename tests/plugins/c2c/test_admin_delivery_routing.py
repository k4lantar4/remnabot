"""C2C admin chat and forum topic routing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramBadRequest

from app.config import Settings
from app.services.admin_notification_service import (
    AdminNotificationService,
    NotificationCategory,
    _admin_topic_fallback_chain,
    send_with_admin_topic_fallback,
)


def _settings(**overrides: object) -> Settings:
    base = {
        'ADMIN_NOTIFICATIONS_CHAT_ID': '-1001111111111',
        'ADMIN_NOTIFICATIONS_TOPIC_ID': 1,
        'ADMIN_NOTIFICATIONS_BALANCE_TOPIC_ID': 42,
        'C2C_ADMIN_CHAT_ID': '',
    }
    base.update(overrides)
    return Settings(**base)


def test_get_c2c_admin_chat_id_rejects_positive_user_id():
    cfg = _settings(C2C_ADMIN_CHAT_ID='1713374557')
    assert cfg.get_c2c_admin_chat_id() == -1001111111111


def test_get_c2c_admin_chat_id_uses_explicit_supergroup():
    cfg = _settings(C2C_ADMIN_CHAT_ID='-1002222222222')
    assert cfg.get_c2c_admin_chat_id() == -1002222222222


def test_admin_forum_topics_apply_only_to_notifications_chat():
    cfg = _settings()
    assert cfg.admin_forum_topics_apply_to_chat(-1001111111111) is True
    assert cfg.admin_forum_topics_apply_to_chat(-1002222222222) is False


def test_build_delivery_kwargs_skips_topic_for_foreign_chat(monkeypatch: pytest.MonkeyPatch):
    cfg = _settings(C2C_ADMIN_CHAT_ID='-1002222222222')
    monkeypatch.setattr('app.services.admin_notification_service.settings', cfg)
    service = AdminNotificationService(MagicMock())
    kwargs = service.build_delivery_kwargs(
        chat_id=-1002222222222,
        category=NotificationCategory.BALANCE,
    )
    assert kwargs == {'chat_id': -1002222222222}


def test_build_delivery_kwargs_includes_balance_topic_for_notifications_chat(
    monkeypatch: pytest.MonkeyPatch,
):
    cfg = _settings()
    monkeypatch.setattr('app.services.admin_notification_service.settings', cfg)
    service = AdminNotificationService(MagicMock())
    kwargs = service.build_delivery_kwargs(
        chat_id=-1001111111111,
        category=NotificationCategory.BALANCE,
    )
    assert kwargs == {'chat_id': -1001111111111, 'message_thread_id': 42}


def test_admin_topic_fallback_chain_order():
    kwargs = {'chat_id': -1001, 'message_thread_id': 42}
    chain = _admin_topic_fallback_chain(kwargs)
    assert chain[0]['message_thread_id'] == 42
    assert chain[1]['message_thread_id'] == 1
    assert 'message_thread_id' not in chain[2]


@pytest.mark.asyncio
async def test_send_with_admin_topic_fallback_retries_without_thread():
    calls: list[dict] = []

    async def factory(kw: dict) -> str:
        calls.append(dict(kw))
        if kw.get('message_thread_id') is not None:
            raise TelegramBadRequest(method='sendMessage', message='Bad Request: message thread not found')
        return 'ok'

    result = await send_with_admin_topic_fallback(
        factory,
        {'chat_id': -1001, 'message_thread_id': 99},
    )
    assert result == 'ok'
    assert calls[-1].get('message_thread_id') is None
