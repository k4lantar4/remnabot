import html
import logging
from datetime import datetime

from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.localization.texts import get_texts
from app.services.faq_service import FaqService
from app.states import AdminStates
from app.utils.decorators import admin_required, error_handler
from app.utils.validators import get_html_help_text, validate_html_tags

logger = logging.getLogger(__name__)


def _format_timestamp(value: datetime | None) -> str:
    if not value:
        return ""
    try:
        return value.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return ""


async def _build_overview(
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)

    normalized_language = FaqService.normalize_language(db_user.language)
    setting = await FaqService.get_setting(
        db,
        db_user.language,
        fallback=False,
    )

    pages = await FaqService.get_pages(
        db,
        db_user.language,
        include_inactive=True,
        fallback=False,
    )

    total_pages = len(pages)
    active_pages = sum(1 for page in pages if page.is_active)

    description = texts.t(
        "ADMIN_FAQ_DESCRIPTION",
        "FAQ is shown in the \"Info\" section.",
    )

    if setting and not setting.is_enabled:
        status_text = texts.t(
            "ADMIN_FAQ_STATUS_DISABLED",
            "⚠️ FAQ display is turned off.",
        )
    elif active_pages:
        status_text = texts.t(
            "ADMIN_FAQ_STATUS_ENABLED",
            "✅ FAQ is enabled. Active pages: {count}.",
        ).format(count=active_pages)
    elif total_pages:
        status_text = texts.t(
            "ADMIN_FAQ_STATUS_ENABLED_EMPTY",
            "⚠️ FAQ is enabled but there are no active pages.",
        )
    else:
        status_text = texts.t(
            "ADMIN_FAQ_STATUS_EMPTY",
            "⚠️ FAQ has not been configured yet.",
        )

    pages_overview = texts.t(
        "ADMIN_FAQ_PAGES_EMPTY",
        "No pages have been created yet.",
    )

    if pages:
        rows: list[str] = []
        for index, page in enumerate(pages, start=1):
            title = (page.title or "").strip()
            if not title:
                title = texts.t("FAQ_PAGE_UNTITLED", "Untitled")
            if len(title) > 60:
                title = f"{title[:57]}..."

            status_label = texts.t(
                "ADMIN_FAQ_PAGE_STATUS_ACTIVE",
                "✅ Active",
            )
            if not page.is_active:
                status_label = texts.t(
                    "ADMIN_FAQ_PAGE_STATUS_INACTIVE",
                    "🚫 Disabled",
                )

            updated = _format_timestamp(getattr(page, "updated_at", None))
            updated_block = f" ({updated})" if updated else ""
            rows.append(
                f"{index}. {html.escape(title)} — {status_label}{updated_block}"
            )

        pages_list_header = texts.t(
            "ADMIN_FAQ_PAGES_OVERVIEW",
            "<b>Page list:</b>\n{items}",
        )
        pages_overview = pages_list_header.format(items="\n".join(rows))

    language_block = texts.t(
        "ADMIN_FAQ_LANGUAGE",
        "Language: <code>{lang}</code>",
    ).format(lang=normalized_language)

    stats_block = texts.t(
        "ADMIN_FAQ_PAGE_STATS",
        "Total pages: {total}",
    ).format(total=total_pages)

    header = texts.t("ADMIN_FAQ_HEADER", "❓ <b>FAQ</b>")
    actions_prompt = texts.t(
        "ADMIN_FAQ_ACTION_PROMPT",
        "Choose an action:",
    )

    message_parts = [
        header,
        description,
        language_block,
        status_text,
        stats_block,
        pages_overview,
        actions_prompt,
    ]

    overview_text = "\n\n".join(part for part in message_parts if part)

    buttons: list[list[types.InlineKeyboardButton]] = []

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t(
                "ADMIN_FAQ_ADD_PAGE_BUTTON",
                "➕ Add page",
            ),
            callback_data="admin_faq_create",
        )
    ])

    for page in pages[:25]:
        title = (page.title or "").strip()
        if not title:
            title = texts.t("FAQ_PAGE_UNTITLED", "Untitled")
        if len(title) > 40:
            title = f"{title[:37]}..."
        buttons.append([
            types.InlineKeyboardButton(
                text=f"{page.display_order}. {title}",
                callback_data=f"admin_faq_page:{page.id}",
            )
        ])

    toggle_text = texts.t(
        "ADMIN_FAQ_ENABLE_BUTTON",
        "✅ Enable display",
    )
    if setting and setting.is_enabled:
        toggle_text = texts.t(
            "ADMIN_FAQ_DISABLE_BUTTON",
            "🚫 Disable display",
        )

    buttons.append([
        types.InlineKeyboardButton(
            text=toggle_text,
            callback_data="admin_faq_toggle",
        )
    ])

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_FAQ_HTML_HELP", "ℹ️ HTML help"),
            callback_data="admin_faq_help",
        )
    ])

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data="admin_submenu_settings",
        )
    ])

    return overview_text, types.InlineKeyboardMarkup(inline_keyboard=buttons)


