"""
Tenant Middleware for FastAPI

Extracts tenant (bot_id) from bot_token in URL path and sets tenant context.
This middleware should be applied to all routes that need tenant isolation.
"""

import logging
from typing import Callable
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from sqlalchemy import text
from app.database.database import get_db
from app.database.crud.bot import get_bot_by_token
from app.core.tenant_context import set_current_tenant, clear_current_tenant

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract tenant from bot_token in URL path.

    Extracts bot_token from URL path (e.g., /webhook/{bot_token}),
    looks up the bot in database, and sets tenant context.

    Usage:
        app.add_middleware(TenantMiddleware)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and set tenant context if bot_token is in path.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response
        """
        # Clear tenant context at start of request
        clear_current_tenant()

        # Extract bot_token from path
        # Support both /webhook/{bot_token} and /api/v1/{bot_token}/...
        path = request.url.path
        bot_token = None
        requires_tenant = False

        # Try to extract from /webhook/{bot_token}
        if path.startswith("/webhook/"):
            requires_tenant = True
            parts = path.split("/")
            if len(parts) >= 3:
                bot_token = parts[2]
            # If path is exactly /webhook/ or /webhook//, bot_token is empty
            if not bot_token or bot_token == "":
                logger.warning(f"Invalid webhook path: {path} - missing bot_token")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook path: bot_token is required"
                )

        # Try to extract from /api/v1/{bot_token}/...
        elif path.startswith("/api/v1/"):
            requires_tenant = True
            parts = path.split("/")
            if len(parts) >= 4:
                bot_token = parts[3]
            # If path is /api/v1/ or /api/v1//, bot_token is empty
            if not bot_token or bot_token == "":
                logger.warning(f"Invalid API path: {path} - missing bot_token")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid API path: bot_token is required"
                )

        # If bot_token found, look up bot and set tenant context
        if bot_token:
            try:
                async for db in get_db():
                    bot = await get_bot_by_token(db, bot_token)

                    if not bot:
                        # Truncate token for logging (first 10 chars)
                        token_preview = bot_token[:10] if len(bot_token) > 10 else bot_token
                        logger.warning(f"Bot not found for token: {token_preview}...")
                        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bot not found")

                    if not bot.is_active:
                        logger.warning(f"Bot {bot.id} ({bot.name}) is inactive")
                        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bot is inactive")

                    # Set tenant context (ContextVar)
                    set_current_tenant(bot.id)

                    # Set session variable for RLS policies
                    await db.execute(text("SET app.current_tenant = :bot_id"), {"bot_id": bot.id})
                    await db.commit()

                    logger.debug(f"✅ Tenant context set: bot_id={bot.id}, token={bot_token[:10]}...")
                    break

            except HTTPException:
                # Re-raise HTTP exceptions (404, 403, 400) as-is
                raise
            except Exception as e:
                logger.error(f"Error in TenantMiddleware: {e}", exc_info=True)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
        elif requires_tenant:
            # This should not happen due to checks above, but safety check
            logger.error(f"Tenant required but bot_token is None for path: {path}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path: bot_token is required")

        # Process request
        try:
            response = await call_next(request)
            return response
        finally:
            # Clear tenant context after request
            clear_current_tenant()
