from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Set, Tuple

from aiogram import Dispatcher, F, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database.crud.discount_offer import list_discount_offers, upsert_discount_offer
from app.database.crud.server_squad import (
    get_all_server_squads,
    get_server_squad_by_id,
    get_server_squad_by_uuid,
)
from app.database.crud.promo_offer_template import (
    ensure_default_templates,
    get_promo_offer_template_by_id,
    list_promo_offer_templates,
    update_promo_offer_template,
)
from app.database.crud.promo_offer_log import list_promo_offer_logs
from app.database.crud.user import get_user_by_id, get_users_for_promo_segment
from app.database.models import (
    DiscountOffer,
    PromoOfferLog,
    PromoOfferTemplate,
    SubscriptionTemporaryAccess,
    User,
    UserStatus,
)
from app.keyboards.inline import get_happ_download_button_row
from app.localization.texts import get_texts
from app.services.user_service import UserService
from app.states import AdminStates
from app.utils.decorators import admin_required, error_handler
from app.utils.subscription_utils import get_display_subscription_link
from app.utils.formatters import format_datetime, format_duration
from app.utils.miniapp_buttons import build_miniapp_or_callback_button

logger = logging.getLogger(__name__)


SQUADS_PAGE_LIMIT = 10
PROMO_OFFER_LOGS_PAGE_LIMIT = 10
PROMO_OFFER_USER_PAGE_LIMIT = 10


