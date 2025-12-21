"""
BotConfigService - Single Source of Truth for Bot Configurations and Feature Flags

This service provides a unified interface for accessing bot configurations and feature flags
from dedicated tables (bot_feature_flags and bot_configurations).

All configurations and feature flags are stored in dedicated tables, eliminating redundancy
from the bots table.
"""

from typing import Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.bot_feature_flag import (
    get_feature_flag,
    set_feature_flag,
)
from app.database.crud.bot_configuration import (
    get_configuration,
    set_configuration,
)


class BotConfigService:
    """
    Single Source of Truth for accessing bot configurations and feature flags.
    
    This service provides a clean API for accessing bot configurations and feature flags
    from dedicated tables (bot_feature_flags and bot_configurations).
    """
    
    @staticmethod
    async def is_feature_enabled(
        db: AsyncSession,
        bot_id: int,
        feature_key: str
    ) -> bool:
        """
        Check if a feature is enabled for a bot.
        
        Args:
            db: Database session
            bot_id: Bot ID
            feature_key: Feature key (e.g., 'card_to_card', 'zarinpal')
        
        Returns:
            True if enabled, False otherwise
        """
        feature_flag = await get_feature_flag(db, bot_id, feature_key)
        return feature_flag.enabled if feature_flag else False
    
    @staticmethod
    async def set_feature_enabled(
        db: AsyncSession,
        bot_id: int,
        feature_key: str,
        enabled: bool,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Set or update a feature flag for a bot.
        
        Args:
            db: Database session
            bot_id: Bot ID
            feature_key: Feature key
            enabled: True/False
            config: Optional config dict for the feature
        """
        await set_feature_flag(db, bot_id, feature_key, enabled, config)
    
    @staticmethod
    async def get_config(
        db: AsyncSession,
        bot_id: int,
        config_key: str,
        default: Any = None
    ) -> Any:
        """
        Get a configuration value for a bot.
        
        JSONB Normalization: When storing simple values (string, int, bool), they are
        wrapped in {'value': ...} dict. When reading, automatically unwraps simple values.
        Complex objects are stored as-is.
        
        Args:
            db: Database session
            bot_id: Bot ID
            config_key: Config key (e.g., 'DEFAULT_LANGUAGE', 'SUPPORT_USERNAME')
            default: Default value if not found
        
        Returns:
            Config value or default
        """
        config = await get_configuration(db, bot_id, config_key)
        if config and config.config_value is not None:
            value = config.config_value
            
            # Unwrap simple values from {'value': ...} format
            if isinstance(value, dict) and len(value) == 1 and 'value' in value:
                return value['value']
            
            # Return complex objects as-is
            return value
        
        # Return default if not found
        return default
    
    @staticmethod
    async def set_config(
        db: AsyncSession,
        bot_id: int,
        config_key: str,
        value: Any
    ) -> None:
        """
        Set or update a configuration value for a bot.
        
        JSONB Normalization: When storing simple values (string, int, bool), wraps in
        {'value': ...} dict. When storing complex objects, stores as-is.
        
        Args:
            db: Database session
            bot_id: Bot ID
            config_key: Config key
            value: Config value (can be string, int, bool, dict, etc.)
        """
        # Normalize value for JSONB storage
        if isinstance(value, (str, int, bool, float, type(None))):
            # Simple values: wrap in {'value': ...}
            normalized_value = {'value': value}
        else:
            # Complex objects: store as-is
            normalized_value = value
        
        await set_configuration(db, bot_id, config_key, normalized_value)

