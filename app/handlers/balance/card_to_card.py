import logging
from datetime import datetime
from aiogram import Dispatcher, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import User
from app.database.crud.bot import get_bot_by_id
from app.database.crud.tenant_payment_card import get_next_card_for_rotation, update_card_usage
from app.services.bot_config_service import BotConfigService
from app.database.crud.card_to_card_payment import (
    create_card_payment,
    get_payment_by_id,
    update_payment_status
)
from app.database.crud.transaction import create_transaction
from app.database.crud.user import add_user_balance
from app.keyboards.inline import get_back_keyboard
from app.localization.texts import get_texts
from app.states import BalanceStates
from app.utils.decorators import error_handler
from app.services.admin_notification_service import AdminNotificationService

logger = logging.getLogger(__name__)


@error_handler
async def start_card_to_card_payment(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    bot_id: int = None,
):
    """Start card-to-card payment flow."""
    texts = get_texts(db_user.language)
    
    # Get bot_id from user if not provided
    if bot_id is None:
        bot_id = getattr(db_user, 'bot_id', None)
        if bot_id is None:
            await callback.answer(
                texts.t("PAYMENT_ERROR", "❌ Payment error occurred"),
                show_alert=True
            )
            return
    
    # Get bot config
    bot_config = await get_bot_by_id(db, bot_id)
    if not bot_config:
        await callback.answer(
            texts.t("PAYMENT_ERROR", "❌ Payment error occurred"),
            show_alert=True
        )
        return
    
    # Check if card-to-card is enabled using BotConfigService
    card_to_card_enabled = await BotConfigService.is_feature_enabled(db, bot_id, 'card_to_card')
    if not card_to_card_enabled:
        await callback.answer(
            texts.t("CARD_TO_CARD_DISABLED", "❌ Card-to-card payments are disabled for this bot"),
            show_alert=True
        )
        return
    
    # Get next card (with rotation)
    card = await get_next_card_for_rotation(db, bot_id, strategy='round_robin')
    if not card:
        await callback.answer(
            texts.t(
                "CARD_TO_CARD_NO_CARD",
                "❌ No payment card available. Please contact support."
            ),
            show_alert=True
        )
        return
    
    # Get amount from state data
    state_data = await state.get_data()
    amount_toman = state_data.get('amount_toman', 0)
    
    if not amount_toman or amount_toman <= 0:
        await callback.answer(
            texts.t("CARD_TO_CARD_NO_AMOUNT", "❌ Please select an amount first"),
            show_alert=True
        )
        return
    
    # Format amount
    amount_rub = amount_toman / 100
    
    # Build card info message
    card_info = texts.t(
        "CARD_TO_CARD_INFO",
        """💳 <b>Card-to-Card Payment</b>

<b>Card Number:</b> <code>{card_number}</code>
<b>Card Holder:</b> {card_holder}

<b>Amount:</b> {amount}  Toman

Please send the payment receipt.
You can send an image, text, or both."""
    ).format(
        card_number=card.card_number,
        card_holder=card.card_holder_name,
        amount=f"{amount_rub:,.2f}".replace(',', ' ')
    )
    
    await callback.message.edit_text(
        card_info,
        reply_markup=get_back_keyboard(db_user.language),
        parse_mode="HTML"
    )
    
    # Save card_id and amount in state
    await state.update_data(
        card_id=card.id,
        amount_toman=amount_toman,
        payment_method="card_to_card"
    )
    await state.set_state(BalanceStates.waiting_for_card_to_card_receipt)
    await callback.answer()


