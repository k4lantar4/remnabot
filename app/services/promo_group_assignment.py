import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.transaction import get_user_total_spent_kopeks
from app.database.models import PromoGroup, User
from app.services.admin_notification_service import AdminNotificationService

logger = logging.getLogger(__name__)


async def _notify_admins_about_auto_assignment(
    db: AsyncSession,
    user: User,
    old_group: Optional[PromoGroup],
    new_group: PromoGroup,
    total_spent_kopeks: int,
):
    if not getattr(settings, "ADMIN_NOTIFICATIONS_ENABLED", False):
        return

    bot_token = getattr(settings, "BOT_TOKEN", None)
    if not bot_token:
        logger.debug("BOT_TOKEN not configured — skipping promo group notification")
        return

    bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    try:
        notification_service = AdminNotificationService(bot)
        reason = (
            f"Auto-assignment for spending {settings.format_price(total_spent_kopeks)}"
            if hasattr(settings, "format_price")
            else f"Auto-assignment for spending {total_spent_kopeks / 100:.2f}₽"
        )
        await notification_service.send_user_promo_group_change_notification(
            db,
            user,
            old_group,
            new_group,
            reason=reason,
            initiator=None,
            automatic=True,
        )
    except Exception as exc:
        logger.error(
            "Error sending auto-assignment promo group notification for user %s: %s",
            user.telegram_id,
            exc,
        )
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass


async def _get_best_group_for_spending(
    db: AsyncSession,
    total_spent_kopeks: int,
    min_threshold_kopeks: int = 0,
) -> Optional[PromoGroup]:
    if total_spent_kopeks <= 0:
        return None

    result = await db.execute(
        select(PromoGroup)
        .where(PromoGroup.auto_assign_total_spent_kopeks.is_not(None))
        .where(PromoGroup.auto_assign_total_spent_kopeks > 0)
        .order_by(PromoGroup.auto_assign_total_spent_kopeks.desc(), PromoGroup.id.desc())
    )
    groups = result.scalars().all()

    for group in groups:
        threshold = group.auto_assign_total_spent_kopeks or 0
        if (
            threshold
            and total_spent_kopeks >= threshold
            and threshold > min_threshold_kopeks
        ):
            return group

    return None


async def maybe_assign_promo_group_by_total_spent(
    db: AsyncSession,
    user_id: int,
) -> Optional[PromoGroup]:
    from app.database.crud.user_promo_group import (
        add_user_to_promo_group,
        has_user_promo_group,
        sync_user_primary_promo_group,
    )

    user = await db.get(User, user_id)
    if not user:
        logger.debug("Failed to find user %s for auto promo group assignment", user_id)
        return None

    # Get current primary promo group
    old_group = user.get_primary_promo_group()

    total_spent = await get_user_total_spent_kopeks(db, user_id)
    if total_spent <= 0:
        return None

    previous_threshold = user.auto_promo_group_threshold_kopeks or 0

    target_group = await _get_best_group_for_spending(
        db,
        total_spent,
        min_threshold_kopeks=previous_threshold,
    )
    if not target_group:
        return None

    try:
        target_threshold = target_group.auto_assign_total_spent_kopeks or 0

        if target_threshold <= previous_threshold:
            logger.debug(
                "Promo group threshold '%s' (%s) does not exceed previously assigned (%s) for user %s",
                target_group.name,
                target_threshold,
                previous_threshold,
                user.telegram_id,
            )
            return None

        # Check if user already has this group
        already_has_group = await has_user_promo_group(db, user_id, target_group.id)

        if user.auto_promo_group_assigned and already_has_group:
            logger.debug(
                "User %s already has promo group '%s', re-assignment not required",
                user.telegram_id,
                target_group.name,
            )
            await sync_user_primary_promo_group(db, user_id)
            if target_threshold > previous_threshold:
                user.auto_promo_group_threshold_kopeks = target_threshold
                user.updated_at = datetime.utcnow()
                await db.commit()
                await db.refresh(user)
            return target_group

        user.auto_promo_group_assigned = True
        user.auto_promo_group_threshold_kopeks = target_threshold
        user.updated_at = datetime.utcnow()

        if not already_has_group:
            # Add new promo group to existing ones
            await add_user_to_promo_group(db, user_id, target_group.id, assigned_by="auto")
            logger.info(
                "Promo group '%s' added to user %s for spending %s ₽",
                target_group.name,
                user.telegram_id,
                total_spent / 100,
            )
        else:
            logger.info(
                "User %s already has promo group '%s', marking auto-assignment",
                user.telegram_id,
                target_group.name,
            )

        await db.commit()
        await db.refresh(user)

        if not already_has_group:
            await _notify_admins_about_auto_assignment(
                db,
                user,
                old_group,
                target_group,
                total_spent,
            )

        return target_group
    except Exception as exc:
        logger.error(
            "Error auto-assigning promo group to user %s: %s",
            user_id,
            exc,
        )
        await db.rollback()
        return None
