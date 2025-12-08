import html
import logging
from aiogram import Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.states import AdminStates
from app.database.models import User
from app.database.crud.server_squad import (
    get_all_server_squads,
    get_server_squad_by_id,
    update_server_squad,
    delete_server_squad,
    sync_with_remnawave,
    get_server_statistics,
    create_server_squad,
    get_available_server_squads,
    update_server_squad_promo_groups,
    get_server_connected_users,
)
from app.database.crud.promo_group import get_promo_groups_with_counts
from app.services.remnawave_service import RemnaWaveService
from app.utils.decorators import admin_required, error_handler
from app.utils.cache import cache
from app.localization.texts import get_texts

logger = logging.getLogger(__name__)


def _build_server_edit_view(server, language: str = "en"):
    texts = get_texts(language)
    status_emoji = texts.t("ADMIN_SRV_STATUS_AVAILABLE", "✅ Available") if server.is_available else texts.t("ADMIN_SRV_STATUS_UNAVAILABLE", "❌ Unavailable")
    price_text = f"{int(server.price_rubles)} ₽" if server.price_kopeks > 0 else texts.t("ADMIN_SRV_FREE", "Free")
    promo_groups_text = (
        ", ".join(sorted(pg.name for pg in server.allowed_promo_groups))
        if server.allowed_promo_groups
        else texts.t("ADMIN_SRV_NOT_SELECTED", "Not selected")
    )

    trial_status = texts.t("YES", "Yes") if server.is_trial_eligible else texts.t("NO", "No")
    not_specified = texts.t("ADMIN_SRV_NOT_SPECIFIED", "Not specified")
    no_limit = texts.t("ADMIN_SRV_NO_LIMIT", "No limit")

    text = texts.t(
        "ADMIN_SRV_EDIT_VIEW",
        """
🌐 <b>Server Editing</b>

<b>Information:</b>
• ID: {server_id}
• UUID: <code>{uuid}</code>
• Name: {name}
• Original: {original}
• Status: {status}

<b>Settings:</b>
• Price: {price}
• Country code: {country}
• User limit: {limit}
• Current users: {current}
• Promo groups: {promo}
• Trial eligible: {trial}

<b>Description:</b>
{description}

Select what to edit:
"""
    ).format(
        server_id=server.id,
        uuid=server.squad_uuid,
        name=server.display_name,
        original=server.original_name or not_specified,
        status=status_emoji,
        price=price_text,
        country=server.country_code or not_specified,
        limit=server.max_users or no_limit,
        current=server.current_users,
        promo=promo_groups_text,
        trial=trial_status,
        description=server.description or not_specified,
    )

    keyboard = [
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_SRV_BTN_NAME", "✏️ Name"), callback_data=f"admin_server_edit_name_{server.id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_SRV_BTN_PRICE", "💰 Price"), callback_data=f"admin_server_edit_price_{server.id}"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_SRV_BTN_COUNTRY", "🌍 Country"), callback_data=f"admin_server_edit_country_{server.id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_SRV_BTN_LIMIT", "👥 Limit"), callback_data=f"admin_server_edit_limit_{server.id}"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_SRV_BTN_USERS", "👥 Users"), callback_data=f"admin_server_users_{server.id}"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_SRV_BTN_ENABLE_TRIAL", "🎁 Enable for trial") if not server.is_trial_eligible else texts.t("ADMIN_SRV_BTN_DISABLE_TRIAL", "🚫 Disable for trial"),
                callback_data=f"admin_server_trial_{server.id}",
            ),
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_SRV_BTN_PROMO", "🎯 Promo groups"), callback_data=f"admin_server_edit_promo_{server.id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_SRV_BTN_DESC", "📝 Description"), callback_data=f"admin_server_edit_desc_{server.id}"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_SRV_BTN_DISABLE", "❌ Disable") if server.is_available else texts.t("ADMIN_SRV_BTN_ENABLE", "✅ Enable"),
                callback_data=f"admin_server_toggle_{server.id}",
            )
        ],
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_SRV_BTN_DELETE", "🗑️ Delete"), callback_data=f"admin_server_delete_{server.id}"
            ),
            types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_servers_list"),
        ],
    ]

    return text, types.InlineKeyboardMarkup(inline_keyboard=keyboard)


def _build_server_promo_groups_keyboard(server_id: int, promo_groups, selected_ids, language: str = "en"):
    texts = get_texts(language)
    keyboard = []
    for group in promo_groups:
        emoji = "✅" if group["id"] in selected_ids else "⚪"
        keyboard.append(
            [
                types.InlineKeyboardButton(
                    text=f"{emoji} {group['name']}",
                    callback_data=f"admin_server_promo_toggle_{server_id}_{group['id']}",
                )
            ]
        )

    keyboard.append(
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_SRV_BTN_SAVE", "💾 Save"), callback_data=f"admin_server_promo_save_{server_id}"
            )
        ]
    )
    keyboard.append(
        [
            types.InlineKeyboardButton(
                text=texts.BACK, callback_data=f"admin_server_edit_{server_id}"
            )
        ]
    )

    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


