import logging
import re
from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.localization.texts import get_texts
from app.states import AdminStates
from app.keyboards.admin import get_welcome_text_keyboard, get_admin_main_keyboard
from app.utils.decorators import admin_required, error_handler
from app.database.crud.welcome_text import (
    get_active_welcome_text, 
    set_welcome_text, 
    get_current_welcome_text_or_default,
    get_available_placeholders,
    get_current_welcome_text_settings,
    toggle_welcome_text_status
)

logger = logging.getLogger(__name__)


def validate_html_tags(text: str, texts=None) -> tuple[bool, str | None]:
    """
    Validate HTML tags against Telegram API requirements.
    """
    allowed_tags = {
        'b', 'strong',  # bold
        'i', 'em',      # italic
        'u', 'ins',     # underline
        's', 'strike', 'del',  # strikethrough
        'code',         # monospace for short fragments
        'pre',          # monospace code block
        'a'             # links
    }
    
    # Remove placeholders before tag validation; placeholders are not tags
    placeholder_pattern = r'\{[^{}]+\}'
    clean_text = re.sub(placeholder_pattern, '', text)
    
    tag_pattern = r'<(/?)([a-zA-Z]+)(\s[^>]*)?>'
    tags_with_pos = [(m.group(1), m.group(2), m.group(3), m.start(), m.end()) for m in re.finditer(tag_pattern, clean_text)]
    
    for closing, tag, attrs, start_pos, end_pos in tags_with_pos:
        tag_lower = tag.lower()
        
        if tag_lower not in allowed_tags:
            allowed = ", ".join(sorted(allowed_tags))
            message = (
                texts.t(
                    "ADMIN_WELCOME_TEXT_HTML_UNSUPPORTED_TAG",
                    "Unsupported HTML tag: <{tag}>. Use only: {allowed}",
                ).format(tag=tag, allowed=allowed)
                if texts
                else f"Unsupported HTML tag: <{tag}>. Use only: {allowed}"
            )
            return False, message
        
        if tag_lower == 'a':
            if closing:
                continue
            if not attrs:
                message = (
                    texts.t(
                        "ADMIN_WELCOME_TEXT_HTML_A_NEEDS_HREF",
                        "Tag <a> must contain href attribute, e.g. <a href='URL'>link</a>",
                    )
                    if texts
                    else "Tag <a> must contain href attribute, e.g. <a href='URL'>link</a>"
                )
                return False, message
            
            if 'href=' not in attrs.lower():
                message = (
                    texts.t(
                        "ADMIN_WELCOME_TEXT_HTML_A_NEEDS_HREF",
                        "Tag <a> must contain href attribute, e.g. <a href='URL'>link</a>",
                    )
                    if texts
                    else "Tag <a> must contain href attribute, e.g. <a href='URL'>link</a>"
                )
                return False, message
            
            href_match = re.search(r'href\s*=\s*[\'"]([^\'"]+)[\'"]', attrs, re.IGNORECASE)
            if href_match:
                url = href_match.group(1)
                if not re.match(r'^https?://|^tg://', url, re.IGNORECASE):
                    message = (
                        texts.t(
                            "ADMIN_WELCOME_TEXT_HTML_A_INVALID_URL",
                            "URL in <a> must start with http://, https:// or tg://. Found: {url}",
                        ).format(url=url)
                        if texts
                        else f"URL in <a> must start with http://, https:// or tg://. Found: {url}"
                    )
                    return False, message
            else:
                message = (
                    texts.t(
                        "ADMIN_WELCOME_TEXT_HTML_A_URL_MISSING",
                        "Cannot extract URL from href attribute of <a> tag",
                    )
                    if texts
                    else "Cannot extract URL from href attribute of <a> tag"
                )
                return False, message
    
    stack = []
    for closing, tag, attrs, start_pos, end_pos in tags_with_pos:
        tag_lower = tag.lower()
        
        if tag_lower not in allowed_tags:
            continue
            
        if closing:
            if not stack:
                message = (
                    texts.t(
                        "ADMIN_WELCOME_TEXT_HTML_EXTRA_CLOSING",
                        "Extra closing tag: </{tag}>",
                    ).format(tag=tag)
                    if texts
                    else f"Extra closing tag: </{tag}>"
                )
                return False, message
                
            last_opening_tag = stack.pop()
            if last_opening_tag.lower() != tag_lower:
                message = (
                    texts.t(
                        "ADMIN_WELCOME_TEXT_HTML_MISMATCH",
                        "Tag </{tag}> does not match opening <{opening}>",
                    ).format(tag=tag, opening=last_opening_tag)
                    if texts
                    else f"Tag </{tag}> does not match opening <{last_opening_tag}>"
                )
                return False, message
        else:
            stack.append(tag)
    
    if stack:
        unclosed_tags = ", ".join([f"<{tag}>" for tag in stack])
        message = (
            texts.t(
                "ADMIN_WELCOME_TEXT_HTML_UNCLOSED",
                "Unclosed tags: {tags}",
            ).format(tags=unclosed_tags)
            if texts
            else f"Unclosed tags: {unclosed_tags}"
        )
        return False, message
    
    return True, None

