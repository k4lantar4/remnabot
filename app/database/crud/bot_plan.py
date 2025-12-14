from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload

from app.database.models import BotPlan, Bot


async def create_plan(
    db: AsyncSession,
    bot_id: int,
    name: str,
    period_days: int,
    price_kopeks: int,
    traffic_limit_gb: int = 0,
    device_limit: int = 1,
    sort_order: int = 0,
    is_active: bool = True
) -> BotPlan:
    """Create a new plan for a bot."""
    plan = BotPlan(
        bot_id=bot_id,
        name=name,
        period_days=period_days,
        price_kopeks=price_kopeks,
        traffic_limit_gb=traffic_limit_gb,
        device_limit=device_limit,
        sort_order=sort_order,
        is_active=is_active
    )
    
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def get_plan(
    db: AsyncSession,
    plan_id: int
) -> Optional[BotPlan]:
    """Get plan by ID."""
    result = await db.execute(
        select(BotPlan)
        .options(selectinload(BotPlan.bot))
        .where(BotPlan.id == plan_id)
    )
    return result.scalar_one_or_none()


async def get_plans(
    db: AsyncSession,
    bot_id: int,
    active_only: bool = True
) -> List[BotPlan]:
    """Get all plans for a bot, ordered by sort_order."""
    query = select(BotPlan).where(BotPlan.bot_id == bot_id)
    
    if active_only:
        query = query.where(BotPlan.is_active == True)
    
    result = await db.execute(
        query.order_by(BotPlan.sort_order, BotPlan.price_kopeks)
    )
    return list(result.scalars().all())


async def update_plan(
    db: AsyncSession,
    plan_id: int,
    **kwargs
) -> Optional[BotPlan]:
    """Update plan fields."""
    result = await db.execute(
        update(BotPlan)
        .where(BotPlan.id == plan_id)
        .values(**kwargs)
        .returning(BotPlan)
    )
    await db.commit()
    return result.scalar_one_or_none()


async def delete_plan(
    db: AsyncSession,
    plan_id: int
) -> bool:
    """Delete a plan."""
    plan = await get_plan(db, plan_id)
    if not plan:
        return False
    
    await db.delete(plan)
    await db.commit()
    return True


async def activate_plan(
    db: AsyncSession,
    plan_id: int
) -> bool:
    """Activate a plan."""
    result = await db.execute(
        update(BotPlan)
        .where(BotPlan.id == plan_id)
        .values(is_active=True)
    )
    await db.commit()
    return result.rowcount > 0


async def deactivate_plan(
    db: AsyncSession,
    plan_id: int
) -> bool:
    """Deactivate a plan."""
    result = await db.execute(
        update(BotPlan)
        .where(BotPlan.id == plan_id)
        .values(is_active=False)
    )
    await db.commit()
    return result.rowcount > 0


async def get_plan_by_price_range(
    db: AsyncSession,
    bot_id: int,
    min_price_kopeks: Optional[int] = None,
    max_price_kopeks: Optional[int] = None,
    active_only: bool = True
) -> List[BotPlan]:
    """Get plans within a price range."""
    query = select(BotPlan).where(BotPlan.bot_id == bot_id)
    
    if active_only:
        query = query.where(BotPlan.is_active == True)
    
    if min_price_kopeks is not None:
        query = query.where(BotPlan.price_kopeks >= min_price_kopeks)
    
    if max_price_kopeks is not None:
        query = query.where(BotPlan.price_kopeks <= max_price_kopeks)
    
    result = await db.execute(
        query.order_by(BotPlan.sort_order, BotPlan.price_kopeks)
    )
    return list(result.scalars().all())


async def update_plan_sort_order(
    db: AsyncSession,
    plan_id: int,
    sort_order: int
) -> Optional[BotPlan]:
    """Update plan sort order."""
    return await update_plan(db, plan_id, sort_order=sort_order)


async def reorder_plans(
    db: AsyncSession,
    bot_id: int,
    plan_ids: List[int]
) -> bool:
    """
    Reorder plans by providing list of plan IDs in desired order.
    Updates sort_order for each plan.
    """
    for index, plan_id in enumerate(plan_ids):
        await update_plan(db, plan_id, sort_order=index)
    
    return True