@admin_required
@error_handler
async def show_servers_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    stats = await get_server_statistics(db)
    
    text = texts.t(
        "ADMIN_SRV_MENU",
        """
🌐 <b>Server Management</b>

📊 <b>Statistics:</b>
• Total servers: {total}
• Available: {available}
• Unavailable: {unavailable}
• With connections: {with_connections}

💰 <b>Server revenue:</b>
• Total: {revenue} ₽

Select an action:
"""
    ).format(
        total=stats['total_servers'],
        available=stats['available_servers'],
        unavailable=stats['unavailable_servers'],
        with_connections=stats['servers_with_connections'],
        revenue=int(stats['total_revenue_rubles']),
    )
    
    keyboard = [
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_LIST", "📋 Server list"), callback_data="admin_servers_list"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_SYNC", "🔄 Sync"), callback_data="admin_servers_sync")
        ],
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_SYNC_COUNTS", "📊 Sync counters"), callback_data="admin_servers_sync_counts"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_STATS", "📈 Detailed stats"), callback_data="admin_servers_stats")
        ],
        [
            types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_panel")
        ]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def show_servers_list(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    page: int = 1
):
    texts = get_texts(db_user.language)
    servers, total_count = await get_all_server_squads(db, page=page, limit=10)
    total_pages = (total_count + 9) // 10
    
    if not servers:
        text = texts.t("ADMIN_SRV_LIST_EMPTY", "🌐 <b>Server List</b>\n\n❌ No servers found.")
    else:
        text = texts.t("ADMIN_SRV_LIST_TITLE", "🌐 <b>Server List</b>") + "\n\n"
        text += texts.t("ADMIN_SRV_LIST_STATS", "📊 Total: {total} | Page: {page}/{pages}").format(
            total=total_count, page=page, pages=total_pages
        ) + "\n\n"
        
        for i, server in enumerate(servers, 1 + (page - 1) * 10):
            status_emoji = "✅" if server.is_available else "❌"
            price_text = f"{int(server.price_rubles)} ₽" if server.price_kopeks > 0 else texts.t("ADMIN_SRV_FREE", "Free")
            
            text += f"{i}. {status_emoji} {server.display_name}\n"
            text += f"   💰 {texts.t('ADMIN_SRV_PRICE_LABEL', 'Price')}: {price_text}"
            
            if server.max_users:
                text += f" | 👥 {server.current_users}/{server.max_users}"
            
            text += f"\n   UUID: <code>{server.squad_uuid}</code>\n\n"
    
    keyboard = []
    
    for i, server in enumerate(servers):
        row_num = i // 2 
        if len(keyboard) <= row_num:
            keyboard.append([])
        
        status_emoji = "✅" if server.is_available else "❌"
        keyboard[row_num].append(
            types.InlineKeyboardButton(
                text=f"{status_emoji} {server.display_name[:15]}...",
                callback_data=f"admin_server_edit_{server.id}"
            )
        )
    
    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(types.InlineKeyboardButton(
                text="⬅️", callback_data=f"admin_servers_list_page_{page-1}"
            ))
        
        nav_row.append(types.InlineKeyboardButton(
            text=f"{page}/{total_pages}", callback_data="current_page"
        ))
        
        if page < total_pages:
            nav_row.append(types.InlineKeyboardButton(
                text="➡️", callback_data=f"admin_servers_list_page_{page+1}"
            ))
        
        keyboard.append(nav_row)
    
    keyboard.extend([
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_servers")]
    ])
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def sync_servers_with_remnawave(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t("ADMIN_SRV_SYNC_IN_PROGRESS", "🔄 Syncing with Remnawave...\n\nPlease wait, this may take some time."),
        reply_markup=None
    )
    
    try:
        remnawave_service = RemnaWaveService()
        squads = await remnawave_service.get_all_squads()
        
        if not squads:
            await callback.message.edit_text(
                texts.t("ADMIN_SRV_SYNC_NO_SQUADS", "❌ Failed to get squad data from Remnawave.\n\nCheck API settings."),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_servers")]
                ])
            )
            return
        
        created, updated, removed = await sync_with_remnawave(db, squads)
        
        await cache.delete_pattern("available_countries*")
        
        text = texts.t(
            "ADMIN_SRV_SYNC_COMPLETE",
            """
✅ <b>Sync completed</b>

📊 <b>Results:</b>
• New servers created: {created}
• Existing updated: {updated}
• Missing removed: {removed}
• Total processed: {total}

ℹ️ New servers are created as unavailable.
Configure them in the server list.
"""
        ).format(created=created, updated=updated, removed=removed, total=len(squads))
        
        keyboard = [
            [
                types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_LIST", "📋 Server list"), callback_data="admin_servers_list"),
                types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_REPEAT", "🔄 Repeat"), callback_data="admin_servers_sync")
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_servers")]
        ]
        
        await callback.message.edit_text(
            text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    except Exception as e:
        logger.error(f"Server sync error: {e}")
        await callback.message.edit_text(
            texts.t("ADMIN_SRV_SYNC_ERROR", "❌ Sync error: {error}").format(error=str(e)),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_servers")]
            ])
        )

    await callback.answer()


