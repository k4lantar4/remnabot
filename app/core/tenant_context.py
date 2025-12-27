"""
Tenant Context Management

Provides ContextVar-based tenant context for multi-tenant isolation.
This is the base layer with no dependencies on database or services.
"""

import logging
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger(__name__)

# ContextVar for current tenant (bot_id)
# This is thread-safe and async-safe
tenant_context: ContextVar[Optional[int]] = ContextVar("current_tenant", default=None)


def get_current_tenant() -> Optional[int]:
    """
    Get current tenant (bot_id) from context.

    Returns:
        bot_id if set, None otherwise

    Note:
        This does NOT raise an error if tenant is not set.
        Use require_current_tenant() if you need to ensure tenant is set.
    """
    return tenant_context.get()


def require_current_tenant() -> int:
    """
    Get current tenant (bot_id) from context, raising error if not set.

    Returns:
        bot_id

    Raises:
        RuntimeError: If tenant context is not set
    """
    bot_id = tenant_context.get()
    if bot_id is None:
        raise RuntimeError("No tenant in context. TenantMiddleware must be applied.")
    return bot_id


def set_current_tenant(bot_id: int) -> None:
    """
    Set current tenant (bot_id) in context.

    Args:
        bot_id: Bot ID to set as current tenant
    """
    tenant_context.set(bot_id)
    logger.debug(f"Tenant context set: bot_id={bot_id}")


def clear_current_tenant() -> None:
    """Clear current tenant from context."""
    tenant_context.set(None)
    logger.debug("Tenant context cleared")
