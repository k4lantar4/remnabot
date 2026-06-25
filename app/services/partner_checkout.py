"""Partner checkout field application for cabinet/miniapp purchase API."""

from __future__ import annotations

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.user import update_user
from app.database.models import Subscription, User
from app.utils.remnawave_panel_identity import MAX_PURCHASE_NOTE_LEN, validate_brand_prefix

logger = structlog.get_logger(__name__)


class PartnerCheckoutValidationError(ValueError):
    """Invalid partner checkout input from cabinet purchase request."""


def sanitize_purchase_note(value: str | None) -> str | None:
    note = (value or '').strip()
    if not note:
        return None
    return note[:MAX_PURCHASE_NOTE_LEN]


async def apply_partner_checkout_fields(
    db: AsyncSession,
    user: User,
    subscription: Subscription,
    *,
    purchase_note: str | None,
    panel_brand_prefix: str | None,
) -> bool:
    """Apply partner-only checkout fields. Returns use_brand_prefix for panel user create."""
    if not getattr(user, 'is_partner', False):
        if purchase_note or (panel_brand_prefix or '').strip():
            logger.debug(
                'Ignoring partner checkout fields for non-partner user',
                user_id=user.id,
            )
        return False

    subscription.purchase_note = sanitize_purchase_note(purchase_note)
    await db.flush()

    if panel_brand_prefix is not None:
        raw = panel_brand_prefix.strip()
        if raw:
            validated = validate_brand_prefix(raw)
            if validated is None:
                raise PartnerCheckoutValidationError('Invalid panel brand prefix')
            user = await update_user(db, user, panel_brand_prefix=validated)

    return bool((getattr(user, 'panel_brand_prefix', None) or '').strip())
