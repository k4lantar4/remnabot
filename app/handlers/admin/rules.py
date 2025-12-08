import logging
from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.states import AdminStates
from app.database.models import User
from app.localization.texts import get_texts
from app.utils.decorators import admin_required, error_handler
from app.utils.validators import validate_html_tags, get_html_help_text
from app.database.crud.rules import get_current_rules_content, create_or_update_rules, clear_all_rules

logger = logging.getLogger(__name__)


@admin_required
@error_handler
async def show_rules_management(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    text = texts.t(
        "ADMIN_RULES_PANEL",
        "📋 <b>Service rules management</b>\n\n"
        "Current rules are shown to users during registration and in the main menu.\n\n"
        "Choose an action:"
    )
    
    keyboard = [
        [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_EDIT_BUTTON", "📝 Edit rules"), callback_data="admin_edit_rules")],
        [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_VIEW_BUTTON", "👀 View rules"), callback_data="admin_view_rules")],
        [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_CLEAR_BUTTON", "🗑️ Clear rules"), callback_data="admin_clear_rules")],
        [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_HTML_HELP", "ℹ️ HTML help"), callback_data="admin_rules_help")],
        [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_BACK", "⬅️ Back"), callback_data="admin_submenu_settings")]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def view_current_rules(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    try:
        current_rules = await get_current_rules_content(db, db_user.language)
        
        texts = get_texts(db_user.language)
        is_valid, error_msg = validate_html_tags(current_rules)
        warning = ""
        if not is_valid:
            warning = texts.t("ADMIN_RULES_HTML_WARNING", "\n\n⚠️ <b>Warning:</b> HTML error found in rules: {error}").format(error=error_msg)
        
        await callback.message.edit_text(
            texts.t("ADMIN_RULES_VIEW_TITLE", "📋 <b>Current service rules</b>\n\n{content}{warning}").format(content=current_rules, warning=warning),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_EDIT", "✏️ Edit"), callback_data="admin_edit_rules")],
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_CLEAR", "🗑️ Clear"), callback_data="admin_clear_rules")],
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_BACK", "⬅️ Back"), callback_data="admin_rules")]
            ])
        )
        await callback.answer()
    except Exception as e:
        texts = get_texts(db_user.language)
        logger.error(f"Error showing rules: {e}")
        await callback.message.edit_text(
            texts.t("ADMIN_RULES_LOAD_ERROR", "❌ Error loading rules. The text may contain invalid HTML tags."),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_CLEAR_BUTTON", "🗑️ Clear rules"), callback_data="admin_clear_rules")],
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_BACK", "⬅️ Back"), callback_data="admin_rules")]
            ])
        )
        await callback.answer()


@admin_required
@error_handler
async def start_edit_rules(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    try:
        current_rules = await get_current_rules_content(db, db_user.language)
        
        texts = get_texts(db_user.language)
        preview = current_rules[:500] + ('...' if len(current_rules) > 500 else '')
        
        text = texts.t(
            "ADMIN_RULES_EDIT_PROMPT",
            "✏️ <b>Editing rules</b>\n\n"
            "<b>Current rules:</b>\n<code>{preview}</code>\n\n"
            "Send the new service rules text.\n\n"
            "<i>HTML markup is supported. All tags will be validated before saving.</i>\n\n"
            "💡 <b>Tip:</b> Press /html_help to view supported tags"
        ).format(preview=preview)
        
        await callback.message.edit_text(
            text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_HTML_HELP", "ℹ️ HTML help"), callback_data="admin_rules_help")],
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_CANCEL", "❌ Cancel"), callback_data="admin_rules")]
            ])
        )
        
        await state.set_state(AdminStates.editing_rules_page)
        await callback.answer()
        
    except Exception as e:
        texts = get_texts(db_user.language)
        logger.error(f"Error starting rules edit: {e}")
        await callback.answer(texts.t("ADMIN_RULES_EDIT_LOAD_ERROR", "❌ Error loading rules for editing"), show_alert=True)


@admin_required
@error_handler
async def process_rules_edit(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    new_rules = message.text
    
    if len(new_rules) > 4000:
        await message.answer(texts.t("ADMIN_RULES_TOO_LONG", "❌ Rules text is too long (maximum 4000 characters)"))
        return
    
    is_valid, error_msg = validate_html_tags(new_rules)
    if not is_valid:
        await message.answer(
            texts.t(
                "ADMIN_RULES_HTML_ERROR_DETAILED",
                "❌ <b>HTML markup error:</b>\n{error}\n\n"
                "Please fix the errors and send the text again.\n\n"
                "💡 Use /html_help to view correct syntax"
            ).format(error=error_msg),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_HTML_HELP", "ℹ️ HTML help"), callback_data="admin_rules_help")],
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_CANCEL", "❌ Cancel"), callback_data="admin_rules")]
            ])
        )
        return
    
    try:
        preview_text = texts.t(
            "ADMIN_RULES_PREVIEW",
            "📋 <b>Preview of new rules:</b>\n\n{content}\n\n"
            "⚠️ <b>Warning!</b> New rules will be shown to all users.\n\n"
            "Save changes?"
        ).format(content=new_rules)
        
        if len(preview_text) > 4000:
            preview_text = texts.t(
                "ADMIN_RULES_PREVIEW_TRUNCATED",
                "📋 <b>Preview of new rules:</b>\n\n{content}...\n\n"
                "⚠️ <b>Warning!</b> New rules will be shown to all users.\n\n"
                "Rules text: {length} characters\n"
                "Save changes?"
            ).format(content=new_rules[:500], length=len(new_rules))
        
        await message.answer(
            preview_text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_SAVE", "✅ Save"), callback_data="admin_save_rules"),
                    types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_CANCEL", "❌ Cancel"), callback_data="admin_rules")
                ]
            ])
        )
        
        await state.update_data(new_rules=new_rules)
        
    except Exception as e:
        logger.error(f"Error showing rules preview: {e}")
        await message.answer(
            texts.t(
                "ADMIN_RULES_CONFIRM_SAVE",
                "⚠️ <b>Rules save confirmation</b>\n\n"
                "New rules are ready to save ({length} characters).\n"
                "HTML tags are validated and correct.\n\n"
                "Save changes?"
            ).format(length=len(new_rules)),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_SAVE", "✅ Save"), callback_data="admin_save_rules"),
                    types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_CANCEL", "❌ Cancel"), callback_data="admin_rules")
                ]
            ])
        )
        
        await state.update_data(new_rules=new_rules)


