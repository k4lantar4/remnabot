import logging
import math
from datetime import datetime
from typing import Any, Dict, Optional

from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from app.states import (
    RemnaWaveSyncStates,
    SquadRenameStates,
    SquadCreateStates,
    SquadMigrationStates,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.database.crud.server_squad import (
    count_active_users_for_squad,
    get_all_server_squads,
    get_server_squad_by_uuid,
)
from app.keyboards.admin import (
   get_admin_remnawave_keyboard, get_sync_options_keyboard,
   get_node_management_keyboard, get_confirmation_keyboard,
   get_squad_management_keyboard, get_squad_edit_keyboard
)
from app.localization.texts import get_texts
from app.services.remnawave_service import RemnaWaveService, RemnaWaveConfigurationError
from app.services.remnawave_sync_service import (
    RemnaWaveAutoSyncStatus,
    remnawave_sync_service,
)
from app.services.system_settings_service import bot_configuration_service
from app.utils.decorators import admin_required, error_handler
from app.utils.formatters import format_bytes, format_datetime

logger = logging.getLogger(__name__)

squad_inbound_selections = {}
squad_create_data = {}

MIGRATION_PAGE_SIZE = 8


def _format_duration(seconds: float, texts) -> str:
    if seconds < 1:
        return texts.t("ADMIN_RW_DURATION_LT_1S", "less than 1s")

    minutes, sec = divmod(int(seconds), 60)
    if minutes:
        if sec:
            return texts.t("ADMIN_RW_DURATION_MIN_SEC", "{minutes} min {seconds} s").format(minutes=minutes, seconds=sec)
        return texts.t("ADMIN_RW_DURATION_MIN", "{minutes} min").format(minutes=minutes)
    return texts.t("ADMIN_RW_DURATION_SEC", "{seconds} s").format(seconds=sec)


def _format_user_stats(stats: Optional[Dict[str, Any]], texts) -> str:
    if not stats:
        return "—"

    created = stats.get("created", 0)
    updated = stats.get("updated", 0)
    deleted = stats.get("deleted", stats.get("deactivated", 0))
    errors = stats.get("errors", 0)

    return texts.t(
        "ADMIN_RW_USER_STATS",
        "• Created: {created}\n"
        "• Updated: {updated}\n"
        "• Deactivated: {deleted}\n"
        "• Errors: {errors}",
    ).format(created=created, updated=updated, deleted=deleted, errors=errors)


def _format_server_stats(stats: Optional[Dict[str, Any]], texts) -> str:
    if not stats:
        return "—"

    created = stats.get("created", 0)
    updated = stats.get("updated", 0)
    removed = stats.get("removed", 0)
    total = stats.get("total", 0)

    return texts.t(
        "ADMIN_RW_SERVER_STATS",
        "• Created: {created}\n"
        "• Updated: {updated}\n"
        "• Removed: {removed}\n"
        "• Total in panel: {total}",
    ).format(created=created, updated=updated, removed=removed, total=total)


def _build_auto_sync_view(status: RemnaWaveAutoSyncStatus, language: str = "en") -> tuple[str, types.InlineKeyboardMarkup]:
    texts = get_texts(language)
    times_text = ", ".join(t.strftime("%H:%M") for t in status.times) if status.times else "—"
    next_run_text = format_datetime(status.next_run) if status.next_run else "—"

    if status.last_run_finished_at:
        finished_text = format_datetime(status.last_run_finished_at)
        started_text = (
            format_datetime(status.last_run_started_at)
            if status.last_run_started_at
            else "—"
        )
        duration = (
            status.last_run_finished_at - status.last_run_started_at
            if status.last_run_started_at
            else None
        )
        duration_text = f" ({_format_duration(duration.total_seconds(), texts)})" if duration else ""
        reason_map = {
            "manual": texts.t("ADMIN_RW_REASON_MANUAL", "manual"),
            "auto": texts.t("ADMIN_RW_REASON_AUTO", "scheduled"),
            "immediate": texts.t("ADMIN_RW_REASON_IMMEDIATE", "on start"),
        }
        reason_text = reason_map.get(status.last_run_reason or "", "—")
        result_icon = "✅" if status.last_run_success else "❌"
        result_label = texts.t("ADMIN_RW_RESULT_SUCCESS", "success") if status.last_run_success else texts.t("ADMIN_RW_RESULT_ERRORS", "with errors")
        error_block = (
            texts.t("ADMIN_RW_LAST_RUN_ERROR", "\n⚠️ Error: {error}").format(error=status.last_run_error)
            if status.last_run_error
            else ""
        )
        last_run_text = texts.t(
            "ADMIN_RW_LAST_RUN_SUMMARY",
            "{icon} {label}\n"
            "• Started: {started}\n"
            "• Finished: {finished}{duration}\n"
            "• Reason: {reason}{error}"
        ).format(
            icon=result_icon,
            label=result_label,
            started=started_text,
            finished=finished_text,
            duration=duration_text,
            reason=reason_text,
            error=error_block,
        )
    elif status.last_run_started_at:
        last_run_text = (
            texts.t("ADMIN_RW_LAST_RUN_IN_PROGRESS", "⏳ Sync started but not finished yet")
            if status.is_running
            else texts.t("ADMIN_RW_LAST_RUN_INFO", "ℹ️ Last run: {time}").format(time=format_datetime(status.last_run_started_at))
        )
    else:
        last_run_text = "—"

    running_text = texts.t("ADMIN_RW_RUNNING_NOW", "⏳ Running now") if status.is_running else texts.t("ADMIN_RW_WAITING", "Waiting")
    toggle_text = texts.t("ADMIN_RW_DISABLE", "❌ Disable") if status.enabled else texts.t("ADMIN_RW_ENABLE", "✅ Enable")

    text = texts.t(
        "ADMIN_RW_AUTOSYNC_VIEW",
        "🔄 <b>RemnaWave Auto Sync</b>\n\n"
        "⚙️ <b>Status:</b> {status_emoji} {status_label}\n"
        "🕒 <b>Schedule:</b> {schedule}\n"
        "📅 <b>Next run:</b> {next_run}\n"
        "⏱️ <b>State:</b> {state}\n\n"
        "📊 <b>Last run:</b>\n"
        "{last_run}\n\n"
        "👥 <b>Users:</b>\n"
        "{user_stats}\n\n"
        "🌐 <b>Servers:</b>\n"
        "{server_stats}"
    ).format(
        status_emoji="✅" if status.enabled else "❌",
        status_label=texts.t("ADMIN_RW_STATUS_ENABLED", "Enabled") if status.enabled else texts.t("ADMIN_RW_STATUS_DISABLED", "Disabled"),
        schedule=times_text,
        next_run=next_run_text if status.enabled else "—",
        state=running_text,
        last_run=last_run_text,
        user_stats=_format_user_stats(status.last_user_stats, texts),
        server_stats=_format_server_stats(status.last_server_stats, texts),
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_RW_BTN_RUN_NOW", "🔁 Run now"),
                    callback_data="remnawave_auto_sync_run",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=toggle_text,
                    callback_data="remnawave_auto_sync_toggle",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_RW_BTN_EDIT_SCHEDULE", "🕒 Edit schedule"),
                    callback_data="remnawave_auto_sync_times",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.BACK,
                    callback_data="admin_rw_sync",
                )
            ],
        ]
    )

    return text, keyboard


def _format_migration_server_label(texts, server) -> str:
    status = (
        texts.get_text("ADMIN_SQUAD_MIGRATION_STATUS_AVAILABLE", "✅ Available")
        if getattr(server, "is_available", True)
        else texts.get_text("ADMIN_SQUAD_MIGRATION_STATUS_UNAVAILABLE", "🚫 Unavailable")
    )
    return texts.get_text(
        "ADMIN_SQUAD_MIGRATION_SERVER_LABEL",
        "{name} — 👥 {users} ({status})",
    ).format(name=server.display_name, users=server.current_users, status=status)


def _build_migration_keyboard(
    texts,
    squads,
    page: int,
    total_pages: int,
    stage: str,
    *,
    exclude_uuid: str = None,
):
    prefix = "admin_migration_source" if stage == "source" else "admin_migration_target"
    rows = []
    has_items = False

    button_template = texts.get_text(
        "ADMIN_SQUAD_MIGRATION_SQUAD_BUTTON",
        "🌍 {name} — 👥 {users} ({status})",
    )

    for squad in squads:
        if exclude_uuid and squad.squad_uuid == exclude_uuid:
            continue

        has_items = True
        status = (
            texts.get_text("ADMIN_SQUAD_MIGRATION_STATUS_AVAILABLE_SHORT", "✅")
            if getattr(squad, "is_available", True)
            else texts.get_text("ADMIN_SQUAD_MIGRATION_STATUS_UNAVAILABLE_SHORT", "🚫")
        )
        rows.append(
            [
                types.InlineKeyboardButton(
                    text=button_template.format(
                        name=squad.display_name,
                        users=squad.current_users,
                        status=status,
                    ),
                    callback_data=f"{prefix}_{squad.squad_uuid}",
                )
            ]
        )

    if total_pages > 1:
        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                types.InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"{prefix}_page_{page - 1}",
                )
            )
        nav_buttons.append(
            types.InlineKeyboardButton(
                text=texts.get_text(
                    "PAGINATION_PAGE_INFO",
                    "Page {page}/{pages}",
                ).format(page=page, pages=total_pages),
                callback_data="admin_migration_page_info",
            )
        )
        if page < total_pages:
            nav_buttons.append(
                types.InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"{prefix}_page_{page + 1}",
                )
            )
        rows.append(nav_buttons)

    rows.append(
        [
            types.InlineKeyboardButton(
                text=texts.CANCEL,
                callback_data="admin_migration_cancel",
            )
        ]
    )

    return types.InlineKeyboardMarkup(inline_keyboard=rows), has_items


async def _fetch_migration_page(
    db: AsyncSession,
    page: int,
):
    squads, total = await get_all_server_squads(
        db,
        page=max(1, page),
        limit=MIGRATION_PAGE_SIZE,
    )
    total_pages = max(1, math.ceil(total / MIGRATION_PAGE_SIZE))

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
        squads, total = await get_all_server_squads(
            db,
            page=page,
            limit=MIGRATION_PAGE_SIZE,
        )
        total_pages = max(1, math.ceil(total / MIGRATION_PAGE_SIZE))

    return squads, page, total_pages


