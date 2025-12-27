"""
Initialize master bot from config.
This should be called on startup to ensure master bot exists.
"""

import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.bot import get_bot_by_token, create_bot, get_master_bot

logger = logging.getLogger(__name__)


async def ensure_master_bot(db: AsyncSession) -> tuple[bool, str]:
    """
    Ensure master bot exists in database.
    Creates it from BOT_TOKEN in config if doesn't exist.

    Returns: (success: bool, message: str)
    """
    try:
        # Check if master bot already exists
        master_bot = await get_master_bot(db)
        if master_bot:
            logger.info(f"✅ Master bot already exists: ID={master_bot.id}, Name={master_bot.name}")
            return True, f"Master bot already exists (ID: {master_bot.id})"

        # Check if bot with this token exists (might not be master)
        existing_bot = await get_bot_by_token(db, settings.BOT_TOKEN)
        if existing_bot:
            # Update to master
            existing_bot.is_master = True
            await db.commit()
            logger.info(f"✅ Updated existing bot to master: ID={existing_bot.id}")
            return True, f"Updated existing bot to master (ID: {existing_bot.id})"

        # Create new master bot
        bot_name = settings.BOT_USERNAME or "Master Bot"
        bot, api_token = await create_bot(
            db=db,
            name=bot_name,
            telegram_bot_token=settings.BOT_TOKEN,
            is_master=True,
            is_active=True,
            default_language="fa",
        )

        logger.info(f"✅ Master bot created: ID={bot.id}, Name={bot.name}")
        logger.warning(f"⚠️  IMPORTANT: Save this API token securely: {api_token}")
        logger.warning(f"⚠️  This token will not be shown again!")

        return True, f"Master bot created (ID: {bot.id}, API Token: {api_token[:20]}...)"

    except Exception as e:
        logger.error(f"❌ Error ensuring master bot: {e}", exc_info=True)
        return False, f"Error: {str(e)}"