@admin_required
@error_handler
async def show_server_edit_menu(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    
    server_id = int(callback.data.split('_')[-1])
    server = await get_server_squad_by_id(db, server_id)

    texts = get_texts(db_user.language)
    if not server:
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found!"), show_alert=True)
        return

    text, keyboard = _build_server_edit_view(server, db_user.language)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def show_server_users(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):

    payload = callback.data.split("admin_server_users_", 1)[-1]
    payload_parts = payload.split("_")

    server_id = int(payload_parts[0])
    page = int(payload_parts[1]) if len(payload_parts) > 1 else 1
    page = max(page, 1)
    server = await get_server_squad_by_id(db, server_id)

    if not server:
        texts = get_texts(db_user.language)
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found!"), show_alert=True)
        return

    users = await get_server_connected_users(db, server_id)
    total_users = len(users)

    page_size = 10
    total_pages = max((total_users + page_size - 1) // page_size, 1)

    if page > total_pages:
        page = total_pages

    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    page_users = users[start_index:end_index]

    safe_name = html.escape(server.display_name or "—")
    safe_uuid = html.escape(server.squad_uuid or "—")

    texts = get_texts(db_user.language)
    header = [
        texts.t("ADMIN_SRV_USERS_TITLE", "🌐 <b>Server Users</b>"),
        "",
        texts.t("ADMIN_SRV_USERS_SERVER", "• Server: {name}").format(name=safe_name),
        f"• UUID: <code>{safe_uuid}</code>",
        texts.t("ADMIN_SRV_USERS_CONNECTIONS", "• Connections: {count}").format(count=total_users),
    ]

    if total_pages > 1:
        header.append(texts.t("ADMIN_SRV_USERS_PAGE", "• Page: {page}/{total}").format(page=page, total=total_pages))

    header.append("")

    text = "\n".join(header)

    def _get_status_icon(status_text: str) -> str:
        if not status_text:
            return ""

        parts = status_text.split(" ", 1)
        return parts[0] if parts else status_text

    if users:
        lines = []
        for index, user in enumerate(page_users, start=start_index + 1):
            safe_user_name = html.escape(user.full_name)
            user_link = f'<a href="tg://user?id={user.telegram_id}">{safe_user_name}</a>'
            lines.append(f"{index}. {user_link}")

        text += "\n" + "\n".join(lines)
    else:
        text += texts.t("ADMIN_SRV_USERS_NOT_FOUND", "Users not found.")

    keyboard: list[list[types.InlineKeyboardButton]] = []

    for user in page_users:
        display_name = user.full_name
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."

        subscription_status = (
            user.subscription.status_display
            if user.subscription
            else texts.t("ADMIN_SRV_NO_SUBSCRIPTION", "❌ No subscription")
        )
        status_icon = _get_status_icon(subscription_status)

        if status_icon:
            button_text = f"{status_icon} {display_name}"
        else:
            button_text = display_name

        keyboard.append([
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"admin_user_manage_{user.id}",
            )
        ])

    if total_pages > 1:
        navigation_buttons: list[types.InlineKeyboardButton] = []

        if page > 1:
            navigation_buttons.append(
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SRV_BTN_PREV", "⬅️ Previous"),
                    callback_data=f"admin_server_users_{server_id}_{page - 1}",
                )
            )

        navigation_buttons.append(
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_SRV_PAGE_INFO", "Page {page}/{total}").format(page=page, total=total_pages),
                callback_data=f"admin_server_users_{server_id}_{page}",
            )
        )

        if page < total_pages:
            navigation_buttons.append(
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_SRV_BTN_NEXT", "Next ➡️"),
                    callback_data=f"admin_server_users_{server_id}_{page + 1}",
                )
            )

        keyboard.append(navigation_buttons)

    keyboard.append([
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_SRV_BTN_TO_SERVER", "⬅️ To server"), callback_data=f"admin_server_edit_{server_id}"
        )
    ])

    keyboard.append([
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_SRV_BTN_TO_LIST", "⬅️ To list"), callback_data="admin_servers_list"
        )
    ])

    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML",
    )

    await callback.answer()


