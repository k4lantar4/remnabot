import logging
import re
from typing import List

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.campaign import (
    create_campaign,
    delete_campaign,
    get_campaign_by_id,
    get_campaign_by_start_parameter,
    get_campaign_statistics,
    get_campaigns_count,
    get_campaigns_list,
    get_campaigns_overview,
    update_campaign,
)
from app.database.crud.server_squad import get_all_server_squads, get_server_squad_by_id
from app.database.models import User
from app.keyboards.admin import (
    get_admin_campaigns_keyboard,
    get_admin_pagination_keyboard,
    get_campaign_bonus_type_keyboard,
    get_campaign_edit_keyboard,
    get_campaign_management_keyboard,
    get_confirmation_keyboard,
)
from app.localization.texts import get_texts
from app.states import AdminStates
from app.utils.decorators import admin_required, error_handler

logger = logging.getLogger(__name__)

_CAMPAIGN_PARAM_REGEX = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
_CAMPAIGNS_PAGE_SIZE = 5


def _format_campaign_summary(campaign, texts) -> str:
    status = texts.t("ADMIN_CAMPAIGN_STATUS_ACTIVE", "🟢 Active") if campaign.is_active else texts.t("ADMIN_CAMPAIGN_STATUS_INACTIVE", "⚪️ Disabled")

    if campaign.is_balance_bonus:
        bonus_text = texts.format_price(campaign.balance_bonus_kopeks)
        bonus_info = texts.t("ADMIN_CAMPAIGN_BALANCE_BONUS", "💰 Balance bonus: <b>{amount}</b>").format(amount=bonus_text)
    else:
        traffic_text = texts.format_traffic(campaign.subscription_traffic_gb or 0)
        device_limit = campaign.subscription_device_limit
        if device_limit is None:
            device_limit = settings.DEFAULT_DEVICE_LIMIT
        bonus_info = texts.t(
            "ADMIN_CAMPAIGN_SUBSCRIPTION_BONUS",
            "📱 Subscription: <b>{days} d.</b>\n"
            "🌐 Traffic: <b>{traffic}</b>\n"
            "📱 Devices: <b>{devices}</b>"
        ).format(
            days=campaign.subscription_duration_days or 0,
            traffic=traffic_text,
            devices=device_limit,
        )

    return texts.t(
        "ADMIN_CAMPAIGN_SUMMARY",
        "<b>{name}</b>\n"
        "Start parameter: <code>{param}</code>\n"
        "Status: {status}\n"
        "{bonus_info}\n"
    ).format(
        name=campaign.name,
        param=campaign.start_parameter,
        status=status,
        bonus_info=bonus_info,
    )


async def _get_bot_deep_link(
    callback: types.CallbackQuery, start_parameter: str
) -> str:
    bot = await callback.bot.get_me()
    return f"https://t.me/{bot.username}?start={start_parameter}"


async def _get_bot_deep_link_from_message(
    message: types.Message, start_parameter: str
) -> str:
    bot = await message.bot.get_me()
    return f"https://t.me/{bot.username}?start={start_parameter}"


def _build_campaign_servers_keyboard(
    servers,
    selected_uuids: List[str],
    texts,
    *,
    toggle_prefix: str = "campaign_toggle_server_",
    save_callback: str = "campaign_servers_save",
    back_callback: str = "admin_campaigns",
) -> types.InlineKeyboardMarkup:
    keyboard: List[List[types.InlineKeyboardButton]] = []

    for server in servers[:20]:
        is_selected = server.squad_uuid in selected_uuids
        emoji = "✅" if is_selected else ("⚪" if server.is_available else "🔒")
        text = f"{emoji} {server.display_name}"
        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=text, callback_data=f"{toggle_prefix}{server.id}"
                )
            ]
        )

    keyboard.append(
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_BTN_SAVE", "✅ Save"), callback_data=save_callback
            ),
            types.InlineKeyboardButton(
                text=texts.BACK, callback_data=back_callback
            ),
        ]
    )

    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


async def _render_campaign_edit_menu(
    bot: Bot,
    chat_id: int,
    message_id: int,
    campaign,
    language: str,
    *,
    use_caption: bool = False,
):
    texts = get_texts(language)
    text = texts.t(
        "ADMIN_CAMPAIGN_EDIT_MENU",
        "✏️ <b>Edit campaign</b>\n\n{summary}\nSelect what to change:"
    ).format(summary=_format_campaign_summary(campaign, texts))

    edit_kwargs = dict(
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=get_campaign_edit_keyboard(
            campaign.id,
            is_balance_bonus=campaign.is_balance_bonus,
            language=language,
        ),
        parse_mode="HTML",
    )

    if use_caption:
        await bot.edit_message_caption(
            caption=text,
            **edit_kwargs,
        )
    else:
        await bot.edit_message_text(
            text=text,
            **edit_kwargs,
        )


@admin_required
@error_handler
async def show_campaigns_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    overview = await get_campaigns_overview(db)

    text = texts.t(
        "ADMIN_CAMPAIGNS_MENU",
        "📣 <b>Advertising Campaigns</b>\n\n"
        "Total campaigns: <b>{total}</b>\n"
        "Active: <b>{active}</b> | Disabled: <b>{inactive}</b>\n"
        "Registrations: <b>{registrations}</b>\n"
        "Balance issued: <b>{balance}</b>\n"
        "Subscriptions issued: <b>{subscriptions}</b>"
    ).format(
        total=overview['total'],
        active=overview['active'],
        inactive=overview['inactive'],
        registrations=overview['registrations'],
        balance=texts.format_price(overview['balance_total']),
        subscriptions=overview['subscription_total']
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_admin_campaigns_keyboard(db_user.language),
    )
    await callback.answer()