def get_telegram_formatting_info(texts) -> str:
    return texts.t(
        "ADMIN_WELCOME_TEXT_FORMATTING_INFO",
        (
            "📝 <b>Supported formatting tags:</b>\n\n"
            "• <code>&lt;b&gt;bold&lt;/b&gt;</code> → <b>bold</b>\n"
            "• <code>&lt;i&gt;italic&lt;/i&gt;</code> → <i>italic</i>\n"
            "• <code>&lt;u&gt;underline&lt;/u&gt;</code> → <u>underline</u>\n"
            "• <code>&lt;s&gt;strikethrough&lt;/s&gt;</code> → <s>strikethrough</s>\n"
            "• <code>&lt;code&gt;monospace&lt;/code&gt;</code> → <code>monospace</code>\n"
            "• <code>&lt;pre&gt;code block&lt;/pre&gt;</code> → multiline code\n"
            '• <code>&lt;a href="URL"&gt;link&lt;/a&gt;</code> → link\n\n'
            "⚠️ <b>IMPORTANT:</b> Use only the tags above.\n"
            "Other HTML tags are not supported and will be shown as plain text.\n\n"
            "❌ <b>Do NOT use:</b> &lt;div&gt;, &lt;span&gt;, &lt;p&gt;, &lt;br&gt;, &lt;h1&gt;-&lt;h6&gt;, "
            "&lt;img&gt; and other HTML tags."
        ),
    )

@admin_required
@error_handler
async def show_welcome_text_panel(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    welcome_settings = await get_current_welcome_text_settings(db)
    status_emoji = "🟢" if welcome_settings['is_enabled'] else "🔴"
    status_text = texts.t("ADMIN_WELCOME_TEXT_ENABLED", "enabled") if welcome_settings['is_enabled'] else texts.t("ADMIN_WELCOME_TEXT_DISABLED", "disabled")
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_WELCOME_TEXT_PANEL",
            "👋 Welcome text management\n\n"
            "{emoji} <b>Status:</b> {status}\n\n"
            "Here you can manage the text that is shown to new users after registration.\n\n"
            "💡 Available placeholders for auto-replacement:"
        ).format(emoji=status_emoji, status=status_text),
        reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_required
@error_handler
async def toggle_welcome_text(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    new_status = await toggle_welcome_text_status(db, db_user.id)
    
    status_emoji = "🟢" if new_status else "🔴"
    status_text = texts.t("ADMIN_WELCOME_TEXT_ENABLED", "enabled") if new_status else texts.t("ADMIN_WELCOME_TEXT_DISABLED", "disabled")
    action_text = texts.t("ADMIN_WELCOME_TEXT_ENABLED_PLURAL", "enabled") if new_status else texts.t("ADMIN_WELCOME_TEXT_DISABLED_PLURAL", "disabled")
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_WELCOME_TEXT_PANEL_TOGGLE",
            "👋 Welcome text management\n\n"
            "{emoji} <b>Status:</b> {status}\n\n"
            "✅ Welcome messages {action}!\n\n"
            "Here you can manage the text that is shown to new users after registration.\n\n"
            "💡 Available placeholders for auto-replacement:"
        ).format(emoji=status_emoji, status=status_text, action=action_text),
        reply_markup=get_welcome_text_keyboard(db_user.language, new_status),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_required