async def _safe_delete_message(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest as exc:
        if "message to delete not found" not in str(exc).lower():
            logger.debug("Could not delete admin message: %s", exc)
    except TelegramForbiddenError:
        logger.debug("Insufficient permissions to delete admin message")


async def _safe_delete_message_by_id(bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramBadRequest as exc:
        if "message to delete not found" not in str(exc).lower():
            logger.debug(
                "Could not delete admin message (%s, %s): %s",
                chat_id,
                message_id,
                exc,
            )
    except TelegramForbiddenError:
        logger.debug(
            "Insufficient permissions to delete admin message (%s, %s)",
            chat_id,
            message_id,
        )


async def _clear_promo_offer_search_prompt(state: FSMContext, bot) -> None:
    data = await state.get_data()
    prompt_info = data.get("promo_offer_user_search_prompt") or {}
    chat_id = prompt_info.get("chat_id")
    message_id = prompt_info.get("message_id")

    if chat_id and message_id:
        await _safe_delete_message_by_id(bot, chat_id, message_id)

    if prompt_info:
        await state.update_data(promo_offer_user_search_prompt=None)


ACTION_LABEL_KEYS = {
    "claimed": "ADMIN_PROMO_OFFER_LOGS_ACTION_CLAIMED",
    "consumed": "ADMIN_PROMO_OFFER_LOGS_ACTION_CONSUMED",
    "disabled": "ADMIN_PROMO_OFFER_LOGS_ACTION_DISABLED",
}


REASON_LABEL_KEYS = {
    "manual_charge": "ADMIN_PROMO_OFFER_LOGS_REASON_MANUAL",
    "autopay_consumed": "ADMIN_PROMO_OFFER_LOGS_REASON_AUTOPAY",
    "offer_expired": "ADMIN_PROMO_OFFER_LOGS_REASON_EXPIRED",
    "test_access_expired": "ADMIN_PROMO_OFFER_LOGS_REASON_TEST_EXPIRED",
}


OFFER_TYPE_CONFIG = {
    "test_access": {
        "icon": "🧪",
        "label_key": "ADMIN_PROMO_OFFER_TEST_ACCESS",
        "default_label": "Test servers",
        "allowed_segments": [
            ("paid_active", "ADMIN_SEGMENT_PAID_ACTIVE"),
            ("trial_active", "ADMIN_SEGMENT_TRIAL_ACTIVE"),
        ],
        "effect_type": "test_access",
    },
    "extend_discount": {
        "icon": "💎",
        "label_key": "ADMIN_PROMO_OFFER_EXTEND",
        "default_label": "Extension discount",
        "allowed_segments": [
            ("paid_active", "ADMIN_SEGMENT_PAID_ACTIVE"),
        ],
        "effect_type": "percent_discount",
    },
    "purchase_discount": {
        "icon": "🎯",
        "label_key": "ADMIN_PROMO_OFFER_PURCHASE",
        "default_label": "Purchase discount",
        "allowed_segments": [
            ("paid_expired", "ADMIN_SEGMENT_PAID_EXPIRED"),
            ("trial_expired", "ADMIN_SEGMENT_TRIAL_EXPIRED"),
            ("trial_active", "ADMIN_SEGMENT_TRIAL_ACTIVE"),
        ],
        "effect_type": "percent_discount",
    },
}

def _render_template_text(
    template: PromoOfferTemplate,
    language: str,
    *,
    server_name: Optional[str] = None,
) -> str:
    replacements = {
        "discount_percent": template.discount_percent,
        "valid_hours": template.valid_hours,
        "test_duration_hours": template.test_duration_hours or 0,
        "active_discount_hours": template.active_discount_hours or template.valid_hours,
    }

    if server_name is not None:
        replacements.setdefault("server_name", server_name)
    else:
        # Prevent KeyError if template expects server_name
        replacements.setdefault("server_name", "???")
    try:
        return template.message_text.format(**replacements)
    except Exception:  # pragma: no cover - fallback for invalid placeholders
        logger.warning("Could not format promo offer text %s", template.id)
        return template.message_text


async def _resolve_template_squad(
    db: AsyncSession,
    template: PromoOfferTemplate,
) -> Tuple[Optional[str], Optional[str]]:
    if template.offer_type != "test_access":
        return None, None

    squads = template.test_squad_uuids or []
    if not squads:
        return None, None

    squad_uuid = str(squads[0])
    server = await get_server_squad_by_uuid(db, squad_uuid)
    server_name = server.display_name if server else None
    return squad_uuid, server_name


def _build_templates_keyboard(templates: Sequence[PromoOfferTemplate], language: str) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    rows: List[List[InlineKeyboardButton]] = []
    for template in templates:
        config = OFFER_TYPE_CONFIG.get(template.offer_type, {})
        icon = config.get("icon", "📨")
        label = texts.t(config.get("label_key", ""), config.get("default_label", template.offer_type))
        rows.append([
            InlineKeyboardButton(
                text=f"{icon} {label}",
                callback_data=f"promo_offer_{template.id}",
            )
        ])
    rows.append([
        InlineKeyboardButton(
            text=texts.t("ADMIN_PROMO_OFFER_LOGS", "📜 Operations log"),
            callback_data="promo_offer_logs_page_1",
        )
    ])
    rows.append([InlineKeyboardButton(text=texts.BACK, callback_data="admin_submenu_communications")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_offer_detail_keyboard(template: PromoOfferTemplate, language: str) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    config = OFFER_TYPE_CONFIG.get(template.offer_type, {})
    rows: List[List[InlineKeyboardButton]] = []

    rows.append([
        InlineKeyboardButton(text=texts.t("ADMIN_BTN_TEXT", "✏️ Text"), callback_data=f"promo_offer_edit_message_{template.id}"),
        InlineKeyboardButton(text=texts.t("ADMIN_BTN_BUTTON", "🪄 Button"), callback_data=f"promo_offer_edit_button_{template.id}"),
    ])
    rows.append([
        InlineKeyboardButton(text=texts.t("ADMIN_BTN_TERM", "⏱️ Term"), callback_data=f"promo_offer_edit_valid_{template.id}"),
    ])

    if template.offer_type != "test_access":
        rows[-1].append(InlineKeyboardButton(text="📉 %", callback_data=f"promo_offer_edit_discount_{template.id}"))
        rows.append([
            InlineKeyboardButton(text=texts.t("ADMIN_BTN_ACTIVE", "⌛ Active"), callback_data=f"promo_offer_edit_active_{template.id}"),
        ])
    else:
        rows.append([
            InlineKeyboardButton(text=texts.t("ADMIN_BTN_DURATION", "⏳ Duration"), callback_data=f"promo_offer_edit_duration_{template.id}"),
            InlineKeyboardButton(text=texts.t("ADMIN_BTN_SQUADS", "🌍 Squads"), callback_data=f"promo_offer_edit_squads_{template.id}"),
        ])

    rows.append([
        InlineKeyboardButton(text=texts.t("ADMIN_BTN_SEND", "📬 Send"), callback_data=f"promo_offer_send_menu_{template.id}"),
    ])
    rows.append([
        InlineKeyboardButton(text=texts.BACK, callback_data="admin_promo_offers"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _format_offer_remaining(offer, texts) -> str:
    if not offer.expires_at:
        return texts.t("ADMIN_PROMO_OFFER_SEND_USER_OFFER_NO_EXPIRY", "no expiry")

    remaining_seconds = int((offer.expires_at - datetime.utcnow()).total_seconds())
    if remaining_seconds <= 0:
        return texts.t("ADMIN_PROMO_OFFER_SEND_USER_OFFER_TIME_LEFT_EXPIRED", "expired")

    return format_duration(remaining_seconds)


def _extract_offer_active_hours(offer, template: Optional[PromoOfferTemplate]) -> Optional[int]:
    extra = offer.extra_data or {}
    active_hours = extra.get("active_discount_hours")
    if active_hours:
        try:
            return int(active_hours)
        except (TypeError, ValueError):
            pass

    if template and template.active_discount_hours:
        return template.active_discount_hours

    if template and template.offer_type == "test_access" and template.test_duration_hours:
        return template.test_duration_hours

    return None


_TEMPLATE_ID_PATTERN = re.compile(r"promo_template_(?P<template_id>\d+)$")


def _extract_template_id_from_notification(notification_type: Optional[str]) -> Optional[int]:
    if not notification_type:
        return None

    match = _TEMPLATE_ID_PATTERN.match(notification_type)
    if not match:
        return None

    try:
        return int(match.group("template_id"))
    except (TypeError, ValueError):
        return None


def _format_promo_offer_log_entry(
    entry: PromoOfferLog,
    index: int,
    texts,
) -> str:
    timestamp = entry.created_at.strftime("%d.%m.%Y %H:%M") if entry.created_at else "-"
    action_key = ACTION_LABEL_KEYS.get(entry.action, "")
    action_label = texts.get(action_key, entry.action.title())
    lines = [f"{index}. <b>{timestamp}</b> — {action_label}"]

    user = entry.user
    if user:
        username = f"@{user.username}" if user.username else f"ID{user.telegram_id}"
        label = f"{username} (#{user.id})"
    elif entry.user_id:
        label = f"ID{entry.user_id}"
    else:
        label = texts.get("ADMIN_PROMO_OFFER_LOGS_UNKNOWN_USER", "Unknown user")

    lines.append(texts.get("ADMIN_PROMO_OFFER_LOGS_USER", "👤 {user}").format(user=html.escape(label)))

    if entry.percent:
        lines.append(
            texts.get("ADMIN_PROMO_OFFER_LOGS_PERCENT", "📉 Discount: {percent}%").format(
                percent=entry.percent
            )
        )

    effect_type = (entry.effect_type or "").lower()
    if effect_type:
        if effect_type == "test_access":
            effect_label = texts.get("ADMIN_PROMO_OFFER_LOGS_EFFECT_TEST", "🧪 Test access")
        else:
            effect_label = texts.get("ADMIN_PROMO_OFFER_LOGS_EFFECT_DISCOUNT", "💸 Discount")
        lines.append(effect_label)

    if entry.source:
        lines.append(
            texts.get("ADMIN_PROMO_OFFER_LOGS_SOURCE", "🏷 Source: {source}").format(
                source=html.escape(entry.source)
            )
        )

    details: Dict[str, object] = entry.details if isinstance(entry.details, dict) else {}
    reason_key = details.get("reason")
    if reason_key:
        reason_label = texts.get(REASON_LABEL_KEYS.get(reason_key, ""), "")
        if not reason_label:
            reason_label = texts.get(
                "ADMIN_PROMO_OFFER_LOGS_REASON_GENERIC",
                "ℹ️ Action: {reason}",
            ).format(reason=html.escape(str(reason_key)))
        lines.append(reason_label)

    description = details.get("description")
    if description:
        lines.append(
            texts.get("ADMIN_PROMO_OFFER_LOGS_DESCRIPTION", "📝 {description}").format(
                description=html.escape(str(description))
            )
        )

    amount = details.get("amount_kopeks")
    if isinstance(amount, int):
        lines.append(
            texts.get("ADMIN_PROMO_OFFER_LOGS_AMOUNT", "💰 Amount: {amount}").format(
                amount=texts.format_price(amount)
            )
        )

    squad_uuid = details.get("squad_uuid")
    if squad_uuid:
        lines.append(
            texts.get("ADMIN_PROMO_OFFER_LOGS_SQUAD", "🌍 Squad: {squad}").format(
                squad=html.escape(str(squad_uuid))
            )
        )

    new_squads = details.get("new_squads")
    if isinstance(new_squads, (list, tuple)):
        filtered = [html.escape(str(item)) for item in new_squads if item]
        if filtered:
            lines.append(
                texts.get("ADMIN_PROMO_OFFER_LOGS_NEW_SQUADS", "🌍 New squads: {squads}").format(
                    squads=", ".join(filtered)
                )
            )

    return "\n".join(lines)


def _build_logs_keyboard(page: int, total_pages: int, language: str) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    rows: List[List[InlineKeyboardButton]] = []
    if total_pages > 1:
        nav_row: List[InlineKeyboardButton] = []
        if page > 1:
            nav_row.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"promo_offer_logs_page_{page - 1}",
                )
            )
        nav_row.append(
            InlineKeyboardButton(
                text=f"{page}/{total_pages}",
                callback_data=f"promo_offer_logs_page_{page}",
            )
        )
        if page < total_pages:
            nav_row.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"promo_offer_logs_page_{page + 1}",
                )
            )
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text=texts.BACK, callback_data="admin_promo_offers")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


SEGMENT_LABELS = {
    "ADMIN_SEGMENT_PAID_ACTIVE": "🟢 Active paid",
    "ADMIN_SEGMENT_TRIAL_ACTIVE": "🎁 Active trials",
    "ADMIN_SEGMENT_PAID_EXPIRED": "🔴 Expired paid",
    "ADMIN_SEGMENT_TRIAL_EXPIRED": "🥶 Expired trials",
}


def _build_send_keyboard(template: PromoOfferTemplate, language: str) -> InlineKeyboardMarkup:
    config = OFFER_TYPE_CONFIG.get(template.offer_type, {})
    segments = config.get("allowed_segments", [])
    texts = get_texts(language)
    rows: List[List[InlineKeyboardButton]] = []

    for segment, label_key in segments:
        label = texts.t(label_key, SEGMENT_LABELS.get(label_key, label_key))
        rows.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"promo_offer_send_{template.id}_{segment}",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text=texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER",
                    "👤 Send to user",
                ),
                callback_data=f"promo_offer_send_user_{template.id}_page_1",
            )
        ]
    )

    rows.append([InlineKeyboardButton(text=texts.BACK, callback_data=f"promo_offer_{template.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_user_button_label(user: User) -> str:
    status_emoji_map = {
        UserStatus.ACTIVE.value: "✅",
        UserStatus.BLOCKED.value: "🚫",
        UserStatus.DELETED.value: "🗑️",
    }
    status_emoji = status_emoji_map.get(getattr(user, "status", None), "❓")

    subscription = getattr(user, "subscription", None)
    if subscription:
        if subscription.is_trial:
            subscription_emoji = "🎁"
        elif subscription.is_active:
            subscription_emoji = "💎"
        else:
            subscription_emoji = "⏰"
    else:
        subscription_emoji = "❌"

    name = (user.full_name or user.username or f"ID {user.telegram_id or user.id}").strip()
    if not name:
        name = f"ID {user.telegram_id or user.id}"

    if len(name) > 20:
        name = name[:17] + "..."

    parts = [status_emoji, subscription_emoji, name, f"🆔 {user.telegram_id}" if user.telegram_id else f"#{user.id}"]

    balance = getattr(user, "balance_kopeks", 0)
    if balance:
        parts.append(f"💰 {settings.format_price(balance)}")

    return " ".join(parts)


async def _render_send_user_list(
    *,
    bot,
    chat_id: int,
    message_id: int,
    template_id: int,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    page: int = 1,
    query: Optional[str] = None,
) -> None:
    user_service = UserService()
    texts = get_texts(db_user.language)

    limit = PROMO_OFFER_USER_PAGE_LIMIT
    if query:
        result = await user_service.search_users(db, query, page=page, limit=limit)
    else:
        result = await user_service.get_users_page(db, page=page, limit=limit)

    total_pages = max(1, int(result.get("total_pages") or 1))
    current_page = max(1, min(total_pages, int(result.get("current_page") or page or 1)))

    if current_page != page:
        if query:
            result = await user_service.search_users(db, query, page=current_page, limit=limit)
        else:
            result = await user_service.get_users_page(db, page=current_page, limit=limit)

    users: Sequence[User] = result.get("users", [])

    lines = [
        texts.t("ADMIN_PROMO_OFFER_SEND_USER_TITLE", "👤 <b>Send to user</b>"),
        "",
        texts.t(
            "ADMIN_PROMO_OFFER_SEND_USER_HINT",
            "Select a user to send promo offer.",
        ),
    ]

    if query:
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_SEARCH_QUERY",
                "🔍 Search: <b>{query}</b>",
            ).format(query=html.escape(query))
        )

    if not users:
        lines.append("")
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_EMPTY",
                "No matching users found. Change your search query.",
            )
        )

    keyboard_rows: List[List[InlineKeyboardButton]] = []
    for user in users:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text=_build_user_button_label(user),
                    callback_data=f"promo_offer_send_user_select_{template_id}_{user.id}",
                )
            ]
        )

    if total_pages > 1:
        nav_row: List[InlineKeyboardButton] = []
        if current_page > 1:
            nav_row.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"promo_offer_send_user_{template_id}_page_{current_page - 1}",
                )
            )
        nav_row.append(
            InlineKeyboardButton(
                text=f"{current_page}/{total_pages}",
                callback_data=f"promo_offer_send_user_{template_id}_page_{current_page}",
            )
        )
        if current_page < total_pages:
            nav_row.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"promo_offer_send_user_{template_id}_page_{current_page + 1}",
                )
            )
        keyboard_rows.append(nav_row)

    keyboard_rows.append(
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_PROMO_OFFER_SEND_USER_SEARCH", "🔍 Search"),
                callback_data=f"promo_offer_send_user_search_{template_id}",
            )
        ]
    )

    if query:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text=texts.t("ADMIN_PROMO_OFFER_SEND_USER_RESET", "❌ Reset search"),
                    callback_data=f"promo_offer_send_user_reset_{template_id}",
                )
            ]
        )

    keyboard_rows.append(
        [
            InlineKeyboardButton(
                text=texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_BACK_TO_SEGMENTS",
                    "↩️ To category selection",
                ),
                callback_data=f"promo_offer_send_menu_{template_id}",
            )
        ]
    )
    keyboard_rows.append([InlineKeyboardButton(text=texts.BACK, callback_data=f"promo_offer_{template_id}")])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    text = "\n".join(lines)

    current_message_id = message_id
    try:
        await bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=markup,
            parse_mode="HTML",
        )
    except TelegramBadRequest as exc:
        error_text = str(exc).lower()
        if "message is not modified" in error_text:
            await bot.edit_message_reply_markup(
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=markup,
            )
        else:
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=markup,
                parse_mode="HTML",
            )
            current_message_id = sent_message.message_id

    await state.update_data(
        promo_offer_user_message={"chat_id": chat_id, "message_id": current_message_id},
        promo_offer_user_filter={
            "template_id": template_id,
            "page": current_page,
            "query": query,
        },
    )


