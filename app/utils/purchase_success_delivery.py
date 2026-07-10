"""Shared post-purchase success delivery for config link and QR."""

from __future__ import annotations

from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.config import settings
from app.utils.subscription_qr import subscription_qr_photo_file
from app.utils.subscription_utils import get_display_subscription_link, resolve_connect_webapp_url


def _resolve_subscription_link(subscription) -> str | None:
    raw_link = get_display_subscription_link(subscription)
    return raw_link if isinstance(raw_link, str) and raw_link.strip() else None


def build_config_delivery_caption(texts, subscription, *, body_html: str | None = None) -> str:
    """Build HTML caption for config QR delivery (title + link + hint)."""
    subscription_link = _resolve_subscription_link(subscription)
    parts: list[str] = []
    if body_html and body_html.strip():
        parts.append(body_html.strip())
    parts.append(
        texts.t(
            'CONNECT_CONFIG_TITLE',
            '📋 <b>Ваша конфигурация:</b>',
        )
    )
    parts.append(f'<code>{subscription_link or "—"}</code>')
    parts.append(
        texts.t(
            'CONNECT_CONFIG_QR_HINT',
            'Скопируйте ссылку или отсканируйте QR-код',
        )
    )
    return '\n\n'.join(parts)


async def build_post_purchase_connect_keyboard(texts, subscription) -> InlineKeyboardMarkup:
    """Standard post-purchase keyboard: resend QR config + setup guide + subscription menu."""
    sub_id = getattr(subscription, 'id', None) if subscription else None
    has_valid_sub_id = isinstance(sub_id, int) and sub_id > 0
    sub_callback = (
        f'sm:{sub_id}' if settings.is_multi_tariff_enabled() and has_valid_sub_id else 'menu_subscription'
    )
    connect_callback = f'sl_config:{sub_id}' if has_valid_sub_id else 'subscription_connect'
    setup_guide_url = await resolve_connect_webapp_url(subscription, sub_id) if has_valid_sub_id else None
    if not isinstance(setup_guide_url, str) or not setup_guide_url.strip():
        setup_guide_url = None
    setup_guide_button = (
        InlineKeyboardButton(
            text=texts.t('MY_SUB_BTN_SETUP_GUIDE', '📖 Инструкция по настройке'),
            web_app=WebAppInfo(url=setup_guide_url),
        )
        if setup_guide_url
        else InlineKeyboardButton(
            text=texts.t('MY_SUB_BTN_SETUP_GUIDE', '📖 Инструкция по настройке'),
            callback_data='subscription_connect',
        )
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.t('MY_SUB_BTN_GET_CONFIG', '📋 Получить QR и ссылку'),
                    callback_data=connect_callback,
                )
            ],
            [setup_guide_button],
            [
                InlineKeyboardButton(
                    text=texts.t('MY_SUBSCRIPTION_BUTTON', '📱 Моя подписка'),
                    callback_data=sub_callback,
                )
            ],
            [InlineKeyboardButton(text=texts.BACK, callback_data='back_to_menu')],
        ]
    )


async def send_config_qr_to_chat(
    bot,
    chat_id: int,
    texts,
    subscription,
    *,
    body_html: str | None,
    keyboard,
) -> None:
    """Send config QR photo (or text fallback) to a chat."""
    subscription_link = _resolve_subscription_link(subscription)
    caption = build_config_delivery_caption(texts, subscription, body_html=body_html)

    if subscription_link and not settings.should_hide_subscription_link():
        await bot.send_photo(
            chat_id=chat_id,
            photo=subscription_qr_photo_file(subscription_link),
            caption=caption,
            reply_markup=keyboard,
            parse_mode='HTML',
        )
        return

    await bot.send_message(
        chat_id=chat_id,
        text=caption,
        reply_markup=keyboard,
        parse_mode='HTML',
    )


async def send_config_qr_reply(
    callback: types.CallbackQuery,
    texts,
    subscription,
    *,
    keyboard,
    body_html: str | None = None,
) -> None:
    """Answer callback and send config QR photo as a new message."""
    if isinstance(callback.message, types.InaccessibleMessage):
        await callback.answer()
        return

    subscription_link = _resolve_subscription_link(subscription)
    if not subscription_link:
        await callback.answer(
            texts.t(
                'SUBSCRIPTION_NO_ACTIVE_LINK',
                '⚠ У вас нет активной подписки или ссылка еще генерируется',
            ),
            show_alert=True,
        )
        return

    await callback.answer()
    caption = build_config_delivery_caption(texts, subscription, body_html=body_html)

    if not settings.should_hide_subscription_link():
        await callback.message.answer_photo(
            photo=subscription_qr_photo_file(subscription_link),
            caption=caption,
            reply_markup=keyboard,
            parse_mode='HTML',
        )
        return

    await callback.message.answer(
        caption,
        reply_markup=keyboard,
        parse_mode='HTML',
    )


async def send_purchase_success_delivery(message, texts, subscription, *, summary_html: str, keyboard) -> None:
    """Deliver purchase success as QR photo when config link is visible."""
    subscription_link = _resolve_subscription_link(subscription)
    caption = texts.t(
        'PURCHASE_SUCCESS_CONFIG_CAPTION',
        '📋 <b>Ссылка для конфигурации:</b>\n<code>{config_url}</code>',
    ).format(config_url=subscription_link or '—')
    full_message = f'{summary_html}\n\n{caption}' if summary_html else caption

    if subscription_link and not settings.should_hide_subscription_link():
        await message.answer_photo(
            photo=subscription_qr_photo_file(subscription_link),
            caption=full_message,
            reply_markup=keyboard,
            parse_mode='HTML',
        )
        try:
            await message.delete()
        except Exception:
            pass
        return

    await message.edit_text(full_message, reply_markup=keyboard, parse_mode='HTML')


async def send_purchase_success_delivery_to_chat(
    bot,
    chat_id: int,
    texts,
    subscription,
    *,
    summary_html: str,
    keyboard,
) -> None:
    """Deliver purchase success to chat when no source message exists."""
    subscription_link = _resolve_subscription_link(subscription)
    caption = texts.t(
        'PURCHASE_SUCCESS_CONFIG_CAPTION',
        '📋 <b>Ссылка для конфигурации:</b>\n<code>{config_url}</code>',
    ).format(config_url=subscription_link or '—')
    full_message = f'{summary_html}\n\n{caption}' if summary_html else caption

    if subscription_link and not settings.should_hide_subscription_link():
        await bot.send_photo(
            chat_id=chat_id,
            photo=subscription_qr_photo_file(subscription_link),
            caption=full_message,
            reply_markup=keyboard,
            parse_mode='HTML',
        )
        return

    await bot.send_message(
        chat_id=chat_id,
        text=full_message,
        reply_markup=keyboard,
        parse_mode='HTML',
    )
