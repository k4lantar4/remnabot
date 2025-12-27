"""Bot management handlers (activate, deactivate, delete)."""
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.models import User, Transaction, Subscription
from app.database.crud.bot import get_bot_by_id, activate_bot, deactivate_bot, delete_bot
from app.localization.texts import get_texts
from app.utils.decorators import error_handler, admin_required
from .detail import show_bot_detail
from .common import logger


@admin_required
@error_handler
async def activate_tenant_bot(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Activate a tenant bot."""
    texts = get_texts(db_user.language)
    
    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    if bot.is_active:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_ALREADY_ACTIVE", "Bot is already active"),
            show_alert=True
        )
        return
    
    success = await activate_bot(db, bot_id)
    if success:
        await callback.answer(texts.t("BOT_ACTIVATED"), show_alert=True)
        # Refresh detail view
        await show_bot_detail(callback, db_user, db)
    else:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_ACTIVATE_ERROR", "❌ Failed to activate bot"),
            show_alert=True
        )


@admin_required
@error_handler
async def deactivate_tenant_bot(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Deactivate a tenant bot."""
    texts = get_texts(db_user.language)
    
    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    if bot.is_master:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_CANNOT_DEACTIVATE_MASTER", "❌ Cannot deactivate master bot"),
            show_alert=True
        )
        return
    
    if not bot.is_active:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_ALREADY_INACTIVE", "Bot is already inactive"),
            show_alert=True
        )
        return
    
    success = await deactivate_bot(db, bot_id)
    if success:
        await callback.answer(texts.t("BOT_DEACTIVATED"), show_alert=True)
        # Refresh detail view
        await show_bot_detail(callback, db_user, db)
    else:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_DEACTIVATE_ERROR", "❌ Failed to deactivate bot"),
            show_alert=True
        )


@admin_required
@error_handler
async def start_delete_bot(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Start bot deletion flow with confirmation (AC12)."""
    texts = get_texts(db_user.language)
    
    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    if bot.is_master:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_CANNOT_DELETE_MASTER", "❌ Cannot delete master bot"),
            show_alert=True
        )
        return
    
    # Get statistics for warning
    user_count_result = await db.execute(
        select(func.count(User.id)).where(User.bot_id == bot_id)
    )
    user_count = user_count_result.scalar() or 0
    
    sub_count_result = await db.execute(
        select(func.count(Subscription.id)).where(Subscription.bot_id == bot_id)
    )
    sub_count = sub_count_result.scalar() or 0
    
    trans_count_result = await db.execute(
        select(func.count(Transaction.id)).where(Transaction.bot_id == bot_id)
    )
    trans_count = trans_count_result.scalar() or 0
    
    text = texts.t(
        "ADMIN_TENANT_BOT_DELETE_CONFIRM",
        """🗑️ <b>Delete Bot: {name}</b>

⚠️ <b>WARNING:</b> This action cannot be undone!

This will delete:
• {user_count} users associated with this bot
• {sub_count} subscriptions
• {trans_count} transactions
• All configurations and feature flags

<b>Choose deletion type:</b>
• <b>Soft Delete:</b> Deactivates bot (can be reactivated)
• <b>Hard Delete:</b> Permanently removes bot and all data"""
    ).format(
        name=bot.name,
        user_count=user_count,
        sub_count=sub_count,
        trans_count=trans_count
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_DELETE_SOFT", "⏸️ Soft Delete (Deactivate)"),
                callback_data=f"admin_tenant_bot_delete_soft:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_DELETE_HARD", "🗑️ Hard Delete (Permanent)"),
                callback_data=f"admin_tenant_bot_delete_hard:{bot_id}"
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                callback_data=f"admin_tenant_bot_detail:{bot_id}"
            )
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def confirm_delete_bot(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Confirm and execute bot deletion (AC12)."""
    texts = get_texts(db_user.language)
    
    try:
        parts = callback.data.split(":")
        delete_type = parts[1]  # "soft" or "hard"
        bot_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    if bot.is_master:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_CANNOT_DELETE_MASTER", "❌ Cannot delete master bot"),
            show_alert=True
        )
        return
    
    try:
        # Shutdown bot first (stop polling, remove from active_bots)
        from app.bot import shutdown_bot
        await shutdown_bot(bot_id)
        
        if delete_type == "soft":
            # Soft delete: deactivate bot
            success = await deactivate_bot(db, bot_id)
            if success:
                await db.commit()
                result_text = texts.t(
                    "ADMIN_TENANT_BOT_DELETED_SOFT",
                    """✅ <b>Bot Deactivated</b>

Bot <b>{name}</b> has been deactivated.

The bot can be reactivated from the bot detail menu."""
                ).format(name=bot.name)
            else:
                result_text = texts.t(
                    "ADMIN_TENANT_BOT_DELETE_ERROR",
                    "❌ Failed to deactivate bot"
                )
        else:
            # Hard delete: permanently remove bot
            success = await delete_bot(db, bot_id)
            if success:
                result_text = texts.t(
                    "ADMIN_TENANT_BOT_DELETED_HARD",
                    """✅ <b>Bot Deleted</b>

Bot <b>{name}</b> and all associated data have been permanently deleted.

This action cannot be undone."""
                ).format(name=bot.name)
            else:
                result_text = texts.t(
                    "ADMIN_TENANT_BOT_DELETE_ERROR",
                    "❌ Failed to delete bot"
                )
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_TENANT_BOTS_MENU", "🏠 Bots Menu"),
                    callback_data="admin_tenant_bots_menu"
                )
            ]
        ])
        
        await callback.message.edit_text(result_text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error deleting bot {bot_id}: {e}", exc_info=True)
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_DELETE_ERROR", "❌ Error deleting bot"),
            show_alert=True
        )