@admin_required
@error_handler
async def show_faq_management(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    overview_text, markup = await _build_overview(db_user, db)

    await callback.message.edit_text(
        overview_text,
        reply_markup=markup,
    )
    await callback.answer()


@admin_required
@error_handler
async def toggle_faq(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    setting = await FaqService.toggle_enabled(db, db_user.language)

    if setting.is_enabled:
        alert_text = texts.t(
            "ADMIN_FAQ_ENABLED_ALERT",
            "✅ FAQ enabled.",
        )
    else:
        alert_text = texts.t(
            "ADMIN_FAQ_DISABLED_ALERT",
            "🚫 FAQ disabled.",
        )

    overview_text, markup = await _build_overview(db_user, db)

    await callback.message.edit_text(
        overview_text,
        reply_markup=markup,
    )
    await callback.answer(alert_text, show_alert=True)


@admin_required
@error_handler
async def start_create_faq_page(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)

    await state.set_state(AdminStates.creating_faq_title)
    await state.update_data(faq_language=db_user.language)

    await callback.message.edit_text(
        texts.t(
            "ADMIN_FAQ_ENTER_TITLE",
            "Enter a title for the new FAQ page:",
        ),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t(
                            "ADMIN_FAQ_CANCEL_BUTTON",
                            "⬅️ Cancel",
                        ),
                        callback_data="admin_faq_cancel",
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def cancel_faq_creation(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    await state.clear()
    await show_faq_management(callback, db_user, db)


@admin_required
@error_handler
async def process_new_faq_title(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    title = (message.text or "").strip()

    if not title:
        await message.answer(
            texts.t(
                "ADMIN_FAQ_TITLE_EMPTY",
                "❌ Title cannot be empty.",
            )
        )
        return

    if len(title) > 255:
        await message.answer(
            texts.t(
                "ADMIN_FAQ_TITLE_TOO_LONG",
                "❌ Title is too long. Maximum 255 characters.",
            )
        )
        return

    await state.update_data(faq_title=title)
    await state.set_state(AdminStates.creating_faq_content)

    await message.answer(
        texts.t(
            "ADMIN_FAQ_ENTER_CONTENT",
            "Send the content of the FAQ page. HTML is allowed.",
        )
    )


@admin_required
@error_handler
async def process_new_faq_content(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    content = message.text or ""

    if len(content) > 6000:
        await message.answer(
            texts.t(
                "ADMIN_FAQ_CONTENT_TOO_LONG",
                "❌ Content is too long. Maximum 6000 characters.",
            )
        )
        return

    if not content.strip():
        await message.answer(
            texts.t(
                "ADMIN_FAQ_CONTENT_EMPTY",
                "❌ Content cannot be empty.",
            )
        )
        return

    is_valid, error_message = validate_html_tags(content)
    if not is_valid:
        await message.answer(
            texts.t(
                "ADMIN_FAQ_HTML_ERROR",
                "❌ HTML error: {error}",
            ).format(error=error_message)
        )
        return

    data = await state.get_data()
    title = data.get("faq_title") or texts.t("FAQ_PAGE_UNTITLED", "Untitled")
    language = data.get("faq_language", db_user.language)

    await FaqService.create_page(
        db,
        language=language,
        title=title,
        content=content,
    )

    logger.info(
        "Admin %s created FAQ page (%d characters)",
        db_user.telegram_id,
        len(content),
    )

    await state.clear()

    success_text = texts.t(
        "ADMIN_FAQ_PAGE_CREATED",
        "✅ FAQ page created.",
    )

    reply_markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t(
                        "ADMIN_FAQ_BACK_TO_LIST",
                        "⬅️ Back to FAQ settings",
                    ),
                    callback_data="admin_faq",
                )
            ]
        ]
    )

    await message.answer(success_text, reply_markup=reply_markup)


@admin_required
@error_handler
async def show_faq_page_details(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)

    raw_id = (callback.data or "").split(":", 1)[-1]
    try:
        page_id = int(raw_id)
    except ValueError:
        await callback.answer()
        return

    page = await FaqService.get_page(
        db,
        page_id,
        db_user.language,
        fallback=False,
        include_inactive=True,
    )

    if not page:
        await callback.answer(
            texts.t(
                "ADMIN_FAQ_PAGE_NOT_FOUND",
                "⚠️ Page not found.",
            ),
            show_alert=True,
        )
        return

    header = texts.t("ADMIN_FAQ_PAGE_HEADER", "📄 <b>FAQ page</b>")
    title = (page.title or "").strip() or texts.t("FAQ_PAGE_UNTITLED", "Untitled")
    status_label = texts.t(
        "ADMIN_FAQ_PAGE_STATUS_ACTIVE",
        "✅ Active",
    )
    if not page.is_active:
        status_label = texts.t(
            "ADMIN_FAQ_PAGE_STATUS_INACTIVE",
            "🚫 Disabled",
        )

    updated_at = _format_timestamp(getattr(page, "updated_at", None))
    updated_block = ""
    if updated_at:
        updated_block = texts.t(
            "ADMIN_FAQ_PAGE_UPDATED",
            "Updated: {timestamp}",
        ).format(timestamp=updated_at)

    preview = (page.content or "").strip()
    preview_text = texts.t(
        "ADMIN_FAQ_PAGE_PREVIEW_EMPTY",
        "Content has not been provided yet.",
    )
    if preview:
        preview_trimmed = preview[:400]
        if len(preview) > 400:
            preview_trimmed += "..."
        preview_text = (
            texts.t("ADMIN_FAQ_PAGE_PREVIEW", "<b>Preview:</b>\n{content}")
            .format(content=html.escape(preview_trimmed))
        )

    message_parts = [
        header,
        texts.t(
            "ADMIN_FAQ_PAGE_TITLE",
            "<b>Title:</b> {title}",
        ).format(title=html.escape(title)),
        texts.t(
            "ADMIN_FAQ_PAGE_STATUS",
            "Status: {status}",
        ).format(status=status_label),
        preview_text,
        updated_block,
    ]

    message_text = "\n\n".join(part for part in message_parts if part)

    buttons: list[list[types.InlineKeyboardButton]] = []

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_FAQ_EDIT_TITLE_BUTTON", "✏️ Edit title"),
            callback_data=f"admin_faq_edit_title:{page.id}",
        )
    ])
    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_FAQ_EDIT_CONTENT_BUTTON", "📝 Edit text"),
            callback_data=f"admin_faq_edit_content:{page.id}",
        )
    ])

    toggle_text = texts.t("ADMIN_FAQ_PAGE_ENABLE_BUTTON", "✅ Enable page")
    if page.is_active:
        toggle_text = texts.t(
            "ADMIN_FAQ_PAGE_DISABLE_BUTTON",
            "🚫 Disable page",
        )

    buttons.append([
        types.InlineKeyboardButton(
            text=toggle_text,
            callback_data=f"admin_faq_toggle_page:{page.id}",
        )
    ])

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_FAQ_PAGE_MOVE_UP", "⬆️ Up"),
            callback_data=f"admin_faq_move:{page.id}:up",
        ),
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_FAQ_PAGE_MOVE_DOWN", "⬇️ Down"),
            callback_data=f"admin_faq_move:{page.id}:down",
        ),
    ])

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_FAQ_PAGE_DELETE_BUTTON", "🗑️ Delete"),
            callback_data=f"admin_faq_delete:{page.id}",
        )
    ])

    buttons.append([
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_FAQ_BACK_TO_LIST", "⬅️ Back to FAQ settings"),
            callback_data="admin_faq",
        )
    ])

    await callback.message.edit_text(
        message_text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@admin_required
@error_handler
async def start_edit_faq_title(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)

    raw_id = (callback.data or "").split(":", 1)[-1]
    try:
        page_id = int(raw_id)
    except ValueError:
        await callback.answer()
        return

    page = await FaqService.get_page(
        db,
        page_id,
        db_user.language,
        fallback=False,
        include_inactive=True,
    )

    if not page:
        await callback.answer(
            texts.t(
                "ADMIN_FAQ_PAGE_NOT_FOUND",
                "⚠️ Page not found.",
            ),
            show_alert=True,
        )
        return

    await state.set_state(AdminStates.editing_faq_title)
    await state.update_data(faq_page_id=page.id)

    await callback.message.edit_text(
        texts.t(
            "ADMIN_FAQ_EDIT_TITLE_PROMPT",
            "Enter a new title for the page:",
        ),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t(
                            "ADMIN_FAQ_CANCEL_BUTTON",
                            "⬅️ Cancel",
                        ),
                        callback_data=f"admin_faq_page:{page.id}",
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def process_edit_faq_title(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    title = (message.text or "").strip()

    if not title:
        await message.answer(
            texts.t(
                "ADMIN_FAQ_TITLE_EMPTY",
                "❌ Title cannot be empty.",
            )
        )
        return

    if len(title) > 255:
        await message.answer(
            texts.t(
                "ADMIN_FAQ_TITLE_TOO_LONG",
                "❌ Title is too long. Maximum 255 characters.",
            )
        )
        return

    data = await state.get_data()
    page_id = data.get("faq_page_id")

    if not page_id:
        await state.clear()
        await message.answer(texts.t("ADMIN_FAQ_UNEXPECTED_STATE", "⚠️ State was reset."))
        return

    page = await FaqService.get_page(
        db,
        page_id,
        db_user.language,
        fallback=False,
        include_inactive=True,
    )

    if not page:
        await message.answer(
            texts.t("ADMIN_FAQ_PAGE_NOT_FOUND", "⚠️ Page not found."),
        )
        await state.clear()
        return

    await FaqService.update_page(db, page, title=title)
    await state.clear()

    await message.answer(
        texts.t("ADMIN_FAQ_TITLE_UPDATED", "✅ Title updated."),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(
                text=texts.t("ADMIN_FAQ_BACK_TO_LIST", "⬅️ Back to FAQ settings"),
                callback_data="admin_faq",
            )]]
        ),
    )


