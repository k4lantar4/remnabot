from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.database.models import BotConfiguration, Bot


async def get_configuration(db: AsyncSession, bot_id: int, config_key: str) -> Optional[BotConfiguration]:
    """Get a specific configuration for a bot."""
    result = await db.execute(
        select(BotConfiguration)
        .options(selectinload(BotConfiguration.bot))
        .where(BotConfiguration.bot_id == bot_id, BotConfiguration.config_key == config_key)
    )
    return result.scalar_one_or_none()


async def get_config_value(db: AsyncSession, bot_id: int, config_key: str) -> Optional[Dict[str, Any]]:
    """Get configuration value (JSONB) for a bot."""
    config = await get_configuration(db, bot_id, config_key)
    if config and config.config_value:
        return config.config_value if isinstance(config.config_value, dict) else {}
    return None


async def set_configuration(
    db: AsyncSession, bot_id: int, config_key: str, config_value: Dict[str, Any]
) -> BotConfiguration:
    """
    Set or update a configuration for a bot.
    Creates if doesn't exist, updates if exists.
    """
    existing = await get_configuration(db, bot_id, config_key)

    if existing:
        # Update existing
        existing.config_value = config_value
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        # Create new
        configuration = BotConfiguration(bot_id=bot_id, config_key=config_key, config_value=config_value)
        db.add(configuration)
        await db.commit()
        await db.refresh(configuration)
        return configuration


async def get_all_configurations(db: AsyncSession, bot_id: int) -> List[BotConfiguration]:
    """Get all configurations for a bot."""
    result = await db.execute(
        select(BotConfiguration).where(BotConfiguration.bot_id == bot_id).order_by(BotConfiguration.config_key)
    )
    return list(result.scalars().all())


async def get_all_configurations_dict(db: AsyncSession, bot_id: int) -> Dict[str, Dict[str, Any]]:
    """Get all configurations as a dictionary (config_key -> config_value)."""
    configs = await get_all_configurations(db, bot_id)
    return {
        config.config_key: (config.config_value if isinstance(config.config_value, dict) else {}) for config in configs
    }


async def delete_configuration(db: AsyncSession, bot_id: int, config_key: str) -> bool:
    """Delete a configuration."""
    result = await db.execute(
        delete(BotConfiguration).where(BotConfiguration.bot_id == bot_id, BotConfiguration.config_key == config_key)
    )
    await db.commit()
    return result.rowcount > 0


async def delete_all_configurations(db: AsyncSession, bot_id: int) -> int:
    """Delete all configurations for a bot."""
    result = await db.execute(delete(BotConfiguration).where(BotConfiguration.bot_id == bot_id))
    await db.commit()
    return result.rowcount


async def update_configuration_partial(
    db: AsyncSession, bot_id: int, config_key: str, partial_value: Dict[str, Any]
) -> Optional[BotConfiguration]:
    """
    Update configuration by merging partial value with existing.
    Creates new config if doesn't exist.
    """
    existing = await get_configuration(db, bot_id, config_key)

    if existing:
        # Merge with existing
        current_value = existing.config_value if isinstance(existing.config_value, dict) else {}
        merged_value = {**current_value, **partial_value}
        existing.config_value = merged_value
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        # Create new with partial value
        return await set_configuration(db, bot_id, config_key, partial_value)
