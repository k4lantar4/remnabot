import logging
from aiogram import types
from app.config import settings
from app.database.database import get_db
from app.database.crud.user import get_user_by_id, add_user_balance
from app.database.crud.transaction import create_transaction, get_transaction_by_external_id
from app.database.models import TransactionType, PaymentMethod

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
                        logger.info(f"Stars платеж {payment.telegram_payment_charge_id} уже обработан")
                        return
                    
                    user = await get_user_by_id(db, user_id)
                    
                    if user:
                        await add_user_balance(
                            db, user, amount_kopeks,
                            f"Пополнение через Telegram Stars"
                        )
                        
                        await create_transaction(
                            db=db,
                            user_id=user.id,
                            type=TransactionType.DEPOSIT,
                            amount_kopeks=amount_kopeks,
                            description=f"Пополнение через Telegram Stars",
                            payment_method=PaymentMethod.TELEGRAM_STARS,
                            external_id=payment.telegram_payment_charge_id
                        )
                        
                        await message.answer(
                            f"✅ Баланс успешно пополнен на {settings.format_price(amount_kopeks)}!\n\n"
                            "⚠️ <b>Важно:</b> Пополнение баланса не активирует подписку автоматически. "
                            "Обязательно активируйте подписку отдельно!\n\n"
                            f"🔄 При наличии сохранённой корзины подписки и включенной автопокупке, "
                            f"подписка будет приобретена автоматически после пополнения баланса."
                        )
                        
                        logger.info(f"✅ Обработан Stars платеж: {payment.telegram_payment_charge_id}")
                
                except Exception as e:
                    logger.error(f"Ошибка обработки Stars платежа: {e}")
                    await db.rollback()
                finally:
                    break
        
    except Exception as e:
        logger.error(f"Ошибка в обработчике Stars платежа: {e}")


async def handle_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    try:
        await pre_checkout_query.answer(ok=True)
        logger.info(f"Pre-checkout query принят: {pre_checkout_query.id}")
        
    except Exception as e:
        logger.error(f"Ошибка в pre-checkout query: {e}")
        await pre_checkout_query.answer(ok=False, error_message="Ошибка обработки платежа")