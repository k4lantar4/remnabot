"""Regression tests for pending C2C receipt top-up screen."""

from __future__ import annotations

from types import SimpleNamespace

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.plugins.c2c import integration as c2c_integration


def _keyboard(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=data) for label, data in row]
            for row in rows
        ],
    )


def test_payment_keyboard_has_selectable_method_true_for_topup_callback():
    keyboard = _keyboard([('C2C', 'topup_c2c')])
    assert c2c_integration.payment_keyboard_has_selectable_method(keyboard) is True


def test_payment_keyboard_has_selectable_method_false_for_unavailable_only():
    keyboard = _keyboard(
        [('Unavailable', 'payment_methods_unavailable')],
        [('Back', 'menu_balance')],
    )
    assert c2c_integration.payment_keyboard_has_selectable_method(keyboard) is False


def test_payment_keyboard_ignores_support_and_unavailable():
    keyboard = _keyboard(
        [('Unavailable', 'payment_methods_unavailable')],
        [('Support', 'topup_support')],
        [('Back', 'menu_balance')],
    )
    assert c2c_integration.payment_keyboard_has_selectable_method(keyboard) is False


def test_build_pending_receipt_topup_screen_includes_receipt_details():
    receipt = SimpleNamespace(id=183, amount_kopeks=10_000_000)
    message_text, keyboard = c2c_integration.build_pending_receipt_topup_screen(receipt, 'fa')

    assert '#183' in message_text
    assert keyboard.inline_keyboard[-1][0].callback_data == 'menu_balance'


def test_build_pending_receipt_topup_screen_with_return_to_checkout():
    receipt = SimpleNamespace(id=183, amount_kopeks=10_000_000)
    message_text, keyboard = c2c_integration.build_pending_receipt_topup_screen(
        receipt,
        'fa',
        show_return_to_checkout=True,
    )

    assert '#183' in message_text
    callback_data = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    assert 'return_to_saved_cart' in callback_data
    assert callback_data[-1] == 'menu_balance'


def test_show_payment_methods_pending_block_not_inside_cart_except():
    """Guard against indentation regression that skips the dedicated screen."""
    from pathlib import Path

    source_path = Path(__file__).resolve().parents[3] / 'app' / 'handlers' / 'balance' / 'main.py'
    lines = source_path.read_text(encoding='utf-8').splitlines()

    in_show_payment_methods = False
    cart_except_line: int | None = None
    pending_if_line: int | None = None

    for index, line in enumerate(lines):
        if line.startswith('async def show_payment_methods'):
            in_show_payment_methods = True
            continue
        if in_show_payment_methods and line.startswith('async def '):
            break
        if not in_show_payment_methods:
            continue
        if 'except Exception:' in line and 'cart' not in line.lower():
            # cart handler except - distinguish by following pass and amount_kopeks context
            if index > 0 and 'user_cart_service' in '\n'.join(lines[max(0, index - 8) : index]):
                cart_except_line = index
        if 'if pending_receipt and c2c_integration:' in line:
            pending_if_line = index

    assert cart_except_line is not None
    assert pending_if_line is not None
    assert pending_if_line > cart_except_line
    assert lines[pending_if_line].startswith('    if pending_receipt')
    assert lines[cart_except_line].startswith('    except Exception:')