@admin_required
@error_handler
async def toggle_server_availability(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    server_id = int(callback.data.split('_')[-1])
    server = await get_server_squad_by_id(db, server_id)
    
    if not server:
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found!"), show_alert=True)
        return
    
    new_status = not server.is_available
    await update_server_squad(db, server_id, is_available=new_status)
    
    await cache.delete_pattern("available_countries*")
    
    status_text = texts.t("ADMIN_SRV_STATUS_ENABLED", "enabled") if new_status else texts.t("ADMIN_SRV_STATUS_DISABLED", "disabled")
    await callback.answer(texts.t("ADMIN_SRV_TOGGLE_SUCCESS", "✅ Server {status}!").format(status=status_text))
    
    server = await get_server_squad_by_id(db, server_id)
    
    text, keyboard = _build_server_edit_view(server, db_user.language)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@admin_required
@error_handler
async def toggle_server_trial_assignment(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    server_id = int(callback.data.split('_')[-1])
    server = await get_server_squad_by_id(db, server_id)

    if not server:
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found!"), show_alert=True)
        return

    new_status = not server.is_trial_eligible
    await update_server_squad(db, server_id, is_trial_eligible=new_status)

    status_text = texts.t("ADMIN_SRV_TRIAL_WILL_BE_ASSIGNED", "will be assigned") if new_status else texts.t("ADMIN_SRV_TRIAL_WILL_NOT_BE_ASSIGNED", "will not be assigned")
    await callback.answer(texts.t("ADMIN_SRV_TRIAL_TOGGLE", "✅ Squad {status} for trial").format(status=status_text))

    server = await get_server_squad_by_id(db, server_id)

    text, keyboard = _build_server_edit_view(server, db_user.language)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@admin_required
@error_handler
async def start_server_edit_price(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    server_id = int(callback.data.split('_')[-1])
    server = await get_server_squad_by_id(db, server_id)
    
    if not server:
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found!"), show_alert=True)
        return
    
    await state.set_data({'server_id': server_id})
    await state.set_state(AdminStates.editing_server_price)
    
    current_price = f"{int(server.price_rubles)} ₽" if server.price_kopeks > 0 else texts.t("ADMIN_SRV_FREE", "Free")
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_SRV_EDIT_PRICE_PROMPT",
            "💰 <b>Price editing</b>\n\nCurrent price: <b>{price}</b>\n\nSend new price in rubles (e.g.: 15.50) or 0 for free access:"
        ).format(price=current_price),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"admin_server_edit_{server_id}")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def process_server_price_edit(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    server_id = data.get('server_id')
    
    try:
        price_rubles = float(message.text.replace(',', '.'))
        
        if price_rubles < 0:
            await message.answer(texts.t("ADMIN_SRV_PRICE_NEGATIVE", "❌ Price cannot be negative"))
            return
        
        if price_rubles > 10000:
            await message.answer(texts.t("ADMIN_SRV_PRICE_TOO_HIGH", "❌ Price too high (max 10,000 ₽)"))
            return
        
        price_kopeks = int(price_rubles * 100)
        
        server = await update_server_squad(db, server_id, price_kopeks=price_kopeks)
        
        if server:
            await state.clear()
            
            await cache.delete_pattern("available_countries*")
            
            price_text = f"{int(price_rubles)} ₽" if price_kopeks > 0 else texts.t("ADMIN_SRV_FREE", "Free")
            await message.answer(
                texts.t("ADMIN_SRV_PRICE_CHANGED", "✅ Server price changed to: <b>{price}</b>").format(price=price_text),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_TO_SERVER", "🔙 To server"), callback_data=f"admin_server_edit_{server_id}")]
                ]),
                parse_mode="HTML"
            )
        else:
            await message.answer(texts.t("ADMIN_SRV_UPDATE_ERROR", "❌ Error updating server"))
    
    except ValueError:
        await message.answer(texts.t("ADMIN_SRV_PRICE_INVALID", "❌ Invalid price format. Use numbers (e.g.: 15.50)"))


