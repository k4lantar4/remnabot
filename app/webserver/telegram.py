from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from aiogram import Bot, Dispatcher
from aiogram.types import Update

from app.config import settings


logger = logging.getLogger(__name__)

# Global registry for multi-bot webhook routing
# Using string annotation to avoid forward reference issue
_bot_registry: Dict[int, tuple[Bot, Dispatcher, Optional[Any]]] = {}


class TelegramWebhookProcessorError(RuntimeError):
    """Base exception for the Telegram webhook queue."""


class TelegramWebhookProcessorNotRunningError(TelegramWebhookProcessorError):
    """Queue is not started yet or already stopped."""


class TelegramWebhookOverloadedError(TelegramWebhookProcessorError):
    """Queue is overloaded and cannot process new updates fast enough."""


class TelegramWebhookProcessor:
    """Asynchronous queue for processing Telegram webhooks."""

    def __init__(
        self,
        *,
        bot: Bot,
        dispatcher: Dispatcher,
        queue_maxsize: int,
        worker_count: int,
        enqueue_timeout: float,
        shutdown_timeout: float,
    ) -> None:
        self._bot = bot
        self._dispatcher = dispatcher
        self._queue_maxsize = max(1, queue_maxsize)
        self._worker_count = max(0, worker_count)
        self._enqueue_timeout = max(0.0, enqueue_timeout)
        self._shutdown_timeout = max(1.0, shutdown_timeout)
        self._queue: asyncio.Queue[Update | object] = asyncio.Queue(maxsize=self._queue_maxsize)
        self._workers: list[asyncio.Task[None]] = []
        self._running = False
        self._stop_sentinel: object = object()
        self._lifecycle_lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        async with self._lifecycle_lock:
            if self._running:
                return

            self._running = True
            self._queue = asyncio.Queue(maxsize=self._queue_maxsize)
            self._workers.clear()

            for index in range(self._worker_count):
                task = asyncio.create_task(
                    self._worker_loop(index),
                    name=f"telegram-webhook-worker-{index}",
                )
                self._workers.append(task)

            if self._worker_count:
                logger.info(
                    "🚀 Telegram webhook processor started: %s workers, queue %s",
                    self._worker_count,
                    self._queue_maxsize,
                )
            else:
                logger.warning("Telegram webhook processor started with no workers — updates will not be processed")

    async def stop(self) -> None:
        async with self._lifecycle_lock:
            if not self._running:
                return

            self._running = False

            if self._worker_count > 0:
                try:
                    await asyncio.wait_for(self._queue.join(), timeout=self._shutdown_timeout)
                except asyncio.TimeoutError:
                    logger.warning(
                        "⏱️ Failed to wait for Telegram webhook queue to finish within %s seconds",
                        self._shutdown_timeout,
                    )
            else:
                drained = 0
                while not self._queue.empty():
                    try:
                        self._queue.get_nowait()
                    except asyncio.QueueEmpty:  # pragma: no cover - race condition
                        break
                    else:
                        drained += 1
                        self._queue.task_done()
                if drained:
                    logger.warning(
                        "Telegram webhook queue stopped without workers, lost %s updates",
                        drained,
                    )

            for _ in range(len(self._workers)):
                try:
                    self._queue.put_nowait(self._stop_sentinel)
                except asyncio.QueueFull:
                    # Queue is full, wait until space is available
                    await self._queue.put(self._stop_sentinel)

            if self._workers:
                await asyncio.gather(*self._workers, return_exceptions=True)
            self._workers.clear()
            logger.info("🛑 Telegram webhook processor stopped")

    async def enqueue(self, update: Update) -> None:
        if not self._running:
            raise TelegramWebhookProcessorNotRunningError

        try:
            if self._enqueue_timeout <= 0:
                self._queue.put_nowait(update)
            else:
                await asyncio.wait_for(self._queue.put(update), timeout=self._enqueue_timeout)
        except asyncio.QueueFull as error:  # pragma: no cover - defensive scenario
            raise TelegramWebhookOverloadedError from error
        except asyncio.TimeoutError as error:
            raise TelegramWebhookOverloadedError from error

    async def wait_until_drained(self, timeout: float | None = None) -> None:
        if not self._running or self._worker_count == 0:
            return
        if timeout is None:
            await self._queue.join()
            return
        await asyncio.wait_for(self._queue.join(), timeout=timeout)

    async def _worker_loop(self, worker_id: int) -> None:
        try:
            while True:
                try:
                    item = await self._queue.get()
                except asyncio.CancelledError:  # pragma: no cover - application shutdown
                    logger.debug("Worker %s cancelled", worker_id)
                    raise

                if item is self._stop_sentinel:
                    self._queue.task_done()
                    break

                update = item
                try:
                    await self._dispatcher.feed_update(self._bot, update)  # type: ignore[arg-type]
                except asyncio.CancelledError:  # pragma: no cover - application shutdown
                    logger.debug("Worker %s cancelled during processing", worker_id)
                    raise
                except Exception as error:  # pragma: no cover - logging handler failure
                    logger.exception("Error processing Telegram update in worker %s: %s", worker_id, error)
                finally:
                    self._queue.task_done()
        finally:
            logger.debug("Worker %s finished", worker_id)


