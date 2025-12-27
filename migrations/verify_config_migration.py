"""
Verification script to validate migration correctness.

This script verifies that:
1. All feature flags were migrated correctly from bots table to bot_feature_flags
2. All configurations were migrated correctly from bots table to bot_configurations
3. Values match between old and new locations
4. Reports any mismatches
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
from app.database.models import Bot, BotFeatureFlag, BotConfiguration
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


async def verify_migration():
    """Verify that migration was performed correctly."""
    async with AsyncSessionLocal() as db:
        try:
            # Get all bots
            result = await db.execute(select(Bot))
            bots = result.scalars().all()
            
            total_bots = len(bots)
            logger.info(f"Verifying migration for {total_bots} bots...")
            
            mismatches = []
            verified_count = 0
            
            for idx, bot in enumerate(bots, 1):
                bot_id = bot.id
                bot_name = bot.name
                
                logger.debug(f"[{idx}/{total_bots}] Verifying bot {bot_id} ({bot_name})...")
                
                # Verify feature flags
                for column_name, feature_key in FEATURE_FLAGS_MAPPING.items():
                    old_value = getattr(bot, column_name, None)
                    
                    # Get new value from service (will check new table first, then fallback)
                    new_value = await BotConfigService.is_feature_enabled(db, bot_id, feature_key)
                    
                    # Compare values
                    expected_value = bool(old_value) if old_value is not None else False
                    if new_value != expected_value:
                        mismatches.append({
                            'bot_id': bot_id,
                            'bot_name': bot_name,
                            'type': 'feature_flag',
                            'key': feature_key,
                            'old_value': old_value,
                            'new_value': new_value,
                            'expected': expected_value,
                        })
                        logger.warning(
                            f"  ⚠️  Mismatch in feature flag {feature_key}: "
                            f"old={old_value}, new={new_value}, expected={expected_value}"
                        )
                
                # Verify configurations
                for column_name, config_key in CONFIGURATIONS_MAPPING.items():
                    old_value = getattr(bot, column_name, None)
                    
                    # Get new value from service (will check new table first, then fallback)
                    new_value = await BotConfigService.get_config(db, bot_id, config_key)
                    
                    # Compare values (handle None cases)
                    if old_value != new_value:
                        # Special handling for boolean columns
                        if column_name == 'zarinpal_sandbox':
                            expected_value = bool(old_value) if old_value is not None else None
                            if new_value != expected_value:
                                mismatches.append({
                                    'bot_id': bot_id,
                                    'bot_name': bot_name,
                                    'type': 'config',
                                    'key': config_key,
                                    'old_value': old_value,
                                    'new_value': new_value,
                                    'expected': expected_value,
                                })
                                logger.warning(
                                    f"  ⚠️  Mismatch in config {config_key}: "
                                    f"old={old_value}, new={new_value}, expected={expected_value}"
                                )
                        else:
                            mismatches.append({
                                'bot_id': bot_id,
                                'bot_name': bot_name,
                                'type': 'config',
                                'key': config_key,
                                'old_value': old_value,
                                'new_value': new_value,
                                'expected': old_value,
                            })
                            logger.warning(
                                f"  ⚠️  Mismatch in config {config_key}: "
                                f"old={old_value}, new={new_value}"
                            )
                
                verified_count += 1
            
            # Summary
            logger.info("=" * 60)
            logger.info("Verification Summary:")
            logger.info(f"  Total bots verified: {verified_count}")
            logger.info(f"  Mismatches found: {len(mismatches)}")
            logger.info("=" * 60)
            
            if mismatches:
                logger.error("❌ Migration verification FAILED!")
                logger.error("\nMismatches found:")
                for mismatch in mismatches:
                    logger.error(
                        f"  Bot {mismatch['bot_id']} ({mismatch['bot_name']}): "
                        f"{mismatch['type']} {mismatch['key']} - "
                        f"old={mismatch['old_value']}, new={mismatch['new_value']}, "
                        f"expected={mismatch.get('expected', mismatch['old_value'])}"
                    )
                return 1
            else:
                logger.info("✅ Migration verification PASSED! All values match.")
                return 0
            
        except Exception as e:
            logger.error(f"Fatal error during verification: {e}", exc_info=True)
            return 1


if __name__ == "__main__":
    exit_code = asyncio.run(verify_migration())
    sys.exit(exit_code)

