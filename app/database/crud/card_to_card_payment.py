import logging
import secrets
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import CardToCardPayment, User, Transaction

logger = logging.getLogger(__name__)


def generate_tracking_number() -> str:
    """Generate a unique tracking number for card-to-card payment."""
    return f"C2C{secrets.token_hex(8).upper()}"


async def create_card_payment(
    db: AsyncSession,
    bot_id: int,
    user_id: int,
    amount_kopeks: int,
    tracking_number: Optional[str] = None,
    card_id: Optional[int] = None,
    receipt_type: Optional[str] = None,
    receipt_text: Optional[str] = None,
    receipt_image_file_id: Optional[str] = None,
    status: str = 'pending'
) -> CardToCardPayment:
    """Create a new card-to-card payment record."""
    if not tracking_number:
        tracking_number = generate_tracking_number()
    
    payment = CardToCardPayment(
        bot_id=bot_id,
        user_id=user_id,
        amount_kopeks=amount_kopeks,
        tracking_number=tracking_number,
        card_id=card_id,
        receipt_type=receipt_type,
        receipt_text=receipt_text,
        receipt_image_file_id=receipt_image_file_id,
        status=status
    )
    
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    
    logger.info(f"✅ Card payment created: {tracking_number} (ID: {payment.id})")
    return payment


async def get_payment_by_id(
    db: AsyncSession,
    payment_id: int,
    bot_id: Optional[int] = None
) -> Optional[CardToCardPayment]:
    """Get card payment by ID."""
    query = select(CardToCardPayment).options(
        selectinload(CardToCardPayment.user),
        selectinload(CardToCardPayment.card),
        selectinload(CardToCardPayment.transaction)
    ).where(CardToCardPayment.id == payment_id)
    
    if bot_id is not None:
        query = query.where(CardToCardPayment.bot_id == bot_id)
    
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_payment_by_tracking(
    db: AsyncSession,
    tracking_number: str,
    bot_id: Optional[int] = None
) -> Optional[CardToCardPayment]:
    """Get card payment by tracking number."""
    query = select(CardToCardPayment).options(
        selectinload(CardToCardPayment.user),
        selectinload(CardToCardPayment.card),
        selectinload(CardToCardPayment.transaction)
    ).where(CardToCardPayment.tracking_number == tracking_number)
    
    if bot_id is not None:
        query = query.where(CardToCardPayment.bot_id == bot_id)
    
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_user_payments(
    db: AsyncSession,
    user_id: int,
    bot_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[CardToCardPayment]:
    """Get card payments for a user."""
    query = select(CardToCardPayment).options(
        selectinload(CardToCardPayment.card),
        selectinload(CardToCardPayment.transaction)
    ).where(CardToCardPayment.user_id == user_id)
    
    if bot_id is not None:
        query = query.where(CardToCardPayment.bot_id == bot_id)
    
    if status:
        query = query.where(CardToCardPayment.status == status)
    
    query = query.order_by(CardToCardPayment.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


async def get_pending_payments(
    db: AsyncSession,
    bot_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
) -> List[CardToCardPayment]:
    """Get pending card payments."""
    query = select(CardToCardPayment).options(
        selectinload(CardToCardPayment.user),
        selectinload(CardToCardPayment.card)
    ).where(CardToCardPayment.status == 'pending')
    
    if bot_id is not None:
        query = query.where(CardToCardPayment.bot_id == bot_id)
    
    query = query.order_by(CardToCardPayment.created_at.asc()).offset(offset).limit(limit)
    
    result = await db.execute(query)
    return result.scalars().all()


async def update_payment_status(
    db: AsyncSession,
    payment_id: int,
    status: str,
    admin_reviewed_by: Optional[int] = None,
    admin_notes: Optional[str] = None,
    transaction_id: Optional[int] = None,
    bot_id: Optional[int] = None
) -> Optional[CardToCardPayment]:
    """Update payment status."""
    query = select(CardToCardPayment).where(CardToCardPayment.id == payment_id)
    
    if bot_id is not None:
        query = query.where(CardToCardPayment.bot_id == bot_id)
    
    result = await db.execute(query)
    payment = result.scalar_one_or_none()
    
    if not payment:
        return None
    
    payment.status = status
    payment.updated_at = datetime.utcnow()
    
    if admin_reviewed_by:
        payment.admin_reviewed_by = admin_reviewed_by
        payment.admin_reviewed_at = datetime.utcnow()
    
    if admin_notes:
        payment.admin_notes = admin_notes
    
    if transaction_id:
        payment.transaction_id = transaction_id
    
    await db.commit()
    await db.refresh(payment)
    
    logger.info(f"✅ Card payment {payment.tracking_number} status updated to {status}")
    return payment
