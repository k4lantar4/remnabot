import asyncio
import logging
from typing import Dict, Optional
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
import redis.asyncio as redis

from app.config import settings
from app.database.models import Bot as BotModel
from app.middlewares.global_error import GlobalErrorMiddleware
from app.middlewares.bot_context import BotContextMiddleware
from app.middlewares.auth import AuthMiddleware
from app.middlewares.logging import LoggingMiddleware
from app.middlewares.throttling import ThrottlingMiddleware
from app.middlewares.subscription_checker import SubscriptionStatusMiddleware
from app.middlewares.maintenance import MaintenanceMiddleware
from app.middlewares.display_name_restriction import DisplayNameRestrictionMiddleware
from app.middlewares.button_stats import ButtonStatsMiddleware
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
    blacklist as admin_blacklist,
    bulk_ban as admin_bulk_ban,
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
    contests as admin_contests,
    daily_contests as admin_daily_contests,
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
from app.handlers import contests as user_contests
from app.handlers.stars_payments import register_stars_handlers

from app.utils.message_patch import patch_message_methods

patch_message_methods()

logger = logging.getLogger(__name__)

# Global registry for active bots and dispatchers
active_bots: Dict[int, Bot] = {}
active_dispatchers: Dict[int, Dispatcher] = {}
polling_tasks: Dict[int, asyncio.Task] = {}  # Track polling tasks for each bot


async def debug_callback_handler(callback: types.CallbackQuery):
    logger.info("🔍 DEBUG CALLBACK:")
    logger.info("  - Data: %s", callback.data)
    logger.info("  - User: %s", callback.from_user.id)
    logger.info("  - Username: %s", callback.from_user.username)


async def setup_bot(bot_config: Optional[BotModel] = None) -> tuple[Bot, Dispatcher]:
    """
    Setup a single bot instance.

    Args:
        bot_config: Bot configuration from database. If None, uses BOT_TOKEN from settings (backward compatibility).

    Returns:
        Tuple of (Bot instance, Dispatcher instance)
    """
    # Initialize cache once (shared across all bots)
    if not cache._connected:
        try:
            await cache.connect()
            logger.info("Cache initialized")
        except Exception as e:
            logger.warning("Cache initialization failed: %s", e)

    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    # Use bot_config if provided, otherwise fall back to settings (backward compatibility)
    if bot_config:
        bot_token = bot_config.telegram_bot_token
        bot_id = bot_config.id
        bot_name = bot_config.name
        logger.info(f"🤖 Setting up bot: {bot_name} (ID: {bot_id})")
    else:
        bot_token = settings.BOT_TOKEN
        bot_id = None
        bot_name = "Default Bot"
        logger.info(f"🤖 Setting up default bot from settings")

    bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Set bot in maintenance service (for backward compatibility, uses last bot)
    maintenance_service.set_bot(bot)
    if bot_id:
        logger.info(f"Bot {bot_name} (ID: {bot_id}) set in maintenance_service")
    else:
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

    # Bot Context Middleware - injects bot_id and bot_config
    bot_context_middleware = BotContextMiddleware()
    dp.message.middleware(bot_context_middleware)
    dp.callback_query.middleware(bot_context_middleware)
    dp.pre_checkout_query.middleware(bot_context_middleware)
    logger.info("✅ BotContextMiddleware registered")

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

    # Middleware для автоматического логирования кликов по кнопкам
    if settings.MENU_LAYOUT_ENABLED:
        button_stats_middleware = ButtonStatsMiddleware()
        dp.callback_query.middleware(button_stats_middleware)
        logger.info("📊 ButtonStatsMiddleware активирован")

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
    admin_contests.register_handlers(dp)
    admin_daily_contests.register_handlers(dp)
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
    from app.handlers.admin import tenant_bots

    tenant_bots.register_handlers(dp)
    admin_bulk_ban.register_bulk_ban_handlers(dp)
    admin_blacklist.register_blacklist_handlers(dp)
    common.register_handlers(dp)
    register_stars_handlers(dp)
    user_contests.register_handlers(dp)
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
    if bot_id:
        logger.info(f"✅ Bot {bot_name} (ID: {bot_id}) successfully configured")
    else:
        logger.info("Bot successfully configured")

    return bot, dp