@error_handler
async def handle_card_to_card_receipt(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
    bot_id: int = None,
):
    """Process received receipt."""
    texts = get_texts(db_user.language)
    
    # Get bot_id from user if not provided
    if bot_id is None:
        bot_id = getattr(db_user, 'bot_id', None)
        if bot_id is None:
            await message.answer(
                texts.t("PAYMENT_ERROR", "❌ Payment error occurred")
            )
            return
    
    data = await state.get_data()
    card_id = data.get('card_id')
    amount_toman = data.get('amount_toman', 0)
    
    if not card_id or not amount_toman:
        await message.answer(
            texts.t("CARD_TO_CARD_SESSION_EXPIRED", "❌ Session expired. Please start over.")
        )
        await state.clear()
        return
    
    # Extract receipt data
    receipt_type = None
    receipt_text = None
    receipt_image_file_id = None
    
    if message.photo:
        receipt_image_file_id = message.photo[-1].file_id
        receipt_type = 'image'
        if message.caption:
            receipt_text = message.caption
            receipt_type = 'both'
    elif message.text:
        receipt_text = message.text
        receipt_type = 'text'
    else:
        await message.answer(
            texts.t(
                "CARD_TO_CARD_INVALID_RECEIPT",
                "❌ Please send an image or text receipt"
            )
        )
        return
    
    try:
        # Create payment record
        payment = await create_card_payment(
            db=db,
            bot_id=bot_id,
            user_id=db_user.id,
            amount_toman=amount_toman,
            card_id=card_id,
            receipt_type=receipt_type,
            receipt_text=receipt_text,
            receipt_image_file_id=receipt_image_file_id,
            status='pending'
        )
        
        # Update card usage
        await update_card_usage(db, card_id, success=False)  # Will be updated on approval
        
        # Send notification to admin
        await send_admin_notification(db, bot_id, payment, message.bot)
        
        # Confirm to user
        await message.answer(
            texts.t(
                "CARD_TO_CARD_RECEIPT_RECEIVED",
                """✅ Your receipt has been received.

<b>Tracking Number:</b> <code>{tracking}</code>

After review, you will be notified of the result."""
            ).format(tracking=payment.tracking_number),
            parse_mode="HTML"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error processing card-to-card receipt: {e}", exc_info=True)
        await message.answer(
            texts.t("PAYMENT_ERROR", "❌ Payment error occurred. Please try again.")
        )


async def send_admin_notification(
    db: AsyncSession,
    bot_id: int,
    payment,
    bot: Bot
):
    """Send payment notification to admin for review."""
    try:
        bot_config = await get_bot_by_id(db, bot_id)
        if not bot_config:
            logger.warning(f"Bot {bot_id} not found")
            return
        
        # Get admin configs using BotConfigService
        admin_chat_id = await BotConfigService.get_config(db, bot_id, 'ADMIN_NOTIFICATIONS_CHAT_ID')
        if not admin_chat_id:
            logger.warning(f"No admin chat configured for bot {bot_id}")
            return
        
        card_receipt_topic_id = await BotConfigService.get_config(db, bot_id, 'CARD_RECEIPT_TOPIC_ID')
        
        from app.database.crud.user import get_user_by_id
        user = await get_user_by_id(db, payment.user_id)
        if not user:
            logger.warning(f"User {payment.user_id} not found")
            return
        
        # Build notification message
        amount_rub = payment.amount_toman / 100
        message_text = f"""🔔 <b>Card-to-Card Payment Request</b>

👤 <b>User:</b> @{user.username or 'N/A'} ({user.telegram_id})
💰 <b>Amount:</b> {amount_rub:,.2f}  Toman
🔢 <b>Tracking:</b> <code>{payment.tracking_number}</code>
📅 <b>Date:</b> {payment.created_at.strftime('%Y-%m-%d %H:%M')}
💳 <b>Card:</b> {payment.card.card_number if payment.card else 'N/A'}"""
        
        if payment.receipt_text:
            message_text += f"\n📝 <b>Receipt Text:</b> {payment.receipt_text[:200]}"
        
        # Build inline keyboard
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="✅ Approve",
                    callback_data=f"approve_card_payment:{payment.id}"
                ),
                types.InlineKeyboardButton(
                    text="❌ Reject",
                    callback_data=f"reject_card_payment:{payment.id}"
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="📋 Details",
                    callback_data=f"card_payment_details:{payment.id}"
                )
            ]
        ])
        
        # Send to admin
        try:
            if card_receipt_topic_id:
                await bot.send_message(
                    chat_id=admin_chat_id,
                    message_thread_id=card_receipt_topic_id,
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=admin_chat_id,
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            
            # Send receipt image if available
            if payment.receipt_image_file_id:
                try:
                    if card_receipt_topic_id:
                        await bot.send_photo(
                            chat_id=admin_chat_id,
                            photo=payment.receipt_image_file_id,
                            message_thread_id=card_receipt_topic_id
                        )
                    else:
                        await bot.send_photo(
                            chat_id=admin_chat_id,
                            photo=payment.receipt_image_file_id
                        )
                except Exception as photo_error:
                    logger.warning(f"Failed to send receipt photo: {photo_error}")
        
        except Exception as send_error:
            logger.error(f"Failed to send admin notification: {send_error}", exc_info=True)
    
    except Exception as e:
        logger.error(f"Error in send_admin_notification: {e}", exc_info=True)


@error_handler
async def handle_payment_approval(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    bot_id: int = None,
):
    """Approve card-to-card payment."""
    texts = get_texts(db_user.language)
    
    # Get bot_id from user if not provided
    if bot_id is None:
        bot_id = getattr(db_user, 'bot_id', None)
    
    if not settings.is_admin(db_user.telegram_id):
        await callback.answer(
            texts.t("ACCESS_DENIED", "❌ Access denied"),
            show_alert=True
        )
        return
    
    try:
        payment_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    # Get payment
    payment = await get_payment_by_id(db, payment_id, bot_id=bot_id)
    if not payment:
        await callback.answer(
            texts.t("PAYMENT_NOT_FOUND", "❌ Payment not found"),
            show_alert=True
        )
        return
    
    if payment.status != 'pending':
        await callback.answer(
            texts.t("PAYMENT_ALREADY_REVIEWED", "❌ This payment has already been reviewed"),
            show_alert=True
        )
        return
    
    try:
        # Update payment status
        await update_payment_status(
            db=db,
            payment_id=payment_id,
            status='approved',
            admin_reviewed_by=db_user.id,
            admin_notes=None,
            bot_id=bot_id
        )
        
        # Create transaction
        from app.database.crud.transaction import create_transaction
        from app.database.models import TransactionType, PaymentMethod
        transaction = await create_transaction(
            db=db,
            user_id=payment.user_id,
            type=TransactionType.DEPOSIT,
            amount_toman=payment.amount_toman,
            description=f"Card-to-card payment {payment.tracking_number}",
            payment_method=None,  # card_to_card not in PaymentMethod enum yet
            bot_id=bot_id
        )
        
        # Update payment with transaction_id
        await update_payment_status(
            db=db,
            payment_id=payment_id,
            status='approved',
            transaction_id=transaction.id,
            bot_id=bot_id
        )
        
        # Add balance to user
        from app.database.crud.user import get_user_by_id
        user = await get_user_by_id(db, payment.user_id)
        if user:
            await add_user_balance(
                db=db,
                user=user,
                amount_toman=payment.amount_toman,
                description=f"Card-to-card payment approved: {payment.tracking_number}",
                create_transaction=False  # Already created above
            )
            
            # Update card usage
            if payment.card_id:
                await update_card_usage(db, payment.card_id, success=True)
            
            # Notify user
            try:
                user_texts = get_texts(user.language)
                await callback.bot.send_message(
                    chat_id=user.telegram_id,
                    text=user_texts.t(
                        "CARD_TO_CARD_APPROVED",
                        """✅ Your payment has been approved.

<b>Tracking Number:</b> <code>{tracking}</code>
<b>Amount:</b> {amount}  Toman

Your balance has been updated."""
                    ).format(
                        tracking=payment.tracking_number,
                        amount=f"{payment.amount_toman / 100:,.2f}".replace(',', ' ')
                    ),
                    parse_mode="HTML"
                )
            except Exception as notify_error:
                logger.error(f"Failed to notify user: {notify_error}")
        
        # Update admin message
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ <b>Approved</b>",
                reply_markup=None,
                parse_mode="HTML"
            )
        except Exception:
            pass
        
        await callback.answer(texts.t("PAYMENT_APPROVED"), show_alert=True)
        
    except Exception as e:
        logger.error(f"Error approving payment: {e}", exc_info=True)
        await callback.answer(
            texts.t("PAYMENT_ERROR", "❌ Error processing payment"),
            show_alert=True
        )


