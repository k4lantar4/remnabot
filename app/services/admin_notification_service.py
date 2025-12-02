import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from aiogram import Bot, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import MissingGreenlet

from app.config import settings
from app.localization.texts import get_texts
from app.database.crud.promo_group import get_promo_group_by_id
from app.database.crud.subscription_event import create_subscription_event
from app.database.crud.user import get_user_by_id
from app.database.crud.transaction import get_transaction_by_id
from app.database.models import (
    AdvertisingCampaign,
    PromoCodeType,
    PromoGroup,
    Subscription,
    Transaction,
    TransactionType,
    User,
)
from app.utils.timezone import format_local_datetime

logger = logging.getLogger(__name__)


class AdminNotificationService:
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.chat_id = getattr(settings, 'ADMIN_NOTIFICATIONS_CHAT_ID', None)
        self.topic_id = getattr(settings, 'ADMIN_NOTIFICATIONS_TOPIC_ID', None)
        self.ticket_topic_id = getattr(settings, 'ADMIN_NOTIFICATIONS_TICKET_TOPIC_ID', None)
        self.enabled = getattr(settings, 'ADMIN_NOTIFICATIONS_ENABLED', False)
        # Admin notifications use a single localization context
        default_locale = getattr(settings, "DEFAULT_LANGUAGE", "en")
        self.texts = get_texts(default_locale)
    
    async def _get_referrer_info(self, db: AsyncSession, referred_by_id: Optional[int]) -> str:
        if not referred_by_id:
            return self.texts.t("service.notifications.admin.referrer_none", "None")

        try:
            referrer = await get_user_by_id(db, referred_by_id)
            if not referrer:
                return self.texts.t(
                    "service.notifications.admin.referrer_not_found",
                    "ID {id} (not found)"
                ).format(id=referred_by_id)

            if referrer.username:
                return f"@{referrer.username} (ID: {referred_by_id})"
            else:
                return f"ID {referrer.telegram_id}"

        except Exception as e:
            logger.error(f"Failed to get referrer data for {referred_by_id}: {e}")
            return f"ID {referred_by_id}"

    async def _get_user_promo_group(self, db: AsyncSession, user: User) -> Optional[PromoGroup]:
        if getattr(user, "promo_group", None):
            return user.promo_group

        if not user.promo_group_id:
            return None

        try:
            await db.refresh(user, attribute_names=["promo_group"])
        except Exception:
            # relationship might not be available — fallback to direct fetch
            pass

        if getattr(user, "promo_group", None):
            return user.promo_group

        try:
            return await get_promo_group_by_id(db, user.promo_group_id)
        except Exception as e:
            logger.error(
                "Failed to load promo group %s for user %s: %s",
                user.promo_group_id,
                user.telegram_id,
                e,
            )
            return None

    def _get_user_display(self, user: User) -> str:
        first_name = getattr(user, "first_name", "") or ""
        if first_name:
            return first_name

        username = getattr(user, "username", "") or ""
        if username:
            return username

        telegram_id = getattr(user, "telegram_id", None)
        if telegram_id is None:
            return "IDUnknown"
        return f"ID{telegram_id}"

    async def _record_subscription_event(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        user: User,
        subscription: Subscription | None,
        transaction: Transaction | None = None,
        amount_kopeks: int | None = None,
        message: str | None = None,
        extra: Dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        """Persist subscription-related event for external dashboards."""

        try:
            await create_subscription_event(
                db,
                user_id=user.id,
                event_type=event_type,
                subscription_id=subscription.id if subscription else None,
                transaction_id=transaction.id if transaction else None,
                amount_kopeks=amount_kopeks,
                currency=None,
                message=message,
                occurred_at=occurred_at,
                extra=extra or None,
            )
        except Exception:
            logger.error(
                "Failed to save subscription event (%s) for user %s",
                event_type,
                getattr(user, "id", "unknown"),
                exc_info=True,
            )

            try:
                await db.rollback()
            except Exception:
                logger.error(
                    "Failed to rollback after subscription event error for user %s",
                    getattr(user, "id", "unknown"),
                    exc_info=True,
                )

    def _format_promo_group_discounts(self, promo_group: PromoGroup) -> List[str]:
        discount_lines: List[str] = []

        discount_map = {
            "servers": (
                self.texts.t("service.notifications.admin.discount_servers", "Servers"),
                promo_group.server_discount_percent,
            ),
            "traffic": (
                self.texts.t("service.notifications.admin.discount_traffic", "Traffic"),
                promo_group.traffic_discount_percent,
            ),
            "devices": (
                self.texts.t("service.notifications.admin.discount_devices", "Devices"),
                promo_group.device_discount_percent,
            ),
        }

        for _, (title, percent) in discount_map.items():
            if percent and percent > 0:
                discount_lines.append(f"• {title}: -{percent}%")

        period_discounts_raw = promo_group.period_discounts or {}
        period_items: List[tuple[int, int]] = []

        if isinstance(period_discounts_raw, dict):
            for raw_days, raw_percent in period_discounts_raw.items():
                try:
                    days = int(raw_days)
                    percent = int(raw_percent)
                except (TypeError, ValueError):
                    continue

                if percent > 0:
                    period_items.append((days, percent))

        period_items.sort(key=lambda item: item[0])

        if period_items:
            formatted_periods = ", ".join(
                self.texts.t(
                    "service.notifications.admin.discount_period_item",
                    "{days} days — -{percent}%"
                ).format(days=days, percent=percent)
                for days, percent in period_items
            )
            discount_lines.append(
                self.texts.t(
                    "service.notifications.admin.discount_periods",
                    "• Periods: {formatted_periods}"
                ).format(formatted_periods=formatted_periods)
            )

        if promo_group.apply_discounts_to_addons:
            discount_lines.append(
                self.texts.t(
                    "service.notifications.admin.discount_addons_enabled",
                    "• Add-ons: ✅ discount applies"
                )
            )
        else:
            discount_lines.append(
                self.texts.t(
                    "service.notifications.admin.discount_addons_disabled",
                    "• Add-ons: ❌ no discount"
                )
            )

        return discount_lines

    def _format_promo_group_block(
        self,
        promo_group: Optional[PromoGroup],
        *,
        title: str = None,
        icon: str = "🏷️",
    ) -> str:
        if title is None:
            title = self.texts.t("service.notifications.admin.promo_group", "Promo group")
        
        if not promo_group:
            return f"{icon} <b>{title}:</b> —"

        lines = [f"{icon} <b>{title}:</b> {promo_group.name}"]

        discount_lines = self._format_promo_group_discounts(promo_group)
        if discount_lines:
            lines.append(
                self.texts.t(
                    "service.notifications.admin.discounts_title",
                    "💸 <b>Discounts:</b>"
                )
            )
            lines.extend(discount_lines)
        else:
            lines.append(
                self.texts.t(
                    "service.notifications.admin.discounts_none",
                    "💸 <b>Discounts:</b> none"
                )
            )

        return "\n".join(lines)

    def _get_promocode_type_display(self, promo_type: Optional[str]) -> str:
        mapping = {
            PromoCodeType.BALANCE.value: self.texts.t(
                "service.notifications.admin.promocode_type.balance",
                "💰 Balance bonus"
            ),
            PromoCodeType.SUBSCRIPTION_DAYS.value: self.texts.t(
                "service.notifications.admin.promocode_type.subscription_days",
                "⏰ Extra subscription days"
            ),
            PromoCodeType.TRIAL_SUBSCRIPTION.value: self.texts.t(
                "service.notifications.admin.promocode_type.trial",
                "🎁 Trial subscription"
            ),
        }

        if not promo_type:
            return self.texts.t(
                "service.notifications.admin.promocode_type.unspecified",
                "ℹ️ Not specified"
            )

        return mapping.get(promo_type, f"ℹ️ {promo_type}")

    def _format_campaign_bonus(self, campaign: AdvertisingCampaign) -> List[str]:
        if campaign.is_balance_bonus:
            return [
                self.texts.t(
                    "service.notifications.admin.campaign_bonus.balance",
                    "💰 Balance: {amount}"
                ).format(amount=settings.format_price(campaign.balance_bonus_kopeks or 0)),
            ]

        if campaign.is_subscription_bonus:
            default_devices = getattr(settings, "DEFAULT_DEVICE_LIMIT", 1)
            details = [
                self.texts.t(
                    "service.notifications.admin.campaign_bonus.subscription_days",
                    "📅 Subscription days: {days}"
                ).format(days=campaign.subscription_duration_days or 0),
                self.texts.t(
                    "service.notifications.admin.campaign_bonus.traffic",
                    "📊 Traffic: {traffic} GB"
                ).format(traffic=campaign.subscription_traffic_gb or 0),
                self.texts.t(
                    "service.notifications.admin.campaign_bonus.devices",
                    "📱 Devices: {devices}"
                ).format(devices=campaign.subscription_device_limit or default_devices),
            ]
            if campaign.subscription_squads:
                details.append(
                    self.texts.t(
                        "service.notifications.admin.campaign_bonus.squads",
                        "🌐 Squads: {count} pcs."
                    ).format(count=len(campaign.subscription_squads))
                )
            return details

        return [
            self.texts.t(
                "service.notifications.admin.campaign_bonus.none",
                "ℹ️ No bonuses provided"
            )
        ]
    
    async def send_trial_activation_notification(
        self,
        db: AsyncSession,
        user: User,
        subscription: Subscription,
        *,
        charged_amount_kopeks: Optional[int] = None,
    ) -> bool:
        try:
            await self._record_subscription_event(
                db,
                event_type="activation",
                user=user,
                subscription=subscription,
                transaction=None,
                amount_kopeks=charged_amount_kopeks,
                message="Trial activation",
                occurred_at=datetime.utcnow(),
                extra={
                    "charged_amount_kopeks": charged_amount_kopeks,
                    "trial_duration_days": settings.TRIAL_DURATION_DAYS,
                    "traffic_limit_gb": settings.TRIAL_TRAFFIC_LIMIT_GB,
                    "device_limit": subscription.device_limit,
                },
            )

            if not self._is_enabled():
                return False

            user_status = (
                "🆕 New"
                if not user.has_had_paid_subscription
                else "🔄 Existing"
            )
            referrer_info = await self._get_referrer_info(db, user.referred_by_id)
            promo_group = await self._get_user_promo_group(db, user)
            promo_block = self._format_promo_group_block(promo_group)
            user_display = self._get_user_display(user)

            trial_device_limit = subscription.device_limit
            if trial_device_limit is None:
                fallback_forced_limit = settings.get_disabled_mode_device_limit()
                if fallback_forced_limit is not None:
                    trial_device_limit = fallback_forced_limit
                else:
                    trial_device_limit = settings.TRIAL_DEVICE_LIMIT

            payment_block = ""
            if charged_amount_kopeks and charged_amount_kopeks > 0:
                payment_block = (
                    f"\n💳 <b>Activation payment:</b> {settings.format_price(charged_amount_kopeks)}"
                )
            username = getattr(user, "username", None) or self.texts.t(
                "service.notifications.admin.username_missing",
                "not set",
            )

            template = self.texts.t(
                "service.notifications.admin.trial_activation",
                (
                    "🎯 <b>TRIAL ACTIVATION</b>\n\n"
                    "👤 <b>User:</b> {user_display}\n"
                    "🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
                    "📱 <b>Username:</b> @{username}\n"
                    "👥 <b>Status:</b> {user_status}\n\n"
                    "{promo_block}\n\n"
                    "⏰ <b>Trial parameters:</b>\n"
                    "📅 Period: {trial_days} days\n"
                    "📊 Traffic: {traffic}\n"
                    "📱 Devices: {device_limit}\n"
                    "🌐 Server: {server}\n"
                    "{payment_block}\n\n"
                    "📆 <b>Valid until:</b> {valid_until}\n"
                    "🔗 <b>Referrer:</b> {referrer_info}\n\n"
                    "⏰ <i>{timestamp}</i>"
                ),
            )

            message = template.format(
                user_display=user_display,
                telegram_id=user.telegram_id,
                username=username,
                user_status=user_status,
                promo_block=promo_block,
                trial_days=settings.TRIAL_DURATION_DAYS,
                traffic=self._format_traffic(settings.TRIAL_TRAFFIC_LIMIT_GB),
                device_limit=trial_device_limit,
                server=(
                    subscription.connected_squads[0]
                    if subscription.connected_squads
                    else self.texts.t(
                        "service.notifications.admin.server_default",
                        "Default",
                    )
                ),
                payment_block=payment_block,
                valid_until=format_local_datetime(
                    subscription.end_date, "%d.%m.%Y %H:%M"
                ),
                referrer_info=referrer_info,
                timestamp=format_local_datetime(
                    datetime.utcnow(), "%d.%m.%Y %H:%M:%S"
                ),
            )
            
            return await self._send_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send trial notification: {e}")
            return False
    
    async def send_subscription_purchase_notification(
        self,
        db: AsyncSession,
        user: User,
        subscription: Subscription,
        transaction: Optional[Transaction],
        period_days: int,
        was_trial_conversion: bool = False,
        amount_kopeks: Optional[int] = None,
    ) -> bool:
        try:
            total_amount = amount_kopeks if amount_kopeks is not None else (transaction.amount_kopeks if transaction else 0)

            await self._record_subscription_event(
                db,
                event_type="purchase",
                user=user,
                subscription=subscription,
                transaction=transaction,
                amount_kopeks=total_amount,
                message="Subscription purchase",
                occurred_at=(transaction.completed_at or transaction.created_at) if transaction else datetime.utcnow(),
                extra={
                    "period_days": period_days,
                    "was_trial_conversion": was_trial_conversion,
                    "payment_method": self._get_payment_method_display(transaction.payment_method) if transaction else self.texts.t("service.notifications.admin.payment_method.balance", "Balance"),
                },
            )

            if not self._is_enabled():
                return False

            event_type = (
                "🔄 TRIAL CONVERSION" if was_trial_conversion else "💎 SUBSCRIPTION PURCHASE"
            )

            if was_trial_conversion:
                user_status = "🎯 Trial conversion"
            elif user.has_had_paid_subscription:
                user_status = "🔄 Renewal/Upgrade"
            else:
                user_status = "🆕 First purchase"

            servers_info = await self._get_servers_info(subscription.connected_squads)
            payment_method = self._get_payment_method_display(transaction.payment_method) if transaction else self.texts.t("service.notifications.admin.payment_method.balance", "Balance")
            referrer_info = await self._get_referrer_info(db, user.referred_by_id)
            promo_group = await self._get_user_promo_group(db, user)
            promo_block = self._format_promo_group_block(promo_group)
            user_display = self._get_user_display(user)

            transaction_id = transaction.id if transaction else "—"

            username = getattr(user, "username", None) or self.texts.t(
                "service.notifications.admin.username_missing",
                "not set",
            )

            template = self.texts.t(
                "service.notifications.admin.subscription_purchase",
                (
                    "💎 <b>{event_type}</b>\n\n"
                    "👤 <b>User:</b> {user_display}\n"
                    "🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
                    "📱 <b>Username:</b> @{username}\n"
                    "👥 <b>Status:</b> {user_status}\n\n"
                    "{promo_block}\n\n"
                    "💰 <b>Payment:</b>\n"
                    "💵 Amount: {amount}\n"
                    "💳 Method: {payment_method}\n"
                    "🆔 Transaction ID: {transaction_id}\n\n"
                    "📱 <b>Subscription parameters:</b>\n"
                    "📅 Period: {period_days} days\n"
                    "📊 Traffic: {traffic}\n"
                    "📱 Devices: {device_limit}\n"
                    "🌐 Servers: {servers_info}\n\n"
                    "📆 <b>Valid until:</b> {valid_until}\n"
                    "💰 <b>Balance after purchase:</b> {balance_after}\n"
                    "🔗 <b>Referrer:</b> {referrer_info}\n\n"
                    "⏰ <i>{timestamp}</i>"
                ),
            )

            message = template.format(
                event_type=event_type,
                user_display=user_display,
                telegram_id=user.telegram_id,
                username=username,
                user_status=user_status,
                promo_block=promo_block,
                amount=settings.format_price(total_amount),
                payment_method=payment_method,
                transaction_id=transaction_id,
                period_days=period_days,
                traffic=self._format_traffic(subscription.traffic_limit_gb),
                device_limit=subscription.device_limit,
                servers_info=servers_info,
                valid_until=format_local_datetime(
                    subscription.end_date, "%d.%m.%Y %H:%M"
                ),
                balance_after=settings.format_price(user.balance_kopeks),
                referrer_info=referrer_info,
                timestamp=format_local_datetime(
                    datetime.utcnow(), "%d.%m.%Y %H:%M:%S"
                ),
            )
            
            return await self._send_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send purchase notification: {e}")
            return False

    async def send_version_update_notification(
        self,
        current_version: str,
        latest_version, 
        total_updates: int
    ) -> bool:
        if not self._is_enabled():
            return False
        
        try:
            if latest_version.prerelease:
                update_type = "🧪 PRERELEASE VERSION"
                type_icon = "🧪"
            elif latest_version.is_dev:
                update_type = "🔧 DEV VERSION"
                type_icon = "🔧"
            else:
                update_type = "📦 NEW VERSION"
                type_icon = "📦"
            
            description = latest_version.short_description
            if len(description) > 200:
                description = description[:197] + "..."
            
            repo = getattr(self, "repo", "fr1ngg/remnawave-bedolaga-telegram-bot")
            template = self.texts.t(
                "service.notifications.admin.version_update",
                (
                    "{type_icon} <b>{update_type} AVAILABLE</b>\n\n"
                    "📦 <b>Current version:</b> <code>{current_version}</code>\n"
                    "🆕 <b>New version:</b> <code>{latest_version}</code>\n"
                    "📅 <b>Release date:</b> {release_date}\n\n"
                    "📝 <b>Description:</b>\n"
                    "{description}\n\n"
                    "🔢 <b>Total updates available:</b> {total_updates}\n"
                    "🔗 <b>Repository:</b> https://github.com/{repo}\n\n"
                    "ℹ️ To update, restart the container with a new tag or pull the latest code.\n\n"
                    "⚙️ <i>Automatic update check • {timestamp}</i>"
                ),
            )

            message = template.format(
                type_icon=type_icon,
                update_type=update_type,
                current_version=current_version,
                latest_version=latest_version.tag_name,
                release_date=latest_version.formatted_date,
                description=description,
                total_updates=total_updates,
                repo=repo,
                timestamp=format_local_datetime(
                    datetime.utcnow(), "%d.%m.%Y %H:%M:%S"
                ),
            )
            
            return await self._send_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send version update notification: {e}")
            return False
    
    async def send_version_check_error_notification(
        self,
        error_message: str,
        current_version: str
    ) -> bool:
        if not self._is_enabled():
            return False
        
        try:
            template = self.texts.t(
                "service.notifications.admin.version_check_error",
                (
                    "⚠️ <b>UPDATE CHECK ERROR</b>\n\n"
                    "📦 <b>Current version:</b> <code>{current_version}</code>\n"
                    "❌ <b>Error:</b> {error_message}\n\n"
                    "🔄 Next attempt in one hour.\n"
                    "⚙️ Check GitHub API availability and network settings.\n\n"
                    "⚙️ <i>Automatic update system • {timestamp}</i>"
                ),
            )

            message = template.format(
                current_version=current_version,
                error_message=error_message,
                timestamp=format_local_datetime(
                    datetime.utcnow(), "%d.%m.%Y %H:%M:%S"
                ),
            )
            
            return await self._send_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send version check error notification: {e}")
            return False
    
    def _build_balance_topup_message(
        self,
        user: User,
        transaction: Transaction,
        old_balance: int,
        *,
        topup_status: str,
        referrer_info: str,
        subscription: Subscription | None,
        promo_group: PromoGroup | None,
    ) -> str:
        payment_method = self._get_payment_method_display(transaction.payment_method)
        balance_change = user.balance_kopeks - old_balance
        subscription_status = self._get_subscription_status(subscription)
        promo_block = self._format_promo_group_block(promo_group)
        timestamp = format_local_datetime(datetime.utcnow(), '%d.%m.%Y %H:%M:%S')
        user_display = self._get_user_display(user)

        username = getattr(user, "username", None) or self.texts.t(
            "service.notifications.admin.username_missing",
            "not set",
        )

        template = self.texts.t(
            "service.notifications.admin.balance_topup",
            (
                "💰 <b>BALANCE TOP-UP</b>\n\n"
                "👤 <b>User:</b> {user_display}\n"
                "🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
                "📱 <b>Username:</b> @{username}\n"
                "💳 <b>Status:</b> {topup_status}\n\n"
                "{promo_block}\n\n"
                "💰 <b>Top-up details:</b>\n"
                "💵 Amount: {amount}\n"
                "💳 Method: {payment_method}\n"
                "🆔 Transaction ID: {transaction_id}\n\n"
                "💰 <b>Balance:</b>\n"
                "📉 Before: {balance_before}\n"
                "📈 After: {balance_after}\n"
                "➕ Change: +{balance_change}\n\n"
                "🔗 <b>Referrer:</b> {referrer_info}\n"
                "📱 <b>Subscription:</b> {subscription_status}\n\n"
                "⏰ <i>{timestamp}</i>"
            ),
        )

        return template.format(
            user_display=user_display,
            telegram_id=user.telegram_id,
            username=username,
            topup_status=topup_status,
            promo_block=promo_block,
            amount=settings.format_price(transaction.amount_kopeks),
            payment_method=payment_method,
            transaction_id=transaction.id,
            balance_before=settings.format_price(old_balance),
            balance_after=settings.format_price(user.balance_kopeks),
            balance_change=settings.format_price(balance_change),
            referrer_info=referrer_info,
            subscription_status=subscription_status,
            timestamp=timestamp,
        )

    async def _reload_topup_notification_entities(
        self,
        db: AsyncSession,
        user: User,
        transaction: Transaction,
    ) -> tuple[User, Transaction, Subscription | None, PromoGroup | None]:
        refreshed_user = await get_user_by_id(db, user.id)
        if not refreshed_user:
            raise ValueError(
                f"Failed to reload user {user.id} for top-up notification"
            )

        refreshed_transaction = await get_transaction_by_id(db, transaction.id)
        if not refreshed_transaction:
            raise ValueError(
                f"Failed to reload transaction {transaction.id} for top-up notification"
            )

        subscription = getattr(refreshed_user, "subscription", None)
        promo_group = await self._get_user_promo_group(db, refreshed_user)

        return refreshed_user, refreshed_transaction, subscription, promo_group

    def _is_lazy_loading_error(self, error: Exception) -> bool:
        message = str(error).lower()
        return (
            isinstance(error, MissingGreenlet)
            or "greenlet_spawn" in message
            or "await_only" in message
            or "missinggreenlet" in message
        )


    async def send_balance_topup_notification(
        self,
        user: User,
        transaction: Transaction,
        old_balance: int,
        *,
        topup_status: str,
        referrer_info: str,
        subscription: Subscription | None,
        promo_group: PromoGroup | None,
        db: AsyncSession | None = None,
    ) -> bool:
        logger.info("Starting balance top-up notification")

        if db:
            try:
                await self._record_subscription_event(
                    db,
                    event_type="balance_topup",
                    user=user,
                    subscription=subscription,
                    transaction=transaction,
                    amount_kopeks=transaction.amount_kopeks,
                    message="Balance top-up",
                    occurred_at=transaction.completed_at or transaction.created_at,
                    extra={
                        "status": topup_status,
                        "balance_before": old_balance,
                        "balance_after": user.balance_kopeks,
                        "referrer_info": referrer_info,
                        "promo_group_id": getattr(promo_group, "id", None),
                        "promo_group_name": getattr(promo_group, "name", None),
                    },
                )
            except Exception:
                logger.error(
                    "Failed to save balance top-up event for user %s",
                    getattr(user, "id", "unknown"),
                    exc_info=True,
                )

        if not self._is_enabled():
            return False

        try:
            logger.info("Attempting to create notification message")
            message = self._build_balance_topup_message(
                user,
                transaction,
                old_balance,
                topup_status=topup_status,
                referrer_info=referrer_info,
                subscription=subscription,
                promo_group=promo_group,
            )
            logger.info("Notification message created successfully")
        except Exception as error:
            logger.info(f"Caught error while creating notification message: {type(error).__name__}: {error}")
            if not self._is_lazy_loading_error(error):
                logger.error(
                    "Error preparing top-up notification: %s",
                    error,
                    exc_info=True,
                )
                return False

            if db is None:
                logger.error(
                    "Insufficient data for top-up notification and no DB access: %s",
                    error,
                    exc_info=True,
                )
                return False

            logger.warning(
                "Reloading data for top-up notification after lazy loading error: %s",
                error,
            )

            try:
                logger.info("Attempting to reload notification data")
                (
                    user,
                    transaction,
                    subscription,
                    promo_group,
                ) = await self._reload_topup_notification_entities(db, user, transaction)
                logger.info("Data reloaded successfully")
            except Exception as reload_error:
                logger.error(
                    "Error reloading data for top-up notification: %s",
                    reload_error,
                    exc_info=True,
                )
                return False

            try:
                logger.info("Attempting to create message after data reload")
                message = self._build_balance_topup_message(
                    user,
                    transaction,
                    old_balance,
                    topup_status=topup_status,
                    referrer_info=referrer_info,
                    subscription=subscription,
                    promo_group=promo_group,
                )
                logger.info("Message created successfully after data reload")
            except Exception as rebuild_error:
                logger.error(
                    "Error re-preparing top-up notification after reload: %s",
                    rebuild_error,
                    exc_info=True,
                )
                return False

        try:
            return await self._send_message(message)
        except Exception as e:
            logger.error(
                f"Failed to send top-up notification: {e}",
                exc_info=True,
            )
            return False
    
    async def send_subscription_extension_notification(
        self,
        db: AsyncSession,
        user: User,
        subscription: Subscription,
        transaction: Transaction,
        extended_days: int,
        old_end_date: datetime,
        *,
        new_end_date: datetime | None = None,
        balance_after: int | None = None,
    ) -> bool:
        try:
            current_end_date = new_end_date or subscription.end_date
            current_balance = balance_after if balance_after is not None else user.balance_kopeks

            await self._record_subscription_event(
                db,
                event_type="renewal",
                user=user,
                subscription=subscription,
                transaction=transaction,
                amount_kopeks=transaction.amount_kopeks,
                message="Subscription renewed",
                occurred_at=transaction.completed_at or transaction.created_at,
                extra={
                    "extended_days": extended_days,
                    "previous_end_date": old_end_date.isoformat(),
                    "new_end_date": current_end_date.isoformat(),
                    "payment_method": transaction.payment_method,
                    "balance_after": current_balance,
                },
            )

            if not self._is_enabled():
                return False

            payment_method = self._get_payment_method_display(transaction.payment_method)
            servers_info = await self._get_servers_info(subscription.connected_squads)
            promo_group = await self._get_user_promo_group(db, user)
            promo_block = self._format_promo_group_block(promo_group)
            user_display = self._get_user_display(user)

            username = getattr(user, "username", None) or self.texts.t(
                "service.notifications.admin.username_missing",
                "not set",
            )

            template = self.texts.t(
                "service.notifications.admin.subscription_extension",
                (
                    "⏰ <b>SUBSCRIPTION EXTENSION</b>\n\n"
                    "👤 <b>User:</b> {user_display}\n"
                    "🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
                    "📱 <b>Username:</b> @{username}\n\n"
                    "{promo_block}\n\n"
                    "💰 <b>Payment:</b>\n"
                    "💵 Amount: {amount}\n"
                    "💳 Method: {payment_method}\n"
                    "🆔 Transaction ID: {transaction_id}\n\n"
                    "📅 <b>Extension:</b>\n"
                    "➕ Added days: {extended_days}\n"
                    "📆 Previous end: {old_end}\n"
                    "📆 New end: {new_end}\n\n"
                    "📱 <b>Current parameters:</b>\n"
                    "📊 Traffic: {traffic}\n"
                    "📱 Devices: {device_limit}\n"
                    "🌐 Servers: {servers_info}\n\n"
                    "💰 <b>Balance after operation:</b> {balance_after}\n\n"
                    "⏰ <i>{timestamp}</i>"
                ),
            )

            message = template.format(
                user_display=user_display,
                telegram_id=user.telegram_id,
                username=username,
                promo_block=promo_block,
                amount=settings.format_price(transaction.amount_kopeks),
                payment_method=payment_method,
                transaction_id=transaction.id,
                extended_days=extended_days,
                old_end=format_local_datetime(old_end_date, "%d.%m.%Y %H:%M"),
                new_end=format_local_datetime(current_end_date, "%d.%m.%Y %H:%M"),
                traffic=self._format_traffic(subscription.traffic_limit_gb),
                device_limit=subscription.device_limit,
                servers_info=servers_info,
                balance_after=settings.format_price(current_balance),
                timestamp=format_local_datetime(
                    datetime.utcnow(), "%d.%m.%Y %H:%M:%S"
                ),
            )

            return await self._send_message(message)

        except Exception as e:
            logger.error(f"Failed to send extension notification: {e}")
            return False

    async def send_promocode_activation_notification(
        self,
        db: AsyncSession,
        user: User,
        promocode_data: Dict[str, Any],
        effect_description: str,
        balance_before_kopeks: int | None = None,
        balance_after_kopeks: int | None = None,
    ) -> bool:
        try:
            await self._record_subscription_event(
                db,
                event_type="promocode_activation",
                user=user,
                subscription=None,
                transaction=None,
                amount_kopeks=promocode_data.get("balance_bonus_kopeks"),
                message="Promocode activation",
                occurred_at=datetime.utcnow(),
                extra={
                    "code": promocode_data.get("code"),
                    "type": promocode_data.get("type"),
                    "subscription_days": promocode_data.get("subscription_days"),
                    "balance_bonus_kopeks": promocode_data.get("balance_bonus_kopeks"),
                    "description": effect_description,
                    "valid_until": (
                        promocode_data.get("valid_until").isoformat()
                        if isinstance(promocode_data.get("valid_until"), datetime)
                        else promocode_data.get("valid_until")
                    ),
                    "balance_before_kopeks": balance_before_kopeks,
                    "balance_after_kopeks": balance_after_kopeks,
                },
            )
        except Exception:
            logger.error(
                "Failed to save promocode activation event for user %s",
                getattr(user, "id", "unknown"),
                exc_info=True,
            )

        if not self._is_enabled():
            return False

        try:
            promo_group = await self._get_user_promo_group(db, user)
            promo_block = self._format_promo_group_block(promo_group)
            type_display = self._get_promocode_type_display(promocode_data.get("type"))
            usage_info = f"{promocode_data.get('current_uses', 0)}/{promocode_data.get('max_uses', 0)}"
            user_display = self._get_user_display(user)

            username = getattr(user, "username", None) or self.texts.t(
                "service.notifications.admin.username_missing",
                "not set",
            )

            message_lines = [
                self.texts.t(
                    "service.notifications.admin.promocode_activation.title",
                    "🎫 <b>PROMO CODE ACTIVATION</b>",
                ),
                "",
                self.texts.t(
                    "service.notifications.admin.promocode_activation.user",
                    "👤 <b>User:</b> {user_display}",
                ).format(user_display=user_display),
                self.texts.t(
                    "service.notifications.admin.promocode_activation.telegram_id",
                    "🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>",
                ).format(telegram_id=user.telegram_id),
                self.texts.t(
                    "service.notifications.admin.promocode_activation.username",
                    "📱 <b>Username:</b> @{username}",
                ).format(username=username),
                "",
                promo_block,
                "",
                self.texts.t(
                    "service.notifications.admin.promocode_activation.block_title",
                    "🎟️ <b>Promo code:</b>",
                ),
                self.texts.t(
                    "service.notifications.admin.promocode_activation.code",
                    "🔖 Code: <code>{code}</code>",
                ).format(code=promocode_data.get("code")),
                self.texts.t(
                    "service.notifications.admin.promocode_activation.type",
                    "🧾 Type: {type_display}",
                ).format(type_display=type_display),
                self.texts.t(
                    "service.notifications.admin.promocode_activation.usage",
                    "📊 Usage: {usage_info}",
                ).format(usage_info=usage_info),
            ]

            balance_bonus = promocode_data.get("balance_bonus_kopeks", 0)
            if balance_bonus:
                message_lines.append(
                    self.texts.t(
                        "service.notifications.admin.promocode_activation.balance_bonus",
                        "💰 Balance bonus: {amount}",
                    ).format(amount=settings.format_price(balance_bonus))
                )

            subscription_days = promocode_data.get("subscription_days", 0)
            if subscription_days:
                message_lines.append(
                    self.texts.t(
                        "service.notifications.admin.promocode_activation.subscription_days",
                        "📅 Extra subscription days: {days}",
                    ).format(days=subscription_days)
                )

            valid_until = promocode_data.get("valid_until")
            if valid_until:
                message_lines.append(
                    self.texts.t(
                        "service.notifications.admin.promocode_activation.valid_until",
                        "⏳ Valid until: {valid_until}",
                    ).format(
                        valid_until=format_local_datetime(
                            valid_until, "%d.%m.%Y %H:%M"
                        )
                    )
                    if isinstance(valid_until, datetime)
                    else self.texts.t(
                        "service.notifications.admin.promocode_activation.valid_until",
                        "⏳ Valid until: {valid_until}",
                    ).format(valid_until=valid_until)
                )

            message_lines.extend(
                [
                    "",
                    self.texts.t(
                        "service.notifications.admin.promocode_activation.balance_title",
                        "💼 <b>Balance:</b>",
                    ),
                    (
                        self.texts.t(
                            "service.notifications.admin.promocode_activation.balance_change",
                            "{before} → {after}",
                        ).format(
                            before=settings.format_price(balance_before_kopeks),
                            after=settings.format_price(balance_after_kopeks),
                        )
                        if balance_before_kopeks is not None and balance_after_kopeks is not None
                        else self.texts.t(
                            "service.notifications.admin.promocode_activation.balance_unchanged",
                            "ℹ️ Balance has not changed",
                        )
                    ),
                    "",
                    self.texts.t(
                        "service.notifications.admin.promocode_activation.effect_title",
                        "📝 <b>Effect:</b>",
                    ),
                    effect_description.strip()
                    or self.texts.t(
                        "service.notifications.admin.promocode_activation.effect_default",
                        "✅ Promo code activated",
                    ),
                    "",
                    self.texts.t(
                        "service.notifications.admin.promocode_activation.timestamp",
                        "⏰ <i>{timestamp}</i>",
                    ).format(
                        timestamp=format_local_datetime(
                            datetime.utcnow(), "%d.%m.%Y %H:%M:%S"
                        )
                    ),
                ]
            )

            return await self._send_message("\n".join(message_lines))

        except Exception as e:
            logger.error(f"Failed to send promocode activation notification: {e}")
            return False

    async def send_campaign_link_visit_notification(
        self,
        db: AsyncSession,
        telegram_user: types.User,
        campaign: AdvertisingCampaign,
        user: Optional[User] = None,
    ) -> bool:
        if user:
            try:
                await self._record_subscription_event(
                    db,
                    event_type="referral_link_visit",
                    user=user,
                    subscription=None,
                    transaction=None,
                    amount_kopeks=None,
                    message="Referral link visit",
                    occurred_at=datetime.utcnow(),
                    extra={
                        "campaign_id": campaign.id,
                        "campaign_name": campaign.name,
                        "start_parameter": campaign.start_parameter,
                        "was_registered": bool(user),
                    },
                )
            except Exception:
                logger.error(
                    "Failed to save campaign link visit event for user %s",
                    getattr(user, "id", "unknown"),
                    exc_info=True,
                )

        if not self._is_enabled():
            return False

        try:
            user_status = (
                self.texts.t("service.notifications.admin.campaign_visit.new_user", "🆕 New user")
                if not user
                else self.texts.t("service.notifications.admin.campaign_visit.existing_user", "👥 Already registered")
            )
            promo_block = (
                self._format_promo_group_block(await self._get_user_promo_group(db, user))
                if user
                else self._format_promo_group_block(None)
            )

            full_name = telegram_user.full_name or telegram_user.username or str(telegram_user.id)
            username = (
                f"@{telegram_user.username}"
                if telegram_user.username
                else self.texts.t("service.notifications.admin.username_missing", "not set")
            )

            template = self.texts.t(
                "service.notifications.admin.campaign_visit",
                (
                    "📣 <b>ADVERTISING CAMPAIGN VISIT</b>\n\n"
                    "🧾 <b>Campaign:</b> {campaign_name}\n"
                    "🆔 Campaign ID: {campaign_id}\n"
                    "🔗 Start parameter: <code>{start_parameter}</code>\n\n"
                    "👤 <b>User:</b> {full_name}\n"
                    "🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
                    "📱 <b>Username:</b> {username}\n"
                    "{user_status}\n\n"
                    "{promo_block}\n\n"
                    "🎯 <b>Campaign bonus:</b>\n"
                    "{bonus_lines}\n\n"
                    "⏰ <i>{timestamp}</i>"
                ),
            )

            bonus_lines = "\n".join(self._format_campaign_bonus(campaign))
            message = template.format(
                campaign_name=campaign.name,
                campaign_id=campaign.id,
                start_parameter=campaign.start_parameter,
                full_name=full_name,
                telegram_id=telegram_user.id,
                username=username,
                user_status=user_status,
                promo_block=promo_block,
                bonus_lines=bonus_lines,
                timestamp=format_local_datetime(datetime.utcnow(), "%d.%m.%Y %H:%M:%S"),
            )

            return await self._send_message(message)

        except Exception as e:
            logger.error(f"Failed to send campaign visit notification: {e}")
            return False

    async def send_user_promo_group_change_notification(
        self,
        db: AsyncSession,
        user: User,
        old_group: Optional[PromoGroup],
        new_group: PromoGroup,
        *,
        reason: Optional[str] = None,
        initiator: Optional[User] = None,
        automatic: bool = False,
    ) -> bool:
        try:
            await self._record_subscription_event(
                db,
                event_type="promo_group_change",
                user=user,
                subscription=None,
                transaction=None,
                message="Promo group change",
                occurred_at=datetime.utcnow(),
                extra={
                    "old_group_id": getattr(old_group, "id", None),
                    "old_group_name": getattr(old_group, "name", None),
                    "new_group_id": new_group.id,
                    "new_group_name": new_group.name,
                    "reason": reason,
                    "initiator_id": getattr(initiator, "id", None),
                    "initiator_telegram_id": getattr(initiator, "telegram_id", None),
                    "automatic": automatic,
                },
            )
        except Exception:
            logger.error(
                "Failed to save promo group change event for user %s",
                getattr(user, "id", "unknown"),
                exc_info=True,
            )

        if not self._is_enabled():
            return False

        try:
            title = (
                self.texts.t(
                    "service.notifications.admin.promo_group_change.auto",
                    "🤖 AUTOMATIC PROMO GROUP CHANGE"
                )
                if automatic
                else self.texts.t(
                    "service.notifications.admin.promo_group_change.manual",
                    "👥 PROMO GROUP CHANGE"
                )
            )
            initiator_line = None
            if initiator:
                initiator_line = self.texts.t(
                    "service.notifications.admin.promo_group_change.initiator",
                    "👮 <b>Initiator:</b> {name} (ID: {id})"
                ).format(name=initiator.full_name, id=initiator.telegram_id)
            elif automatic:
                initiator_line = self.texts.t(
                    "service.notifications.admin.promo_group_change.auto_assignment",
                    "🤖 Automatic assignment"
                )
            user_display = self._get_user_display(user)

            username = getattr(user, "username", None) or self.texts.t(
                "service.notifications.admin.username_missing",
                "not set",
            )

            new_group_title = self.texts.t(
                "service.notifications.admin.promo_group_change.new_group",
                "New promo group"
            )
            old_group_title = self.texts.t(
                "service.notifications.admin.promo_group_change.old_group",
                "Previous promo group"
            )

            template = self.texts.t(
                "service.notifications.admin.promo_group_change",
                (
                    "{title}\n\n"
                    "👤 <b>User:</b> {user_display}\n"
                    "🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
                    "📱 <b>Username:</b> @{username}\n\n"
                    "{new_group_block}\n"
                    "{old_group_block}\n"
                    "{initiator_line}\n"
                    "{reason_line}\n\n"
                    "💰 <b>User balance:</b> {balance}\n"
                    "⏰ <i>{timestamp}</i>"
                ),
            )

            old_group_block = ""
            if old_group and old_group.id != new_group.id:
                old_group_block = "\n\n" + self._format_promo_group_block(
                    old_group, title=old_group_title, icon="♻️"
                )

            reason_line = ""
            if reason:
                reason_line = "\n" + self.texts.t(
                    "service.notifications.admin.promo_group_change.reason",
                    "📝 Reason: {reason}"
                ).format(reason=reason)

            message = template.format(
                title=title,
                user_display=user_display,
                telegram_id=user.telegram_id,
                username=username,
                new_group_block=self._format_promo_group_block(
                    new_group, title=new_group_title, icon="🏆"
                ),
                old_group_block=old_group_block,
                initiator_line=("\n" + initiator_line) if initiator_line else "",
                reason_line=reason_line,
                balance=settings.format_price(user.balance_kopeks),
                timestamp=format_local_datetime(datetime.utcnow(), "%d.%m.%Y %H:%M:%S"),
            )

            return await self._send_message(message)

        except Exception as e:
            logger.error(f"Failed to send promo group change notification: {e}")
            return False

    async def _send_message(self, text: str, reply_markup: types.InlineKeyboardMarkup | None = None, *, ticket_event: bool = False) -> bool:
        if not self.chat_id:
            logger.warning("ADMIN_NOTIFICATIONS_CHAT_ID not configured")
            return False
        
        try:
            message_kwargs = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            # route to ticket-specific topic if provided
            thread_id = None
            if ticket_event and self.ticket_topic_id:
                thread_id = self.ticket_topic_id
            elif self.topic_id:
                thread_id = self.topic_id
            if thread_id:
                message_kwargs['message_thread_id'] = thread_id
            if reply_markup is not None:
                message_kwargs['reply_markup'] = reply_markup
            
            await self.bot.send_message(**message_kwargs)
            logger.info(f"Notification sent to chat {self.chat_id}")
            return True
            
        except TelegramForbiddenError:
            logger.error(f"Bot does not have permission to send to chat {self.chat_id}")
            return False
        except TelegramBadRequest as e:
            logger.error(f"Error sending notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending notification: {e}")
            return False
    
    def _is_enabled(self) -> bool:
        return self.enabled and bool(self.chat_id)
    
    def _get_payment_method_display(self, payment_method: Optional[str]) -> str:
        mulenpay_name = settings.get_mulenpay_display_name()
        method_names = {
            'telegram_stars': '⭐ Telegram Stars',
            'yookassa': self.texts.t("service.notifications.admin.payment_method.yookassa", "💳 YooKassa (card)"),
            'tribute': self.texts.t("service.notifications.admin.payment_method.tribute", "💎 Tribute (card)"),
            'mulenpay': self.texts.t(
                "service.notifications.admin.payment_method.mulenpay",
                "💳 {name} (card)"
            ).format(name=mulenpay_name),
            'pal24': self.texts.t("service.notifications.admin.payment_method.pal24", "🏦 PayPalych (SBP)"),
            'manual': self.texts.t("service.notifications.admin.payment_method.manual", "🛠️ Manual (admin)"),
            'balance': self.texts.t("service.notifications.admin.payment_method.balance", "💰 From balance")
        }
        
        default = self.texts.t("service.notifications.admin.payment_method.balance", "💰 From balance")
        if not payment_method:
            return default
            
        return method_names.get(payment_method, default)
    
    def _format_traffic(self, traffic_gb: int) -> str:
        if traffic_gb == 0:
            return self.texts.t("service.notifications.admin.traffic_unlimited", "∞ Unlimited")
        return self.texts.t("service.notifications.admin.traffic_gb", "{gb} GB").format(gb=traffic_gb)
    
    def _get_subscription_status(self, subscription: Optional[Subscription]) -> str:
        if not subscription:
            return self.texts.t("service.notifications.admin.subscription_status.none", "❌ No subscription")

        if subscription.is_trial:
            return self.texts.t(
                "service.notifications.admin.subscription_status.trial",
                "🎯 Trial (until {date})"
            ).format(date=format_local_datetime(subscription.end_date, "%d.%m"))
        elif subscription.is_active:
            return self.texts.t(
                "service.notifications.admin.subscription_status.active",
                "✅ Active (until {date})"
            ).format(date=format_local_datetime(subscription.end_date, "%d.%m"))
        else:
            return self.texts.t("service.notifications.admin.subscription_status.inactive", "❌ Inactive")
    
    async def _get_servers_info(self, squad_uuids: list) -> str:
        if not squad_uuids:
            return self.texts.t("service.notifications.admin.servers_none", "❌ No servers")
        
        try:
            from app.handlers.subscription import get_servers_display_names
            servers_names = await get_servers_display_names(squad_uuids)
            return self.texts.t(
                "service.notifications.admin.servers_with_names",
                "{count} pcs. ({names})"
            ).format(count=len(squad_uuids), names=servers_names)
        except Exception as e:
            logger.warning(f"Failed to get server names: {e}")
            return self.texts.t(
                "service.notifications.admin.servers_count",
                "{count} pcs."
            ).format(count=len(squad_uuids))


    async def send_maintenance_status_notification(
        self,
        event_type: str,
        status: str,
        details: Dict[str, Any] = None
    ) -> bool:
        if not self._is_enabled():
            return False
        
        try:
            details = details or {}
            
            if event_type == "enable":
                if details.get("auto_enabled", False):
                    icon = "⚠️"
                    title = self.texts.t("service.notifications.admin.maintenance.enable.auto", "AUTOMATIC MAINTENANCE ENABLED")
                else:
                    icon = "🔧"
                    title = self.texts.t("service.notifications.admin.maintenance.enable.manual", "MAINTENANCE ENABLED")
                    
            elif event_type == "disable":
                icon = "✅"
                title = self.texts.t("service.notifications.admin.maintenance.disable", "MAINTENANCE DISABLED")
                
            elif event_type == "api_status":
                if status == "online":
                    icon = "🟢"
                    title = self.texts.t("service.notifications.admin.maintenance.api.online", "API REMNAWAVE RESTORED")
                else:
                    icon = "🔴"
                    title = self.texts.t("service.notifications.admin.maintenance.api.offline", "API REMNAWAVE UNAVAILABLE")
                    
            elif event_type == "monitoring":
                if status == "started":
                    icon = "🔍"
                    title = self.texts.t("service.notifications.admin.maintenance.monitoring.started", "MONITORING STARTED")
                else:
                    icon = "⏹️"
                    title = self.texts.t("service.notifications.admin.maintenance.monitoring.stopped", "MONITORING STOPPED")
            else:
                icon = "ℹ️"
                title = self.texts.t("service.notifications.admin.maintenance.system", "MAINTENANCE SYSTEM")
            
            message_parts = [f"{icon} <b>{title}</b>", ""]
            
            if event_type == "enable":
                if details.get("reason"):
                    message_parts.append(
                        self.texts.t("service.notifications.admin.maintenance.reason", "📋 <b>Reason:</b> {reason}").format(reason=details['reason'])
                    )
                
                if details.get("enabled_at"):
                    enabled_at = details["enabled_at"]
                    if isinstance(enabled_at, str):
                        from datetime import datetime
                        enabled_at = datetime.fromisoformat(enabled_at)
                    message_parts.append(
                        self.texts.t(
                            "service.notifications.admin.maintenance.enabled_at",
                            "🕐 <b>Enabled at:</b> {time}"
                        ).format(time=format_local_datetime(enabled_at, '%d.%m.%Y %H:%M:%S'))
                    )
                
                auto_text = self.texts.t("service.notifications.admin.yes", "Yes") if details.get('auto_enabled', False) else self.texts.t("service.notifications.admin.no", "No")
                message_parts.append(
                    self.texts.t("service.notifications.admin.maintenance.automatic", "🤖 <b>Automatic:</b> {auto}").format(auto=auto_text)
                )
                message_parts.append("")
                message_parts.append(self.texts.t("service.notifications.admin.maintenance.users_blocked", "❗ Regular users temporarily cannot use the bot."))
                
            elif event_type == "disable":
                if details.get("disabled_at"):
                    disabled_at = details["disabled_at"]
                    if isinstance(disabled_at, str):
                        from datetime import datetime
                        disabled_at = datetime.fromisoformat(disabled_at)
                    message_parts.append(
                        self.texts.t(
                            "service.notifications.admin.maintenance.disabled_at",
                            "🕐 <b>Disabled at:</b> {time}"
                        ).format(time=format_local_datetime(disabled_at, '%d.%m.%Y %H:%M:%S'))
                    )
                
                if details.get("duration"):
                    duration = details["duration"]
                    if isinstance(duration, (int, float)):
                        hours = int(duration // 3600)
                        minutes = int((duration % 3600) // 60)
                        if hours > 0:
                            duration_str = self.texts.t("service.notifications.admin.duration.hours_minutes", "{hours}h {minutes}min").format(hours=hours, minutes=minutes)
                        else:
                            duration_str = self.texts.t("service.notifications.admin.duration.minutes", "{minutes}min").format(minutes=minutes)
                        message_parts.append(
                            self.texts.t("service.notifications.admin.maintenance.duration", "⏱️ <b>Duration:</b> {duration}").format(duration=duration_str)
                        )
                
                was_auto_text = self.texts.t("service.notifications.admin.yes", "Yes") if details.get('was_auto', False) else self.texts.t("service.notifications.admin.no", "No")
                message_parts.append(
                    self.texts.t("service.notifications.admin.maintenance.was_auto", "🤖 <b>Was automatic:</b> {was_auto}").format(was_auto=was_auto_text)
                )
                message_parts.append("")
                message_parts.append(self.texts.t("service.notifications.admin.maintenance.service_available", "✅ Service is available again for users."))
                
            elif event_type == "api_status":
                api_url = details.get('api_url', self.texts.t("service.notifications.admin.unknown", "unknown"))
                message_parts.append(
                    self.texts.t("service.notifications.admin.maintenance.api_url", "🔗 <b>API URL:</b> {url}").format(url=api_url)
                )
                
                if status == "online":
                    if details.get("response_time"):
                        message_parts.append(
                            self.texts.t("service.notifications.admin.maintenance.response_time", "⚡ <b>Response time:</b> {time} sec").format(time=details['response_time'])
                        )
                        
                    if details.get("consecutive_failures", 0) > 0:
                        message_parts.append(
                            self.texts.t("service.notifications.admin.maintenance.failures_was", "🔄 <b>Failed attempts were:</b> {count}").format(count=details['consecutive_failures'])
                        )
                        
                    message_parts.append("")
                    message_parts.append(self.texts.t("service.notifications.admin.maintenance.api_responding", "API is responding to requests again."))
                    
                else: 
                    if details.get("consecutive_failures"):
                        message_parts.append(
                            self.texts.t("service.notifications.admin.maintenance.attempt_number", "🔄 <b>Attempt #:</b> {count}").format(count=details['consecutive_failures'])
                        )
                        
                    if details.get("error"):
                        error_msg = str(details["error"])[:100]  
                        message_parts.append(
                            self.texts.t("service.notifications.admin.maintenance.error", "❌ <b>Error:</b> {error}").format(error=error_msg)
                        )
                        
                    message_parts.append("")
                    message_parts.append(self.texts.t("service.notifications.admin.maintenance.api_failures_started", "⚠️ A series of failed API checks has started."))
                    
            elif event_type == "monitoring":
                if status == "started":
                    if details.get("check_interval"):
                        message_parts.append(
                            self.texts.t("service.notifications.admin.maintenance.check_interval", "🔄 <b>Check interval:</b> {interval} sec").format(interval=details['check_interval'])
                        )
                        
                    if details.get("auto_enable_configured") is not None:
                        auto_enable = self.texts.t("service.notifications.admin.enabled", "Enabled") if details["auto_enable_configured"] else self.texts.t("service.notifications.admin.disabled", "Disabled")
                        message_parts.append(
                            self.texts.t("service.notifications.admin.maintenance.auto_enable", "🤖 <b>Auto-enable:</b> {auto_enable}").format(auto_enable=auto_enable)
                        )
                        
                    if details.get("max_failures"):
                        message_parts.append(
                            self.texts.t("service.notifications.admin.maintenance.max_failures", "🎯 <b>Error threshold:</b> {max}").format(max=details['max_failures'])
                        )
                        
                    message_parts.append("")
                    message_parts.append(self.texts.t("service.notifications.admin.maintenance.monitoring_will_watch", "System will monitor API availability."))
                    
                else:  
                    message_parts.append(self.texts.t("service.notifications.admin.maintenance.monitoring_stopped", "Automatic API monitoring stopped."))
            
            message_parts.append("")
            message_parts.append(
                f"⏰ <i>{format_local_datetime(datetime.utcnow(), '%d.%m.%Y %H:%M:%S')}</i>"
            )
            
            message = "\n".join(message_parts)
            
            return await self._send_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send maintenance notification: {e}")
            return False
    
    async def send_remnawave_panel_status_notification(
        self,
        status: str,
        details: Dict[str, Any] = None
    ) -> bool:
        if not self._is_enabled():
            return False
        
        try:
            details = details or {}
            
            status_config = {
                "online": {"icon": "🟢", "title": self.texts.t("service.notifications.admin.panel_status.online", "REMNAWAVE PANEL AVAILABLE"), "alert_type": "success"},
                "offline": {"icon": "🔴", "title": self.texts.t("service.notifications.admin.panel_status.offline", "REMNAWAVE PANEL UNAVAILABLE"), "alert_type": "error"},
                "degraded": {"icon": "🟡", "title": self.texts.t("service.notifications.admin.panel_status.degraded", "REMNAWAVE PANEL WORKING WITH ISSUES"), "alert_type": "warning"},
                "maintenance": {"icon": "🔧", "title": self.texts.t("service.notifications.admin.panel_status.maintenance", "REMNAWAVE PANEL UNDER MAINTENANCE"), "alert_type": "info"}
            }
            
            config = status_config.get(status, status_config["offline"])
            
            message_parts = [
                f"{config['icon']} <b>{config['title']}</b>",
                ""
            ]
            
            if details.get("api_url"):
                message_parts.append(f"🔗 <b>URL:</b> {details['api_url']}")
                
            if details.get("response_time"):
                message_parts.append(
                    self.texts.t("service.notifications.admin.panel_status.response_time", "⚡ <b>Response time:</b> {time} sec").format(time=details['response_time'])
                )
                
            if details.get("last_check"):
                last_check = details["last_check"]
                if isinstance(last_check, str):
                    from datetime import datetime
                    last_check = datetime.fromisoformat(last_check)
                message_parts.append(
                    self.texts.t(
                        "service.notifications.admin.panel_status.last_check",
                        "🕐 <b>Last check:</b> {time}"
                    ).format(time=format_local_datetime(last_check, '%H:%M:%S'))
                )
                
            if status == "online":
                if details.get("uptime"):
                    message_parts.append(
                        self.texts.t("service.notifications.admin.panel_status.uptime", "⏱️ <b>Uptime:</b> {uptime}").format(uptime=details['uptime'])
                    )
                    
                if details.get("users_online"):
                    message_parts.append(
                        self.texts.t("service.notifications.admin.panel_status.users_online", "👥 <b>Users online:</b> {count}").format(count=details['users_online'])
                    )
                    
                message_parts.append("")
                message_parts.append(self.texts.t("service.notifications.admin.panel_status.all_systems_ok", "✅ All systems working normally."))
                
            elif status == "offline":
                if details.get("error"):
                    error_msg = str(details["error"])[:150]
                    message_parts.append(
                        self.texts.t("service.notifications.admin.panel_status.error", "❌ <b>Error:</b> {error}").format(error=error_msg)
                    )
                    
                if details.get("consecutive_failures"):
                    message_parts.append(
                        self.texts.t("service.notifications.admin.panel_status.failed_attempts", "🔄 <b>Failed attempts:</b> {count}").format(count=details['consecutive_failures'])
                    )
                    
                message_parts.append("")
                message_parts.append(self.texts.t("service.notifications.admin.panel_status.unavailable", "⚠️ Panel unavailable. Check connection and server status."))
                
            elif status == "degraded":
                if details.get("issues"):
                    issues = details["issues"]
                    if isinstance(issues, list):
                        message_parts.append(self.texts.t("service.notifications.admin.panel_status.issues_detected", "⚠️ <b>Detected issues:</b>"))
                        for issue in issues[:3]: 
                            message_parts.append(f"   • {issue}")
                    else:
                        message_parts.append(
                            self.texts.t("service.notifications.admin.panel_status.issue", "⚠️ <b>Issue:</b> {issue}").format(issue=issues)
                        )
                        
                message_parts.append("")
                message_parts.append(self.texts.t("service.notifications.admin.panel_status.degraded_message", "Panel is working but delays or failures may occur."))
                
            elif status == "maintenance":
                if details.get("maintenance_reason"):
                    message_parts.append(
                        self.texts.t("service.notifications.admin.panel_status.maintenance_reason", "🔧 <b>Reason:</b> {reason}").format(reason=details['maintenance_reason'])
                    )
                    
                if details.get("estimated_duration"):
                    message_parts.append(
                        self.texts.t("service.notifications.admin.panel_status.estimated_duration", "⏰ <b>Estimated duration:</b> {duration}").format(duration=details['estimated_duration'])
                    )
                    
                message_parts.append("")
                message_parts.append(self.texts.t("service.notifications.admin.panel_status.maintenance_message", "Panel temporarily unavailable for maintenance."))
            
            message_parts.append("")
            message_parts.append(
                f"⏰ <i>{format_local_datetime(datetime.utcnow(), '%d.%m.%Y %H:%M:%S')}</i>"
            )
            
            message = "\n".join(message_parts)
            
            return await self._send_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send Remnawave panel status notification: {e}")
            return False

    async def send_subscription_update_notification(
        self,
        db: AsyncSession,
        user: User,
        subscription: Subscription,
        update_type: str,
        old_value: Any,
        new_value: Any,
        price_paid: int = 0
    ) -> bool:
        if not self._is_enabled():
            return False
        
        try:
            referrer_info = await self._get_referrer_info(db, user.referred_by_id)
            promo_group = await self._get_user_promo_group(db, user)
            promo_block = self._format_promo_group_block(promo_group)
            user_display = self._get_user_display(user)

            update_types = {
                "traffic": (
                    self.texts.t("service.notifications.admin.subscription_update.traffic.title", "📊 TRAFFIC CHANGE"),
                    self.texts.t("service.notifications.admin.subscription_update.traffic.param", "traffic")
                ),
                "devices": (
                    self.texts.t("service.notifications.admin.subscription_update.devices.title", "📱 DEVICE COUNT CHANGE"),
                    self.texts.t("service.notifications.admin.subscription_update.devices.param", "device count")
                ),
                "servers": (
                    self.texts.t("service.notifications.admin.subscription_update.servers.title", "🌐 SERVER CHANGE"),
                    self.texts.t("service.notifications.admin.subscription_update.servers.param", "servers")
                )
            }

            title, param_name = update_types.get(
                update_type,
                (
                    self.texts.t("service.notifications.admin.subscription_update.generic.title", "⚙️ SUBSCRIPTION CHANGE"),
                    self.texts.t("service.notifications.admin.subscription_update.generic.param", "parameters")
                )
            )

            username = getattr(user, "username", None) or self.texts.t(
                "service.notifications.admin.username_missing",
                "not set",
            )

            template = self.texts.t(
                "service.notifications.admin.subscription_update",
                (
                    "{title}\n\n"
                    "👤 <b>User:</b> {user_display}\n"
                    "🆔 <b>Telegram ID:</b> <code>{telegram_id}</code>\n"
                    "📱 <b>Username:</b> @{username}\n\n"
                    "{promo_block}\n\n"
                    "🔧 <b>Change:</b>\n"
                    "📋 Parameter: {param_name}\n"
                    "{old_new_values}\n"
                    "{price_line}\n\n"
                    "📅 <b>Subscription valid until:</b> {valid_until}\n"
                    "💰 <b>Balance after operation:</b> {balance_after}\n"
                    "🔗 <b>Referrer:</b> {referrer_info}\n\n"
                    "⏰ <i>{timestamp}</i>"
                ),
            )

            if update_type == "servers":
                old_servers_info = await self._format_servers_detailed(old_value)
                new_servers_info = await self._format_servers_detailed(new_value)
                old_new_values = (
                    self.texts.t("service.notifications.admin.subscription_update.old", "📉 Before: {old}").format(old=old_servers_info) + "\n" +
                    self.texts.t("service.notifications.admin.subscription_update.new", "📈 After: {new}").format(new=new_servers_info)
                )
            else:
                old_val = self._format_update_value(old_value, update_type)
                new_val = self._format_update_value(new_value, update_type)
                old_new_values = (
                    self.texts.t("service.notifications.admin.subscription_update.old", "📉 Before: {old}").format(old=old_val) + "\n" +
                    self.texts.t("service.notifications.admin.subscription_update.new", "📈 After: {new}").format(new=new_val)
                )

            price_line = (
                self.texts.t("service.notifications.admin.subscription_update.price_paid", "💰 Extra paid: {price}").format(price=settings.format_price(price_paid))
                if price_paid > 0
                else self.texts.t("service.notifications.admin.subscription_update.free", "💸 Free")
            )

            message = template.format(
                title=title,
                user_display=user_display,
                telegram_id=user.telegram_id,
                username=username,
                promo_block=promo_block,
                param_name=param_name,
                old_new_values=old_new_values,
                price_line=price_line,
                valid_until=format_local_datetime(subscription.end_date, "%d.%m.%Y %H:%M"),
                balance_after=settings.format_price(user.balance_kopeks),
                referrer_info=referrer_info,
                timestamp=format_local_datetime(datetime.utcnow(), "%d.%m.%Y %H:%M:%S"),
            )

            return await self._send_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send subscription update notification: {e}")
            return False

    async def _format_servers_detailed(self, server_uuids: List[str]) -> str:
        if not server_uuids:
            return self.texts.t("service.notifications.admin.servers_none", "No servers")
        
        try:
            from app.handlers.subscription import get_servers_display_names
            servers_names = await get_servers_display_names(server_uuids)
            
            none_text = self.texts.t("service.notifications.admin.servers_none", "No servers")
            if servers_names and servers_names != none_text:
                return self.texts.t(
                    "service.notifications.admin.servers_detailed_with_names",
                    "{count} servers ({names})"
                ).format(count=len(server_uuids), names=servers_names)
            else:
                return self.texts.t(
                    "service.notifications.admin.servers_detailed_count",
                    "{count} servers"
                ).format(count=len(server_uuids))
                
        except Exception as e:
            logger.warning(f"Error getting server names for notification: {e}")
            return self.texts.t(
                "service.notifications.admin.servers_detailed_count",
                "{count} servers"
            ).format(count=len(server_uuids))

    def _format_update_value(self, value: Any, update_type: str) -> str:
        if update_type == "traffic":
            if value == 0:
                return self.texts.t("service.notifications.admin.traffic_unlimited", "∞ Unlimited")
            return self.texts.t("service.notifications.admin.traffic_gb", "{gb} GB").format(gb=value)
        elif update_type == "devices":
            return self.texts.t("service.notifications.admin.devices_count", "{count} devices").format(count=value)
        elif update_type == "servers":
            if isinstance(value, list):
                return self.texts.t("service.notifications.admin.servers_detailed_count", "{count} servers").format(count=len(value))
            return str(value)
        return str(value)

    async def send_ticket_event_notification(
        self,
        text: str,
        keyboard: types.InlineKeyboardMarkup | None = None
    ) -> bool:
        """Public method for sending ticket notifications to admin topic.
        Respects enabled settings in settings.
        """
        # Respect runtime toggle for admin ticket notifications
        try:
            from app.services.support_settings_service import SupportSettingsService
            runtime_enabled = SupportSettingsService.get_admin_ticket_notifications_enabled()
        except Exception:
            runtime_enabled = True
        if not (self._is_enabled() and runtime_enabled):
            return False
        return await self._send_message(text, reply_markup=keyboard, ticket_event=True)
