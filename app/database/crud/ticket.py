from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_, update, func
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.database.models import Ticket, TicketMessage, TicketStatus, User, SupportAuditLog


class TicketCRUD:
    """CRUD operations for working with tickets"""
    
    @staticmethod
    async def create_ticket(
        db: AsyncSession,
        user_id: int,
        title: str,
        message_text: str,
        priority: str = "normal",
        *,
        media_type: Optional[str] = None,
        media_file_id: Optional[str] = None,
        media_caption: Optional[str] = None,
    ) -> Ticket:
        """Create new ticket with first message"""
        ticket = Ticket(
            user_id=user_id,
            title=title,
            status=TicketStatus.OPEN.value,
            priority=priority
        )
        db.add(ticket)
        await db.flush()  # Get ticket ID
        
        # Create first message
        message = TicketMessage(
            ticket_id=ticket.id,
            user_id=user_id,
            message_text=message_text,
            is_from_admin=False,
            has_media=bool(media_type and media_file_id),
            media_type=media_type,
            media_file_id=media_file_id,
            media_caption=media_caption,
        )
        db.add(message)
        
        await db.commit()
        await db.refresh(ticket)
        return ticket
    
    @staticmethod
    async def get_ticket_by_id(
        db: AsyncSession,
        ticket_id: int,
        load_messages: bool = True,
        load_user: bool = False
    ) -> Optional[Ticket]:
        """Get ticket by ID"""
        query = select(Ticket).where(Ticket.id == ticket_id)
        
        if load_user:
            query = query.options(selectinload(Ticket.user))
        
        if load_messages:
            query = query.options(selectinload(Ticket.messages))
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_tickets(
        db: AsyncSession,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Ticket]:
        """Get user tickets"""
        query = select(Ticket).where(Ticket.user_id == user_id)
        
        if status:
            query = query.where(Ticket.status == status)
        
        query = query.order_by(desc(Ticket.updated_at)).offset(offset).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def count_user_tickets_by_statuses(
        db: AsyncSession,
        user_id: int,
        statuses: List[str]
    ) -> int:
        """Count number of user tickets by status list"""
        query = select(func.count()).select_from(Ticket).where(Ticket.user_id == user_id)
        if statuses:
            query = query.where(Ticket.status.in_(statuses))
        result = await db.execute(query)
        return int(result.scalar() or 0)

    @staticmethod
    async def get_user_tickets_by_statuses(
        db: AsyncSession,
        user_id: int,
        statuses: List[str],
        limit: int = 20,
        offset: int = 0
    ) -> List[Ticket]:
        """Get user tickets by status list with pagination"""
        query = (
            select(Ticket)
            .where(Ticket.user_id == user_id)
            .order_by(desc(Ticket.updated_at))
            .offset(offset)
            .limit(limit)
        )
        if statuses:
            query = query.where(Ticket.status.in_(statuses))
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def user_has_active_ticket(
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """Check if user has active (not closed) ticket"""
        query = (
            select(Ticket.id)
            .where(
                Ticket.user_id == user_id,
                Ticket.status.in_([TicketStatus.OPEN.value, TicketStatus.ANSWERED.value])
            )
            .limit(1)
        )
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def is_user_globally_blocked(
        db: AsyncSession,
        user_id: int
    ) -> Optional[datetime]:
        """Check if user is blocked for creating/replying to any ticket.
        Returns block end date if active, or None.
        """
        query = select(Ticket).where(
            Ticket.user_id == user_id,
            or_(Ticket.user_reply_block_permanent == True, Ticket.user_reply_block_until.isnot(None))
        ).order_by(desc(Ticket.updated_at)).limit(10)
        result = await db.execute(query)
        tickets = result.scalars().all()
        if not tickets:
            return None
        from datetime import datetime
        # If there is permanent block in any ticket — block is active without term
        for t in tickets:
            if t.user_reply_block_permanent:
                return datetime.max
        # Otherwise find maximum block term, if it's in the future
        future_until = [t.user_reply_block_until for t in tickets if t.user_reply_block_until]
        if not future_until:
            return None
        max_until = max(future_until)
        return max_until if max_until > datetime.utcnow() else None
    
    @staticmethod
    async def get_all_tickets(
        db: AsyncSession,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Ticket]:
        """Get all tickets (for admins)"""
        query = select(Ticket).options(selectinload(Ticket.user))
        
        conditions = []
        if status:
            conditions.append(Ticket.status == status)
        if priority:
            conditions.append(Ticket.priority == priority)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(desc(Ticket.updated_at)).offset(offset).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_tickets_by_statuses(
        db: AsyncSession,
        statuses: List[str],
        limit: int = 50,
        offset: int = 0
    ) -> List[Ticket]:
        query = select(Ticket).options(selectinload(Ticket.user))
        if statuses:
            query = query.where(Ticket.status.in_(statuses))
        query = query.order_by(desc(Ticket.updated_at)).offset(offset).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def count_tickets(
        db: AsyncSession,
        status: Optional[str] = None
    ) -> int:
        query = select(func.count()).select_from(Ticket)
        if status:
            query = query.where(Ticket.status == status)
        result = await db.execute(query)
        return int(result.scalar() or 0)

    @staticmethod
    async def count_tickets_by_statuses(
        db: AsyncSession,
        statuses: List[str]
    ) -> int:
        query = select(func.count()).select_from(Ticket)
        if statuses:
            query = query.where(Ticket.status.in_(statuses))
        result = await db.execute(query)
        return int(result.scalar() or 0)
    
    @staticmethod
    async def update_ticket_status(
        db: AsyncSession,
        ticket_id: int,
        status: str,
        closed_at: Optional[datetime] = None
    ) -> bool:
        """Update ticket status"""
        ticket = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=False)
        if not ticket:
            return False
        
        ticket.status = status
        ticket.updated_at = datetime.utcnow()
        
        if status == TicketStatus.CLOSED.value and closed_at:
            ticket.closed_at = closed_at
        
        await db.commit()
        return True

    @staticmethod
    async def set_user_reply_block(
        db: AsyncSession,
        ticket_id: int,
        permanent: bool,
        until: Optional[datetime]
    ) -> bool:
        ticket = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=False)
        if not ticket:
            return False
        ticket.user_reply_block_permanent = bool(permanent)
        ticket.user_reply_block_until = until
        ticket.updated_at = datetime.utcnow()
        await db.commit()
        return True
    
    @staticmethod
    async def close_ticket(
        db: AsyncSession,
        ticket_id: int
    ) -> bool:
        """Close ticket"""
        return await TicketCRUD.update_ticket_status(
            db, ticket_id, TicketStatus.CLOSED.value, datetime.utcnow()
        )

    @staticmethod
    async def close_all_open_tickets(
        db: AsyncSession,
    ) -> List[int]:
        """Close all open tickets. Returns list of closed ticket IDs."""
        open_statuses = [TicketStatus.OPEN.value, TicketStatus.ANSWERED.value]
        result = await db.execute(
            select(Ticket.id).where(Ticket.status.in_(open_statuses))
        )
        ticket_ids = result.scalars().all()

        if not ticket_ids:
            return []

        now = datetime.utcnow()
        await db.execute(
            update(Ticket)
            .where(Ticket.id.in_(ticket_ids))
            .values(status=TicketStatus.CLOSED.value, closed_at=now, updated_at=now)
        )
        await db.commit()

        return ticket_ids

    @staticmethod
    async def add_support_audit(
        db: AsyncSession,
        *,
        actor_user_id: Optional[int],
        actor_telegram_id: int,
        is_moderator: bool,
        action: str,
        ticket_id: Optional[int] = None,
        target_user_id: Optional[int] = None,
        details: Optional[dict] = None,
    ) -> None:
        try:
            log = SupportAuditLog(
                actor_user_id=actor_user_id,
                actor_telegram_id=actor_telegram_id,
                is_moderator=bool(is_moderator),
                action=action,
                ticket_id=ticket_id,
                target_user_id=target_user_id,
                details=details or {},
            )
            db.add(log)
            await db.commit()
        except Exception:
            await db.rollback()
            # don't interfere with main logic
            pass

    @staticmethod
    async def list_support_audit(
        db: AsyncSession,
        *,
        limit: int = 50,
        offset: int = 0,
        action: Optional[str] = None,
    ) -> List[SupportAuditLog]:
        from sqlalchemy import select, desc

        query = select(SupportAuditLog).order_by(desc(SupportAuditLog.created_at))

        if action:
            query = query.where(SupportAuditLog.action == action)

        result = await db.execute(query.offset(offset).limit(limit))
        return result.scalars().all()

    @staticmethod
    async def count_support_audit(db: AsyncSession, action: Optional[str] = None) -> int:
        from sqlalchemy import select, func

        query = select(func.count()).select_from(SupportAuditLog)

        if action:
            query = query.where(SupportAuditLog.action == action)

        result = await db.execute(query)
        return int(result.scalar() or 0)

    @staticmethod
    async def list_support_audit_actions(db: AsyncSession) -> List[str]:
        from sqlalchemy import select

        result = await db.execute(
            select(SupportAuditLog.action)
            .where(SupportAuditLog.action.isnot(None))
            .distinct()
            .order_by(SupportAuditLog.action)
        )

        return [row[0] for row in result.fetchall()]
    
    @staticmethod
    async def get_open_tickets_count(db: AsyncSession) -> int:
        """Get number of open tickets"""
        query = select(Ticket).where(Ticket.status.in_([
            TicketStatus.OPEN.value,
            TicketStatus.ANSWERED.value
        ]))
        result = await db.execute(query)
        return len(result.scalars().all())