async def initialize_all_bots() -> Dict[int, tuple[Bot, Dispatcher]]:
    """
    Initialize all active bots from database.

    Returns:
        Dictionary mapping bot_id -> (Bot, Dispatcher) tuple
    """
    from app.database.database import AsyncSessionLocal
    from app.database.crud.bot import get_active_bots

    logger.info("🚀 Initializing all active bots from database...")

    async with AsyncSessionLocal() as db:
        bots = await get_active_bots(db)

        if not bots:
            logger.warning("⚠️ No active bots found in database")
            # Fallback to single bot from settings for backward compatibility
            logger.info("📋 Falling back to single bot from BOT_TOKEN setting")
            bot, dp = await setup_bot()
            return {0: (bot, dp)}  # Use 0 as key for default bot

        initialized = {}
        for bot_config in bots:
            try:
                bot, dp = await setup_bot(bot_config)
                active_bots[bot_config.id] = bot
                active_dispatchers[bot_config.id] = dp
                initialized[bot_config.id] = (bot, dp)
                logger.info(
                    f"✅ Bot initialized: {bot_config.name} (ID: {bot_config.id}, Master: {bot_config.is_master})"
                )
            except Exception as e:
                logger.error(f"❌ Failed to initialize bot {bot_config.id} ({bot_config.name}): {e}", exc_info=True)

        logger.info(f"🎉 Successfully initialized {len(initialized)} bot(s)")
        return initialized


async def initialize_single_bot(bot_config: BotModel) -> tuple[Bot, Dispatcher] | None:
    """
    Initialize a single bot dynamically (after server startup).
    This is used when a new bot is added to the database.

    Args:
        bot_config: Bot configuration from database

    Returns:
        Tuple of (Bot, Dispatcher) if successful, None otherwise
    """
    if bot_config.id in active_bots:
        logger.warning(f"Bot {bot_config.id} ({bot_config.name}) is already initialized")
        return active_bots[bot_config.id], active_dispatchers[bot_config.id]

    if not bot_config.is_active:
        logger.warning(f"Bot {bot_config.id} ({bot_config.name}) is not active, skipping initialization")
        return None

    try:
        bot, dp = await setup_bot(bot_config)
        active_bots[bot_config.id] = bot
        active_dispatchers[bot_config.id] = dp

        logger.info(
            f"✅ Bot dynamically initialized: {bot_config.name} (ID: {bot_config.id}, Master: {bot_config.is_master})"
        )

        return bot, dp
    except Exception as e:
        logger.error(f"❌ Failed to initialize bot {bot_config.id} ({bot_config.name}): {e}", exc_info=True)
        return None


async def start_bot_polling(bot_id: int, bot: Bot, dispatcher: Dispatcher) -> asyncio.Task | None:
    """
    Start polling for a single bot.

    Args:
        bot_id: Bot ID
        bot: Bot instance
        dispatcher: Dispatcher instance

    Returns:
        Polling task if started, None otherwise
    """
    from app.config import settings

    bot_run_mode = settings.get_bot_run_mode()
    polling_enabled = bot_run_mode in {"polling", "both"}

    if not polling_enabled:
        logger.debug(f"Polling disabled for bot {bot_id}")
        return None

    # Check if polling is already running for this bot
    if bot_id in polling_tasks and not polling_tasks[bot_id].done():
        logger.warning(f"Polling already running for bot {bot_id}")
        return polling_tasks[bot_id]

    try:
        task = asyncio.create_task(dispatcher.start_polling(bot, skip_updates=True))
        polling_tasks[bot_id] = task
        logger.info(f"✅ Started polling for bot {bot_id}")
        return task
    except Exception as e:
        logger.error(f"❌ Failed to start polling for bot {bot_id}: {e}", exc_info=True)
        return None


