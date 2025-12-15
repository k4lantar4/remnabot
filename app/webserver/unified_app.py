from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from aiogram import Bot
from aiogram import Dispatcher

from app.config import settings
from app.services.payment_service import PaymentService
from app.webapi.app import create_web_api_app
from app.webapi.docs import add_redoc_endpoint

from . import payments
from . import telegram


logger = logging.getLogger(__name__)


def _attach_docs_alias(app: FastAPI, docs_url: str | None) -> None:
    if not docs_url:
        return

    alias_path = "/doc"
    if alias_path == docs_url:
        return

    for route in app.router.routes:
        if getattr(route, "path", None) == alias_path:
            return

    target_url = docs_url

    @app.get(alias_path, include_in_schema=False)
    async def redirect_doc() -> RedirectResponse:  # pragma: no cover - simple redirect
        return RedirectResponse(url=target_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


def _create_base_app() -> FastAPI:
    docs_config = settings.get_web_api_docs_config()

    if settings.is_web_api_enabled():
        app = create_web_api_app()
    else:
        app = FastAPI(
            title="Bedolaga Unified Server",
            version=settings.WEB_API_VERSION,
            docs_url=docs_config.get("docs_url"),
            redoc_url=None,
            openapi_url=docs_config.get("openapi_url"),
        )

        add_redoc_endpoint(
            app,
            redoc_url=docs_config.get("redoc_url"),
            openapi_url=docs_config.get("openapi_url"),
            title="Bedolaga Unified Server",
        )

    _attach_docs_alias(app, app.docs_url)
    return app


def _mount_miniapp_static(app: FastAPI) -> tuple[bool, Path]:
    static_path: Path = settings.get_miniapp_static_path()
    if not static_path.exists():
        logger.debug("Miniapp static path %s does not exist, skipping mount", static_path)
        return False, static_path

    try:
        app.mount("/miniapp/static", StaticFiles(directory=static_path), name="miniapp-static")
        logger.info("📦 Miniapp static files mounted at /miniapp/static from %s", static_path)
    except RuntimeError as error:  # pragma: no cover - defensive guard
        logger.warning("Failed to mount miniapp static files: %s", error)
        return False, static_path

    return True, static_path


def create_unified_app(
    bot: Bot,
    dispatcher: Dispatcher,
    payment_service: PaymentService,
    *,
    enable_telegram_webhook: bool,
    initialized_bots: dict[int, tuple[Bot, Dispatcher]] | None = None,
) -> FastAPI:
    """
    Create unified FastAPI app.
    
    Args:
        bot: Primary bot (for backward compatibility)
        dispatcher: Primary dispatcher (for backward compatibility)
        payment_service: Payment service
        enable_telegram_webhook: Whether to enable Telegram webhooks
        initialized_bots: Dictionary of all initialized bots (bot_id -> (Bot, Dispatcher))
    """
    app = _create_base_app()

    app.state.bot = bot
    app.state.dispatcher = dispatcher
    app.state.payment_service = payment_service

    payments_router = payments.create_payment_router(bot, payment_service)
    if payments_router:
        app.include_router(payments_router)
    payment_providers_state = {
        "tribute": settings.TRIBUTE_ENABLED,
        "mulenpay": settings.is_mulenpay_enabled(),
        "cryptobot": settings.is_cryptobot_enabled(),
        "yookassa": settings.is_yookassa_enabled(),
        "pal24": settings.is_pal24_enabled(),
        "wata": settings.is_wata_enabled(),
        "heleket": settings.is_heleket_enabled(),
    }

    if enable_telegram_webhook:
        # For multi-bot support, register all bots
        if initialized_bots:
            from app.bot import active_bots, active_dispatchers
            
            processors = {}
            for bot_id, (bot_instance, dp_instance) in initialized_bots.items():
                telegram_processor = telegram.TelegramWebhookProcessor(
                    bot=bot_instance,
                    dispatcher=dp_instance,
                    queue_maxsize=settings.get_webhook_queue_maxsize(),
                    worker_count=settings.get_webhook_worker_count(),
                    enqueue_timeout=settings.get_webhook_enqueue_timeout(),
                    shutdown_timeout=settings.get_webhook_shutdown_timeout(),
                )
                processors[bot_id] = telegram_processor
                
                # Register bot in webhook registry
                telegram.register_bot_for_webhook(bot_id, bot_instance, dp_instance, telegram_processor)
                
                # Create bot-specific webhook router
                app.include_router(
                    telegram.create_telegram_router(
                        bot_instance, 
                        dp_instance, 
                        processor=telegram_processor,
                        bot_id=bot_id
                    )
                )
                logger.info(f"✅ Webhook router registered for bot {bot_id}")
            
            app.state.telegram_webhook_processors = processors
            
            # Include unified multi-bot webhook router for dynamic bot support
            app.include_router(telegram.create_multi_bot_webhook_router())
            logger.info("✅ Unified multi-bot webhook router registered")
            
            @app.on_event("startup")
            async def start_all_telegram_webhook_processors() -> None:
                for bot_id, processor in processors.items():
                    await processor.start()
                    logger.info(f"🚀 Webhook processor started for bot {bot_id}")
            
            @app.on_event("shutdown")
            async def stop_all_telegram_webhook_processors() -> None:
                for bot_id, processor in processors.items():
                    await processor.stop()
                    logger.info(f"🛑 Webhook processor stopped for bot {bot_id}")
        else:
            # Single bot mode (backward compatibility)
            telegram_processor = telegram.TelegramWebhookProcessor(
                bot=bot,
                dispatcher=dispatcher,
                queue_maxsize=settings.get_webhook_queue_maxsize(),
                worker_count=settings.get_webhook_worker_count(),
                enqueue_timeout=settings.get_webhook_enqueue_timeout(),
                shutdown_timeout=settings.get_webhook_shutdown_timeout(),
            )
            app.state.telegram_webhook_processor = telegram_processor

            @app.on_event("startup")
            async def start_telegram_webhook_processor() -> None:
                await telegram_processor.start()

            @app.on_event("shutdown")
            async def stop_telegram_webhook_processor() -> None:
                await telegram_processor.stop()

            app.include_router(telegram.create_telegram_router(bot, dispatcher, processor=telegram_processor))
    else:
        telegram_processor = None

    miniapp_mounted, miniapp_path = _mount_miniapp_static(app)

    unified_health_path = "/health/unified" if settings.is_web_api_enabled() else "/health"

    @app.get(unified_health_path)
    async def unified_health() -> JSONResponse:
        webhook_path = settings.get_telegram_webhook_path() if enable_telegram_webhook else None

        telegram_state = {
            "enabled": enable_telegram_webhook,
            "running": bool(telegram_processor and telegram_processor.is_running),
            "url": settings.get_telegram_webhook_url(),
            "path": webhook_path,
            "secret_configured": bool(settings.WEBHOOK_SECRET_TOKEN),
            "queue_maxsize": settings.get_webhook_queue_maxsize(),
            "workers": settings.get_webhook_worker_count(),
        }

        payment_state = {
            "enabled": bool(payments_router),
            "providers": payment_providers_state,
        }

        miniapp_state = {
            "mounted": miniapp_mounted,
            "path": str(miniapp_path),
        }

        return JSONResponse(
            {
                "status": "ok",
                "bot_run_mode": settings.get_bot_run_mode(),
                "web_api_enabled": settings.is_web_api_enabled(),
                "payment_webhooks": payment_state,
                "telegram_webhook": telegram_state,
                "miniapp_static": miniapp_state,
            }
        )

    return app