async def _dispatch_update(
    update: Update,
    *,
    dispatcher: Dispatcher,
    bot: Bot,
    processor: TelegramWebhookProcessor | None,
) -> None:
    if processor is not None:
        try:
            await processor.enqueue(update)
        except TelegramWebhookOverloadedError as error:
            logger.warning("Telegram webhook queue is full: %s", error)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="webhook_queue_full") from error
        except TelegramWebhookProcessorNotRunningError as error:
            logger.error("Telegram webhook processor is inactive: %s", error)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="webhook_processor_unavailable"
            ) from error
        return

    await dispatcher.feed_update(bot, update)


def register_bot_for_webhook(
    bot_id: int,
    bot: Bot,
    dispatcher: Dispatcher,
    processor: TelegramWebhookProcessor | None = None,
) -> None:
    """Register a bot for multi-bot webhook routing."""
    _bot_registry[bot_id] = (bot, dispatcher, processor)
    logger.info(f"✅ Bot {bot_id} registered for webhook routing")


def unregister_bot_from_webhook(bot_id: int) -> None:
    """Unregister a bot from webhook routing."""
    if bot_id in _bot_registry:
        del _bot_registry[bot_id]
        logger.info(f"🛑 Bot {bot_id} unregistered from webhook routing")


def create_telegram_router(
    bot: Bot,
    dispatcher: Dispatcher,
    *,
    processor: TelegramWebhookProcessor | None = None,
    bot_id: Optional[int] = None,
) -> APIRouter:
    """
    Create a Telegram webhook router.

    If bot_id is provided, registers the bot for multi-bot routing and creates bot-specific endpoint.
    Otherwise, creates a single-bot endpoint (backward compatibility).
    """
    router = APIRouter()
    secret_token = settings.WEBHOOK_SECRET_TOKEN

    # For multi-bot support, use bot-specific path
    if bot_id is not None:
        webhook_path = f"/webhook/{bot_id}"
        register_bot_for_webhook(bot_id, bot, dispatcher, processor)
        logger.info(f"📡 Multi-bot webhook endpoint created: {webhook_path}")
    else:
        # Backward compatibility: single bot
        webhook_path = settings.get_telegram_webhook_path()
        logger.info(f"📡 Single-bot webhook endpoint created: {webhook_path}")

    @router.post(webhook_path)
    async def telegram_webhook(request: Request) -> JSONResponse:
        if secret_token:
            header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if header_token != secret_token:
                logger.warning("Received Telegram webhook with invalid secret")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_secret_token")

        content_type = request.headers.get("content-type", "")
        if content_type and "application/json" not in content_type.lower():
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="invalid_content_type")

        try:
            payload: Any = await request.json()
        except Exception as error:  # pragma: no cover - defensive logging
            logger.error("Error reading Telegram webhook: %s", error)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_payload") from error

        try:
            update = Update.model_validate(payload)
        except Exception as error:  # pragma: no cover - defensive logging
            logger.error("Error validating Telegram update: %s", error)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_update") from error

        await _dispatch_update(update, dispatcher=dispatcher, bot=bot, processor=processor)
        return JSONResponse({"status": "ok"})

    @router.get("/health/telegram-webhook")
    async def telegram_webhook_health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "mode": settings.get_bot_run_mode(),
                "path": webhook_path,
                "webhook_configured": bool(settings.get_telegram_webhook_url()),
                "queue_maxsize": settings.get_webhook_queue_maxsize(),
                "workers": settings.get_webhook_worker_count(),
                "bot_id": bot_id,
                "multi_bot": bot_id is not None,
            }
        )

    return router