@error_handler
async def handle_payment_rejection(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    bot_id: int = None,
):
    """Reject card-to-card payment."""
    texts = get_texts(db_user.language)
    
    # Get bot_id from user if not provided
    if bot_id is None:
        bot_id = getattr(db_user, 'bot_id', None)
    
    if not settings.is_admin(db_user.telegram_id):
        await callback.answer(
            texts.t("ACCESS_DENIED", "❌ Access denied"),
            show_alert=True
        )
        return
    
    try:
        payment_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    # Get payment
    payment = await get_payment_by_id(db, payment_id, bot_id=bot_id)
    if not payment:
        await callback.answer(
            texts.t("PAYMENT_NOT_FOUND", "❌ Payment not found"),
            show_alert=True
        )
        return
    
    if payment.status != 'pending':
        await callback.answer(
            texts.t("PAYMENT_ALREADY_REVIEWED", "❌ This payment has already been reviewed"),
            show_alert=True
        )
        return
    
    try:
        # Update payment status
        await update_payment_status(
            db=db,
            payment_id=payment_id,
            status='rejected',
            admin_reviewed_by=db_user.id,
            admin_notes=None,
            bot_id=bot_id
        )
        
        # Update card usage
        if payment.card_id:
            await update_card_usage(db, payment.card_id, success=False)
        
        # Notify user
        from app.database.crud.user import get_user_by_id
        user = await get_user_by_id(db, payment.user_id)
        if user:
            try:
                user_texts = get_texts(user.language)
                await callback.bot.send_message(
                    chat_id=user.telegram_id,
                    text=user_texts.t(
                        "CARD_TO_CARD_REJECTED",
                        """❌ Your payment has been rejected.

<b>Tracking Number:</b> <code>{tracking}</code>

Please contact support for more information."""
                    ).format(tracking=payment.tracking_number),
                    parse_mode="HTML"
                )
            except Exception as notify_error:
                logger.error(f"Failed to notify user: {notify_error}")
        
        # Update admin message
        try:
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ <b>Rejected</b>",
                reply_markup=None,
                parse_mode="HTML"
            )
        except Exception:
            pass
        
        await callback.answer(texts.t("PAYMENT_REJECTED"), show_alert=True)
        
    except Exception as e:
        logger.error(f"Error rejecting payment: {e}", exc_info=True)
        await callback.answer(
            texts.t("PAYMENT_ERROR", "❌ Error processing payment"),
            show_alert=True
        )


def register_card_to_card_handlers(dp: Dispatcher):
    """Register card-to-card payment handlers."""
    dp.callback_query.register(
        start_card_to_card_payment,
        F.data == "payment_card_to_card"
    )
    
    dp.message.register(
        handle_card_to_card_receipt,
        StateFilter(BalanceStates.waiting_for_card_to_card_receipt)
    )
    
    dp.callback_query.register(
        handle_payment_approval,
        F.data.startswith("approve_card_payment:")
    )
    
    dp.callback_query.register(
        handle_payment_rejection,
        F.data.startswith("reject_card_payment:")
    )
    
    logger.info("✅ Card-to-card payment handlers registered")