@admin_required
@error_handler
async def save_rules(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession
):
    data = await state.get_data()
    new_rules = data.get('new_rules')
    
    texts = get_texts(db_user.language)
    if not new_rules:
        await callback.answer(texts.t("ADMIN_RULES_NOT_FOUND", "❌ Error: rules text not found"), show_alert=True)
        return
    
    is_valid, error_msg = validate_html_tags(new_rules)
    if not is_valid:
        await callback.message.edit_text(
            texts.t(
                "ADMIN_RULES_SAVE_ERROR",
                "❌ <b>Save error:</b>\n{error}\n\n"
                "Rules were not saved due to HTML markup errors."
            ).format(error=error_msg),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_TRY_AGAIN", "🔄 Try again"), callback_data="admin_edit_rules")],
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_BACK_TO_RULES", "📋 Back to rules"), callback_data="admin_rules")]
            ])
        )
        await state.clear()
        await callback.answer()
        return
    
    try:
        await create_or_update_rules(
            db=db,
            content=new_rules,
            language=db_user.language
        )
        
        from app.localization.texts import clear_rules_cache
        clear_rules_cache()
        
        from app.localization.texts import refresh_rules_cache
        await refresh_rules_cache(db_user.language)
        
        await callback.message.edit_text(
            texts.t(
                "ADMIN_RULES_SAVED_SUCCESS",
                "✅ <b>Service rules successfully updated!</b>\n\n"
                "✓ New rules saved to database\n"
                "✓ HTML tags validated and correct\n"
                "✓ Rules cache cleared and updated\n"
                "✓ Rules will be shown to users\n\n"
                "📊 Text size: {length} characters"
            ).format(length=len(new_rules)),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_VIEW", "👀 View"), callback_data="admin_view_rules")],
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_BACK_TO_RULES", "📋 Back to rules"), callback_data="admin_rules")]
            ])
        )
        
        await state.clear()
        logger.info(f"Service rules updated by admin {db_user.telegram_id}")
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error saving rules: {e}")
        await callback.message.edit_text(
            texts.t(
                "ADMIN_RULES_SAVE_DB_ERROR",
                "❌ <b>Error saving rules</b>\n\n"
                "An error occurred while writing to the database. Please try again."
            ),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_TRY_AGAIN", "🔄 Try again"), callback_data="admin_save_rules")],
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_BACK_TO_RULES", "📋 Back to rules"), callback_data="admin_rules")]
            ])
        )
        await callback.answer()


