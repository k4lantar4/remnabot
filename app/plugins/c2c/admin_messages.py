"""Rich admin group messages for C2C receipts."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import settings
from app.database.models import C2cReceipt, C2cReceiptStatus, User
from app.localization.texts import get_texts
from app.plugins.c2c.constants import C2C_CALLBACK_ADMIN_INBOX, C2C_CALLBACK_RESOLVED_PREFIX
from app.plugins.c2c.reject_reasons import get_admin_reject_button_label
from app.utils.jalali_datetime import format_user_datetime


def _resolve_lang(language: str | None) -> str:
    if language:
        return language
    default = settings.DEFAULT_LANGUAGE
    return default if isinstance(default, str) else 'fa'


def _resolve_admin_reject_reason(receipt: C2cReceipt, texts) -> str | None:
    if receipt.rejection_reason_key:
        return get_admin_reject_button_label(receipt.rejection_reason_key, texts)
    if receipt.rejection_reason:
        return receipt.rejection_reason
    return None


def build_c2c_admin_receipt_body(
    receipt: C2cReceipt,
    user: User | None,
    *,
    lang: str | None = None,
    admin_label: str | None = None,
) -> str:
    """Build admin group caption/text for a C2C receipt (pending or resolved)."""
    resolved_lang = _resolve_lang(lang)
    texts = get_texts(resolved_lang)

    if user is not None:
        name = user.full_name or user.username or f'User {user.id}'
        telegram_id = user.telegram_id or '—'
    else:
        name = '—'
        telegram_id = '—'

    card_label = receipt.card_label or '—'
    amount_display = settings.format_balance(receipt.amount_kopeks)

    lines = [
        texts.t('ADMIN_NOTIFY_C2C_TITLE', '🔔 <b>C2C Receipt #{receipt_id}</b>').format(receipt_id=receipt.id),
        texts.t('ADMIN_NOTIFY_C2C_USER', '👤 <b>User:</b> {name} (ID: {telegram_id})').format(
            name=name,
            telegram_id=telegram_id,
        ),
        texts.t('ADMIN_NOTIFY_C2C_AMOUNT', '💰 <b>Amount:</b> {amount}').format(amount=amount_display),
        texts.t('ADMIN_NOTIFY_C2C_CARD', '💳 <b>Card shown:</b> {card}').format(card=card_label),
        texts.t('ADMIN_NOTIFY_C2C_SENT_AT', '📅 <b>Sent:</b> {sent_at}').format(
            sent_at=format_user_datetime(getattr(receipt, 'created_at', None), language=resolved_lang),
        ),
    ]

    if receipt.status == C2cReceiptStatus.APPROVED.value:
        lines.append(
            texts.t('ADMIN_NOTIFY_C2C_RESOLVED_HEADER_APPROVED', '✅ <b>Approved</b>'),
        )
        lines.append(
            texts.t('ADMIN_NOTIFY_C2C_RESOLVED_AT', '⏱ <b>Resolved:</b> {resolved_at}').format(
                resolved_at=format_user_datetime(receipt.processed_at, language=resolved_lang),
            ),
        )
        if admin_label:
            lines.append(
                texts.t('ADMIN_NOTIFY_C2C_RESOLVED_BY', '👤 <b>Admin:</b> @{admin}').format(admin=admin_label),
            )
        credited = (
            receipt.approved_amount_kopeks if receipt.approved_amount_kopeks is not None else receipt.amount_kopeks
        )
        lines.append(
            texts.t('ADMIN_NOTIFY_C2C_CREDITED_AMOUNT', '💰 <b>Credited:</b> {amount}').format(
                amount=settings.format_balance(credited),
            ),
        )
    elif receipt.status == C2cReceiptStatus.REJECTED.value:
        lines.append(
            texts.t('ADMIN_NOTIFY_C2C_RESOLVED_HEADER_REJECTED', '❌ <b>Rejected</b>'),
        )
        lines.append(
            texts.t('ADMIN_NOTIFY_C2C_RESOLVED_AT', '⏱ <b>Resolved:</b> {resolved_at}').format(
                resolved_at=format_user_datetime(receipt.processed_at, language=resolved_lang),
            ),
        )
        if admin_label:
            lines.append(
                texts.t('ADMIN_NOTIFY_C2C_RESOLVED_BY', '👤 <b>Admin:</b> @{admin}').format(admin=admin_label),
            )
        reason_text = _resolve_admin_reject_reason(receipt, texts)
        if reason_text:
            lines.append(
                texts.t('ADMIN_NOTIFY_C2C_REJECT_REASON', '<b>Reason:</b> {reason}').format(reason=reason_text),
            )

    return '\n'.join(lines)


def build_c2c_resolved_keyboard(
    receipt_id: int,
    status: str,
    *,
    lang: str | None = None,
    include_inbox_back: bool = False,
) -> InlineKeyboardMarkup:
    resolved_lang = _resolve_lang(lang)
    texts = get_texts(resolved_lang)
    if status == C2cReceiptStatus.APPROVED.value:
        button_text = texts.t('C2C_ADMIN_RESOLVED_BTN_APPROVED', '✅ Approved')
    else:
        button_text = texts.t('C2C_ADMIN_RESOLVED_BTN_REJECTED', '❌ Rejected')
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=button_text,
                callback_data=f'{C2C_CALLBACK_RESOLVED_PREFIX}{receipt_id}',
            ),
        ],
    ]
    if include_inbox_back:
        rows.append(
            [
                InlineKeyboardButton(
                    text=texts.t('C2C_ADMIN_INBOX_BACK', '📥 صندوق ورودی'),
                    callback_data=C2C_CALLBACK_ADMIN_INBOX,
                ),
            ],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
