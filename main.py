import asyncio
import logging
import sys
import os
import signal
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from app.bot import setup_bot
from app.config import settings
from app.database.database import init_db
from app.services.monitoring_service import monitoring_service
from app.services.maintenance_service import maintenance_service
from app.services.payment_service import PaymentService
from app.services.payment_verification_service import (
    PENDING_MAX_AGE,
    SUPPORTED_MANUAL_CHECK_METHODS,
    auto_payment_verification_service,
    get_enabled_auto_methods,
    method_display_name,
)
from app.database.models import PaymentMethod
from app.services.version_service import version_service
from app.webapi.server import WebAPIServer
from app.webserver.unified_app import create_unified_app
from app.database.universal_migration import run_universal_migration
from app.services.backup_service import backup_service
from app.services.reporting_service import reporting_service
from app.services.remnawave_sync_service import remnawave_sync_service
from app.localization.loader import ensure_locale_templates
from app.services.system_settings_service import bot_configuration_service
from app.services.external_admin_service import ensure_external_admin_token
from app.services.broadcast_service import broadcast_service
from app.utils.startup_timeline import StartupTimeline
from app.utils.timezone import TimezoneAwareFormatter


class GracefulExit:
    
    def __init__(self):
        self.exit = False
        
    def exit_gracefully(self, signum, frame):
        logging.getLogger(__name__).info(f"Received signal {signum}. Shutting down gracefully...")
        self.exit = True