@admin_required
@error_handler
async def show_campaigns_overall_stats(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    overview = await get_campaigns_overview(db)

    text = texts.t(
        "ADMIN_CAMPAIGNS_OVERALL_STATS",
        "📊 <b>Overall campaign statistics</b>\n\n"
        "Total campaigns: <b>{total}</b>\n"
        "Active: <b>{active}</b>, disabled: <b>{inactive}</b>\n"
        "Total registrations: <b>{registrations}</b>\n"
        "Total balance issued: <b>{balance}</b>\n"
        "Subscriptions issued: <b>{subscriptions}</b>"
    ).format(
        total=overview['total'],
        active=overview['active'],
        inactive=overview['inactive'],
        registrations=overview['registrations'],
        balance=texts.format_price(overview['balance_total']),
        subscriptions=overview['subscription_total']
    )

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.BACK, callback_data="admin_campaigns"
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def show_campaigns_list(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)

    page = 1
    if callback.data.startswith("admin_campaigns_list_page_"):
        try:
            page = int(callback.data.split("_")[-1])
        except ValueError:
            page = 1

    offset = (page - 1) * _CAMPAIGNS_PAGE_SIZE
    campaigns = await get_campaigns_list(
        db,
        offset=offset,
        limit=_CAMPAIGNS_PAGE_SIZE,
    )
    total = await get_campaigns_count(db)
    total_pages = max(1, (total + _CAMPAIGNS_PAGE_SIZE - 1) // _CAMPAIGNS_PAGE_SIZE)

    if not campaigns:
        await callback.message.edit_text(
            texts.t("ADMIN_CAMPAIGNS_NOT_FOUND", "❌ Advertising campaigns not found."),
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.t("ADMIN_BTN_CREATE", "➕ Create"), callback_data="admin_campaigns_create"
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text=texts.BACK, callback_data="admin_campaigns"
                        )
                    ],
                ]
            ),
        )
        await callback.answer()
        return

    text_lines = [texts.t("ADMIN_CAMPAIGNS_LIST_HEADER", "📋 <b>Campaign list</b>") + "\n"]

    for campaign in campaigns:
        registrations = len(campaign.registrations or [])
        total_balance = sum(
            r.balance_bonus_kopeks or 0 for r in campaign.registrations or []
        )
        status = "🟢" if campaign.is_active else "⚪"
        line = (
            f"{status} <b>{campaign.name}</b> — <code>{campaign.start_parameter}</code>\n"
        )
        line += texts.t(
            "ADMIN_CAMPAIGNS_LIST_ITEM_INFO",
            "   Registrations: {registrations}, balance: {balance}"
        ).format(registrations=registrations, balance=texts.format_price(total_balance))
        if campaign.is_subscription_bonus:
            line += texts.t("ADMIN_CAMPAIGNS_LIST_SUBSCRIPTION", ", subscription: {days} d.").format(
                days=campaign.subscription_duration_days or 0
            )
        else:
            line += texts.t("ADMIN_CAMPAIGNS_LIST_BALANCE", ", bonus: balance")
        text_lines.append(line)

    keyboard_rows = [
        [
            types.InlineKeyboardButton(
                text=f"🔍 {campaign.name}",
                callback_data=f"admin_campaign_manage_{campaign.id}",
            )
        ]
        for campaign in campaigns
    ]

    pagination = get_admin_pagination_keyboard(
        current_page=page,
        total_pages=total_pages,
        callback_prefix="admin_campaigns_list",
        back_callback="admin_campaigns",
        language=db_user.language,
    )

    keyboard_rows.extend(pagination.inline_keyboard)

    await callback.message.edit_text(
        "\n".join(text_lines),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
    )
    await callback.answer()


