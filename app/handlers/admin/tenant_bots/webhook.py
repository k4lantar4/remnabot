"""Webhook management handlers for tenant bots."""

from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sql_text

from app.database.models import User
from app.database.crud.bot import get_bot_by_id
from app.localization.texts import get_texts
from app.utils.decorators import error_handler
from app.utils.permissions import admin_required
from app.services.bot_config_service import BotConfigService
from .common import logger
from app.config import settings
from urllib.parse import urljoin


@admin_required
@error_handler
async def update_all_webhooks(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Update webhooks for all active bots."""
    texts = get_texts(db_user.language)

    from app.bot import active_bots, active_dispatchers
    from app.config import settings
    from urllib.parse import urljoin

    # Check if webhook mode is enabled
    bot_run_mode = settings.get_bot_run_mode()
    telegram_webhook_enabled = bot_run_mode in {"webhook", "both"}

    if not telegram_webhook_enabled:
        await callback.answer(
            texts.t(
                "ADMIN_TENANT_BOTS_WEBHOOK_DISABLED", "❌ Webhook mode is disabled. Set BOT_RUN_MODE=webhook or both"
            ),
            show_alert=True,
        )
        return

    base_webhook_url = settings.get_telegram_webhook_url()
    if not base_webhook_url:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOTS_WEBHOOK_URL_NOT_SET", "❌ WEBHOOK_URL is not set in configuration"),
            show_alert=True,
        )
        return

    await callback.answer(texts.t("UPDATING_WEBHOOKS"), show_alert=True)

    # Get active bots from database
    from app.database.crud.bot import get_active_bots

    active_bot_configs = await get_active_bots(db)

    if not active_bot_configs:
        await callback.message.edit_text(
            texts.t("ADMIN_TENANT_BOTS_NO_ACTIVE_BOTS", "❌ No active bots found"), parse_mode="HTML"
        )
        return

    # Get dispatcher to resolve allowed updates
    if active_dispatchers:
        first_dp = list(active_dispatchers.values())[0]
        allowed_updates = first_dp.resolve_used_update_types()
    else:
        allowed_updates = None

    results = []
    success_count = 0
    error_count = 0

    for bot_config in active_bot_configs:
        bot_id = bot_config.id

        # Get bot instance from active_bots registry
        if bot_id not in active_bots:
            results.append(f"❌ Bot {bot_id} ({bot_config.name}): Not initialized")
            error_count += 1
            continue

        bot_instance = active_bots[bot_id]

        # Construct webhook URL using bot_token (PRD FR2.1)
        bot_token = bot_config.telegram_bot_token
        bot_webhook_url = urljoin(base_webhook_url.rstrip("/") + "/", f"webhook/{bot_token}")

        try:
            await bot_instance.set_webhook(
                url=bot_webhook_url,
                secret_token=settings.WEBHOOK_SECRET_TOKEN,
                drop_pending_updates=settings.WEBHOOK_DROP_PENDING_UPDATES,
                allowed_updates=allowed_updates,
            )
            results.append(f"✅ Bot {bot_id} ({bot_config.name}): {bot_webhook_url}")
            success_count += 1
            logger.info(f"✅ Webhook updated for bot {bot_id} ({bot_config.name}): {bot_webhook_url}")
        except Exception as e:
            error_msg = str(e)[:100]  # Limit error message length
            results.append(f"❌ Bot {bot_id} ({bot_config.name}): {error_msg}")
            error_count += 1
            logger.error(f"❌ Failed to update webhook for bot {bot_id} ({bot_config.name}): {e}", exc_info=True)

    # Build result message
    result_text = texts.t(
        "ADMIN_TENANT_BOTS_WEBHOOK_UPDATE_RESULT",
        """🔄 <b>Webhook Update Results</b>

✅ Success: {success}
❌ Errors: {errors}

<b>Details:</b>
{details}

<a href="admin_tenant_bots_menu">🔙 Back to Menu</a>""",
    ).format(
        success=success_count,
        errors=error_count,
        details="\n".join(results[:20]),  # Limit to 20 results
    )

    if len(results) > 20:
        result_text += f"\n\n... and {len(results) - 20} more"

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOTS_MENU", "🔙 Back to Menu"), callback_data="admin_tenant_bots_menu"
                )
            ]
        ]
    )

    await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
