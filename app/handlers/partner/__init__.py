from aiogram import Dispatcher

from .apply import register_partner_application_handlers
from .settings import register_partner_handlers as register_partner_settings_handlers


def register_partner_handlers(dp: Dispatcher) -> None:
    register_partner_settings_handlers(dp)
    register_partner_application_handlers(dp)


__all__ = ['register_partner_handlers']
