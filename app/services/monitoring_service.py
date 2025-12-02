import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.enums import ChatMemberStatus
from aiogram.types import FSInputFile
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database.database import get_db
from app.database.crud.discount_offer import (
    deactivate_expired_offers,
    get_latest_claimed_offer_for_user,
    upsert_discount_offer,
)
from app.database.crud.promo_offer_log import log_promo_offer_action
from app.database.crud.notification import (
    clear_notification_by_type,
    notification_sent,
    record_notification,
)
from app.database.crud.subscription import (
    deactivate_subscription,
    extend_subscription,
    get_expired_subscriptions,
    get_expiring_subscriptions,
    get_subscriptions_for_autopay,
)
from app.database.crud.user import (
    delete_user,
    get_inactive_users,
    get_user_by_id,
    subtract_user_balance,
    cleanup_expired_promo_offer_discounts,
)
from app.utils.timezone import format_local_datetime
from app.utils.subscription_utils import (
    resolve_hwid_device_limit_for_payload,
)
from app.database.models import (
    MonitoringLog,
    SubscriptionStatus,
    Subscription,
    User,
    Ticket,
    TicketStatus,
    UserPromoGroup,
)
from app.localization.texts import get_texts
from app.services.notification_settings_service import NotificationSettingsService
from app.services.payment_service import PaymentService
from app.services.subscription_service import SubscriptionService
from app.services.promo_offer_service import promo_offer_service
from app.utils.pricing_utils import apply_percentage_discount
from app.utils.miniapp_buttons import build_miniapp_or_callback_button

from app.external.remnawave_api import (
    RemnaWaveAPIError,
    RemnaWaveUser,
    TrafficLimitStrategy,
    UserStatus,
)

logger = logging.getLogger(__name__)


LOGO_PATH = Path(settings.LOGO_FILE)


