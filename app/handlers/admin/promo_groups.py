import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Optional, Tuple

from aiogram import Dispatcher, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.promo_group import (
    get_promo_groups_with_counts,
    get_promo_group_by_id,
    create_promo_group,
    update_promo_group,
    delete_promo_group,
    get_promo_group_members,
    count_promo_group_members,
)
from app.database.models import PromoGroup
from app.localization.texts import get_texts
from app.states import AdminStates
from app.utils.decorators import admin_required, error_handler
from app.keyboards.admin import (
    get_admin_pagination_keyboard,
    get_confirmation_keyboard,
)
from app.utils.pricing_utils import format_period_description
logger = logging.getLogger(__name__)


def _format_discount_lines(texts, group) -> list[str]:
    return [
        texts.get_text(
            "ADMIN_PROMO_GROUP_DISCOUNTS_HEADER",
            "💸 Promo group discounts:",
        ),
        texts.get_text(
            "ADMIN_PROMO_GROUP_DISCOUNT_LINE_SERVERS",
            "• Servers: {percent}%",
        ).format(percent=group.server_discount_percent),
        texts.get_text(
            "ADMIN_PROMO_GROUP_DISCOUNT_LINE_TRAFFIC",
            "• Traffic: {percent}%",
        ).format(percent=group.traffic_discount_percent),
        texts.get_text(
            "ADMIN_PROMO_GROUP_DISCOUNT_LINE_DEVICES",
            "• Devices: {percent}%",
        ).format(percent=group.device_discount_percent),
    ]


def _format_addon_discounts_line(texts, group: PromoGroup) -> str:
    enabled = getattr(group, "apply_discounts_to_addons", True)
    if enabled:
        return texts.get_text(
            "ADMIN_PROMO_GROUP_ADDON_DISCOUNT_ENABLED",
            "🧩 Add-on discounts: <b>enabled</b>",
        )
    return texts.get_text(
        "ADMIN_PROMO_GROUP_ADDON_DISCOUNT_DISABLED",
        "🧩 Add-on discounts: <b>disabled</b>",
    )


def _get_addon_discounts_button_text(texts, group: PromoGroup) -> str:
    enabled = getattr(group, "apply_discounts_to_addons", True)
    if enabled:
        return texts.get_text(
            "ADMIN_PROMO_GROUP_TOGGLE_ADDON_DISCOUNT_DISABLE",
            "🧩 Disable add-on discounts",
        )
    return texts.get_text(
        "ADMIN_PROMO_GROUP_TOGGLE_ADDON_DISCOUNT_ENABLE",
        "🧩 Enable add-on discounts",
    )


def _normalize_periods_dict(raw: Optional[Dict]) -> Dict[int, int]:
    if not raw or not isinstance(raw, dict):
        return {}

    normalized: Dict[int, int] = {}

    for key, value in raw.items():
        try:
            period = int(key)
            percent = int(value)
        except (TypeError, ValueError):
            continue

        normalized[period] = max(0, min(100, percent))

    return normalized


def _collect_period_discounts(group: PromoGroup) -> Dict[int, int]:
    discounts = _normalize_periods_dict(getattr(group, "period_discounts", None))

    if discounts:
        return dict(sorted(discounts.items()))

    if group.is_default and settings.is_base_promo_group_period_discount_enabled():
        try:
            base_discounts = settings.get_base_promo_group_period_discounts()
            normalized = _normalize_periods_dict(base_discounts)
            return dict(sorted(normalized.items()))
        except Exception:
            return {}

    return {}


def _format_period_discounts_lines(texts, group: PromoGroup, language: str) -> list:
    discounts = _collect_period_discounts(group)

    if not discounts:
        return []

    header = texts.get_text(
        "ADMIN_PROMO_GROUP_PERIOD_DISCOUNTS_HEADER",
        "⏳ Period discounts:",
    )

    lines = [header]

    for period_days, percent in discounts.items():
        period_display = format_period_description(period_days, language)
        lines.append(
            texts.get_text("PROMO_GROUP_PERIOD_DISCOUNT_ITEM", "{period} — {percent}%").format(
                period=period_display,
                percent=percent,
            )
        )

    return lines


def _format_period_discounts_value(discounts: Dict[int, int]) -> str:
    if not discounts:
        return "0"

    return ", ".join(
        f"{period}:{percent}"
        for period, percent in sorted(discounts.items())
    )


def _parse_period_discounts_input(value: str) -> Dict[int, int]:
    cleaned = (value or "").strip()

    if not cleaned or cleaned in {"0", "-"}:
        return {}

    cleaned = cleaned.replace(";", ",").replace("\n", ",")
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]

    if not parts:
        return {}

    discounts: Dict[int, int] = {}

    for part in parts:
        if ":" not in part:
            raise ValueError

        period_raw, percent_raw = part.split(":", 1)

        period = int(period_raw.strip())
        percent = int(percent_raw.strip())

        if period <= 0:
            raise ValueError

        discounts[period] = max(0, min(100, percent))

    return discounts