@admin_required
@error_handler
async def start_server_edit_name(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    server_id = int(callback.data.split('_')[-1])
    server = await get_server_squad_by_id(db, server_id)
    
    if not server:
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found!"), show_alert=True)
        return
    
    await state.set_data({'server_id': server_id})
    await state.set_state(AdminStates.editing_server_name)
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_SRV_EDIT_NAME_PROMPT",
            "✏️ <b>Name editing</b>\n\nCurrent name: <b>{name}</b>\n\nSend new name for the server:"
        ).format(name=server.display_name),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"admin_server_edit_{server_id}")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def process_server_name_edit(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    server_id = data.get('server_id')
    
    new_name = message.text.strip()
    
    if len(new_name) > 255:
        await message.answer(texts.t("ADMIN_SRV_NAME_TOO_LONG", "❌ Name too long (max 255 characters)"))
        return
    
    if len(new_name) < 3:
        await message.answer(texts.t("ADMIN_SRV_NAME_TOO_SHORT", "❌ Name too short (min 3 characters)"))
        return
    
    server = await update_server_squad(db, server_id, display_name=new_name)
    
    if server:
        await state.clear()
        
        await cache.delete_pattern("available_countries*")
        
        await message.answer(
            texts.t("ADMIN_SRV_NAME_CHANGED", "✅ Server name changed to: <b>{name}</b>").format(name=new_name),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_TO_SERVER", "🔙 To server"), callback_data=f"admin_server_edit_{server_id}")]
            ]),
            parse_mode="HTML"
        )
    else:
        await message.answer(texts.t("ADMIN_SRV_UPDATE_ERROR", "❌ Error updating server"))


@admin_required
@error_handler
async def delete_server_confirm(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    server_id = int(callback.data.split('_')[-1])
    server = await get_server_squad_by_id(db, server_id)
    
    if not server:
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found!"), show_alert=True)
        return
    
    text = texts.t(
        "ADMIN_SRV_DELETE_CONFIRM",
        """
🗑️ <b>Delete server</b>

Are you sure you want to delete server:
<b>{name}</b>

⚠️ <b>Warning!</b>
Server can only be deleted if there are no active connections.

This action cannot be undone!
"""
    ).format(name=server.display_name)
    
    keyboard = [
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_YES_DELETE", "🗑️ Yes, delete"), callback_data=f"admin_server_delete_confirm_{server_id}"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"admin_server_edit_{server_id}")
        ]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def delete_server_execute(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    server_id = int(callback.data.split('_')[-1])
    server = await get_server_squad_by_id(db, server_id)
    
    if not server:
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found!"), show_alert=True)
        return
    
    success = await delete_server_squad(db, server_id)
    
    if success:
        await cache.delete_pattern("available_countries*")
        
        await callback.message.edit_text(
            texts.t("ADMIN_SRV_DELETE_SUCCESS", "✅ Server <b>{name}</b> successfully deleted!").format(name=server.display_name),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_TO_LIST", "📋 To server list"), callback_data="admin_servers_list")]
            ]),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            texts.t(
                "ADMIN_SRV_DELETE_FAILED",
                "❌ Failed to delete server <b>{name}</b>\n\nPossibly there are active connections."
            ).format(name=server.display_name),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_TO_SERVER", "🔙 To server"), callback_data=f"admin_server_edit_{server_id}")]
            ]),
            parse_mode="HTML"
        )
    
    await callback.answer()


@admin_required
@error_handler
async def show_server_detailed_stats(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    stats = await get_server_statistics(db)
    available_servers = await get_available_server_squads(db)
    
    avg_price = int(stats['total_revenue_rubles'] / max(stats['servers_with_connections'], 1))
    text = texts.t(
        "ADMIN_SRV_DETAILED_STATS",
        """
📊 <b>Detailed server statistics</b>

<b>🌐 General information:</b>
• Total servers: {total}
• Available: {available}
• Unavailable: {unavailable}
• With active connections: {with_connections}

<b>💰 Financial statistics:</b>
• Total revenue: {revenue} ₽
• Average price per server: {avg_price} ₽

<b>🔥 Top servers by price:</b>
"""
    ).format(
        total=stats['total_servers'],
        available=stats['available_servers'],
        unavailable=stats['unavailable_servers'],
        with_connections=stats['servers_with_connections'],
        revenue=int(stats['total_revenue_rubles']),
        avg_price=avg_price
    )
    
    sorted_servers = sorted(available_servers, key=lambda x: x.price_kopeks, reverse=True)
    
    for i, server in enumerate(sorted_servers[:5], 1):
        price_text = f"{int(server.price_rubles)} ₽" if server.price_kopeks > 0 else texts.t("ADMIN_SRV_FREE", "Free")
        text += f"{i}. {server.display_name} - {price_text}\n"
    
    if not sorted_servers:
        text += texts.t("ADMIN_SRV_NO_AVAILABLE", "No available servers\n")
    
    keyboard = [
        [
            types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_REFRESH", "🔄 Refresh"), callback_data="admin_servers_stats"),
            types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_LIST", "📋 List"), callback_data="admin_servers_list")
        ],
        [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_servers")]
    ]
    
    await callback.message.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@admin_required
@error_handler
async def start_server_edit_country(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    server_id = int(callback.data.split('_')[-1])
    server = await get_server_squad_by_id(db, server_id)
    
    if not server:
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found!"), show_alert=True)
        return
    
    await state.set_data({'server_id': server_id})
    await state.set_state(AdminStates.editing_server_country)
    
    current_country = server.country_code or texts.t("ADMIN_SRV_NOT_SPECIFIED", "Not specified")
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_SRV_EDIT_COUNTRY_PROMPT",
            "🌍 <b>Country code editing</b>\n\nCurrent country code: <b>{country}</b>\n\nSend new country code (e.g.: RU, US, DE) or '-' to remove:"
        ).format(country=current_country),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"admin_server_edit_{server_id}")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def process_server_country_edit(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    server_id = data.get('server_id')
    
    new_country = message.text.strip().upper()
    
    if new_country == "-":
        new_country = None
    elif len(new_country) > 5:
        await message.answer(texts.t("ADMIN_SRV_COUNTRY_TOO_LONG", "❌ Country code too long (max 5 characters)"))
        return
    
    server = await update_server_squad(db, server_id, country_code=new_country)
    
    if server:
        await state.clear()
        
        await cache.delete_pattern("available_countries*")
        
        country_text = new_country or texts.t("ADMIN_SRV_REMOVED", "Removed")
        await message.answer(
            texts.t("ADMIN_SRV_COUNTRY_CHANGED", "✅ Country code changed to: <b>{country}</b>").format(country=country_text),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_TO_SERVER", "🔙 To server"), callback_data=f"admin_server_edit_{server_id}")]
            ]),
            parse_mode="HTML"
        )
    else:
        await message.answer(texts.t("ADMIN_SRV_UPDATE_ERROR", "❌ Error updating server"))