class TicketMessageCRUD:
    """CRUD operations for working with ticket messages"""
    
    @staticmethod
    async def add_message(
        db: AsyncSession,
        ticket_id: int,
        user_id: int,
        message_text: str,
        is_from_admin: bool = False,
        media_type: Optional[str] = None,
        media_file_id: Optional[str] = None,
        media_caption: Optional[str] = None
    ) -> TicketMessage:
        """Add message to ticket"""
        message = TicketMessage(
            ticket_id=ticket_id,
            user_id=user_id,
            message_text=message_text,
            is_from_admin=is_from_admin,
            has_media=bool(media_type and media_file_id),
            media_type=media_type,
            media_file_id=media_file_id,
            media_caption=media_caption
        )
        
        db.add(message)
        
        # Update ticket status
        ticket = await TicketCRUD.get_ticket_by_id(db, ticket_id, load_messages=False)
        if ticket:
            # If ticket is closed, prevent status change when user sends message
            if not is_from_admin and ticket.status == TicketStatus.CLOSED.value:
                return message
            if is_from_admin:
                # Admin replied - ticket answered
                ticket.status = TicketStatus.ANSWERED.value
            else:
                # User replied - ticket opened
                ticket.status = TicketStatus.OPEN.value
                # Reset last SLA reminder mark to remind again from new message time
                try:
                    from sqlalchemy import inspect as sa_inspect
                    # if column exists in model
                    if hasattr(ticket, 'last_sla_reminder_at'):
                        ticket.last_sla_reminder_at = None
                except Exception:
                    pass
            
            ticket.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(message)
        return message
    
    @staticmethod
    async def get_ticket_messages(
        db: AsyncSession,
        ticket_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[TicketMessage]:
        """Get ticket messages"""
        query = (
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at)
            .offset(offset)
            .limit(limit)
        )
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_last_message(
        db: AsyncSession,
        ticket_id: int
    ) -> Optional[TicketMessage]:
        """Get last message in ticket"""
        query = (
            select(TicketMessage)
            .where(TicketMessage.ticket_id == ticket_id)
            .order_by(desc(TicketMessage.created_at))
            .limit(1)
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