@error_handler
async def show_current_welcome_text(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    welcome_settings = await get_current_welcome_text_settings(db)
    current_text = welcome_settings['text']
    is_enabled = welcome_settings['is_enabled']

    texts = get_texts(db_user.language)
    if not welcome_settings['id']:
        status = texts.t("ADMIN_WELCOME_TEXT_DEFAULT", "📝 Using default text:")
    else:
        status = texts.t("ADMIN_WELCOME_TEXT_CURRENT", "📝 Current welcome text:")
    
    status_emoji = "🟢" if is_enabled else "🔴"
    status_text = texts.t("ADMIN_WELCOME_TEXT_ENABLED", "enabled") if is_enabled else texts.t("ADMIN_WELCOME_TEXT_DISABLED", "disabled")
    
    placeholders = get_available_placeholders()
    placeholders_text = "\n".join([f"• <code>{key}</code> - {desc}" for key, desc in placeholders.items()])
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_WELCOME_TEXT_VIEW",
            "{emoji} <b>Status:</b> {status}\n\n"
            "{text_status}\n\n"
            "<code>{text}</code>\n\n"
            "💡 Available placeholders:\n{placeholders}"
        ).format(
            emoji=status_emoji,
            status=status_text,
            text_status=status,
            text=current_text,
            placeholders=placeholders_text
        ),
        reply_markup=get_welcome_text_keyboard(db_user.language, is_enabled),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_required