def _describe_offer(
    template: PromoOfferTemplate,
    language: str,
    *,
    server_name: Optional[str] = None,
    server_uuid: Optional[str] = None,
) -> str:
    texts = get_texts(language)
    config = OFFER_TYPE_CONFIG.get(template.offer_type, {})
    label = texts.t(config.get("label_key", ""), config.get("default_label", template.offer_type))
    icon = config.get("icon", "📨")

    lines = [f"{icon} <b>{template.name}</b>", ""]
    lines.append(texts.t("ADMIN_PROMO_OFFER_TYPE", "Type: {label}").format(label=label))
    lines.append(texts.t("ADMIN_PROMO_OFFER_VALID", "Validity: {hours} h").format(hours=template.valid_hours))

    if template.offer_type != "test_access":
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_DISCOUNT",
                "Extra discount: {percent}% (stacks with promo group)",
            ).format(percent=template.discount_percent)
        )
        stack_note = texts.t(
            "ADMIN_PROMO_OFFER_STACKABLE_NOTE",
            "Discount applies once and adds to promo group.",
        )
        if stack_note:
            lines.append(stack_note)
        active_hours = template.active_discount_hours or 0
        if active_hours > 0:
            lines.append(
                texts.t(
                    "ADMIN_PROMO_OFFER_ACTIVE_DURATION",
                    "Discount active for {hours} h after activation.",
                ).format(hours=active_hours)
            )
    else:
        duration = template.test_duration_hours or 0
        lines.append(texts.t("ADMIN_PROMO_OFFER_TEST_DURATION", "Access: {hours} h").format(hours=duration))
        squads = template.test_squad_uuids or []
        if server_name:
            lines.append(
                texts.t("ADMIN_PROMO_OFFER_TEST_SQUAD_NAME", "Server: {name}").format(name=server_name)
            )
        elif squads:
            lines.append(
                texts.t("ADMIN_PROMO_OFFER_TEST_SQUADS", "Squads: {squads}").format(
                    squads=", ".join(str(item) for item in squads)
                )
            )
        elif server_uuid:
            lines.append(
                texts.t("ADMIN_PROMO_OFFER_TEST_SQUADS", "Squads: {squads}").format(squads=server_uuid)
            )
        else:
            lines.append(texts.t("ADMIN_PROMO_OFFER_TEST_SQUADS_EMPTY", "Squads: not specified"))

    allowed_segments = config.get("allowed_segments", [])
    if allowed_segments:
        segment_labels = [texts.t(label_key, SEGMENT_LABELS.get(label_key, label_key)) for _, label_key in allowed_segments]
        lines.append("")
        lines.append(texts.t("ADMIN_PROMO_OFFER_ALLOWED", "Allowed categories:"))
        lines.extend(segment_labels)

    lines.append("")
    lines.append(texts.t("ADMIN_PROMO_OFFER_PREVIEW", "Preview:"))
    lines.append(
        _render_template_text(
            template,
            language,
            server_name=server_name,
        )
    )

    return "\n".join(lines)