@admin_required
@error_handler
async def show_squad_migration_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)

    await state.clear()

    squads, page, total_pages = await _fetch_migration_page(db, page=1)
    keyboard, has_items = _build_migration_keyboard(
        texts,
        squads,
        page,
        total_pages,
        "source",
    )

    message = (
        texts.t("ADMIN_SQUAD_MIGRATION_TITLE", "🚚 <b>Squad migration</b>")
        + "\n\n"
        + texts.t(
            "ADMIN_SQUAD_MIGRATION_SELECT_SOURCE",
            "Select a squad to migrate FROM:",
        )
    )

    if not has_items:
        message += (
            "\n\n"
            + texts.t(
                "ADMIN_SQUAD_MIGRATION_NO_OPTIONS",
                "No squads available. Add new ones or cancel.",
            )
        )

    await state.set_state(SquadMigrationStates.selecting_source)

    await callback.message.edit_text(
        message,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()


@admin_required
@error_handler
async def paginate_migration_source(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    if await state.get_state() != SquadMigrationStates.selecting_source:
        await callback.answer()
        return

    try:
        page = int(callback.data.split("_page_")[-1])
    except (ValueError, IndexError):
        await callback.answer()
        return

    squads, page, total_pages = await _fetch_migration_page(db, page=page)
    texts = get_texts(db_user.language)
    keyboard, has_items = _build_migration_keyboard(
        texts,
        squads,
        page,
        total_pages,
        "source",
    )

    message = (
        texts.t("ADMIN_SQUAD_MIGRATION_TITLE", "🚚 <b>Squad migration</b>")
        + "\n\n"
        + texts.t(
            "ADMIN_SQUAD_MIGRATION_SELECT_SOURCE",
            "Select a squad to migrate FROM:",
        )
    )

    if not has_items:
        message += (
            "\n\n"
            + texts.t(
                "ADMIN_SQUAD_MIGRATION_NO_OPTIONS",
                "No squads available. Add new ones or cancel.",
            )
        )

    await callback.message.edit_text(
        message,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()


@admin_required
@error_handler
async def handle_migration_source_selection(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    if await state.get_state() != SquadMigrationStates.selecting_source:
        await callback.answer()
        return

    if "_page_" in callback.data:
        await callback.answer()
        return

    source_uuid = callback.data.replace("admin_migration_source_", "", 1)

    texts = get_texts(db_user.language)
    server = await get_server_squad_by_uuid(db, source_uuid)

    if not server:
        await callback.answer(
            texts.get_text(
                "ADMIN_SQUAD_MIGRATION_SQUAD_NOT_FOUND",
                "Squad not found or unavailable.",
            ),
            show_alert=True,
        )
        return

    await state.update_data(
        source_uuid=server.squad_uuid,
        source_display=_format_migration_server_label(texts, server),
    )

    squads, page, total_pages = await _fetch_migration_page(db, page=1)
    keyboard, has_items = _build_migration_keyboard(
        texts,
        squads,
        page,
        total_pages,
        "target",
        exclude_uuid=server.squad_uuid,
    )

    message = (
        texts.get_text("ADMIN_SQUAD_MIGRATION_TITLE", "🚚 <b>Squad Migration</b>")
        + "\n\n"
        + texts.get_text(
            "ADMIN_SQUAD_MIGRATION_SELECTED_SOURCE",
            "Source: {source}",
        ).format(source=_format_migration_server_label(texts, server))
        + "\n\n"
        + texts.get_text(
            "ADMIN_SQUAD_MIGRATION_SELECT_TARGET",
            "Select a squad to migrate TO:",
        )
    )

    if not has_items:
        message += (
            "\n\n"
            + texts.get_text(
                "ADMIN_SQUAD_MIGRATION_TARGET_EMPTY",
                "No other squads available for migration. Cancel the operation or create new squads.",
            )
        )

    await state.set_state(SquadMigrationStates.selecting_target)

    await callback.message.edit_text(
        message,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()


@admin_required
@error_handler
async def paginate_migration_target(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    if await state.get_state() != SquadMigrationStates.selecting_target:
        await callback.answer()
        return

    try:
        page = int(callback.data.split("_page_")[-1])
    except (ValueError, IndexError):
        await callback.answer()
        return

    data = await state.get_data()
    source_uuid = data.get("source_uuid")
    if not source_uuid:
        await callback.answer()
        return

    texts = get_texts(db_user.language)

    squads, page, total_pages = await _fetch_migration_page(db, page=page)
    keyboard, has_items = _build_migration_keyboard(
        texts,
        squads,
        page,
        total_pages,
        "target",
        exclude_uuid=source_uuid,
    )

    source_display = data.get("source_display") or source_uuid

    message = (
        texts.get_text("ADMIN_SQUAD_MIGRATION_TITLE", "🚚 <b>Squad Migration</b>")
        + "\n\n"
        + texts.get_text(
            "ADMIN_SQUAD_MIGRATION_SELECTED_SOURCE",
            "Source: {source}",
        ).format(source=source_display)
        + "\n\n"
        + texts.get_text(
            "ADMIN_SQUAD_MIGRATION_SELECT_TARGET",
            "Select a squad to migrate TO:",
        )
    )

    if not has_items:
        message += (
            "\n\n"
            + texts.get_text(
                "ADMIN_SQUAD_MIGRATION_TARGET_EMPTY",
                "No other squads available for migration. Cancel the operation or create new squads.",
            )
        )

    await callback.message.edit_text(
        message,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()


@admin_required
@error_handler
async def handle_migration_target_selection(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    current_state = await state.get_state()
    if current_state != SquadMigrationStates.selecting_target:
        await callback.answer()
        return

    if "_page_" in callback.data:
        await callback.answer()
        return

    data = await state.get_data()
    source_uuid = data.get("source_uuid")

    if not source_uuid:
        await callback.answer()
        return

    target_uuid = callback.data.replace("admin_migration_target_", "", 1)

    texts = get_texts(db_user.language)

    if target_uuid == source_uuid:
        await callback.answer(
            texts.get_text(
                "ADMIN_SQUAD_MIGRATION_SAME_SQUAD",
                "Cannot select the same squad.",
            ),
            show_alert=True,
        )
        return

    target_server = await get_server_squad_by_uuid(db, target_uuid)
    if not target_server:
        await callback.answer(
            texts.get_text(
                "ADMIN_SQUAD_MIGRATION_SQUAD_NOT_FOUND",
                "Squad not found or unavailable.",
            ),
            show_alert=True,
        )
        return

    source_display = data.get("source_display") or source_uuid

    users_to_move = await count_active_users_for_squad(db, source_uuid)

    await state.update_data(
        target_uuid=target_server.squad_uuid,
        target_display=_format_migration_server_label(texts, target_server),
        migration_count=users_to_move,
    )

    await state.set_state(SquadMigrationStates.confirming)

    message_lines = [
        texts.get_text("ADMIN_SQUAD_MIGRATION_TITLE", "🚚 <b>Squad Migration</b>"),
        "",
        texts.get_text(
            "ADMIN_SQUAD_MIGRATION_CONFIRM_DETAILS",
            "Review migration parameters:",
        ),
        texts.get_text(
            "ADMIN_SQUAD_MIGRATION_CONFIRM_SOURCE",
            "• From: {source}",
        ).format(source=source_display),
        texts.get_text(
            "ADMIN_SQUAD_MIGRATION_CONFIRM_TARGET",
            "• To: {target}",
        ).format(target=_format_migration_server_label(texts, target_server)),
        texts.get_text(
            "ADMIN_SQUAD_MIGRATION_CONFIRM_COUNT",
            "• Users to migrate: {count}",
        ).format(count=users_to_move),
        "",
        texts.get_text(
            "ADMIN_SQUAD_MIGRATION_CONFIRM_PROMPT",
            "Confirm the operation.",
        ),
    ]

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.get_text(
                        "ADMIN_SQUAD_MIGRATION_CONFIRM_BUTTON",
                        "✅ Confirm",
                    ),
                    callback_data="admin_migration_confirm",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.get_text(
                        "ADMIN_SQUAD_MIGRATION_CHANGE_TARGET",
                        "🔄 Change target server",
                    ),
                    callback_data="admin_migration_change_target",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.CANCEL,
                    callback_data="admin_migration_cancel",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "\n".join(message_lines),
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()


@admin_required
@error_handler
async def change_migration_target(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    data = await state.get_data()
    source_uuid = data.get("source_uuid")

    if not source_uuid:
        await callback.answer()
        return

    await state.set_state(SquadMigrationStates.selecting_target)

    texts = get_texts(db_user.language)
    squads, page, total_pages = await _fetch_migration_page(db, page=1)
    keyboard, has_items = _build_migration_keyboard(
        texts,
        squads,
        page,
        total_pages,
        "target",
        exclude_uuid=source_uuid,
    )

    source_display = data.get("source_display") or source_uuid

    message = (
        texts.get_text("ADMIN_SQUAD_MIGRATION_TITLE", "🚚 <b>Squad Migration</b>")
        + "\n\n"
        + texts.get_text(
            "ADMIN_SQUAD_MIGRATION_SELECTED_SOURCE",
            "Source: {source}",
        ).format(source=source_display)
        + "\n\n"
        + texts.get_text(
            "ADMIN_SQUAD_MIGRATION_SELECT_TARGET",
            "Select a squad to migrate TO:",
        )
    )

    if not has_items:
        message += (
            "\n\n"
            + texts.get_text(
                "ADMIN_SQUAD_MIGRATION_TARGET_EMPTY",
                "No other squads available for migration. Cancel the operation or create new squads.",
            )
        )

    await callback.message.edit_text(
        message,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
    await callback.answer()


@admin_required
@error_handler
async def confirm_squad_migration(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    current_state = await state.get_state()
    if current_state != SquadMigrationStates.confirming:
        await callback.answer()
        return

    data = await state.get_data()
    source_uuid = data.get("source_uuid")
    target_uuid = data.get("target_uuid")

    if not source_uuid or not target_uuid:
        await callback.answer()
        return

    texts = get_texts(db_user.language)
    remnawave_service = RemnaWaveService()

    await callback.answer(texts.get_text("ADMIN_SQUAD_MIGRATION_IN_PROGRESS", "Starting migration..."))

    try:
        result = await remnawave_service.migrate_squad_users(
            db,
            source_uuid=source_uuid,
            target_uuid=target_uuid,
        )
    except RemnaWaveConfigurationError as error:
        message = texts.get_text(
            "ADMIN_SQUAD_MIGRATION_API_ERROR",
            "❌ RemnaWave API not configured: {error}",
        ).format(error=str(error))
        reply_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.get_text(
                            "ADMIN_SQUAD_MIGRATION_BACK_BUTTON",
                            "⬅️ Back to Remnawave",
                        ),
                        callback_data="admin_remnawave",
                    )
                ]
            ]
        )
        await callback.message.edit_text(message, reply_markup=reply_markup)
        await state.clear()
        return

    source_display = data.get("source_display") or source_uuid
    target_display = data.get("target_display") or target_uuid

    if not result.get("success"):
        error_message = result.get("message") or ""
        error_code = result.get("error") or "unexpected"
        message = texts.get_text(
            "ADMIN_SQUAD_MIGRATION_ERROR",
            "❌ Failed to perform migration (code: {code}). {details}",
        ).format(code=error_code, details=error_message)
        reply_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.get_text(
                            "ADMIN_SQUAD_MIGRATION_BACK_BUTTON",
                            "⬅️ Back to Remnawave",
                        ),
                        callback_data="admin_remnawave",
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.get_text(
                            "ADMIN_SQUAD_MIGRATION_NEW_BUTTON",
                            "🔁 New Migration",
                        ),
                        callback_data="admin_rw_migration",
                    )
                ],
            ]
        )
        await callback.message.edit_text(message, reply_markup=reply_markup)
        await state.clear()
        return

    message_lines = [
        texts.get_text("ADMIN_SQUAD_MIGRATION_SUCCESS_TITLE", "✅ Migration completed"),
        "",
        texts.get_text("ADMIN_SQUAD_MIGRATION_CONFIRM_SOURCE", "• From: {source}").format(
            source=source_display
        ),
        texts.get_text("ADMIN_SQUAD_MIGRATION_CONFIRM_TARGET", "• To: {target}").format(
            target=target_display
        ),
        "",
        texts.get_text(
            "ADMIN_SQUAD_MIGRATION_RESULT_TOTAL",
            "Subscriptions found: {count}",
        ).format(count=result.get("total", 0)),
        texts.get_text(
            "ADMIN_SQUAD_MIGRATION_RESULT_UPDATED",
            "Migrated: {count}",
        ).format(count=result.get("updated", 0)),
    ]

    panel_updated = result.get("panel_updated", 0)
    panel_failed = result.get("panel_failed", 0)

    if panel_updated:
        message_lines.append(
            texts.get_text(
                "ADMIN_SQUAD_MIGRATION_RESULT_PANEL_UPDATED",
                "Updated in panel: {count}",
            ).format(count=panel_updated)
        )
    if panel_failed:
        message_lines.append(
            texts.get_text(
                "ADMIN_SQUAD_MIGRATION_RESULT_PANEL_FAILED",
                "Failed to update in panel: {count}",
            ).format(count=panel_failed)
        )

    reply_markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.get_text(
                        "ADMIN_SQUAD_MIGRATION_NEW_BUTTON",
                        "🔁 New Migration",
                    ),
                    callback_data="admin_rw_migration",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=texts.get_text(
                        "ADMIN_SQUAD_MIGRATION_BACK_BUTTON",
                        "⬅️ Back to Remnawave",
                    ),
                    callback_data="admin_remnawave",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "\n".join(message_lines),
        reply_markup=reply_markup,
        disable_web_page_preview=True,
    )
    await state.clear()


@admin_required
@error_handler
async def cancel_squad_migration(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    await state.clear()

    message = texts.get_text(
        "ADMIN_SQUAD_MIGRATION_CANCELLED",
        "❌ Migration cancelled.",
    )

    reply_markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.get_text(
                        "ADMIN_SQUAD_MIGRATION_BACK_BUTTON",
                        "⬅️ Back to Remnawave",
                    ),
                    callback_data="admin_remnawave",
                )
            ]
        ]
    )

    await callback.message.edit_text(message, reply_markup=reply_markup)
    await callback.answer()


