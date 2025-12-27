"""Test bot functionality handlers for tenant bots."""

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


@admin_required
@error_handler
async def test_bot_status(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Test bot status and connectivity."""
    texts = get_texts(db_user.language)

    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    await callback.answer(texts.t("TESTING_BOT"), show_alert=True)

    from app.bot import active_bots, active_dispatchers, polling_tasks
    from app.config import settings
    from app.webserver import telegram

    status_lines = []
    status_lines.append(f"🤖 <b>Bot Status Test</b>\n")
    status_lines.append(f"<b>Name:</b> {bot.name}")
    status_lines.append(f"<b>ID:</b> {bot.id}")
    status_lines.append(f"<b>Token:</b> {bot.telegram_bot_token[:20]}...\n")

    # Check if initialized
    is_initialized = bot_id in active_bots

    # Try to initialize if not initialized
    if not is_initialized:
        status_lines.append(f"<b>Initialized:</b> ❌ No")
        status_lines.append("\n🔄 <b>Attempting to initialize bot...</b>")

        try:
            from app.bot import initialize_single_bot, start_bot_polling, setup_bot_webhook

            # Get fresh bot config (get_bot_by_id is already imported at top of file)
            bot_config = await get_bot_by_id(db, bot_id)
            if bot_config and bot_config.is_active:
                result = await initialize_single_bot(bot_config)
                if result:
                    bot_instance, dp_instance = result
                    status_lines.append("✅ <b>Bot initialized successfully!</b>\n")

                    # Start polling if enabled
                    bot_run_mode = settings.get_bot_run_mode()
                    polling_enabled = bot_run_mode in {"polling", "both"}
                    if polling_enabled:
                        await start_bot_polling(bot_id, bot_instance, dp_instance)
                        status_lines.append("✅ <b>Polling started</b>\n")

                    # Setup webhook if enabled
                    telegram_webhook_enabled = bot_run_mode in {"webhook", "both"}
                    if telegram_webhook_enabled:
                        await setup_bot_webhook(bot_id, bot_instance)
                        status_lines.append("✅ <b>Webhook configured</b>\n")

                    is_initialized = True
                else:
                    status_lines.append("❌ <b>Failed to initialize bot</b>\n")
                    status_lines.append("Please check logs for details.\n")
            elif not bot_config:
                status_lines.append("❌ <b>Bot not found in database</b>\n")
            elif not bot_config.is_active:
                status_lines.append("❌ <b>Bot is not active</b>\n")
                status_lines.append("Activate the bot first.\n")
        except Exception as e:
            status_lines.append(f"❌ <b>Error during initialization: {str(e)[:100]}</b>\n")
            logger.error(f"Error initializing bot {bot_id} in test handler: {e}", exc_info=True)

    if is_initialized:
        status_lines.append(f"<b>Initialized:</b> ✅ Yes\n")
        bot_instance = active_bots[bot_id]
        dp_instance = active_dispatchers.get(bot_id)

        # Test bot connectivity
        try:
            bot_info = await bot_instance.get_me()
            status_lines.append(f"<b>Bot Username:</b> @{bot_info.username}")
            status_lines.append(f"<b>Bot Name:</b> {bot_info.first_name}")
            status_lines.append(f"<b>Connectivity:</b> ✅ Connected")
        except Exception as e:
            status_lines.append(f"<b>Connectivity:</b> ❌ Error: {str(e)[:50]}")

        # Check polling
        bot_run_mode = settings.get_bot_run_mode()
        polling_enabled = bot_run_mode in {"polling", "both"}
        if polling_enabled:
            is_polling = bot_id in polling_tasks and not polling_tasks[bot_id].done()
            status_lines.append(f"<b>Polling:</b> {'✅ Running' if is_polling else '❌ Not running'}")
        else:
            status_lines.append(f"<b>Polling:</b> ⏸️ Disabled (mode: {bot_run_mode})")

        # Check webhook
        telegram_webhook_enabled = bot_run_mode in {"webhook", "both"}
        if telegram_webhook_enabled:
            try:
                webhook_info = await bot_instance.get_webhook_info()
                if webhook_info.url:
                    status_lines.append(f"<b>Webhook:</b> ✅ Set")
                    status_lines.append(f"<b>Webhook URL:</b> {webhook_info.url}")
                    status_lines.append(f"<b>Pending Updates:</b> {webhook_info.pending_update_count}")
                else:
                    status_lines.append(f"<b>Webhook:</b> ❌ Not set")
            except Exception as e:
                status_lines.append(f"<b>Webhook:</b> ❌ Error: {str(e)[:50]}")
        else:
            status_lines.append(f"<b>Webhook:</b> ⏸️ Disabled (mode: {bot_run_mode})")

        # Check webhook registry
        if bot_id in telegram._bot_registry:
            status_lines.append(f"<b>Webhook Registry:</b> ✅ Registered")
        else:
            status_lines.append(f"<b>Webhook Registry:</b> ⚠️ Not registered (may use fallback)")

        # Check dispatcher
        if dp_instance:
            status_lines.append(f"<b>Dispatcher:</b> ✅ Available")
        else:
            status_lines.append(f"<b>Dispatcher:</b> ❌ Missing")

        # Final status
        status_lines.append("\n" + "=" * 30)
        status_lines.append("✅ <b>Bot is ready and operational!</b>")
        status_lines.append("=" * 30)
    else:
        status_lines.append("\n⚠️ <b>Bot initialization failed!</b>")
        status_lines.append("The bot needs to be initialized to work.")
        status_lines.append("Try:")
        status_lines.append("• Restarting the server")
        status_lines.append("• Using 'Update All Webhooks' button")
        status_lines.append("• Checking bot is active in database")

    result_text = "\n".join(status_lines)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOT_VIEW", "👁️ View Bot"),
                    callback_data=f"admin_tenant_bot_detail:{bot_id}",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOTS_MENU", "🏠 Bots Menu"), callback_data="admin_tenant_bots_menu"
                )
            ],
        ]
    )

    await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()