@admin_required
@error_handler
async def clear_rules_confirmation(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t(
            "ADMIN_RULES_CLEAR_CONFIRM",
            "🗑️ <b>Clearing service rules</b>\n\n"
            "⚠️ <b>WARNING!</b> You are about to completely delete all service rules.\n\n"
            "After clearing, users will see default rules.\n\n"
            "This action cannot be undone. Continue?"
        ),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_CLEAR_YES", "✅ Yes, clear"), callback_data="admin_confirm_clear_rules"),
                types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_CANCEL", "❌ Cancel"), callback_data="admin_rules")
            ]
        ])
    )
    await callback.answer()


@admin_required
@error_handler
async def confirm_clear_rules(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    try:
        await clear_all_rules(db, db_user.language)
        
        from app.localization.texts import clear_rules_cache
        clear_rules_cache()
        
        texts = get_texts(db_user.language)
        await callback.message.edit_text(
            texts.t(
                "ADMIN_RULES_CLEARED_SUCCESS",
                "✅ <b>Rules successfully cleared!</b>\n\n"
                "✓ All user rules deleted\n"
                "✓ Default rules are now used\n"
                "✓ Rules cache cleared\n\n"
                "Users will see default rules."
            ),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_CREATE_NEW", "📝 Create new"), callback_data="admin_edit_rules")],
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_VIEW_CURRENT", "👀 View current"), callback_data="admin_view_rules")],
                [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_BACK_TO_RULES", "📋 Back to rules"), callback_data="admin_rules")]
            ])
        )
        
        logger.info(f"Rules cleared by admin {db_user.telegram_id}")
        await callback.answer()
        
    except Exception as e:
        texts = get_texts(db_user.language)
        logger.error(f"Error clearing rules: {e}")
        await callback.answer(texts.t("ADMIN_RULES_CLEAR_ERROR", "❌ Error clearing rules"), show_alert=True)


@admin_required
@error_handler
async def show_html_help(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    help_text = get_html_help_text()
    
    await callback.message.edit_text(
        texts.t("ADMIN_RULES_HTML_HELP_TITLE", "ℹ️ <b>HTML formatting help</b>\n\n{help}").format(help=help_text),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_EDIT_BUTTON", "📝 Edit rules"), callback_data="admin_edit_rules")],
            [types.InlineKeyboardButton(text=texts.t("ADMIN_RULES_BACK", "⬅️ Back"), callback_data="admin_rules")]
        ])
    )
    await callback.answer()


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_rules_management, F.data == "admin_rules")
    dp.callback_query.register(view_current_rules, F.data == "admin_view_rules")
    dp.callback_query.register(start_edit_rules, F.data == "admin_edit_rules")
    dp.callback_query.register(save_rules, F.data == "admin_save_rules")
    
    dp.callback_query.register(clear_rules_confirmation, F.data == "admin_clear_rules")
    dp.callback_query.register(confirm_clear_rules, F.data == "admin_confirm_clear_rules")
    
    dp.callback_query.register(show_html_help, F.data == "admin_rules_help")
    
    dp.message.register(process_rules_edit, AdminStates.editing_rules_page)