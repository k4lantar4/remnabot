"""C2C admin supergroup delivery helpers (forum topic fallback)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from aiogram.exceptions import TelegramBadRequest

from app.config import settings


if TYPE_CHECKING:
    from app.services.admin_notification_service import AdminNotificationService, NotificationCategory


logger = structlog.get_logger(__name__)


def _redact_telegram_secrets(text: str) -> str:
    from app.services.admin_notification_service import _redact_telegram_secrets as redact

    return redact(text)


def is_message_thread_not_found(error: Exception) -> bool:
    """True when Telegram rejects message_thread_id (deleted/invalid forum topic)."""
    if not isinstance(error, TelegramBadRequest):
        return False
    return 'message thread not found' in str(error).lower()


def without_message_thread_id(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Copy delivery kwargs without message_thread_id (fallback to main group chat)."""
    return {key: value for key, value in kwargs.items() if key != 'message_thread_id'}


def _admin_topic_fallback_chain(kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    """Delivery attempts: category topic → general topic → main chat (no thread)."""
    chain: list[dict[str, Any]] = [kwargs]
    thread_id = kwargs.get('message_thread_id')
    default_topic = settings.ADMIN_NOTIFICATIONS_TOPIC_ID
    if thread_id is not None and default_topic is not None and int(default_topic) != int(thread_id):
        chain.append({**kwargs, 'message_thread_id': int(default_topic)})
    chain.append(without_message_thread_id(kwargs))

    seen: set[tuple[int | None, int | None]] = set()
    unique: list[dict[str, Any]] = []
    for item in chain:
        key = (item.get('chat_id'), item.get('message_thread_id'))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


async def send_with_admin_topic_fallback(coro_factory, kwargs: dict[str, Any]) -> Any:
    """Call coro_factory(kwargs); on missing forum topic, retry alternate topics then main chat."""
    last_error: TelegramBadRequest | None = None
    for attempt_kwargs in _admin_topic_fallback_chain(kwargs):
        try:
            return await coro_factory(attempt_kwargs)
        except TelegramBadRequest as error:
            if attempt_kwargs.get('message_thread_id') is None or not is_message_thread_not_found(error):
                raise
            last_error = error
            logger.warning(
                'Admin forum topic not found, trying next delivery target',
                chat_id=attempt_kwargs.get('chat_id'),
                message_thread_id=attempt_kwargs.get('message_thread_id'),
                error=_redact_telegram_secrets(str(error))[:200],
            )
    if last_error is not None:
        raise last_error
    raise RuntimeError('send_with_admin_topic_fallback: empty attempt chain')


def build_delivery_kwargs(
    notification_service: AdminNotificationService,
    *,
    chat_id: int,
    category: NotificationCategory | None = None,
) -> dict[str, Any]:
    """Build chat_id and optional message_thread_id for a specific admin supergroup."""
    kwargs: dict[str, Any] = {'chat_id': chat_id}
    if not settings.admin_forum_topics_apply_to_chat(chat_id):
        return kwargs
    thread_id = notification_service._resolve_topic_id(category)
    if thread_id is not None:
        kwargs['message_thread_id'] = int(thread_id)
    return kwargs
