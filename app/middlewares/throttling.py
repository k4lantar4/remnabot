import asyncio
import logging
import time
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.fsm.context import FSMContext

from app.localization.texts import get_texts
from app.localization.loader import DEFAULT_LANGUAGE

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    
    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit
        self.user_buckets: Dict[int, float] = {}
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        user_id = None
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
        
        if not user_id:
            return await handler(event, data)
        
        now = time.time()
        last_call = self.user_buckets.get(user_id, 0)
        
        if now - last_call < self.rate_limit:
            logger.warning(f"🚫 Throttling for user {user_id}")

            # For messages: silently ignore only if in ticket states; otherwise show block
            if isinstance(event, Message):
                try:
                    fsm: FSMContext = data.get("state")  # may be absent
                    current = await fsm.get_state() if fsm else None
                except Exception:
                    current = None
                is_ticket_state = False
                if current:
                    # Silently ignore only in ticket states (user/admin): waiting_for_message / waiting_for_reply
                    lowered = str(current)
                    is_ticket_state = (
                        (":waiting_for_message" in lowered or ":waiting_for_reply" in lowered) and
                        ("TicketStates" in lowered or "AdminTicketStates" in lowered)
                    )
                if is_ticket_state:
                    return
                # In other cases — explicit block
                user = event.from_user
                language = DEFAULT_LANGUAGE
                if user and user.language_code:
                    language = user.language_code.split('-')[0]
                texts = get_texts(language)
                message = texts.get(
                    "THROTTLING_MESSAGE",
                    "⏳ Please don't send messages so frequently!"
                )
                await event.answer(message)
                return
            # For callbacks, allow brief notification
            elif isinstance(event, CallbackQuery):
                user = event.from_user
                language = DEFAULT_LANGUAGE
                if user and user.language_code:
                    language = user.language_code.split('-')[0]
                texts = get_texts(language)
                message = texts.get(
                    "THROTTLING_CALLBACK",
                    "⏳ Too fast! Please wait a moment."
                )
                await event.answer(message, show_alert=True)
                return
        
        self.user_buckets[user_id] = now
        
        cleanup_threshold = now - 60
        self.user_buckets = {
            uid: timestamp 
            for uid, timestamp in self.user_buckets.items() 
            if timestamp > cleanup_threshold
        }
        
        return await handler(event, data)