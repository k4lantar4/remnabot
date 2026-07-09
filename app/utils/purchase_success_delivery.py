"""Shared post-purchase success delivery for config link and QR."""

from __future__ import annotations

from app.config import settings
from app.utils.subscription_qr import subscription_qr_photo_file
from app.utils.subscription_utils import get_display_subscription_link


async def send_purchase_success_delivery(message, texts, subscription, *, summary_html: str, keyboard) -> None:
    """Deliver purchase success as QR photo when config link is visible."""
    subscription_link = get_display_subscription_link(subscription)
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