@admin_required
@error_handler
async def show_promo_offers_menu(callback: CallbackQuery, db_user: User, db: AsyncSession):
    await ensure_default_templates(db, created_by=db_user.id)
    templates = await list_promo_offer_templates(db)
    texts = get_texts(db_user.language)
    header = texts.t("ADMIN_PROMO_OFFERS_TITLE", "🎯 <b>Promo offers</b>\n\nSelect an offer to configure:")
    await callback.message.edit_text(
        header,
        reply_markup=_build_templates_keyboard(templates, db_user.language),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_required
@error_handler
async def show_promo_offer_details(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    try:
        template_id = int(callback.data.split("_")[-1])
    except (ValueError, AttributeError):
        await callback.answer(texts.t("ADMIN_ERROR_INVALID_ID", "❌ Invalid identifier"), show_alert=True)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    await state.update_data(selected_promo_offer=template.id)
    squad_uuid, squad_name = await _resolve_template_squad(db, template)
    description = _describe_offer(
        template,
        db_user.language,
        server_name=squad_name,
        server_uuid=squad_uuid,
    )
    await callback.message.edit_text(
        description,
        reply_markup=_build_offer_detail_keyboard(template, db_user.language),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_required
@error_handler
async def show_promo_offer_logs(callback: CallbackQuery, db_user: User, db: AsyncSession):
    try:
        if "_page_" in callback.data:
            page = int(callback.data.split("_page_")[-1])
        else:
            page = 1
    except (ValueError, AttributeError):
        page = 1

    if page < 1:
        page = 1

    limit = PROMO_OFFER_LOGS_PAGE_LIMIT
    offset = (page - 1) * limit
    logs, total = await list_promo_offer_logs(db, offset=offset, limit=limit)
    total_pages = max(1, (total + limit - 1) // limit)

    if page > total_pages and total > 0:
        page = total_pages
        offset = (page - 1) * limit
        logs, _ = await list_promo_offer_logs(db, offset=offset, limit=limit)

    texts = get_texts(db_user.language)
    header = texts.t(
        "ADMIN_PROMO_OFFER_LOGS_TITLE",
        "📜 <b>Promo offer operations log</b>",
    )

    if logs:
        message_lines = [
            header,
            texts.get(
                "ADMIN_PROMO_OFFER_LOGS_PAGINATION",
                "Page {page}/{total}",
            ).format(page=page, total=total_pages),
            "",
        ]
        for index, entry in enumerate(logs, start=offset + 1):
            message_lines.append(_format_promo_offer_log_entry(entry, index, texts))
            message_lines.append("")
        message_text = "\n".join(message_lines).rstrip()
    else:
        message_text = "\n".join(
            [
                header,
                "",
                texts.get(
                    "ADMIN_PROMO_OFFER_LOGS_EMPTY_BODY",
                    "No entries yet.",
                ),
            ]
        )

    keyboard = _build_logs_keyboard(page, total_pages, db_user.language)
    await callback.message.edit_text(
        message_text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


async def _prompt_edit(callback: CallbackQuery, state: FSMContext, template_id: int, prompt: str, new_state):
    await state.update_data(
        selected_promo_offer=template_id,
        promo_edit_message_id=callback.message.message_id,
        promo_edit_chat_id=callback.message.chat.id,
    )
    await callback.message.edit_text(prompt)
    await state.set_state(new_state)
    await callback.answer()


@admin_required
@error_handler
async def prompt_edit_message(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    texts = get_texts(db_user.language)
    prompt = texts.t("ADMIN_PROMO_OFFER_PROMPT_MESSAGE", "Enter new offer text:")
    await _prompt_edit(callback, state, template_id, prompt, AdminStates.editing_promo_offer_message)


@admin_required
@error_handler
async def prompt_edit_button(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    texts = get_texts(db_user.language)
    prompt = texts.t("ADMIN_PROMO_OFFER_PROMPT_BUTTON", "Enter new button text:")
    await _prompt_edit(callback, state, template_id, prompt, AdminStates.editing_promo_offer_button)


@admin_required
@error_handler
async def prompt_edit_valid(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    texts = get_texts(db_user.language)
    prompt = texts.t("ADMIN_PROMO_OFFER_PROMPT_VALID", "Enter validity period (in hours):")
    await _prompt_edit(callback, state, template_id, prompt, AdminStates.editing_promo_offer_valid_hours)


@admin_required
@error_handler
async def prompt_edit_discount(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    texts = get_texts(db_user.language)
    prompt = texts.t("ADMIN_PROMO_OFFER_PROMPT_DISCOUNT", "Enter discount percentage:")
    await _prompt_edit(callback, state, template_id, prompt, AdminStates.editing_promo_offer_discount)


@admin_required
@error_handler
async def prompt_edit_active_duration(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    texts = get_texts(db_user.language)
    prompt = texts.t(
        "ADMIN_PROMO_OFFER_PROMPT_ACTIVE_DURATION",
        "Enter activated discount duration (in hours):",
    )
    await _prompt_edit(
        callback,
        state,
        template_id,
        prompt,
        AdminStates.editing_promo_offer_active_duration,
    )


@admin_required
@error_handler
async def prompt_edit_duration(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    texts = get_texts(db_user.language)
    prompt = texts.t("ADMIN_PROMO_OFFER_PROMPT_DURATION", "Enter test access duration (in hours):")
    await _prompt_edit(callback, state, template_id, prompt, AdminStates.editing_promo_offer_test_duration)


@admin_required
@error_handler
async def prompt_edit_squads(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    template_id = int(callback.data.split("_")[-1])
    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    await state.update_data(
        selected_promo_offer=template.id,
        promo_edit_message_id=callback.message.message_id,
        promo_edit_chat_id=callback.message.chat.id,
    )

    await _render_squad_selection(callback, template, db, db_user.language)
    await callback.answer()


async def _render_squad_selection(
    callback: CallbackQuery,
    template: PromoOfferTemplate,
    db: AsyncSession,
    language: str,
    page: int = 1,
):
    texts = get_texts(language)

    squads, total_count = await get_all_server_squads(
        db,
        available_only=False,
        page=page,
        limit=SQUADS_PAGE_LIMIT,
    )

    if total_count == 0:
        await callback.message.edit_text(
            texts.t("ADMIN_PROMO_OFFER_NO_SQUADS_AVAILABLE", "❌ No available servers found."),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=texts.BACK, callback_data=f"promo_offer_squad_back_{template.id}")]]
            ),
        )
        return

    selected_uuid = None
    if template.test_squad_uuids:
        selected_uuid = str(template.test_squad_uuids[0])

    selected_server_name = None
    if selected_uuid:
        selected_server = next((srv for srv in squads if srv.squad_uuid == selected_uuid), None)
        if not selected_server:
            selected_server = await get_server_squad_by_uuid(db, selected_uuid)
        if selected_server:
            selected_server_name = selected_server.display_name

    header = texts.t("ADMIN_PROMO_OFFER_SELECT_SQUAD_TITLE", "🌍 <b>Select squad</b>")
    if selected_server_name:
        current = texts.t(
            "ADMIN_PROMO_OFFER_SELECTED_SQUAD",
            "Current squad: {name}",
        ).format(name=selected_server_name)
    elif selected_uuid:
        current = texts.t(
            "ADMIN_PROMO_OFFER_SELECTED_SQUAD_UUID",
            "Current squad: {uuid}",
        ).format(uuid=selected_uuid)
    else:
        current = texts.t(
            "ADMIN_PROMO_OFFER_SELECTED_SQUAD_EMPTY",
            "Current squad: not selected",
        )

    hint = texts.t(
        "ADMIN_PROMO_OFFER_SELECT_SQUAD_HINT",
        "Select server for test access from the list below.",
    )

    total_pages = (total_count + SQUADS_PAGE_LIMIT - 1) // SQUADS_PAGE_LIMIT or 1
    page = max(1, min(page, total_pages))

    lines = [header, "", current, "", hint]
    if total_pages > 1:
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SELECT_SQUAD_PAGE",
                "Page {page}/{total}",
            ).format(page=page, total=total_pages)
        )

    text = "\n".join(lines)

    keyboard_rows: List[List[InlineKeyboardButton]] = []
    for server in squads:
        emoji = "✅" if server.squad_uuid == selected_uuid else ("⚪" if server.is_available else "🔒")
        label = f"{emoji} {server.display_name}"
        keyboard_rows.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"promo_offer_select_squad_{template.id}_{server.id}_{page}",
            )
        ])

    if total_pages > 1:
        nav_row: List[InlineKeyboardButton] = []
        if page > 1:
            nav_row.append(
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"promo_offer_squad_page_{template.id}_{page - 1}",
                )
            )
        if page < total_pages:
            nav_row.append(
                InlineKeyboardButton(
                    text="➡️",
                    callback_data=f"promo_offer_squad_page_{template.id}_{page + 1}",
                )
            )
        if nav_row:
            keyboard_rows.append(nav_row)

    action_row = [
        InlineKeyboardButton(
            text=texts.t("ADMIN_PROMO_OFFER_SELECT_SQUAD_CLEAR", "🗑 Clear"),
            callback_data=f"promo_offer_clear_squad_{template.id}_{page}",
        ),
        InlineKeyboardButton(
            text=texts.t("ADMIN_PROMO_OFFER_SELECT_SQUAD_BACK", "↩️ Back"),
            callback_data=f"promo_offer_squad_back_{template.id}",
        ),
    ]
    keyboard_rows.append(action_row)

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML",
    )


async def _render_offer_details(
    callback: CallbackQuery,
    template: PromoOfferTemplate,
    language: str,
    db: AsyncSession,
):
    squad_uuid, squad_name = await _resolve_template_squad(db, template)
    description = _describe_offer(
        template,
        language,
        server_name=squad_name,
        server_uuid=squad_uuid,
    )
    await callback.message.edit_text(
        description,
        reply_markup=_build_offer_detail_keyboard(template, language),
        parse_mode="HTML",
    )


async def _handle_edit_field(
    message: Message,
    state: FSMContext,
    db: AsyncSession,
    db_user: User,
    field: str,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    template_id = data.get("selected_promo_offer")
    if not template_id:
        await _safe_delete_message(message)
        await message.answer(texts.t("ADMIN_PROMO_OFFER_CANNOT_DETERMINE", "❌ Could not determine offer. Try again."))
        await state.clear()
        return

    template = await get_promo_offer_template_by_id(db, int(template_id))
    if not template:
        await _safe_delete_message(message)
        await message.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found."))
        await state.clear()
        return

    value = message.text.strip()
    try:
        if field == "message_text":
            await update_promo_offer_template(db, template, message_text=value)
        elif field == "button_text":
            await update_promo_offer_template(db, template, button_text=value)
        elif field == "valid_hours":
            hours = max(1, int(value))
            await update_promo_offer_template(db, template, valid_hours=hours)
        elif field == "discount_percent":
            percent = max(0, min(100, int(value)))
            await update_promo_offer_template(db, template, discount_percent=percent)
        elif field == "active_discount_hours":
            hours = max(1, int(value))
            await update_promo_offer_template(db, template, active_discount_hours=hours)
        elif field == "test_duration_hours":
            hours = max(1, int(value))
            await update_promo_offer_template(db, template, test_duration_hours=hours)
        elif field == "test_squad_uuids":
            if value.lower() in {"clear"}:
                squads: List[str] = []
            else:
                squads = [item for item in re.split(r"[\s,]+", value) if item]
            await update_promo_offer_template(db, template, test_squad_uuids=squads)
        else:
            raise ValueError("Unsupported field")
    except ValueError:
        await _safe_delete_message(message)
        await message.answer(texts.t("ADMIN_ERROR_INVALID_VALUE", "❌ Invalid value. Try again."))
        return

    edit_message_id = data.get("promo_edit_message_id")
    edit_chat_id = data.get("promo_edit_chat_id", message.chat.id)

    await state.clear()
    updated_template = await get_promo_offer_template_by_id(db, template.id)
    if not updated_template:
        await _safe_delete_message(message)
        await message.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND_AFTER_UPDATE", "❌ Offer not found after update."))
        return

    squad_uuid, squad_name = await _resolve_template_squad(db, updated_template)
    description = _describe_offer(
        updated_template,
        db_user.language,
        server_name=squad_name,
        server_uuid=squad_uuid,
    )
    reply_markup = _build_offer_detail_keyboard(updated_template, db_user.language)

    if edit_message_id:
        try:
            await message.bot.edit_message_text(
                description,
                chat_id=edit_chat_id,
                message_id=edit_message_id,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
        except TelegramBadRequest as exc:
            error_text = str(exc).lower()
            if "there is no text in the message to edit" in error_text:
                logger.debug("Promo message without text, forwarding updated version")
                try:
                    await message.bot.delete_message(chat_id=edit_chat_id, message_id=edit_message_id)
                except TelegramBadRequest:
                    logger.debug("Could not delete promo message without text")
            else:
                logger.warning("Could not update promo edit message: %s", exc)
            await message.answer(description, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await message.answer(description, reply_markup=reply_markup, parse_mode="HTML")

    await _safe_delete_message(message)


@admin_required
@error_handler
async def show_send_segments(callback: CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    template_id = int(callback.data.split("_")[-1])
    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    await callback.message.edit_reply_markup(
        reply_markup=_build_send_keyboard(template, db_user.language)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_send_user_list(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    try:
        prefix = "promo_offer_send_user_"
        if not callback.data.startswith(prefix):
            raise ValueError("invalid prefix")
        payload = callback.data[len(prefix):]
        template_id_str, page_label, page_str = payload.split("_", 2)
        if page_label != "page":
            raise ValueError("invalid payload")
        template_id = int(template_id_str)
        page = int(page_str)
    except (ValueError, AttributeError):
        await callback.answer(texts.t("ADMIN_ERROR_INVALID_DATA", "❌ Invalid data"), show_alert=True)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    if page < 1:
        page = 1

    await state.set_state(AdminStates.selecting_promo_offer_user)
    data = await state.get_data()
    filter_data = data.get("promo_offer_user_filter") or {}
    query = filter_data.get("query") if filter_data.get("template_id") == template_id else None

    await _render_send_user_list(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        template_id=template_id,
        db_user=db_user,
        db=db,
        state=state,
        page=page,
        query=query,
    )
    await callback.answer()


@admin_required
@error_handler
async def prompt_send_user_search(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    try:
        template_id = int(callback.data.split("_")[-1])
    except (ValueError, AttributeError):
        await callback.answer(texts.t("ADMIN_ERROR_INVALID_DATA", "❌ Invalid data"), show_alert=True)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    await _clear_promo_offer_search_prompt(state, callback.bot)
    await state.set_state(AdminStates.searching_promo_offer_user)
    await state.update_data(promo_offer_user_search_template=template_id)

    texts = get_texts(db_user.language)
    prompt_message = await callback.message.answer(
        texts.t(
            "ADMIN_PROMO_OFFER_SEND_USER_SEARCH_PROMPT",
            "Enter name, username or user ID to search:",
        )
    )
    await state.update_data(
        promo_offer_user_search_prompt={
            "chat_id": prompt_message.chat.id,
            "message_id": prompt_message.message_id,
        }
    )
    await callback.answer()


@admin_required
@error_handler
async def reset_send_user_search(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    try:
        template_id = int(callback.data.split("_")[-1])
    except (ValueError, AttributeError):
        await callback.answer(texts.t("ADMIN_ERROR_INVALID_DATA", "❌ Invalid data"), show_alert=True)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    await _clear_promo_offer_search_prompt(state, callback.bot)
    await state.set_state(AdminStates.selecting_promo_offer_user)
    await _render_send_user_list(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        template_id=template_id,
        db_user=db_user,
        db=db,
        state=state,
        page=1,
        query=None,
    )
    await callback.answer()


@admin_required
@error_handler
async def back_to_user_list(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    try:
        template_id = int(callback.data.split("_")[-1])
    except (ValueError, AttributeError):
        await callback.answer(texts.t("ADMIN_ERROR_INVALID_DATA", "❌ Invalid data"), show_alert=True)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    await _clear_promo_offer_search_prompt(state, callback.bot)
    data = await state.get_data()
    filter_data = data.get("promo_offer_user_filter") or {}
    if filter_data.get("template_id") == template_id:
        page = int(filter_data.get("page") or 1)
        query = filter_data.get("query")
    else:
        page = 1
        query = None

    await state.set_state(AdminStates.selecting_promo_offer_user)
    await _render_send_user_list(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        template_id=template_id,
        db_user=db_user,
        db=db,
        state=state,
        page=page,
        query=query,
    )
    await callback.answer()


@admin_required
@error_handler
async def process_send_user_search(
    message: Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    query = (message.text or "").strip()
    if not query:
        await message.answer(texts.t("ADMIN_ERROR_EMPTY_SEARCH", "❌ Enter a valid search query"))
        return

    data = await state.get_data()
    template_id = data.get("promo_offer_user_search_template")
    if not template_id:
        await message.answer(texts.t("ADMIN_PROMO_OFFER_CANNOT_DETERMINE", "❌ Could not determine promo offer"))
        await _safe_delete_message(message)
        return

    try:
        template_id = int(template_id)
    except (TypeError, ValueError):
        await message.answer(texts.t("ADMIN_ERROR_INVALID_SEARCH_DATA", "❌ Invalid search data"))
        await _safe_delete_message(message)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await message.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"))
        await _safe_delete_message(message)
        return

    await _clear_promo_offer_search_prompt(state, message.bot)
    message_info = data.get("promo_offer_user_message") or {}
    chat_id = message_info.get("chat_id")
    message_id = message_info.get("message_id")

    if not chat_id or not message_id:
        placeholder = await message.answer(texts.t("ADMIN_UPDATING_USER_LIST", "⏳ Updating user list..."))
        chat_id = placeholder.chat.id
        message_id = placeholder.message_id

    await _render_send_user_list(
        bot=message.bot,
        chat_id=chat_id,
        message_id=message_id,
        template_id=template_id,
        db_user=db_user,
        db=db,
        state=state,
        page=1,
        query=query,
    )

    await state.set_state(AdminStates.selecting_promo_offer_user)
    await state.update_data(
        promo_offer_user_search_template=None,
        promo_offer_user_search_prompt=None,
    )
    await _safe_delete_message(message)


@admin_required
@error_handler
async def show_selected_user_details(
    callback: CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    texts = get_texts(db_user.language)
    try:
        prefix = "promo_offer_send_user_select_"
        if not callback.data.startswith(prefix):
            raise ValueError("invalid prefix")
        payload = callback.data[len(prefix):]
        template_id_str, user_id_str = payload.split("_", 1)
        template_id = int(template_id_str)
        user_id = int(user_id_str)
    except (ValueError, AttributeError):
        await callback.answer(texts.t("ADMIN_ERROR_INVALID_DATA", "❌ Invalid data"), show_alert=True)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    user = await get_user_by_id(db, user_id)
    if not user:
        await callback.answer(texts.t("ADMIN_USER_NOT_FOUND", "❌ User not found"), show_alert=True)
        return

    texts = get_texts(db_user.language)
    status_map = {
        UserStatus.ACTIVE.value: texts.ADMIN_USER_STATUS_ACTIVE,
        UserStatus.BLOCKED.value: texts.ADMIN_USER_STATUS_BLOCKED,
        UserStatus.DELETED.value: texts.ADMIN_USER_STATUS_DELETED,
    }

    name = html.escape(user.full_name or user.username or str(user.telegram_id or user.id))
    username = html.escape(user.username) if user.username else None
    balance = getattr(user, "balance_kopeks", 0)

    lines = [
        texts.t("ADMIN_PROMO_OFFER_SEND_USER_PROFILE", "👤 <b>{name}</b>").format(name=name),
        texts.t("ADMIN_PROMO_OFFER_SEND_USER_TELEGRAM", "🆔 <code>{telegram_id}</code>").format(
            telegram_id=user.telegram_id or "—"
        ),
    ]

    if username:
        lines.append(texts.t("ADMIN_PROMO_OFFER_SEND_USER_USERNAME", "🔗 @{username}").format(username=username))

    status_label = status_map.get(user.status, texts.ADMIN_USER_STATUS_UNKNOWN)
    lines.append(
        texts.t("ADMIN_PROMO_OFFER_SEND_USER_STATUS", "Status: {status}").format(status=status_label)
    )

    if balance:
        lines.append(
            texts.t("ADMIN_PROMO_OFFER_SEND_USER_BALANCE", "Balance: {amount}").format(
                amount=settings.format_price(balance)
            )
        )

    subscription = getattr(user, "subscription", None)
    if subscription:
        lines.append("")
        lines.append(texts.t("ADMIN_PROMO_OFFER_SEND_USER_SUBSCRIPTION", "💳 <b>Subscription</b>"))
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_SUBSCRIPTION_STATUS",
                "Status: {status}",
            ).format(status=subscription.status_display)
        )
        end_date_text = (
            format_datetime(subscription.end_date)
            if subscription.end_date
            else texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_SUBSCRIPTION_END_UNKNOWN",
                "not specified",
            )
        )
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_SUBSCRIPTION_END",
                "Expires: {date}",
            ).format(date=end_date_text)
        )
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_SUBSCRIPTION_TRAFFIC",
                "Traffic: {used}/{limit} GB",
            ).format(
                used=subscription.traffic_used_gb or 0,
                limit=subscription.traffic_limit_gb or 0,
            )
        )
        connected = subscription.connected_squads or []
        if connected:
            lines.append(
                texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_SUBSCRIPTION_SQUADS",
                    "Connected squads: {count}",
                ).format(count=len(connected))
            )
    else:
        lines.append("")
        lines.append(texts.t("ADMIN_PROMO_OFFER_SEND_USER_NO_SUBSCRIPTION", "💳 No subscription"))

    now = datetime.utcnow()
    percent = 0
    try:
        percent = int(getattr(user, "promo_offer_discount_percent", 0) or 0)
    except (TypeError, ValueError):
        percent = 0
    expires_at = getattr(user, "promo_offer_discount_expires_at", None)
    if percent > 0 and (not expires_at or expires_at > now):
        discount_line = texts.t(
            "ADMIN_PROMO_OFFER_SEND_USER_ACTIVE_DISCOUNT",
            "💸 Active discount: {percent}%",
        ).format(percent=percent)
        if expires_at:
            date_text = format_datetime(expires_at)
            remaining_seconds = int((expires_at - now).total_seconds())
            if remaining_seconds > 0:
                discount_line += texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_ACTIVE_DISCOUNT_LEFT",
                    " (until {date}, {time} left)",
                ).format(date=date_text, time=format_duration(remaining_seconds))
            else:
                discount_line += texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_ACTIVE_DISCOUNT_UNTIL",
                    " (until {date})",
                ).format(date=date_text)
        source = getattr(user, "promo_offer_discount_source", None)
        if source:
            discount_line += texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_ACTIVE_DISCOUNT_SOURCE",
                " — source: {source}",
            ).format(source=html.escape(str(source)))
    else:
        discount_line = texts.t(
            "ADMIN_PROMO_OFFER_SEND_USER_ACTIVE_DISCOUNT_NONE",
            "💸 No active discount",
        )
    lines.append("")
    lines.append(discount_line)

    config = OFFER_TYPE_CONFIG.get(template.offer_type, {})
    offer_label = texts.t(
        config.get("label_key", ""),
        config.get("default_label", template.offer_type),
    )
    lines.append("")
    lines.append(
        texts.t(
            "ADMIN_PROMO_OFFER_SEND_USER_TEMPLATE_HEADER",
            "📨 <b>Selected offer</b>",
        )
    )
    lines.append(
        texts.t(
            "ADMIN_PROMO_OFFER_SEND_USER_TEMPLATE_TYPE",
            "Type: {label}",
        ).format(label=offer_label)
    )
    lines.append(
        texts.t(
            "ADMIN_PROMO_OFFER_SEND_USER_TEMPLATE_VALID",
            "Valid: {hours} h.",
        ).format(hours=template.valid_hours)
    )

    if template.offer_type == "test_access":
        duration_hours = template.test_duration_hours or 0
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_TEMPLATE_TEST_DURATION",
                "Test access: {hours} h.",
            ).format(hours=duration_hours)
        )
    else:
        if template.discount_percent:
            lines.append(
                texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_TEMPLATE_DISCOUNT",
                    "Discount: {percent}%",
                ).format(percent=template.discount_percent)
            )

        active_hours = template.active_discount_hours or 0
        if active_hours:
            lines.append(
                texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_TEMPLATE_ACTIVE_DURATION",
                    "Active for {hours} h. after activation.",
                ).format(hours=active_hours)
            )

    active_offers = await list_discount_offers(db, user_id=user.id, is_active=True)
    if active_offers:
        lines.append("")
        lines.append(texts.t("ADMIN_PROMO_OFFER_SEND_USER_ACTIVE_OFFERS", "📨 Active offers:"))

        template_map: Dict[int, PromoOfferTemplate] = {template.id: template}
        template_ids_to_load: Set[int] = set()

        for offer in active_offers:
            offer_template_id = _extract_template_id_from_notification(offer.notification_type)
            if offer_template_id and offer_template_id not in template_map:
                template_ids_to_load.add(offer_template_id)

        if template_ids_to_load:
            templates_result = await db.execute(
                select(PromoOfferTemplate).where(PromoOfferTemplate.id.in_(template_ids_to_load))
            )
            for offer_template in templates_result.scalars():
                template_map[offer_template.id] = offer_template

        for offer in active_offers[:5]:
            parts: List[str] = []
            if offer.effect_type == "test_access":
                parts.append(texts.t("ADMIN_PROMO_OFFER_SEND_USER_OFFER_TEST", "Test access"))
            if offer.discount_percent:
                parts.append(
                    texts.t(
                        "ADMIN_PROMO_OFFER_SEND_USER_OFFER_PERCENT",
                        "Discount {percent}%",
                    ).format(percent=offer.discount_percent)
                )
            if offer.bonus_amount_kopeks:
                parts.append(
                    texts.t(
                        "ADMIN_PROMO_OFFER_SEND_USER_OFFER_BONUS",
                        "Bonus {amount}",
                    ).format(amount=settings.format_price(offer.bonus_amount_kopeks))
                )
            description = ", ".join(parts) or offer.effect_type
            lines.append(
                texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_OFFER_ITEM_HEADER",
                    "• {description}",
                ).format(description=description)
            )

            expires_text = (
                format_datetime(offer.expires_at)
                if offer.expires_at
                else texts.t("ADMIN_PROMO_OFFER_SEND_USER_OFFER_NO_EXPIRY", "no expiry")
            )
            lines.append(
                texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_OFFER_EXPIRES",
                    "  Expires: {expires}",
                ).format(expires=expires_text)
            )

            status_label = texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_OFFER_STATUS_ACCEPTED",
                "✅ Accepted",
            )
            if not offer.claimed_at:
                status_label = texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_OFFER_STATUS_PENDING",
                    "⏳ Not accepted",
                )
            lines.append(
                texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_OFFER_STATUS",
                    "  Status: {status}",
                ).format(status=status_label)
            )

            time_left = _format_offer_remaining(offer, texts)
            lines.append(
                texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_OFFER_TIME_LEFT",
                    "  Remaining: {time}",
                ).format(time=time_left)
            )

            offer_template = None
            offer_template_id = _extract_template_id_from_notification(offer.notification_type)
            if offer_template_id:
                offer_template = template_map.get(offer_template_id)

            active_hours = _extract_offer_active_hours(offer, offer_template)
            if active_hours:
                lines.append(
                    texts.t(
                        "ADMIN_PROMO_OFFER_SEND_USER_OFFER_ACTIVE_DURATION",
                        "  After activation: {duration}",
                    ).format(duration=format_duration(active_hours * 3600))
                )

            if offer.expires_at and offer.created_at:
                total_seconds = int((offer.expires_at - offer.created_at).total_seconds())
                if total_seconds > 0:
                    lines.append(
                        texts.t(
                            "ADMIN_PROMO_OFFER_SEND_USER_OFFER_TOTAL_DURATION",
                            "  Total duration: {duration}",
                        ).format(duration=format_duration(total_seconds))
                    )

            lines.append("")
        if lines[-1] == "":
            lines.pop()
    else:
        lines.append("")
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_NO_ACTIVE_OFFERS",
                "📨 No active offers",
            )
        )

    stats_stmt = (
        select(
            func.count(DiscountOffer.id),
            func.sum(
                case(
                    (DiscountOffer.claimed_at.isnot(None), 1),
                    else_=0,
                )
            ),
        )
        .where(
            DiscountOffer.user_id == user.id,
            DiscountOffer.notification_type == f"promo_template_{template.id}",
        )
    )
    stats_result = await db.execute(stats_stmt)
    total_offers, accepted_offers = stats_result.one()
    total_offers = int(total_offers or 0)
    accepted_offers = int(accepted_offers or 0)
    pending_offers = max(total_offers - accepted_offers, 0)

    if total_offers > 0:
        lines.append("")
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_OFFER_STATS_HEADER",
                "📊 Offer statistics",
            )
        )
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_OFFER_STATS_TOTAL",
                "Total sent: {count}",
            ).format(count=total_offers)
        )
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_OFFER_STATS_ACCEPTED",
                "Accepted: {count}",
            ).format(count=accepted_offers)
        )
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_OFFER_STATS_PENDING",
                "Not accepted: {count}",
            ).format(count=pending_offers)
        )
        lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_OFFER_STATS_ACTIVE",
                "Active now: {count}",
            ).format(count=len(active_offers))
        )

    if subscription:
        now = datetime.utcnow()
        result = await db.execute(
            select(SubscriptionTemporaryAccess)
            .options(selectinload(SubscriptionTemporaryAccess.offer))
            .where(
                SubscriptionTemporaryAccess.subscription_id == subscription.id,
                SubscriptionTemporaryAccess.is_active == True,  # noqa: E712
                SubscriptionTemporaryAccess.expires_at > now,
            )
            .order_by(SubscriptionTemporaryAccess.expires_at.desc())
        )
        accesses = result.scalars().all()
    else:
        accesses = []

    if accesses:
        lines.append("")
        lines.append(texts.t("ADMIN_PROMO_OFFER_SEND_USER_TEST_ACCESS", "🧪 Active test accesses:"))
        for entry in accesses[:5]:
            squad_label = html.escape(entry.squad_uuid or "—")
            expires_text = (
                format_datetime(entry.expires_at)
                if entry.expires_at
                else texts.t("ADMIN_PROMO_OFFER_SEND_USER_OFFER_NO_EXPIRY", "no expiry")
            )
            lines.append(
                texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_TEST_ACCESS_ITEM",
                    "• {squad} (until {expires})",
                ).format(squad=squad_label, expires=expires_text)
            )

    keyboard_rows = [
        [
            InlineKeyboardButton(
                text=texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_SEND_BUTTON",
                    "📬 Send offer",
                ),
                callback_data=f"promo_offer_send_user_confirm_{template_id}_{user.id}",
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_BACK_TO_LIST",
                    "⬅️ To user list",
                ),
                callback_data=f"promo_offer_send_user_back_{template_id}",
            )
        ],
        [InlineKeyboardButton(text=texts.BACK, callback_data=f"promo_offer_{template_id}")],
    ]

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML",
    )

    await state.set_state(AdminStates.selecting_promo_offer_user)
    await state.update_data(
        promo_offer_selected_user=user.id,
        promo_offer_user_message={
            "chat_id": callback.message.chat.id,
            "message_id": callback.message.message_id,
        },
    )
    await callback.answer()


