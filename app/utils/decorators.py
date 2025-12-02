import logging
import functools
from typing import Callable, Any
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from app.config import settings
from app.localization.texts import get_texts

logger = logging.getLogger(__name__)


def admin_required(func: Callable) -> Callable:
    
    @functools.wraps(func)
    async def wrapper(
        event: types.Update,
        *args,
        **kwargs
    ) -> Any:
        user = None
        if isinstance(event, (types.Message, types.CallbackQuery)):
            user = event.from_user
        
        if not user or not settings.is_admin(user.id):
            texts = get_texts()
            
            try:
                if isinstance(event, types.Message):
                    await event.answer(texts.ACCESS_DENIED)
                elif isinstance(event, types.CallbackQuery):
                    await event.answer(texts.ACCESS_DENIED, show_alert=True)
            except TelegramBadRequest as e:
                if "query is too old" in str(e).lower():
                    logger.warning(f"Attempt to answer outdated callback query from {user.id if user else 'Unknown'}")
                else:
                    raise
            
            logger.warning(f"Attempt to access admin function from {user.id if user else 'Unknown'}")
            return
        
        return await func(event, *args, **kwargs)
    
    return wrapper


def error_handler(func: Callable) -> Callable:
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except TelegramBadRequest as e:
            error_message = str(e).lower()
            
            if "query is too old" in error_message or "query id is invalid" in error_message:
                event = _extract_event(args)
                if event and isinstance(event, types.CallbackQuery):
                    user_info = f"@{event.from_user.username}" if event.from_user.username else f"ID:{event.from_user.id}"
                    logger.warning(f"🕐 Ignoring outdated callback '{event.data}' from {user_info} in {func.__name__}")
                else:
                    logger.warning(f"🕐 Ignoring outdated request in {func.__name__}: {e}")
                return None
                
            elif "message is not modified" in error_message:
                logger.debug(f"📝 Message not modified in {func.__name__}")
                event = _extract_event(args)
                if event and isinstance(event, types.CallbackQuery):
                    try:
                        await event.answer()
                    except TelegramBadRequest as answer_error:
                        if "query is too old" not in str(answer_error).lower():
                            logger.error(f"Error answering callback: {answer_error}")
                return None
                
            else:
                logger.error(f"Telegram API error in {func.__name__}: {e}")
                await _send_error_message(args, kwargs, e)
                
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            await _send_error_message(args, kwargs, e)
    
    return wrapper


def _extract_event(args) -> types.TelegramObject:
    for arg in args:
        if isinstance(arg, (types.Message, types.CallbackQuery)):
            return arg
    return None


async def _send_error_message(args, kwargs, original_error):
    try:
        event = _extract_event(args)
        db_user = kwargs.get('db_user')
        
        if not event:
            return
            
        texts = get_texts(db_user.language if db_user else 'ru')
        
        if isinstance(event, types.Message):
            await event.answer(texts.ERROR)
        elif isinstance(event, types.CallbackQuery):
            await event.answer(texts.ERROR, show_alert=True)
                
    except TelegramBadRequest as e:
        if "query is too old" in str(e).lower():
            logger.warning("Failed to send error message - callback query is outdated")
        else:
            logger.error(f"Ошибка при отправке сообщения об ошибке: {e}")
    except Exception as e:
        logger.error(f"Критическая ошибка при отправке сообщения об ошибке: {e}")


def state_cleanup(func: Callable) -> Callable:
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        state = kwargs.get('state')
        
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if state and isinstance(state, FSMContext):
                await state.clear()
            raise e
    
    return wrapper


def typing_action(func: Callable) -> Callable:
    
    @functools.wraps(func)
    async def wrapper(
        event: types.Update,
        *args,
        **kwargs
    ) -> Any:
        if isinstance(event, types.Message):
            try:
                await event.bot.send_chat_action(
                    chat_id=event.chat.id,
                    action="typing"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить typing action: {e}")
        
        return await func(event, *args, **kwargs)
    
    return wrapper


def rate_limit(rate: float = 1.0, key: str = None):
    def decorator(func: Callable) -> Callable:
        
        @functools.wraps(func)
        async def wrapper(
            event: types.Update,
            *args,
            **kwargs
        ) -> Any:
            return await func(event, *args, **kwargs)
        
        return wrapper
    
    return decorator