class MonitoringService:
    
    def __init__(self, bot=None):
        self.is_running = False
        self.subscription_service = SubscriptionService()
        self.payment_service = PaymentService()
        self.bot = bot
        self._notified_users: Set[str] = set()
        self._last_cleanup = datetime.utcnow()
        self._sla_task = None

    async def _send_message_with_logo(
        self,
        chat_id: int,
        text: str,
        reply_markup=None,
        parse_mode: Optional[str] = "HTML",
    ):
        """Sends a message, adding logo if necessary."""
        if not self.bot:
            raise RuntimeError("Bot instance is not available")

        if (
            settings.ENABLE_LOGO_MODE
            and LOGO_PATH.exists()
            and (text is None or len(text) <= 1000)
        ):
            try:
                return await self.bot.send_photo(
                    chat_id=chat_id,
                    photo=FSInputFile(LOGO_PATH),
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                )
            except TelegramBadRequest as exc:
                logger.warning(
                    "Failed to send message with logo to user %s: %s. "
                    "Sending text message instead.",
                    chat_id,
                    exc,
                )

        return await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    @staticmethod
    def _is_unreachable_error(error: TelegramBadRequest) -> bool:
        message = str(error).lower()
        unreachable_markers = (
            "chat not found",
            "user is deactivated",
            "bot was blocked by the user",
            "bot can't initiate conversation",
            "can't initiate conversation",
            "user not found",
            "peer id invalid",
        )
        return any(marker in message for marker in unreachable_markers)

    def _handle_unreachable_user(self, user: User, error: Exception, context: str) -> bool:
        if isinstance(error, TelegramForbiddenError):
            logger.warning(
                "⚠️ User %s unavailable (%s): bot blocked",
                user.telegram_id,
                context,
            )
            return True

        if isinstance(error, TelegramBadRequest) and self._is_unreachable_error(error):
            logger.warning(
                "⚠️ User %s unavailable (%s): %s",
                user.telegram_id,
                context,
                error,
            )
            return True

        return False
    
    async def start_monitoring(self):
        if self.is_running:
            logger.warning("Monitoring already running")
            return
        
        self.is_running = True
        logger.info("🔄 Starting monitoring service")
        # Start dedicated SLA loop with its own interval for timely 5-min checks
        try:
            if not self._sla_task or self._sla_task.done():
                self._sla_task = asyncio.create_task(self._sla_loop())
        except Exception as e:
            logger.error(f"Failed to start SLA monitoring: {e}")
        
        while self.is_running:
            try:
                await self._monitoring_cycle()
                await asyncio.sleep(settings.MONITORING_INTERVAL * 60) 
                
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")
                await asyncio.sleep(60) 
    
    def stop_monitoring(self):
        self.is_running = False
        logger.info("ℹ️ Monitoring stopped")
        try:
            if self._sla_task and not self._sla_task.done():
                self._sla_task.cancel()
        except Exception:
            pass
    
    async def _monitoring_cycle(self):
        async for db in get_db():
            try:
                await self._cleanup_notification_cache()

                expired_offers = await deactivate_expired_offers(db)
                if expired_offers:
                    logger.info(f"🧹 Deactivated {expired_offers} expired discount offers")

                expired_active_discounts = await cleanup_expired_promo_offer_discounts(db)
                if expired_active_discounts:
                    logger.info(
                        "🧹 Reset %s active promo offer discounts with expired terms",
                        expired_active_discounts,
                    )

                cleaned_test_access = await promo_offer_service.cleanup_expired_test_access(db)
                if cleaned_test_access:
                    logger.info(f"🧹 Revoked {cleaned_test_access} expired test access to squads")

                await self._check_expired_subscriptions(db)
                await self._check_expiring_subscriptions(db)
                await self._check_trial_expiring_soon(db)
                await self._check_trial_inactivity_notifications(db)
                await self._check_trial_channel_subscriptions(db)
                await self._check_expired_subscription_followups(db)
                await self._process_autopayments(db)
                await self._cleanup_inactive_users(db)
                await self._sync_with_remnawave(db)
                
                await self._log_monitoring_event(
                    db, "monitoring_cycle_completed", 
                    "Monitoring cycle completed successfully", 
                    {"timestamp": datetime.utcnow().isoformat()}
                )
                
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                await self._log_monitoring_event(
                    db, "monitoring_cycle_error", 
                    f"Error in monitoring cycle: {str(e)}", 
                    {"error": str(e)},
                    is_success=False
                )
            finally:
                break 
    
    async def _cleanup_notification_cache(self):
        current_time = datetime.utcnow()
        
        if (current_time - self._last_cleanup).total_seconds() >= 3600:
            old_count = len(self._notified_users)
            self._notified_users.clear()
            self._last_cleanup = current_time
            logger.info(f"🧹 Cleared notification cache ({old_count} entries)")
    
    async def _check_expired_subscriptions(self, db: AsyncSession):
        try:
            expired_subscriptions = await get_expired_subscriptions(db)
            
            for subscription in expired_subscriptions:
                from app.database.crud.subscription import expire_subscription
                await expire_subscription(db, subscription)
                
                user = await get_user_by_id(db, subscription.user_id)
                if user and self.bot:
                    await self._send_subscription_expired_notification(user)
                
                logger.info(f"🔴 Subscription for user {subscription.user_id} expired and status changed to 'expired'")
            
            if expired_subscriptions:
                await self._log_monitoring_event(
                    db, "expired_subscriptions_processed",
                    f"Processed {len(expired_subscriptions)} expired subscriptions",
                    {"count": len(expired_subscriptions)}
                )
                
        except Exception as e:
            logger.error(f"Error checking expired subscriptions: {e}")

    async def update_remnawave_user(
        self,
        db: AsyncSession,
        subscription: Subscription
    ) -> Optional[RemnaWaveUser]:
        
        try:
            user = await get_user_by_id(db, subscription.user_id)
            if not user or not user.remnawave_uuid:
                logger.error(f"RemnaWave UUID not found for user {subscription.user_id}")
                return None
            
            current_time = datetime.utcnow()
            is_active = (subscription.status == SubscriptionStatus.ACTIVE.value and 
                        subscription.end_date > current_time)
            
            if (subscription.status == SubscriptionStatus.ACTIVE.value and 
                subscription.end_date <= current_time):
                subscription.status = SubscriptionStatus.EXPIRED.value
                await db.commit()
                is_active = False
                logger.info(f"📝 Subscription {subscription.id} status updated to 'expired'")
            
            if not self.subscription_service.is_configured:
                logger.warning(
                    "RemnaWave API not configured. Skipping user update %s",
                    subscription.user_id,
                )
                return None

            async with self.subscription_service.get_api_client() as api:
                hwid_limit = resolve_hwid_device_limit_for_payload(subscription)

                update_kwargs = dict(
                    uuid=user.remnawave_uuid,
                    status=UserStatus.ACTIVE if is_active else UserStatus.EXPIRED,
                    expire_at=subscription.end_date,
                    traffic_limit_bytes=self._gb_to_bytes(subscription.traffic_limit_gb),
                    traffic_limit_strategy=TrafficLimitStrategy.MONTH,
                    description=settings.format_remnawave_user_description(
                        full_name=user.full_name,
                        username=user.username,
                        telegram_id=user.telegram_id
                    ),
                    active_internal_squads=subscription.connected_squads,
                )

                if hwid_limit is not None:
                    update_kwargs['hwid_device_limit'] = hwid_limit

                updated_user = await api.update_user(**update_kwargs)
                
                subscription.subscription_url = updated_user.subscription_url
                subscription.subscription_crypto_link = updated_user.happ_crypto_link
                await db.commit()
                
                status_text = "active" if is_active else "expired"
                logger.info(f"✅ Updated RemnaWave user {user.remnawave_uuid} with status {status_text}")
                return updated_user
                
        except RemnaWaveAPIError as e:
            logger.error(f"Ошибка обновления RemnaWave пользователя: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка обновления RemnaWave пользователя: {e}")
            return None
    
    async def _check_expiring_subscriptions(self, db: AsyncSession):
        try:
            warning_days = settings.get_autopay_warning_days()
            all_processed_users = set() 
            
            for days in warning_days:
                expiring_subscriptions = await self._get_expiring_paid_subscriptions(db, days)
                sent_count = 0
                
                for subscription in expiring_subscriptions:
                    user = await get_user_by_id(db, subscription.user_id)
                    if not user:
                        continue

                    user_key = f"user_{user.telegram_id}_today"

                    if (await notification_sent(db, user.id, subscription.id, "expiring", days) or
                        user_key in all_processed_users):
                        logger.debug(f"🔄 Skipping duplicate for user {user.telegram_id} for {days} days")
                        continue

                    should_send = True
                    for other_days in warning_days:
                        if other_days < days:
                            other_subs = await self._get_expiring_paid_subscriptions(db, other_days)
                            if any(s.user_id == user.id for s in other_subs):
                                should_send = False
                                logger.debug(f"🎯 Skipping {days} day notification for user {user.telegram_id}, more urgent {other_days} day notification exists")
                                break

                    if not should_send:
                        continue

                    if self.bot:
                        success = await self._send_subscription_expiring_notification(user, subscription, days)
                        if success:
                            await record_notification(db, user.id, subscription.id, "expiring", days)
                            all_processed_users.add(user_key)
                            sent_count += 1
                            logger.info(f"✅ Sent subscription expiration notification to user {user.telegram_id} for {days} days")
                        else:
                            logger.warning(f"❌ Failed to send notification to user {user.telegram_id}")
                
                if sent_count > 0:
                    await self._log_monitoring_event(
                        db, "expiring_notifications_sent",
                        f"Sent {sent_count} expiration notifications for {days} days",
                        {"days": days, "count": sent_count}
                    )
                    
        except Exception as e:
            logger.error(f"Error checking expiring subscriptions: {e}")
    
    async def _check_trial_expiring_soon(self, db: AsyncSession):
        try:
            threshold_time = datetime.utcnow() + timedelta(hours=2)

            result = await db.execute(
                select(Subscription)
                .options(
                    selectinload(Subscription.user).selectinload(User.promo_group),
                    selectinload(Subscription.user)
                    .selectinload(User.user_promo_groups)
                    .selectinload(UserPromoGroup.promo_group),
                )
                .where(
                    and_(
                        Subscription.status == SubscriptionStatus.ACTIVE.value,
                        Subscription.is_trial == True,
                        Subscription.end_date <= threshold_time,
                        Subscription.end_date > datetime.utcnow()
                    )
                )
            )
            trial_expiring = result.scalars().all()
            
            for subscription in trial_expiring:
                user = subscription.user
                if not user:
                    continue

                if await notification_sent(db, user.id, subscription.id, "trial_2h"):
                    continue

                if self.bot:
                    success = await self._send_trial_ending_notification(user, subscription)
                    if success:
                        await record_notification(db, user.id, subscription.id, "trial_2h")
                        logger.info(f"🎁 Sent trial subscription ending notification to user {user.telegram_id} (2 hours remaining)")
            
            if trial_expiring:
                await self._log_monitoring_event(
                    db, "trial_expiring_notifications_sent",
                    f"Sent {len(trial_expiring)} trial subscription ending notifications",
                    {"count": len(trial_expiring)}
                )
                
        except Exception as e:
            logger.error(f"Error checking expiring trial subscriptions: {e}")

    async def _check_trial_inactivity_notifications(self, db: AsyncSession):
        if not NotificationSettingsService.are_notifications_globally_enabled():
            return
        if not self.bot:
            return

        try:
            now = datetime.utcnow()
            one_hour_ago = now - timedelta(hours=1)

            result = await db.execute(
                select(Subscription)
                .options(selectinload(Subscription.user))
                .where(
                    and_(
                        Subscription.status == SubscriptionStatus.ACTIVE.value,
                        Subscription.is_trial == True,
                        Subscription.start_date.isnot(None),
                        Subscription.start_date <= one_hour_ago,
                        Subscription.end_date > now,
                    )
                )
            )

            subscriptions = result.scalars().all()
            sent_1h = 0
            sent_24h = 0

            for subscription in subscriptions:
                user = subscription.user
                if not user:
                    continue

                if (subscription.traffic_used_gb or 0) > 0:
                    continue

                start_date = subscription.start_date
                if not start_date:
                    continue

                time_since_start = now - start_date

                if (NotificationSettingsService.is_trial_inactive_1h_enabled()
                        and timedelta(hours=1) <= time_since_start < timedelta(hours=24)):
                    if not await notification_sent(db, user.id, subscription.id, "trial_inactive_1h"):
                        success = await self._send_trial_inactive_notification(user, subscription, 1)
                        if success:
                            await record_notification(db, user.id, subscription.id, "trial_inactive_1h")
                            sent_1h += 1

                if NotificationSettingsService.is_trial_inactive_24h_enabled() and time_since_start >= timedelta(hours=24):
                    if not await notification_sent(db, user.id, subscription.id, "trial_inactive_24h"):
                        success = await self._send_trial_inactive_notification(user, subscription, 24)
                        if success:
                            await record_notification(db, user.id, subscription.id, "trial_inactive_24h")
                            sent_24h += 1

            if sent_1h or sent_24h:
                await self._log_monitoring_event(
                    db,
                    "trial_inactivity_notifications",
                    f"Sent {sent_1h} notifications after 1 hour and {sent_24h} after 24 hours",
                    {"sent_1h": sent_1h, "sent_24h": sent_24h},
                )

        except Exception as e:
            logger.error(f"Error checking inactive trial subscriptions: {e}")

    async def _check_trial_channel_subscriptions(self, db: AsyncSession):
        if not settings.CHANNEL_IS_REQUIRED_SUB:
            return

        channel_id = settings.CHANNEL_SUB_ID
        if not channel_id:
            return

        if not self.bot:
            logger.debug("⚠️ Skipping channel subscription check — bot unavailable")
            return

        try:
            now = datetime.utcnow()
            notifications_allowed = (
                NotificationSettingsService.are_notifications_globally_enabled()
                and NotificationSettingsService.is_trial_channel_unsubscribed_enabled()
            )
            result = await db.execute(
                select(Subscription)
                .options(selectinload(Subscription.user))
                .where(
                    and_(
                        Subscription.is_trial.is_(True),
                        Subscription.end_date > now,
                        Subscription.status.in_(
                            [
                                SubscriptionStatus.ACTIVE.value,
                                SubscriptionStatus.DISABLED.value,
                            ]
                        ),
                    )
                )
            )

            subscriptions = result.scalars().all()
            if not subscriptions:
                return

            disabled_count = 0
            restored_count = 0

            for subscription in subscriptions:
                user = subscription.user
                if not user or not user.telegram_id:
                    continue

                try:
                    member = await self.bot.get_chat_member(channel_id, user.telegram_id)
                    member_status = member.status
                    is_member = member_status in (
                        ChatMemberStatus.MEMBER,
                        ChatMemberStatus.ADMINISTRATOR,
                        ChatMemberStatus.CREATOR,
                    )
                except TelegramForbiddenError as error:
                    logger.error(
                        "❌ Failed to check user %s subscription to channel %s: bot blocked (%s)",
                        user.telegram_id,
                        channel_id,
                        error,
                    )
                    continue
                except TelegramBadRequest as error:
                    logger.error(
                        "❌ Telegram error checking user %s subscription: %s",
                        user.telegram_id,
                        error,
                    )
                    continue
                except Exception as error:
                    logger.error(
                        "❌ Unexpected error checking user %s subscription: %s",
                        user.telegram_id,
                        error,
                    )
                    continue

                if (
                    subscription.status == SubscriptionStatus.ACTIVE.value
                    and subscription.is_trial
                    and not is_member
                ):
                    subscription = await deactivate_subscription(db, subscription)
                    disabled_count += 1
                    logger.info(
                        "🚫 Trial subscription for user %s (ID %s) disabled due to channel unsubscription",
                        user.telegram_id,
                        subscription.id,
                    )

                    if user.remnawave_uuid:
                        try:
                            await self.subscription_service.disable_remnawave_user(user.remnawave_uuid)
                        except Exception as api_error:
                            logger.error(
                                "❌ Failed to disable RemnaWave user %s: %s",
                                user.remnawave_uuid,
                                api_error,
                            )

                    if notifications_allowed:
                        if not await notification_sent(
                            db,
                            user.id,
                            subscription.id,
                            "trial_channel_unsubscribed",
                        ):
                            sent = await self._send_trial_channel_unsubscribed_notification(user)
                            if sent:
                                await record_notification(
                                    db,
                                    user.id,
                                    subscription.id,
                                    "trial_channel_unsubscribed",
                                )
                elif (
                    subscription.status == SubscriptionStatus.DISABLED.value
                    and subscription.is_trial
                    and is_member
                ):
                    subscription.status = SubscriptionStatus.ACTIVE.value
                    subscription.updated_at = datetime.utcnow()
                    await db.commit()
                    await db.refresh(subscription)
                    restored_count += 1

                    logger.info(
                        "✅ Trial subscription for user %s (ID %s) restored after resubscribing to channel",
                        user.telegram_id,
                        subscription.id,
                    )

                    try:
                        if user.remnawave_uuid:
                            await self.subscription_service.update_remnawave_user(db, subscription)
                        else:
                            await self.subscription_service.create_remnawave_user(db, subscription)
                    except Exception as api_error:
                        logger.error(
                            "❌ Failed to update RemnaWave user %s: %s",
                            user.telegram_id,
                            api_error,
                        )

                    await clear_notification_by_type(
                        db,
                        subscription.id,
                        "trial_channel_unsubscribed",
                    )

            if disabled_count or restored_count:
                await self._log_monitoring_event(
                    db,
                    "trial_channel_subscription_check",
                    (
                        "Checked {total} trial subscriptions: disabled {disabled}, "
                        "restored {restored}"
                    ).format(
                        total=len(subscriptions),
                        disabled=disabled_count,
                        restored=restored_count,
                    ),
                    {
                        "checked": len(subscriptions),
                        "disabled": disabled_count,
                        "restored": restored_count,
                    },
                )

        except Exception as error:
            logger.error(f"Error checking channel subscription for trial users: {error}")

    async def _check_expired_subscription_followups(self, db: AsyncSession):
        if not NotificationSettingsService.are_notifications_globally_enabled():
            return
        if not self.bot:
            return

        try:
            now = datetime.utcnow()

            result = await db.execute(
                select(Subscription)
                .options(selectinload(Subscription.user))
                .where(
                    and_(
                        Subscription.is_trial == False,
                        Subscription.end_date <= now,
                    )
                )
            )

            subscriptions = result.scalars().all()
            sent_day1 = 0
            sent_wave2 = 0
            sent_wave3 = 0

            for subscription in subscriptions:
                user = subscription.user
                if not user:
                    continue

                if subscription.end_date is None:
                    continue

                time_since_end = now - subscription.end_date
                if time_since_end.total_seconds() < 0:
                    continue

                days_since = time_since_end.total_seconds() / 86400

                # Day 1 reminder
                if NotificationSettingsService.is_expired_1d_enabled() and 1 <= days_since < 2:
                    if not await notification_sent(db, user.id, subscription.id, "expired_1d"):
                        success = await self._send_expired_day1_notification(user, subscription)
                        if success:
                            await record_notification(db, user.id, subscription.id, "expired_1d")
                            sent_day1 += 1

                # Second wave (2-3 days) discount
                if NotificationSettingsService.is_second_wave_enabled() and 2 <= days_since < 4:
                    if not await notification_sent(db, user.id, subscription.id, "expired_discount_wave2"):
                        percent = NotificationSettingsService.get_second_wave_discount_percent()
                        valid_hours = NotificationSettingsService.get_second_wave_valid_hours()
                        offer = await upsert_discount_offer(
                            db,
                            user_id=user.id,
                            subscription_id=subscription.id,
                            notification_type="expired_discount_wave2",
                            discount_percent=percent,
                            bonus_amount_kopeks=0,
                            valid_hours=valid_hours,
                            effect_type="percent_discount",
                        )
                        success = await self._send_expired_discount_notification(
                            user,
                            subscription,
                            percent,
                            offer.expires_at,
                            offer.id,
                            "second",
                        )
                        if success:
                            await record_notification(db, user.id, subscription.id, "expired_discount_wave2")
                            sent_wave2 += 1

                # Third wave (N days) discount
                if NotificationSettingsService.is_third_wave_enabled():
                    trigger_days = NotificationSettingsService.get_third_wave_trigger_days()
                    if trigger_days <= days_since < trigger_days + 1:
                        if not await notification_sent(db, user.id, subscription.id, "expired_discount_wave3"):
                            percent = NotificationSettingsService.get_third_wave_discount_percent()
                            valid_hours = NotificationSettingsService.get_third_wave_valid_hours()
                            offer = await upsert_discount_offer(
                                db,
                                user_id=user.id,
                                subscription_id=subscription.id,
                                notification_type="expired_discount_wave3",
                                discount_percent=percent,
                                bonus_amount_kopeks=0,
                                valid_hours=valid_hours,
                                effect_type="percent_discount",
                            )
                            success = await self._send_expired_discount_notification(
                                user,
                                subscription,
                                percent,
                                offer.expires_at,
                                offer.id,
                                "third",
                                trigger_days=trigger_days,
                            )
                            if success:
                                await record_notification(db, user.id, subscription.id, "expired_discount_wave3")
                                sent_wave3 += 1

            if sent_day1 or sent_wave2 or sent_wave3:
                await self._log_monitoring_event(
                    db,
                    "expired_followups_sent",
                    (
                        "Follow-ups: 1d={0}, discount 2-3d={1}, discount N={2}".format(
                            sent_day1,
                            sent_wave2,
                            sent_wave3,
                        )
                    ),
                    {
                        "day1": sent_day1,
                        "wave2": sent_wave2,
                        "wave3": sent_wave3,
                    },
                )

        except Exception as e:
            logger.error(f"Error checking expired subscription reminders: {e}")

    async def _get_expiring_paid_subscriptions(self, db: AsyncSession, days_before: int) -> List[Subscription]:
        current_time = datetime.utcnow()
        threshold_date = current_time + timedelta(days=days_before)
        
        result = await db.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .where(
                and_(
                    Subscription.status == SubscriptionStatus.ACTIVE.value,
                    Subscription.is_trial == False, 
                    Subscription.end_date > current_time,
                    Subscription.end_date <= threshold_date
                )
            )
        )
        
        logger.debug(f"🔍 Searching for paid subscriptions expiring in {days_before} days")
        logger.debug(f"📅 Current time: {current_time}")
        logger.debug(f"📅 Threshold date: {threshold_date}")
        
        subscriptions = result.scalars().all()
        logger.info(f"📊 Found {len(subscriptions)} paid subscriptions for notifications")
        
        return subscriptions
    
    @staticmethod
    def _get_user_promo_offer_discount_percent(user: Optional[User]) -> int:
        if not user:
            return 0

        try:
            percent = int(getattr(user, "promo_offer_discount_percent", 0) or 0)
        except (TypeError, ValueError):
            return 0

        expires_at = getattr(user, "promo_offer_discount_expires_at", None)
        if expires_at and expires_at <= datetime.utcnow():
            return 0

        return max(0, min(100, percent))

    @staticmethod
    async def _consume_user_promo_offer_discount(db: AsyncSession, user: User) -> None:
        percent = MonitoringService._get_user_promo_offer_discount_percent(user)
        if percent <= 0:
            return

        source = getattr(user, "promo_offer_discount_source", None)
        log_payload = {
            "offer_id": None,
            "percent": percent,
            "source": source,
            "effect_type": None,
        }

        try:
            offer = await get_latest_claimed_offer_for_user(db, user.id, source)
        except Exception as lookup_error:  # pragma: no cover - defensive logging
            logger.warning(
                "Failed to resolve latest claimed promo offer for user %s: %s",
                user.id,
                lookup_error,
            )
            offer = None

        if offer:
            log_payload["offer_id"] = offer.id
            log_payload["effect_type"] = offer.effect_type
            if not log_payload["percent"] and offer.discount_percent:
                log_payload["percent"] = offer.discount_percent

        user.promo_offer_discount_percent = 0
        user.promo_offer_discount_source = None
        user.promo_offer_discount_expires_at = None
        user.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(user)

        try:
            await log_promo_offer_action(
                db,
                user_id=user.id,
                offer_id=log_payload.get("offer_id"),
                action="consumed",
                source=log_payload.get("source"),
                percent=log_payload.get("percent"),
                effect_type=log_payload.get("effect_type"),
                details={"reason": "autopay_consumed"},
            )
        except Exception as log_error:  # pragma: no cover - defensive logging
            logger.warning(
                "Failed to record promo offer autopay log for user %s: %s",
                user.id,
                log_error,
            )
            try:
                await db.rollback()
            except Exception as rollback_error:  # pragma: no cover - defensive logging
                logger.warning(
                    "Failed to rollback session after promo offer autopay log failure: %s",
                    rollback_error,
                )

    async def _process_autopayments(self, db: AsyncSession):
        try:
            current_time = datetime.utcnow()
            
            result = await db.execute(
                select(Subscription)
                .options(
                    selectinload(Subscription.user).options(
                        selectinload(User.promo_group),
                        selectinload(User.user_promo_groups).selectinload(UserPromoGroup.promo_group),
                    )
                )
                .where(
                    and_(
                        Subscription.status == SubscriptionStatus.ACTIVE.value,
                        Subscription.autopay_enabled == True,
                        Subscription.is_trial == False
                    )
                )
            )
            all_autopay_subscriptions = result.scalars().all()
            
            autopay_subscriptions = []
            for sub in all_autopay_subscriptions:
                days_before_expiry = (sub.end_date - current_time).days
                if days_before_expiry <= sub.autopay_days_before:
                    autopay_subscriptions.append(sub)
            
            processed_count = 0
            failed_count = 0
            
            for subscription in autopay_subscriptions:
                user = subscription.user
                if not user:
                    continue
                
                # Correct renewal cost calculation considering all subscription parameters
                renewal_cost = await self.subscription_service.calculate_renewal_price(
                    subscription, 30, db, user=user
                )
                promo_discount_percent = self._get_user_promo_offer_discount_percent(user)
                charge_amount = renewal_cost
                promo_discount_value = 0

                if renewal_cost > 0 and promo_discount_percent > 0:
                    charge_amount, promo_discount_value = apply_percentage_discount(
                        renewal_cost,
                        promo_discount_percent,
                    )

                autopay_key = f"autopay_{user.telegram_id}_{subscription.id}"
                if autopay_key in self._notified_users:
                    continue

                if user.balance_kopeks >= charge_amount:
                    success = await subtract_user_balance(
                        db, user, charge_amount,
                        "Subscription auto-renewal"
                    )

                    if success:
                        await extend_subscription(db, subscription, 30)
                        await self.subscription_service.update_remnawave_user(
                            db,
                            subscription,
                            reset_traffic=settings.RESET_TRAFFIC_ON_PAYMENT,
                            reset_reason="subscription auto-renewal",
                        )

                        if promo_discount_value > 0:
                            await self._consume_user_promo_offer_discount(db, user)

                        if self.bot:
                            await self._send_autopay_success_notification(user, charge_amount, 30)

                        processed_count += 1
                        self._notified_users.add(autopay_key)
                        logger.info(
                            "💳 Subscription auto-renewal for user %s successful (charged %s, discount %s%%)",
                            user.telegram_id,
                            charge_amount,
                            promo_discount_percent,
                        )
                    else:
                        failed_count += 1
                        if self.bot:
                            await self._send_autopay_failed_notification(user, user.balance_kopeks, charge_amount)
                        logger.warning(f"💳 Error charging funds for auto-renewal for user {user.telegram_id}")
                else:
                    failed_count += 1
                    if self.bot:
                        await self._send_autopay_failed_notification(user, user.balance_kopeks, charge_amount)
                    logger.warning(f"💳 Insufficient funds for auto-renewal for user {user.telegram_id}")
            
            if processed_count > 0 or failed_count > 0:
                await self._log_monitoring_event(
                    db, "autopayments_processed",
                    f"Auto-payments: successful {processed_count}, failed {failed_count}",
                    {"processed": processed_count, "failed": failed_count}
                )
                
        except Exception as e:
            logger.error(f"Error processing auto-payments: {e}")
    
    async def _send_subscription_expired_notification(self, user: User) -> bool:
        try:
            texts = get_texts(user.language)
            message = texts.get(
                "SUBSCRIPTION_EXPIRED",
                """⛔ <b>Subscription expired</b>

Your subscription has expired. To restore access, renew your subscription.

🔧 Server access is blocked until renewal.
"""
            )
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [build_miniapp_or_callback_button(text="💎 Купить подписку", callback_data="menu_buy")],
                [build_miniapp_or_callback_button(text="💳 Пополнить баланс", callback_data="balance_topup")],
            ])

            await self._send_message_with_logo(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return True

        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            if self._handle_unreachable_user(user, exc, "subscription expiration notification"):
                return True
            logger.error(
                "Ошибка Telegram API при отправке уведомления об истечении подписки пользователю %s: %s",
                user.telegram_id,
                exc,
            )
            return False
        except Exception as e:
            logger.error(
                "Ошибка отправки уведомления об истечении подписки пользователю %s: %s",
                user.telegram_id,
                e,
            )
            return False
    
    async def _send_subscription_expiring_notification(self, user: User, subscription: Subscription, days: int) -> bool:
        try:
            from app.utils.formatters import format_days_declension
            
            texts = get_texts(user.language)
            days_text = format_days_declension(days, user.language)
            
            if subscription.autopay_enabled:
                autopay_status = "✅ Enabled - subscription will renew automatically"
                action_text = f"💰 Make sure you have sufficient balance: {texts.format_price(user.balance_kopeks)}"
            else:
                autopay_status = "❌ Disabled - don't forget to renew manually!"
                action_text = "💡 Enable auto-payment or renew subscription manually"
            
            message = f"""
⚠️ <b>Subscription expires in {days_text}!</b>

Your paid subscription expires on {format_local_datetime(subscription.end_date, "%d.%m.%Y %H:%M")}.

💳 <b>Auto-payment:</b> {autopay_status}

{action_text}
"""
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [build_miniapp_or_callback_button(text="⏰ Продлить подписку", callback_data="subscription_extend")],
                [build_miniapp_or_callback_button(text="💳 Пополнить баланс", callback_data="balance_topup")],
                [build_miniapp_or_callback_button(text="📱 Моя подписка", callback_data="menu_subscription")],
            ])

            await self._send_message_with_logo(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return True

        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            if self._handle_unreachable_user(user, exc, "expiring subscription notification"):
                return True
            logger.error(
                "Ошибка Telegram API при отправке уведомления об истечении подписки пользователю %s: %s",
                user.telegram_id,
                exc,
            )
            return False
        except Exception as e:
            logger.error(
                "Ошибка отправки уведомления об истечении подписки пользователю %s: %s",
                user.telegram_id,
                e,
            )
            return False
    
    async def _send_trial_ending_notification(self, user: User, subscription: Subscription) -> bool:
        try:
            texts = get_texts(user.language)

            # Calculate minimum subscription price with minimal configuration
            from app.config import settings, PERIOD_PRICES
            from app.utils.pricing_utils import apply_percentage_discount

            # Base price for 30 days
            base_price_original = PERIOD_PRICES.get(30, settings.PRICE_30_DAYS)
            
            # Apply promo group discount for "period" category
            promo_group_discount = user.get_promo_discount("period", 30) if user else 0
            # Apply user promo discount (if any)
            user_discount_percent = self._get_user_promo_offer_discount_percent(user)
            
            # Total discount - maximum of promo group and user discount
            total_discount_percent = max(promo_group_discount, user_discount_percent)
            
            base_price, _ = apply_percentage_discount(base_price_original, total_discount_percent)

            # Add traffic price (if fixed traffic is enabled)
            if settings.is_traffic_fixed():
                traffic_price = settings.get_traffic_price(settings.get_fixed_traffic_limit())
                # Apply traffic discounts
                traffic_discount = user.get_promo_discount("traffic", 30) if user else 0
                traffic_price, _ = apply_percentage_discount(traffic_price, traffic_discount)
            else:
                traffic_price = 0  # Traffic is not fixed, price included in base

            # Add server price (assume minimum 1 server at minimum price)
            # Instead of complex DB query, use settings
            # For minimal configuration - one server with minimum price
            min_server_price = getattr(settings, 'MIN_SERVER_PRICE', 0) or 0
            if min_server_price == 0:
                # If no explicit minimum price, use base price
                # In real conditions, server price will be determined during subscription setup
                min_server_price = 0
            
            # Add device price (if more than base limit)
            # In minimal configuration - base limit, no additional devices
            device_limit = settings.DEFAULT_DEVICE_LIMIT
            additional_devices = max(0, device_limit - settings.DEFAULT_DEVICE_LIMIT)
            devices_price = additional_devices * settings.PRICE_PER_DEVICE

            # For simplicity and correct operation without DB access, calculate minimum price as:
            # base price + minimum traffic price (if fixed traffic exists)
            min_server_price = 0  # for minimal configuration with 1 server use 0 or known minimum
            
            # Try to get minimum server price from settings or use appropriate value
            # Find minimum possible price from possible server prices
            # In simplified version use base configuration: base price + traffic
            min_total_price = base_price + traffic_price

            texts = get_texts(user.language)
            message = texts.get(
                "TRIAL_SUBSCRIPTION_ENDING_2H",
                f"""🎁 <b>Trial subscription ending soon!</b>

Your trial subscription expires in 2 hours.

💎 <b>Don't want to be without VPN?</b>
Switch to a full subscription!

🔥 <b>Special offer:</b>
• 30 days for just {settings.format_price(min_total_price)}
• Unlimited traffic
• All servers available
• Speed up to 1 Gbit/s

⚡️ Complete your order before the trial period ends!
"""
            )
            
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [build_miniapp_or_callback_button(text="💎 Купить подписку", callback_data="menu_buy")],
                [build_miniapp_or_callback_button(text="💰 Пополнить баланс", callback_data="balance_topup")],
            ])

            await self._send_message_with_logo(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return True

        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            if self._handle_unreachable_user(user, exc, "trial subscription ending notification"):
                return True
            logger.error(
                "Telegram API error sending trial subscription ending notification to user %s: %s",
                user.telegram_id,
                exc,
            )
            return False
        except Exception as e:
            logger.error(
                "Error sending trial subscription ending notification to user %s: %s",
                user.telegram_id,
                e,
            )
            return False

    async def _send_trial_inactive_notification(self, user: User, subscription: Subscription, hours: int) -> bool:
        try:
            texts = get_texts(user.language)
            if hours >= 24:
                template = texts.get(
                    "TRIAL_INACTIVE_24H",
                    (
                        "⏳ <b>You haven't connected to VPN yet</b>\n\n"
                        "A day has passed since trial activation, but no traffic has been recorded."
                        "\n\nClick the button below to connect."
                    ),
                )
            else:
                template = texts.get(
                    "TRIAL_INACTIVE_1H",
                    (
                        "⏳ <b>An hour has passed, but no connection</b>\n\n"
                        "If you're having trouble starting — use the instructions."
                    ),
                )

            message = template.format(
                price=settings.format_price(settings.PRICE_30_DAYS),
                end_date=format_local_datetime(subscription.end_date, "%d.%m.%Y %H:%M"),
            )

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [build_miniapp_or_callback_button(
                    text=texts.t("CONNECT_BUTTON", "🔗 Подключиться"),
                    callback_data="subscription_connect",
                )],
                [build_miniapp_or_callback_button(
                    text=texts.t("MY_SUBSCRIPTION_BUTTON", "📱 Моя подписка"),
                    callback_data="menu_subscription",
                )],
                [InlineKeyboardButton(text=texts.t("SUPPORT_BUTTON", "🆘 Поддержка"), callback_data="menu_support")],
            ])

            await self._send_message_with_logo(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return True

        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            if self._handle_unreachable_user(user, exc, "trial inactivity notification"):
                return True
            logger.error(
                "Telegram API error sending no connection notification to user %s: %s",
                user.telegram_id,
                exc,
            )
            return False
        except Exception as e:
            logger.error(
                "Error sending no connection notification to user %s: %s",
                user.telegram_id,
                e,
            )
            return False

    async def _send_trial_channel_unsubscribed_notification(self, user: User) -> bool:
        try:
            texts = get_texts(user.language)
            template = texts.get(
                "TRIAL_CHANNEL_UNSUBSCRIBED",
                (
                    "🚫 <b>Access suspended</b>\n\n"
                    "We couldn't find your subscription to our channel, so the trial subscription has been disabled.\n\n"
                    "Subscribe to the channel and click «{check_button}» to restore access."
                ),
            )

            check_button = texts.t("CHANNEL_CHECK_BUTTON", "✅ I subscribed")
            message = template.format(check_button=check_button)

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            buttons = []
            if settings.CHANNEL_LINK:
                buttons.append(
                    [
                        InlineKeyboardButton(
                            text=texts.t("CHANNEL_SUBSCRIBE_BUTTON", "🔗 Подписаться"),
                            url=settings.CHANNEL_LINK,
                        )
                    ]
                )
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=check_button,
                        callback_data="sub_channel_check",
                    )
                ]
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            await self._send_message_with_logo(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return True

        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            if self._handle_unreachable_user(user, exc, "channel unsubscription notification"):
                return True
            logger.error(
                "Telegram API error sending channel unsubscription notification to user %s: %s",
                user.telegram_id,
                exc,
            )
            return False
        except Exception as error:
            logger.error(
                "Error sending channel unsubscription notification to user %s: %s",
                user.telegram_id,
                error,
            )
            return False

    async def _send_expired_day1_notification(self, user: User, subscription: Subscription) -> bool:
        try:
            texts = get_texts(user.language)
            template = texts.get(
                "SUBSCRIPTION_EXPIRED_1D",
                (
                    "⛔ <b>Subscription ended</b>\n\n"
                    "Access was disabled on {end_date}. Renew your subscription to return to the service."
                ),
            )
            message = template.format(
                end_date=format_local_datetime(subscription.end_date, "%d.%m.%Y %H:%M"),
                price=settings.format_price(settings.PRICE_30_DAYS),
            )

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [build_miniapp_or_callback_button(
                    text=texts.t("SUBSCRIPTION_EXTEND", "💎 Продлить подписку"),
                    callback_data="subscription_extend",
                )],
                [build_miniapp_or_callback_button(
                    text=texts.t("BALANCE_TOPUP", "💳 Пополнить баланс"),
                    callback_data="balance_topup",
                )],
                [InlineKeyboardButton(text=texts.t("SUPPORT_BUTTON", "🆘 Поддержка"), callback_data="menu_support")],
            ])

            await self._send_message_with_logo(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return True

        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            if self._handle_unreachable_user(user, exc, "expired subscription reminder"):
                return True
            logger.error(
                "Telegram API error sending expired subscription reminder to user %s: %s",
                user.telegram_id,
                exc,
            )
            return False
        except Exception as e:
            logger.error(
                "Error sending expired subscription reminder to user %s: %s",
                user.telegram_id,
                e,
            )
            return False

    async def _send_expired_discount_notification(
        self,
        user: User,
        subscription: Subscription,
        percent: int,
        expires_at: datetime,
        offer_id: int,
        wave: str,
        trigger_days: int = None,
    ) -> bool:
        try:
            texts = get_texts(user.language)

            if wave == "second":
                template = texts.get(
                    "SUBSCRIPTION_EXPIRED_SECOND_WAVE",
                    (
                        "🔥 <b>{percent}% discount on renewal</b>\n\n"
                        "Activate the offer to get an additional discount. "
                        "It stacks with your promo group and is valid until {expires_at}."
                    ),
                )
            else:
                template = texts.get(
                    "SUBSCRIPTION_EXPIRED_THIRD_WAVE",
                    (
                        "🎁 <b>Individual {percent}% discount</b>\n\n"
                        "{trigger_days} days have passed without a subscription — come back and activate an additional discount. "
                        "It stacks with the promo group and is valid until {expires_at}."
                    ),
                )

            message = template.format(
                percent=percent,
                expires_at=format_local_datetime(expires_at, "%d.%m.%Y %H:%M"),
                trigger_days=trigger_days or "",
            )

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [build_miniapp_or_callback_button(text="🎁 Получить скидку", callback_data=f"claim_discount_{offer_id}")],
                [build_miniapp_or_callback_button(
                    text=texts.t("SUBSCRIPTION_EXTEND", "💎 Продлить подписку"),
                    callback_data="subscription_extend",
                )],
                [build_miniapp_or_callback_button(
                    text=texts.t("BALANCE_TOPUP", "💳 Пополнить баланс"),
                    callback_data="balance_topup",
                )],
                [InlineKeyboardButton(text=texts.t("SUPPORT_BUTTON", "🆘 Поддержка"), callback_data="menu_support")],
            ])

            await self._send_message_with_logo(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return True

        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            if self._handle_unreachable_user(user, exc, "discount notification"):
                return True
            logger.error(
                "Telegram API error sending discount notification to user %s: %s",
                user.telegram_id,
                exc,
            )
            return False
        except Exception as e:
            logger.error(
                "Error sending discount notification to user %s: %s",
                user.telegram_id,
                e,
            )
            return False

    async def _send_autopay_success_notification(self, user: User, amount: int, days: int):
        try:
            texts = get_texts(user.language)
            message = texts.AUTOPAY_SUCCESS.format(
                days=days,
                amount=settings.format_price(amount)
            )
            await self._send_message_with_logo(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="HTML",
            )
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            if not self._handle_unreachable_user(user, exc, "successful auto-payment notification"):
                logger.error(
                    "Telegram API error sending auto-payment notification to user %s: %s",
                    user.telegram_id,
                    exc,
                )
        except Exception as e:
            logger.error(
                "Error sending auto-payment notification to user %s: %s",
                user.telegram_id,
                e,
            )

    async def _send_autopay_failed_notification(self, user: User, balance: int, required: int):
        try:
            texts = get_texts(user.language)
            message = texts.AUTOPAY_FAILED.format(
                balance=settings.format_price(balance),
                required=settings.format_price(required)
            )
            
            from aiogram.types import InlineKeyboardMarkup

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [build_miniapp_or_callback_button(text="💳 Пополнить баланс", callback_data="balance_topup")],
                [build_miniapp_or_callback_button(text="📱 Моя подписка", callback_data="menu_subscription")],
            ])
            
            await self._send_message_with_logo(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            if not self._handle_unreachable_user(user, exc, "failed auto-payment notification"):
                logger.error(
                    "Telegram API error sending failed auto-payment notification to user %s: %s",
                    user.telegram_id,
                    exc,
                )
        except Exception as e:
            logger.error(
                "Error sending failed auto-payment notification to user %s: %s",
                user.telegram_id,
                e,
            )
    
    async def _cleanup_inactive_users(self, db: AsyncSession):
        try:
            now = datetime.utcnow()
            if now.hour != 3: 
                return
            
            inactive_users = await get_inactive_users(db, settings.INACTIVE_USER_DELETE_MONTHS)
            deleted_count = 0
            
            for user in inactive_users:
                if not user.subscription or not user.subscription.is_active:
                    success = await delete_user(db, user)
                    if success:
                        deleted_count += 1
            
            if deleted_count > 0:
                await self._log_monitoring_event(
                    db, "inactive_users_cleanup",
                    f"Deleted {deleted_count} inactive users",
                    {"deleted_count": deleted_count}
                )
                logger.info(f"🗑️ Deleted {deleted_count} inactive users")
                
        except Exception as e:
            logger.error(f"Error cleaning up inactive users: {e}")
    
    async def _sync_with_remnawave(self, db: AsyncSession):
        try:
            now = datetime.utcnow()
            if now.minute != 0:
                return
            
            if not self.subscription_service.is_configured:
                logger.warning("RemnaWave API not configured. Skipping synchronization")
                return

            async with self.subscription_service.get_api_client() as api:
                system_stats = await api.get_system_stats()
                
                await self._log_monitoring_event(
                    db, "remnawave_sync",
                    "Synchronization with RemnaWave completed",
                    {"stats": system_stats}
                )
                
        except Exception as e:
            logger.error(f"Error synchronizing with RemnaWave: {e}")
            await self._log_monitoring_event(
                db, "remnawave_sync_error",
                f"Error synchronizing with RemnaWave: {str(e)}",
                {"error": str(e)},
                is_success=False
            )
    
    async def _check_ticket_sla(self, db: AsyncSession):
        try:
            # Quick guards
            # Allow runtime toggle from SupportSettingsService
            try:
                from app.services.support_settings_service import SupportSettingsService
                sla_enabled_runtime = SupportSettingsService.get_sla_enabled()
            except Exception:
                sla_enabled_runtime = getattr(settings, 'SUPPORT_TICKET_SLA_ENABLED', True)
            if not sla_enabled_runtime:
                return
            if not self.bot:
                return
            if not settings.is_admin_notifications_enabled():
                return

            from datetime import datetime, timedelta
            try:
                from app.services.support_settings_service import SupportSettingsService
                sla_minutes = max(1, int(SupportSettingsService.get_sla_minutes()))
            except Exception:
                sla_minutes = max(1, int(getattr(settings, 'SUPPORT_TICKET_SLA_MINUTES', 5)))
            cooldown_minutes = max(1, int(getattr(settings, 'SUPPORT_TICKET_SLA_REMINDER_COOLDOWN_MINUTES', 15)))
            now = datetime.utcnow()
            stale_before = now - timedelta(minutes=sla_minutes)
            cooldown_before = now - timedelta(minutes=cooldown_minutes)

            # Tickets to remind: open, no admin reply yet after user's last message (status OPEN), stale by SLA,
            # and either never reminded or cooldown passed
            result = await db.execute(
                select(Ticket)
                .options(selectinload(Ticket.user))
                .where(
                    and_(
                        Ticket.status == TicketStatus.OPEN.value,
                        Ticket.updated_at <= stale_before,
                        or_(Ticket.last_sla_reminder_at.is_(None), Ticket.last_sla_reminder_at <= cooldown_before),
                    )
                )
            )
            tickets = result.scalars().all()
            if not tickets:
                return

            from app.services.admin_notification_service import AdminNotificationService

            reminders_sent = 0
            service = AdminNotificationService(self.bot)

            for ticket in tickets:
                try:
                    waited_minutes = max(0, int((now - ticket.updated_at).total_seconds() // 60))
                    title = (ticket.title or '').strip()
                    if len(title) > 60:
                        title = title[:57] + '...'

                    # User details: name, Telegram ID and username
                    full_name = ticket.user.full_name if ticket.user else "Unknown"
                    telegram_id_display = ticket.user.telegram_id if ticket.user else "—"
                    username_display = (ticket.user.username or "not set") if ticket.user else "not set"

                    text = (
                        f"⏰ <b>Ticket response time exceeded</b>\n\n"
                        f"🆔 <b>ID:</b> <code>{ticket.id}</code>\n"
                        f"👤 <b>User:</b> {full_name}\n"
                        f"🆔 <b>Telegram ID:</b> <code>{telegram_id_display}</code>\n"
                        f"📱 <b>Username:</b> @{username_display}\n"
                        f"📝 <b>Title:</b> {title or '—'}\n"
                        f"⏱️ <b>Waiting for response:</b> {waited_minutes} min\n"
                    )

                    sent = await service.send_ticket_event_notification(text)
                    if sent:
                        ticket.last_sla_reminder_at = now
                        reminders_sent += 1
                        # commit after each to persist timestamp and avoid duplicate reminders on crash
                        await db.commit()
                except Exception as notify_error:
                    logger.error(f"Error sending SLA notification for ticket {ticket.id}: {notify_error}")

            if reminders_sent > 0:
                await self._log_monitoring_event(
                    db,
                    "ticket_sla_reminders_sent",
                    f"Sent {reminders_sent} SLA reminders for tickets",
                    {"count": reminders_sent},
                )
        except Exception as e:
            logger.error(f"Error checking ticket SLA: {e}")

    async def _sla_loop(self):
        try:
            interval_seconds = max(10, int(getattr(settings, 'SUPPORT_TICKET_SLA_CHECK_INTERVAL_SECONDS', 60)))
        except Exception:
            interval_seconds = 60
        while self.is_running:
            try:
                async for db in get_db():
                    try:
                        await self._check_ticket_sla(db)
                    finally:
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in SLA loop: {e}")
            await asyncio.sleep(interval_seconds)

    async def _log_monitoring_event(
        self,
        db: AsyncSession,
        event_type: str,
        message: str,
        data: Dict[str, Any] = None,
        is_success: bool = True
    ):
        try:
            log_entry = MonitoringLog(
                event_type=event_type,
                message=message,
                data=data or {},
                is_success=is_success
            )
            
            db.add(log_entry)
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error logging monitoring event: {e}")

    async def get_monitoring_status(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            from sqlalchemy import select, desc
            
            recent_events_result = await db.execute(
                select(MonitoringLog)
                .order_by(desc(MonitoringLog.created_at))
                .limit(10)
            )
            recent_events = recent_events_result.scalars().all()
            
            yesterday = datetime.utcnow() - timedelta(days=1)
            
            events_24h_result = await db.execute(
                select(MonitoringLog)
                .where(MonitoringLog.created_at >= yesterday)
            )
            events_24h = events_24h_result.scalars().all()
            
            successful_events = sum(1 for event in events_24h if event.is_success)
            failed_events = sum(1 for event in events_24h if not event.is_success)
            
            return {
                "is_running": self.is_running,
                "last_update": datetime.utcnow(),
                "recent_events": [
                    {
                        "type": event.event_type,
                        "message": event.message,
                        "success": event.is_success,
                        "created_at": event.created_at
                    }
                    for event in recent_events
                ],
                "stats_24h": {
                    "total_events": len(events_24h),
                    "successful": successful_events,
                    "failed": failed_events,
                    "success_rate": round(successful_events / len(events_24h) * 100, 1) if events_24h else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting monitoring status: {e}")
            return {
                "is_running": self.is_running,
                "last_update": datetime.utcnow(),
                "recent_events": [],
                "stats_24h": {
                    "total_events": 0,
                    "successful": 0,
                    "failed": 0,
                    "success_rate": 0
                }
            }
    
    async def force_check_subscriptions(self, db: AsyncSession) -> Dict[str, int]:
        try:
            expired_subscriptions = await get_expired_subscriptions(db)
            expired_count = 0
            
            for subscription in expired_subscriptions:
                await deactivate_subscription(db, subscription)
                expired_count += 1
            
            expiring_subscriptions = await get_expiring_subscriptions(db, 1)
            expiring_count = len(expiring_subscriptions)
            
            autopay_subscriptions = await get_subscriptions_for_autopay(db)
            autopay_processed = 0
            
            for subscription in autopay_subscriptions:
                user = await get_user_by_id(db, subscription.user_id)
                if user and user.balance_kopeks >= settings.PRICE_30_DAYS:
                    autopay_processed += 1
            
            await self._log_monitoring_event(
                db, "manual_check_subscriptions",
                    f"Force check: expired {expired_count}, expiring {expiring_count}, auto-payments {autopay_processed}",
                {
                    "expired": expired_count,
                    "expiring": expiring_count,
                    "autopay_ready": autopay_processed
                }
            )
            
            return {
                "expired": expired_count,
                "expiring": expiring_count,
                "autopay_ready": autopay_processed
            }
            
        except Exception as e:
            logger.error(f"Error in force subscription check: {e}")
            return {"expired": 0, "expiring": 0, "autopay_ready": 0}
    
    async def get_monitoring_logs(
        self,
        db: AsyncSession,
        limit: int = 50,
        event_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> List[Dict[str, Any]]:
        try:
            from sqlalchemy import select, desc
            
            query = select(MonitoringLog).order_by(desc(MonitoringLog.created_at))
            
            if event_type:
                query = query.where(MonitoringLog.event_type == event_type)
            
            if page > 1 or per_page != 20:
                offset = (page - 1) * per_page
                query = query.offset(offset).limit(per_page)
            else:
                query = query.limit(limit)
            
            result = await db.execute(query)
            logs = result.scalars().all()
            
            return [
                {
                    "id": log.id,
                    "event_type": log.event_type,
                    "message": log.message,
                    "data": log.data,
                    "is_success": log.is_success,
                    "created_at": log.created_at
                }
                for log in logs
            ]
            
        except Exception as e:
            logger.error(f"Error getting monitoring logs: {e}")
            return []

    async def get_monitoring_logs_count(
        self,
        db: AsyncSession,
        event_type: Optional[str] = None
    ) -> int:
        try:
            from sqlalchemy import select, func

            query = select(func.count(MonitoringLog.id))

            if event_type:
                query = query.where(MonitoringLog.event_type == event_type)

            result = await db.execute(query)
            count = result.scalar()

            return count or 0

        except Exception as e:
            logger.error(f"Error getting log count: {e}")
            return 0

    async def get_monitoring_event_types(self, db: AsyncSession) -> List[str]:
        try:
            from sqlalchemy import select

            result = await db.execute(
                select(MonitoringLog.event_type)
                .where(MonitoringLog.event_type.isnot(None))
                .distinct()
                .order_by(MonitoringLog.event_type)
            )

            return [row[0] for row in result.fetchall() if row[0]]

        except Exception as e:
            logger.error(f"Error getting monitoring event types list: {e}")
            return []
    
    async def cleanup_old_logs(self, db: AsyncSession, days: int = 30) -> int:
        try:
            from sqlalchemy import delete, select
            
            if days == 0:
                result = await db.execute(delete(MonitoringLog))
            else:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                result = await db.execute(
                    delete(MonitoringLog).where(MonitoringLog.created_at < cutoff_date)
                )
            
            deleted_count = result.rowcount
            await db.commit()
            
            if days == 0:
                logger.info(f"🗑️ Deleted all monitoring logs ({deleted_count} entries)")
            else:
                logger.info(f"🗑️ Deleted {deleted_count} old log entries (older than {days} days)")
                
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up logs: {e}")
            await db.rollback()
            return 0


monitoring_service = MonitoringService()