@admin_required
@error_handler
async def start_edit_faq_content(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)

    raw_id = (callback.data or "").split(":", 1)[-1]
    try:
        page_id = int(raw_id)
    except ValueError:
        await callback.answer()
        return

    page = await FaqService.get_page(
        db,
        page_id,
        db_user.language,
        fallback=False,
        include_inactive=True,
    )

    if not page:
        await callback.answer(
            texts.t("ADMIN_FAQ_PAGE_NOT_FOUND", "⚠️ Page not found."),
            show_alert=True,
        )
        return

    await state.set_state(AdminStates.editing_faq_content)
    await state.update_data(faq_page_id=page.id)

    await callback.message.edit_text(
        texts.t(
            "ADMIN_FAQ_EDIT_CONTENT_PROMPT",
            "Send the new text for the FAQ page.",
        ),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t(
                            "ADMIN_FAQ_CANCEL_BUTTON",
                            "⬅️ Cancel",
                        ),
                        callback_data=f"admin_faq_page:{page.id}",
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def process_edit_faq_content(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    content = message.text or ""

    if len(content) > 6000:
        await message.answer(
            texts.t(
                "ADMIN_FAQ_CONTENT_TOO_LONG",
                "❌ Content is too long. Maximum 6000 characters.",
            )
        )
        return

    if not content.strip():
        await message.answer(
            texts.t(
                "ADMIN_FAQ_CONTENT_EMPTY",
                "❌ Content cannot be empty.",
            )
        )
        return

    is_valid, error_message = validate_html_tags(content)
    if not is_valid:
        await message.answer(
            texts.t(
                "ADMIN_FAQ_HTML_ERROR",
                "❌ HTML error: {error}",
            ).format(error=error_message)
        )
        return

    data = await state.get_data()
    page_id = data.get("faq_page_id")

    if not page_id:
        await state.clear()
        await message.answer(texts.t("ADMIN_FAQ_UNEXPECTED_STATE", "⚠️ State was reset."))
        return

    page = await FaqService.get_page(
        db,
        page_id,
        db_user.language,
        fallback=False,
        include_inactive=True,
    )

    if not page:
        await message.answer(
            texts.t("ADMIN_FAQ_PAGE_NOT_FOUND", "⚠️ Page not found."),
        )
        await state.clear()
        return

    await FaqService.update_page(db, page, content=content)
    await state.clear()

    await message.answer(
        texts.t("ADMIN_FAQ_CONTENT_UPDATED", "✅ Page text updated."),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(
                text=texts.t("ADMIN_FAQ_BACK_TO_LIST", "⬅️ Back to FAQ settings"),
                callback_data="admin_faq",
            )]]
        ),
    )