@error_handler
async def show_placeholders_help(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    welcome_settings = await get_current_welcome_text_settings(db)
    placeholders = get_available_placeholders()
    placeholders_text = "\n".join([f"• <code>{key}</code>\n  {desc}" for key, desc in placeholders.items()])
    
    help_text = texts.t(
        "ADMIN_WELCOME_TEXT_PLACEHOLDERS_HELP",
        "💡 Available placeholders for auto-replacement:\n\n"
        "{placeholders}\n\n"
        "📌 Usage examples:\n"
        "• <code>Hello, {user_name}! Welcome!</code>\n"
        "• <code>Hi, {first_name}! Glad to see you!</code>\n"
        "• <code>Hello, {username}! Thanks for registering!</code>\n\n"
        "If user data is missing, the word 'friend' is used."
    ).format(placeholders=placeholders_text)
    
    await callback.message.edit_text(
        help_text,
        reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_required
@error_handler
async def show_formatting_help(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    welcome_settings = await get_current_welcome_text_settings(db)
    texts = get_texts(db_user.language)
    formatting_info = get_telegram_formatting_info(texts)
    
    await callback.message.edit_text(
        formatting_info,
        reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_required
@error_handler
async def start_edit_welcome_text(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    welcome_settings = await get_current_welcome_text_settings(db)
    current_text = welcome_settings['text']
    
    placeholders = get_available_placeholders()
    placeholders_text = "\n".join([f"• <code>{key}</code> - {desc}" for key, desc in placeholders.items()])
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_WELCOME_TEXT_EDIT_PROMPT",
            "📝 Editing welcome text\n\n"
            "Current text:\n"
            "<code>{current}</code>\n\n"
            "💡 Available placeholders:\n{placeholders}\n\n"
            "Send the new text:"
        ).format(current=current_text, placeholders=placeholders_text),
        parse_mode="HTML"
    )
    
    await state.set_state(AdminStates.editing_welcome_text)
    await callback.answer()

@admin_required
@error_handler
async def process_welcome_text_edit(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    new_text = message.text.strip()
    
    if len(new_text) < 10:
        await message.answer(texts.t("ADMIN_WELCOME_TEXT_TOO_SHORT", "❌ Text is too short! Minimum 10 characters."))
        return
    
    if len(new_text) > 4000:
        await message.answer(texts.t("ADMIN_WELCOME_TEXT_TOO_LONG", "❌ Text is too long! Maximum 4000 characters."))
        return
    
    is_valid, error_msg = validate_html_tags(new_text, texts)
    if not is_valid:
        await message.answer(texts.t("ADMIN_WELCOME_TEXT_HTML_ERROR", "❌ HTML markup error:\n\n{error}").format(error=error_msg))
        return
    
    success = await set_welcome_text(db, new_text, db_user.id)
    
    if success:
        welcome_settings = await get_current_welcome_text_settings(db)
        status_emoji = "🟢" if welcome_settings['is_enabled'] else "🔴"
        status_text = texts.t("ADMIN_WELCOME_TEXT_ENABLED", "enabled") if welcome_settings['is_enabled'] else texts.t("ADMIN_WELCOME_TEXT_DISABLED", "disabled")
        
        placeholders = get_available_placeholders()
        placeholders_text = "\n".join([f"• <code>{key}</code>" for key in placeholders.keys()])
        
        await message.answer(
            texts.t(
                "ADMIN_WELCOME_TEXT_UPDATED_SUCCESS",
                "✅ Welcome text successfully updated!\n\n"
                "{emoji} <b>Status:</b> {status}\n\n"
                "New text:\n"
                "<code>{text}</code>\n\n"
                "💡 Placeholders will be replaced: {placeholders}"
            ).format(
                emoji=status_emoji,
                status=status_text,
                text=new_text,
                placeholders=placeholders_text
            ),
            reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
            parse_mode="HTML"
        )
    else:
        welcome_settings = await get_current_welcome_text_settings(db)
        await message.answer(
            texts.t("ADMIN_WELCOME_TEXT_SAVE_ERROR", "❌ Error saving text. Please try again."),
            reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled'])
        )
    
    await state.clear()

@admin_required
@error_handler
async def reset_welcome_text(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    default_text = await get_current_welcome_text_or_default()
    success = await set_welcome_text(db, default_text, db_user.id)
    
    texts = get_texts(db_user.language)
    if success:
        welcome_settings = await get_current_welcome_text_settings(db)
        status_emoji = "🟢" if welcome_settings['is_enabled'] else "🔴"
        status_text = texts.t("ADMIN_WELCOME_TEXT_ENABLED", "enabled") if welcome_settings['is_enabled'] else texts.t("ADMIN_WELCOME_TEXT_DISABLED", "disabled")
        
        await callback.message.edit_text(
            texts.t(
                "ADMIN_WELCOME_TEXT_RESET_SUCCESS",
                "✅ Welcome text reset to default!\n\n"
                "{emoji} <b>Status:</b> {status}\n\n"
                "Default text:\n"
                "<code>{text}</code>\n\n"
                "💡 Placeholder <code>{{user_name}}</code> will be replaced with user name"
            ).format(emoji=status_emoji, status=status_text, text=default_text),
            reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
            parse_mode="HTML"
        )
    else:
        welcome_settings = await get_current_welcome_text_settings(db)
        await callback.message.edit_text(
            texts.t("ADMIN_WELCOME_TEXT_RESET_ERROR", "❌ Error resetting text. Please try again."),
            reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled'])
        )
    
    await callback.answer()

@admin_required
@error_handler
async def show_preview_welcome_text(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    from app.database.crud.welcome_text import get_welcome_text_for_user
    
    texts = get_texts(db_user.language)
    class TestUser:
        def __init__(self):
            self.first_name = "John"
            self.username = "test_user"
    
    test_user = TestUser()
    preview_text = await get_welcome_text_for_user(db, test_user)
    
    welcome_settings = await get_current_welcome_text_settings(db)
    
    if preview_text:
        await callback.message.edit_text(
            texts.t(
                "ADMIN_WELCOME_TEXT_PREVIEW_ENABLED",
                "👁️ Preview\n\n"
                "How the text will look for user 'John' (@test_user):\n\n"
                "<code>{text}</code>"
            ).format(text=preview_text),
            reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            texts.t(
                "ADMIN_WELCOME_TEXT_PREVIEW_DISABLED",
                "👁️ Preview\n\n"
                "🔴 Welcome messages are disabled.\n"
                "New users will not receive welcome text after registration."
            ),
            reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
            parse_mode="HTML"
        )
    
    await callback.answer()

def register_welcome_text_handlers(dp: Dispatcher):
    dp.callback_query.register(
        show_welcome_text_panel,
        F.data == "welcome_text_panel"
    )
    
    dp.callback_query.register(
        toggle_welcome_text,
        F.data == "toggle_welcome_text"
    )
    
    dp.callback_query.register(
        show_current_welcome_text,
        F.data == "show_welcome_text"
    )
    
    dp.callback_query.register(
        show_placeholders_help,
        F.data == "show_placeholders_help"
    )
    
    dp.callback_query.register(
        show_formatting_help,
        F.data == "show_formatting_help"
    )
    
    dp.callback_query.register(
        show_preview_welcome_text,
        F.data == "preview_welcome_text"
    )
    
    dp.callback_query.register(
        start_edit_welcome_text,
        F.data == "edit_welcome_text"
    )
    
    dp.callback_query.register(
        reset_welcome_text,
        F.data == "reset_welcome_text"
    )
    
    dp.message.register(
        process_welcome_text_edit,
        AdminStates.editing_welcome_text
    )
