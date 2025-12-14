import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.database.database import get_db
from app.database.crud.bot import get_bot_by_token

logger = logging.getLogger(__name__)


class BotContextMiddleware(BaseMiddleware):
    """
    Middleware to inject bot context (bot_id, bot instance) into handlers.
    Detects bot from Telegram event and adds bot context to handler data.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Get bot instance from event
        bot = getattr(event, 'bot', None)
        
        if not bot:
            logger.warning("Bot instance not found in event")
            return await handler(event, data)
        
        # Get bot token
        bot_token = getattr(bot, 'token', None)
        if not bot_token:
            logger.warning("Bot token not found in bot instance")
            return await handler(event, data)
        
        # Get bot from database
        async for db in get_db():
            try:
                bot_config = await get_bot_by_token(db, bot_token)
                
                if not bot_config:
                    logger.error(f"Bot not found in database for token: {bot_token[:10]}...")
                    # Continue without bot context - might be during migration
                    break
                
                if not bot_config.is_active:
                    logger.warning(f"Bot {bot_config.id} ({bot_config.name}) is inactive")
                    # Continue but log warning
                
                # Inject bot context
                data['bot_id'] = bot_config.id
                data['bot_config'] = bot_config
                
                logger.debug(f"✅ Bot context injected: bot_id={bot_config.id}, name={bot_config.name}")
                break
                
            except Exception as e:
                logger.error(f"Error in BotContextMiddleware: {e}", exc_info=True)
                # Continue without bot context on error
                break
        
        return await handler(event, data)
