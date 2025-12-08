import logging
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
import redis.asyncio as redis

from app.config import settings
from app.middlewares.global_error import GlobalErrorMiddleware 
from app.middlewares.auth import AuthMiddleware
from app.middlewares.logging import LoggingMiddleware
from app.middlewares.throttling import ThrottlingMiddleware
from app.middlewares.subscription_checker import SubscriptionStatusMiddleware
from app.middlewares.maintenance import MaintenanceMiddleware
from app.middlewares.display_name_restriction import DisplayNameRestrictionMiddleware
from app.services.maintenance_service import maintenance_service
from app.utils.cache import cache 

from app.handlers import (
    start,
    menu,
    subscription,
    balance,
    promocode,
    referral,
    support,
    server_status,
    common,
    tickets,
)
from app.handlers import polls as user_polls
from app.handlers import simple_subscription
from app.handlers.admin import (
    main as admin_main,
    users as admin_users,
    subscriptions as admin_subscriptions,
    promocodes as admin_promocodes,
    messages as admin_messages,
    monitoring as admin_monitoring,
    referrals as admin_referrals,
    rules as admin_rules,
    remnawave as admin_remnawave,
    statistics as admin_statistics,
    polls as admin_polls,
    servers as admin_servers,
    maintenance as admin_maintenance,
    promo_groups as admin_promo_groups,
    campaigns as admin_campaigns,
    promo_offers as admin_promo_offers,
    user_messages as admin_user_messages,
    updates as admin_updates,
    backup as admin_backup,
    system_logs as admin_system_logs,
    welcome_text as admin_welcome_text,
    tickets as admin_tickets,
    reports as admin_reports,
    bot_configuration as admin_bot_configuration,
    pricing as admin_pricing,
    privacy_policy as admin_privacy_policy,
    public_offer as admin_public_offer,
    faq as admin_faq,
    payments as admin_payments,
    trials as admin_trials,
)
from app.handlers.stars_payments import register_stars_handlers

from app.utils.message_patch import patch_message_methods

patch_message_methods()

logger = logging.getLogger(__name__)


async def debug_callback_handler(callback: types.CallbackQuery):
    logger.info("🔍 DEBUG CALLBACK:")
    logger.info("  - Data: %s", callback.data)
    logger.info("  - User: %s", callback.from_user.id)
    logger.info("  - Username: %s", callback.from_user.username)


async def setup_bot() -> tuple[Bot, Dispatcher]:
    
    try:
        await cache.connect()
        logger.info("Cache initialized")
    except Exception as e:
        logger.warning("Cache initialization failed: %s", e)
    
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    bot = Bot(
        token=settings.BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    maintenance_service.set_bot(bot)
    logger.info("Bot set in maintenance_service")
    
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        storage = RedisStorage(redis_client)
        logger.info("Connected to Redis for FSM storage")
    except Exception as e:
        logger.warning("Failed to connect to Redis: %s", e)
        logger.info("Using MemoryStorage for FSM")
        storage = MemoryStorage()
    
    
    dp = Dispatcher(storage=storage)

    dp.message.middleware(GlobalErrorMiddleware())
    dp.callback_query.middleware(GlobalErrorMiddleware())
    dp.pre_checkout_query.middleware(GlobalErrorMiddleware())
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.message.middleware(MaintenanceMiddleware())
    dp.callback_query.middleware(MaintenanceMiddleware())
    display_name_middleware = DisplayNameRestrictionMiddleware()
    dp.message.middleware(display_name_middleware)
    dp.callback_query.middleware(display_name_middleware)
    dp.pre_checkout_query.middleware(display_name_middleware)
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())

    if settings.CHANNEL_IS_REQUIRED_SUB:
        from app.middlewares.channel_checker import ChannelCheckerMiddleware

        channel_checker_middleware = ChannelCheckerMiddleware()
        dp.message.middleware(channel_checker_middleware)
        dp.callback_query.middleware(channel_checker_middleware)
        logger.info("🔒 Mandatory channel subscription enabled - ChannelCheckerMiddleware activated")
    else:
        logger.info("🔓 Mandatory channel subscription disabled - ChannelCheckerMiddleware not registered")
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.pre_checkout_query.middleware(AuthMiddleware())
    dp.message.middleware(SubscriptionStatusMiddleware())
    dp.callback_query.middleware(SubscriptionStatusMiddleware())
    start.register_handlers(dp)
    menu.register_handlers(dp)
    subscription.register_handlers(dp)
    balance.register_balance_handlers(dp)
    promocode.register_handlers(dp)
    referral.register_handlers(dp)
    support.register_handlers(dp)
    server_status.register_handlers(dp)
    tickets.register_handlers(dp)
    admin_main.register_handlers(dp)
    admin_users.register_handlers(dp)
    admin_subscriptions.register_handlers(dp)
    admin_servers.register_handlers(dp)  
    admin_promocodes.register_handlers(dp)
    admin_messages.register_handlers(dp)
    admin_monitoring.register_handlers(dp)
    admin_referrals.register_handlers(dp)
    admin_rules.register_handlers(dp)
    admin_remnawave.register_handlers(dp)
    admin_statistics.register_handlers(dp)
    admin_polls.register_handlers(dp)
    admin_promo_groups.register_handlers(dp)
    admin_campaigns.register_handlers(dp)
    admin_promo_offers.register_handlers(dp)
    admin_maintenance.register_handlers(dp)
    admin_user_messages.register_handlers(dp)
    admin_updates.register_handlers(dp)
    admin_backup.register_handlers(dp)
    admin_system_logs.register_handlers(dp)
    admin_welcome_text.register_welcome_text_handlers(dp)
    admin_tickets.register_handlers(dp)
    admin_reports.register_handlers(dp)
    admin_bot_configuration.register_handlers(dp)
    admin_pricing.register_handlers(dp)
    admin_privacy_policy.register_handlers(dp)
    admin_public_offer.register_handlers(dp)
    admin_faq.register_handlers(dp)
    admin_payments.register_handlers(dp)
    admin_trials.register_handlers(dp)
    common.register_handlers(dp)
    register_stars_handlers(dp)
    user_polls.register_handlers(dp)
    simple_subscription.register_simple_subscription_handlers(dp)
    logger.info("⭐ Telegram Stars payment handlers registered")
    logger.info("⚡ Simple purchase handlers registered")
    logger.info("⚡ Simple subscription handlers registered")
    
    if settings.is_maintenance_monitoring_enabled():
        try:
            await maintenance_service.start_monitoring()
            logger.info("Maintenance monitoring started")
        except Exception as e:
            logger.error("Failed to start maintenance monitoring: %s", e)
    else:
        logger.info("Maintenance monitoring disabled by settings")
    
    logger.info("🛡️ GlobalErrorMiddleware enabled - bot protected from stale callback queries")
    logger.info("Bot successfully configured")
    
    return bot, dp


async def shutdown_bot():
    try:
        await maintenance_service.stop_monitoring()
        logger.info("Maintenance monitoring stopped")
    except Exception as e:
        logger.error("Failed to stop maintenance monitoring: %s", e)
    
    try:
        await cache.close()
        logger.info("Cache connections closed")
    except Exception as e:
        logger.error("Failed to close cache connections: %s", e)
