"""
Initialize master bot from config.
This should be called on startup to ensure master bot exists.
Master bot uses .env file for configuration and stores configs in dedicated tables.
"""
import logging
import os
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.bot import get_bot_by_token, create_bot, get_master_bot
from app.services.bot_config_service import BotConfigService

logger = logging.getLogger(__name__)


def _get_env_config(key: str, default=None):
    """Get config from environment variable."""
    return os.getenv(key, default)


async def _sync_master_bot_configs_from_env(db: AsyncSession, bot_id: int) -> None:
    """
    Sync master bot configurations from .env file to dedicated tables.
    This makes master bot work like a tenant bot, using BotConfigService.
    """
    logger.info(f"🔄 Syncing master bot (ID: {bot_id}) configs from .env...")
    
    # Feature flags from .env
    manual_payment_enabled = _get_env_config('MANUAL_PAYMENT_ENABLED', 'false').lower() == 'true'
    zarinpal_enabled = _get_env_config('ZARINPAL_ENABLED', 'false').lower() == 'true'
    
    await BotConfigService.set_feature_enabled(db, bot_id, 'card_to_card', manual_payment_enabled)
    await BotConfigService.set_feature_enabled(db, bot_id, 'zarinpal', zarinpal_enabled)
    logger.debug(f"  ✓ Feature flags synced: card_to_card={manual_payment_enabled}, zarinpal={zarinpal_enabled}")
    
    # Configurations from .env
    default_language = _get_env_config('DEFAULT_LANGUAGE', 'fa')
    support_username = _get_env_config('SUPPORT_USERNAME')
    admin_chat_id = _get_env_config('ADMIN_NOTIFICATIONS_CHAT_ID')
    admin_topic_id = _get_env_config('ADMIN_NOTIFICATIONS_TOPIC_ID')
    notification_group_id = _get_env_config('NOTIFICATION_GROUP_ID')
    notification_topic_id = _get_env_config('NOTIFICATION_TOPIC_ID')
    card_receipt_topic_id = _get_env_config('CARD_RECEIPT_TOPIC_ID')
    zarinpal_merchant_id = _get_env_config('ZARINPAL_MERCHANT_ID')
    zarinpal_sandbox = _get_env_config('ZARINPAL_SANDBOX', 'false').lower() == 'true'
    
    await BotConfigService.set_config(db, bot_id, 'DEFAULT_LANGUAGE', default_language)
    logger.debug(f"  ✓ DEFAULT_LANGUAGE={default_language}")
    
    if support_username:
        await BotConfigService.set_config(db, bot_id, 'SUPPORT_USERNAME', support_username)
        logger.debug(f"  ✓ SUPPORT_USERNAME={support_username}")
    
    if admin_chat_id:
        try:
            admin_chat_id_int = int(admin_chat_id)
            await BotConfigService.set_config(db, bot_id, 'ADMIN_NOTIFICATIONS_CHAT_ID', admin_chat_id_int)
            logger.debug(f"  ✓ ADMIN_NOTIFICATIONS_CHAT_ID={admin_chat_id_int}")
        except (ValueError, TypeError):
            logger.warning(f"  ⚠️ Invalid ADMIN_NOTIFICATIONS_CHAT_ID: {admin_chat_id}")
    
    if admin_topic_id:
        try:
            admin_topic_id_int = int(admin_topic_id)
            await BotConfigService.set_config(db, bot_id, 'ADMIN_NOTIFICATIONS_TOPIC_ID', admin_topic_id_int)
            logger.debug(f"  ✓ ADMIN_NOTIFICATIONS_TOPIC_ID={admin_topic_id_int}")
        except (ValueError, TypeError):
            logger.warning(f"  ⚠️ Invalid ADMIN_NOTIFICATIONS_TOPIC_ID: {admin_topic_id}")
    
    if notification_group_id:
        try:
            notification_group_id_int = int(notification_group_id)
            await BotConfigService.set_config(db, bot_id, 'NOTIFICATION_GROUP_ID', notification_group_id_int)
            logger.debug(f"  ✓ NOTIFICATION_GROUP_ID={notification_group_id_int}")
        except (ValueError, TypeError):
            logger.warning(f"  ⚠️ Invalid NOTIFICATION_GROUP_ID: {notification_group_id}")
    
    if notification_topic_id:
        try:
            notification_topic_id_int = int(notification_topic_id)
            await BotConfigService.set_config(db, bot_id, 'NOTIFICATION_TOPIC_ID', notification_topic_id_int)
            logger.debug(f"  ✓ NOTIFICATION_TOPIC_ID={notification_topic_id_int}")
        except (ValueError, TypeError):
            logger.warning(f"  ⚠️ Invalid NOTIFICATION_TOPIC_ID: {notification_topic_id}")
    
    if card_receipt_topic_id:
        try:
            card_receipt_topic_id_int = int(card_receipt_topic_id)
            await BotConfigService.set_config(db, bot_id, 'CARD_RECEIPT_TOPIC_ID', card_receipt_topic_id_int)
            logger.debug(f"  ✓ CARD_RECEIPT_TOPIC_ID={card_receipt_topic_id_int}")
        except (ValueError, TypeError):
            logger.warning(f"  ⚠️ Invalid CARD_RECEIPT_TOPIC_ID: {card_receipt_topic_id}")
    
    if zarinpal_merchant_id:
        await BotConfigService.set_config(db, bot_id, 'ZARINPAL_MERCHANT_ID', zarinpal_merchant_id)
        logger.debug(f"  ✓ ZARINPAL_MERCHANT_ID={zarinpal_merchant_id}")
    
    await BotConfigService.set_config(db, bot_id, 'ZARINPAL_SANDBOX', zarinpal_sandbox)
    logger.debug(f"  ✓ ZARINPAL_SANDBOX={zarinpal_sandbox}")
    
    logger.info(f"✅ Master bot configs synced from .env")


