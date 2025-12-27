"""Payment methods management handlers for tenant bots."""
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
from app.database.crud.tenant_payment_card import get_payment_cards


@admin_required
@error_handler
async def show_bot_payment_cards(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show payment cards for a bot."""
    texts = get_texts(db_user.language)
    
    try:
        parts = callback.data.split(":")
        bot_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
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
    
    cards = await get_payment_cards(db, bot_id, active_only=False)
    page_size = 5
    total_pages = (len(cards) + page_size - 1) // page_size
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_cards = cards[start_idx:end_idx]
    
    text = texts.t(
        "ADMIN_TENANT_BOT_CARDS_TITLE",
        """💳 <b>Payment Cards</b>
Bot: <b>{bot_name}</b>

Page {page} of {total_pages}
"""
    ).format(
        bot_name=bot.name,
        page=page + 1,
        total_pages=max(1, total_pages)
    )
    
    if not page_cards:
        text += texts.t("ADMIN_TENANT_BOT_CARDS_EMPTY", "No payment cards found.")
    else:
        for card in page_cards:
            status_icon = "✅" if card.is_active else "❌"
            masked_number = f"****{card.card_number[-4:]}" if len(card.card_number) > 4 else "****"
            text += f"\n{status_icon} <b>{masked_number}</b>\n"
            text += f"   • Holder: {card.card_holder_name}\n"
            text += f"   • Strategy: {card.rotation_strategy}\n"
            text += f"   • Uses: {card.success_count + card.failure_count}\n"
    
    keyboard_buttons = []
    
    # Add card button
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=texts.t("ADMIN_TENANT_BOT_CARDS_ADD", "➕ Add Card"),
            callback_data=f"admin_tenant_bot_card_add:{bot_id}"
        )
    ])
    
    # Card buttons
    for card in page_cards:
        keyboard_buttons.append([
            types.InlineKeyboardButton(
                text=f"{'✅' if card.is_active else '❌'} Card {card.id}",
                callback_data=f"admin_tenant_bot_card_detail:{card.id}"
            )
        ])
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            types.InlineKeyboardButton(
                text="⬅️ Previous",
                callback_data=f"admin_tenant_bot_cards:{bot_id}:{page - 1}"
            )
        )
    if end_idx < len(cards):
        nav_buttons.append(
            types.InlineKeyboardButton(
                text="Next ➡️",
                callback_data=f"admin_tenant_bot_cards:{bot_id}:{page + 1}"
            )
        )
    if nav_buttons:
        keyboard_buttons.append(nav_buttons)
    
    # Back button
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data=f"admin_tenant_bot_detail:{bot_id}"
        )
    ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def show_bot_payment_methods(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show payment methods management for a bot (AC7)."""
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
    
    # Get payment method statuses using BotConfigService
    card_to_card_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'card_to_card')
    zarinpal_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'zarinpal')
    yookassa_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'yookassa')
    cryptobot_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'cryptobot')
    pal24_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'pal24')
    mulenpay_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'mulenpay')
    heleket_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'heleket')
    tribute_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'tribute')
    wata_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'wata')
    telegram_stars_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'telegram_stars')
    
    # Get card-to-card cards count
    cards = await get_payment_cards(db, bot_id, active_only=True)
    card_count = len(cards)
    card_receipt_topic_id = await BotConfigService.get_config(db, bot_id, 'CARD_RECEIPT_TOPIC_ID')
    
    # Get Zarinpal config
    zarinpal_merchant_id = await BotConfigService.get_config(db, bot_id, 'ZARINPAL_MERCHANT_ID')
    zarinpal_sandbox = await BotConfigService.get_config(db, bot_id, 'ZARINPAL_SANDBOX', False)
    
    text = texts.t(
        "ADMIN_TENANT_BOT_PAYMENTS",
        """💳 <b>Payment Methods: {name}</b>

<b>Payment Gateways:</b>
{card_to_card_status} Card-to-Card
  • Active cards: {card_count}
  • Receipt topic: {receipt_topic}

{zarinpal_status} Zarinpal
  • Merchant ID: {zarinpal_merchant}
  • Sandbox: {zarinpal_sandbox}

{yookassa_status} YooKassa
{cryptobot_status} CryptoBot
{pal24_status} Pal24
{mulenpay_status} MulenPay
{heleket_status} Heleket
{tribute_status} Tribute
{wata_status} WATA
{telegram_stars_status} Telegram Stars

Select payment method to configure:"""
    ).format(
        name=bot.name,
        card_to_card_status="✅" if card_to_card_enabled else "❌",
        card_count=card_count,
        receipt_topic=card_receipt_topic_id if card_receipt_topic_id else "Not set",
        zarinpal_status="✅" if zarinpal_enabled else "❌",
        zarinpal_merchant=zarinpal_merchant_id[:20] + "..." if zarinpal_merchant_id and len(zarinpal_merchant_id) > 20 else (zarinpal_merchant_id or "Not set"),
        zarinpal_sandbox="Yes" if zarinpal_sandbox else "No",
        yookassa_status="✅" if yookassa_enabled else "❌",
        cryptobot_status="✅" if cryptobot_enabled else "❌",
        pal24_status="✅" if pal24_enabled else "❌",
        mulenpay_status="✅" if mulenpay_enabled else "❌",
        heleket_status="✅" if heleket_enabled else "❌",
        tribute_status="✅" if tribute_enabled else "❌",
        wata_status="✅" if wata_enabled else "❌",
        telegram_stars_status="✅" if telegram_stars_enabled else "❌",
    )
    
    keyboard_buttons = []
    
    # Payment method buttons
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=f"{'🔴 Disable' if card_to_card_enabled else '🟢 Enable'} Card-to-Card",
            callback_data=f"admin_tenant_bot_toggle_payment:card_to_card:{bot_id}"
        )
    ])
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text="⚙️ Configure Card-to-Card",
            callback_data=f"admin_tenant_bot_cards:{bot_id}:0"
        )
    ])
    
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=f"{'🔴 Disable' if zarinpal_enabled else '🟢 Enable'} Zarinpal",
            callback_data=f"admin_tenant_bot_toggle_payment:zarinpal:{bot_id}"
        )
    ])
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text="⚙️ Configure Zarinpal",
            callback_data=f"admin_tenant_bot_zarinpal:{bot_id}"
        )
    ])
    
    # Other gateways (toggle only for now)
    other_gateways = [
        ("yookassa", "YooKassa"),
        ("cryptobot", "CryptoBot"),
        ("pal24", "Pal24"),
        ("mulenpay", "MulenPay"),
        ("heleket", "Heleket"),
        ("tribute", "Tribute"),
        ("wata", "WATA"),
        ("telegram_stars", "Telegram Stars"),
    ]
    
    for gateway_key, gateway_name in other_gateways:
        gateway_enabled = await BotConfigService.is_feature_enabled(db, bot_id, gateway_key)
        keyboard_buttons.append([
            types.InlineKeyboardButton(
                text=f"{'🔴 Disable' if gateway_enabled else '🟢 Enable'} {gateway_name}",
                callback_data=f"admin_tenant_bot_toggle_payment:{gateway_key}:{bot_id}"
            )
        ])
    
    # Back button
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data=f"admin_tenant_bot_detail:{bot_id}"
        )
    ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def toggle_payment_method(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Toggle a payment method for a bot (AC7)."""
    texts = get_texts(db_user.language)
    
    try:
        parts = callback.data.split(":")
        payment_key = parts[1]  # e.g., "card_to_card", "zarinpal"
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
    
    # Get current value and toggle using BotConfigService
    current_value = await BotConfigService.is_feature_enabled(db, bot_id, payment_key)
    new_value = not current_value
    await BotConfigService.set_feature_enabled(db, bot_id, payment_key, new_value)
    
    # Payment method display names
    payment_names = {
        'card_to_card': 'Card-to-Card',
        'zarinpal': 'Zarinpal',
        'yookassa': 'YooKassa',
        'cryptobot': 'CryptoBot',
        'pal24': 'Pal24',
        'mulenpay': 'MulenPay',
        'heleket': 'Heleket',
        'tribute': 'Tribute',
        'wata': 'WATA',
        'telegram_stars': 'Telegram Stars',
    }
    
    payment_name = payment_names.get(payment_key, payment_key)
    status_text = "enabled" if new_value else "disabled"
    await callback.answer(f"✅ {payment_name} {status_text}")
    
    # Refresh payment methods view
    await show_bot_payment_methods(callback, db_user, db)


@admin_required
@error_handler
async def show_zarinpal_config(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show Zarinpal configuration for a bot (AC7)."""
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
    
    # Get Zarinpal status and config
    zarinpal_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'zarinpal')
    zarinpal_merchant_id = await BotConfigService.get_config(db, bot_id, 'ZARINPAL_MERCHANT_ID')
    zarinpal_sandbox = await BotConfigService.get_config(db, bot_id, 'ZARINPAL_SANDBOX', False)
    
    text = texts.t(
        "ADMIN_TENANT_BOT_ZARINPAL_CONFIG",
        """💳 <b>Zarinpal Configuration: {name}</b>

<b>Status:</b> {status}

<b>Configuration:</b>
• Merchant ID: {merchant_id}
• Sandbox Mode: {sandbox}

Select action:"""
    ).format(
        name=bot.name,
        status="✅ Enabled" if zarinpal_enabled else "❌ Disabled",
        merchant_id=zarinpal_merchant_id or "Not set",
        sandbox="Yes" if zarinpal_sandbox else "No"
    )
    
    keyboard_buttons = []
    
    # Toggle button (use existing callback for backward compatibility)
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=f"{'🔴 Disable' if zarinpal_enabled else '🟢 Enable'} Zarinpal",
            callback_data=f"admin_tenant_bot_toggle_zarinpal:{bot_id}"
        )
    ])
    
    # Edit buttons (FSM states would be needed for editing)
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text="✏️ Edit Merchant ID",
            callback_data=f"admin_tenant_bot_edit_zarinpal_merchant:{bot_id}"
        )
    ])
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text="✏️ Toggle Sandbox",
            callback_data=f"admin_tenant_bot_toggle_zarinpal_sandbox:{bot_id}"
        )
    ])
    
    # Back button
    keyboard_buttons.append([
        types.InlineKeyboardButton(
            text=texts.BACK,
            callback_data=f"admin_tenant_bot_payments:{bot_id}"
        )
    ])
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def toggle_zarinpal_sandbox(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Toggle Zarinpal sandbox mode for a bot (AC7)."""
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
    
    # Get current value and toggle
    current_value = await BotConfigService.get_config(db, bot_id, 'ZARINPAL_SANDBOX', False)
    new_value = not current_value
    await BotConfigService.set_config(db, bot_id, 'ZARINPAL_SANDBOX', new_value)
    
    status_text = "enabled" if new_value else "disabled"
    await callback.answer(f"✅ Sandbox mode {status_text}")
    
    # Refresh Zarinpal config view
    await show_zarinpal_config(callback, db_user, db)