async def main():
    formatter = TimezoneAwareFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        timezone_name=settings.TIMEZONE,
    )

    file_handler = logging.FileHandler(settings.LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        handlers=[file_handler, stream_handler],
    )
    
    # Set higher logging level for "noisy" loggers
    logging.getLogger("aiohttp.access").setLevel(logging.ERROR)
    logging.getLogger("aiohttp.client").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.internal").setLevel(logging.WARNING)
    logging.getLogger("app.external.remnawave_api").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    timeline = StartupTimeline(logger, "Capitan VPN Core")  # Rebranded Name
    timeline.log_banner(
        [
            ("Log Level", settings.LOG_LEVEL),
            ("DB Mode", settings.DATABASE_MODE),
        ]
    )

    async with timeline.stage(
        "Localization Setup", "🗂️", success_message="Locale templates ready"
    ) as stage:
        try:
            ensure_locale_templates()
        except Exception as error:
            stage.warning(f"Failed to prepare locale templates: {error}")
            logger.warning("Failed to prepare locale templates: %s", error)

    killer = GracefulExit()
    signal.signal(signal.SIGINT, killer.exit_gracefully)
    signal.signal(signal.SIGTERM, killer.exit_gracefully)
    
    web_app = None
    monitoring_task = None
    maintenance_task = None
    version_check_task = None
    polling_task = None
    web_api_server = None
    telegram_webhook_enabled = False
    polling_enabled = True
    payment_webhooks_enabled = False

    summary_logged = False

    try:
        async with timeline.stage(
            "Database Initialization", "🗄️", success_message="Database ready"
        ):
            await init_db()

        skip_migration = os.getenv('SKIP_MIGRATION', 'false').lower() == 'true'

        if not skip_migration:
            async with timeline.stage(
                "Database Migration",
                "🧬",
                success_message="Migration completed successfully",
            ) as stage:
                try:
                    migration_success = await run_universal_migration()
                    if migration_success:
                        stage.success("Migration completed successfully")
                    else:
                        stage.warning(
                            "Migration finished with warnings, continuing startup"
                        )
                        logger.warning(
                            "⚠️ Migration finished with warnings, but continuing startup"
                        )
                except Exception as migration_error:
                    stage.warning(f"Migration error: {migration_error}")
                    logger.error(f"❌ Migration error: {migration_error}")
                    logger.warning("⚠️ Continuing startup without migration")
        else:
            timeline.add_manual_step(
                "Database Migration",
                "⏭️",
                "Skipped",
                "SKIP_MIGRATION=true",
            )

        async with timeline.stage(
            "Loading Config from DB",
            "⚙️",
            success_message="Configuration loaded",
        ) as stage:
            try:
                await bot_configuration_service.initialize()
            except Exception as error:
                stage.warning(f"Failed to load configuration: {error}")
                logger.error(f"❌ Failed to load configuration: {error}")

        bot = None
        dp = None
        async with timeline.stage("Bot Setup", "🤖", success_message="Bot configured") as stage:
            bot, dp = await setup_bot()
            stage.log("Cache and FSM prepared")

        monitoring_service.bot = bot
        maintenance_service.set_bot(bot)
        broadcast_service.set_bot(bot)

        from app.services.admin_notification_service import AdminNotificationService

        async with timeline.stage(
            "Service Integration",
            "🔗",
            success_message="Services connected",
        ) as stage:
            admin_notification_service = AdminNotificationService(bot)
            version_service.bot = bot
            version_service.set_notification_service(admin_notification_service)
            stage.log(f"Version Repo: {version_service.repo}")
            stage.log(f"Current Version: {version_service.current_version}")
            stage.success("Monitoring, notifications, and broadcasts connected")

        async with timeline.stage(
            "Backup Service",
            "🗄️",
            success_message="Backup service initialized",
        ) as stage:
            try:
                backup_service.bot = bot
                settings_obj = await backup_service.get_backup_settings()
                if settings_obj.auto_backup_enabled:
                    await backup_service.start_auto_backup()
                    stage.log(
                        "Auto-backup enabled: interval "
                        f"{settings_obj.backup_interval_hours}h, runs at {settings_obj.backup_time}"
                    )
                else:
                    stage.log("Auto-backup disabled by settings")
                stage.success("Backup service initialized")
            except Exception as e:
                stage.warning(f"Backup service initialization error: {e}")
                logger.error(f"❌ Backup service initialization error: {e}")

        async with timeline.stage(
            "Reporting Service",
            "📊",
            success_message="Reporting service ready",
        ) as stage:
            try:
                reporting_service.set_bot(bot)
                await reporting_service.start()
            except Exception as e:
                stage.warning(f"Reporting service startup error: {e}")
                logger.error(f"❌ Reporting service startup error: {e}")

        async with timeline.stage(
            "RemnaWave Auto-Sync",
            "🔄",
            success_message="Auto-sync service ready",
        ) as stage:
            try:
                await remnawave_sync_service.initialize()
                status = remnawave_sync_service.get_status()
                if status.enabled:
                    times_text = ", ".join(t.strftime("%H:%M") for t in status.times) or "—"
                    if status.next_run:
                        next_run_text = status.next_run.strftime("%d.%m.%Y %H:%M")
                        stage.log(
                            f"Active: schedule {times_text}, next run {next_run_text}"
                        )
                    else:
                        stage.log(f"Active: schedule {times_text}")
                else:
                    stage.log("Auto-sync disabled by settings")
            except Exception as e:
                stage.warning(f"Auto-sync startup error: {e}")
                logger.error(f"❌ RemnaWave auto-sync startup error: {e}")

        payment_service = PaymentService(bot)
        auto_payment_verification_service.set_payment_service(payment_service)

        verification_providers: list[str] = []
        auto_verification_active = False
        async with timeline.stage(
            "Payment Verification Service",
            "💳",
            success_message="Manual verification active",
        ) as stage:
            for method in SUPPORTED_MANUAL_CHECK_METHODS:
                if method == PaymentMethod.YOOKASSA and settings.is_yookassa_enabled():
                    verification_providers.append("YooKassa")
                elif method == PaymentMethod.MULENPAY and settings.is_mulenpay_enabled():
                    verification_providers.append(settings.get_mulenpay_display_name())
                elif method == PaymentMethod.PAL24 and settings.is_pal24_enabled():
                    verification_providers.append("PayPalych")
                elif method == PaymentMethod.WATA and settings.is_wata_enabled():
                    verification_providers.append("WATA")
                elif method == PaymentMethod.HELEKET and settings.is_heleket_enabled():
                    verification_providers.append("Heleket")
                elif method == PaymentMethod.CRYPTOBOT and settings.is_cryptobot_enabled():
                    verification_providers.append("CryptoBot")

            if verification_providers:
                hours = int(PENDING_MAX_AGE.total_seconds() // 3600)
                stage.log(
                    "Pending payments automatically tracked not older than "
                    f"{hours}h"
                )
                stage.log(
                    "Manual verification available for: "
                    + ", ".join(sorted(verification_providers))
                )
                stage.success(
                    f"Active providers: {len(verification_providers)}"
                )
            else:
                stage.skip("No active providers for manual verification")

            if settings.is_payment_verification_auto_check_enabled():
                auto_methods = get_enabled_auto_methods()
                if auto_methods:
                    interval_minutes = settings.get_payment_verification_auto_check_interval()
                    auto_labels = ", ".join(
                        sorted(method_display_name(method) for method in auto_methods)
                    )
                    stage.log(
                        "Auto-check every "
                        f"{interval_minutes} min: {auto_labels}"
                    )
                else:
                    stage.log(
                        "Auto-check enabled, but no active providers"
                    )
            else:
                stage.log("Auto-check disabled by settings")

            await auto_payment_verification_service.start()
            auto_verification_active = auto_payment_verification_service.is_running()
            if auto_verification_active:
                stage.log("Background auto-check started")

        async with timeline.stage(
            "External Admin",
            "🛡️",
            success_message="External admin token ready",
        ) as stage:
            try:
                bot_user = await bot.get_me()
                token = await ensure_external_admin_token(
                    bot_user.username,
                    bot_user.id,
                )
                if token:
                    stage.log("Token synchronized")
                else:
                    stage.warning("Failed to get external admin token")
            except Exception as error: 
                stage.warning(f"External admin setup error: {error}")
                logger.error("❌ External admin setup error: %s", error)

        bot_run_mode = settings.get_bot_run_mode()
        polling_enabled = bot_run_mode in {"polling", "both"}
        telegram_webhook_enabled = bot_run_mode in {"webhook", "both"}

        payment_webhooks_enabled = any(
            [
                settings.TRIBUTE_ENABLED,
                settings.is_cryptobot_enabled(),
                settings.is_mulenpay_enabled(),
                settings.is_yookassa_enabled(),
                settings.is_pal24_enabled(),
                settings.is_wata_enabled(),
                settings.is_heleket_enabled(),
            ]
        )

        async with timeline.stage(
            "Unified Web Server",
            "🌐",
            success_message="Web server started",
        ) as stage:
            should_start_web_app = (
                settings.is_web_api_enabled()
                or telegram_webhook_enabled
                or payment_webhooks_enabled
                or settings.get_miniapp_static_path().exists()
            )

            if should_start_web_app:
                web_app = create_unified_app(
                    bot,
                    dp,
                    payment_service,
                    enable_telegram_webhook=telegram_webhook_enabled,
                )

                web_api_server = WebAPIServer(app=web_app)
                await web_api_server.start()

                base_url = settings.WEBHOOK_URL or f"http://{settings.WEB_API_HOST}:{settings.WEB_API_PORT}"
                stage.log(f"Base URL: {base_url}")

                features: list[str] = []
                if settings.is_web_api_enabled():
                    features.append("admin-api")
                if payment_webhooks_enabled:
                    features.append("payment-webhooks")
                if telegram_webhook_enabled:
                    features.append("telegram-webhook")
                if settings.get_miniapp_static_path().exists():
                    features.append("miniapp-static")

                if features:
                    stage.log("Active services: " + ", ".join(features))
                stage.success("HTTP services active")
            else:
                stage.skip("HTTP services disabled by settings")

        async with timeline.stage(
            "Telegram Webhook",
            "🤖",
            success_message="Telegram webhook configured",
        ) as stage:
            if telegram_webhook_enabled:
                webhook_url = settings.get_telegram_webhook_url()
                if not webhook_url:
                    stage.warning("WEBHOOK_URL not set, skipping webhook setup")
                else:
                    allowed_updates = dp.resolve_used_update_types()
                    await bot.set_webhook(
                        url=webhook_url,
                        secret_token=settings.WEBHOOK_SECRET_TOKEN,
                        drop_pending_updates=settings.WEBHOOK_DROP_PENDING_UPDATES,
                        allowed_updates=allowed_updates,
                    )
                    stage.log(f"Webhook set: {webhook_url}")
                    stage.log(f"Allowed updates: {', '.join(sorted(allowed_updates)) if allowed_updates else 'all'}")
                    stage.success("Telegram webhook active")
            else:
                stage.skip("Webhook mode disabled")

        async with timeline.stage(
            "Monitoring Service",
            "📈",
            success_message="Monitoring service started",
        ) as stage:
            monitoring_task = asyncio.create_task(monitoring_service.start_monitoring())
            stage.log(f"Polling interval: {settings.MONITORING_INTERVAL}s")

        async with timeline.stage(
            "Maintenance Service",
            "🛡️",
            success_message="Maintenance service started",
        ) as stage:
            if not settings.is_maintenance_monitoring_enabled():
                maintenance_task = None
                stage.skip("Maintenance monitoring disabled by settings")
            elif not maintenance_service._check_task or maintenance_service._check_task.done():
                maintenance_task = asyncio.create_task(maintenance_service.start_monitoring())
                stage.log(f"Check interval: {settings.MAINTENANCE_CHECK_INTERVAL}s")
                stage.log(
                    f"Retry attempts: {settings.get_maintenance_retry_attempts()}"
                )
            else:
                maintenance_task = None
                stage.skip("Maintenance service already active")

        async with timeline.stage(
            "Version Check Service",
            "📄",
            success_message="Version check started",
        ) as stage:
            if settings.is_version_check_enabled():
                version_check_task = asyncio.create_task(version_service.start_periodic_check())
                stage.log(
                    f"Check interval: {settings.VERSION_CHECK_INTERVAL_HOURS}h"
                )
            else:
                version_check_task = None
                stage.skip("Version check disabled by settings")

        async with timeline.stage(
            "Starting Polling",
            "🤖",
            success_message="Aiogram polling started",
        ) as stage:
            if polling_enabled:
                polling_task = asyncio.create_task(dp.start_polling(bot, skip_updates=True))
                stage.log("skip_updates=True")
            else:
                polling_task = None
                stage.skip("Polling disabled by run mode")

        webhook_lines: list[str] = []
        base_url = settings.WEBHOOK_URL or f"http://{settings.WEB_API_HOST}:{settings.WEB_API_PORT}"

        def _fmt(path: str) -> str:
            return f"{base_url}{path if path.startswith('/') else '/' + path}"

        telegram_webhook_url = settings.get_telegram_webhook_url()
        if telegram_webhook_enabled and telegram_webhook_url:
            webhook_lines.append(f"Telegram: {telegram_webhook_url}")
        if settings.TRIBUTE_ENABLED:
            webhook_lines.append(f"Tribute: {_fmt(settings.TRIBUTE_WEBHOOK_PATH)}")
        if settings.is_mulenpay_enabled():
            webhook_lines.append(
                f"{settings.get_mulenpay_display_name()}: {_fmt(settings.MULENPAY_WEBHOOK_PATH)}"
            )
        if settings.is_cryptobot_enabled():
            webhook_lines.append(f"CryptoBot: {_fmt(settings.CRYPTOBOT_WEBHOOK_PATH)}")
        if settings.is_yookassa_enabled():
            webhook_lines.append(f"YooKassa: {_fmt(settings.YOOKASSA_WEBHOOK_PATH)}")
        if settings.is_pal24_enabled():
            webhook_lines.append(f"PayPalych: {_fmt(settings.PAL24_WEBHOOK_PATH)}")
        if settings.is_wata_enabled():
            webhook_lines.append(f"WATA: {_fmt(settings.WATA_WEBHOOK_PATH)}")
        if settings.is_heleket_enabled():
            webhook_lines.append(f"Heleket: {_fmt(settings.HELEKET_WEBHOOK_PATH)}")

        timeline.log_section(
            "Active Webhook Endpoints",
            webhook_lines if webhook_lines else ["No active endpoints"],
            icon="🎯",
        )

        services_lines = [
            f"Monitoring: {'On' if monitoring_task else 'Off'}",
            f"Maintenance: {'On' if maintenance_task else 'Off'}",
            f"Version Check: {'On' if version_check_task else 'Off'}",
            f"Reporting: {'On' if reporting_service.is_running() else 'Off'}",
        ]
        services_lines.append(
            "Payment Verification: "
            + ("On" if verification_providers else "Off")
        )
        services_lines.append(
            "Auto Payment Check: "
            + (
                "On"
                if auto_payment_verification_service.is_running()
                else "Off"
            )
        )
        timeline.log_section("Active Background Services", services_lines, icon="📄")

        timeline.log_summary()
        summary_logged = True
        
        try:
            while not killer.exit:
                await asyncio.sleep(1)
                
                if monitoring_task.done():
                    exception = monitoring_task.exception()
                    if exception:
                        logger.error(f"Monitoring service failed: {exception}")
                        monitoring_task = asyncio.create_task(monitoring_service.start_monitoring())
                        
                if maintenance_task and maintenance_task.done():
                    exception = maintenance_task.exception()
                    if exception:
                        logger.error(f"Maintenance service failed: {exception}")
                        maintenance_task = asyncio.create_task(maintenance_service.start_monitoring())
                
                if version_check_task and version_check_task.done():
                    exception = version_check_task.exception()
                    if exception:
                        logger.error(f"Version check service failed: {exception}")
                        if settings.is_version_check_enabled():
                            logger.info("🔄 Restarting version check service...")
                            version_check_task = asyncio.create_task(version_service.start_periodic_check())

                if auto_verification_active and not auto_payment_verification_service.is_running():
                    logger.warning(
                        "Auto payment verification service stopped, restarting..."
                    )
                    await auto_payment_verification_service.start()
                    auto_verification_active = auto_payment_verification_service.is_running()

                if polling_task and polling_task.done():
                    exception = polling_task.exception()
                    if exception:
                        logger.error(f"Polling failed: {exception}")
                        break
                        
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            
    except Exception as e:
        logger.error(f"❌ Critical startup error: {e}")
        raise
        
    finally:
        if not summary_logged:
            timeline.log_summary()
            summary_logged = True
        logger.info("🛑 Initiating graceful shutdown...")

        logger.info("ℹ️ Stopping auto payment verification...")
        try:
            await auto_payment_verification_service.stop()
        except Exception as error:
            logger.error(
                f"Error stopping auto payment verification: {error}"
            )

        if monitoring_task and not monitoring_task.done():
            logger.info("ℹ️ Stopping monitoring service...")
            monitoring_service.stop_monitoring()
            monitoring_task.cancel()
            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass

        if maintenance_task and not maintenance_task.done():
            logger.info("ℹ️ Stopping maintenance service...")
            await maintenance_service.stop_monitoring()
            maintenance_task.cancel()
            try:
                await maintenance_task
            except asyncio.CancelledError:
                pass
        
        if version_check_task and not version_check_task.done():
            logger.info("ℹ️ Stopping version check service...")
            version_check_task.cancel()
            try:
                await version_check_task
            except asyncio.CancelledError:
                pass

        logger.info("ℹ️ Stopping reporting service...")
        try:
            await reporting_service.stop()
        except Exception as e:
            logger.error(f"Error stopping reporting service: {e}")

        logger.info("ℹ️ Stopping RemnaWave auto-sync...")
        try:
            await remnawave_sync_service.stop()
        except Exception as e:
            logger.error(f"Error stopping RemnaWave auto-sync: {e}")

        logger.info("ℹ️ Stopping backup service...")
        try:
            await backup_service.stop_auto_backup()
        except Exception as e:
            logger.error(f"Error stopping backup service: {e}")
        
        if polling_task and not polling_task.done():
            logger.info("ℹ️ Stopping polling...")
            polling_task.cancel()
            try:
                await polling_task
            except asyncio.CancelledError:
                pass
        
        if telegram_webhook_enabled and 'bot' in locals():
            logger.info("ℹ️ Removing Telegram webhook...")
            try:
                await bot.delete_webhook(drop_pending_updates=False)
                logger.info("✅ Telegram webhook removed")
            except Exception as error:
                logger.error(f"Error removing Telegram webhook: {error}")

        if web_api_server:
            try:
                await web_api_server.stop()
                logger.info("✅ Admin Web API stopped")
            except Exception as error:
                logger.error(f"Error stopping Web API: {error}")
        
        if 'bot' in locals():
            try:
                await bot.session.close()
                logger.info("✅ Bot session closed")
            except Exception as e:
                logger.error(f"Error closing bot session: {e}")
        
        logger.info("✅ Bot shutdown completed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Critical error: {e}")
        sys.exit(1)