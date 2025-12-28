import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from aiogram import Bot

from app.config import settings
from app.localization.texts import get_texts
from app.database.crud.user import add_user_balance, get_user_by_id
from app.database.crud.referral import create_referral_earning
from app.database.models import TransactionType, ReferralEarning
from app.utils.user_utils import get_effective_referral_commission_percent

logger = logging.getLogger(__name__)


async def send_referral_notification(
    bot: Bot,
    user_id: int,
    message: str
):
    try:
        await bot.send_message(user_id, message, parse_mode="HTML")
        logger.info(f"Referral notification sent to user {user_id}")
    except Exception as e:
        logger.error(f"Error sending referral notification to user {user_id}: {e}")


async def process_referral_registration(
    db: AsyncSession,
    new_user_id: int,
    referrer_id: int,
    bot: Bot = None
):
    try:
        new_user = await get_user_by_id(db, new_user_id)
        referrer = await get_user_by_id(db, referrer_id)
        
        if not new_user or not referrer:
            logger.error(f"Users not found: new_user_id={new_user_id}, referrer_id={referrer_id}")
            return False

        if new_user.referred_by_id != referrer_id:
            logger.error(f"User {new_user_id} not linked to referrer {referrer_id}")
            return False
        
        await create_referral_earning(
            db=db,
            user_id=referrer_id,
            referral_id=new_user_id,
            amount_kopeks=0,
            reason="referral_registration_pending"
        )

        try:
            from app.services.referral_contest_service import referral_contest_service

            await referral_contest_service.on_referral_registration(db, new_user_id)
        except Exception as exc:
            logger.debug("Не удалось записать конкурсную регистрацию: %s", exc)

        if bot:
            commission_percent = get_effective_referral_commission_percent(referrer)
            # TODO: Restore proper localization for referral notifications
            referral_notification = (
                f"🎉 <b>Welcome!</b>\n\n"
                f"You came through the referral link of user <b>{referrer.full_name}</b>!\n\n"
                f"💰 On your first top-up of {settings.format_price(settings.REFERRAL_MINIMUM_TOPUP_KOPEKS)} "
                f"you will receive a bonus of {settings.format_price(settings.REFERRAL_FIRST_TOPUP_BONUS_KOPEKS)}!\n\n"
                # f"🎁 Your referrer will also receive a reward for your first top-up."
            )
            await send_referral_notification(bot, new_user.telegram_id, referral_notification)
            
            # TODO: Restore proper localization for referral notifications
            inviter_notification = (
                f"👥 <b>New referral!</b>\n\n"
                f"User <b>{new_user.full_name}</b> registered through your link!\n\n"
                f"💰 When they top-up {settings.format_price(settings.REFERRAL_MINIMUM_TOPUP_KOPEKS)}, "
                f"you will receive at least {settings.format_price(settings.REFERRAL_INVITER_BONUS_KOPEKS)} or "
                f"{commission_percent}% of the amount (whichever is greater).\n\n"
                f"📈 You will receive {commission_percent}% commission from each subsequent top-up."
            )
            await send_referral_notification(bot, referrer.telegram_id, inviter_notification)
        
        logger.info(f"Referral {new_user_id} registered for {referrer_id}. Bonuses will be awarded after top-up.")
        return True
        
    except Exception as e:
        logger.error(f"Error processing referral registration: {e}")
        return False