async def setup_bot_webhook(bot_id: int, bot: Bot, bot_token: str) -> bool:
    """
    Setup webhook for a single bot using bot_token (PRD FR2.1).

    Args:
        bot_id: Bot ID
        bot: Bot instance
        bot_token: Telegram bot token (used in webhook URL)

    Returns:
        True if webhook was set successfully, False otherwise
    """
    from app.config import settings
    from urllib.parse import urljoin

    bot_run_mode = settings.get_bot_run_mode()
    telegram_webhook_enabled = bot_run_mode in {"webhook", "both"}

    if not telegram_webhook_enabled:
        logger.debug(f"Webhook disabled for bot {bot_id}")
        return False

    base_webhook_url = settings.get_telegram_webhook_url()
    if not base_webhook_url:
        logger.warning(f"WEBHOOK_URL not set, cannot setup webhook for bot {bot_id}")
        return False

    try:
        # Get dispatcher to resolve allowed updates
        if bot_id in active_dispatchers:
            dp = active_dispatchers[bot_id]
            allowed_updates = dp.resolve_used_update_types()

            # Register bot in webhook registry for unified endpoint (lazy import to avoid circular dependency)
            try:
                from app.webserver import telegram

                telegram_processor = telegram.TelegramWebhookProcessor(
                    bot=bot,
                    dispatcher=dp,
                    queue_maxsize=settings.get_webhook_queue_maxsize(),
                    worker_count=settings.get_webhook_worker_count(),
                    enqueue_timeout=settings.get_webhook_enqueue_timeout(),
                    shutdown_timeout=settings.get_webhook_shutdown_timeout(),
                )
                telegram.register_bot_for_webhook(bot_id, bot, dp, telegram_processor)

                # Start processor
                await telegram_processor.start()
                logger.info(f"✅ Webhook processor started for bot {bot_id}")
            except ImportError:
                logger.warning(f"Could not import telegram module, skipping processor setup for bot {bot_id}")
        else:
            allowed_updates = None
            logger.warning(f"Dispatcher not found for bot {bot_id}, skipping webhook processor setup")

        # Construct webhook URL using bot_token (PRD FR2.1)
        bot_webhook_url = urljoin(base_webhook_url.rstrip("/") + "/", f"webhook/{bot_token}")

        await bot.set_webhook(
            url=bot_webhook_url,
            secret_token=settings.WEBHOOK_SECRET_TOKEN,
            drop_pending_updates=settings.WEBHOOK_DROP_PENDING_UPDATES,
            allowed_updates=allowed_updates,
        )

        logger.info(f"✅ Webhook set for bot {bot_id}: {bot_webhook_url}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to set webhook for bot {bot_id}: {e}", exc_info=True)
        return False


async def shutdown_bot(bot_id: Optional[int] = None):
    """
    Shutdown bot(s).

    Args:
        bot_id: Specific bot ID to shutdown. If None, shuts down all bots.
    """
    if bot_id is not None:
        # Shutdown specific bot
        if bot_id in active_bots:
            bot = active_bots[bot_id]
            try:
                # Cancel polling task if it exists
                if bot_id in polling_tasks:
                    task = polling_tasks[bot_id]
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    del polling_tasks[bot_id]
                    logger.info(f"🛑 Polling task cancelled for bot {bot_id}")

                await bot.session.close()
                del active_bots[bot_id]
                if bot_id in active_dispatchers:
                    del active_dispatchers[bot_id]
                logger.info(f"🛑 Bot {bot_id} shut down")
            except Exception as e:
                logger.error(f"Failed to shutdown bot {bot_id}: {e}")
    else:
        # Shutdown all bots
        try:
            await maintenance_service.stop_monitoring()
            logger.info("Maintenance monitoring stopped")
        except Exception as e:
            logger.error("Failed to stop maintenance monitoring: %s", e)

        # Close all bot sessions
        for bot_id, bot in list(active_bots.items()):
            try:
                await bot.session.close()
                logger.info(f"🛑 Bot {bot_id} session closed")
            except Exception as e:
                logger.error(f"Failed to close bot {bot_id} session: {e}")

        # Cancel all polling tasks
        for bot_id, task in list(polling_tasks.items()):
            try:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                logger.info(f"🛑 Polling task cancelled for bot {bot_id}")
            except Exception as e:
                logger.error(f"Failed to cancel polling task for bot {bot_id}: {e}")

        polling_tasks.clear()
        active_bots.clear()
        active_dispatchers.clear()

        try:
            await cache.close()
            logger.info("Cache connections closed")
        except Exception as e:
            logger.error("Failed to close cache connections: %s", e)
