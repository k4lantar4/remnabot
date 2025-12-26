from __future__ import annotations

import asyncio
import logging
from typing import Optional

import uvicorn

from app.config import settings

from .app import create_web_api_app


logger = logging.getLogger(__name__)


class WebAPIServer:
    """Asynchronous uvicorn server for the admin API."""

    def __init__(self, app: Optional[object] = None) -> None:
        self._app = app or create_web_api_app()

        workers = max(1, int(settings.WEB_API_WORKERS or 1))
        if workers > 1:
            logger.warning("WEB_API_WORKERS > 1 is not supported in embed mode, using 1")
            workers = 1

        self._config = uvicorn.Config(
            app=self._app,
            host=settings.WEB_API_HOST,
            port=int(settings.WEB_API_PORT or 8080),
            log_level=settings.LOG_LEVEL.lower(),
            workers=workers,
            lifespan="on",
        )
        self._server = uvicorn.Server(self._config)
        self._task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            logger.info("🌐 Admin web API is already running")
            return

        async def _serve() -> None:
            try:
                await self._server.serve()
            except Exception as error:  # pragma: no cover - log server errors
                logger.exception("❌ Web API error: %s", error)
                raise

        logger.info(
            "🌐 Starting admin API at %s:%s",
            settings.WEB_API_HOST,
            settings.WEB_API_PORT,
        )
        self._task = asyncio.create_task(_serve(), name="web-api-server")

        started_attr = getattr(self._server, "started", None)
        started_event = getattr(self._server, "started_event", None)

        if isinstance(started_attr, asyncio.Event):
            await started_attr.wait()
        elif isinstance(started_event, asyncio.Event):
            await started_event.wait()
        else:
            while not getattr(self._server, "started", False):
                if self._task.done():
                    break
                await asyncio.sleep(0.1)

        if self._task.done() and self._task.exception():
            raise self._task.exception()

    async def stop(self) -> None:
        if not self._task:
            return

        logger.info("🛑 Stopping admin API")
        self._server.should_exit = True
        await self._task
        self._task = None
