"""Rich admin group messages for C2C receipts."""

from __future__ import annotations

import html

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import settings
from app.database.models import C2cReceipt, C2cReceiptStatus, User
from app.localization.texts import get_texts
from app.plugins.c2c.constants import C2C_CALLBACK_ADMIN_INBOX, C2C_CALLBACK_RESOLVED_PREFIX
from app.plugins.c2c.reject_reasons import get_admin_reject_button_label
from app.utils.jalali_datetime import format_user_datetime


ADMIN_DATETIME_FMT = '%d.%m.%Y %H:%M'
C2C_MESSAGE_SEPARATOR = '──────────'


def _resolve_lang(language: str | None) -> str:
    if language:
        return language
    default = settings.DEFAULT_LANGUAGE
    return default if isinstance(default, str) else 'fa'


def _format_c2c_admin_datetime(dt, lang: str) -> str:
    return format_user_datetime(dt, language=lang, fmt=ADMIN_DATETIME_FMT)


def _looks_like_card_digits(card_label: str) -> bool:
    stripped = card_label.replace(' ', '').replace('-', '')
    return bool(stripped) and stripped.isdigit()


def _format_code_value(value) -> str:
    if value in (None, '—', ''):
        return '—'
    return f'<code>{value}</code>'


def _resolve_admin_reject_reason(receipt: C2cReceipt, texts) -> str | None:
    if receipt.rejection_reason_key:
        return get_admin_reject_button_label(receipt.rejection_reason_key, texts)
    if receipt.rejection_reason:
        return receipt.rejection_reason
    return None


def _assemble_c2c_admin_message(
    header_lines: list[str],
    body_lines: list[str],
    footer_lines: list[str],
) -> str:
    parts = ['\n'.join(header_lines)]
    if body_lines:
        parts.append('\n'.join(body_lines))
    parts.append(f'{C2C_MESSAGE_SEPARATOR}\n' + '\n'.join(footer_lines))
    return '\n\n'.join(parts)


def build_c2c_admin_scan_lines(
    receipt: C2cReceipt,
    user: User | None,
    *,
    lang: str | None = None,
) -> list[str]:
    """Build the scan/header block for admin C2C receipt messages."""
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
    telegram_id_html = _format_code_value(telegram_id)
    card_display = _format_code_value(card_label) if _looks_like_card_digits(card_label) else card_label

    return [
        texts.t(
            'ADMIN_NOTIFY_C2C_HEADER',
            texts.t('ADMIN_NOTIFY_C2C_TITLE', '🔔 <b>C2C Receipt #{receipt_id}</b>'),
        ).format(receipt_id=_format_code_value(receipt.id)),
        texts.t(
            'ADMIN_NOTIFY_C2C_SCAN_AMOUNT',
            texts.t('ADMIN_NOTIFY_C2C_AMOUNT', '💰 <b>Amount:</b> {amount}'),
        ).format(amount=amount_display),
        texts.t(
            'ADMIN_NOTIFY_C2C_SCAN_USER',
            texts.t('ADMIN_NOTIFY_C2C_USER', '👤 <b>User:</b> {name}'),
        ).format(name=name),
        texts.t(
            'ADMIN_NOTIFY_C2C_SCAN_TG_ID',
            '🆔 {telegram_id}',
        ).format(telegram_id=telegram_id_html),
        texts.t(
            'ADMIN_NOTIFY_C2C_SCAN_CARD',
            texts.t('ADMIN_NOTIFY_C2C_CARD', '💳 <b>Card shown:</b> {card}'),
        ).format(card=card_display),
    ]


def build_c2c_admin_receipt_body(
    receipt: C2cReceipt,
    user: User | None,
    *,
    lang: str | None = None,
    admin_label: str | None = None,
    receipt_text: str | None = None,
) -> str:
    """Build admin group caption/text for a C2C receipt (pending or resolved)."""
    resolved_lang = _resolve_lang(lang)
    texts = get_texts(resolved_lang)

    header_lines = build_c2c_admin_scan_lines(receipt, user, lang=resolved_lang)

    body_lines: list[str] = []
    text_content = receipt_text if receipt_text is not None else getattr(receipt, 'receipt_text', None)
    if text_content and text_content.strip():
        safe_receipt = html.escape(text_content.strip())
        attach_label = texts.t('ADMIN_NOTIFY_C2C_RECEIPT_ATTACH', '📎 <b>Receipt:</b>')
        body_lines = [attach_label, safe_receipt]

    footer_lines = [
        texts.t(
            'ADMIN_NOTIFY_C2C_FOOTER_SENT',
            texts.t('ADMIN_NOTIFY_C2C_SENT_AT', '📅 <b>Sent:</b> {sent_at}'),
        ).format(
            sent_at=_format_c2c_admin_datetime(getattr(receipt, 'created_at', None), resolved_lang),
        ),
    ]

    if receipt.status == C2cReceiptStatus.APPROVED.value:
        footer_lines.append(
            texts.t('ADMIN_NOTIFY_C2C_RESOLVED_HEADER_APPROVED', '✅ <b>Approved</b>'),
        )
        footer_lines.append(
            texts.t(
                'ADMIN_NOTIFY_C2C_FOOTER_RESOLVED',
                texts.t('ADMIN_NOTIFY_C2C_RESOLVED_AT', '⏱ <b>Resolved:</b> {resolved_at}'),
            ).format(
                resolved_at=_format_c2c_admin_datetime(receipt.processed_at, resolved_lang),
            ),
        )
        if admin_label:
            footer_lines.append(
                texts.t('ADMIN_NOTIFY_C2C_RESOLVED_BY', '👤 <b>Admin:</b> @{admin}').format(admin=admin_label),
            )
        credited = (
            receipt.approved_amount_kopeks if receipt.approved_amount_kopeks is not None else receipt.amount_kopeks
        )
        footer_lines.append(
            texts.t('ADMIN_NOTIFY_C2C_CREDITED_AMOUNT', '💰 <b>Credited:</b> {amount}').format(
                amount=settings.format_balance(credited),
            ),
        )
    elif receipt.status == C2cReceiptStatus.REJECTED.value:
        footer_lines.append(
            texts.t('ADMIN_NOTIFY_C2C_RESOLVED_HEADER_REJECTED', '❌ <b>Rejected</b>'),
        )
        footer_lines.append(
            texts.t(
                'ADMIN_NOTIFY_C2C_FOOTER_RESOLVED',
                texts.t('ADMIN_NOTIFY_C2C_RESOLVED_AT', '⏱ <b>Resolved:</b> {resolved_at}'),
            ).format(
                resolved_at=_format_c2c_admin_datetime(receipt.processed_at, resolved_lang),
            ),
        )
        if admin_label:
            footer_lines.append(
                texts.t('ADMIN_NOTIFY_C2C_RESOLVED_BY', '👤 <b>Admin:</b> @{admin}').format(admin=admin_label),
            )
        reason_text = _resolve_admin_reject_reason(receipt, texts)
        if reason_text:
            footer_lines.append(
                texts.t('ADMIN_NOTIFY_C2C_REJECT_REASON', '<b>Reason:</b> {reason}').format(reason=reason_text),
            )

    return _assemble_c2c_admin_message(header_lines, body_lines, footer_lines)


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