@admin_required
@error_handler
async def handle_migration_page_info(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    await callback.answer(
        texts.get_text("ADMIN_SQUAD_MIGRATION_PAGE_HINT", "This is the current page."),
        show_alert=False,
    )

@admin_required
@error_handler
async def show_remnawave_menu(
   callback: types.CallbackQuery,
   db_user: User,
   db: AsyncSession
):
   texts = get_texts(db_user.language)
   remnawave_service = RemnaWaveService()
   connection_test = await remnawave_service.test_api_connection()

   status = connection_test.get("status")
   if status == "connected":
       status_emoji = "✅"
   elif status == "not_configured":
       status_emoji = "ℹ️"
   else:
       status_emoji = "❌"

   api_url_display = settings.REMNAWAVE_API_URL or "—"
   connection_message = connection_test.get("message", texts.get_text("ADMIN_RW_NO_DATA", "No data"))

   text = texts.get_text(
       "ADMIN_RW_MENU_TITLE",
       "🖥️ <b>Remnawave Management</b>\n\n"
       "📡 <b>Connection:</b> {status_emoji} {message}\n"
       "🌐 <b>URL:</b> <code>{url}</code>\n\n"
       "Select an action:"
   ).format(
       status_emoji=status_emoji,
       message=connection_message,
       url=api_url_display
   )
   
   await callback.message.edit_text(
       text,
       reply_markup=get_admin_remnawave_keyboard(db_user.language)
   )
   await callback.answer()


@admin_required
@error_handler
async def show_system_stats(
   callback: types.CallbackQuery,
   db_user: User,
   db: AsyncSession
):
   texts = get_texts(db_user.language)
   from datetime import datetime, timedelta
   
   remnawave_service = RemnaWaveService()
   stats = await remnawave_service.get_system_statistics()
   
   if "error" in stats:
       await callback.message.edit_text(
           texts.t(
               "ADMIN_RW_SYSTEM_STATS_ERROR",
               "❌ Failed to fetch statistics: {error}"
           ).format(error=stats["error"]),
           reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
               [types.InlineKeyboardButton(
                   text=texts.t("ADMIN_RW_BACK", "⬅️ Back"),
                   callback_data="admin_remnawave"
               )]
           ])
       )
       await callback.answer()
       return
   
   system = stats.get("system", {})
   users_by_status = stats.get("users_by_status", {})
   server_info = stats.get("server_info", {})
   bandwidth = stats.get("bandwidth", {})
   traffic_periods = stats.get("traffic_periods", {})
   nodes_realtime = stats.get("nodes_realtime", [])
   nodes_weekly = stats.get("nodes_weekly", [])
   
   memory_total = server_info.get('memory_total', 1)
   memory_used_percent = (server_info.get('memory_used', 0) / memory_total * 100) if memory_total > 0 else 0
   
   uptime_seconds = server_info.get('uptime_seconds', 0)
   uptime_days = int(uptime_seconds // 86400)
   uptime_hours = int((uptime_seconds % 86400) // 3600)
   uptime_str = texts.get_text(
       "ADMIN_RW_UPTIME_FORMAT",
       "{days}d {hours}h"
   ).format(days=uptime_days, hours=uptime_hours)
   
   users_status_text = ""
   for status, count in users_by_status.items():
       status_emoji = {
           'ACTIVE': '✅',
           'DISABLED': '❌', 
           'LIMITED': '⚠️',
           'EXPIRED': '⏰'
       }.get(status, '❓')
       users_status_text += f"  {status_emoji} {status}: {count}\n"
   
   top_nodes_text = ""
   for i, node in enumerate(nodes_weekly[:3], 1):
       top_nodes_text += f"  {i}. {node['name']}: {format_bytes(node['total_bytes'])}\n"
   
   realtime_nodes_text = ""
   for node in nodes_realtime[:3]:
       node_total = node.get('downloadBytes', 0) + node.get('uploadBytes', 0)
       if node_total > 0:
           realtime_nodes_text += f"  📡 {node.get('nodeName', 'Unknown')}: {format_bytes(node_total)}\n"
   
   def format_traffic_change(difference_str):
       if not difference_str or difference_str == '0':
           return ""
       elif difference_str.startswith('-'):
           return f" (🔻 {difference_str[1:]})"
       else:
           return f" (🔺 {difference_str})"
   
   text = texts.t(
       "ADMIN_RW_SYSTEM_STATS_BODY",
       """
📊 <b>Remnawave detailed statistics</b>

🖥️ <b>Server:</b>
- CPU: {cpu_cores} cores ({cpu_physical} physical)
- RAM: {memory_used} / {memory_total} ({memory_percent:.1f}%)
- Free: {memory_available}
- Uptime: {uptime}

👥 <b>Users ({total_users} total):</b>
- 🟢 Online now: {users_online}
- 📅 Last day: {users_last_day}
- 📊 Last week: {users_last_week}
- 💤 Never logged in: {users_never_online}

<b>User statuses:</b>
{users_status_text}

🌐 <b>Nodes ({nodes_online} online):</b>"""
   ).format(
       cpu_cores=server_info.get('cpu_cores', 0),
       cpu_physical=server_info.get('cpu_physical_cores', 0),
       memory_used=format_bytes(server_info.get('memory_used', 0)),
       memory_total=format_bytes(memory_total),
       memory_percent=memory_used_percent,
       memory_available=format_bytes(server_info.get('memory_available', 0)),
       uptime=uptime_str,
       total_users=system.get('total_users', 0),
       users_online=system.get('users_online', 0),
       users_last_day=system.get('users_last_day', 0),
       users_last_week=system.get('users_last_week', 0),
       users_never_online=system.get('users_never_online', 0),
       users_status_text=users_status_text,
       nodes_online=system.get('nodes_online', 0),
   )

   if realtime_nodes_text:
       text += texts.t(
           "ADMIN_RW_SYSTEM_STATS_REALTIME_NODES",
           """
<b>Realtime activity:</b>
{realtime_nodes_text}"""
       ).format(realtime_nodes_text=realtime_nodes_text)
   
   if top_nodes_text:
       text += texts.t(
           "ADMIN_RW_SYSTEM_STATS_TOP_NODES",
           """
<b>Top nodes this week:</b>
{top_nodes_text}"""
       ).format(top_nodes_text=top_nodes_text)
   
   text += texts.t(
       "ADMIN_RW_SYSTEM_STATS_TRAFFIC",
       """

📈 <b>Total user traffic:</b> {total_user_traffic}

📊 <b>Traffic by period:</b>
- 2 days: {last_2_days}{last_2_days_diff}
- 7 days: {last_7_days}{last_7_days_diff}
- 30 days: {last_30_days}{last_30_days_diff}
- Month: {current_month}{current_month_diff}
- Year: {current_year}{current_year_diff}
"""
   ).format(
       total_user_traffic=format_bytes(system.get('total_user_traffic', 0)),
       last_2_days=format_bytes(traffic_periods.get('last_2_days', {}).get('current', 0)),
       last_2_days_diff=format_traffic_change(traffic_periods.get('last_2_days', {}).get('difference', '')),
       last_7_days=format_bytes(traffic_periods.get('last_7_days', {}).get('current', 0)),
       last_7_days_diff=format_traffic_change(traffic_periods.get('last_7_days', {}).get('difference', '')),
       last_30_days=format_bytes(traffic_periods.get('last_30_days', {}).get('current', 0)),
       last_30_days_diff=format_traffic_change(traffic_periods.get('last_30_days', {}).get('difference', '')),
       current_month=format_bytes(traffic_periods.get('current_month', {}).get('current', 0)),
       current_month_diff=format_traffic_change(traffic_periods.get('current_month', {}).get('difference', '')),
       current_year=format_bytes(traffic_periods.get('current_year', {}).get('current', 0)),
       current_year_diff=format_traffic_change(traffic_periods.get('current_year', {}).get('difference', '')),
   )

   if bandwidth.get('realtime_total', 0) > 0:
       text += texts.t(
           "ADMIN_RW_SYSTEM_STATS_REALTIME_TRAFFIC",
           """
⚡ <b>Realtime traffic:</b>
- Download: {realtime_download}
- Upload: {realtime_upload}
- Total: {realtime_total}
"""
       ).format(
           realtime_download=format_bytes(bandwidth.get('realtime_download', 0)),
           realtime_upload=format_bytes(bandwidth.get('realtime_upload', 0)),
           realtime_total=format_bytes(bandwidth.get('realtime_total', 0)),
       )
   
   text += texts.t(
       "ADMIN_RW_SYSTEM_STATS_UPDATED_AT",
       """
🕒 <b>Updated:</b> {last_updated}
"""
   ).format(last_updated=format_datetime(stats.get('last_updated', datetime.now())))
   
   keyboard = [
       [types.InlineKeyboardButton(text=texts.t("ADMIN_RW_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_rw_system")],
       [types.InlineKeyboardButton(text=texts.t("ADMIN_RW_BTN_NODES", "📈 Nodes"), callback_data="admin_rw_nodes"),
        types.InlineKeyboardButton(text=texts.t("ADMIN_RW_BTN_SYNC", "👥 Sync"), callback_data="admin_rw_sync")],
       [types.InlineKeyboardButton(text=texts.t("ADMIN_RW_BACK", "⬅️ Back"), callback_data="admin_remnawave")]
   ]
   
   await callback.message.edit_text(
       text,
       reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
   )
   await callback.answer()

@admin_required
@error_handler
async def show_traffic_stats(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    from datetime import datetime, timedelta
    
    remnawave_service = RemnaWaveService()
    
    try:
        async with remnawave_service.get_api_client() as api:
            bandwidth_stats = await api.get_bandwidth_stats()
            
            realtime_usage = await api.get_nodes_realtime_usage()
            
            nodes_stats = await api.get_nodes_statistics()
            
    except Exception as e:
        await callback.message.edit_text(
            texts.t(
                "ADMIN_RW_TRAFFIC_STATS_ERROR",
                "❌ Failed to fetch traffic statistics: {error}"
            ).format(error=str(e)),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(
                    text=texts.t("ADMIN_RW_BACK", "⬅️ Back"),
                    callback_data="admin_remnawave"
                )]
            ])
        )
        await callback.answer()
        return
    
    def parse_bandwidth(bandwidth_str):
        return remnawave_service._parse_bandwidth_string(bandwidth_str)
    
    total_realtime_download = sum(node.get('downloadBytes', 0) for node in realtime_usage)
    total_realtime_upload = sum(node.get('uploadBytes', 0) for node in realtime_usage)
    total_realtime = total_realtime_download + total_realtime_upload
    
    total_download_speed = sum(node.get('downloadSpeedBps', 0) for node in realtime_usage)
    total_upload_speed = sum(node.get('uploadSpeedBps', 0) for node in realtime_usage)
    
    periods = {
        'last_2_days': bandwidth_stats.get('bandwidthLastTwoDays', {}),
        'last_7_days': bandwidth_stats.get('bandwidthLastSevenDays', {}),
        'last_30_days': bandwidth_stats.get('bandwidthLast30Days', {}),
        'current_month': bandwidth_stats.get('bandwidthCalendarMonth', {}),
        'current_year': bandwidth_stats.get('bandwidthCurrentYear', {})
    }
    
    def format_change(diff_str):
        if not diff_str or diff_str == '0':
            return ""
        elif diff_str.startswith('-'):
            return f" 🔻 {diff_str[1:]}"
        else:
            return f" 🔺 {diff_str}"
    
    text = texts.get_text(
        "ADMIN_RW_TRAFFIC_STATS_TITLE",
        "📊 <b>Remnawave Traffic Statistics</b>\n\n"
        "⚡ <b>Realtime data:</b>\n"
        "- Download: {download}\n"
        "- Upload: {upload}\n"
        "- Total traffic: {total}\n\n"
        "🚀 <b>Current speeds:</b>\n"
        "- Download speed: {download_speed}/s\n"
        "- Upload speed: {upload_speed}/s\n"
        "- Total speed: {total_speed}/s\n\n"
        "📈 <b>Statistics by period:</b>\n\n"
        "<b>Last 2 days:</b>\n"
        "- Current: {last_2_days_current}\n"
        "- Previous: {last_2_days_previous}\n"
        "- Change:{last_2_days_change}\n\n"
        "<b>Last 7 days:</b>\n"
        "- Current: {last_7_days_current}\n"
        "- Previous: {last_7_days_previous}\n"
        "- Change:{last_7_days_change}\n\n"
        "<b>Last 30 days:</b>\n"
        "- Current: {last_30_days_current}\n"
        "- Previous: {last_30_days_previous}\n"
        "- Change:{last_30_days_change}\n\n"
        "<b>Current month:</b>\n"
        "- Current: {current_month_current}\n"
        "- Previous: {current_month_previous}\n"
        "- Change:{current_month_change}\n\n"
        "<b>Current year:</b>\n"
        "- Current: {current_year_current}\n"
        "- Previous: {current_year_previous}\n"
        "- Change:{current_year_change}"
    ).format(
        download=format_bytes(total_realtime_download),
        upload=format_bytes(total_realtime_upload),
        total=format_bytes(total_realtime),
        download_speed=format_bytes(total_download_speed),
        upload_speed=format_bytes(total_upload_speed),
        total_speed=format_bytes(total_download_speed + total_upload_speed),
        last_2_days_current=format_bytes(parse_bandwidth(periods['last_2_days'].get('current', '0'))),
        last_2_days_previous=format_bytes(parse_bandwidth(periods['last_2_days'].get('previous', '0'))),
        last_2_days_change=format_change(periods['last_2_days'].get('difference', '')),
        last_7_days_current=format_bytes(parse_bandwidth(periods['last_7_days'].get('current', '0'))),
        last_7_days_previous=format_bytes(parse_bandwidth(periods['last_7_days'].get('previous', '0'))),
        last_7_days_change=format_change(periods['last_7_days'].get('difference', '')),
        last_30_days_current=format_bytes(parse_bandwidth(periods['last_30_days'].get('current', '0'))),
        last_30_days_previous=format_bytes(parse_bandwidth(periods['last_30_days'].get('previous', '0'))),
        last_30_days_change=format_change(periods['last_30_days'].get('difference', '')),
        current_month_current=format_bytes(parse_bandwidth(periods['current_month'].get('current', '0'))),
        current_month_previous=format_bytes(parse_bandwidth(periods['current_month'].get('previous', '0'))),
        current_month_change=format_change(periods['current_month'].get('difference', '')),
        current_year_current=format_bytes(parse_bandwidth(periods['current_year'].get('current', '0'))),
        current_year_previous=format_bytes(parse_bandwidth(periods['current_year'].get('previous', '0'))),
        current_year_change=format_change(periods['current_year'].get('difference', ''))
    )
    
    if realtime_usage:
        nodes_realtime_text = texts.get_text("ADMIN_RW_TRAFFIC_NODES_REALTIME_HEADER", "\n🌐 <b>Traffic by nodes (realtime):</b>\n")
        for node in sorted(realtime_usage, key=lambda x: x.get('totalBytes', 0), reverse=True):
            node_total = node.get('totalBytes', 0)
            if node_total > 0:
                nodes_realtime_text += f"- {node.get('nodeName', 'Unknown')}: {format_bytes(node_total)}\n"
        text += nodes_realtime_text
    
    if nodes_stats.get('lastSevenDays'):
        text += texts.get_text("ADMIN_RW_TRAFFIC_TOP_NODES_HEADER", "\n📊 <b>Top nodes for 7 days:</b>\n")
        
        nodes_weekly = {}
        for day_data in nodes_stats['lastSevenDays']:
            node_name = day_data['nodeName']
            if node_name not in nodes_weekly:
                nodes_weekly[node_name] = 0
            nodes_weekly[node_name] += int(day_data['totalBytes'])
        
        sorted_nodes = sorted(nodes_weekly.items(), key=lambda x: x[1], reverse=True)
        for i, (node_name, total_bytes) in enumerate(sorted_nodes[:5], 1):
            text += f"{i}. {node_name}: {format_bytes(total_bytes)}\n"
    
    text += texts.get_text(
        "ADMIN_RW_TRAFFIC_UPDATED",
        "\n🕒 <b>Updated:</b> {updated_at}"
    ).format(updated_at=format_datetime(datetime.now()))
    
    keyboard = [
        [types.InlineKeyboardButton(text=texts.get_text("ADMIN_RW_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_rw_traffic")],
        [types.InlineKeyboardButton(text=texts.get_text("ADMIN_RW_BTN_NODES", "📈 Nodes"), callback_data="admin_rw_nodes"),
         types.InlineKeyboardButton(text=texts.get_text("ADMIN_RW_BTN_SYSTEM", "📊 System"), callback_data="admin_rw_system")],
        [types.InlineKeyboardButton(text=texts.get_text("ADMIN_RW_BACK", "⬅️ Back"), callback_data="admin_remnawave")]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_nodes_management(
   callback: types.CallbackQuery,
   db_user: User,
   db: AsyncSession
):
   texts = get_texts(db_user.language)
   remnawave_service = RemnaWaveService()
   nodes = await remnawave_service.get_all_nodes()
   
   if not nodes:
       await callback.message.edit_text(
           texts.t(
               "ADMIN_RW_NODES_NOT_FOUND",
               "🖥️ Nodes not found or connection error"
           ),
           reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
               [types.InlineKeyboardButton(
                   text=texts.t("ADMIN_RW_BACK", "⬅️ Back"),
                   callback_data="admin_remnawave"
               )]
           ])
       )
       await callback.answer()
       return
   
   text = texts.t("ADMIN_RW_NODES_TITLE", "🖥️ <b>Node management</b>\n\n")
   keyboard = []
   
   for node in nodes:
       status_emoji = "🟢" if node["is_node_online"] else "🔴"
       connection_emoji = "📡" if node["is_connected"] else "📵"
       
       text += texts.t(
           "ADMIN_RW_NODES_ROW",
           "{status} {connection} <b>{name}</b>\n"
           "🌍 {country} • {address}\n"
           "👥 Online: {online}\n\n"
       ).format(
           status=status_emoji,
           connection=connection_emoji,
           name=node['name'],
           country=node['country_code'],
           address=node['address'],
           online=node['users_online'] or 0,
       )
       
       keyboard.append([
           types.InlineKeyboardButton(
               text=f"⚙️ {node['name']}",
               callback_data=f"admin_node_manage_{node['uuid']}"
           )
       ])
   
   keyboard.extend([
       [types.InlineKeyboardButton(text=texts.t("ADMIN_RW_NODES_RESTART_ALL", "🔄 Restart all"), callback_data="admin_restart_all_nodes")],
       [types.InlineKeyboardButton(text=texts.t("ADMIN_RW_BACK", "⬅️ Back"), callback_data="admin_remnawave")]
   ])
   
   await callback.message.edit_text(
       text,
       reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
   )
   await callback.answer()


@admin_required
@error_handler
async def show_node_details(
   callback: types.CallbackQuery,
   db_user: User,
   db: AsyncSession
):
   texts = get_texts(db_user.language)
   node_uuid = callback.data.split('_')[-1]
   
   remnawave_service = RemnaWaveService()
   node = await remnawave_service.get_node_details(node_uuid)
   
   if not node:
       await callback.answer(
           texts.get_text("ADMIN_RW_NODE_NOT_FOUND", "❌ Node not found"),
           show_alert=True
       )
       return
   
   status_emoji = "🟢" if node["is_node_online"] else "🔴"
   xray_emoji = "✅" if node["is_xray_running"] else "❌"
   
   online_text = texts.get_text("ADMIN_RW_YES", "Yes") if node['is_node_online'] else texts.get_text("ADMIN_RW_NO", "No")
   xray_text = texts.get_text("ADMIN_RW_XRAY_RUNNING", "Running") if node['is_xray_running'] else texts.get_text("ADMIN_RW_XRAY_STOPPED", "Stopped")
   connected_text = texts.get_text("ADMIN_RW_YES", "Yes") if node['is_connected'] else texts.get_text("ADMIN_RW_NO", "No")
   connected_emoji = "📡" if node['is_connected'] else "📵"
   disabled_text = texts.get_text("ADMIN_RW_YES", "Yes") if node['is_disabled'] else texts.get_text("ADMIN_RW_NO", "No")
   disabled_emoji = "❌" if node['is_disabled'] else "✅"
   traffic_limit = format_bytes(node['traffic_limit_bytes']) if node['traffic_limit_bytes'] else texts.get_text("ADMIN_RW_NO_LIMIT", "No limit")
   
   text = texts.get_text(
       "ADMIN_RW_NODE_DETAILS",
       "🖥️ <b>Node: {name}</b>\n\n"
       "<b>Status:</b>\n"
       "- Online: {status_emoji} {online}\n"
       "- Xray: {xray_emoji} {xray}\n"
       "- Connected: {connected_emoji} {connected}\n"
       "- Disabled: {disabled_emoji} {disabled}\n\n"
       "<b>Information:</b>\n"
       "- Address: {address}\n"
       "- Country: {country}\n"
       "- Users online: {users_online}\n\n"
       "<b>Traffic:</b>\n"
       "- Used: {traffic_used}\n"
       "- Limit: {traffic_limit}"
   ).format(
       name=node['name'],
       status_emoji=status_emoji,
       online=online_text,
       xray_emoji=xray_emoji,
       xray=xray_text,
       connected_emoji=connected_emoji,
       connected=connected_text,
       disabled_emoji=disabled_emoji,
       disabled=disabled_text,
       address=node['address'],
       country=node['country_code'],
       users_online=node['users_online'],
       traffic_used=format_bytes(node['traffic_used_bytes']),
       traffic_limit=traffic_limit
   )
   
   await callback.message.edit_text(
       text,
       reply_markup=get_node_management_keyboard(node_uuid, db_user.language)
   )
   await callback.answer()


@admin_required
@error_handler
async def manage_node(
   callback: types.CallbackQuery,
   db_user: User,
   db: AsyncSession
):
   texts = get_texts(db_user.language)
   action, node_uuid = callback.data.split('_')[1], callback.data.split('_')[-1]
   
   remnawave_service = RemnaWaveService()
   success = await remnawave_service.manage_node(node_uuid, action)
   
   if success:
       action_texts = {
           "enable": texts.get_text("ADMIN_RW_NODE_ENABLED", "enabled"),
           "disable": texts.get_text("ADMIN_RW_NODE_DISABLED", "disabled"),
           "restart": texts.get_text("ADMIN_RW_NODE_RESTARTED", "restarted")
       }
       await callback.answer(
           texts.get_text(
               "ADMIN_RW_NODE_ACTION_SUCCESS",
               "✅ Node {action}"
           ).format(action=action_texts.get(action, texts.get_text("ADMIN_RW_NODE_PROCESSED", "processed")))
       )
   else:
       await callback.answer(
           texts.get_text("ADMIN_RW_NODE_ACTION_ERROR", "❌ Error performing action"),
           show_alert=True
       )
   
   await show_node_details(
       types.CallbackQuery(
           id=callback.id,
           from_user=callback.from_user,
           chat_instance=callback.chat_instance,
           data=f"admin_node_manage_{node_uuid}",
           message=callback.message
       ),
       db_user,
       db
   )

@admin_required
@error_handler
async def show_node_statistics(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    node_uuid = callback.data.split('_')[-1]
    
    remnawave_service = RemnaWaveService()
    
    node = await remnawave_service.get_node_details(node_uuid)
    
    if not node:
        await callback.answer(
            texts.get_text("ADMIN_RW_NODE_NOT_FOUND", "❌ Node not found"),
            show_alert=True
        )
        return
    
    try:
        from datetime import datetime, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        node_usage = await remnawave_service.get_node_user_usage_by_range(
            node_uuid, start_date, end_date
        )
        
        realtime_stats = await remnawave_service.get_nodes_realtime_usage()
        
        node_realtime = None
        for stats in realtime_stats:
            if stats.get('nodeUuid') == node_uuid:
                node_realtime = stats
                break
        
        status_emoji = "🟢" if node["is_node_online"] else "🔴"
        xray_emoji = "✅" if node["is_xray_running"] else "❌"
        online_text = texts.get_text("ADMIN_RW_YES", "Yes") if node['is_node_online'] else texts.get_text("ADMIN_RW_NO", "No")
        xray_text = texts.get_text("ADMIN_RW_XRAY_RUNNING", "Running") if node['is_xray_running'] else texts.get_text("ADMIN_RW_XRAY_STOPPED", "Stopped")
        traffic_limit = format_bytes(node['traffic_limit_bytes']) if node['traffic_limit_bytes'] else texts.get_text("ADMIN_RW_NO_LIMIT", "No limit")
        
        text = texts.get_text(
            "ADMIN_RW_NODE_STATS_TITLE",
            "📊 <b>Node statistics: {name}</b>\n\n"
            "<b>Status:</b>\n"
            "- Online: {status_emoji} {online}\n"
            "- Xray: {xray_emoji} {xray}\n"
            "- Users online: {users_online}\n\n"
            "<b>Traffic:</b>\n"
            "- Used: {traffic_used}\n"
            "- Limit: {traffic_limit}"
        ).format(
            name=node['name'],
            status_emoji=status_emoji,
            online=online_text,
            xray_emoji=xray_emoji,
            xray=xray_text,
            users_online=node['users_online'] or 0,
            traffic_used=format_bytes(node['traffic_used_bytes'] or 0),
            traffic_limit=traffic_limit
        )

        if node_realtime:
            text += texts.get_text(
                "ADMIN_RW_NODE_STATS_REALTIME",
                "\n<b>Realtime statistics:</b>\n"
                "- Downloaded: {download}\n"
                "- Uploaded: {upload}\n"
                "- Total traffic: {total}\n"
                "- Download speed: {download_speed}/s\n"
                "- Upload speed: {upload_speed}/s"
            ).format(
                download=format_bytes(node_realtime.get('downloadBytes', 0)),
                upload=format_bytes(node_realtime.get('uploadBytes', 0)),
                total=format_bytes(node_realtime.get('totalBytes', 0)),
                download_speed=format_bytes(node_realtime.get('downloadSpeedBps', 0)),
                upload_speed=format_bytes(node_realtime.get('uploadSpeedBps', 0))
            )

        if node_usage:
            text += texts.get_text("ADMIN_RW_NODE_STATS_7DAYS_HEADER", "\n<b>Statistics for 7 days:</b>\n")
            total_usage = 0
            for usage in node_usage[-5:]: 
                daily_usage = usage.get('total', 0)
                total_usage += daily_usage
                text += f"- {usage.get('date', 'N/A')}: {format_bytes(daily_usage)}\n"
            
            text += texts.get_text(
                "ADMIN_RW_NODE_STATS_7DAYS_TOTAL",
                "\n<b>Total traffic for 7 days:</b> {total}"
            ).format(total=format_bytes(total_usage))
        else:
            text += texts.get_text(
                "ADMIN_RW_NODE_STATS_7DAYS_UNAVAILABLE",
                "\n<b>Statistics for 7 days:</b> Data unavailable"
            )
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.get_text("ADMIN_RW_BTN_REFRESH", "🔄 Refresh"), callback_data=f"node_stats_{node_uuid}")],
            [types.InlineKeyboardButton(text=texts.get_text("ADMIN_RW_BACK", "⬅️ Back"), callback_data=f"admin_node_manage_{node_uuid}")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Failed to fetch node statistics {node_uuid}: {e}")
        
        status_emoji = "🟢" if node["is_node_online"] else "🔴"
        xray_emoji = "✅" if node["is_xray_running"] else "❌"
        online_text = texts.get_text("ADMIN_RW_YES", "Yes") if node['is_node_online'] else texts.get_text("ADMIN_RW_NO", "No")
        xray_text = texts.get_text("ADMIN_RW_XRAY_RUNNING", "Running") if node['is_xray_running'] else texts.get_text("ADMIN_RW_XRAY_STOPPED", "Stopped")
        traffic_limit = format_bytes(node['traffic_limit_bytes']) if node['traffic_limit_bytes'] else texts.get_text("ADMIN_RW_NO_LIMIT", "No limit")
        
        text = texts.get_text(
            "ADMIN_RW_NODE_STATS_TITLE",
            "📊 <b>Node statistics: {name}</b>\n\n"
            "<b>Status:</b>\n"
            "- Online: {status_emoji} {online}\n"
            "- Xray: {xray_emoji} {xray}\n"
            "- Users online: {users_online}\n\n"
            "<b>Traffic:</b>\n"
            "- Used: {traffic_used}\n"
            "- Limit: {traffic_limit}\n\n"
            "⚠️ <b>Detailed statistics temporarily unavailable</b>\n"
            "Possible reasons:\n"
            "• API connection issues\n"
            "• Node recently added\n"
            "• Insufficient data to display\n\n"
            "<b>Updated:</b> {updated_at}"
        ).format(
            name=node['name'],
            status_emoji=status_emoji,
            online=online_text,
            xray_emoji=xray_emoji,
            xray=xray_text,
            users_online=node['users_online'] or 0,
            traffic_used=format_bytes(node['traffic_used_bytes'] or 0),
            traffic_limit=traffic_limit,
            updated_at=format_datetime(datetime.now())
        )
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.get_text("ADMIN_RW_BTN_TRY_AGAIN", "🔄 Try again"), callback_data=f"node_stats_{node_uuid}")],
            [types.InlineKeyboardButton(text=texts.get_text("ADMIN_RW_BACK", "⬅️ Back"), callback_data=f"admin_node_manage_{node_uuid}")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.answer()

@admin_required
@error_handler
async def show_squad_details(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    squad_uuid = callback.data.split('_')[-1]
    
    texts = get_texts(db_user.language)
    remnawave_service = RemnaWaveService()
    squad = await remnawave_service.get_squad_details(squad_uuid)
    
    if not squad:
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_NOT_FOUND", "❌ Squad not found"),
            show_alert=True
        )
        return
    
    text = texts.get_text(
        "ADMIN_SQUAD_DETAILS_HEADER",
        "🌐 <b>Squad: {name}</b>"
    ).format(name=squad['name'])
    
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_DETAILS_INFO", "<b>Information:</b>")
    text += "\n" + texts.get_text("ADMIN_SQUAD_DETAILS_UUID", "- UUID: <code>{uuid}</code>").format(uuid=squad['uuid'])
    text += "\n" + texts.get_text("ADMIN_SQUAD_DETAILS_MEMBERS", "- Members: {count}").format(count=squad['members_count'])
    text += "\n" + texts.get_text("ADMIN_SQUAD_DETAILS_INBOUNDS_COUNT", "- Inbounds: {count}").format(count=squad['inbounds_count'])
    
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_DETAILS_INBOUNDS", "<b>Inbounds:</b>")
    
    if squad.get('inbounds'):
        for inbound in squad['inbounds']:
            text += f"\n- {inbound['tag']} ({inbound['type']})"
    else:
        text += "\n" + texts.get_text("ADMIN_SQUAD_NO_ACTIVE_INBOUNDS", "No active inbounds")
    
    await callback.message.edit_text(
        text,
        reply_markup=get_squad_management_keyboard(squad_uuid, db_user.language)
    )
    await callback.answer()


@admin_required
@error_handler
async def manage_squad_action(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    parts = callback.data.split('_')
    action = parts[1] 
    squad_uuid = parts[-1]
    
    remnawave_service = RemnaWaveService()
    
    if action == "add_users":
        success = await remnawave_service.add_all_users_to_squad(squad_uuid)
        if success:
            await callback.answer(
                texts.get_text("ADMIN_SQUAD_ADD_USERS_QUEUED", "✅ Task to add users queued")
            )
        else:
            await callback.answer(
                texts.get_text("ADMIN_SQUAD_ADD_USERS_ERROR", "❌ Error adding users"),
                show_alert=True
            )
            
    elif action == "remove_users":
        success = await remnawave_service.remove_all_users_from_squad(squad_uuid)
        if success:
            await callback.answer(
                texts.get_text("ADMIN_SQUAD_REMOVE_USERS_QUEUED", "✅ Task to remove users queued")
            )
        else:
            await callback.answer(
                texts.get_text("ADMIN_SQUAD_REMOVE_USERS_ERROR", "❌ Error removing users"),
                show_alert=True
            )
            
    elif action == "delete":
        success = await remnawave_service.delete_squad(squad_uuid)
        if success:
            await callback.message.edit_text(
                texts.get_text("ADMIN_SQUAD_DELETED_SUCCESS", "✅ Squad successfully deleted"),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(
                        text=texts.get_text("ADMIN_SQUAD_BACK_TO_SQUADS", "⬅️ Back to Squads"),
                        callback_data="admin_rw_squads"
                    )]
                ])
            )
        else:
            await callback.answer(
                texts.get_text("ADMIN_SQUAD_DELETE_ERROR", "❌ Error deleting squad"),
                show_alert=True
            )
        return
    
    await show_squad_details(
        types.CallbackQuery(
            id=callback.id,
            from_user=callback.from_user,
            chat_instance=callback.chat_instance,
            data=f"admin_squad_manage_{squad_uuid}",
            message=callback.message
        ),
        db_user,
        db
    )