def create_multi_bot_webhook_router() -> APIRouter:
    """
    Create a unified webhook router that handles all bots.
    Uses bot_token in URL path (PRD FR2.1) for multi-tenant isolation.
    """
    router = APIRouter()
    base_webhook_path = settings.get_telegram_webhook_path()
    secret_token = settings.WEBHOOK_SECRET_TOKEN

    @router.post(f"{base_webhook_path}/{{bot_token:path}}")
    async def multi_bot_webhook_by_token(request: Request, bot_token: str) -> JSONResponse:
        """
        Webhook endpoint for specific bot by token (PRD FR2.1).
        This is the preferred method for new webhooks.
        """
        from app.database.database import get_db
        from app.database.crud.bot import get_bot_by_token

        # Look up bot by token
        async for db in get_db():
            bot_config = await get_bot_by_token(db, bot_token)

            if not bot_config:
                logger.warning(f"Bot not found for token: {bot_token[:10]}...")
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")

            if not bot_config.is_active:
                logger.warning(f"Bot {bot_config.id} ({bot_config.name}) is inactive")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bot is inactive")

            bot_id = bot_config.id
            break

        # Get bot and dispatcher from registry
        if bot_id in _bot_registry:
            bot, dispatcher, processor = _bot_registry[bot_id]
        else:
            from app.bot import active_bots, active_dispatchers

            if bot_id in active_bots and bot_id in active_dispatchers:
                bot = active_bots[bot_id]
                dispatcher = active_dispatchers[bot_id]
                processor = TelegramWebhookProcessor(
                    bot=bot,
                    dispatcher=dispatcher,
                    queue_maxsize=settings.get_webhook_queue_maxsize(),
                    worker_count=settings.get_webhook_worker_count(),
                    enqueue_timeout=settings.get_webhook_enqueue_timeout(),
                    shutdown_timeout=settings.get_webhook_shutdown_timeout(),
                )
                register_bot_for_webhook(bot_id, bot, dispatcher, processor)
                await processor.start()
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot {bot_id} not found")

        if secret_token:
            header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if header_token != secret_token:
                logger.warning(f"Received Telegram webhook with invalid secret for bot {bot_id}")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_secret_token")

        content_type = request.headers.get("content-type", "")
        if content_type and "application/json" not in content_type.lower():
            raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="invalid_content_type")

        try:
            payload: Any = await request.json()
        except Exception as error:
            logger.error(f"Error reading Telegram webhook for bot {bot_id}: {error}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_payload") from error

        try:
            update = Update.model_validate(payload)
        except Exception as error:
            logger.error(f"Error validating Telegram update for bot {bot_id}: {error}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_update") from error

        await _dispatch_update(update, dispatcher=dispatcher, bot=bot, processor=processor)
        return JSONResponse({"status": "ok", "bot_id": bot_id})

    return router
