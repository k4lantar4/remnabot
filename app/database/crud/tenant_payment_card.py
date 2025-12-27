import random
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, func, and_
from sqlalchemy.orm import selectinload

from app.database.models import TenantPaymentCard, Bot


async def create_payment_card(
    db: AsyncSession,
    bot_id: int,
    card_number: str,
    card_holder_name: str,
    rotation_strategy: str = "round_robin",
    rotation_interval_minutes: Optional[int] = 60,
    weight: int = 1,
    created_by: Optional[int] = None,
) -> TenantPaymentCard:
    """Create a new payment card."""
    card = TenantPaymentCard(
        bot_id=bot_id,
        card_number=card_number,
        card_holder_name=card_holder_name,
        rotation_strategy=rotation_strategy,
        rotation_interval_minutes=rotation_interval_minutes,
        weight=weight,
        created_by=created_by,
    )

    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


async def get_payment_card(db: AsyncSession, card_id: int) -> Optional[TenantPaymentCard]:
    """Get payment card by ID."""
    result = await db.execute(
        select(TenantPaymentCard).options(selectinload(TenantPaymentCard.bot)).where(TenantPaymentCard.id == card_id)
    )
    return result.scalar_one_or_none()


async def get_payment_cards(db: AsyncSession, bot_id: int, active_only: bool = True) -> List[TenantPaymentCard]:
    """Get all payment cards for a bot."""
    query = select(TenantPaymentCard).where(TenantPaymentCard.bot_id == bot_id)

    if active_only:
        query = query.where(TenantPaymentCard.is_active == True)

    result = await db.execute(query.order_by(TenantPaymentCard.created_at))
    return list(result.scalars().all())


async def update_payment_card(db: AsyncSession, card_id: int, **kwargs) -> Optional[TenantPaymentCard]:
    """Update payment card fields."""
    result = await db.execute(
        update(TenantPaymentCard).where(TenantPaymentCard.id == card_id).values(**kwargs).returning(TenantPaymentCard)
    )
    await db.commit()
    return result.scalar_one_or_none()


async def delete_payment_card(db: AsyncSession, card_id: int) -> bool:
    """Delete a payment card."""
    card = await get_payment_card(db, card_id)
    if not card:
        return False

    await db.delete(card)
    await db.commit()
    return True


async def activate_card(db: AsyncSession, card_id: int) -> bool:
    """Activate a payment card."""
    result = await db.execute(update(TenantPaymentCard).where(TenantPaymentCard.id == card_id).values(is_active=True))
    await db.commit()
    return result.rowcount > 0


async def deactivate_card(db: AsyncSession, card_id: int) -> bool:
    """Deactivate a payment card."""
    result = await db.execute(update(TenantPaymentCard).where(TenantPaymentCard.id == card_id).values(is_active=False))
    await db.commit()
    return result.rowcount > 0


async def update_card_usage(db: AsyncSession, card_id: int, success: bool = True) -> Optional[TenantPaymentCard]:
    """Update card usage statistics."""
    card = await get_payment_card(db, card_id)
    if not card:
        return None

    if success:
        card.success_count += 1
    else:
        card.failure_count += 1

    card.current_usage_count += 1
    card.last_used_at = datetime.utcnow()

    await db.commit()
    await db.refresh(card)
    return card


async def get_next_card_for_rotation(
    db: AsyncSession, bot_id: int, strategy: str = "round_robin"
) -> Optional[TenantPaymentCard]:
    """
    Get next card for rotation based on strategy.
    Strategies: round_robin, random, time_based, weighted
    """
    # Get all active cards for this bot
    cards = await get_payment_cards(db, bot_id, active_only=True)

    if not cards:
        return None

    # Filter cards by strategy if needed
    if strategy != "round_robin":
        cards = [c for c in cards if c.rotation_strategy == strategy]

    if not cards:
        return None

    if strategy == "round_robin":
        # Find card with lowest current_usage_count
        return min(cards, key=lambda c: c.current_usage_count)

    elif strategy == "random":
        # Random selection
        return random.choice(cards)

    elif strategy == "time_based":
        # Find card that hasn't been used recently (based on rotation_interval_minutes)
        now = datetime.utcnow()
        available_cards = []

        for card in cards:
            if card.last_used_at is None:
                available_cards.append(card)
            else:
                interval = timedelta(minutes=card.rotation_interval_minutes or 60)
                if now - card.last_used_at >= interval:
                    available_cards.append(card)

        if available_cards:
            # Return the one with oldest last_used_at
            return min(available_cards, key=lambda c: c.last_used_at or datetime.min)
        else:
            # All cards recently used, return one with oldest last_used_at
            return min(cards, key=lambda c: c.last_used_at or datetime.min)

    elif strategy == "weighted":
        # Weighted selection based on success rate and weight
        weighted_cards = []
        for card in cards:
            total_uses = card.success_count + card.failure_count
            if total_uses == 0:
                # New card, use weight directly
                success_rate = 1.0
            else:
                success_rate = card.success_count / total_uses

            # Calculate weight: base_weight * success_rate
            calculated_weight = card.weight * success_rate
            weighted_cards.append((card, calculated_weight))

        # Select based on weights
        if weighted_cards:
            total_weight = sum(w for _, w in weighted_cards)
            if total_weight > 0:
                rand = random.uniform(0, total_weight)
                current = 0
                for card, weight in weighted_cards:
                    current += weight
                    if rand <= current:
                        return card

            # Fallback: return first card
            return weighted_cards[0][0]

    # Default: return first card
    return cards[0]


async def reset_card_usage_count(db: AsyncSession, card_id: int) -> Optional[TenantPaymentCard]:
    """Reset current_usage_count for a card (useful for round_robin)."""
    result = await db.execute(
        update(TenantPaymentCard)
        .where(TenantPaymentCard.id == card_id)
        .values(current_usage_count=0)
        .returning(TenantPaymentCard)
    )
    await db.commit()
    return result.scalar_one_or_none()


async def get_card_statistics(db: AsyncSession, card_id: int) -> Optional[dict]:
    """Get usage statistics for a card."""
    card = await get_payment_card(db, card_id)
    if not card:
        return None

    total_uses = card.success_count + card.failure_count
    success_rate = (card.success_count / total_uses * 100) if total_uses > 0 else 0

    return {
        "card_id": card.id,
        "success_count": card.success_count,
        "failure_count": card.failure_count,
        "total_uses": total_uses,
        "success_rate": round(success_rate, 2),
        "current_usage_count": card.current_usage_count,
        "last_used_at": card.last_used_at,
        "is_active": card.is_active,
    }