async def _prompt_for_period_discounts(
    message: types.Message,
    state: FSMContext,
    prompt_key: str,
    default_text: str,
    *,
    current_value: Optional[str] = None,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", "en"))
    prompt_text = texts.get_text(prompt_key, default_text)

    if current_value is not None:
        try:
            prompt_text = prompt_text.format(current=current_value)
        except KeyError:
            pass

    await message.answer(prompt_text)


def _format_rubles(amount_kopeks: int) -> str:
    if amount_kopeks <= 0:
        return "0"

    rubles = Decimal(amount_kopeks) / Decimal(100)
    if rubles == rubles.to_integral_value():
        formatted = f"{rubles:,.0f}"
    else:
        formatted = f"{rubles:,.2f}"

    return formatted.replace(",", " ")


def _format_priority_line(texts, group: PromoGroup) -> str:
    priority = getattr(group, "priority", 0)
    return texts.get_text(
        "ADMIN_PROMO_GROUP_PRIORITY_LINE",
        "🎯 Priority: {priority}",
    ).format(priority=priority)


def _format_auto_assign_line(texts, group: PromoGroup) -> str:
    threshold = getattr(group, "auto_assign_total_spent_kopeks", 0) or 0

    if threshold <= 0:
        return texts.get_text(
            "ADMIN_PROMO_GROUP_AUTO_ASSIGN_DISABLED",
            "Auto-assign by total spent: disabled",
        )

    amount = _format_rubles(threshold)
    return texts.get_text(
        "ADMIN_PROMO_GROUP_AUTO_ASSIGN_LINE",
        "Auto-assign by total spent: from {amount}",
    ).format(amount=amount)


def _format_auto_assign_value(value_kopeks: Optional[int]) -> str:
    if not value_kopeks or value_kopeks <= 0:
        return "0"

    rubles = Decimal(value_kopeks) / Decimal(100)
    quantized = (
        rubles.quantize(Decimal("1"))
        if rubles == rubles.to_integral_value()
        else rubles.quantize(Decimal("0.01"))
    )
    return str(quantized)


def _parse_auto_assign_threshold_input(value: str) -> int:
    cleaned = (value or "").strip()

    if not cleaned or cleaned in {"0", "-", "off"}:
        return 0

    normalized = cleaned.replace(" ", "").replace(",", ".")

    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        raise ValueError

    if amount < 0:
        raise ValueError

    kopeks = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return max(0, kopeks)


async def _prompt_for_auto_assign_threshold(
    message: types.Message,
    state: FSMContext,
    prompt_key: str,
    default_text: str,
    *,
    current_value: Optional[str] = None,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", "en"))
    prompt_text = texts.get_text(prompt_key, default_text)

    if current_value is not None:
        try:
            prompt_text = prompt_text.format(current=current_value)
        except KeyError:
            pass

    await message.answer(prompt_text)


def _build_edit_menu_content(
    texts,
    group: PromoGroup,
    language: str,
) -> Tuple[str, types.InlineKeyboardMarkup]:
    header = texts.get_text(
        "ADMIN_PROMO_GROUP_EDIT_MENU_TITLE",
        "✏️ Promo group settings «{name}»",
    ).format(name=group.name)

    lines = [header]
    lines.extend(_format_discount_lines(texts, group))
    lines.append(_format_addon_discounts_line(texts, group))
    lines.append(_format_priority_line(texts, group))
    lines.append(_format_auto_assign_line(texts, group))

    period_lines = _format_period_discounts_lines(texts, group, language)
    lines.extend(period_lines)

    lines.append(
        texts.get_text(
            "ADMIN_PROMO_GROUP_EDIT_MENU_HINT",
            "Select parameter to change:",
        )
    )

    text = "\n".join(line for line in lines if line)

    keyboard_rows = [
        [
            types.InlineKeyboardButton(
                text=texts.get_text(
                    "ADMIN_PROMO_GROUP_EDIT_FIELD_NAME",
                    "✏️ Edit name",
                ),
                callback_data=f"promo_group_edit_field_{group.id}_name",
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.get_text(
                    "ADMIN_PROMO_GROUP_EDIT_FIELD_PRIORITY",
                    "🎯 Priority",
                ),
                callback_data=f"promo_group_edit_field_{group.id}_priority",
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.get_text(
                    "ADMIN_PROMO_GROUP_EDIT_FIELD_TRAFFIC",
                    "🌐 Traffic discount",
                ),
                callback_data=f"promo_group_edit_field_{group.id}_traffic",
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.get_text(
                    "ADMIN_PROMO_GROUP_EDIT_FIELD_SERVERS",
                    "🖥 Server discount",
                ),
                callback_data=f"promo_group_edit_field_{group.id}_servers",
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.get_text(
                    "ADMIN_PROMO_GROUP_EDIT_FIELD_DEVICES",
                    "📱 Device discount",
                ),
                callback_data=f"promo_group_edit_field_{group.id}_devices",
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.get_text(
                    "ADMIN_PROMO_GROUP_EDIT_FIELD_PERIODS",
                    "⏳ Period discounts",
                ),
                callback_data=f"promo_group_edit_field_{group.id}_periods",
            )
        ],
        [
            types.InlineKeyboardButton(
                text=_get_addon_discounts_button_text(texts, group),
                callback_data=f"promo_group_toggle_addons_{group.id}",
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.get_text(
                    "ADMIN_PROMO_GROUP_EDIT_FIELD_AUTO_ASSIGN",
                    "🤖 Auto-assign by spending",
                ),
                callback_data=f"promo_group_edit_field_{group.id}_auto",
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.BACK,
                callback_data=f"promo_group_manage_{group.id}",
            )
        ],
    ]

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    return text, keyboard


def _get_edit_prompt_keyboard(group_id: int, texts) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.BACK,
                    callback_data=f"promo_group_edit_{group_id}",
                )
            ]
        ]
    )