@admin_required
@error_handler
async def toggle_faq_page(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)

    parts = (callback.data or "").split(":")
    try:
        page_id = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer()
        return

    page = await FaqService.get_page(
        db,
        page_id,
        db_user.language,
        fallback=False,
        include_inactive=True,
    )

    if not page:
        await callback.answer(
            texts.t("ADMIN_FAQ_PAGE_NOT_FOUND", "⚠️ Page not found."),
            show_alert=True,
        )
        return

    updated_page = await FaqService.update_page(db, page, is_active=not page.is_active)

    alert_text = texts.t(
        "ADMIN_FAQ_PAGE_ENABLED_ALERT",
        "✅ Page enabled.",
    )
    if not updated_page.is_active:
        alert_text = texts.t(
            "ADMIN_FAQ_PAGE_DISABLED_ALERT",
            "🚫 Page disabled.",
        )

    await callback.answer(alert_text, show_alert=True)
    await show_faq_page_details(callback, db_user, db)


@admin_required
@error_handler
async def delete_faq_page(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)

    parts = (callback.data or "").split(":")
    try:
        page_id = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer()
        return

    page = await FaqService.get_page(
        db,
        page_id,
        db_user.language,
        fallback=False,
        include_inactive=True,
    )

    if not page:
        await callback.answer(
            texts.t("ADMIN_FAQ_PAGE_NOT_FOUND", "⚠️ Page not found."),
            show_alert=True,
        )
        return

    await FaqService.delete_page(db, page.id)

    remaining_pages = await FaqService.get_pages(
        db,
        db_user.language,
        include_inactive=True,
        fallback=False,
    )

    if remaining_pages:
        remaining_sorted = sorted(
            remaining_pages,
            key=lambda item: (item.display_order, item.id),
        )
        await FaqService.reorder_pages(db, db_user.language, remaining_sorted)

    await callback.answer(
        texts.t("ADMIN_FAQ_PAGE_DELETED", "🗑️ Page deleted."),
        show_alert=True,
    )

    await show_faq_management(callback, db_user, db)


