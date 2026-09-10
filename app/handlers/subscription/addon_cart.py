"""Возврат к сохранённой корзине докупки трафика или устройств.

Жалоба (upstream 0009c30b): докупил трафик, денег не хватило, пополнил баланс —
«Трафик не покупается сам», а кнопка «Вернуться к оформлению подписки» отвечает
«Корзина повреждена» и удаляет её; следующее нажатие — «Корзина не найдена».

Причины были две. Корзины докупки сохранялись без метки намерения
(``return_to_cart``), и тихая автопокупка после пополнения их пропускала. А
общий обработчик кнопки знал только подписочные корзины и требовал у корзины
``period_days`` — у докупки его нет и быть не может.

Шкала (Phase B): ``price_kopeks`` корзины — каталожная (÷100 при показе), баланс —
томаны 1:1. Поэтому сравнение идёт через ``user_can_afford``, а экран нехватки —
общий для всех докупок (``render_addon_insufficient_funds``), с кнопкой пополнения
на недостающие томаны. Upstream сравнивал ``balance < price_kopeks`` как есть — у нас
это была бы 100-кратная ошибка.
"""

from __future__ import annotations

from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.keyboards.inline import get_insufficient_balance_keyboard_with_cart
from app.localization.texts import get_texts
from app.services.subscription_auto_purchase_service import resume_addon_cart
from app.utils.price_display import render_addon_insufficient_funds, user_can_afford
from app.utils.topup_suggestion import suggest_topup_amount_toman


def _price_kopeks(cart_data: dict) -> int:
    try:
        return int(cart_data.get('price_kopeks') or 0)
    except (TypeError, ValueError):
        return 0


async def resume_addon_cart_from_button(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    cart_data: dict,
) -> None:
    """Довести докупку до конца по явному нажатию; при нехватке — снова к пополнению."""
    texts = get_texts(db_user.language)
    price = _price_kopeks(cart_data)

    if price > 0 and not user_can_afford(db_user.balance_kopeks, price):
        text, missing_toman = render_addon_insufficient_funds(
            texts,
            price_kopeks=price,
            balance_toman=db_user.balance_kopeks,
        )
        await callback.message.edit_text(
            text,
            reply_markup=get_insufficient_balance_keyboard_with_cart(
                db_user.language,
                suggest_topup_amount_toman(missing_toman),
            ),
        )
        await callback.answer()
        return

    # Сама покупка шлёт человеку итог («Трафик добавлен» / «Устройства добавлены»)
    # и чистит корзину; здесь — только короткий ответ на нажатие.
    succeeded = await resume_addon_cart(db, db_user, cart_data, bot=callback.bot)
    if succeeded:
        await callback.answer(texts.t('ADDON_CART_COMPLETED', '✅ Готово!'))
        return

    await callback.answer(
        texts.t(
            'ADDON_CART_FAILED',
            '❌ Не удалось завершить покупку. Попробуйте ещё раз или напишите в поддержку.',
        ),
        show_alert=True,
    )
