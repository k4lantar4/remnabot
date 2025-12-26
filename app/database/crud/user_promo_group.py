"""CRUD operations for linking users with promo groups (Many-to-Many)."""
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import UserPromoGroup, PromoGroup, User

logger = logging.getLogger(__name__)


async def _sync_user_primary_promo_group(
    db: AsyncSession,
    user_id: int,
) -> None:
    """Synchronizes users.promo_group_id column with primary promo group."""

    try:
        result = await db.execute(
            select(UserPromoGroup.promo_group_id)
            .join(PromoGroup, UserPromoGroup.promo_group_id == PromoGroup.id)
            .where(UserPromoGroup.user_id == user_id)
            .order_by(desc(PromoGroup.priority), PromoGroup.id)
        )

        first = result.first()
        new_primary_id = first[0] if first else None

        user = await db.get(User, user_id)
        if not user:
            return

        if user.promo_group_id != new_primary_id:
            user.promo_group_id = new_primary_id
            user.updated_at = datetime.utcnow()

    except Exception as error:
        logger.error(
            "Error synchronizing primary promo group for user %s: %s",
            user_id,
            error,
        )


async def sync_user_primary_promo_group(
    db: AsyncSession,
    user_id: int,
) -> None:
    """Public wrapper for synchronizing user's primary promo group."""

    await _sync_user_primary_promo_group(db, user_id)


async def add_user_to_promo_group(
    db: AsyncSession,
    user_id: int,
    promo_group_id: int,
    assigned_by: str = "admin"
) -> Optional[UserPromoGroup]:
    """
    Adds promo group to user.

    Args:
        db: DB session
        user_id: User ID
        promo_group_id: Promo group ID
        assigned_by: Who assigned ('admin', 'system', 'auto', 'promocode')

    Returns:
        UserPromoGroup or None if already exists
    """
    try:
        # Check if link exists
        existing = await has_user_promo_group(db, user_id, promo_group_id)
        if existing:
            logger.info(f"User {user_id} already has promo group {promo_group_id}")
            return None

        # Create new link
        user_promo_group = UserPromoGroup(
            user_id=user_id,
            promo_group_id=promo_group_id,
            assigned_by=assigned_by,
        )
        db.add(user_promo_group)
        await db.flush()

        await _sync_user_primary_promo_group(db, user_id)

        await db.commit()
        await db.refresh(user_promo_group)

        logger.info(f"Promo group {promo_group_id} added to user {user_id} ({assigned_by})")
        return user_promo_group

    except Exception as error:
        logger.error(f"Error adding promo group to user: {error}")
        await db.rollback()
        return None


async def remove_user_from_promo_group(
    db: AsyncSession,
    user_id: int,
    promo_group_id: int
) -> bool:
    """
    Removes promo group from user.

    Args:
        db: DB session
        user_id: User ID
        promo_group_id: Promo group ID

    Returns:
        True if removed, False if link didn't exist
    """
    try:
        result = await db.execute(
            select(UserPromoGroup).where(
                and_(
                    UserPromoGroup.user_id == user_id,
                    UserPromoGroup.promo_group_id == promo_group_id
                )
            )
        )
        user_promo_group = result.scalar_one_or_none()

        if not user_promo_group:
            logger.warning(f"User {user_id} link with promo group {promo_group_id} not found")
            return False

        await db.delete(user_promo_group)
        await db.flush()

        await _sync_user_primary_promo_group(db, user_id)

        await db.commit()

        logger.info(f"Promo group {promo_group_id} removed from user {user_id}")
        return True

    except Exception as error:
        logger.error(f"Error removing promo group from user: {error}")
        await db.rollback()
        return False


async def get_user_promo_groups(
    db: AsyncSession,
    user_id: int
) -> List[UserPromoGroup]:
    """
    Gets all user promo groups, sorted by priority.

    Args:
        db: DB session
        user_id: User ID

    Returns:
        List of UserPromoGroup with loaded PromoGroup, sorted by priority DESC
    """
    try:
        result = await db.execute(
            select(UserPromoGroup)
            .options(selectinload(UserPromoGroup.promo_group))
            .where(UserPromoGroup.user_id == user_id)
            .join(PromoGroup, UserPromoGroup.promo_group_id == PromoGroup.id)
            .order_by(desc(PromoGroup.priority), PromoGroup.id)
        )
        return list(result.scalars().all())

    except Exception as error:
        logger.error(f"Error getting user promo groups {user_id}: {error}")
        return []


async def get_primary_user_promo_group(
    db: AsyncSession,
    user_id: int
) -> Optional[PromoGroup]:
    """
    Gets user promo group with maximum priority.

    Args:
        db: DB session
        user_id: User ID

    Returns:
        PromoGroup with maximum priority or None
    """
    try:
        user_promo_groups = await get_user_promo_groups(db, user_id)

        if not user_promo_groups:
            return None

        # First in list has maximum priority (list is already sorted)
        return user_promo_groups[0].promo_group if user_promo_groups[0].promo_group else None

    except Exception as error:
        logger.error(f"Error getting primary promo group for user {user_id}: {error}")
        return None


async def has_user_promo_group(
    db: AsyncSession,
    user_id: int,
    promo_group_id: int
) -> bool:
    """
    Checks if user has promo group.

    Args:
        db: DB session
        user_id: User ID
        promo_group_id: Promo group ID

    Returns:
        True if user already has this promo group
    """
    try:
        result = await db.execute(
            select(UserPromoGroup).where(
                and_(
                    UserPromoGroup.user_id == user_id,
                    UserPromoGroup.promo_group_id == promo_group_id
                )
            )
        )
        return result.scalar_one_or_none() is not None

    except Exception as error:
        logger.error(f"Error checking user promo group: {error}")
        return False


async def count_user_promo_groups(
    db: AsyncSession,
    user_id: int
) -> int:
    """
    Counts number of promo groups for user.

    Args:
        db: DB session
        user_id: User ID

    Returns:
        Number of promo groups
    """
    try:
        result = await db.execute(
            select(UserPromoGroup).where(UserPromoGroup.user_id == user_id)
        )
        return len(list(result.scalars().all()))

    except Exception as error:
        logger.error(f"Error counting user promo groups: {error}")
        return 0


async def replace_user_promo_groups(
    db: AsyncSession,
    user_id: int,
    promo_group_ids: List[int],
    assigned_by: str = "admin"
) -> bool:
    """
    Replaces all user promo groups with new list.

    Args:
        db: DB session
        user_id: User ID
        promo_group_ids: List of promo group IDs
        assigned_by: Who assigned

    Returns:
        True if successful
    """
    try:
        # Remove all current promo groups
        await db.execute(
            select(UserPromoGroup).where(UserPromoGroup.user_id == user_id)
        )
        result = await db.execute(
            select(UserPromoGroup).where(UserPromoGroup.user_id == user_id)
        )
        for upg in result.scalars().all():
            await db.delete(upg)

        # Add new ones
        for promo_group_id in promo_group_ids:
            user_promo_group = UserPromoGroup(
                user_id=user_id,
                promo_group_id=promo_group_id,
                assigned_by=assigned_by
            )
            db.add(user_promo_group)

        await db.commit()
        logger.info(f"User {user_id} promo groups replaced with {promo_group_ids}")
        return True

    except Exception as error:
        logger.error(f"Error replacing user promo groups: {error}")
        await db.rollback()
        return False