def _build_connect_button_rows(user: User, texts) -> List[List[InlineKeyboardButton]]:
    subscription = getattr(user, "subscription", None)
    if not subscription:
        return []

    button_text = texts.t("CONNECT_BUTTON", "🔗 Connect")
    subscription_link = get_display_subscription_link(subscription)
    connect_mode = settings.CONNECT_BUTTON_MODE

    def _fallback_button() -> InlineKeyboardButton:
        return InlineKeyboardButton(text=button_text, callback_data="subscription_connect")

    rows: List[List[InlineKeyboardButton]] = []

    if connect_mode == "miniapp_subscription":
        if subscription_link:
            rows.append([
                InlineKeyboardButton(
                    text=button_text,
                    web_app=types.WebAppInfo(url=subscription_link),
                )
            ])
        else:
            rows.append([_fallback_button()])
    elif connect_mode == "miniapp_custom":
        if settings.MINIAPP_CUSTOM_URL:
            rows.append([
                InlineKeyboardButton(
                    text=button_text,
                    web_app=types.WebAppInfo(url=settings.MINIAPP_CUSTOM_URL),
                )
            ])
        else:
            rows.append([_fallback_button()])
    elif connect_mode == "link":
        if subscription_link:
            rows.append([
                InlineKeyboardButton(text=button_text, url=subscription_link)
            ])
        else:
            rows.append([_fallback_button()])
    elif connect_mode == "happ_cryptolink":
        if subscription_link:
            rows.append([
                InlineKeyboardButton(text=button_text, callback_data="open_subscription_link")
            ])
        else:
            rows.append([_fallback_button()])
    else:
        rows.append([_fallback_button()])

    happ_row = get_happ_download_button_row(texts)
    if happ_row:
        rows.append(happ_row)

    return rows


