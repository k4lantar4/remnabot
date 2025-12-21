"""
Migration script to copy data from bots table to bot_feature_flags and bot_configurations tables.

This script migrates:
- Feature flags: card_to_card_enabled, zarinpal_enabled
- Configurations: default_language, support_username, admin_chat_id, admin_topic_id,
  notification_group_id, notification_topic_id, card_receipt_topic_id,
  zarinpal_merchant_id, zarinpal_sandbox

The script uses BotConfigService to ensure dual-write during transition period.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from app.database.database import AsyncSessionLocal
from app.database.models import Bot
from app.services.bot_config_service import BotConfigService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Feature flags mapping: column_name -> feature_key
FEATURE_FLAGS_MAPPING = {
    'card_to_card_enabled': 'card_to_card',
    'zarinpal_enabled': 'zarinpal',
}

# Configurations mapping: column_name -> config_key
CONFIGURATIONS_MAPPING = {
    'default_language': 'DEFAULT_LANGUAGE',
    'support_username': 'SUPPORT_USERNAME',
    'admin_chat_id': 'ADMIN_NOTIFICATIONS_CHAT_ID',
    'admin_topic_id': 'ADMIN_NOTIFICATIONS_TOPIC_ID',
    'notification_group_id': 'NOTIFICATION_GROUP_ID',
    'notification_topic_id': 'NOTIFICATION_TOPIC_ID',
    'card_receipt_topic_id': 'CARD_RECEIPT_TOPIC_ID',
    'zarinpal_merchant_id': 'ZARINPAL_MERCHANT_ID',
    'zarinpal_sandbox': 'ZARINPAL_SANDBOX',
}


async def migrate_bot_configs():
    """Migrate configurations from bots table to dedicated tables."""
    async with AsyncSessionLocal() as db:
        try:
            # Get all bots
            result = await db.execute(select(Bot))
            bots = result.scalars().all()
            
            total_bots = len(bots)
            logger.info(f"Found {total_bots} bots to migrate")
            
            migrated_count = 0
            skipped_count = 0
            error_count = 0
            
            for idx, bot in enumerate(bots, 1):
                bot_id = bot.id
                bot_name = bot.name
                
                try:
                    logger.info(f"[{idx}/{total_bots}] Migrating bot {bot_id} ({bot_name})...")
                    
                    # Migrate feature flags
                    for column_name, feature_key in FEATURE_FLAGS_MAPPING.items():
                        column_value = getattr(bot, column_name, None)
                        if column_value is not None:
                            await BotConfigService.set_feature_enabled(
                                db, bot_id, feature_key, bool(column_value)
                            )
                            logger.debug(f"  ✓ Migrated feature flag: {feature_key} = {column_value}")
                    
                    # Migrate configurations
                    for column_name, config_key in CONFIGURATIONS_MAPPING.items():
                        column_value = getattr(bot, column_name, None)
                        if column_value is not None:
                            await BotConfigService.set_config(
                                db, bot_id, config_key, column_value
                            )
                            logger.debug(f"  ✓ Migrated config: {config_key} = {column_value}")
                    
                    # Commit after each bot to allow partial rollback
                    await db.commit()
                    migrated_count += 1
                    logger.info(f"  ✅ Bot {bot_id} migrated successfully")
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"  ❌ Error migrating bot {bot_id}: {e}", exc_info=True)
                    await db.rollback()
                    # Continue with next bot
                    continue
            
            # Summary
            logger.info("=" * 60)
            logger.info("Migration Summary:")
            logger.info(f"  Total bots: {total_bots}")
            logger.info(f"  Successfully migrated: {migrated_count}")
            logger.info(f"  Skipped: {skipped_count}")
            logger.info(f"  Errors: {error_count}")
            logger.info("=" * 60)
            
            if error_count > 0:
                logger.warning("⚠️  Some bots failed to migrate. Please review errors above.")
                return 1
            
            logger.info("✅ Migration completed successfully!")
            return 0
            
        except Exception as e:
            logger.error(f"Fatal error during migration: {e}", exc_info=True)
            await db.rollback()
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(migrate_bot_configs())
    sys.exit(exit_code)

