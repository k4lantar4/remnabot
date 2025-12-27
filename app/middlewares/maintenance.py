import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject, User as TgUser

from app.config import settings
from app.services.maintenance_service import maintenance_service
from app.localization.texts import get_texts

logger = logging.getLogger(__name__)


class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user: TgUser = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user

        if not user or user.is_bot:
            return await handler(event, data)

        if not maintenance_service.is_maintenance_active():
            return await handler(event, data)

        if settings.is_admin(user.id):
            return await handler(event, data)

        # Try to get user language from data, fallback to user's language_code or "en"
        user_language = "en"
        if "db_user" in data and data["db_user"]:
            user_language = data["db_user"].language or "en"
        elif user.language_code:
            user_language = user.language_code.split("-")[0] if user.language_code else "en"

        maintenance_message = maintenance_service.get_maintenance_message(language=user_language)

        try:
            if isinstance(event, Message):
                await event.answer(maintenance_message, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.answer(maintenance_message, show_alert=True)
        except Exception as e:
            logger.error(f"Error sending maintenance message to user {user.id}: {e}")

        logger.info(f"🔧 User {user.id} blocked during maintenance")
        return