async def _send_edit_menu_after_update(
    message: types.Message,
    texts,
    group: PromoGroup,
    language: str,
    success_message: Optional[str] = None,
):
    menu_text, keyboard = _build_edit_menu_content(texts, group, language)
    parts = [part for part in [success_message, menu_text] if part]

    text = "\n\n".join(parts)

    from_user = getattr(message, "from_user", None)

    if getattr(from_user, "is_bot", False):
        try:
            await message.edit_text(
                text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            return
        except TelegramBadRequest:
            pass

    await message.answer(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )


@admin_required
@error_handler
async def show_promo_groups_menu(
    callback: types.CallbackQuery,
    db_user,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    groups = await get_promo_groups_with_counts(db)

    total_members = sum(count for _, count in groups)
    header = texts.get_text("ADMIN_PROMO_GROUPS_TITLE", "💳 <b>Promo groups</b>")

    if groups:
        summary = texts.get_text(
            "ADMIN_PROMO_GROUPS_SUMMARY",
            "Total groups: {count}\nTotal members: {members}",
        ).format(count=len(groups), members=total_members)
        lines = [header, "", summary, ""]

        keyboard_rows = []
        for group, member_count in groups:
            default_suffix = (
                texts.get_text("ADMIN_PROMO_GROUPS_DEFAULT_LABEL", " (default)")
                if group.is_default
                else ""
            )
            group_lines = [
                f"{'⭐' if group.is_default else '🎯'} <b>{group.name}</b>{default_suffix}",
            ]
            group_lines.extend(_format_discount_lines(texts, group))
            group_lines.append(_format_auto_assign_line(texts, group))
            group_lines.append(
                texts.get_text(
                    "ADMIN_PROMO_GROUPS_MEMBERS_COUNT",
                    "Members: {count}",
                ).format(count=member_count)
            )

            period_lines = _format_period_discounts_lines(texts, group, db_user.language)
            group_lines.extend(period_lines)
            group_lines.append("")

            lines.extend(group_lines)
            keyboard_rows.append([
                types.InlineKeyboardButton(
                    text=f"{'⭐' if group.is_default else '🎯'} {group.name}",
                    callback_data=f"promo_group_manage_{group.id}",
                )
            ])
    else:
        lines = [header, "", texts.get_text("ADMIN_PROMO_GROUPS_EMPTY", "No promo groups found.")]
        keyboard_rows = []

    keyboard_rows.append(
        [types.InlineKeyboardButton(text=texts.get_text("ADMIN_PROMO_GROUP_BTN_CREATE", "➕ Create"), callback_data="admin_promo_group_create")]
    )
    keyboard_rows.append(
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_promo")]
    )

    await callback.message.edit_text(
        "\n".join(line for line in lines if line is not None),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML",
    )
    await callback.answer()


async def _get_group_or_alert(
    callback: types.CallbackQuery,
    db: AsyncSession,
) -> Optional[PromoGroup]:
    group_id = int(callback.data.split("_")[-1])
    group = await get_promo_group_by_id(db, group_id)
    if not group:
        texts = get_texts("en")
        await callback.answer(texts.get_text("ADMIN_PROMO_GROUP_NOT_FOUND", "❌ Promo group not found"), show_alert=True)
        return None
    return group


@admin_required
@error_handler
async def show_promo_group_details(
    callback: types.CallbackQuery,
    db_user,
    db: AsyncSession,
):
    group = await _get_group_or_alert(callback, db)
    if not group:
        return

    texts = get_texts(db_user.language)
    member_count = await count_promo_group_members(db, group.id)

    default_note = (
        texts.get_text("ADMIN_PROMO_GROUP_DETAILS_DEFAULT", "This is the default group.")
        if group.is_default
        else ""
    )

    lines = [
        texts.get_text(
            "ADMIN_PROMO_GROUP_DETAILS_TITLE",
            "💳 <b>Promo group:</b> {name}",
        ).format(name=group.name)
    ]
    lines.extend(_format_discount_lines(texts, group))
    lines.append(_format_auto_assign_line(texts, group))
    lines.append(
        texts.get_text(
            "ADMIN_PROMO_GROUP_DETAILS_MEMBERS",
            "Members: {count}",
        ).format(count=member_count)
    )

    period_lines = _format_period_discounts_lines(texts, group, db_user.language)
    lines.extend(period_lines)

    if default_note:
        lines.append(default_note)

    text = "\n".join(line for line in lines if line)

    keyboard_rows = []
    if member_count > 0:
        keyboard_rows.append(
            [
                types.InlineKeyboardButton(
                    text=texts.get_text("ADMIN_PROMO_GROUP_MEMBERS_BUTTON", "👥 Members"),
                    callback_data=f"promo_group_members_{group.id}_page_1",
                )
            ]
        )

    keyboard_rows.append(
        [
            types.InlineKeyboardButton(
                text=texts.get_text("ADMIN_PROMO_GROUP_EDIT_BUTTON", "✏️ Edit"),
                callback_data=f"promo_group_edit_{group.id}",
            )
        ]
    )

    if not group.is_default:
        keyboard_rows.append(
            [
                types.InlineKeyboardButton(
                    text=texts.get_text("ADMIN_PROMO_GROUP_DELETE_BUTTON", "🗑️ Delete"),
                    callback_data=f"promo_group_delete_{group.id}",
                )
            ]
        )

    keyboard_rows.append(
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_promo_groups")]
    )

    await callback.message.edit_text(
        text.strip(),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML",
    )
    await callback.answer()


def _validate_percent(value: str) -> int:
    percent = int(value)
    if percent < 0 or percent > 100:
        raise ValueError
    return percent


async def _prompt_for_discount(
    message: types.Message,
    state: FSMContext,
    prompt_key: str,
    default_text: str,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", "en"))
    await message.answer(texts.get_text(prompt_key, default_text))


@admin_required
@error_handler
async def start_create_promo_group(
    callback: types.CallbackQuery,
    db_user,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    await state.set_state(AdminStates.creating_promo_group_name)
    await state.update_data(language=db_user.language)
    await callback.message.edit_text(
        texts.get_text("ADMIN_PROMO_GROUP_CREATE_NAME_PROMPT", "Enter name for new promo group:"),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_promo_groups")]
            ]
        ),
    )
    await callback.answer()


async def process_create_group_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        texts = get_texts((await state.get_data()).get("language", "en"))
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_INVALID_NAME", "Name cannot be empty."))
        return

    await state.update_data(new_group_name=name)
    await state.set_state(AdminStates.creating_promo_group_priority)
    texts = get_texts((await state.get_data()).get("language", "en"))
    await message.answer(
        texts.get_text(
            "ADMIN_PROMO_GROUP_CREATE_PRIORITY_PROMPT",
            "Enter group priority (0 = default, higher = higher priority):",
        )
    )


async def process_create_group_priority(message: types.Message, state: FSMContext):
    texts = get_texts((await state.get_data()).get("language", "en"))
    try:
        priority = int(message.text)
        if priority < 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer(
            texts.get_text(
                "ADMIN_PROMO_GROUP_INVALID_PRIORITY",
                "❌ Priority must be a non-negative integer",
            )
        )
        return

    await state.update_data(new_group_priority=priority)
    await state.set_state(AdminStates.creating_promo_group_traffic_discount)
    await _prompt_for_discount(
        message,
        state,
        "ADMIN_PROMO_GROUP_CREATE_TRAFFIC_PROMPT",
        "Enter traffic discount (0-100):",
    )


async def process_create_group_traffic(message: types.Message, state: FSMContext):
    texts = get_texts((await state.get_data()).get("language", "en"))
    try:
        value = _validate_percent(message.text)
    except (ValueError, TypeError):
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_INVALID_PERCENT", "Enter a number from 0 to 100."))
        return

    await state.update_data(new_group_traffic=value)
    await state.set_state(AdminStates.creating_promo_group_server_discount)
    await _prompt_for_discount(
        message,
        state,
        "ADMIN_PROMO_GROUP_CREATE_SERVERS_PROMPT",
        "Enter server discount (0-100):",
    )


async def process_create_group_servers(message: types.Message, state: FSMContext):
    texts = get_texts((await state.get_data()).get("language", "en"))
    try:
        value = _validate_percent(message.text)
    except (ValueError, TypeError):
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_INVALID_PERCENT", "Enter a number from 0 to 100."))
        return

    await state.update_data(new_group_servers=value)
    await state.set_state(AdminStates.creating_promo_group_device_discount)
    await _prompt_for_discount(
        message,
        state,
        "ADMIN_PROMO_GROUP_CREATE_DEVICES_PROMPT",
        "Enter device discount (0-100):",
    )


@admin_required
@error_handler
async def process_create_group_devices(
    message: types.Message,
    state: FSMContext,
    db_user,
    db: AsyncSession,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", db_user.language))

    try:
        devices_discount = _validate_percent(message.text)
    except (ValueError, TypeError):
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_INVALID_PERCENT", "Enter a number from 0 to 100."))
        return

    await state.update_data(new_group_devices=devices_discount)
    await state.set_state(AdminStates.creating_promo_group_period_discount)

    await _prompt_for_period_discounts(
        message,
        state,
        "ADMIN_PROMO_GROUP_CREATE_PERIOD_PROMPT",
        "Enter subscription period discounts (e.g., 30:10, 90:15). Send 0 if no discounts.",
    )


@admin_required
@error_handler
async def process_create_group_period_discounts(
    message: types.Message,
    state: FSMContext,
    db_user,
    db: AsyncSession,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", db_user.language))

    try:
        period_discounts = _parse_period_discounts_input(message.text)
    except ValueError:
        await message.answer(
            texts.get_text(
                "ADMIN_PROMO_GROUP_INVALID_PERIOD_DISCOUNTS",
                "Enter period:discount pairs separated by comma, e.g. 30:10, 90:15, or 0.",
            )
        )
        return

    await state.update_data(new_group_period_discounts=period_discounts)
    await state.set_state(AdminStates.creating_promo_group_auto_assign)

    await _prompt_for_auto_assign_threshold(
        message,
        state,
        "ADMIN_PROMO_GROUP_CREATE_AUTO_ASSIGN_PROMPT",
        "Enter total spending amount for automatic group assignment. Send 0 to disable.",
    )


@admin_required
@error_handler
async def process_create_group_auto_assign(
    message: types.Message,
    state: FSMContext,
    db_user,
    db: AsyncSession,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", db_user.language))

    try:
        auto_assign_kopeks = _parse_auto_assign_threshold_input(message.text)
    except ValueError:
        await message.answer(
            texts.get_text(
                "ADMIN_PROMO_GROUP_INVALID_AUTO_ASSIGN",
                "Enter a non-negative number or 0 to disable.",
            )
        )
        return

    try:
        group = await create_promo_group(
            db,
            data["new_group_name"],
            priority=data.get("new_group_priority", 0),
            traffic_discount_percent=data["new_group_traffic"],
            server_discount_percent=data["new_group_servers"],
            device_discount_percent=data["new_group_devices"],
            period_discounts=data.get("new_group_period_discounts"),
            auto_assign_total_spent_kopeks=auto_assign_kopeks,
        )
    except Exception as e:
        logger.error(f"Failed to create promo group: {e}")
        await message.answer(texts.ERROR)
        await state.clear()
        return

    await state.clear()
    await message.answer(
        texts.get_text("ADMIN_PROMO_GROUP_CREATED", "Promo group «{name}» created.").format(
            name=group.name
        ),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.get_text(
                            "ADMIN_PROMO_GROUP_CREATED_BACK_BUTTON",
                            "↩️ To promo groups",
                        ),
                        callback_data="admin_promo_groups",
                    )
                ]
            ]
        ),
    )


@admin_required
@error_handler
async def start_edit_promo_group(
    callback: types.CallbackQuery,
    db_user,
    state: FSMContext,
    db: AsyncSession,
):
    group = await _get_group_or_alert(callback, db)
    if not group:
        return

    texts = get_texts(db_user.language)
    await state.update_data(edit_group_id=group.id, language=db_user.language)
    await state.set_state(AdminStates.editing_promo_group_menu)

    text, keyboard = _build_edit_menu_content(texts, group, db_user.language)
    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@admin_required
@error_handler
async def prompt_edit_promo_group_field(
    callback: types.CallbackQuery,
    db_user,
    state: FSMContext,
    db: AsyncSession,
):
    parts = callback.data.split("_")
    if len(parts) < 6:
        texts = get_texts(db_user.language)
        await callback.answer(texts.get_text("ADMIN_PROMO_GROUP_INVALID_COMMAND", "❌ Invalid command"), show_alert=True)
        return

    group_id = int(parts[4])
    field = parts[5]

    group = await get_promo_group_by_id(db, group_id)
    if not group:
        texts = get_texts(db_user.language)
        await callback.answer(texts.get_text("ADMIN_PROMO_GROUP_NOT_FOUND", "❌ Promo group not found"), show_alert=True)
        return

    await state.update_data(edit_group_id=group.id, language=db_user.language)

    texts = get_texts(db_user.language)
    reply_markup = _get_edit_prompt_keyboard(group.id, texts)

    if field == "name":
        await state.set_state(AdminStates.editing_promo_group_name)
        prompt = texts.get_text(
            "ADMIN_PROMO_GROUP_EDIT_NAME_PROMPT",
            "Enter new promo group name (current: {name}):",
        ).format(name=group.name)
    elif field == "priority":
        await state.set_state(AdminStates.editing_promo_group_priority)
        prompt = texts.get_text(
            "ADMIN_PROMO_GROUP_EDIT_PRIORITY_PROMPT",
            "Enter new priority (current: {current}):",
        ).format(current=getattr(group, "priority", 0))
    elif field == "traffic":
        await state.set_state(AdminStates.editing_promo_group_traffic_discount)
        prompt = texts.get_text(
            "ADMIN_PROMO_GROUP_EDIT_TRAFFIC_PROMPT",
            "Enter new traffic discount (current value: {current}%):",
        ).format(current=group.traffic_discount_percent)
    elif field == "servers":
        await state.set_state(AdminStates.editing_promo_group_server_discount)
        prompt = texts.get_text(
            "ADMIN_PROMO_GROUP_EDIT_SERVERS_PROMPT",
            "Enter new server discount (current value: {current}%):",
        ).format(current=group.server_discount_percent)
    elif field == "devices":
        await state.set_state(AdminStates.editing_promo_group_device_discount)
        prompt = texts.get_text(
            "ADMIN_PROMO_GROUP_EDIT_DEVICES_PROMPT",
            "Enter new device discount (current value: {current}%):",
        ).format(current=group.device_discount_percent)
    elif field == "periods":
        await state.set_state(AdminStates.editing_promo_group_period_discount)
        current_discounts = _normalize_periods_dict(getattr(group, "period_discounts", None))
        prompt = texts.get_text(
            "ADMIN_PROMO_GROUP_EDIT_PERIOD_PROMPT",
            "Enter new period discounts (current: {current}). Send 0 if no discounts.",
        ).format(current=_format_period_discounts_value(current_discounts))
    elif field == "auto":
        await state.set_state(AdminStates.editing_promo_group_auto_assign)
        prompt = texts.get_text(
            "ADMIN_PROMO_GROUP_EDIT_AUTO_ASSIGN_PROMPT",
            "Enter total spending amount for auto-assign. Current value: {current}.",
        ).format(current=_format_auto_assign_value(group.auto_assign_total_spent_kopeks))
    else:
        await callback.answer(texts.get_text("ADMIN_PROMO_GROUP_UNKNOWN_PARAM", "❌ Unknown parameter"), show_alert=True)
        return

    await callback.message.edit_text(prompt, reply_markup=reply_markup)
    await callback.answer()


@admin_required
@error_handler
async def process_edit_group_name(
    message: types.Message,
    state: FSMContext,
    db_user,
    db: AsyncSession,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", db_user.language))

    name = message.text.strip()
    if not name:
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_INVALID_NAME", "Name cannot be empty."))
        return

    group = await get_promo_group_by_id(db, data.get("edit_group_id"))
    if not group:
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_NOT_FOUND", "❌ Promo group not found"))
        await state.clear()
        return

    group = await update_promo_group(db, group, name=name)
    await state.set_state(AdminStates.editing_promo_group_menu)

    await _send_edit_menu_after_update(
        message,
        texts,
        group,
        data.get("language", db_user.language),
        texts.get_text("ADMIN_PROMO_GROUP_UPDATED", "Promo group «{name}» updated.").format(name=group.name),
    )


@admin_required
@error_handler
async def process_edit_group_priority(
    message: types.Message,
    state: FSMContext,
    db_user,
    db: AsyncSession,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", db_user.language))

    try:
        priority = int(message.text)
        if priority < 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer(
            texts.get_text(
                "ADMIN_PROMO_GROUP_INVALID_PRIORITY",
                "❌ Priority must be a non-negative integer",
            )
        )
        return

    group = await get_promo_group_by_id(db, data.get("edit_group_id"))
    if not group:
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_NOT_FOUND", "❌ Promo group not found"))
        await state.clear()
        return

    group = await update_promo_group(db, group, priority=priority)
    await state.set_state(AdminStates.editing_promo_group_menu)

    await _send_edit_menu_after_update(
        message,
        texts,
        group,
        data.get("language", db_user.language),
        texts.get_text("ADMIN_PROMO_GROUP_UPDATED", "Promo group «{name}» updated.").format(name=group.name),
    )


@admin_required
@error_handler
async def process_edit_group_traffic(
    message: types.Message,
    state: FSMContext,
    db_user,
    db: AsyncSession,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", db_user.language))

    try:
        value = _validate_percent(message.text)
    except (ValueError, TypeError):
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_INVALID_PERCENT", "Enter a number from 0 to 100."))
        return

    group = await get_promo_group_by_id(db, data.get("edit_group_id"))
    if not group:
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_NOT_FOUND", "❌ Promo group not found"))
        await state.clear()
        return

    group = await update_promo_group(db, group, traffic_discount_percent=value)
    await state.set_state(AdminStates.editing_promo_group_menu)

    await _send_edit_menu_after_update(
        message,
        texts,
        group,
        data.get("language", db_user.language),
        texts.get_text("ADMIN_PROMO_GROUP_UPDATED", "Promo group «{name}» updated.").format(name=group.name),
    )


@admin_required
@error_handler
async def process_edit_group_servers(
    message: types.Message,
    state: FSMContext,
    db_user,
    db: AsyncSession,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", db_user.language))

    try:
        value = _validate_percent(message.text)
    except (ValueError, TypeError):
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_INVALID_PERCENT", "Enter a number from 0 to 100."))
        return

    group = await get_promo_group_by_id(db, data.get("edit_group_id"))
    if not group:
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_NOT_FOUND", "❌ Promo group not found"))
        await state.clear()
        return

    group = await update_promo_group(db, group, server_discount_percent=value)
    await state.set_state(AdminStates.editing_promo_group_menu)

    await _send_edit_menu_after_update(
        message,
        texts,
        group,
        data.get("language", db_user.language),
        texts.get_text("ADMIN_PROMO_GROUP_UPDATED", "Promo group «{name}» updated.").format(name=group.name),
    )


@admin_required
@error_handler
async def process_edit_group_devices(
    message: types.Message,
    state: FSMContext,
    db_user,
    db: AsyncSession,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", db_user.language))

    try:
        devices_discount = _validate_percent(message.text)
    except (ValueError, TypeError):
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_INVALID_PERCENT", "Enter a number from 0 to 100."))
        return

    group = await get_promo_group_by_id(db, data.get("edit_group_id"))
    if not group:
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_NOT_FOUND", "❌ Promo group not found"))
        await state.clear()
        return

    group = await update_promo_group(db, group, device_discount_percent=devices_discount)
    await state.set_state(AdminStates.editing_promo_group_menu)

    await _send_edit_menu_after_update(
        message,
        texts,
        group,
        data.get("language", db_user.language),
        texts.get_text("ADMIN_PROMO_GROUP_UPDATED", "Promo group «{name}» updated.").format(name=group.name),
    )


@admin_required
@error_handler
async def process_edit_group_period_discounts(
    message: types.Message,
    state: FSMContext,
    db_user,
    db: AsyncSession,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", db_user.language))

    try:
        period_discounts = _parse_period_discounts_input(message.text)
    except ValueError:
        await message.answer(
            texts.get_text(
                "ADMIN_PROMO_GROUP_INVALID_PERIOD_DISCOUNTS",
                "Enter period:discount pairs separated by comma, e.g. 30:10, 90:15, or 0.",
            )
        )
        return

    group = await get_promo_group_by_id(db, data.get("edit_group_id"))
    if not group:
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_NOT_FOUND", "❌ Promo group not found"))
        await state.clear()
        return

    group = await update_promo_group(db, group, period_discounts=period_discounts)
    await state.set_state(AdminStates.editing_promo_group_menu)

    await _send_edit_menu_after_update(
        message,
        texts,
        group,
        data.get("language", db_user.language),
        texts.get_text("ADMIN_PROMO_GROUP_UPDATED", "Promo group «{name}» updated.").format(name=group.name),
    )


@admin_required
@error_handler
async def process_edit_group_auto_assign(
    message: types.Message,
    state: FSMContext,
    db_user,
    db: AsyncSession,
):
    data = await state.get_data()
    texts = get_texts(data.get("language", db_user.language))

    try:
        auto_assign_kopeks = _parse_auto_assign_threshold_input(message.text)
    except ValueError:
        await message.answer(
            texts.get_text(
                "ADMIN_PROMO_GROUP_INVALID_AUTO_ASSIGN",
                "Enter a non-negative number or 0 to disable.",
            )
        )
        return

    group = await get_promo_group_by_id(db, data.get("edit_group_id"))
    if not group:
        await message.answer(texts.get_text("ADMIN_PROMO_GROUP_NOT_FOUND", "❌ Promo group not found"))
        await state.clear()
        return

    group = await update_promo_group(
        db,
        group,
        auto_assign_total_spent_kopeks=auto_assign_kopeks,
    )
    await state.set_state(AdminStates.editing_promo_group_menu)

    await _send_edit_menu_after_update(
        message,
        texts,
        group,
        data.get("language", db_user.language),
        texts.get_text("ADMIN_PROMO_GROUP_UPDATED", "Promo group «{name}» updated.").format(name=group.name),
    )


@admin_required
@error_handler
async def show_promo_group_members(
    callback: types.CallbackQuery,
    db_user,
    db: AsyncSession,
):
    parts = callback.data.split("_")
    group_id = int(parts[3])
    page = int(parts[-1])
    limit = 10
    offset = (page - 1) * limit

    group = await get_promo_group_by_id(db, group_id)
    if not group:
        texts = get_texts("en")
        await callback.answer(texts.get_text("ADMIN_PROMO_GROUP_NOT_FOUND", "❌ Promo group not found"), show_alert=True)
        return

    texts = get_texts(db_user.language)
    members = await get_promo_group_members(db, group_id, offset=offset, limit=limit)
    total_members = await count_promo_group_members(db, group_id)
    total_pages = max(1, (total_members + limit - 1) // limit)

    title = texts.get_text(
        "ADMIN_PROMO_GROUP_MEMBERS_TITLE",
        "👥 Group members {name}",
    ).format(name=group.name)

    if not members:
        body = texts.get_text("ADMIN_PROMO_GROUP_MEMBERS_EMPTY", "No members in this group yet.")
    else:
        lines = []
        for index, user in enumerate(members, start=offset + 1):
            username = f"@{user.username}" if user.username else "—"
            user_link = f'<a href="tg://user?id={user.telegram_id}">{user.full_name}</a>'
            lines.append(
                f"{index}. {user_link} (ID {user.id}, {username}, TG {user.telegram_id})"
            )
        body = "\n".join(lines)

    keyboard = []
    if total_pages > 1:
        pagination = get_admin_pagination_keyboard(
            page,
            total_pages,
            f"promo_group_members_{group_id}",
            f"promo_group_manage_{group_id}",
            db_user.language,
        )
        keyboard.extend(pagination.inline_keyboard)

    keyboard.append(
        [types.InlineKeyboardButton(text=texts.BACK, callback_data=f"promo_group_manage_{group_id}")]
    )

    await callback.message.edit_text(
        f"{title}\n\n{body}",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_required
@error_handler
async def request_delete_promo_group(
    callback: types.CallbackQuery,
    db_user,
    db: AsyncSession,
):
    group = await _get_group_or_alert(callback, db)
    if not group:
        return

    texts = get_texts(db_user.language)

    if group.is_default:
        await callback.answer(
            texts.get_text("ADMIN_PROMO_GROUP_DELETE_FORBIDDEN", "Default promo group cannot be deleted."),
            show_alert=True,
        )
        return

    confirm_text = texts.get_text(
        "ADMIN_PROMO_GROUP_DELETE_CONFIRM",
        "Delete promo group «{name}»? All users will be moved to the default group.",
    ).format(name=group.name)

    await callback.message.edit_text(
        confirm_text,
        reply_markup=get_confirmation_keyboard(
            confirm_action=f"promo_group_delete_confirm_{group.id}",
            cancel_action=f"promo_group_manage_{group.id}",
            language=db_user.language,
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def delete_promo_group_confirmed(
    callback: types.CallbackQuery,
    db_user,
    db: AsyncSession,
):
    group = await _get_group_or_alert(callback, db)
    if not group:
        return

    texts = get_texts(db_user.language)

    success = await delete_promo_group(db, group)
    if not success:
        await callback.answer(
            texts.get_text("ADMIN_PROMO_GROUP_DELETE_FORBIDDEN", "Default promo group cannot be deleted."),
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        texts.get_text("ADMIN_PROMO_GROUP_DELETED", "Promo group «{name}» deleted.").format(name=group.name),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_promo_groups")]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def toggle_promo_group_addon_discounts(
    callback: types.CallbackQuery,
    db_user,
    db: AsyncSession,
):
    group = await _get_group_or_alert(callback, db)
    if not group:
        return

    texts = get_texts(db_user.language)

    new_value = not getattr(group, "apply_discounts_to_addons", True)

    group = await update_promo_group(
        db,
        group,
        apply_discounts_to_addons=new_value,
    )

    status_text = texts.get_text(
        "ADMIN_PROMO_GROUP_ADDON_DISCOUNT_UPDATED_ENABLED"
        if new_value
        else "ADMIN_PROMO_GROUP_ADDON_DISCOUNT_UPDATED_DISABLED",
        "🧩 Add-on purchase discounts {status}.",
    ).format(status="<b>enabled</b>" if new_value else "<b>disabled</b>")

    await _send_edit_menu_after_update(
        callback.message,
        texts,
        group,
        db_user.language,
        status_text,
    )

    await callback.answer()


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_promo_groups_menu, F.data == "admin_promo_groups")
    dp.callback_query.register(show_promo_group_details, F.data.startswith("promo_group_manage_"))
    dp.callback_query.register(start_create_promo_group, F.data == "admin_promo_group_create")
    dp.callback_query.register(
        prompt_edit_promo_group_field,
        F.data.startswith("promo_group_edit_field_"),
    )
    dp.callback_query.register(
        toggle_promo_group_addon_discounts,
        F.data.startswith("promo_group_toggle_addons_"),
    )
    dp.callback_query.register(
        start_edit_promo_group,
        F.data.regexp(r"^promo_group_edit_\d+$"),
    )
    dp.callback_query.register(
        request_delete_promo_group,
        F.data.startswith("promo_group_delete_")
        & ~F.data.startswith("promo_group_delete_confirm_"),
    )
    dp.callback_query.register(
        delete_promo_group_confirmed,
        F.data.startswith("promo_group_delete_confirm_"),
    )
    dp.callback_query.register(
        show_promo_group_members,
        F.data.regexp(r"^promo_group_members_\d+_page_\d+$"),
    )

    dp.message.register(process_create_group_name, AdminStates.creating_promo_group_name)
    dp.message.register(
        process_create_group_priority,
        AdminStates.creating_promo_group_priority,
    )
    dp.message.register(
        process_create_group_traffic,
        AdminStates.creating_promo_group_traffic_discount,
    )
    dp.message.register(
        process_create_group_servers,
        AdminStates.creating_promo_group_server_discount,
    )
    dp.message.register(
        process_create_group_devices,
        AdminStates.creating_promo_group_device_discount,
    )
    dp.message.register(
        process_create_group_period_discounts,
        AdminStates.creating_promo_group_period_discount,
    )
    dp.message.register(
        process_create_group_auto_assign,
        AdminStates.creating_promo_group_auto_assign,
    )

    dp.message.register(process_edit_group_name, AdminStates.editing_promo_group_name)
    dp.message.register(
        process_edit_group_priority,
        AdminStates.editing_promo_group_priority,
    )
    dp.message.register(
        process_edit_group_traffic,
        AdminStates.editing_promo_group_traffic_discount,
    )
    dp.message.register(
        process_edit_group_servers,
        AdminStates.editing_promo_group_server_discount,
    )
    dp.message.register(
        process_edit_group_devices,
        AdminStates.editing_promo_group_device_discount,
    )
    dp.message.register(
        process_edit_group_period_discounts,
        AdminStates.editing_promo_group_period_discount,
    )
    dp.message.register(
        process_edit_group_auto_assign,
        AdminStates.editing_promo_group_auto_assign,
    )