async def _send_offer_to_users(
    bot,
    template: PromoOfferTemplate,
    db_user: User,
    db: AsyncSession,
    users: Sequence[User],
    *,
    squad_name: Optional[str],
    effect_type: str,
) -> Tuple[int, int]:
    from app.database.database import AsyncSessionLocal
    
    sent = 0
    failed = 0

    # Limit concurrent sends
    semaphore = asyncio.Semaphore(20)

    async def send_single_offer(user):
        """Sends a single offer with semaphore limiting"""
        async with semaphore:
            try:
                # Use a separate session for transaction isolation
                async with AsyncSessionLocal() as new_db:
                    offer_record = await upsert_discount_offer(
                        new_db,
                        user_id=user.id,
                        subscription_id=getattr(user, "subscription", None).id if getattr(user, "subscription", None) else None,
                        notification_type=f"promo_template_{template.id}",
                        discount_percent=template.discount_percent,
                        bonus_amount_kopeks=0,
                        valid_hours=template.valid_hours,
                        effect_type=effect_type,
                        extra_data={
                            "template_id": template.id,
                            "offer_type": template.offer_type,
                            "test_duration_hours": template.test_duration_hours,
                            "test_squad_uuids": template.test_squad_uuids,
                            "active_discount_hours": template.active_discount_hours,
                        },
                    )

                    user_texts = get_texts(user.language or db_user.language)
                    keyboard_rows: List[List[InlineKeyboardButton]] = [
                        [
                            build_miniapp_or_callback_button(
                                text=template.button_text,
                                callback_data=f"claim_discount_{offer_record.id}",
                            )
                        ]
                    ]

                    keyboard_rows.append([
                        InlineKeyboardButton(
                            text=user_texts.t("PROMO_OFFER_CLOSE", "❌ Close"),
                            callback_data="promo_offer_close",
                        )
                    ])

                    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

                    message_text = _render_template_text(
                        template,
                        user.language or db_user.language,
                        server_name=squad_name,
                    )
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode="HTML",
                    )
                    return True
            except (TelegramForbiddenError, TelegramBadRequest) as exc:
                logger.warning("Could not send offer to user %s: %s", user.telegram_id, exc)
                return False
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error("Error sending promo offer to user %s: %s", user.telegram_id, exc)
                return False

    # Send offers in batches for efficiency
    batch_size = 100
    for i in range(0, len(users), batch_size):
        batch = users[i:i + batch_size]
        tasks = [send_single_offer(user) for user in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, bool):  # Success or failure
                if result:
                    sent += 1
                else:
                    failed += 1
            elif isinstance(result, Exception):  # Task execution error
                failed += 1

        # Small delay between batches to reduce API load
        await asyncio.sleep(0.1)

    return sent, failed