@admin_required
@error_handler
async def show_campaign_detail(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)

    if not campaign:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    stats = await get_campaign_statistics(db, campaign_id)
    deep_link = await _get_bot_deep_link(callback, campaign.start_parameter)

    text = [texts.t("ADMIN_CAMPAIGN_MANAGE_HEADER", "📣 <b>Campaign Management</b>") + "\n"]
    text.append(_format_campaign_summary(campaign, texts))
    text.append(texts.t("ADMIN_CAMPAIGN_LINK", "🔗 Link: <code>{link}</code>").format(link=deep_link))
    text.append("\n" + texts.t("ADMIN_CAMPAIGN_STATS_HEADER", "📊 <b>Statistics</b>"))
    text.append(texts.t("ADMIN_CAMPAIGN_STATS_REGISTRATIONS", "• Registrations: <b>{count}</b>").format(count=stats['registrations']))
    text.append(texts.t("ADMIN_CAMPAIGN_STATS_BALANCE", "• Balance issued: <b>{amount}</b>").format(
        amount=texts.format_price(stats['balance_issued'])
    ))
    text.append(texts.t("ADMIN_CAMPAIGN_STATS_SUBSCRIPTIONS", "• Subscriptions issued: <b>{count}</b>").format(
        count=stats['subscription_issued']
    ))
    text.append(texts.t("ADMIN_CAMPAIGN_STATS_REVENUE", "• Revenue: <b>{amount}</b>").format(
        amount=texts.format_price(stats['total_revenue_kopeks'])
    ))
    text.append(texts.t(
        "ADMIN_CAMPAIGN_STATS_TRIAL",
        "• Got trial: <b>{total}</b> (active: {active})"
    ).format(total=stats['trial_users_count'], active=stats['active_trials_count']))
    text.append(texts.t(
        "ADMIN_CAMPAIGN_STATS_CONVERSIONS",
        "• Payment conversions: <b>{conversions}</b> / users with payments: {paid}"
    ).format(conversions=stats['conversion_count'], paid=stats['paid_users_count']))
    text.append(texts.t(
        "ADMIN_CAMPAIGN_STATS_CONVERSION_RATE",
        "• Payment conversion rate: <b>{rate:.1f}%</b>"
    ).format(rate=stats['conversion_rate']))
    text.append(texts.t(
        "ADMIN_CAMPAIGN_STATS_TRIAL_CONVERSION",
        "• Trial conversion rate: <b>{rate:.1f}%</b>"
    ).format(rate=stats['trial_conversion_rate']))
    text.append(texts.t(
        "ADMIN_CAMPAIGN_STATS_AVG_REVENUE",
        "• Avg revenue per user: <b>{amount}</b>"
    ).format(amount=texts.format_price(stats['avg_revenue_per_user_kopeks'])))
    text.append(texts.t(
        "ADMIN_CAMPAIGN_STATS_AVG_FIRST_PAYMENT",
        "• Avg first payment: <b>{amount}</b>"
    ).format(amount=texts.format_price(stats['avg_first_payment_kopeks'])))
    if stats["last_registration"]:
        text.append(texts.t(
            "ADMIN_CAMPAIGN_STATS_LAST_REG",
            "• Last: {date}"
        ).format(date=stats['last_registration'].strftime('%d.%m.%Y %H:%M')))

    await callback.message.edit_text(
        "\n".join(text),
        reply_markup=get_campaign_management_keyboard(
            campaign.id, campaign.is_active, db_user.language
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def show_campaign_edit_menu(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)

    if not campaign:
        await state.clear()
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    await state.clear()

    use_caption = bool(callback.message.caption) and not bool(callback.message.text)

    await _render_campaign_edit_menu(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        campaign,
        db_user.language,
        use_caption=use_caption,
    )
    await callback.answer()


@admin_required
@error_handler
async def start_edit_campaign_name(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminStates.editing_campaign_name)
    is_caption = bool(callback.message.caption) and not bool(callback.message.text)
    await state.update_data(
        editing_campaign_id=campaign_id,
        campaign_edit_message_id=callback.message.message_id,
        campaign_edit_message_is_caption=is_caption,
    )

    await callback.message.edit_text(
        texts.t(
            "ADMIN_CAMPAIGN_EDIT_NAME_PROMPT",
            "✏️ <b>Change campaign name</b>\n\n"
            "Current name: <b>{name}</b>\n"
            "Enter new name (3-100 characters):"
        ).format(name=campaign.name),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"),
                        callback_data=f"admin_campaign_edit_{campaign_id}",
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def process_edit_campaign_name(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    campaign_id = data.get("editing_campaign_id")
    if not campaign_id:
        await message.answer(texts.t("ADMIN_SESSION_EXPIRED", "❌ Edit session expired. Try again."))
        await state.clear()
        return

    new_name = message.text.strip()
    if len(new_name) < 3 or len(new_name) > 100:
        await message.answer(
            texts.t("ADMIN_CAMPAIGN_NAME_LENGTH", "❌ Name must be 3-100 characters. Try again.")
        )
        return

    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await message.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"))
        await state.clear()
        return

    await update_campaign(db, campaign, name=new_name)
    await state.clear()

    await message.answer(texts.t("ADMIN_CAMPAIGN_NAME_UPDATED", "✅ Name updated."))

    edit_message_id = data.get("campaign_edit_message_id")
    edit_message_is_caption = data.get("campaign_edit_message_is_caption", False)
    if edit_message_id:
        await _render_campaign_edit_menu(
            message.bot,
            message.chat.id,
            edit_message_id,
            campaign,
            db_user.language,
            use_caption=edit_message_is_caption,
        )


@admin_required
@error_handler
async def start_edit_campaign_start_parameter(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminStates.editing_campaign_start)
    is_caption = bool(callback.message.caption) and not bool(callback.message.text)
    await state.update_data(
        editing_campaign_id=campaign_id,
        campaign_edit_message_id=callback.message.message_id,
        campaign_edit_message_is_caption=is_caption,
    )

    await callback.message.edit_text(
        texts.t(
            "ADMIN_CAMPAIGN_EDIT_START_PROMPT",
            "🔗 <b>Change start parameter</b>\n\n"
            "Current parameter: <code>{param}</code>\n"
            "Enter new parameter (Latin letters, numbers, - or _, 3-32 characters):"
        ).format(param=campaign.start_parameter),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"),
                        callback_data=f"admin_campaign_edit_{campaign_id}",
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def process_edit_campaign_start_parameter(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    campaign_id = data.get("editing_campaign_id")
    if not campaign_id:
        await message.answer(texts.t("ADMIN_SESSION_EXPIRED", "❌ Edit session expired. Try again."))
        await state.clear()
        return

    new_param = message.text.strip()
    if not _CAMPAIGN_PARAM_REGEX.match(new_param):
        await message.answer(
            texts.t("ADMIN_CAMPAIGN_PARAM_INVALID", "❌ Only Latin letters, numbers, - and _ allowed. Length 3-32 characters.")
        )
        return

    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await message.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"))
        await state.clear()
        return

    existing = await get_campaign_by_start_parameter(db, new_param)
    if existing and existing.id != campaign_id:
        await message.answer(texts.t("ADMIN_CAMPAIGN_PARAM_EXISTS", "❌ This parameter is already in use. Enter another."))
        return

    await update_campaign(db, campaign, start_parameter=new_param)
    await state.clear()

    await message.answer(texts.t("ADMIN_CAMPAIGN_PARAM_UPDATED", "✅ Start parameter updated."))

    edit_message_id = data.get("campaign_edit_message_id")
    edit_message_is_caption = data.get("campaign_edit_message_is_caption", False)
    if edit_message_id:
        await _render_campaign_edit_menu(
            message.bot,
            message.chat.id,
            edit_message_id,
            campaign,
            db_user.language,
            use_caption=edit_message_is_caption,
        )


@admin_required
@error_handler
async def start_edit_campaign_balance_bonus(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    if not campaign.is_balance_bonus:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_DIFFERENT_BONUS", "❌ Campaign has different bonus type"), show_alert=True)
        return

    await state.clear()
    await state.set_state(AdminStates.editing_campaign_balance)
    is_caption = bool(callback.message.caption) and not bool(callback.message.text)
    await state.update_data(
        editing_campaign_id=campaign_id,
        campaign_edit_message_id=callback.message.message_id,
        campaign_edit_message_is_caption=is_caption,
    )

    await callback.message.edit_text(
        texts.t(
            "ADMIN_CAMPAIGN_EDIT_BALANCE_PROMPT",
            "💰 <b>Change balance bonus</b>\n\n"
            "Current bonus: <b>{amount}</b>\n"
            "Enter new amount in rubles (e.g. 100 or 99.5):"
        ).format(amount=texts.format_price(campaign.balance_bonus_kopeks)),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"),
                        callback_data=f"admin_campaign_edit_{campaign_id}",
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def process_edit_campaign_balance_bonus(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    campaign_id = data.get("editing_campaign_id")
    if not campaign_id:
        await message.answer(texts.t("ADMIN_SESSION_EXPIRED", "❌ Edit session expired. Try again."))
        await state.clear()
        return

    try:
        amount_rubles = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(texts.t("ADMIN_CAMPAIGN_INVALID_AMOUNT", "❌ Enter a valid amount (e.g. 100 or 99.5)"))
        return

    if amount_rubles <= 0:
        await message.answer(texts.t("ADMIN_CAMPAIGN_AMOUNT_POSITIVE", "❌ Amount must be greater than zero"))
        return

    amount_kopeks = int(round(amount_rubles * 100))

    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await message.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"))
        await state.clear()
        return

    if not campaign.is_balance_bonus:
        await message.answer(texts.t("ADMIN_CAMPAIGN_DIFFERENT_BONUS", "❌ Campaign has different bonus type"))
        await state.clear()
        return

    await update_campaign(db, campaign, balance_bonus_kopeks=amount_kopeks)
    await state.clear()

    await message.answer(texts.t("ADMIN_CAMPAIGN_BONUS_UPDATED", "✅ Bonus updated."))

    edit_message_id = data.get("campaign_edit_message_id")
    edit_message_is_caption = data.get("campaign_edit_message_is_caption", False)
    if edit_message_id:
        await _render_campaign_edit_menu(
            message.bot,
            message.chat.id,
            edit_message_id,
            campaign,
            db_user.language,
            use_caption=edit_message_is_caption,
        )


async def _ensure_subscription_campaign(message_or_callback, campaign, texts) -> bool:
    if campaign.is_balance_bonus:
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.answer(
                texts.t("ADMIN_CAMPAIGN_BALANCE_ONLY", "❌ This campaign only supports balance bonus"),
                show_alert=True,
            )
        else:
            await message_or_callback.answer(
                texts.t("ADMIN_CAMPAIGN_CANNOT_EDIT_SUB", "❌ Cannot edit subscription parameters for this campaign")
            )
        return False
    return True


@admin_required
@error_handler
async def start_edit_campaign_subscription_days(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    if not await _ensure_subscription_campaign(callback, campaign, texts):
        return

    await state.clear()
    await state.set_state(AdminStates.editing_campaign_subscription_days)
    is_caption = bool(callback.message.caption) and not bool(callback.message.text)
    await state.update_data(
        editing_campaign_id=campaign_id,
        campaign_edit_message_id=callback.message.message_id,
        campaign_edit_message_is_caption=is_caption,
    )

    await callback.message.edit_text(
        texts.t(
            "ADMIN_CAMPAIGN_EDIT_DAYS_PROMPT",
            "📅 <b>Change subscription duration</b>\n\n"
            "Current value: <b>{days} d.</b>\n"
            "Enter new number of days (1-730):"
        ).format(days=campaign.subscription_duration_days or 0),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"),
                        callback_data=f"admin_campaign_edit_{campaign_id}",
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def process_edit_campaign_subscription_days(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    campaign_id = data.get("editing_campaign_id")
    if not campaign_id:
        await message.answer(texts.t("ADMIN_SESSION_EXPIRED", "❌ Edit session expired. Try again."))
        await state.clear()
        return

    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(texts.t("ADMIN_CAMPAIGN_INVALID_DAYS", "❌ Enter number of days (1-730)"))
        return

    if days <= 0 or days > 730:
        await message.answer(texts.t("ADMIN_CAMPAIGN_DAYS_RANGE", "❌ Duration must be 1-730 days"))
        return

    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await message.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"))
        await state.clear()
        return

    if not await _ensure_subscription_campaign(message, campaign, texts):
        await state.clear()
        return

    await update_campaign(db, campaign, subscription_duration_days=days)
    await state.clear()

    await message.answer(texts.t("ADMIN_CAMPAIGN_DAYS_UPDATED", "✅ Subscription duration updated."))

    edit_message_id = data.get("campaign_edit_message_id")
    edit_message_is_caption = data.get("campaign_edit_message_is_caption", False)
    if edit_message_id:
        await _render_campaign_edit_menu(
            message.bot,
            message.chat.id,
            edit_message_id,
            campaign,
            db_user.language,
            use_caption=edit_message_is_caption,
        )


@admin_required
@error_handler
async def start_edit_campaign_subscription_traffic(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    if not await _ensure_subscription_campaign(callback, campaign, texts):
        return

    await state.clear()
    await state.set_state(AdminStates.editing_campaign_subscription_traffic)
    is_caption = bool(callback.message.caption) and not bool(callback.message.text)
    await state.update_data(
        editing_campaign_id=campaign_id,
        campaign_edit_message_id=callback.message.message_id,
        campaign_edit_message_is_caption=is_caption,
    )

    current_traffic = campaign.subscription_traffic_gb or 0
    traffic_text = texts.t("ADMIN_UNLIMITED", "unlimited") if current_traffic == 0 else f"{current_traffic} GB"

    await callback.message.edit_text(
        texts.t(
            "ADMIN_CAMPAIGN_EDIT_TRAFFIC_PROMPT",
            "🌐 <b>Change traffic limit</b>\n\n"
            "Current value: <b>{traffic}</b>\n"
            "Enter new limit in GB (0 = unlimited, max 10000):"
        ).format(traffic=traffic_text),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"),
                        callback_data=f"admin_campaign_edit_{campaign_id}",
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def process_edit_campaign_subscription_traffic(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    campaign_id = data.get("editing_campaign_id")
    if not campaign_id:
        await message.answer(texts.t("ADMIN_SESSION_EXPIRED", "❌ Edit session expired. Try again."))
        await state.clear()
        return

    try:
        traffic = int(message.text.strip())
    except ValueError:
        await message.answer(texts.t("ADMIN_CAMPAIGN_INVALID_TRAFFIC", "❌ Enter an integer (0 or more)"))
        return

    if traffic < 0 or traffic > 10000:
        await message.answer(texts.t("ADMIN_CAMPAIGN_TRAFFIC_RANGE", "❌ Traffic limit must be 0-10000 GB"))
        return

    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await message.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"))
        await state.clear()
        return

    if not await _ensure_subscription_campaign(message, campaign, texts):
        await state.clear()
        return

    await update_campaign(db, campaign, subscription_traffic_gb=traffic)
    await state.clear()

    await message.answer(texts.t("ADMIN_CAMPAIGN_TRAFFIC_UPDATED", "✅ Traffic limit updated."))

    edit_message_id = data.get("campaign_edit_message_id")
    edit_message_is_caption = data.get("campaign_edit_message_is_caption", False)
    if edit_message_id:
        await _render_campaign_edit_menu(
            message.bot,
            message.chat.id,
            edit_message_id,
            campaign,
            db_user.language,
            use_caption=edit_message_is_caption,
        )


@admin_required
@error_handler
async def start_edit_campaign_subscription_devices(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    if not await _ensure_subscription_campaign(callback, campaign, texts):
        return

    await state.clear()
    await state.set_state(AdminStates.editing_campaign_subscription_devices)
    is_caption = bool(callback.message.caption) and not bool(callback.message.text)
    await state.update_data(
        editing_campaign_id=campaign_id,
        campaign_edit_message_id=callback.message.message_id,
        campaign_edit_message_is_caption=is_caption,
    )

    current_devices = campaign.subscription_device_limit
    if current_devices is None:
        current_devices = settings.DEFAULT_DEVICE_LIMIT

    await callback.message.edit_text(
        texts.t(
            "ADMIN_CAMPAIGN_EDIT_DEVICES_PROMPT",
            "📱 <b>Change device limit</b>\n\n"
            "Current value: <b>{devices}</b>\n"
            "Enter new count (1-{max}):"
        ).format(devices=current_devices, max=settings.MAX_DEVICES_LIMIT),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"),
                        callback_data=f"admin_campaign_edit_{campaign_id}",
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def process_edit_campaign_subscription_devices(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    campaign_id = data.get("editing_campaign_id")
    if not campaign_id:
        await message.answer(texts.t("ADMIN_SESSION_EXPIRED", "❌ Edit session expired. Try again."))
        await state.clear()
        return

    try:
        devices = int(message.text.strip())
    except ValueError:
        await message.answer(texts.t("ADMIN_CAMPAIGN_INVALID_DEVICES", "❌ Enter an integer for devices"))
        return

    if devices < 1 or devices > settings.MAX_DEVICES_LIMIT:
        await message.answer(
            texts.t("ADMIN_CAMPAIGN_DEVICES_RANGE", "❌ Devices must be 1-{max}").format(max=settings.MAX_DEVICES_LIMIT)
        )
        return

    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await message.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"))
        await state.clear()
        return

    if not await _ensure_subscription_campaign(message, campaign, texts):
        await state.clear()
        return

    await update_campaign(db, campaign, subscription_device_limit=devices)
    await state.clear()

    await message.answer(texts.t("ADMIN_CAMPAIGN_DEVICES_UPDATED", "✅ Device limit updated."))

    edit_message_id = data.get("campaign_edit_message_id")
    edit_message_is_caption = data.get("campaign_edit_message_is_caption", False)
    if edit_message_id:
        await _render_campaign_edit_menu(
            message.bot,
            message.chat.id,
            edit_message_id,
            campaign,
            db_user.language,
            use_caption=edit_message_is_caption,
        )


@admin_required
@error_handler
async def start_edit_campaign_subscription_servers(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    if not await _ensure_subscription_campaign(callback, campaign, texts):
        return

    servers, _ = await get_all_server_squads(db, available_only=False)
    if not servers:
        await callback.answer(
            texts.t("ADMIN_CAMPAIGN_NO_SERVERS", "❌ No servers found. Add servers before editing."),
            show_alert=True,
        )
        return

    selected = list(campaign.subscription_squads or [])

    await state.clear()
    await state.set_state(AdminStates.editing_campaign_subscription_servers)
    is_caption = bool(callback.message.caption) and not bool(callback.message.text)
    await state.update_data(
        editing_campaign_id=campaign_id,
        campaign_edit_message_id=callback.message.message_id,
        campaign_subscription_squads=selected,
        campaign_edit_message_is_caption=is_caption,
    )

    keyboard = _build_campaign_servers_keyboard(
        servers,
        selected,
        texts,
        toggle_prefix=f"campaign_edit_toggle_{campaign_id}_",
        save_callback=f"campaign_edit_servers_save_{campaign_id}",
        back_callback=f"admin_campaign_edit_{campaign_id}",
    )

    await callback.message.edit_text(
        texts.t(
            "ADMIN_CAMPAIGN_EDIT_SERVERS_PROMPT",
            "🌍 <b>Edit available servers</b>\n\n"
            "Click on a server to add or remove it from the campaign.\n"
            "After selection, click \"✅ Save\"."
        ),
        reply_markup=keyboard,
    )
    await callback.answer()


@admin_required
@error_handler
async def toggle_edit_campaign_server(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    parts = callback.data.split("_")
    try:
        server_id = int(parts[-1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_CAMPAIGN_SERVER_ERROR", "❌ Could not determine server"), show_alert=True)
        return

    data = await state.get_data()
    campaign_id = data.get("editing_campaign_id")
    if not campaign_id:
        await callback.answer(texts.t("ADMIN_SESSION_EXPIRED", "❌ Edit session expired"), show_alert=True)
        await state.clear()
        return

    server = await get_server_squad_by_id(db, server_id)
    if not server:
        await callback.answer(texts.t("ADMIN_SERVER_NOT_FOUND", "❌ Server not found"), show_alert=True)
        return

    selected = list(data.get("campaign_subscription_squads", []))

    if server.squad_uuid in selected:
        selected.remove(server.squad_uuid)
    else:
        selected.append(server.squad_uuid)

    await state.update_data(campaign_subscription_squads=selected)

    servers, _ = await get_all_server_squads(db, available_only=False)
    keyboard = _build_campaign_servers_keyboard(
        servers,
        selected,
        texts,
        toggle_prefix=f"campaign_edit_toggle_{campaign_id}_",
        save_callback=f"campaign_edit_servers_save_{campaign_id}",
        back_callback=f"admin_campaign_edit_{campaign_id}",
    )

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@admin_required
@error_handler
async def save_edit_campaign_subscription_servers(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    campaign_id = data.get("editing_campaign_id")
    if not campaign_id:
        await callback.answer(texts.t("ADMIN_SESSION_EXPIRED", "❌ Edit session expired"), show_alert=True)
        await state.clear()
        return

    selected = list(data.get("campaign_subscription_squads", []))
    if not selected:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_SELECT_SERVER", "❗ Select at least one server"), show_alert=True)
        return

    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await state.clear()
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    if not await _ensure_subscription_campaign(callback, campaign, texts):
        await state.clear()
        return

    await update_campaign(db, campaign, subscription_squads=selected)
    await state.clear()

    use_caption = bool(callback.message.caption) and not bool(callback.message.text)

    await _render_campaign_edit_menu(
        callback.bot,
        callback.message.chat.id,
        callback.message.message_id,
        campaign,
        db_user.language,
        use_caption=use_caption,
    )
    await callback.answer(texts.t("ADMIN_SAVED", "✅ Saved"))


@admin_required
@error_handler
async def toggle_campaign_status(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    new_status = not campaign.is_active
    await update_campaign(db, campaign, is_active=new_status)
    status_text = "enabled" if new_status else "disabled"
    logger.info("Campaign %s toggled: %s", campaign_id, status_text)

    await show_campaign_detail(callback, db_user, db)


@admin_required
@error_handler
async def show_campaign_stats(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    stats = await get_campaign_statistics(db, campaign_id)

    text = [texts.t("ADMIN_CAMPAIGN_STATS_TITLE", "📊 <b>Campaign Statistics</b>") + "\n"]
    text.append(_format_campaign_summary(campaign, texts))
    text.append(texts.t("ADMIN_CAMPAIGN_STATS_REGISTRATIONS", "Registrations: <b>{count}</b>").format(count=stats['registrations']))
    text.append(texts.t("ADMIN_CAMPAIGN_STATS_BALANCE_ISSUED", "Balance issued: <b>{amount}</b>").format(
        amount=texts.format_price(stats['balance_issued'])
    ))
    text.append(texts.t("ADMIN_CAMPAIGN_STATS_SUBS_ISSUED", "Subscriptions issued: <b>{count}</b>").format(
        count=stats['subscription_issued']
    ))
    if stats["last_registration"]:
        text.append(texts.t("ADMIN_CAMPAIGN_STATS_LAST_REG_DATE", "Last registration: {date}").format(
            date=stats['last_registration'].strftime('%d.%m.%Y %H:%M')
        ))

    await callback.message.edit_text(
        "\n".join(text),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.BACK,
                        callback_data=f"admin_campaign_manage_{campaign_id}",
                    )
                ]
            ]
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def confirm_delete_campaign(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    text = texts.t(
        "ADMIN_CAMPAIGN_DELETE_CONFIRM",
        "🗑️ <b>Delete campaign</b>\n\n"
        "Name: <b>{name}</b>\n"
        "Parameter: <code>{param}</code>\n\n"
        "Are you sure you want to delete this campaign?"
    ).format(name=campaign.name, param=campaign.start_parameter)

    await callback.message.edit_text(
        text,
        reply_markup=get_confirmation_keyboard(
            confirm_action=f"admin_campaign_delete_confirm_{campaign_id}",
            cancel_action=f"admin_campaign_manage_{campaign_id}",
        ),
    )
    await callback.answer()


@admin_required
@error_handler
async def delete_campaign_confirmed(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    campaign_id = int(callback.data.split("_")[-1])
    campaign = await get_campaign_by_id(db, campaign_id)
    if not campaign:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_NOT_FOUND", "❌ Campaign not found"), show_alert=True)
        return

    await delete_campaign(db, campaign)
    await callback.message.edit_text(
        texts.t("ADMIN_CAMPAIGN_DELETED", "✅ Campaign deleted."),
        reply_markup=get_admin_campaigns_keyboard(db_user.language),
    )
    await callback.answer(texts.t("ADMIN_DELETED", "Deleted"))


@admin_required
@error_handler
async def start_campaign_creation(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    await state.clear()
    await callback.message.edit_text(
        texts.t("ADMIN_CAMPAIGN_CREATE_NAME_PROMPT", "🆕 <b>Create advertising campaign</b>\n\nEnter campaign name:"),
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.BACK, callback_data="admin_campaigns"
                    )
                ]
            ]
        ),
    )
    await state.set_state(AdminStates.creating_campaign_name)
    await callback.answer()


@admin_required
@error_handler
async def process_campaign_name(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    name = message.text.strip()
    if len(name) < 3 or len(name) > 100:
        await message.answer(
            texts.t("ADMIN_CAMPAIGN_NAME_LENGTH", "❌ Name must be 3-100 characters. Try again.")
        )
        return

    await state.update_data(campaign_name=name)
    await state.set_state(AdminStates.creating_campaign_start)
    await message.answer(
        texts.t("ADMIN_CAMPAIGN_CREATE_PARAM_PROMPT", "🔗 Now enter start parameter (Latin letters, numbers, - or _):"),
    )


@admin_required
@error_handler
async def process_campaign_start_parameter(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    start_param = message.text.strip()
    if not _CAMPAIGN_PARAM_REGEX.match(start_param):
        await message.answer(
            texts.t("ADMIN_CAMPAIGN_PARAM_INVALID", "❌ Only Latin letters, numbers, - and _ allowed. Length 3-32 characters.")
        )
        return

    existing = await get_campaign_by_start_parameter(db, start_param)
    if existing:
        await message.answer(
            texts.t("ADMIN_CAMPAIGN_PARAM_EXISTS", "❌ Campaign with this parameter already exists. Enter another.")
        )
        return

    await state.update_data(campaign_start_parameter=start_param)
    await state.set_state(AdminStates.creating_campaign_bonus)
    await message.answer(
        texts.t("ADMIN_CAMPAIGN_SELECT_BONUS_TYPE", "🎯 Select bonus type for campaign:"),
        reply_markup=get_campaign_bonus_type_keyboard(db_user.language),
    )


@admin_required
@error_handler
async def select_campaign_bonus_type(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    bonus_type = "balance" if callback.data.endswith("balance") else "subscription"
    await state.update_data(campaign_bonus_type=bonus_type)

    if bonus_type == "balance":
        await state.set_state(AdminStates.creating_campaign_balance)
        await callback.message.edit_text(
            texts.t("ADMIN_CAMPAIGN_ENTER_BALANCE", "💰 Enter balance bonus amount (in rubles):"),
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.BACK, callback_data="admin_campaigns"
                        )
                    ]
                ]
            ),
        )
    else:
        await state.set_state(AdminStates.creating_campaign_subscription_days)
        await callback.message.edit_text(
            texts.t("ADMIN_CAMPAIGN_ENTER_DAYS", "📅 Enter subscription duration in days (1-730):"),
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text=texts.BACK, callback_data="admin_campaigns"
                        )
                    ]
                ]
            ),
        )
    await callback.answer()


@admin_required
@error_handler
async def process_campaign_balance_value(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    try:
        amount_rubles = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(texts.t("ADMIN_CAMPAIGN_INVALID_AMOUNT", "❌ Enter a valid amount (e.g. 100 or 99.5)"))
        return

    if amount_rubles <= 0:
        await message.answer(texts.t("ADMIN_CAMPAIGN_AMOUNT_POSITIVE", "❌ Amount must be greater than zero"))
        return

    amount_kopeks = int(round(amount_rubles * 100))
    data = await state.get_data()

    campaign = await create_campaign(
        db,
        name=data["campaign_name"],
        start_parameter=data["campaign_start_parameter"],
        bonus_type="balance",
        balance_bonus_kopeks=amount_kopeks,
        created_by=db_user.id,
    )

    await state.clear()

    deep_link = await _get_bot_deep_link_from_message(message, campaign.start_parameter)
    summary = _format_campaign_summary(campaign, texts)
    text = texts.t(
        "ADMIN_CAMPAIGN_CREATED",
        "✅ <b>Campaign created!</b>\n\n{summary}\n🔗 Link: <code>{link}</code>"
    ).format(summary=summary, link=deep_link)

    await message.answer(
        text,
        reply_markup=get_campaign_management_keyboard(
            campaign.id, campaign.is_active, db_user.language
        ),
    )


@admin_required
@error_handler
async def process_campaign_subscription_days(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(texts.t("ADMIN_CAMPAIGN_INVALID_DAYS", "❌ Enter number of days (1-730)"))
        return

    if days <= 0 or days > 730:
        await message.answer(texts.t("ADMIN_CAMPAIGN_DAYS_RANGE", "❌ Duration must be 1-730 days"))
        return

    await state.update_data(campaign_subscription_days=days)
    await state.set_state(AdminStates.creating_campaign_subscription_traffic)
    await message.answer(texts.t("ADMIN_CAMPAIGN_ENTER_TRAFFIC", "🌐 Enter traffic limit in GB (0 = unlimited):"))


@admin_required
@error_handler
async def process_campaign_subscription_traffic(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    try:
        traffic = int(message.text.strip())
    except ValueError:
        await message.answer(texts.t("ADMIN_CAMPAIGN_INVALID_TRAFFIC", "❌ Enter an integer (0 or more)"))
        return

    if traffic < 0 or traffic > 10000:
        await message.answer(texts.t("ADMIN_CAMPAIGN_TRAFFIC_RANGE", "❌ Traffic limit must be 0-10000 GB"))
        return

    await state.update_data(campaign_subscription_traffic=traffic)
    await state.set_state(AdminStates.creating_campaign_subscription_devices)
    await message.answer(
        texts.t("ADMIN_CAMPAIGN_ENTER_DEVICES", "📱 Enter device count (1-{max}):").format(max=settings.MAX_DEVICES_LIMIT)
    )


@admin_required
@error_handler
async def process_campaign_subscription_devices(
    message: types.Message,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    try:
        devices = int(message.text.strip())
    except ValueError:
        await message.answer(texts.t("ADMIN_CAMPAIGN_INVALID_DEVICES", "❌ Enter an integer for devices"))
        return

    if devices < 1 or devices > settings.MAX_DEVICES_LIMIT:
        await message.answer(
            texts.t("ADMIN_CAMPAIGN_DEVICES_RANGE", "❌ Devices must be 1-{max}").format(max=settings.MAX_DEVICES_LIMIT)
        )
        return

    await state.update_data(campaign_subscription_devices=devices)
    await state.update_data(campaign_subscription_squads=[])
    await state.set_state(AdminStates.creating_campaign_subscription_servers)

    servers, _ = await get_all_server_squads(db, available_only=False)
    if not servers:
        await message.answer(
            texts.t("ADMIN_CAMPAIGN_NO_SERVERS_CREATE", "❌ No servers found. Add servers before creating campaign."),
        )
        await state.clear()
        return

    keyboard = _build_campaign_servers_keyboard(servers, [], texts)
    await message.answer(
        texts.t("ADMIN_CAMPAIGN_SELECT_SERVERS", "🌍 Select servers available for subscription (max 20 shown)."),
        reply_markup=keyboard,
    )


@admin_required
@error_handler
async def toggle_campaign_server(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    server_id = int(callback.data.split("_")[-1])
    server = await get_server_squad_by_id(db, server_id)
    if not server:
        await callback.answer(texts.t("ADMIN_SERVER_NOT_FOUND", "❌ Server not found"), show_alert=True)
        return

    data = await state.get_data()
    selected = list(data.get("campaign_subscription_squads", []))

    if server.squad_uuid in selected:
        selected.remove(server.squad_uuid)
    else:
        selected.append(server.squad_uuid)

    await state.update_data(campaign_subscription_squads=selected)

    servers, _ = await get_all_server_squads(db, available_only=False)
    keyboard = _build_campaign_servers_keyboard(servers, selected, texts)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@admin_required
@error_handler
async def finalize_campaign_subscription(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    selected = data.get("campaign_subscription_squads", [])

    if not selected:
        await callback.answer(texts.t("ADMIN_CAMPAIGN_SELECT_SERVER", "❗ Select at least one server"), show_alert=True)
        return

    campaign = await create_campaign(
        db,
        name=data["campaign_name"],
        start_parameter=data["campaign_start_parameter"],
        bonus_type="subscription",
        subscription_duration_days=data.get("campaign_subscription_days"),
        subscription_traffic_gb=data.get("campaign_subscription_traffic"),
        subscription_device_limit=data.get("campaign_subscription_devices"),
        subscription_squads=selected,
        created_by=db_user.id,
    )

    await state.clear()

    deep_link = await _get_bot_deep_link(callback, campaign.start_parameter)
    summary = _format_campaign_summary(campaign, texts)
    text = texts.t(
        "ADMIN_CAMPAIGN_CREATED",
        "✅ <b>Campaign created!</b>\n\n{summary}\n🔗 Link: <code>{link}</code>"
    ).format(summary=summary, link=deep_link)

    await callback.message.edit_text(
        text,
        reply_markup=get_campaign_management_keyboard(
            campaign.id, campaign.is_active, db_user.language
        ),
    )
    await callback.answer()


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_campaigns_menu, F.data == "admin_campaigns")
    dp.callback_query.register(
        show_campaigns_overall_stats, F.data == "admin_campaigns_stats"
    )
    dp.callback_query.register(show_campaigns_list, F.data == "admin_campaigns_list")
    dp.callback_query.register(
        show_campaigns_list, F.data.startswith("admin_campaigns_list_page_")
    )
    dp.callback_query.register(
        start_campaign_creation, F.data == "admin_campaigns_create"
    )
    dp.callback_query.register(
        show_campaign_stats, F.data.startswith("admin_campaign_stats_")
    )
    dp.callback_query.register(
        show_campaign_detail, F.data.startswith("admin_campaign_manage_")
    )
    dp.callback_query.register(
        start_edit_campaign_name, F.data.startswith("admin_campaign_edit_name_")
    )
    dp.callback_query.register(
        start_edit_campaign_start_parameter,
        F.data.startswith("admin_campaign_edit_start_"),
    )
    dp.callback_query.register(
        start_edit_campaign_balance_bonus,
        F.data.startswith("admin_campaign_edit_balance_"),
    )
    dp.callback_query.register(
        start_edit_campaign_subscription_days,
        F.data.startswith("admin_campaign_edit_sub_days_"),
    )
    dp.callback_query.register(
        start_edit_campaign_subscription_traffic,
        F.data.startswith("admin_campaign_edit_sub_traffic_"),
    )
    dp.callback_query.register(
        start_edit_campaign_subscription_devices,
        F.data.startswith("admin_campaign_edit_sub_devices_"),
    )
    dp.callback_query.register(
        start_edit_campaign_subscription_servers,
        F.data.startswith("admin_campaign_edit_sub_servers_"),
    )
    dp.callback_query.register(
        save_edit_campaign_subscription_servers,
        F.data.startswith("campaign_edit_servers_save_"),
    )
    dp.callback_query.register(
        toggle_edit_campaign_server, F.data.startswith("campaign_edit_toggle_")
    )
    dp.callback_query.register(
        show_campaign_edit_menu, F.data.startswith("admin_campaign_edit_")
    )
    dp.callback_query.register(
        delete_campaign_confirmed, F.data.startswith("admin_campaign_delete_confirm_")
    )
    dp.callback_query.register(
        confirm_delete_campaign, F.data.startswith("admin_campaign_delete_")
    )
    dp.callback_query.register(
        toggle_campaign_status, F.data.startswith("admin_campaign_toggle_")
    )
    dp.callback_query.register(
        finalize_campaign_subscription, F.data == "campaign_servers_save"
    )
    dp.callback_query.register(
        toggle_campaign_server, F.data.startswith("campaign_toggle_server_")
    )
    dp.callback_query.register(
        select_campaign_bonus_type, F.data.startswith("campaign_bonus_")
    )

    dp.message.register(process_campaign_name, AdminStates.creating_campaign_name)
    dp.message.register(
        process_campaign_start_parameter, AdminStates.creating_campaign_start
    )
    dp.message.register(
        process_campaign_balance_value, AdminStates.creating_campaign_balance
    )
    dp.message.register(
        process_campaign_subscription_days,
        AdminStates.creating_campaign_subscription_days,
    )
    dp.message.register(
        process_campaign_subscription_traffic,
        AdminStates.creating_campaign_subscription_traffic,
    )
    dp.message.register(
        process_campaign_subscription_devices,
        AdminStates.creating_campaign_subscription_devices,
    )
    dp.message.register(
        process_edit_campaign_name, AdminStates.editing_campaign_name
    )
    dp.message.register(
        process_edit_campaign_start_parameter,
        AdminStates.editing_campaign_start,
    )
    dp.message.register(
        process_edit_campaign_balance_bonus,
        AdminStates.editing_campaign_balance,
    )
    dp.message.register(
        process_edit_campaign_subscription_days,
        AdminStates.editing_campaign_subscription_days,
    )
    dp.message.register(
        process_edit_campaign_subscription_traffic,
        AdminStates.editing_campaign_subscription_traffic,
    )
    dp.message.register(
        process_edit_campaign_subscription_devices,
        AdminStates.editing_campaign_subscription_devices,
    )