@admin_required
@error_handler
async def show_squad_edit_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    squad_uuid = callback.data.split('_')[-1]
    
    remnawave_service = RemnaWaveService()
    squad = await remnawave_service.get_squad_details(squad_uuid)
    
    if not squad:
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_NOT_FOUND", "❌ Squad not found"),
            show_alert=True
        )
        return
    
    text = texts.get_text(
        "ADMIN_SQUAD_EDIT_HEADER",
        "✏️ <b>Editing squad: {name}</b>"
    ).format(name=squad['name'])
    
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_EDIT_CURRENT_INBOUNDS", "<b>Current inbounds:</b>")
    
    if squad.get('inbounds'):
        for inbound in squad['inbounds']:
            text += f"\n✅ {inbound['tag']} ({inbound['type']})"
    else:
        text += "\n" + texts.get_text("ADMIN_SQUAD_NO_ACTIVE_INBOUNDS", "No active inbounds")
    
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_EDIT_AVAILABLE_ACTIONS", "<b>Available actions:</b>")
    
    await callback.message.edit_text(
        text,
        reply_markup=get_squad_edit_keyboard(squad_uuid, db_user.language)
    )
    await callback.answer()

@admin_required
@error_handler
async def show_squad_inbounds_selection(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    squad_uuid = callback.data.split('_')[-1]
    
    remnawave_service = RemnaWaveService()
    
    squad = await remnawave_service.get_squad_details(squad_uuid)
    all_inbounds = await remnawave_service.get_all_inbounds()
    
    if not squad:
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_NOT_FOUND", "❌ Squad not found"),
            show_alert=True
        )
        return
    
    if not all_inbounds:
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_NO_AVAILABLE_INBOUNDS", "❌ No available inbounds"),
            show_alert=True
        )
        return
    
    if squad_uuid not in squad_inbound_selections:
        squad_inbound_selections[squad_uuid] = set(
            inbound['uuid'] for inbound in squad.get('inbounds', [])
        )
    
    text = texts.get_text("ADMIN_SQUAD_CHANGE_INBOUNDS_HEADER", "🔧 <b>Changing inbounds</b>")
    
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CHANGE_INBOUNDS_SQUAD", "<b>Squad:</b> {name}").format(name=squad['name'])
    text += "\n" + texts.get_text("ADMIN_SQUAD_CHANGE_INBOUNDS_CURRENT", "<b>Current inbounds:</b> {count}").format(count=len(squad_inbound_selections[squad_uuid]))
    
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CHANGE_INBOUNDS_AVAILABLE", "<b>Available inbounds:</b>")
    
    keyboard = []
    
    for i, inbound in enumerate(all_inbounds[:15]): 
        is_selected = inbound['uuid'] in squad_inbound_selections[squad_uuid]
        emoji = "✅" if is_selected else "☐"
        
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"{emoji} {inbound['tag']} ({inbound['type']})",
                callback_data=f"sqd_tgl_{i}_{squad_uuid[:8]}"
            )
        ])
    
    if len(all_inbounds) > 15:
        text += "\n" + texts.get_text(
            "ADMIN_SQUAD_CHANGE_INBOUNDS_SHOWN",
            "⚠️ Showing first 15 of {total} inbounds"
        ).format(total=len(all_inbounds))
    
    keyboard.extend([
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_SQUAD_SAVE_CHANGES", "💾 Save changes"),
            callback_data=f"sqd_save_{squad_uuid[:8]}"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_SQUAD_BACK", "⬅️ Back"),
            callback_data=f"sqd_edit_{squad_uuid[:8]}"
        )]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@admin_required