@admin_required
@error_handler
async def start_server_edit_limit(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    server_id = int(callback.data.split('_')[-1])
    server = await get_server_squad_by_id(db, server_id)
    
    if not server:
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found!"), show_alert=True)
        return
    
    await state.set_data({'server_id': server_id})
    await state.set_state(AdminStates.editing_server_limit)
    
    current_limit = server.max_users or texts.t("ADMIN_SRV_NO_LIMIT", "No limit")
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_SRV_EDIT_LIMIT_PROMPT",
            "👥 <b>User limit editing</b>\n\nCurrent limit: <b>{limit}</b>\n\nSend new user limit (number) or 0 for unlimited access:"
        ).format(limit=current_limit),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"admin_server_edit_{server_id}")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def process_server_limit_edit(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    server_id = data.get('server_id')
    
    try:
        limit = int(message.text.strip())
        
        if limit < 0:
            await message.answer(texts.t("ADMIN_SRV_LIMIT_NEGATIVE", "❌ Limit cannot be negative"))
            return
        
        if limit > 10000:
            await message.answer(texts.t("ADMIN_SRV_LIMIT_TOO_HIGH", "❌ Limit too high (max 10,000)"))
            return
        
        max_users = limit if limit > 0 else None
        
        server = await update_server_squad(db, server_id, max_users=max_users)
        
        if server:
            await state.clear()
            
            limit_text = texts.t("ADMIN_SRV_LIMIT_USERS", "{limit} users").format(limit=limit) if limit > 0 else texts.t("ADMIN_SRV_NO_LIMIT", "No limit")
            await message.answer(
                texts.t("ADMIN_SRV_LIMIT_CHANGED", "✅ User limit changed to: <b>{limit}</b>").format(limit=limit_text),
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_TO_SERVER", "🔙 To server"), callback_data=f"admin_server_edit_{server_id}")]
                ]),
                parse_mode="HTML"
            )
        else:
            await message.answer(texts.t("ADMIN_SRV_UPDATE_ERROR", "❌ Error updating server"))
    
    except ValueError:
        await message.answer(texts.t("ADMIN_SRV_LIMIT_INVALID", "❌ Invalid number format. Enter an integer."))


