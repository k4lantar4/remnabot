import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select, update, func
from aiogram import Bot, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from app.database.crud.user import (
    get_user_by_id, get_user_by_telegram_id, get_users_list,
    get_users_count, get_users_statistics, get_inactive_users,
    add_user_balance, subtract_user_balance, update_user, delete_user,
    get_users_spending_stats, get_referrals
)
from app.database.crud.promo_group import get_promo_group_by_id
from app.database.crud.transaction import get_user_transactions_count
from app.database.crud.subscription import (
    get_subscription_by_user_id,
    decrement_subscription_server_counts,
)
from app.database.models import (
    User, UserStatus, Subscription, Transaction, PromoCode, PromoCodeUse,
    ReferralEarning, SubscriptionServer, YooKassaPayment, BroadcastHistory,
    CryptoBotPayment, PlategaPayment, SubscriptionConversion, UserMessage, WelcomeText,
    SentNotification, PromoGroup, MulenPayPayment, Pal24Payment, HeleketPayment,
    AdvertisingCampaign, AdvertisingCampaignRegistration, PaymentMethod,
    TransactionType
)
from app.config import settings
from app.localization.texts import get_texts

logger = logging.getLogger(__name__)


class UserService:
    
    async def _send_balance_notification(
        self,
        bot: Bot,
        user: User,
        amount_kopeks: int,
        admin_name: str
    ) -> bool:
        """Sends notification to user about balance top-up/deduction"""
        try:
            texts = get_texts(user.language)
            if amount_kopeks > 0:
                # Top-up
                emoji = "💰"
                amount_text = f"+{settings.format_price(amount_kopeks)}"
                message = texts.t(
                    "service.notifications.user.balance_topup",
                    (
                        "{emoji} <b>Balance topped up!</b>\n\n"
                        "💵 <b>Amount:</b> {amount}\n"
                        "👤 <b>Administrator:</b> {admin_name}\n"
                        "💳 <b>Current balance:</b> {balance}\n\n"
                        "Thank you for using our service! 🎉"
                    )
                ).format(
                    emoji=emoji,
                    amount=amount_text,
                    admin_name=admin_name,
                    balance=settings.format_price(user.balance_kopeks)
                )
            else:
                # Deduction
                emoji = "💸"
                amount_text = f"-{settings.format_price(abs(amount_kopeks))}"
                message = texts.t(
                    "service.notifications.user.balance_deduction",
                    (
                        "{emoji} <b>Funds deducted from balance</b>\n\n"
                        "💵 <b>Amount:</b> {amount}\n"
                        "👤 <b>Administrator:</b> {admin_name}\n"
                        "💳 <b>Current balance:</b> {balance}\n\n"
                        "If you have any questions, please contact support."
                    )
                ).format(
                    emoji=emoji,
                    amount=amount_text,
                    admin_name=admin_name,
                    balance=settings.format_price(user.balance_kopeks)
                )

            keyboard_rows = []
            if getattr(user, "subscription", None) and user.subscription.status in {
                "active",
                "expired",
                "trial",
            }:
                keyboard_rows.append([
                    types.InlineKeyboardButton(
                        text=get_texts(user.language).t("SUBSCRIPTION_EXTEND", "💎 Extend subscription"),
                        callback_data="subscription_extend",
                    )
                ])

            reply_markup = (
                types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
                if keyboard_rows
                else None
            )

            await bot.send_message(
                chat_id=user.telegram_id,
                text=message,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            
            logger.info(f"Balance change notification sent to user {user.telegram_id}")
            return True
            
        except TelegramForbiddenError:
            logger.warning(f"User {user.telegram_id} blocked the bot")
            return False
        except TelegramBadRequest as e:
            logger.error(f"Telegram API error sending notification to user {user.telegram_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending notification to user {user.telegram_id}: {e}")
            return False
    
    async def get_user_profile(
        self, 
        db: AsyncSession, 
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        try:
            user = await get_user_by_id(db, user_id)
            if not user:
                return None
            
            subscription = await get_subscription_by_user_id(db, user_id)
            transactions_count = await get_user_transactions_count(db, user_id)
            
            return {
                "user": user,
                "subscription": subscription,
                "transactions_count": transactions_count,
                "is_admin": settings.is_admin(user.telegram_id),
                "registration_days": (datetime.utcnow() - user.created_at).days
            }
            
        except Exception as e:
            logger.error(f"Error getting user profile {user_id}: {e}")
            return None
    
    async def search_users(
        self,
        db: AsyncSession,
        query: str,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        try:
            offset = (page - 1) * limit
            
            users = await get_users_list(
                db, offset=offset, limit=limit, search=query
            )
            total_count = await get_users_count(db, search=query)
            
            total_pages = (total_count + limit - 1) // limit
            
            return {
                "users": users,
                "current_page": page,
                "total_pages": total_pages,
                "total_count": total_count,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
            
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return {
                "users": [],
                "current_page": 1,
                "total_pages": 1,
                "total_count": 0,
                "has_next": False,
                "has_prev": False
            }

    async def get_users_page(
        self,
        db: AsyncSession,
        page: int = 1,
        limit: int = 20,
        status: Optional[UserStatus] = None,
        order_by_balance: bool = False,
        order_by_traffic: bool = False,
        order_by_last_activity: bool = False,
        order_by_total_spent: bool = False,
        order_by_purchase_count: bool = False
    ) -> Dict[str, Any]:
        try:
            offset = (page - 1) * limit
            
            users = await get_users_list(
                db,
                offset=offset,
                limit=limit,
                status=status,
                order_by_balance=order_by_balance,
                order_by_traffic=order_by_traffic,
                order_by_last_activity=order_by_last_activity,
                order_by_total_spent=order_by_total_spent,
                order_by_purchase_count=order_by_purchase_count,
            )
            total_count = await get_users_count(db, status=status)
            
            total_pages = (total_count + limit - 1) // limit
            
            return {
                "users": users,
                "current_page": page,
                "total_pages": total_pages,
                "total_count": total_count,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
            
        except Exception as e:
            logger.error(f"Error getting users page: {e}")
            return {
                "users": [],
                "current_page": 1,
                "total_pages": 1,
                "total_count": 0,
                "has_next": False,
                "has_prev": False
            }

    async def get_user_spending_stats_map(
        self,
        db: AsyncSession,
        user_ids: List[int]
    ) -> Dict[int, Dict[str, int]]:
        try:
            return await get_users_spending_stats(db, user_ids)
        except Exception as e:
            logger.error(f"Error getting user spending stats: {e}")
            return {}

    async def get_users_by_campaign_page(
        self,
        db: AsyncSession,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        try:
            offset = (page - 1) * limit

            campaign_ranked = (
                select(
                    AdvertisingCampaignRegistration.user_id.label("user_id"),
                    AdvertisingCampaignRegistration.campaign_id.label("campaign_id"),
                    AdvertisingCampaignRegistration.created_at.label("created_at"),
                    func.row_number()
                    .over(
                        partition_by=AdvertisingCampaignRegistration.user_id,
                        order_by=AdvertisingCampaignRegistration.created_at.desc(),
                    )
                    .label("rn"),
                )
                .cte("campaign_ranked")
            )

            latest_campaign = (
                select(
                    campaign_ranked.c.user_id,
                    campaign_ranked.c.campaign_id,
                    campaign_ranked.c.created_at,
                )
                .where(campaign_ranked.c.rn == 1)
                .subquery()
            )

            query = (
                select(
                    User,
                    AdvertisingCampaign.name.label("campaign_name"),
                    latest_campaign.c.created_at,
                )
                .join(latest_campaign, latest_campaign.c.user_id == User.id)
                .join(
                    AdvertisingCampaign,
                    AdvertisingCampaign.id == latest_campaign.c.campaign_id,
                )
                .order_by(
                    AdvertisingCampaign.name.asc(),
                    latest_campaign.c.created_at.desc(),
                )
                .offset(offset)
                .limit(limit)
            )

            result = await db.execute(query)
            rows = result.all()

            users = [row[0] for row in rows]
            campaign_map = {
                row[0].id: {
                    "campaign_name": row[1],
                    "registered_at": row[2],
                }
                for row in rows
            }

            total_stmt = select(func.count()).select_from(latest_campaign)
            total_result = await db.execute(total_stmt)
            total_count = total_result.scalar() or 0
            total_pages = (total_count + limit - 1) // limit if total_count else 1

            return {
                "users": users,
                "campaigns": campaign_map,
                "current_page": page,
                "total_pages": total_pages,
                "total_count": total_count,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            }

        except Exception as e:
            logger.error(f"Error getting users by campaign: {e}")
            return {
                "users": [],
                "campaigns": {},
                "current_page": 1,
                "total_pages": 1,
                "total_count": 0,
                "has_next": False,
                "has_prev": False,
            }

    async def update_user_balance(
        self,
        db: AsyncSession,
        user_id: int,
        amount_kopeks: int,
        description: str,
        admin_id: int,
        bot: Optional[Bot] = None,
        admin_name: Optional[str] = None
    ) -> bool:
        try:
            user = await get_user_by_id(db, user_id)
            if not user:
                return False

            # Save old balance for notification
            old_balance = user.balance_kopeks

            if amount_kopeks > 0:
                await add_user_balance(db, user, amount_kopeks, description=description)
                logger.info(f"Admin {admin_id} topped up balance for user {user_id} by {amount_kopeks/100}₽")
                success = True
            else:
                success = await subtract_user_balance(
                    db,
                    user,
                    abs(amount_kopeks),
                    description,
                    create_transaction=True,
                    payment_method=PaymentMethod.MANUAL,
                )
                if success:
                    logger.info(f"Admin {admin_id} deducted {abs(amount_kopeks)/100}₽ from user {user_id} balance")

            # Send notification to user if operation succeeded
            if success and bot:
                # Refresh user to get new balance
                await db.refresh(user)

                # Get administrator name
                if not admin_name:
                    admin_user = await get_user_by_id(db, admin_id)
                    admin_name = admin_user.full_name if admin_user else f"Admin #{admin_id}"

                # Send notification (don't block operation if sending fails)
                await self._send_balance_notification(bot, user, amount_kopeks, admin_name)

            return success

        except Exception as e:
            logger.error(f"Error updating user balance: {e}")
            return False

    async def update_user_promo_group(
        self,
        db: AsyncSession,
        user_id: int,
        promo_group_id: int
    ) -> Tuple[bool, Optional[User], Optional[PromoGroup], Optional[PromoGroup]]:
        try:
            user = await get_user_by_id(db, user_id)
            if not user:
                return False, None, None, None

            old_group = user.promo_group

            promo_group = await get_promo_group_by_id(db, promo_group_id)
            if not promo_group:
                return False, None, None, old_group

            user.promo_group_id = promo_group.id
            user.promo_group = promo_group
            user.updated_at = datetime.utcnow()

            await db.commit()
            await db.refresh(user)

            logger.info(
                "Promo group for user %s updated to '%s'",
                user.telegram_id,
                promo_group.name,
            )

            return True, user, promo_group, old_group

        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating user promo group {user_id}: {e}")
            return False, None, None, None

    async def update_user_referrals(
        self,
        db: AsyncSession,
        user_id: int,
        referral_user_ids: List[int],
        admin_id: int,
    ) -> Tuple[bool, Dict[str, int]]:
        try:
            user = await get_user_by_id(db, user_id)
            if not user:
                return False, {"error": "user_not_found"}

            unique_ids: List[int] = []
            for referral_id in referral_user_ids:
                if referral_id == user_id:
                    continue
                if referral_id not in unique_ids:
                    unique_ids.append(referral_id)

            current_referrals = await get_referrals(db, user_id)
            current_ids = {ref.id for ref in current_referrals}

            to_assign = unique_ids
            to_remove = [rid for rid in current_ids if rid not in unique_ids]
            to_add = [rid for rid in unique_ids if rid not in current_ids]

            if to_assign:
                await db.execute(
                    update(User)
                    .where(User.id.in_(to_assign))
                    .values(referred_by_id=user_id)
                )

            if to_remove:
                await db.execute(
                    update(User)
                    .where(User.id.in_(to_remove))
                    .values(referred_by_id=None)
                )

            await db.commit()

            logger.info(
                "Admin %s updated referrals for user %s: added %s, removed %s, total %s",
                admin_id,
                user_id,
                len(to_add),
                len(to_remove),
                len(unique_ids),
            )

            return True, {
                "added": len(to_add),
                "removed": len(to_remove),
                "total": len(unique_ids),
            }

        except Exception as e:
            await db.rollback()
            logger.error(
                "Error updating user referrals %s: %s",
                user_id,
                e,
            )
            return False, {"error": "update_failed"}

    async def block_user(
        self,
        db: AsyncSession,
        user_id: int,
        admin_id: int,
        reason: str = "Blocked by administrator"
    ) -> bool:
        try:
            user = await get_user_by_id(db, user_id)
            if not user:
                return False
            
            if user.remnawave_uuid:
                try:
                    from app.services.subscription_service import SubscriptionService
                    subscription_service = SubscriptionService()
                    await subscription_service.disable_remnawave_user(user.remnawave_uuid)
                    logger.info(f"RemnaWave user {user.remnawave_uuid} deactivated on block")
                except Exception as e:
                    logger.error(f"Error deactivating RemnaWave user on block: {e}")
            
            if user.subscription:
                from app.database.crud.subscription import deactivate_subscription
                await deactivate_subscription(db, user.subscription)
            
            await update_user(db, user, status=UserStatus.BLOCKED.value)
            
            logger.info(f"Admin {admin_id} blocked user {user_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Error blocking user: {e}")
            return False
    
    async def unblock_user(
        self,
        db: AsyncSession,
        user_id: int,
        admin_id: int
    ) -> bool:
        try:
            user = await get_user_by_id(db, user_id)
            if not user:
                return False
            
            await update_user(db, user, status=UserStatus.ACTIVE.value)
            
            if user.subscription:
                from datetime import datetime
                from app.database.models import SubscriptionStatus
                
                if user.subscription.end_date > datetime.utcnow():
                    user.subscription.status = SubscriptionStatus.ACTIVE.value
                    await db.commit()
                    await db.refresh(user.subscription)
                    logger.info(f"Subscription for user {user_id} restored")
                    
                    if user.remnawave_uuid:
                        try:
                            from app.services.subscription_service import SubscriptionService
                            subscription_service = SubscriptionService()
                            await subscription_service.update_remnawave_user(db, user.subscription)
                            logger.info(f"RemnaWave user {user.remnawave_uuid} restored on unblock")
                        except Exception as e:
                            logger.error(f"Error restoring RemnaWave user on unblock: {e}")
                else:
                    logger.info(f"Subscription for user {user_id} expired, cannot restore")
            
            logger.info(f"Admin {admin_id} unblocked user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error unblocking user: {e}")
            return False
    
    async def delete_user_account(
        self,
        db: AsyncSession,
        user_id: int,
        admin_id: int
    ) -> bool:
        try:
            user = await get_user_by_id(db, user_id)
            if not user:
                logger.warning(f"User {user_id} not found for deletion")
                return False
            
            logger.info(f"Starting full deletion of user {user_id} (Telegram ID: {user.telegram_id})")
            
            if user.remnawave_uuid:
                from app.config import settings
                delete_mode = settings.get_remnawave_user_delete_mode()
                
                try:
                    from app.services.remnawave_service import RemnaWaveService
                    remnawave_service = RemnaWaveService()
                    
                    if delete_mode == "delete":
                        # Delete user from Remnawave panel
                        async with remnawave_service.get_api_client() as api:
                            delete_success = await api.delete_user(user.remnawave_uuid)
                            if delete_success:
                                logger.info(f"RemnaWave user {user.remnawave_uuid} deleted from panel")
                            else:
                                logger.warning(f"Failed to delete user {user.remnawave_uuid} from Remnawave panel")
                    else:
                        # Deactivate user in Remnawave panel
                        from app.services.subscription_service import SubscriptionService
                        subscription_service = SubscriptionService()
                        await subscription_service.disable_remnawave_user(user.remnawave_uuid)
                        logger.info(f"RemnaWave user {user.remnawave_uuid} deactivated (mode: {delete_mode})")
                    
                except Exception as e:
                    logger.warning(f"Error processing user in Remnawave (mode: {delete_mode}): {e}")
                    # If main action failed, try to at least deactivate
                    if delete_mode == "delete":
                        try:
                            from app.services.subscription_service import SubscriptionService
                            subscription_service = SubscriptionService()
                            await subscription_service.disable_remnawave_user(user.remnawave_uuid)
                            logger.info(f"RemnaWave user {user.remnawave_uuid} deactivated as fallback")
                        except Exception as fallback_e:
                            logger.error(f"Error deactivating RemnaWave as fallback: {fallback_e}")
            
            try:
                sent_notifications_result = await db.execute(
                    select(SentNotification).where(SentNotification.user_id == user_id)
                )
                sent_notifications = sent_notifications_result.scalars().all()
                
                if sent_notifications:
                    logger.info(f"Deleting {len(sent_notifications)} notifications")
                    await db.execute(
                        delete(SentNotification).where(SentNotification.user_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting notifications: {e}")
    
            try:
                if user.subscription:
                    subscription_servers_result = await db.execute(
                        select(SubscriptionServer).where(
                            SubscriptionServer.subscription_id == user.subscription.id
                        )
                    )
                    subscription_servers = subscription_servers_result.scalars().all()

                    await decrement_subscription_server_counts(
                        db,
                        user.subscription,
                        subscription_servers=subscription_servers,
                    )

                    if subscription_servers:
                        logger.info(f"Deleting {len(subscription_servers)} subscription-server links")
                        await db.execute(
                            delete(SubscriptionServer).where(
                                SubscriptionServer.subscription_id == user.subscription.id
                            )
                        )
                        await db.flush()
            except Exception as e:
                logger.error(f"Error deleting subscription-server links: {e}")
    
            try:
                user_messages_result = await db.execute(
                    update(UserMessage)
                    .where(UserMessage.created_by == user_id)
                    .values(created_by=None)
                )
                if user_messages_result.rowcount > 0:
                    logger.info(f"Updated {user_messages_result.rowcount} user messages")
                await db.flush()
            except Exception as e:
                logger.error(f"Error updating user messages: {e}")
    
            try:
                promocodes_result = await db.execute(
                    update(PromoCode)
                    .where(PromoCode.created_by == user_id)
                    .values(created_by=None)
                )
                if promocodes_result.rowcount > 0:
                    logger.info(f"Updated {promocodes_result.rowcount} promocodes")
                await db.flush()
            except Exception as e:
                logger.error(f"Error updating promocodes: {e}")
    
            try:
                welcome_texts_result = await db.execute(
                    update(WelcomeText)
                    .where(WelcomeText.created_by == user_id)
                    .values(created_by=None)
                )
                if welcome_texts_result.rowcount > 0:
                    logger.info(f"Updated {welcome_texts_result.rowcount} welcome texts")
                await db.flush()
            except Exception as e:
                logger.error(f"Error updating welcome texts: {e}")
    
            try:
                referrals_result = await db.execute(
                    update(User)
                    .where(User.referred_by_id == user_id)
                    .values(referred_by_id=None)
                )
                if referrals_result.rowcount > 0:
                    logger.info(f"Cleared referral links for {referrals_result.rowcount} referrals")
                await db.flush()
            except Exception as e:
                logger.error(f"Error clearing referral links: {e}")
    
            try:
                yookassa_result = await db.execute(
                    select(YooKassaPayment).where(YooKassaPayment.user_id == user_id)
                )
                yookassa_payments = yookassa_result.scalars().all()
                
                if yookassa_payments:
                    logger.info(f"Deleting {len(yookassa_payments)} YooKassa payments")
                    await db.execute(
                        update(YooKassaPayment)
                        .where(YooKassaPayment.user_id == user_id)
                        .values(transaction_id=None)
                    )
                    await db.flush()
                    await db.execute(
                        delete(YooKassaPayment).where(YooKassaPayment.user_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting YooKassa payments: {e}")
    
            try:
                cryptobot_result = await db.execute(
                    select(CryptoBotPayment).where(CryptoBotPayment.user_id == user_id)
                )
                cryptobot_payments = cryptobot_result.scalars().all()

                if cryptobot_payments:
                    logger.info(f"Deleting {len(cryptobot_payments)} CryptoBot payments")
                    await db.execute(
                        update(CryptoBotPayment)
                        .where(CryptoBotPayment.user_id == user_id)
                        .values(transaction_id=None)
                    )
                    await db.flush()
                    await db.execute(
                        delete(CryptoBotPayment).where(CryptoBotPayment.user_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting CryptoBot payments: {e}")

            try:
                platega_result = await db.execute(
                    select(PlategaPayment).where(PlategaPayment.user_id == user_id)
                )
                platega_payments = platega_result.scalars().all()

                if platega_payments:
                    logger.info(f"Deleting {len(platega_payments)} Platega payments")
                    await db.execute(
                        update(PlategaPayment)
                        .where(PlategaPayment.user_id == user_id)
                        .values(transaction_id=None)
                    )
                    await db.flush()
                    await db.execute(
                        delete(PlategaPayment).where(PlategaPayment.user_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting Platega payments: {e}")

            try:
                mulenpay_result = await db.execute(
                    select(MulenPayPayment).where(MulenPayPayment.user_id == user_id)
                )
                mulenpay_payments = mulenpay_result.scalars().all()

                if mulenpay_payments:
                    mulenpay_name = settings.get_mulenpay_display_name()
                    logger.info(
                        f"Deleting {len(mulenpay_payments)} {mulenpay_name} payments"
                    )
                    await db.execute(
                        update(MulenPayPayment)
                        .where(MulenPayPayment.user_id == user_id)
                        .values(transaction_id=None)
                    )
                    await db.flush()
                    await db.execute(
                        delete(MulenPayPayment).where(MulenPayPayment.user_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(
                    f"Error deleting {settings.get_mulenpay_display_name()} payments: {e}"
                )

            try:
                pal24_result = await db.execute(
                    select(Pal24Payment).where(Pal24Payment.user_id == user_id)
                )
                pal24_payments = pal24_result.scalars().all()

                if pal24_payments:
                    logger.info(f"Deleting {len(pal24_payments)} Pal24 payments")
                    await db.execute(
                        update(Pal24Payment)
                        .where(Pal24Payment.user_id == user_id)
                        .values(transaction_id=None)
                    )
                    await db.flush()
                    await db.execute(
                        delete(Pal24Payment).where(Pal24Payment.user_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting Pal24 payments: {e}")

            try:
                heleket_result = await db.execute(
                    select(HeleketPayment).where(HeleketPayment.user_id == user_id)
                )
                heleket_payments = heleket_result.scalars().all()

                if heleket_payments:
                    logger.info(
                        f"Deleting {len(heleket_payments)} Heleket payments"
                    )
                    await db.execute(
                        update(HeleketPayment)
                        .where(HeleketPayment.user_id == user_id)
                        .values(transaction_id=None)
                    )
                    await db.flush()
                    await db.execute(
                        delete(HeleketPayment).where(HeleketPayment.user_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting Heleket payments: {e}")

            try:
                transactions_result = await db.execute(
                    select(Transaction).where(Transaction.user_id == user_id)
                )
                transactions = transactions_result.scalars().all()
                
                if transactions:
                    logger.info(f"Deleting {len(transactions)} transactions")
                    await db.execute(
                        delete(Transaction).where(Transaction.user_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting transactions: {e}")
    
            try:
                promocode_uses_result = await db.execute(
                    select(PromoCodeUse).where(PromoCodeUse.user_id == user_id)
                )
                promocode_uses = promocode_uses_result.scalars().all()
                
                if promocode_uses:
                    logger.info(f"Deleting {len(promocode_uses)} promocode uses")
                    await db.execute(
                        delete(PromoCodeUse).where(PromoCodeUse.user_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting promocode uses: {e}")
    
            try:
                referral_earnings_result = await db.execute(
                    select(ReferralEarning).where(ReferralEarning.user_id == user_id)
                )
                referral_earnings = referral_earnings_result.scalars().all()
                
                if referral_earnings:
                    logger.info(f"Deleting {len(referral_earnings)} referral earnings")
                    await db.execute(
                        delete(ReferralEarning).where(ReferralEarning.user_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting referral earnings: {e}")
    
            try:
                referral_records_result = await db.execute(
                    select(ReferralEarning).where(ReferralEarning.referral_id == user_id)
                )
                referral_records = referral_records_result.scalars().all()
                
                if referral_records:
                    logger.info(f"Deleting {len(referral_records)} referral records")
                    await db.execute(
                        delete(ReferralEarning).where(ReferralEarning.referral_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting referral records: {e}")
    
            try:
                conversions_result = await db.execute(
                    select(SubscriptionConversion).where(SubscriptionConversion.user_id == user_id)
                )
                conversions = conversions_result.scalars().all()
                
                if conversions:
                    logger.info(f"Deleting {len(conversions)} conversion records")
                    await db.execute(
                        delete(SubscriptionConversion).where(SubscriptionConversion.user_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting conversion records: {e}")
    
            try:
                broadcast_history_result = await db.execute(
                    select(BroadcastHistory).where(BroadcastHistory.admin_id == user_id)
                )
                broadcast_history = broadcast_history_result.scalars().all()

                if broadcast_history:
                    logger.info(f"Deleting {len(broadcast_history)} broadcast history records")
                    await db.execute(
                        delete(BroadcastHistory).where(BroadcastHistory.admin_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting broadcast history: {e}")

            try:
                campaigns_result = await db.execute(
                    select(AdvertisingCampaign).where(AdvertisingCampaign.created_by == user_id)
                )
                campaigns = campaigns_result.scalars().all()

                if campaigns:
                    logger.info(f"Clearing creator for {len(campaigns)} advertising campaigns")
                    await db.execute(
                        update(AdvertisingCampaign)
                        .where(AdvertisingCampaign.created_by == user_id)
                        .values(created_by=None)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error updating advertising campaigns: {e}")
    
            try:
                if user.subscription:
                    logger.info(f"Deleting subscription {user.subscription.id}")
                    await db.execute(
                        delete(Subscription).where(Subscription.user_id == user_id)
                    )
                    await db.flush()
            except Exception as e:
                logger.error(f"Error deleting subscription: {e}")
    
            try:
                await db.execute(
                    delete(User).where(User.id == user_id)
                )
                await db.commit()
                logger.info(f"User {user_id} finally deleted from database")
            except Exception as e:
                logger.error(f"Error in final user deletion: {e}")
                await db.rollback()
                return False
            
            logger.info(f"User {user.telegram_id} (ID: {user_id}) fully deleted by admin {admin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Critical error deleting user {user_id}: {e}")
            await db.rollback()
            return False
    
    async def get_user_statistics(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            stats = await get_users_statistics(db)
            return stats
            
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return {
                "total_users": 0,
                "active_users": 0,
                "blocked_users": 0,
                "new_today": 0,
                "new_week": 0,
                "new_month": 0
            }
    
    async def cleanup_inactive_users(
        self,
        db: AsyncSession,
        months: int = None
    ) -> int:
        try:
            if months is None:
                months = settings.INACTIVE_USER_DELETE_MONTHS
            
            inactive_users = await get_inactive_users(db, months)
            deleted_count = 0
            
            for user in inactive_users:
                success = await self.delete_user_account(db, user.id, 0) 
                if success:
                    deleted_count += 1
            
            logger.info(f"Deleted {deleted_count} inactive users")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up inactive users: {e}")
            return 0
    
    async def get_user_activity_summary(
        self,
        db: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        try:
            user = await get_user_by_id(db, user_id)
            if not user:
                return {}
            
            subscription = await get_subscription_by_user_id(db, user_id)
            transactions_count = await get_user_transactions_count(db, user_id)
            
            days_since_registration = (datetime.utcnow() - user.created_at).days
            
            days_since_activity = (datetime.utcnow() - user.last_activity).days if user.last_activity else None
            
            return {
                "user_id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "full_name": user.full_name,
                "status": user.status,
                "language": user.language,
                "balance_kopeks": user.balance_kopeks,
                "registration_date": user.created_at,
                "last_activity": user.last_activity,
                "days_since_registration": days_since_registration,
                "days_since_activity": days_since_activity,
                "has_subscription": subscription is not None,
                "subscription_active": subscription.is_active if subscription else False,
                "subscription_trial": subscription.is_trial if subscription else False,
                "transactions_count": transactions_count,
                "referrer_id": user.referred_by_id,
                "referral_code": user.referral_code
            }
            
        except Exception as e:
            logger.error(f"Error getting user activity summary {user_id}: {e}")
            return {}
    
    async def get_users_by_criteria(
        self,
        db: AsyncSession,
        criteria: Dict[str, Any]
    ) -> List[User]:
        try:
            status = criteria.get('status')
            has_subscription = criteria.get('has_subscription')
            is_trial = criteria.get('is_trial')
            min_balance = criteria.get('min_balance', 0)
            max_balance = criteria.get('max_balance')
            days_inactive = criteria.get('days_inactive')
            
            registered_after = criteria.get('registered_after')
            registered_before = criteria.get('registered_before')
            
            users = await get_users_list(db, offset=0, limit=10000, status=status)
            
            filtered_users = []
            for user in users:
                if user.balance_kopeks < min_balance:
                    continue
                if max_balance and user.balance_kopeks > max_balance:
                    continue
                
                if registered_after and user.created_at < registered_after:
                    continue
                if registered_before and user.created_at > registered_before:
                    continue
                
                if days_inactive and user.last_activity:
                    inactive_threshold = datetime.utcnow() - timedelta(days=days_inactive)
                    if user.last_activity > inactive_threshold:
                        continue
                
                filtered_users.append(user)
            
            return filtered_users
            
        except Exception as e:
            logger.error(f"Error getting users by criteria: {e}")
            return []
