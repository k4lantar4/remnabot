import secrets
import hashlib
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.database.models import Bot


def generate_api_token() -> str:
    """Generate a secure API token."""
    return secrets.token_urlsafe(32)


def hash_api_token(token: str) -> str:
    """Hash API token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def get_bot_by_id(db: AsyncSession, bot_id: int) -> Optional[Bot]:
    """Get bot by ID."""
    result = await db.execute(select(Bot).where(Bot.id == bot_id))
    return result.scalar_one_or_none()


async def get_bot_by_token(db: AsyncSession, telegram_token: str) -> Optional[Bot]:
    """Get bot by Telegram bot token."""
    result = await db.execute(select(Bot).where(Bot.telegram_bot_token == telegram_token))
    return result.scalar_one_or_none()


async def get_bot_by_api_token(db: AsyncSession, api_token: str) -> Optional[Bot]:
    """Get bot by API token (hashed)."""
    token_hash = hash_api_token(api_token)
    result = await db.execute(select(Bot).where(Bot.api_token_hash == token_hash))
    return result.scalar_one_or_none()


async def get_master_bot(db: AsyncSession) -> Optional[Bot]:
    """Get master bot."""
    result = await db.execute(select(Bot).where(Bot.is_master == True, Bot.is_active == True))
    return result.scalar_one_or_none()


async def get_active_bots(db: AsyncSession) -> List[Bot]:
    """Get all active bots."""
    result = await db.execute(select(Bot).where(Bot.is_active == True))
    return list(result.scalars().all())


async def get_all_bots(db: AsyncSession) -> List[Bot]:
    """Get all bots (active and inactive)."""
    result = await db.execute(select(Bot).order_by(Bot.created_at.desc()))
    return list(result.scalars().all())


async def create_bot(
    db: AsyncSession, name: str, telegram_bot_token: str, is_master: bool = False, is_active: bool = True, **kwargs
) -> tuple[Bot, str]:
    """
    Create a new bot.
    Returns: (Bot instance, plain API token)
    """
    # Generate API token
    api_token = generate_api_token()
    api_token_hash = hash_api_token(api_token)

    bot = Bot(
        name=name,
        telegram_bot_token=telegram_bot_token,
        api_token=api_token,  # Store plain token temporarily (will be removed after first read)
        api_token_hash=api_token_hash,
        is_master=is_master,
        is_active=is_active,
        **kwargs,
    )

    db.add(bot)
    await db.commit()
    await db.refresh(bot)

    return bot, api_token


async def update_bot(db: AsyncSession, bot_id: int, **kwargs) -> Optional[Bot]:
    """Update bot fields."""
    result = await db.execute(update(Bot).where(Bot.id == bot_id).values(**kwargs).returning(Bot))
    await db.commit()
    return result.scalar_one_or_none()


async def deactivate_bot(db: AsyncSession, bot_id: int) -> bool:
    """Deactivate a bot."""
    result = await db.execute(update(Bot).where(Bot.id == bot_id).values(is_active=False))
    await db.commit()
    return result.rowcount > 0


async def activate_bot(db: AsyncSession, bot_id: int) -> bool:
    """Activate a bot."""
    result = await db.execute(update(Bot).where(Bot.id == bot_id).values(is_active=True))
    await db.commit()
    return result.rowcount > 0


async def delete_bot(db: AsyncSession, bot_id: int) -> bool:
    """Delete a bot (cascade will delete related data)."""
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        return False

    await db.delete(bot)
    await db.commit()
    return True