@admin_required
@error_handler
async def start_server_edit_description(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    server_id = int(callback.data.split('_')[-1])
    server = await get_server_squad_by_id(db, server_id)
    
    if not server:
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found!"), show_alert=True)
        return
    
    await state.set_data({'server_id': server_id})
    await state.set_state(AdminStates.editing_server_description)
    
    current_desc = server.description or texts.t("ADMIN_SRV_NOT_SPECIFIED", "Not specified")
    
    await callback.message.edit_text(
        texts.t(
            "ADMIN_SRV_EDIT_DESC_PROMPT",
            "📝 <b>Description editing</b>\n\nCurrent description:\n<i>{desc}</i>\n\nSend new server description or '-' to remove:"
        ).format(desc=current_desc),
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text=texts.t("ADMIN_BTN_CANCEL", "❌ Cancel"), callback_data=f"admin_server_edit_{server_id}")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_required
@error_handler
async def process_server_description_edit(
    message: types.Message,
    state: FSMContext,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    server_id = data.get('server_id')
    
    new_description = message.text.strip()
    
    if new_description == "-":
        new_description = None
    elif len(new_description) > 1000:
        await message.answer(texts.t("ADMIN_SRV_DESC_TOO_LONG", "❌ Description too long (max 1000 characters)"))
        return
    
    server = await update_server_squad(db, server_id, description=new_description)

    if server:
        await state.clear()

        desc_text = new_description or texts.t("ADMIN_SRV_REMOVED", "Removed")
        await cache.delete_pattern("available_countries*")
        await message.answer(
            texts.t("ADMIN_SRV_DESC_CHANGED", "✅ Server description changed:\n\n<i>{desc}</i>").format(desc=desc_text),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_TO_SERVER", "🔙 To server"), callback_data=f"admin_server_edit_{server_id}")]
            ]),
            parse_mode="HTML"
        )
    else:
        await message.answer(texts.t("ADMIN_SRV_UPDATE_ERROR", "❌ Error updating server"))