@error_handler
async def show_squad_rename_form(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    squad_uuid = callback.data.split('_')[-1]
    
    remnawave_service = RemnaWaveService()
    squad = await remnawave_service.get_squad_details(squad_uuid)
    
    if not squad:
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_NOT_FOUND", "❌ Squad not found"),
            show_alert=True
        )
        return
    
    await state.update_data(squad_uuid=squad_uuid, squad_name=squad['name'])
    await state.set_state(SquadRenameStates.waiting_for_new_name)
    
    text = texts.get_text("ADMIN_SQUAD_RENAME_HEADER", "✏️ <b>Renaming squad</b>")
    
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_RENAME_CURRENT", "<b>Current name:</b> {name}").format(name=squad['name'])
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_RENAME_PROMPT", "📝 <b>Enter new squad name:</b>")
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_RENAME_REQUIREMENTS", "<i>Name requirements:</i>")
    text += "\n" + texts.get_text("ADMIN_SQUAD_RENAME_REQ_LENGTH", "• 2 to 20 characters")
    text += "\n" + texts.get_text("ADMIN_SQUAD_RENAME_REQ_CHARS", "• Only letters, numbers, hyphens and underscores")
    text += "\n" + texts.get_text("ADMIN_SQUAD_RENAME_REQ_NO_SPACES", "• No spaces or special characters")
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_RENAME_INSTRUCTIONS", "Send a message with the new name or press 'Cancel' to exit.")
    
    keyboard = [
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_SQUAD_CANCEL", "❌ Cancel"),
            callback_data=f"cancel_rename_{squad_uuid}"
        )]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@admin_required
@error_handler
async def cancel_squad_rename(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    squad_uuid = callback.data.split('_')[-1]
    
    await state.clear()
    
    new_callback = types.CallbackQuery(
        id=callback.id,
        from_user=callback.from_user,
        chat_instance=callback.chat_instance,
        data=f"squad_edit_{squad_uuid}",
        message=callback.message
    )
    
    await show_squad_edit_menu(new_callback, db_user, db)

@admin_required
@error_handler
async def process_squad_new_name(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    squad_uuid = data.get('squad_uuid')
    old_name = data.get('squad_name')
    
    if not squad_uuid:
        await message.answer(
            texts.get_text("ADMIN_SQUAD_RENAME_ERROR_NOT_FOUND", "❌ Error: squad not found")
        )
        await state.clear()
        return
    
    new_name = message.text.strip()
    
    if not new_name:
        await message.answer(
            texts.get_text("ADMIN_SQUAD_RENAME_ERROR_EMPTY", "❌ Name cannot be empty. Try again:")
        )
        return
    
    if len(new_name) < 2 or len(new_name) > 20:
        await message.answer(
            texts.get_text("ADMIN_SQUAD_RENAME_ERROR_LENGTH", "❌ Name must be 2 to 20 characters. Try again:")
        )
        return
    
    import re
    if not re.match(r'^[A-Za-z0-9_-]+$', new_name):
        await message.answer(
            texts.get_text("ADMIN_SQUAD_RENAME_ERROR_INVALID_CHARS", "❌ Name can only contain letters, numbers, hyphens and underscores. Try again:")
        )
        return
    
    if new_name == old_name:
        await message.answer(
            texts.get_text("ADMIN_SQUAD_RENAME_ERROR_SAME", "❌ New name is the same as current. Enter a different name:")
        )
        return
    
    remnawave_service = RemnaWaveService()
    success = await remnawave_service.rename_squad(squad_uuid, new_name)
    
    if success:
        await message.answer(
            texts.get_text(
                "ADMIN_SQUAD_RENAME_SUCCESS",
                "✅ <b>Squad successfully renamed!</b>\n\n"
                "<b>Old name:</b> {old_name}\n"
                "<b>New name:</b> {new_name}"
            ).format(old_name=old_name, new_name=new_name),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(
                    text=texts.get_text("ADMIN_SQUAD_DETAILS", "📋 Squad Details"),
                    callback_data=f"admin_squad_manage_{squad_uuid}"
                )],
                [types.InlineKeyboardButton(
                    text=texts.get_text("ADMIN_SQUAD_BACK_TO_SQUADS", "⬅️ Back to Squads"),
                    callback_data="admin_rw_squads"
                )]
            ])
        )
        await state.clear()
    else:
        await message.answer(
            texts.get_text(
                "ADMIN_SQUAD_RENAME_ERROR_FAILED",
                "❌ <b>Squad rename error</b>\n\n"
                "Possible reasons:\n"
                "• Squad with this name already exists\n"
                "• API connection issues\n"
                "• Insufficient permissions\n\n"
                "Try a different name:"
            ),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(
                    text=texts.get_text("ADMIN_SQUAD_CANCEL", "❌ Cancel"),
                    callback_data=f"cancel_rename_{squad_uuid}"
                )]
            ])
        )


@admin_required
@error_handler
async def toggle_squad_inbound(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    parts = callback.data.split('_')
    inbound_index = int(parts[2])
    short_squad_uuid = parts[3]
    
    remnawave_service = RemnaWaveService()
    squads = await remnawave_service.get_all_squads()
    
    full_squad_uuid = None
    for squad in squads:
        if squad['uuid'].startswith(short_squad_uuid):
            full_squad_uuid = squad['uuid']
            break
    
    texts = get_texts(db_user.language)
    
    if not full_squad_uuid:
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_NOT_FOUND", "❌ Squad not found"),
            show_alert=True
        )
        return
    
    all_inbounds = await remnawave_service.get_all_inbounds()
    if inbound_index >= len(all_inbounds):
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_INBOUND_NOT_FOUND", "❌ Inbound not found"),
            show_alert=True
        )
        return
    
    selected_inbound = all_inbounds[inbound_index]
    
    if full_squad_uuid not in squad_inbound_selections:
        squad_inbound_selections[full_squad_uuid] = set()
    
    if selected_inbound['uuid'] in squad_inbound_selections[full_squad_uuid]:
        squad_inbound_selections[full_squad_uuid].remove(selected_inbound['uuid'])
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_INBOUND_REMOVED", "➖ Removed: {tag}").format(tag=selected_inbound['tag'])
        )
    else:
        squad_inbound_selections[full_squad_uuid].add(selected_inbound['uuid'])
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_INBOUND_ADDED", "➕ Added: {tag}").format(tag=selected_inbound['tag'])
        )
    
    text = texts.get_text("ADMIN_SQUAD_CHANGE_INBOUNDS_HEADER", "🔧 <b>Changing inbounds</b>")
    
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CHANGE_INBOUNDS_SQUAD", "<b>Squad:</b> {name}").format(
        name=squads[0]['name'] if squads else texts.get_text("ADMIN_SQUAD_UNKNOWN", "Unknown")
    )
    text += "\n" + texts.get_text("ADMIN_SQUAD_CHANGE_INBOUNDS_SELECTED", "<b>Selected inbounds:</b> {count}").format(
        count=len(squad_inbound_selections[full_squad_uuid])
    )
    
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CHANGE_INBOUNDS_AVAILABLE", "<b>Available inbounds:</b>")
    
    keyboard = []
    for i, inbound in enumerate(all_inbounds[:15]):
        is_selected = inbound['uuid'] in squad_inbound_selections[full_squad_uuid]
        emoji = "✅" if is_selected else "☐"
        
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"{emoji} {inbound['tag']} ({inbound['type']})",
                callback_data=f"sqd_tgl_{i}_{short_squad_uuid}"
            )
        ])
    
    keyboard.extend([
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_SQUAD_SAVE_CHANGES", "💾 Save changes"),
            callback_data=f"sqd_save_{short_squad_uuid}"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_SQUAD_BACK", "⬅️ Back"),
            callback_data=f"sqd_edit_{short_squad_uuid}"
        )]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


@admin_required  
@error_handler
async def save_squad_inbounds(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    short_squad_uuid = callback.data.split('_')[-1]
    
    remnawave_service = RemnaWaveService()
    squads = await remnawave_service.get_all_squads()
    
    full_squad_uuid = None
    squad_name = None
    for squad in squads:
        if squad['uuid'].startswith(short_squad_uuid):
            full_squad_uuid = squad['uuid']
            squad_name = squad['name']
            break
    
    texts = get_texts(db_user.language)
    
    if not full_squad_uuid:
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_NOT_FOUND", "❌ Squad not found"),
            show_alert=True
        )
        return
    
    selected_inbounds = squad_inbound_selections.get(full_squad_uuid, set())
    
    try:
        success = await remnawave_service.update_squad_inbounds(full_squad_uuid, list(selected_inbounds))
        
        if success:
            if full_squad_uuid in squad_inbound_selections:
                del squad_inbound_selections[full_squad_uuid]
            
            await callback.message.edit_text(
                texts.get_text(
                    "ADMIN_SQUAD_INBOUNDS_UPDATED",
                    "✅ <b>Squad inbounds updated</b>\n\n"
                    "<b>Squad:</b> {name}\n"
                    "<b>Number of inbounds:</b> {count}"
                ).format(name=squad_name, count=len(selected_inbounds)),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(
                        text=texts.get_text("ADMIN_SQUAD_BACK_TO_SQUADS", "⬅️ Back to Squads"),
                        callback_data="admin_rw_squads"
                    )],
                    [types.InlineKeyboardButton(
                        text=texts.get_text("ADMIN_SQUAD_DETAILS", "📋 Squad Details"),
                        callback_data=f"admin_squad_manage_{full_squad_uuid}"
                    )]
                ])
            )
            await callback.answer(
                texts.get_text("ADMIN_SQUAD_CHANGES_SAVED", "✅ Changes saved!")
            )
        else:
            await callback.answer(
                texts.get_text("ADMIN_SQUAD_SAVE_ERROR", "❌ Error saving changes"),
                show_alert=True
            )
            
    except Exception as e:
        logger.error(f"Error saving squad inbounds: {e}")
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_SAVE_ERROR_GENERIC", "❌ Error while saving"),
            show_alert=True
        )

@admin_required
@error_handler
async def show_squad_edit_menu_short(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    short_squad_uuid = callback.data.split('_')[-1]
    
    remnawave_service = RemnaWaveService()
    squads = await remnawave_service.get_all_squads()
    
    full_squad_uuid = None
    for squad in squads:
        if squad['uuid'].startswith(short_squad_uuid):
            full_squad_uuid = squad['uuid']
            break
    
    texts = get_texts(db_user.language)
    
    if not full_squad_uuid:
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_NOT_FOUND", "❌ Squad not found"),
            show_alert=True
        )
        return
    
    new_callback = types.CallbackQuery(
        id=callback.id,
        from_user=callback.from_user,
        chat_instance=callback.chat_instance,
        data=f"squad_edit_{full_squad_uuid}",
        message=callback.message
    )
    
    await show_squad_edit_menu(new_callback, db_user, db)

@admin_required
@error_handler
async def start_squad_creation(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    await state.set_state(SquadCreateStates.waiting_for_name)
    
    text = texts.get_text("ADMIN_SQUAD_CREATE_HEADER", "➕ <b>Creating new squad</b>")
    
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CREATE_STEP_1", "<b>Step 1 of 2: Squad name</b>")
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CREATE_NAME_PROMPT", "📝 <b>Enter name for new squad:</b>")
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CREATE_NAME_REQUIREMENTS", "<i>Name requirements:</i>")
    text += "\n" + texts.get_text("ADMIN_SQUAD_RENAME_REQ_LENGTH", "• 2 to 20 characters")
    text += "\n" + texts.get_text("ADMIN_SQUAD_RENAME_REQ_CHARS", "• Only letters, numbers, hyphens and underscores")
    text += "\n" + texts.get_text("ADMIN_SQUAD_RENAME_REQ_NO_SPACES", "• No spaces or special characters")
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CREATE_NAME_INSTRUCTIONS", "Send a message with the name or press 'Cancel' to exit.")
    
    keyboard = [
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_SQUAD_CANCEL", "❌ Cancel"),
            callback_data="cancel_squad_create"
        )]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def process_squad_name(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    squad_name = message.text.strip()
    
    if not squad_name:
        await message.answer(
            texts.get_text("ADMIN_SQUAD_CREATE_ERROR_EMPTY", "❌ Name cannot be empty. Try again:")
        )
        return
    
    if len(squad_name) < 2 or len(squad_name) > 20:
        await message.answer(
            texts.get_text("ADMIN_SQUAD_CREATE_ERROR_LENGTH", "❌ Name must be 2 to 20 characters. Try again:")
        )
        return
    
    import re
    if not re.match(r'^[A-Za-z0-9_-]+$', squad_name):
        await message.answer(
            texts.get_text("ADMIN_SQUAD_CREATE_ERROR_INVALID_CHARS", "❌ Name can only contain letters, numbers, hyphens and underscores. Try again:")
        )
        return
    
    await state.update_data(squad_name=squad_name)
    await state.set_state(SquadCreateStates.selecting_inbounds)
    
    user_id = message.from_user.id
    squad_create_data[user_id] = {'name': squad_name, 'selected_inbounds': set()}
    
    remnawave_service = RemnaWaveService()
    all_inbounds = await remnawave_service.get_all_inbounds()
    
    if not all_inbounds:
        await message.answer(
            texts.get_text(
                "ADMIN_SQUAD_CREATE_NO_INBOUNDS",
                "❌ <b>No available inbounds</b>\n\n"
                "At least one inbound is required to create a squad."
            ),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(
                    text=texts.get_text("ADMIN_SQUAD_BACK_TO_SQUADS", "⬅️ Back to Squads"),
                    callback_data="admin_rw_squads"
                )]
            ])
        )
        await state.clear()
        return
    
    text = texts.get_text(
        "ADMIN_SQUAD_CREATE_SELECT_INBOUNDS_HEADER",
        "➕ <b>Creating squad: {name}</b>"
    ).format(name=squad_name)
    
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CREATE_STEP_2", "<b>Step 2 of 2: Select inbounds</b>")
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CREATE_SELECTED_COUNT", "<b>Selected inbounds:</b> 0")
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CHANGE_INBOUNDS_AVAILABLE", "<b>Available inbounds:</b>")
    
    keyboard = []
    
    for i, inbound in enumerate(all_inbounds[:15]): 
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"☐ {inbound['tag']} ({inbound['type']})",
                callback_data=f"create_tgl_{i}"
            )
        ])
    
    if len(all_inbounds) > 15:
        text += "\n" + texts.get_text(
            "ADMIN_SQUAD_CHANGE_INBOUNDS_SHOWN",
            "⚠️ Showing first 15 of {total} inbounds"
        ).format(total=len(all_inbounds))
    
    keyboard.extend([
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_SQUAD_CREATE_BUTTON", "✅ Create Squad"),
            callback_data="create_squad_finish"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_SQUAD_CANCEL", "❌ Cancel"),
            callback_data="cancel_squad_create"
        )]
    ])
    
    await message.answer(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@admin_required
@error_handler
async def toggle_create_inbound(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    inbound_index = int(callback.data.split('_')[-1])
    user_id = callback.from_user.id
    
    if user_id not in squad_create_data:
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_CREATE_ERROR_SESSION", "❌ Error: session data not found"),
            show_alert=True
        )
        await state.clear()
        return
    
    remnawave_service = RemnaWaveService()
    all_inbounds = await remnawave_service.get_all_inbounds()
    
    if inbound_index >= len(all_inbounds):
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_INBOUND_NOT_FOUND", "❌ Inbound not found"),
            show_alert=True
        )
        return
    
    selected_inbound = all_inbounds[inbound_index]
    selected_inbounds = squad_create_data[user_id]['selected_inbounds']
    
    if selected_inbound['uuid'] in selected_inbounds:
        selected_inbounds.remove(selected_inbound['uuid'])
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_INBOUND_REMOVED", "➖ Removed: {tag}").format(tag=selected_inbound['tag'])
        )
    else:
        selected_inbounds.add(selected_inbound['uuid'])
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_INBOUND_ADDED", "➕ Added: {tag}").format(tag=selected_inbound['tag'])
        )
    
    squad_name = squad_create_data[user_id]['name']
    
    text = texts.get_text(
        "ADMIN_SQUAD_CREATE_SELECT_INBOUNDS_HEADER",
        "➕ <b>Creating squad: {name}</b>"
    ).format(name=squad_name)
    
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CREATE_STEP_2", "<b>Step 2 of 2: Select inbounds</b>")
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CREATE_SELECTED_COUNT", "<b>Selected inbounds:</b> {count}").format(
        count=len(selected_inbounds)
    )
    text += "\n\n" + texts.get_text("ADMIN_SQUAD_CHANGE_INBOUNDS_AVAILABLE", "<b>Available inbounds:</b>")
    
    keyboard = []
    
    for i, inbound in enumerate(all_inbounds[:15]):
        is_selected = inbound['uuid'] in selected_inbounds
        emoji = "✅" if is_selected else "☐"
        
        keyboard.append([
            types.InlineKeyboardButton(
                text=f"{emoji} {inbound['tag']} ({inbound['type']})",
                callback_data=f"create_tgl_{i}"
            )
        ])
    
    keyboard.extend([
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_SQUAD_CREATE_BUTTON", "✅ Create Squad"),
            callback_data="create_squad_finish"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_SQUAD_CANCEL", "❌ Cancel"),
            callback_data="cancel_squad_create"
        )]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )

@admin_required
@error_handler
async def finish_squad_creation(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    texts = get_texts(db_user.language)
    user_id = callback.from_user.id
    
    if user_id not in squad_create_data:
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_CREATE_ERROR_SESSION", "❌ Error: session data not found"),
            show_alert=True
        )
        await state.clear()
        return
    
    squad_name = squad_create_data[user_id]['name']
    selected_inbounds = list(squad_create_data[user_id]['selected_inbounds'])
    
    if not selected_inbounds:
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_CREATE_ERROR_NO_INBOUNDS", "❌ At least one inbound must be selected"),
            show_alert=True
        )
        return
    
    remnawave_service = RemnaWaveService()
    success = await remnawave_service.create_squad(squad_name, selected_inbounds)
    
    if user_id in squad_create_data:
        del squad_create_data[user_id]
    await state.clear()
    
    if success:
        await callback.message.edit_text(
            texts.get_text(
                "ADMIN_SQUAD_CREATE_SUCCESS",
                "✅ <b>Squad successfully created!</b>\n\n"
                "<b>Name:</b> {name}\n"
                "<b>Number of inbounds:</b> {count}\n\n"
                "Squad is ready to use!"
            ).format(name=squad_name, count=len(selected_inbounds)),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(
                    text=texts.get_text("ADMIN_SQUAD_LIST", "📋 Squad List"),
                    callback_data="admin_rw_squads"
                )],
                [types.InlineKeyboardButton(
                    text=texts.get_text("ADMIN_SQUAD_BACK_TO_REMNAWAVE", "⬅️ Back to Remnawave Panel"),
                    callback_data="admin_remnawave"
                )]
            ])
        )
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_CREATED", "✅ Squad created!")
        )
    else:
        await callback.message.edit_text(
            texts.get_text(
                "ADMIN_SQUAD_CREATE_ERROR_FAILED",
                "❌ <b>Squad creation error</b>\n\n"
                "<b>Name:</b> {name}\n\n"
                "Possible reasons:\n"
                "• Squad with this name already exists\n"
                "• API connection issues\n"
                "• Insufficient permissions\n"
                "• Invalid inbounds"
            ).format(name=squad_name),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(
                    text=texts.get_text("ADMIN_SQUAD_TRY_AGAIN", "🔄 Try Again"),
                    callback_data="admin_squad_create"
                )],
                [types.InlineKeyboardButton(
                    text=texts.get_text("ADMIN_SQUAD_BACK_TO_SQUADS", "⬅️ Back to Squads"),
                    callback_data="admin_rw_squads"
                )]
            ])
        )
        await callback.answer(
            texts.get_text("ADMIN_SQUAD_CREATE_ERROR_FAILED_SHORT", "❌ Squad creation error"),
            show_alert=True
        )

@admin_required
@error_handler
async def cancel_squad_creation(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext
):
    user_id = callback.from_user.id
    
    if user_id in squad_create_data:
        del squad_create_data[user_id]
    await state.clear()
    
    await show_squads_management(callback, db_user, db)


@admin_required
@error_handler
async def restart_all_nodes(
   callback: types.CallbackQuery,
   db_user: User,
   db: AsyncSession
):
   texts = get_texts(db_user.language)
   remnawave_service = RemnaWaveService()
   success = await remnawave_service.restart_all_nodes()
   
   if success:
       await callback.message.edit_text(
           texts.get_text(
               "ADMIN_RW_NODES_RESTART_SUCCESS",
               "✅ Command to restart all nodes has been sent",
           ),
           reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
               [types.InlineKeyboardButton(
                   text=texts.get_text("ADMIN_RW_BACK_TO_NODES", "⬅️ Back to nodes"),
                   callback_data="admin_rw_nodes"
               )]
           ])
       )
   else:
       await callback.message.edit_text(
           texts.get_text(
               "ADMIN_RW_NODES_RESTART_ERROR",
               "❌ Error restarting nodes",
           ),
           reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
               [types.InlineKeyboardButton(
                   text=texts.get_text("ADMIN_RW_BACK_TO_NODES", "⬅️ Back to nodes"),
                   callback_data="admin_rw_nodes"
               )]
           ])
       )
   
   await callback.answer()


@admin_required
@error_handler
async def show_sync_options(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    status = remnawave_sync_service.get_status()
    times_text = ", ".join(t.strftime("%H:%M") for t in status.times) if status.times else "—"
    next_run_text = format_datetime(status.next_run) if status.next_run else "—"
    last_result = "—"

    if status.last_run_finished_at:
        result_icon = "✅" if status.last_run_success else "❌"
        result_label = texts.t("ADMIN_RW_SYNC_RESULT_SUCCESS", "success") if status.last_run_success else texts.t("ADMIN_RW_SYNC_RESULT_WITH_ERRORS", "with errors")
        finished_text = format_datetime(status.last_run_finished_at)
        last_result = f"{result_icon} {result_label} ({finished_text})"
    elif status.last_run_started_at:
        last_result = texts.t(
            "ADMIN_RW_SYNC_RESULT_STARTED",
            "⏳ Started at {started_at}"
        ).format(started_at=format_datetime(status.last_run_started_at))

    status_lines = [
        texts.t(
            "ADMIN_RW_SYNC_STATUS_LINE",
            "⚙️ Status: {status}"
        ).format(status=texts.t("ADMIN_RW_STATUS_ENABLED", "✅ Enabled") if status.enabled else texts.t("ADMIN_RW_STATUS_DISABLED", "❌ Disabled")),
        texts.t(
            "ADMIN_RW_SYNC_SCHEDULE_LINE",
            "🕒 Schedule: {schedule}"
        ).format(schedule=times_text),
        texts.t(
            "ADMIN_RW_SYNC_NEXT_RUN_LINE",
            "📅 Next run: {next_run}"
        ).format(next_run=next_run_text if status.enabled else "—"),
        texts.t(
            "ADMIN_RW_SYNC_LAST_RUN_LINE",
            "📊 Last run: {last_result}"
        ).format(last_result=last_result),
    ]

    text = texts.t(
        "ADMIN_RW_SYNC_OVERVIEW",
        "🔄 <b>Remnawave sync</b>\n\n"
        "🔄 <b>Full sync does:</b>\n"
        "• Create new users from panel into bot\n"
        "• Update existing users\n"
        "• Deactivate subscriptions of users missing in panel\n"
        "• Preserve user balances\n"
        "• ⏱️ Expected time: 2-5 minutes\n\n"
        "⚠️ <b>Important:</b>\n"
        "• Avoid other operations while sync is running\n"
        "• Full sync deactivates subscriptions for users missing in panel\n"
        "• Recommended daily full sync\n"
        "• User balances are NOT removed\n\n"
        "⬆️ <b>Reverse sync:</b>\n"
        "• Sends active bot users to the panel\n"
        "• Use for panel issues or data recovery\n\n"
        "{status_lines}"
    ).format(status_lines="\n".join(status_lines))

    keyboard = [
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_RW_SYNC_RUN_FULL", "🔄 Start full sync"),
                callback_data="sync_all_users",
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_RW_SYNC_TO_PANEL", "⬆️ Sync to panel"),
                callback_data="sync_to_panel",
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_RW_SYNC_AUTOSYNC_SETTINGS", "⚙️ Auto-sync settings"),
                callback_data="admin_rw_auto_sync",
            )
        ],
        [types.InlineKeyboardButton(text=texts.t("ADMIN_RW_BACK", "⬅️ Back"), callback_data="admin_remnawave")],
    ]

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
    )
    await callback.answer()