@admin_required
@error_handler
async def send_offer_to_segment(callback: CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    try:
        prefix = "promo_offer_send_"
        if not callback.data.startswith(prefix):
            raise ValueError("invalid prefix")
        data = callback.data[len(prefix):]
        template_id_str, segment = data.split("_", 1)
        template_id = int(template_id_str)
    except (ValueError, AttributeError):
        await callback.answer(texts.t("ADMIN_ERROR_INVALID_DATA", "❌ Invalid data"), show_alert=True)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    config = OFFER_TYPE_CONFIG.get(template.offer_type, {})
    squad_uuid, squad_name = await _resolve_template_squad(db, template)
    allowed_segments = {seg for seg, _ in config.get("allowed_segments", [])}
    if segment not in allowed_segments:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_SEGMENT_NOT_ALLOWED", "⚠️ Cannot send this offer to selected category"), show_alert=True)
        return

    texts = get_texts(db_user.language)
    await callback.answer(texts.t("ADMIN_PROMO_OFFER_SENDING", "Начинаем рассылку..."), show_alert=True)

    users = await get_users_for_promo_segment(db, segment)
    initial_count = len(users)

    if template.offer_type == "test_access" and squad_uuid:
        filtered_users: List[User] = []
        for user in users:
            subscription = getattr(user, "subscription", None)
            connected = set(subscription.connected_squads or []) if subscription else set()
            if squad_uuid in connected:
                continue
            filtered_users.append(user)
        users = filtered_users

    if not users:
        await callback.message.answer(texts.t("ADMIN_PROMO_OFFER_NO_USERS", "No matching users found."))
        return

    skipped = initial_count - len(users)
    effect_type = config.get("effect_type", "percent_discount")
    sent, failed = await _send_offer_to_users(
        callback.bot,
        template,
        db_user,
        db,
        users,
        squad_name=squad_name,
        effect_type=effect_type,
    )

    summary = texts.t(
        "ADMIN_PROMO_OFFER_RESULT",
        "📬 Broadcast completed\nSent: {sent}\nErrors: {failed}",
    ).format(sent=sent, failed=failed)
    if skipped > 0:
        summary += "\n" + texts.t(
            "ADMIN_PROMO_OFFER_SKIPPED",
            "Skipped: {skipped} (already have access)",
        ).format(skipped=skipped)
    refreshed = await get_promo_offer_template_by_id(db, template.id)
    result_keyboard_rows: List[List[InlineKeyboardButton]] = []

    if refreshed:
        result_keyboard_rows.append([
            InlineKeyboardButton(
                text=texts.t("ADMIN_PROMO_OFFER_BACK_TO_TEMPLATE", "↩️ To offer"),
                callback_data=f"promo_offer_{refreshed.id}",
            )
        ])

    result_keyboard_rows.append([
        InlineKeyboardButton(
            text=texts.t("ADMIN_PROMO_OFFER_BACK_TO_LIST", "⬅️ To promo offers"),
            callback_data="admin_promo_offers",
        )
    ])

    await callback.message.edit_text(
        summary,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=result_keyboard_rows),
        parse_mode="HTML",
    )