async def process_referral_topup(
    db: AsyncSession,
    user_id: int, 
    topup_amount_kopeks: int,
    bot: Bot = None
):
    try:
        user = await get_user_by_id(db, user_id)
        if not user or not user.referred_by_id:
            logger.info(f"User {user_id} is not a referral")
            return True

        referrer = await get_user_by_id(db, user.referred_by_id)
        if not referrer:
            logger.error(f"Referrer {user.referred_by_id} not found")
            return False

        commission_percent = get_effective_referral_commission_percent(referrer)
        qualifies_for_first_bonus = (
            topup_amount_kopeks >= settings.REFERRAL_MINIMUM_TOPUP_KOPEKS
        )
        commission_amount = 0
        if commission_percent > 0:
            commission_amount = int(
                topup_amount_kopeks * commission_percent / 100
            )

        if not user.has_made_first_topup:
            if not qualifies_for_first_bonus:
                logger.info(
                    "Top-up %s of %s Toman is below minimum for first bonus, but commission will be credited",
                    user_id,
                    topup_amount_kopeks / 100,
                )

                if commission_amount > 0:
                    await add_user_balance(
                        db,
                        referrer,
                        commission_amount,
                        f"Commission {commission_percent}% from top-up {user.full_name}",
                        bot=bot,
                    )

                    await create_referral_earning(
                        db=db,
                        user_id=referrer.id,
                        referral_id=user.id,
                        amount_kopeks=commission_amount,
                        reason="referral_commission_topup",
                    )

                    logger.info(
                        "💰 Commission from top-up: %s received %s Toman (before first bonus)",
                        referrer.telegram_id,
                        commission_amount / 100,
                    )

                    if bot:
                        commission_notification = (
                            f"💰 <b>Referral commission!</b>\n\n"
                            f"Ваш реферал <b>{user.full_name}</b> пополнил баланс на "
                            f"{settings.format_price(topup_amount_kopeks)}\n\n"
                            f"🎁 Ваша комиссия ({commission_percent}%): "
                            f"{settings.format_price(commission_amount)}\n\n"
                            f"💎 Средства зачислены на ваш баланс."
                        )
                        await send_referral_notification(bot, referrer.telegram_id, commission_notification)

                return True

            user.has_made_first_topup = True
            await db.commit()
            
            try:
                await db.execute(
                    delete(ReferralEarning).where(
                        ReferralEarning.user_id == referrer.id,
                        ReferralEarning.referral_id == user.id, 
                        ReferralEarning.reason == "referral_registration_pending"
                    )
                )
                await db.commit()
                logger.info(f"🗑️ Deleted 'pending top-up' record for referral {user.id}")
            except Exception as e:
                logger.error(f"Error deleting pending record: {e}")
            
            if settings.REFERRAL_FIRST_TOPUP_BONUS_KOPEKS > 0:
                await add_user_balance(
                    db, user, settings.REFERRAL_FIRST_TOPUP_BONUS_KOPEKS,
                    f"Bonus for first top-up via referral program",
                    bot=bot
                )
                logger.info(f"💰 Referral {user.id} received bonus {settings.REFERRAL_FIRST_TOPUP_BONUS_KOPEKS} Toman")
                
                if bot:
                    bonus_notification = (
                        f"🎉 <b>Бонус получен!</b>\n\n"
                        f"За первое пополнение вы получили бонус "
                        f"{settings.format_price(settings.REFERRAL_FIRST_TOPUP_BONUS_KOPEKS)}!\n\n"
                        f"💎 Средства зачислены на ваш баланс."
                    )
                    await send_referral_notification(bot, user.telegram_id, bonus_notification)
            
            commission_amount = int(topup_amount_kopeks * commission_percent / 100)
            inviter_bonus = max(settings.REFERRAL_INVITER_BONUS_KOPEKS, commission_amount)

            if inviter_bonus > 0:
                await add_user_balance(
                    db, referrer, inviter_bonus,
                    f"Bonus for first top-up of referral {user.full_name}",
                    bot=bot
                )

                await create_referral_earning(
                    db=db,
                    user_id=referrer.id,
                    referral_id=user.id,
                    amount_kopeks=inviter_bonus,
                    reason="referral_first_topup"
                )
                logger.info(f"💰 Referrer {referrer.telegram_id} received bonus {inviter_bonus} Toman")

                if bot:
                    inviter_bonus_notification = (
                        f"💰 <b>Referral reward!</b>\n\n"
                        f"Ваш реферал <b>{user.full_name}</b> сделал первое пополнение!\n\n"
                        f"🎁 Вы получили награду: {settings.format_price(inviter_bonus)}\n\n"
                        f"📈 Теперь с каждого его пополнения вы будете получать {commission_percent}% комиссии."
                    )
                    await send_referral_notification(bot, referrer.telegram_id, inviter_bonus_notification)
        
        else:
            if commission_amount > 0:
                await add_user_balance(
                    db, referrer, commission_amount,
                    f"Комиссия {commission_percent}% с пополнения {user.full_name}",
                    bot=bot
                )

                await create_referral_earning(
                    db=db,
                    user_id=referrer.id,
                    referral_id=user.id,
                    amount_kopeks=commission_amount,
                    reason="referral_commission_topup"
                )

                logger.info(f"💰 Commission from top-up: {referrer.telegram_id} received {commission_amount} Toman")

                if bot:
                    commission_notification = (
                        f"💰 <b>Referral commission!</b>\n\n"
                        f"Ваш реферал <b>{user.full_name}</b> пополнил баланс на "
                        f"{settings.format_price(topup_amount_kopeks)}\n\n"
                        f"🎁 Ваша комиссия ({commission_percent}%): "
                        f"{settings.format_price(commission_amount)}\n\n"
                        f"💎 Средства зачислены на ваш баланс."
                    )
                    await send_referral_notification(bot, referrer.telegram_id, commission_notification)
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка обработки пополнения реферала: {e}")
        return False


async def process_referral_purchase(
    db: AsyncSession,
    user_id: int,
    purchase_amount_kopeks: int,
    transaction_id: int = None,
    bot: Bot = None
):
    try:
        user = await get_user_by_id(db, user_id)
        if not user or not user.referred_by_id:
            return True
        
        referrer = await get_user_by_id(db, user.referred_by_id)
        if not referrer:
            logger.error(f"Реферер {user.referred_by_id} не найден")
            return False
        
        commission_percent = get_effective_referral_commission_percent(referrer)
            
        commission_amount = int(purchase_amount_kopeks * commission_percent / 100)
        
        if commission_amount > 0:
            await add_user_balance(
                db, referrer, commission_amount,
                f"Комиссия {commission_percent}% с покупки {user.full_name}",
                bot=bot
            )
            
            await create_referral_earning(
                db=db,
                user_id=referrer.id,
                referral_id=user.id, 
                amount_kopeks=commission_amount,
                reason="referral_commission",
                referral_transaction_id=transaction_id
            )
            
            logger.info(f"💰 Commission from purchase: {referrer.telegram_id} received {commission_amount} Toman")
            
            if bot:
                purchase_commission_notification = (
                    f"💰 <b>Commission from purchase!</b>\n\n"
                    f"Ваш реферал <b>{user.full_name}</b> совершил покупку на "
                    f"{settings.format_price(purchase_amount_kopeks)}\n\n"
                    f"🎁 Ваша комиссия ({commission_percent}%): "
                    f"{settings.format_price(commission_amount)}\n\n"
                    f"💎 Средства зачислены на ваш баланс."
                )
                await send_referral_notification(bot, referrer.telegram_id, purchase_commission_notification)
        
        if not user.has_had_paid_subscription:
            user.has_had_paid_subscription = True
            await db.commit()
            logger.info(f"✅ User {user_id} marked as having had paid subscription")
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing referral purchase: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False
