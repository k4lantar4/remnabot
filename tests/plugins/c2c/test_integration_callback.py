from aiogram.types import InlineKeyboardButton

from app.config import Settings
from app.plugins.c2c.integration import append_payment_button


def test_append_payment_button_uses_build_callback(monkeypatch):
    monkeypatch.setattr(Settings, 'is_c2c_enabled', lambda self: True)
    monkeypatch.setattr(Settings, 'get_c2c_display_name', lambda self: 'C2C')
    keyboard: list[list[InlineKeyboardButton]] = []
    texts = type('T', (), {'t': lambda self, k, d: d})()

    append_payment_button(keyboard, texts, lambda m: f'topup_amount|{m}|150000')

    assert keyboard[0][0].callback_data == 'topup_amount|c2c|150000'
