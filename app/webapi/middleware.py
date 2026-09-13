from __future__ import annotations

from time import monotonic

import structlog
from sqlalchemy.exc import InterfaceError, OperationalError
from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from structlog.contextvars import bound_contextvars

from app.utils.wire_scale import AMOUNT_SCALE_HEADER, reset_wire_scale, use_wire_scale, wire_scale_from_header


logger = structlog.get_logger('web_api')


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Логирование входящих запросов в административный API."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        with bound_contextvars(http_method=request.method, http_path=request.url.path):
            start = monotonic()
            response: Response | None = None
            try:
                response = await call_next(request)
                return response
            except (TimeoutError, ConnectionRefusedError, OSError, OperationalError, InterfaceError) as e:
                logger.error(
                    'Database connection error while handling request',
                    method=request.method,
                    path=request.url.path,
                    e=str(e)[:200],
                )
                response = JSONResponse(
                    status_code=503,
                    content={'detail': 'Service temporarily unavailable. Please try again later.'},
                )
                return response
            finally:
                duration_ms = (monotonic() - start) * 1000
                status = response.status_code if response else 'error'
                logger.debug(
                    'Request handled',
                    method=request.method,
                    path=request.url.path,
                    status=status,
                    duration_ms=duration_ms,
                )


class AmountScaleMiddleware:
    """Phase C-2: the money scale of one request, read from ``X-Amount-Scale`` and echoed back.

    Pure ASGI rather than ``BaseHTTPMiddleware`` so the context variable is set in the request's own
    context and reset once the response is sent; ``wire_scale`` reads it at every amount it converts.
    The echo (plus ``Vary``) lets the cabinet reject a response on the scale it did not ask for.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        scale = wire_scale_from_header(Headers(scope=scope).get(AMOUNT_SCALE_HEADER))

        async def send_with_scale(message: Message) -> None:
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                headers[AMOUNT_SCALE_HEADER] = scale
                headers.add_vary_header(AMOUNT_SCALE_HEADER)
            await send(message)

        token = use_wire_scale(scale)
        try:
            await self.app(scope, receive, send_with_scale)
        finally:
            reset_wire_scale(token)