@admin_required
@error_handler
async def start_server_edit_promo_groups(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    server_id = int(callback.data.split('_')[-1])
    server = await get_server_squad_by_id(db, server_id)

    if not server:
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found!"), show_alert=True)
        return

    promo_groups_data = await get_promo_groups_with_counts(db)
    promo_groups = [
        {"id": group.id, "name": group.name, "is_default": group.is_default}
        for group, _ in promo_groups_data
    ]

    if not promo_groups:
        await callback.answer(texts.t("ADMIN_SRV_NO_PROMO_GROUPS", "❌ No promo groups found"), show_alert=True)
        return

    selected_ids = {pg.id for pg in server.allowed_promo_groups}
    if not selected_ids:
        default_group = next((pg for pg in promo_groups if pg["is_default"]), None)
        if default_group:
            selected_ids.add(default_group["id"])

    await state.set_state(AdminStates.editing_server_promo_groups)
    await state.set_data(
        {
            "server_id": server_id,
            "promo_groups": promo_groups,
            "selected_promo_groups": list(selected_ids),
            "server_name": server.display_name,
        }
    )

    text = texts.t(
        "ADMIN_SRV_PROMO_GROUPS_PROMPT",
        "🎯 <b>Promo groups setup</b>\n\nServer: <b>{name}</b>\n\nSelect promo groups that will have access to this server.\nAt least one promo group must be selected."
    ).format(name=server.display_name)

    await callback.message.edit_text(
        text,
        reply_markup=_build_server_promo_groups_keyboard(server_id, promo_groups, selected_ids, db_user.language),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_required
@error_handler
async def toggle_server_promo_group(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    parts = callback.data.split('_')
    server_id = int(parts[4])
    group_id = int(parts[5])

    data = await state.get_data()
    if not data or data.get("server_id") != server_id:
        await callback.answer(texts.t("ADMIN_SRV_SESSION_EXPIRED", "⚠️ Editing session expired"), show_alert=True)
        return

    selected = set(int(pg_id) for pg_id in data.get("selected_promo_groups", []))
    promo_groups = data.get("promo_groups", [])

    if group_id in selected:
        if len(selected) == 1:
            await callback.answer(texts.t("ADMIN_SRV_CANT_DISABLE_LAST", "⚠️ Cannot disable last promo group"), show_alert=True)
            return
        selected.remove(group_id)
        message = texts.t("ADMIN_SRV_PROMO_DISABLED", "Promo group disabled")
    else:
        selected.add(group_id)
        message = texts.t("ADMIN_SRV_PROMO_ADDED", "Promo group added")

    await state.update_data(selected_promo_groups=list(selected))

    await callback.message.edit_reply_markup(
        reply_markup=_build_server_promo_groups_keyboard(server_id, promo_groups, selected, db_user.language)
    )
    await callback.answer(message)


@admin_required
@error_handler
async def save_server_promo_groups(
    callback: types.CallbackQuery,
    state: FSMContext,
    db_user: User,
    db: AsyncSession,
):
    texts = get_texts(db_user.language)
    data = await state.get_data()
    if not data:
        await callback.answer(texts.t("ADMIN_SRV_NO_DATA", "⚠️ No data to save"), show_alert=True)
        return

    server_id = data.get("server_id")
    selected = data.get("selected_promo_groups", [])

    if not selected:
        await callback.answer(texts.t("ADMIN_SRV_SELECT_PROMO", "❌ Select at least one promo group"), show_alert=True)
        return

    try:
        server = await update_server_squad_promo_groups(db, server_id, selected)
    except ValueError as exc:
        await callback.answer(f"❌ {exc}", show_alert=True)
        return

    if not server:
        await callback.answer(texts.t("ADMIN_SRV_NOT_FOUND", "❌ Server not found"), show_alert=True)
        return

    await cache.delete_pattern("available_countries*")
    await state.clear()

    text, keyboard = _build_server_edit_view(server, db_user.language)

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    await callback.answer(texts.t("ADMIN_SRV_PROMO_UPDATED", "✅ Promo groups updated!"))


@admin_required
@error_handler
async def sync_server_user_counts_handler(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    texts = get_texts(db_user.language)
    await callback.message.edit_text(
        texts.t("ADMIN_SRV_SYNC_COUNTS_IN_PROGRESS", "🔄 Syncing user counters..."),
        reply_markup=None
    )
    
    try:
        from app.database.crud.server_squad import sync_server_user_counts
        
        updated_count = await sync_server_user_counts(db)
        
        text = texts.t(
            "ADMIN_SRV_SYNC_COUNTS_COMPLETE",
            """
✅ <b>Sync completed</b>

📊 <b>Result:</b>
• Servers updated: {count}

User counters synchronized with actual data.
"""
        ).format(count=updated_count)
        
        keyboard = [
            [
                types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_LIST", "📋 Server list"), callback_data="admin_servers_list"),
                types.InlineKeyboardButton(text=texts.t("ADMIN_SRV_BTN_REPEAT", "🔄 Repeat"), callback_data="admin_servers_sync_counts")
            ],
            [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_servers")]
        ]
        
        await callback.message.edit_text(
            text,
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    except Exception as e:
        logger.error(f"User counts sync error: {e}")
        await callback.message.edit_text(
            texts.t("ADMIN_SRV_SYNC_ERROR", "❌ Sync error: {error}").format(error=str(e)),
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text=texts.BACK, callback_data="admin_servers")]
            ])
        )
    
    await callback.answer()


@admin_required
@error_handler  
async def handle_servers_pagination(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    
    page = int(callback.data.split('_')[-1])
    await show_servers_list(callback, db_user, db, page)


def register_handlers(dp: Dispatcher):
    
    dp.callback_query.register(show_servers_menu, F.data == "admin_servers")
    dp.callback_query.register(show_servers_list, F.data == "admin_servers_list")
    dp.callback_query.register(sync_servers_with_remnawave, F.data == "admin_servers_sync")
    dp.callback_query.register(sync_server_user_counts_handler, F.data == "admin_servers_sync_counts")
    dp.callback_query.register(show_server_detailed_stats, F.data == "admin_servers_stats")
    
    dp.callback_query.register(
        show_server_edit_menu,
        F.data.startswith("admin_server_edit_")
        & ~F.data.contains("name")
        & ~F.data.contains("price")
        & ~F.data.contains("country")
        & ~F.data.contains("limit")
        & ~F.data.contains("desc")
        & ~F.data.contains("promo"),
    )
    dp.callback_query.register(toggle_server_availability, F.data.startswith("admin_server_toggle_"))
    dp.callback_query.register(toggle_server_trial_assignment, F.data.startswith("admin_server_trial_"))
    dp.callback_query.register(show_server_users, F.data.startswith("admin_server_users_"))

    dp.callback_query.register(start_server_edit_name, F.data.startswith("admin_server_edit_name_"))
    dp.callback_query.register(start_server_edit_price, F.data.startswith("admin_server_edit_price_"))
    dp.callback_query.register(start_server_edit_country, F.data.startswith("admin_server_edit_country_"))
    dp.callback_query.register(start_server_edit_promo_groups, F.data.startswith("admin_server_edit_promo_"))
    dp.callback_query.register(start_server_edit_limit, F.data.startswith("admin_server_edit_limit_"))         
    dp.callback_query.register(start_server_edit_description, F.data.startswith("admin_server_edit_desc_"))     
    
    dp.message.register(process_server_name_edit, AdminStates.editing_server_name)
    dp.message.register(process_server_price_edit, AdminStates.editing_server_price)
    dp.message.register(process_server_country_edit, AdminStates.editing_server_country)            
    dp.message.register(process_server_limit_edit, AdminStates.editing_server_limit)                
    dp.message.register(process_server_description_edit, AdminStates.editing_server_description)
    dp.callback_query.register(toggle_server_promo_group, F.data.startswith("admin_server_promo_toggle_"))
    dp.callback_query.register(save_server_promo_groups, F.data.startswith("admin_server_promo_save_"))
    
    dp.callback_query.register(delete_server_confirm, F.data.startswith("admin_server_delete_") & ~F.data.contains("confirm"))
    dp.callback_query.register(delete_server_execute, F.data.startswith("admin_server_delete_confirm_"))
    
    dp.callback_query.register(handle_servers_pagination, F.data.startswith("admin_servers_list_page_"))
