"""Unified admin access check — legacy ADMIN_IDS/EMAILS or RBAC role level > 0."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.rbac import UserRoleCRUD
from app.database.models import User


async def is_user_admin(db: AsyncSession, user: User) -> bool:
    """Return True if *user* is admin via legacy config or any active RBAC role."""
    if settings.is_admin(
        telegram_id=user.telegram_id,
        email=user.email if user.email_verified else None,
    ):
        return True

    _permissions, _role_names, max_level = await UserRoleCRUD.get_user_permissions(db, user.id)
    return max_level > 0
