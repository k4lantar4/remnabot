"""Card-to-card manual payment plugin."""

from aiogram import Dispatcher

from app.plugins.c2c.handlers.admin import register_admin_handlers
from app.plugins.c2c.handlers.user import register_user_handlers
from app.plugins.c2c.middleware import register_c2c_callback_middleware
from app.plugins.c2c.service import set_c2c_fsm_storage


__all__ = [
    'register_c2c_callback_middleware',
    'register_c2c_plugin',
]


def register_c2c_plugin(dp: Dispatcher) -> None:
    """Register C2C handlers on the dispatcher."""
    set_c2c_fsm_storage(dp.storage)
    register_user_handlers(dp)
    register_admin_handlers(dp)
