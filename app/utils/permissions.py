"""
Permission utilities for master admin and tenant admin checks.
"""
import logging
from functools import wraps
from typing import Callable, Any
from aiogram import types
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.crud.bot import get_master_bot
from app.services.bot_config_service import BotConfigService
from app.localization.texts import get_texts

logger = logging.getLogger(__name__)


async def is_master_admin(
    user: User,
    db: AsyncSession
) -> bool:
    """
    Check if user is master admin.
    
    Master admin is determined by checking if the user's telegram_id
    is in the master bot's ADMIN_IDS configuration.
    
    Checks both database (bot_configurations) and .env as fallback.
    
    Args:
        user: User object
        db: Database session
    
    Returns:
        True if user is master admin, False otherwise
    """
    try:
        master_bot = await get_master_bot(db)
        if not master_bot:
            logger.warning("Master bot not found in database")
            return False
        
        # Try to get ADMIN_IDS from database first
        admin_ids_str = await BotConfigService.get_config(
            db, master_bot.id, 'ADMIN_IDS', default=''
        )
        
        # If not found in database, fallback to .env
        if not admin_ids_str:
            from app.config import settings
            admin_ids_str = settings.ADMIN_IDS
            logger.debug(f"ADMIN_IDS not found in database, using .env: {admin_ids_str}")
        
        if not admin_ids_str:
            logger.warning(f"ADMIN_IDS not configured in database or .env for master bot {master_bot.id}")
            return False
        
        # Parse comma-separated admin IDs
        admin_ids = [
            int(id.strip()) 
            for id in str(admin_ids_str).split(',') 
            if id.strip() and id.strip().isdigit()
        ]
        
        is_admin = user.telegram_id in admin_ids
        if not is_admin:
            logger.debug(
                f"User {user.telegram_id} not in admin list. "
                f"ADMIN_IDS: {admin_ids_str}, Parsed IDs: {admin_ids}"
            )
        
        return is_admin
    except Exception as e:
        logger.error(f"Error checking master admin status: {e}", exc_info=True)
        return False


def admin_required(func: Callable) -> Callable:
    """
    Decorator to require master admin access.
    
    This decorator checks if the user is a master admin before allowing
    access to the handler function. If not a master admin, sends an error
    message and returns early.
    
    Usage:
        @admin_required
        async def handler(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
            ...
    """
    @wraps(func)
    async def wrapper(
        event: types.Update,
        *args,
        **kwargs
    ) -> Any:
        # Extract user and db from args/kwargs
        # Priority: db_user from kwargs (injected by middleware) > User from args > event.from_user
        user = None
        db = None
        
        # First, try to get db_user from kwargs (this is how middleware injects it)
        if 'db_user' in kwargs:
            user = kwargs['db_user']
        
        # If not found, try to get User from args (common pattern in handlers)
        if not user:
            for arg in args:
                if isinstance(arg, User):
                    user = arg
                    break
        
        # Last resort: try to get user from event (aiogram User, not our database User)
        # This should rarely happen if middleware is working correctly
        if not user and isinstance(event, (types.Message, types.CallbackQuery)):
            user = event.from_user
        
        # Try to get db from args or kwargs
        for arg in args:
            if isinstance(arg, AsyncSession):
                db = arg
                break
        
        if not db and 'db' in kwargs:
            db = kwargs['db']
        
        if not db and 'db_session' in kwargs:
            db = kwargs['db_session']
        
        if not user or not db:
            logger.warning(f"Could not extract user or db from {func.__name__}")
            texts = get_texts()
            try:
                if isinstance(event, types.Message):
                    await event.answer(texts.t("ADMIN_ACCESS_DENIED", "❌ Access denied"))
                    logger.warning(f"Access denied to {func.__name__} for user {user.telegram_id}")
                elif isinstance(event, types.CallbackQuery):
                    await event.answer(
                        texts.t("ADMIN_ACCESS_DENIED", "❌ Access denied"),
                        show_alert=True
                    )
            except TelegramBadRequest:
                pass
            return
        
        # Check if user is master admin
        # Only check if user is our database User model, not aiogram User
        is_admin = False
        if isinstance(user, User):
            is_admin = await is_master_admin(user, db)
        else:
            # If we have aiogram User instead of database User, we can't check admin status
            # This shouldn't happen if middleware is working correctly
            logger.warning(f"User object is not database User model in {func.__name__}")
            texts = get_texts('en')
            try:
                if isinstance(event, types.Message):
                    await event.answer(
                        texts.t("ADMIN_ACCESS_DENIED", "❌ Access denied")
                    )
                elif isinstance(event, types.CallbackQuery):
                    await event.answer(
                        texts.t("ADMIN_ACCESS_DENIED", "❌ Access denied"),
                        show_alert=True
                    )
            except TelegramBadRequest:
                pass
            return
        
        if not is_admin:
            texts = get_texts(user.language if hasattr(user, 'language') else 'en')
            try:
                if isinstance(event, types.Message):
                    await event.answer(
                        texts.t("ADMIN_admin_required", "❌ Master admin access required")
                    )
                elif isinstance(event, types.CallbackQuery):
                    await event.answer(
                        texts.t("ADMIN_admin_required", "❌ Master admin access required"),
                        show_alert=True
                    )
            except TelegramBadRequest as e:
                if "query is too old" in str(e).lower():
                    # Get telegram_id safely
                    telegram_id = user.telegram_id if isinstance(user, User) else getattr(user, 'id', 'unknown')
                    logger.warning(f"Attempt to answer outdated callback query from {telegram_id}")
                else:
                    raise
            
            # Get telegram_id safely for logging
            telegram_id = user.telegram_id if isinstance(user, User) else getattr(user, 'id', 'unknown')
            logger.warning(f"Non-master admin attempt to access {func.__name__} from {telegram_id}")
            return
        
        # User is master admin, proceed with function
        return await func(event, *args, **kwargs)
    
    return wrapper