async def ensure_master_bot(db: AsyncSession) -> tuple[bool, str]:
    """
    Ensure master bot exists in database.
    Creates it from BOT_TOKEN in config if doesn't exist.
    Syncs configurations from .env file to dedicated tables.
    
    Returns: (success: bool, message: str)
    """
    try:
        # Check if master bot already exists
        master_bot = await get_master_bot(db)
        if master_bot:
            logger.info(f"✅ Master bot already exists: ID={master_bot.id}, Name={master_bot.name}")
            # Sync configs from .env (in case .env was updated)
            await _sync_master_bot_configs_from_env(db, master_bot.id)
            return True, f"Master bot already exists (ID: {master_bot.id})"
        
        # Check if bot with this token exists (might not be master)
        existing_bot = await get_bot_by_token(db, settings.BOT_TOKEN)
        if existing_bot:
            # Update to master
            existing_bot.is_master = True
            await db.commit()
            logger.info(f"✅ Updated existing bot to master: ID={existing_bot.id}")
            # Sync configs from .env
            await _sync_master_bot_configs_from_env(db, existing_bot.id)
            return True, f"Updated existing bot to master (ID: {existing_bot.id})"
        
        # Create new master bot (without redundant config columns)
        bot_name = settings.BOT_USERNAME or "Master Bot"
        bot, api_token = await create_bot(
            db=db,
            name=bot_name,
            telegram_bot_token=settings.BOT_TOKEN,
            is_master=True,
            is_active=True,
        )
        
        logger.info(f"✅ Master bot created: ID={bot.id}, Name={bot.name}")
        logger.warning(f"⚠️  IMPORTANT: Save this API token securely: {api_token}")
        logger.warning(f"⚠️  This token will not be shown again!")
        
        # Sync configs from .env to dedicated tables
        await _sync_master_bot_configs_from_env(db, bot.id)
        
        return True, f"Master bot created (ID: {bot.id}, API Token: {api_token[:20]}...)"
        
    except Exception as e:
        logger.error(f"❌ Error ensuring master bot: {e}", exc_info=True)
        return False, f"Error: {str(e)}"