@admin_required
@error_handler
async def move_faq_page(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)

    parts = (callback.data or "").split(":")
    try:
        page_id = int(parts[1])
        direction = parts[2]
    except (ValueError, IndexError):
        await callback.answer()
        return

    pages = await FaqService.get_pages(
        db,
        db_user.language,
        include_inactive=True,
        fallback=False,
    )

    if not pages:
        await callback.answer()
        return

    pages_sorted = sorted(pages, key=lambda item: (item.display_order, item.id))

    index = next((i for i, page in enumerate(pages_sorted) if page.id == page_id), None)

    if index is None:
        await callback.answer()
        return

    if direction == "up" and index > 0:
        pages_sorted[index - 1], pages_sorted[index] = (
            pages_sorted[index],
            pages_sorted[index - 1],
        )
    elif direction == "down" and index < len(pages_sorted) - 1:
        pages_sorted[index + 1], pages_sorted[index] = (
            pages_sorted[index],
            pages_sorted[index + 1],
        )
    else:
        await callback.answer()
        return

    await FaqService.reorder_pages(db, db_user.language, pages_sorted)

    await callback.answer(
        texts.t("ADMIN_FAQ_PAGE_REORDERED", "✅ Order updated."),
        show_alert=True,
    )
    await show_faq_page_details(callback, db_user, db)


@admin_required
@error_handler
async def show_faq_html_help(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    help_text = get_html_help_text()

    buttons = [[
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_FAQ_BACK_TO_LIST", "⬅️ Back to FAQ settings"),
            callback_data="admin_faq",
        )
    ]]

    await callback.message.edit_text(
        help_text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


def register_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(
        show_faq_management,
        F.data == "admin_faq",
    )
    dp.callback_query.register(
        toggle_faq,
        F.data == "admin_faq_toggle",
    )
    dp.callback_query.register(
        start_create_faq_page,
        F.data == "admin_faq_create",
    )
    dp.callback_query.register(
        cancel_faq_creation,
        F.data == "admin_faq_cancel",
    )
    dp.callback_query.register(
        show_faq_page_details,
        F.data.startswith("admin_faq_page:"),
    )
    dp.callback_query.register(
        start_edit_faq_title,
        F.data.startswith("admin_faq_edit_title:"),
    )
    dp.callback_query.register(
        start_edit_faq_content,
        F.data.startswith("admin_faq_edit_content:"),
    )
    dp.callback_query.register(
        toggle_faq_page,
        F.data.startswith("admin_faq_toggle_page:"),
    )
    dp.callback_query.register(
        delete_faq_page,
        F.data.startswith("admin_faq_delete:"),
    )
    dp.callback_query.register(
        move_faq_page,
        F.data.startswith("admin_faq_move:"),
    )
    dp.callback_query.register(
        show_faq_html_help,
        F.data == "admin_faq_help",
    )

    dp.message.register(
        process_new_faq_title,
        AdminStates.creating_faq_title,
    )
    dp.message.register(
        process_new_faq_content,
        AdminStates.creating_faq_content,
    )
    dp.message.register(
        process_edit_faq_title,
        AdminStates.editing_faq_title,
    )
    dp.message.register(
        process_edit_faq_content,
        AdminStates.editing_faq_content,
    )