@admin_required
@error_handler
async def show_auto_sync_settings(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    await state.clear()
    status = remnawave_sync_service.get_status()
    text, keyboard = _build_auto_sync_view(status, db_user.language)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@admin_required
@error_handler
async def toggle_auto_sync_setting(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    await state.clear()
    new_value = not bool(settings.REMNAWAVE_AUTO_SYNC_ENABLED)
    await bot_configuration_service.set_value(
        db,
        "REMNAWAVE_AUTO_SYNC_ENABLED",
        new_value,
    )
    await db.commit()

    status = remnawave_sync_service.get_status()
    text, keyboard = _build_auto_sync_view(status, db_user.language)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer(
        texts.t(
            "ADMIN_RW_AUTOSYNC_TOGGLED",
            "Auto-sync {status}"
        ).format(
            status=texts.t("ADMIN_RW_STATUS_ENABLED", "enabled") if new_value else texts.t("ADMIN_RW_STATUS_DISABLED", "disabled")
        )
    )


@admin_required
@error_handler
async def prompt_auto_sync_schedule(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    status = remnawave_sync_service.get_status()
    current_schedule = ", ".join(t.strftime("%H:%M") for t in status.times) if status.times else "—"

    instructions = texts.get_text(
        "ADMIN_RW_SYNC_SCHEDULE_SETUP",
        "🕒 <b>Auto-sync schedule setup</b>\n\n"
        "Specify launch times separated by commas or on new lines in HH:MM format.\n"
        "Current schedule: <code>{current_schedule}</code>\n\n"
        "Examples: <code>03:00, 15:30</code> or <code>00:15\n06:00\n18:45</code>\n\n"
        "Send <b>cancel</b> to return without changes."
    ).format(current_schedule=current_schedule)

    await state.set_state(RemnaWaveSyncStates.waiting_for_schedule)
    await state.update_data(
        auto_sync_message_id=callback.message.message_id,
        auto_sync_message_chat_id=callback.message.chat.id,
    )

    await callback.message.edit_text(
        instructions,
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.get_text("ADMIN_RW_CANCEL", "❌ Cancel"),
                        callback_data="remnawave_auto_sync_cancel",
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def cancel_auto_sync_schedule(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    await state.clear()
    status = remnawave_sync_service.get_status()
    text, keyboard = _build_auto_sync_view(status, db_user.language)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer(texts.t("ADMIN_RW_SCHEDULE_CANCELLED", "Schedule edit cancelled"))


@admin_required
@error_handler
async def run_auto_sync_now(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    if remnawave_sync_service.get_status().is_running:
        await callback.answer(texts.t("ADMIN_RW_SYNC_ALREADY_RUNNING_SHORT", "Sync is already running"), show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        texts.t("ADMIN_RW_SYNC_STARTING", "🔄 Starting auto-sync...\n\nPlease wait, this may take a few minutes."),
        parse_mode="HTML",
    )
    await callback.answer(texts.t("ADMIN_RW_SYNC_STARTED", "Auto-sync started"))

    result = await remnawave_sync_service.run_sync_now(reason="manual")
    status = remnawave_sync_service.get_status()
    base_text, keyboard = _build_auto_sync_view(status, db_user.language)

    if not result.get("started"):
        await callback.message.edit_text(
            texts.t("ADMIN_RW_SYNC_ALREADY_RUNNING", "⚠️ <b>Sync is already running</b>\n\n") + base_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return

    if result.get("success"):
        user_stats = result.get("user_stats") or {}
        server_stats = result.get("server_stats") or {}
        summary = texts.get_text(
            "ADMIN_RW_SYNC_COMPLETED_SUMMARY",
            "✅ <b>Synchronization completed</b>\n"
            "👥 Users: created {created}, updated {updated}, "
            "deactivated {deactivated}, errors {errors}\n"
            "🌐 Servers: created {srv_created}, updated {srv_updated}, removed {srv_removed}\n\n"
        ).format(
            created=user_stats.get('created', 0),
            updated=user_stats.get('updated', 0),
            deactivated=user_stats.get('deleted', user_stats.get('deactivated', 0)),
            errors=user_stats.get('errors', 0),
            srv_created=server_stats.get('created', 0),
            srv_updated=server_stats.get('updated', 0),
            srv_removed=server_stats.get('removed', 0)
        )
        final_text = summary + base_text
        await callback.message.edit_text(
            final_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    else:
        error_text = result.get("error") or texts.get_text("ADMIN_RW_SYNC_UNKNOWN_ERROR", "Unknown error")
        summary = texts.get_text(
            "ADMIN_RW_SYNC_COMPLETED_WITH_ERROR",
            "❌ <b>Synchronization completed with error</b>\n"
            "Reason: {error_text}\n\n"
        ).format(error_text=error_text)
        await callback.message.edit_text(
            summary + base_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )


@admin_required
@error_handler
async def save_auto_sync_schedule(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    text = (message.text or "").strip()
    data = await state.get_data()

    cancel_text = texts.CANCEL.lower()
    if text.lower() in {cancel_text, "cancel", "отмена"}:
        await state.clear()
        status = remnawave_sync_service.get_status()
        view_text, keyboard = _build_auto_sync_view(status, db_user.language)
        message_id = data.get("auto_sync_message_id")
        chat_id = data.get("auto_sync_message_chat_id", message.chat.id)
        if message_id:
            await message.bot.edit_message_text(
                view_text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        else:
            await message.answer(
                view_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        await message.answer(texts.get_text("ADMIN_RW_SYNC_SCHEDULE_CANCELLED_MSG", "Schedule setup cancelled"))
        return

    parsed_times = settings.parse_daily_time_list(text)

    if not parsed_times:
        await message.answer(
            texts.get_text(
                "ADMIN_RW_SYNC_SCHEDULE_PARSE_ERROR",
                "❌ Failed to parse time. Use HH:MM format, e.g. 03:00 or 18:45."
            ),
        )
        return

    normalized_value = ", ".join(t.strftime("%H:%M") for t in parsed_times)
    await bot_configuration_service.set_value(
        db,
        "REMNAWAVE_AUTO_SYNC_TIMES",
        normalized_value,
    )
    await db.commit()

    status = remnawave_sync_service.get_status()
    view_text, keyboard = _build_auto_sync_view(status, db_user.language)
    message_id = data.get("auto_sync_message_id")
    chat_id = data.get("auto_sync_message_chat_id", message.chat.id)

    if message_id:
        await message.bot.edit_message_text(
            view_text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    else:
        await message.answer(
            view_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    await state.clear()
    await message.answer(texts.get_text("ADMIN_RW_SYNC_SCHEDULE_UPDATED", "✅ Auto-sync schedule updated"))


@admin_required
@error_handler
async def sync_all_users(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    
    progress_text = texts.get_text(
        "ADMIN_RW_SYNC_FULL_PROGRESS",
        "🔄 <b>Performing full synchronization...</b>\n\n"
        "📋 Steps:\n"
        "• Loading ALL users from Remnawave panel\n"
        "• Creating new users in bot\n"
        "• Updating existing users\n"
        "• Deactivating subscriptions of missing users\n"
        "• Preserving balances\n\n"
        "⏳ Please wait..."
    )
    
    await callback.message.edit_text(progress_text, reply_markup=None)
    
    remnawave_service = RemnaWaveService()
    stats = await remnawave_service.sync_users_from_panel(db, "all")
    
    total_operations = stats['created'] + stats['updated'] + stats.get('deleted', 0)
    
    if stats['errors'] == 0:
        status_emoji = "✅"
        status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_SUCCESS", "successfully completed")
    elif stats['errors'] < total_operations:
        status_emoji = "⚠️"
        status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_WARNINGS", "completed with warnings")
    else:
        status_emoji = "❌"
        status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_ERRORS", "completed with errors")
    
    text = texts.get_text(
        "ADMIN_RW_SYNC_FULL_RESULT",
        "{status_emoji} <b>Full synchronization {status_text}</b>\n\n"
        "📊 <b>Result:</b>\n"
        "• 🆕 Created: {created}\n"
        "• 🔄 Updated: {updated}\n"
        "• 🗑️ Deactivated: {deactivated}\n"
        "• ❌ Errors: {errors}"
    ).format(
        status_emoji=status_emoji,
        status_text=status_text,
        created=stats['created'],
        updated=stats['updated'],
        deactivated=stats.get('deleted', 0),
        errors=stats['errors']
    )
    
    if stats.get('deleted', 0) > 0:
        text += "\n\n" + texts.get_text(
            "ADMIN_RW_SYNC_DEACTIVATED_SUBS",
            "🗑️ <b>Deactivated subscriptions:</b>\n"
            "Subscriptions of users who are\n"
            "missing in Remnawave panel have been deactivated.\n"
            "💰 User balances preserved."
        )
    
    if stats['errors'] > 0:
        text += "\n\n" + texts.get_text(
            "ADMIN_RW_SYNC_ERRORS_WARNING",
            "⚠️ <b>Attention:</b>\n"
            "Some operations completed with errors.\n"
            "Check logs for detailed information."
        )
    
    text += "\n\n" + texts.get_text(
        "ADMIN_RW_SYNC_FULL_RECOMMENDATIONS",
        "💡 <b>Recommendations:</b>\n"
        "• Full synchronization completed\n"
        "• Recommended to run once per day\n"
        "• All users from panel synchronized"
    )
    
    keyboard = []
    
    if stats['errors'] > 0:
        keyboard.append([
            types.InlineKeyboardButton(
                text=texts.get_text("ADMIN_RW_SYNC_RETRY", "🔄 Retry synchronization"), 
                callback_data="sync_all_users"
            )
        ])
    
    keyboard.extend([
        [
            types.InlineKeyboardButton(
                text=texts.get_text("ADMIN_RW_SYSTEM_STATS", "📊 System statistics"), 
                callback_data="admin_rw_system"
            ),
            types.InlineKeyboardButton(
                text=texts.get_text("ADMIN_RW_NODES", "🌐 Nodes"), 
                callback_data="admin_rw_nodes"
            )
        ],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_BACK", "⬅️ Back"), 
            callback_data="admin_remnawave"
        )]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def sync_users_to_panel(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.get_text(
            "ADMIN_RW_SYNC_TO_PANEL_PROGRESS",
            "⬆️ Syncing bot data to Remnawave panel...\n\n"
            "This may take a few minutes."
        ),
        reply_markup=None,
    )

    remnawave_service = RemnaWaveService()
    stats = await remnawave_service.sync_users_to_panel(db)

    if stats["errors"] == 0:
        status_emoji = "✅"
        status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_SUCCESS", "successfully completed")
    else:
        status_emoji = "⚠️" if (stats["created"] + stats["updated"]) > 0 else "❌"
        status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_WARNINGS", "completed with warnings") if status_emoji == "⚠️" else texts.get_text("ADMIN_RW_SYNC_STATUS_ERRORS", "completed with errors")

    text = texts.get_text(
        "ADMIN_RW_SYNC_TO_PANEL_RESULT",
        "{status_emoji} <b>Sync to panel {status_text}</b>\n\n"
        "📊 <b>Results:</b>\n"
        "• 🆕 Created: {created}\n"
        "• 🔄 Updated: {updated}\n"
        "• ❌ Errors: {errors}"
    ).format(
        status_emoji=status_emoji,
        status_text=status_text,
        created=stats['created'],
        updated=stats['updated'],
        errors=stats['errors']
    )

    keyboard = [
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_RETRY", "🔄 Retry"), 
            callback_data="sync_to_panel"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_FULL", "🔄 Full synchronization"), 
            callback_data="sync_all_users"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_BACK", "⬅️ Back to sync"), 
            callback_data="admin_rw_sync"
        )],
    ]

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
    )
    await callback.answer()

@admin_required
@error_handler
async def show_sync_recommendations(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    
    await callback.message.edit_text(
        texts.get_text("ADMIN_RW_SYNC_ANALYZING", "🔍 Analyzing synchronization state..."),
        reply_markup=None
    )
    
    remnawave_service = RemnaWaveService()
    recommendations = await remnawave_service.get_sync_recommendations(db)
    
    priority_emoji = {
        "low": "🟢",
        "medium": "🟡", 
        "high": "🔴"
    }
    
    sync_type_text = ""
    if recommendations['sync_type'] == 'all':
        sync_type_text = texts.get_text("ADMIN_RW_SYNC_TYPE_FULL", "🔄 Full synchronization")
    elif recommendations['sync_type'] == 'update_only':
        sync_type_text = texts.get_text("ADMIN_RW_SYNC_TYPE_UPDATE", "📈 Data update")
    elif recommendations['sync_type'] == 'new_only':
        sync_type_text = texts.get_text("ADMIN_RW_SYNC_TYPE_NEW", "🆕 New users sync")
    else:
        sync_type_text = texts.get_text("ADMIN_RW_SYNC_TYPE_NONE", "✅ Synchronization not required")
    
    reasons_text = "\n".join([f"• {reason}" for reason in recommendations['reasons']])
    
    text = texts.get_text(
        "ADMIN_RW_SYNC_RECOMMENDATIONS",
        "💡 <b>Synchronization recommendations</b>\n\n"
        "{priority_emoji} <b>Priority:</b> {priority}\n"
        "⏱️ <b>Estimated time:</b> {estimated_time}\n\n"
        "<b>Recommended action:</b>\n"
        "{sync_type_text}\n\n"
        "<b>Reasons:</b>\n"
        "{reasons_text}"
    ).format(
        priority_emoji=priority_emoji.get(recommendations['priority'], '🟢'),
        priority=recommendations['priority'].upper(),
        estimated_time=recommendations['estimated_time'],
        sync_type_text=sync_type_text,
        reasons_text=reasons_text
    )
    
    keyboard = []
    
    if recommendations['should_sync'] and recommendations['sync_type'] != 'none':
        keyboard.append([
            types.InlineKeyboardButton(
                text=texts.get_text("ADMIN_RW_SYNC_EXECUTE_RECOMMENDATION", "✅ Execute recommendation"), 
                callback_data=f"sync_{recommendations['sync_type']}_users" if recommendations['sync_type'] != 'update_only' else "sync_update_data"
            )
        ])
    
    keyboard.extend([
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_OTHER_OPTIONS", "🔄 Other options"), 
            callback_data="admin_rw_sync"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_BACK", "⬅️ Back"), 
            callback_data="admin_remnawave"
        )]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@admin_required
@error_handler
async def validate_subscriptions(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    
    await callback.message.edit_text(
        texts.get_text(
            "ADMIN_RW_SYNC_VALIDATION_PROGRESS",
            "🔍 Validating subscriptions...\n\nChecking data, may take a few minutes."
        ),
        reply_markup=None
    )
    
    remnawave_service = RemnaWaveService()
    stats = await remnawave_service.validate_and_fix_subscriptions(db)
    
    if stats['errors'] == 0:
        status_emoji = "✅"
        status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_SUCCESS", "successfully completed")
    else:
        status_emoji = "⚠️"
        status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_ERRORS", "completed with errors")
    
    text = texts.get_text(
        "ADMIN_RW_SYNC_VALIDATION_RESULT",
        "{status_emoji} <b>Validation {status_text}</b>\n\n"
        "📊 <b>Results:</b>\n"
        "• 🔍 Checked subscriptions: {checked}\n"
        "• 🔧 Fixed subscriptions: {fixed}\n"
        "• ⚠️ Issues found: {issues_found}\n"
        "• ❌ Errors: {errors}"
    ).format(
        status_emoji=status_emoji,
        status_text=status_text,
        checked=stats['checked'],
        fixed=stats['fixed'],
        issues_found=stats['issues_found'],
        errors=stats['errors']
    )
    
    if stats['fixed'] > 0:
        text += "\n" + texts.get_text(
            "ADMIN_RW_SYNC_VALIDATION_FIXED_ISSUES",
            "✅ <b>Fixed issues:</b>\n"
            "• Expired subscription statuses\n"
            "• Missing Remnawave data\n"
            "• Incorrect traffic limits\n"
            "• Device settings"
        )
    
    if stats['errors'] > 0:
        text += "\n" + texts.get_text(
            "ADMIN_RW_SYNC_VALIDATION_ERRORS",
            "⚠️ Errors detected during processing.\nCheck logs for detailed information."
        )
    
    keyboard = [
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_RETRY_VALIDATION", "🔄 Retry validation"), 
            callback_data="sync_validate"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_FULL", "🔄 Full synchronization"), 
            callback_data="sync_all_users"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_BACK", "⬅️ Back to sync"), 
            callback_data="admin_rw_sync"
        )]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@admin_required
@error_handler
async def cleanup_subscriptions(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    
    await callback.message.edit_text(
        texts.get_text(
            "ADMIN_RW_SYNC_CLEANUP_PROGRESS",
            "🧹 Cleaning up outdated subscriptions...\n\nRemoving subscriptions of users missing in panel."
        ),
        reply_markup=None
    )
    
    remnawave_service = RemnaWaveService()
    stats = await remnawave_service.cleanup_orphaned_subscriptions(db)
    
    if stats['errors'] == 0:
        status_emoji = "✅"
        status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_SUCCESS", "successfully completed")
    else:
        status_emoji = "⚠️"
        status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_ERRORS", "completed with errors")
    
    text = texts.get_text(
        "ADMIN_RW_SYNC_CLEANUP_RESULT",
        "{status_emoji} <b>Cleanup {status_text}</b>\n\n"
        "📊 <b>Results:</b>\n"
        "• 🔍 Checked subscriptions: {checked}\n"
        "• 🗑️ Deactivated: {deactivated}\n"
        "• ❌ Errors: {errors}"
    ).format(
        status_emoji=status_emoji,
        status_text=status_text,
        checked=stats['checked'],
        deactivated=stats['deactivated'],
        errors=stats['errors']
    )
    
    if stats['deactivated'] > 0:
        text += "\n" + texts.get_text(
            "ADMIN_RW_SYNC_CLEANUP_DEACTIVATED",
            "🗑️ <b>Deactivated subscriptions:</b>\n"
            "Subscriptions of users who are\n"
            "missing in Remnawave panel have been disabled."
        )
    else:
        text += "\n" + texts.get_text(
            "ADMIN_RW_SYNC_CLEANUP_ALL_CURRENT",
            "✅ All subscriptions are current!\nNo outdated subscriptions found."
        )
    
    if stats['errors'] > 0:
        text += "\n" + texts.get_text(
            "ADMIN_RW_SYNC_CLEANUP_ERRORS",
            "⚠️ Errors detected during processing.\nCheck logs for detailed information."
        )
    
    keyboard = [
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_RETRY_CLEANUP", "🔄 Retry cleanup"), 
            callback_data="sync_cleanup"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_VALIDATION", "🔍 Validation"), 
            callback_data="sync_validate"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_BACK", "⬅️ Back to sync"), 
            callback_data="admin_rw_sync"
        )]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@admin_required
@error_handler
async def force_cleanup_all_orphaned_users(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    
    await callback.message.edit_text(
        texts.get_text(
            "ADMIN_RW_SYNC_FORCE_CLEANUP_PROGRESS",
            "🗑️ Performing forced cleanup of all users missing in panel...\n\n"
            "⚠️ WARNING: This will completely remove ALL user data!\n"
            "📊 Including: transactions, referral earnings, promo codes, servers, balances\n\n"
            "⏳ Please wait..."
        ),
        reply_markup=None
    )
    
    remnawave_service = RemnaWaveService()
    stats = await remnawave_service.cleanup_orphaned_subscriptions(db)
    
    if stats['errors'] == 0:
        status_emoji = "✅"
        status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_SUCCESS", "successfully completed")
    else:
        status_emoji = "⚠️"
        status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_ERRORS", "completed with errors")
    
    text = texts.get_text(
        "ADMIN_RW_SYNC_FORCE_CLEANUP_RESULT",
        "{status_emoji} <b>Forced cleanup {status_text}</b>\n\n"
        "📊 <b>Results:</b>\n"
        "• 🔍 Checked subscriptions: {checked}\n"
        "• 🗑️ Completely cleaned: {deactivated}\n"
        "• ❌ Errors: {errors}"
    ).format(
        status_emoji=status_emoji,
        status_text=status_text,
        checked=stats['checked'],
        deactivated=stats['deactivated'],
        errors=stats['errors']
    )
    
    if stats['deactivated'] > 0:
        text += "\n\n" + texts.get_text(
            "ADMIN_RW_SYNC_FORCE_CLEANUP_CLEARED_DATA",
            "🗑️ <b>Completely cleared data:</b>\n"
            "• Subscriptions reset to initial state\n"
            "• ALL user transactions removed\n"
            "• ALL referral earnings removed\n"
            "• Promo code usages removed\n"
            "• Balances reset to zero\n"
            "• Connected servers removed\n"
            "• Device HWID reset in Remnawave\n"
            "• Remnawave UUID cleared"
        )
    else:
        text += "\n" + texts.get_text(
            "ADMIN_RW_SYNC_FORCE_CLEANUP_NONE_FOUND",
            "✅ No outdated subscriptions found!\nAll users synchronized with panel."
        )
    
    if stats['errors'] > 0:
        text += "\n" + texts.get_text(
            "ADMIN_RW_SYNC_FORCE_CLEANUP_ERRORS",
            "⚠️ Errors detected during processing.\nCheck logs for detailed information."
        )
    
    keyboard = [
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_RETRY_CLEANUP", "🔄 Retry cleanup"), 
            callback_data="force_cleanup_orphaned"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_FULL", "🔄 Full synchronization"), 
            callback_data="sync_all_users"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_BACK", "⬅️ Back to sync"), 
            callback_data="admin_rw_sync"
        )]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def confirm_force_cleanup(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    
    text = texts.get_text(
        "ADMIN_RW_SYNC_FORCE_CLEANUP_CONFIRM",
        "⚠️ <b>WARNING! DANGEROUS OPERATION!</b>\n\n"
        "🗑️ <b>Forced cleanup will completely remove:</b>\n"
        "• ALL transactions of users missing in panel\n"
        "• ALL referral earnings and connections\n"
        "• ALL promo code usages\n"
        "• ALL connected subscription servers\n"
        "• ALL balances (reset to zero)\n"
        "• ALL device HWID in Remnawave\n"
        "• ALL Remnawave UUID and links\n\n"
        "⚡ <b>This action is IRREVERSIBLE!</b>\n\n"
        "Use only if:\n"
        "• Regular synchronization doesn't help\n"
        "• Need to completely clean \"junk\" data\n"
        "• After mass deletion of users from panel\n\n"
        "❓ <b>Do you really want to continue?</b>"
    )
    
    keyboard = [
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_SYNC_FORCE_CLEANUP_CONFIRM_YES", "🗑️ YES, CLEAR ALL"), 
            callback_data="force_cleanup_orphaned"
        )],
        [types.InlineKeyboardButton(
            text=texts.get_text("ADMIN_RW_CANCEL", "❌ Cancel"), 
            callback_data="admin_rw_sync"
        )]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def sync_users(
   callback: types.CallbackQuery,
   db_user: User,
   db: AsyncSession
):
   texts = get_texts(db_user.language)
   sync_type = callback.data.split('_')[-2] + "_" + callback.data.split('_')[-1]
   
   if sync_type == "all_users":
       progress_text = texts.get_text(
           "ADMIN_RW_SYNC_USERS_PROGRESS_FULL",
           "🔄 Performing synchronization...\n\n"
           "📋 Type: Full synchronization\n"
           "• Creating new users\n"
           "• Updating existing\n"
           "• Removing outdated subscriptions\n\n"
           "⏳ Please wait..."
       )
   elif sync_type == "new_users":
       progress_text = texts.get_text(
           "ADMIN_RW_SYNC_USERS_PROGRESS_NEW",
           "🔄 Performing synchronization...\n\n"
           "📋 Type: New users only\n"
           "• Creating users from panel\n\n"
           "⏳ Please wait..."
       )
   elif sync_type == "update_data":
       progress_text = texts.get_text(
           "ADMIN_RW_SYNC_USERS_PROGRESS_UPDATE",
           "🔄 Performing synchronization...\n\n"
           "📋 Type: Data update\n"
           "• Updating traffic information\n"
           "• Synchronizing subscriptions\n\n"
           "⏳ Please wait..."
       )
   else:
       progress_text = texts.get_text(
           "ADMIN_RW_SYNC_USERS_PROGRESS",
           "🔄 Performing synchronization...\n\n⏳ Please wait..."
       )
   
   await callback.message.edit_text(
       progress_text,
       reply_markup=None
   )
   
   remnawave_service = RemnaWaveService()
   
   sync_map = {
       "all_users": "all",
       "new_users": "new_only", 
       "update_data": "update_only"
   }
   
   stats = await remnawave_service.sync_users_from_panel(db, sync_map.get(sync_type, "all"))
   
   total_operations = stats['created'] + stats['updated'] + stats.get('deleted', 0)
   
   if stats['errors'] == 0:
       status_emoji = "✅"
       status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_SUCCESS", "successfully completed")
   elif stats['errors'] < total_operations:
       status_emoji = "⚠️"
       status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_WARNINGS", "completed with warnings")
   else:
       status_emoji = "❌"
       status_text = texts.get_text("ADMIN_RW_SYNC_STATUS_ERRORS", "completed with errors")
   
   if sync_type == "all_users":
       text = texts.get_text(
           "ADMIN_RW_SYNC_USERS_RESULT_FULL",
           "{status_emoji} <b>Synchronization {status_text}</b>\n\n"
           "📊 <b>Result:</b>\n"
           "• 🆕 Created: {created}\n"
           "• 🔄 Updated: {updated}\n"
           "• 🗑️ Deleted: {deleted}\n"
           "• ❌ Errors: {errors}"
       ).format(
           status_emoji=status_emoji,
           status_text=status_text,
           created=stats['created'],
           updated=stats['updated'],
           deleted=stats.get('deleted', 0),
           errors=stats['errors']
       )
   elif sync_type == "new_users":
       no_new_text = ""
       if stats['created'] == 0 and stats['errors'] == 0:
           no_new_text = "\n" + texts.get_text("ADMIN_RW_SYNC_USERS_NO_NEW", "💡 No new users found")
       text = texts.get_text(
           "ADMIN_RW_SYNC_USERS_RESULT_NEW",
           "{status_emoji} <b>Synchronization {status_text}</b>\n\n"
           "📊 <b>Result:</b>\n"
           "• 🆕 Created: {created}\n"
           "• ❌ Errors: {errors}{no_new_text}"
       ).format(
           status_emoji=status_emoji,
           status_text=status_text,
           created=stats['created'],
           errors=stats['errors'],
           no_new_text=no_new_text
       )
   elif sync_type == "update_data":
       all_current_text = ""
       if stats['updated'] == 0 and stats['errors'] == 0:
           all_current_text = "\n" + texts.get_text("ADMIN_RW_SYNC_USERS_ALL_CURRENT", "💡 All data is current")
       text = texts.get_text(
           "ADMIN_RW_SYNC_USERS_RESULT_UPDATE",
           "{status_emoji} <b>Synchronization {status_text}</b>\n\n"
           "📊 <b>Result:</b>\n"
           "• 🔄 Updated: {updated}\n"
           "• ❌ Errors: {errors}{all_current_text}"
       ).format(
           status_emoji=status_emoji,
           status_text=status_text,
           updated=stats['updated'],
           errors=stats['errors'],
           all_current_text=all_current_text
       )
   else:
       text = texts.get_text(
           "ADMIN_RW_SYNC_USERS_RESULT",
           "{status_emoji} <b>Synchronization {status_text}</b>\n\n"
           "📊 <b>Result:</b>\n"
           "• ❌ Errors: {errors}"
       ).format(
           status_emoji=status_emoji,
           status_text=status_text,
           errors=stats['errors']
       )
   
   if stats['errors'] > 0:
       text += "\n" + texts.get_text(
           "ADMIN_RW_SYNC_USERS_ERRORS_WARNING",
           "⚠️ <b>Attention:</b>\n"
           "Some operations completed with errors.\n"
           "Check logs for detailed information."
       )
   
   if sync_type == "all_users" and 'deleted' in stats and stats['deleted'] > 0:
       text += "\n" + texts.get_text(
           "ADMIN_RW_SYNC_USERS_DELETED_SUBS",
           "🗑️ <b>Deleted subscriptions:</b>\n"
           "Subscriptions of users who are\n"
           "missing in Remnawave panel have been deactivated."
       )
   
   if sync_type == "all_users":
       recommendations = texts.get_text(
           "ADMIN_RW_SYNC_USERS_RECOMMENDATIONS_FULL",
           "💡 <b>Recommendations:</b>\n"
           "• Full synchronization completed\n"
           "• Recommended to run once per day"
       )
   elif sync_type == "new_users":
       recommendations = texts.get_text(
           "ADMIN_RW_SYNC_USERS_RECOMMENDATIONS_NEW",
           "💡 <b>Recommendations:</b>\n"
           "• New users synchronization\n"
           "• Use when adding users in bulk"
       )
   elif sync_type == "update_data":
       recommendations = texts.get_text(
           "ADMIN_RW_SYNC_USERS_RECOMMENDATIONS_UPDATE",
           "💡 <b>Recommendations:</b>\n"
           "• Traffic data update\n"
           "• Run to update statistics"
       )
   else:
       recommendations = ""
   
   if recommendations:
       text += "\n\n" + recommendations
   
   keyboard = []
   
   if stats['errors'] > 0:
       keyboard.append([
           types.InlineKeyboardButton(
               text=texts.get_text("ADMIN_RW_SYNC_RETRY", "🔄 Retry synchronization"), 
               callback_data=callback.data
           )
       ])
   
   if sync_type != "all_users":
       keyboard.append([
           types.InlineKeyboardButton(
               text=texts.get_text("ADMIN_RW_SYNC_FULL", "🔄 Full synchronization"), 
               callback_data="sync_all_users"
           )
       ])
   
   keyboard.extend([
       [
           types.InlineKeyboardButton(
               text=texts.get_text("ADMIN_RW_SYSTEM_STATS", "📊 System statistics"), 
               callback_data="admin_rw_system"
           ),
           types.InlineKeyboardButton(
               text=texts.get_text("ADMIN_RW_NODES", "🌐 Nodes"), 
               callback_data="admin_rw_nodes"
           )
       ],
       [types.InlineKeyboardButton(
           text=texts.get_text("ADMIN_RW_BACK", "⬅️ Back"), 
           callback_data="admin_remnawave"
       )]
   ])
   
   await callback.message.edit_text(
       text,
       reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
   )
   await callback.answer()


@admin_required
@error_handler
async def show_squads_management(
   callback: types.CallbackQuery,
   db_user: User,
   db: AsyncSession
):
   texts = get_texts(db_user.language)
   remnawave_service = RemnaWaveService()
   squads = await remnawave_service.get_all_squads()
   
   text = texts.get_text(
       "ADMIN_RW_SQUADS_MANAGEMENT_TITLE",
       "🌍 <b>Squads Management</b>",
   ) + "\n\n"
   keyboard = []
   
   if squads:
       for squad in squads:
           text += f"🔹 <b>{squad['name']}</b>\n"
           text += texts.get_text(
               "ADMIN_RW_SQUADS_MEMBERS_COUNT",
               "👥 Members: {count}",
           ).format(count=squad['members_count']) + "\n"
           text += texts.get_text(
               "ADMIN_RW_SQUADS_INBOUNDS_COUNT",
               "📡 Inbounds: {count}",
           ).format(count=squad['inbounds_count']) + "\n\n"
           
           keyboard.append([
               types.InlineKeyboardButton(
                   text=f"⚙️ {squad['name']}",
                   callback_data=f"admin_squad_manage_{squad['uuid']}"
               )
           ])
   else:
       text += texts.get_text(
           "ADMIN_RW_SQUADS_NOT_FOUND",
           "Squads not found",
       )
   
   keyboard.extend([
       [types.InlineKeyboardButton(
           text=texts.t("ADMIN_RW_SQUADS_CREATE", "➕ Create squad"),
           callback_data="admin_squad_create"
       )],
       [types.InlineKeyboardButton(
           text=texts.get_text("ADMIN_RW_BACK", "⬅️ Back"),
           callback_data="admin_remnawave"
       )]
   ])
   
   await callback.message.edit_text(
       text,
       reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
       parse_mode="HTML"
   )
   await callback.answer()


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_remnawave_menu, F.data == "admin_remnawave")
    dp.callback_query.register(show_system_stats, F.data == "admin_rw_system")
    dp.callback_query.register(show_traffic_stats, F.data == "admin_rw_traffic")
    dp.callback_query.register(show_nodes_management, F.data == "admin_rw_nodes")
    dp.callback_query.register(show_node_details, F.data.startswith("admin_node_manage_"))
    dp.callback_query.register(show_node_statistics, F.data.startswith("node_stats_"))
    dp.callback_query.register(manage_node, F.data.startswith("node_enable_"))
    dp.callback_query.register(manage_node, F.data.startswith("node_disable_"))
    dp.callback_query.register(manage_node, F.data.startswith("node_restart_"))
    dp.callback_query.register(restart_all_nodes, F.data == "admin_restart_all_nodes")
    dp.callback_query.register(show_sync_options, F.data == "admin_rw_sync")
    dp.callback_query.register(show_auto_sync_settings, F.data == "admin_rw_auto_sync")
    dp.callback_query.register(toggle_auto_sync_setting, F.data == "remnawave_auto_sync_toggle")
    dp.callback_query.register(prompt_auto_sync_schedule, F.data == "remnawave_auto_sync_times")
    dp.callback_query.register(cancel_auto_sync_schedule, F.data == "remnawave_auto_sync_cancel")
    dp.callback_query.register(run_auto_sync_now, F.data == "remnawave_auto_sync_run")
    dp.callback_query.register(sync_all_users, F.data == "sync_all_users")
    dp.callback_query.register(sync_users_to_panel, F.data == "sync_to_panel")
    dp.callback_query.register(show_squad_migration_menu, F.data == "admin_rw_migration")
    dp.callback_query.register(paginate_migration_source, F.data.startswith("admin_migration_source_page_"))
    dp.callback_query.register(handle_migration_source_selection, F.data.startswith("admin_migration_source_"))
    dp.callback_query.register(paginate_migration_target, F.data.startswith("admin_migration_target_page_"))
    dp.callback_query.register(handle_migration_target_selection, F.data.startswith("admin_migration_target_"))
    dp.callback_query.register(change_migration_target, F.data == "admin_migration_change_target")
    dp.callback_query.register(confirm_squad_migration, F.data == "admin_migration_confirm")
    dp.callback_query.register(cancel_squad_migration, F.data == "admin_migration_cancel")
    dp.callback_query.register(handle_migration_page_info, F.data == "admin_migration_page_info")
    dp.callback_query.register(show_squads_management, F.data == "admin_rw_squads")
    dp.callback_query.register(show_squad_details, F.data.startswith("admin_squad_manage_"))
    dp.callback_query.register(manage_squad_action, F.data.startswith("squad_add_users_"))
    dp.callback_query.register(manage_squad_action, F.data.startswith("squad_remove_users_"))
    dp.callback_query.register(manage_squad_action, F.data.startswith("squad_delete_"))
    dp.callback_query.register(show_squad_edit_menu, F.data.startswith("squad_edit_") & ~F.data.startswith("squad_edit_inbounds_"))
    dp.callback_query.register(show_squad_inbounds_selection, F.data.startswith("squad_edit_inbounds_"))
    dp.callback_query.register(show_squad_rename_form, F.data.startswith("squad_rename_"))
    dp.callback_query.register(cancel_squad_rename, F.data.startswith("cancel_rename_"))
    dp.callback_query.register(toggle_squad_inbound, F.data.startswith("sqd_tgl_"))
    dp.callback_query.register(save_squad_inbounds, F.data.startswith("sqd_save_"))
    dp.callback_query.register(show_squad_edit_menu_short, F.data.startswith("sqd_edit_"))
    dp.callback_query.register(start_squad_creation, F.data == "admin_squad_create")
    dp.callback_query.register(cancel_squad_creation, F.data == "cancel_squad_create")
    dp.callback_query.register(toggle_create_inbound, F.data.startswith("create_tgl_"))
    dp.callback_query.register(finish_squad_creation, F.data == "create_squad_finish")
    
    dp.message.register(
        process_squad_new_name,
        SquadRenameStates.waiting_for_new_name,
        F.text
    )

    dp.message.register(
        process_squad_name,
        SquadCreateStates.waiting_for_name,
        F.text
    )

    dp.message.register(
        save_auto_sync_schedule,
        RemnaWaveSyncStates.waiting_for_schedule,
        F.text,
    )
