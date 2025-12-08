import logging
from aiogram import types
from app.config import settings
from app.database.database import get_db
from app.database.crud.user import get_user_by_id, add_user_balance
from app.database.crud.transaction import create_transaction, get_transaction_by_external_id
from app.database.models import TransactionType, PaymentMethod
from app.localization.loader import DEFAULT_LANGUAGE
from app.localization.texts import get_texts

logger = logging.getLogger(__name__)


async def handle_successful_payment(message: types.Message):
    try:
        payment = message.successful_payment
        
        payload_parts = payment.invoice_payload.split('_')
        if len(payload_parts) >= 3 and payload_parts[0] == 'balance':
            user_id = int(payload_parts[1])
            amount_kopeks = int(payload_parts[2])
            
            async for db in get_db():
                try:
                    existing_transaction = await get_transaction_by_external_id(
                        db, payment.telegram_payment_charge_id, PaymentMethod.TELEGRAM_STARS
                    )
                    
                    if existing_transaction:
                        logger.info("Stars payment %s already processed", payment.telegram_payment_charge_id)
                        return
                    
                    user = await get_user_by_id(db, user_id)
                    language = getattr(user, "language", DEFAULT_LANGUAGE)
                    texts = get_texts(language)
                    
                    if user:
                        await add_user_balance(
                            db, user, amount_kopeks,
                            texts.t("STARS_TOPUP_DESCRIPTION", "Top up via Telegram Stars")
                        )
                        
                        await create_transaction(
                            db=db,
                            user_id=user.id,
                            type=TransactionType.DEPOSIT,
                            amount_kopeks=amount_kopeks,
                            description=texts.t("STARS_TOPUP_DESCRIPTION", "Top up via Telegram Stars"),
                            payment_method=PaymentMethod.TELEGRAM_STARS,
                            external_id=payment.telegram_payment_charge_id
                        )
                        
                        await message.answer(
                            texts.t(
                                "STARS_TOPUP_SUCCESS",
                                "✅ Balance credited by {amount}!",
                            ).format(amount=settings.format_price(amount_kopeks))
                            + "\n\n"
                            + texts.t(
                                "STARS_TOPUP_IMPORTANT",
                                "⚠️ <b>Important:</b> Balance top-up does not activate a subscription automatically. Please activate the subscription separately.",
                            )
                            + "\n\n"
                            + texts.t(
                                "STARS_TOPUP_AUTOBUY",
                                "🔄 If a saved cart and auto-purchase are enabled, the subscription will be bought automatically after top-up.",
                            )
                        )
                        
                        logger.info("✅ Processed Stars payment: %s", payment.telegram_payment_charge_id)
                
                except Exception as e:
                    logger.error("Error processing Stars payment: %s", e)
                    await db.rollback()
                finally:
                    break
        
    except Exception as e:
        logger.error("Error in Stars payment handler: %s", e)


async def handle_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    try:
        await pre_checkout_query.answer(ok=True)
        logger.info("Pre-checkout query accepted: %s", pre_checkout_query.id)
        
    except Exception as e:
        logger.error("Error in pre-checkout query: %s", e)
        error_texts = get_texts(DEFAULT_LANGUAGE)
        await pre_checkout_query.answer(
            ok=False,
            error_message=error_texts.t("PAYMENT_PROCESSING_ERROR", "Payment processing error"),
        )