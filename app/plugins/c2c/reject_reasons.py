"""Structured C2C receipt reject reason catalog."""

from __future__ import annotations

from app.localization.texts import Texts

C2C_REJECT_REASONS: dict[str, str | None] = {
    'amt_mismatch': 'C2C_REJECT_REASON_AMT_MISMATCH',
    'unclear': 'C2C_REJECT_REASON_UNCLEAR',
    'wrong_card': 'C2C_REJECT_REASON_WRONG_CARD',
    'duplicate': 'C2C_REJECT_REASON_DUPLICATE',
    'expired': 'C2C_REJECT_REASON_EXPIRED',
    'silent': None,
}

C2C_REJECT_ADMIN_LABELS: dict[str, str] = {
    'amt_mismatch': 'C2C_ADMIN_REJECT_BTN_AMT_MISMATCH',
    'unclear': 'C2C_ADMIN_REJECT_BTN_UNCLEAR',
    'wrong_card': 'C2C_ADMIN_REJECT_BTN_WRONG_CARD',
    'duplicate': 'C2C_ADMIN_REJECT_BTN_DUPLICATE',
    'expired': 'C2C_ADMIN_REJECT_BTN_EXPIRED',
    'silent': 'C2C_ADMIN_REJECT_BTN_SILENT',
}


def get_reject_reason_codes() -> list[str]:
    return list(C2C_REJECT_REASONS.keys())


def get_reject_reason_text_key(code: str) -> str | None:
    return C2C_REJECT_REASONS.get(code)


def get_admin_reject_button_label(code: str, texts: Texts) -> str:
    key = C2C_REJECT_ADMIN_LABELS.get(code)
    if not key:
        return code
    fallbacks = {
        'amt_mismatch': '💰 مبلغ نادرست',
        'unclear': '📷 رسید نامشخص',
        'wrong_card': '💳 کارت اشتباه',
        'duplicate': '🔁 رسید تکراری',
        'expired': '⏰ رسید منقضی',
        'silent': '🔇 رد بدون پیام',
    }
    return texts.t(key, fallbacks.get(code, code))


def resolve_user_reject_reason_text(code: str, texts: Texts) -> str | None:
    """Return Persian reason phrase for user notification, or None for silent."""
    key = get_reject_reason_text_key(code)
    if key is None:
        return None
    fallbacks = {
        'amt_mismatch': 'مبلغ واریزی با مبلغ درخواستی مطابقت ندارد.',
        'unclear': 'تصویر یا متن رسید قابل بررسی نیست.',
        'wrong_card': 'واریز به کارت اشتباه انجام شده است.',
        'duplicate': 'این رسید قبلاً ثبت شده است.',
        'expired': 'مهلت ارسال این رسید به پایان رسیده است.',
    }
    return texts.t(key, fallbacks.get(code, 'رسید تأیید نشد.'))