@admin_required
@error_handler
async def send_offer_to_user(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    try:
        prefix = "promo_offer_send_user_confirm_"
        if not callback.data.startswith(prefix):
            raise ValueError("invalid prefix")
        payload = callback.data[len(prefix):]
        template_id_str, user_id_str = payload.split("_", 1)
        template_id = int(template_id_str)
        user_id = int(user_id_str)
    except (ValueError, AttributeError):
        await callback.answer(texts.t("ADMIN_ERROR_INVALID_DATA", "❌ Invalid data"), show_alert=True)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    user = await get_user_by_id(db, user_id)
    if not user:
        await callback.answer(texts.t("ADMIN_USER_NOT_FOUND", "❌ User not found"), show_alert=True)
        return

    config = OFFER_TYPE_CONFIG.get(template.offer_type, {})
    squad_uuid, squad_name = await _resolve_template_squad(db, template)
    effect_type = config.get("effect_type", "percent_discount")

    texts = get_texts(db_user.language)
    await callback.answer(texts.t("ADMIN_PROMO_OFFER_SENDING", "Начинаем рассылку..."), show_alert=True)

    users_to_send: List[User] = [user]
    skipped = 0
    if template.offer_type == "test_access" and squad_uuid:
        subscription = getattr(user, "subscription", None)
        connected = set(subscription.connected_squads or []) if subscription else set()
        if squad_uuid in connected:
            users_to_send = []
            skipped = 1

    sent = 0
    failed = 0
    if users_to_send:
        sent, failed = await _send_offer_to_users(
            callback.bot,
            template,
            db_user,
            db,
            users_to_send,
            squad_name=squad_name,
            effect_type=effect_type,
        )

    display_name = html.escape(user.full_name or user.username or str(user.telegram_id or user.id))
    summary_lines = [
        texts.t(
            "ADMIN_PROMO_OFFER_SEND_USER_SUMMARY_TITLE",
            "📬 Sending to user {name}",
        ).format(name=display_name),
        texts.t(
            "ADMIN_PROMO_OFFER_RESULT",
            "📬 Broadcast completed\nSent: {sent}\nErrors: {failed}",
        ).format(sent=sent, failed=failed),
    ]

    if skipped:
        summary_lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_SKIPPED",
                "Skipped: {skipped} (already have access)",
            ).format(skipped=skipped)
        )

    if not users_to_send and not skipped:
        summary_lines.append(
            texts.t(
                "ADMIN_PROMO_OFFER_SEND_USER_EMPTY_RESULT",
                "Sending not performed",
            )
        )

    keyboard_rows = [
        [
            InlineKeyboardButton(
                text=texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_BACK_TO_PROFILE",
                    "👤 To user profile",
                ),
                callback_data=f"promo_offer_send_user_select_{template.id}_{user.id}",
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t(
                    "ADMIN_PROMO_OFFER_SEND_USER_BACK_TO_LIST",
                    "⬅️ To user list",
                ),
                callback_data=f"promo_offer_send_user_back_{template.id}",
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_PROMO_OFFER_BACK_TO_TEMPLATE", "↩️ To offer"),
                callback_data=f"promo_offer_{template.id}",
            )
        ],
    ]

    await callback.message.edit_text(
        "\n".join(summary_lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML",
    )

    await state.set_state(AdminStates.selecting_promo_offer_user)
    await state.update_data(
        promo_offer_selected_user=user.id,
        promo_offer_user_message={
            "chat_id": callback.message.chat.id,
            "message_id": callback.message.message_id,
        },
    )


async def process_edit_message_text(message: Message, state: FSMContext, db: AsyncSession, db_user: User):
    await _handle_edit_field(message, state, db, db_user, "message_text")


async def process_edit_button_text(message: Message, state: FSMContext, db: AsyncSession, db_user: User):
    await _handle_edit_field(message, state, db, db_user, "button_text")


async def process_edit_valid_hours(message: Message, state: FSMContext, db: AsyncSession, db_user: User):
    await _handle_edit_field(message, state, db, db_user, "valid_hours")


async def process_edit_active_duration_hours(message: Message, state: FSMContext, db: AsyncSession, db_user: User):
    await _handle_edit_field(message, state, db, db_user, "active_discount_hours")


async def process_edit_discount_percent(message: Message, state: FSMContext, db: AsyncSession, db_user: User):
    await _handle_edit_field(message, state, db, db_user, "discount_percent")


async def process_edit_test_duration(message: Message, state: FSMContext, db: AsyncSession, db_user: User):
    await _handle_edit_field(message, state, db, db_user, "test_duration_hours")


@admin_required
@error_handler
async def paginate_squad_selection(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    try:
        prefix = "promo_offer_squad_page_"
        if not callback.data.startswith(prefix):
            raise ValueError("invalid prefix")
        payload = callback.data[len(prefix):]
        template_id_str, page_str = payload.split("_", 1)
        template_id = int(template_id_str)
        page = int(page_str)
    except (ValueError, AttributeError):
        await callback.answer(texts.t("ADMIN_ERROR_INVALID_DATA", "❌ Invalid data"), show_alert=True)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    await state.update_data(selected_promo_offer=template.id)
    await _render_squad_selection(callback, template, db, db_user.language, page=page)
    await callback.answer()


@admin_required
@error_handler
async def select_squad_for_template(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    try:
        prefix = "promo_offer_select_squad_"
        if not callback.data.startswith(prefix):
            raise ValueError("invalid prefix")
        payload = callback.data[len(prefix):]
        template_id_str, server_id_str, page_str = payload.split("_", 2)
        template_id = int(template_id_str)
        server_id = int(server_id_str)
        page = int(page_str)
    except (ValueError, AttributeError):
        await callback.answer(texts.t("ADMIN_ERROR_INVALID_DATA", "❌ Invalid data"), show_alert=True)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    server = await get_server_squad_by_id(db, server_id)
    if not server:
        await callback.answer(
            get_texts(db_user.language).t(
                "ADMIN_PROMO_OFFER_SELECT_SQUAD_NOT_FOUND",
                "❌ Server not found",
            ),
            show_alert=True,
        )
        return

    await update_promo_offer_template(db, template, test_squad_uuids=[server.squad_uuid])
    updated = await get_promo_offer_template_by_id(db, template.id)
    if updated:
        await state.update_data(selected_promo_offer=updated.id)

    texts = get_texts(db_user.language)
    await callback.answer(texts.t("ADMIN_PROMO_OFFER_SELECT_SQUAD_UPDATED", "✅ Squad updated"))

    if updated:
        await _render_offer_details(callback, updated, db_user.language, db)
    else:
        await _render_squad_selection(callback, template, db, db_user.language, page=page)


@admin_required
@error_handler
async def clear_squad_for_template(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    try:
        prefix = "promo_offer_clear_squad_"
        if not callback.data.startswith(prefix):
            raise ValueError("invalid prefix")
        payload = callback.data[len(prefix):]
        template_id_str, page_str = payload.split("_", 1)
        template_id = int(template_id_str)
        page = int(page_str)
    except (ValueError, AttributeError):
        await callback.answer(texts.t("ADMIN_ERROR_INVALID_DATA", "❌ Invalid data"), show_alert=True)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    await update_promo_offer_template(db, template, test_squad_uuids=[])
    updated = await get_promo_offer_template_by_id(db, template.id)
    if updated:
        await state.update_data(selected_promo_offer=updated.id)

    texts = get_texts(db_user.language)
    await callback.answer(texts.t("ADMIN_PROMO_OFFER_SELECT_SQUAD_CLEARED", "✅ Squad cleared"))

    if updated:
        await _render_squad_selection(callback, updated, db, db_user.language, page=page)
    else:
        await _render_squad_selection(callback, template, db, db_user.language, page=page)


@admin_required
@error_handler
async def back_to_offer_from_squads(callback: CallbackQuery, db_user: User, db: AsyncSession, state: FSMContext):
    texts = get_texts(db_user.language)
    try:
        template_id = int(callback.data.split("_")[-1])
    except (ValueError, AttributeError):
        await callback.answer(texts.t("ADMIN_ERROR_INVALID_DATA", "❌ Invalid data"), show_alert=True)
        return

    template = await get_promo_offer_template_by_id(db, template_id)
    if not template:
        await callback.answer(texts.t("ADMIN_PROMO_OFFER_NOT_FOUND", "❌ Offer not found"), show_alert=True)
        return

    await state.update_data(selected_promo_offer=template.id)
    await _render_offer_details(callback, template, db_user.language, db)
    await callback.answer()


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_promo_offers_menu, F.data == "admin_promo_offers")
    dp.callback_query.register(prompt_edit_message, F.data.startswith("promo_offer_edit_message_"))
    dp.callback_query.register(prompt_edit_button, F.data.startswith("promo_offer_edit_button_"))
    dp.callback_query.register(prompt_edit_valid, F.data.startswith("promo_offer_edit_valid_"))
    dp.callback_query.register(prompt_edit_discount, F.data.startswith("promo_offer_edit_discount_"))
    dp.callback_query.register(prompt_edit_active_duration, F.data.startswith("promo_offer_edit_active_"))
    dp.callback_query.register(prompt_edit_duration, F.data.startswith("promo_offer_edit_duration_"))
    dp.callback_query.register(prompt_edit_squads, F.data.startswith("promo_offer_edit_squads_"))
    dp.callback_query.register(paginate_squad_selection, F.data.startswith("promo_offer_squad_page_"))
    dp.callback_query.register(select_squad_for_template, F.data.startswith("promo_offer_select_squad_"))
    dp.callback_query.register(clear_squad_for_template, F.data.startswith("promo_offer_clear_squad_"))
    dp.callback_query.register(back_to_offer_from_squads, F.data.startswith("promo_offer_squad_back_"))
    dp.callback_query.register(show_send_user_list, F.data.regexp(r"^promo_offer_send_user_\d+_page_\d+$"))
    dp.callback_query.register(show_selected_user_details, F.data.startswith("promo_offer_send_user_select_"))
    dp.callback_query.register(prompt_send_user_search, F.data.startswith("promo_offer_send_user_search_"))
    dp.callback_query.register(reset_send_user_search, F.data.startswith("promo_offer_send_user_reset_"))
    dp.callback_query.register(back_to_user_list, F.data.startswith("promo_offer_send_user_back_"))
    dp.callback_query.register(show_send_segments, F.data.startswith("promo_offer_send_menu_"))
    dp.callback_query.register(send_offer_to_user, F.data.startswith("promo_offer_send_user_confirm_"))
    dp.callback_query.register(send_offer_to_segment, F.data.startswith("promo_offer_send_"))
    dp.callback_query.register(show_promo_offer_logs, F.data.regexp(r"^promo_offer_logs_page_\d+$"))
    dp.callback_query.register(show_promo_offer_details, F.data.startswith("promo_offer_"))

    dp.message.register(process_edit_message_text, AdminStates.editing_promo_offer_message)
    dp.message.register(process_edit_button_text, AdminStates.editing_promo_offer_button)
    dp.message.register(process_edit_valid_hours, AdminStates.editing_promo_offer_valid_hours)
    dp.message.register(process_edit_active_duration_hours, AdminStates.editing_promo_offer_active_duration)
    dp.message.register(process_edit_discount_percent, AdminStates.editing_promo_offer_discount)
    dp.message.register(process_edit_test_duration, AdminStates.editing_promo_offer_test_duration)
    dp.message.register(process_send_user_search, AdminStates.searching_promo_offer_user)
