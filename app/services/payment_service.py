"""Aggregating service that collects all payment modules."""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Optional

from aiogram import Bot

from app.config import settings
from app.utils.currency_converter import currency_converter  # noqa: F401
from app.external.cryptobot import CryptoBotService
from app.services.pal24_service import Pal24Service
from app.services.payment import (
    CryptoBotPaymentMixin,
    Pal24PaymentMixin,
    PaymentCommonMixin,
)

logger = logging.getLogger(__name__)


# --- Compatibility: export functions that are actively mocked in tests ---


async def create_yookassa_payment(*args, **kwargs):
    yk_crud = import_module("app.database.crud.yookassa")
    return await yk_crud.create_yookassa_payment(*args, **kwargs)


async def update_yookassa_payment_status(*args, **kwargs):
    yk_crud = import_module("app.database.crud.yookassa")
    return await yk_crud.update_yookassa_payment_status(*args, **kwargs)


async def link_yookassa_payment_to_transaction(*args, **kwargs):
    yk_crud = import_module("app.database.crud.yookassa")
    return await yk_crud.link_yookassa_payment_to_transaction(*args, **kwargs)


async def get_yookassa_payment_by_id(*args, **kwargs):
    yk_crud = import_module("app.database.crud.yookassa")
    return await yk_crud.get_yookassa_payment_by_id(*args, **kwargs)


async def get_yookassa_payment_by_local_id(*args, **kwargs):
    yk_crud = import_module("app.database.crud.yookassa")
    return await yk_crud.get_yookassa_payment_by_local_id(*args, **kwargs)


async def create_transaction(*args, **kwargs):
    transaction_crud = import_module("app.database.crud.transaction")
    return await transaction_crud.create_transaction(*args, **kwargs)


async def get_transaction_by_external_id(*args, **kwargs):
    transaction_crud = import_module("app.database.crud.transaction")
    return await transaction_crud.get_transaction_by_external_id(*args, **kwargs)


async def add_user_balance(*args, **kwargs):
    user_crud = import_module("app.database.crud.user")
    return await user_crud.add_user_balance(*args, **kwargs)


async def get_user_by_id(*args, **kwargs):
    user_crud = import_module("app.database.crud.user")
    return await user_crud.get_user_by_id(*args, **kwargs)


async def get_user_by_telegram_id(*args, **kwargs):
    user_crud = import_module("app.database.crud.user")
    return await user_crud.get_user_by_telegram_id(*args, **kwargs)


async def create_pal24_payment(*args, **kwargs):
    pal_crud = import_module("app.database.crud.pal24")
    return await pal_crud.create_pal24_payment(*args, **kwargs)


async def get_pal24_payment_by_bill_id(*args, **kwargs):
    pal_crud = import_module("app.database.crud.pal24")
    return await pal_crud.get_pal24_payment_by_bill_id(*args, **kwargs)


async def get_pal24_payment_by_order_id(*args, **kwargs):
    pal_crud = import_module("app.database.crud.pal24")
    return await pal_crud.get_pal24_payment_by_order_id(*args, **kwargs)


async def get_pal24_payment_by_id(*args, **kwargs):
    pal_crud = import_module("app.database.crud.pal24")
    return await pal_crud.get_pal24_payment_by_id(*args, **kwargs)


async def update_pal24_payment_status(*args, **kwargs):
    pal_crud = import_module("app.database.crud.pal24")
    return await pal_crud.update_pal24_payment_status(*args, **kwargs)


async def link_pal24_payment_to_transaction(*args, **kwargs):
    pal_crud = import_module("app.database.crud.pal24")
    return await pal_crud.link_pal24_payment_to_transaction(*args, **kwargs)


async def create_cryptobot_payment(*args, **kwargs):
    crypto_crud = import_module("app.database.crud.cryptobot")
    return await crypto_crud.create_cryptobot_payment(*args, **kwargs)


async def get_cryptobot_payment_by_invoice_id(*args, **kwargs):
    crypto_crud = import_module("app.database.crud.cryptobot")
    return await crypto_crud.get_cryptobot_payment_by_invoice_id(*args, **kwargs)


async def update_cryptobot_payment_status(*args, **kwargs):
    crypto_crud = import_module("app.database.crud.cryptobot")
    return await crypto_crud.update_cryptobot_payment_status(*args, **kwargs)


async def link_cryptobot_payment_to_transaction(*args, **kwargs):
    crypto_crud = import_module("app.database.crud.cryptobot")
    return await crypto_crud.link_cryptobot_payment_to_transaction(*args, **kwargs)


class PaymentService(
    PaymentCommonMixin,
    CryptoBotPaymentMixin,
    Pal24PaymentMixin,
):
    """Main payment interface that delegates work to specialized mixins."""

    def __init__(self, bot: Optional[Bot] = None) -> None:
        # Bot is needed for sending notifications.
        self.bot = bot
        # Initialize wrapper services only for the enabled sample providers.
        self.cryptobot_service = (
            CryptoBotService() if settings.is_cryptobot_enabled() else None
        )
        self.pal24_service = (
            Pal24Service() if settings.is_pal24_enabled() else None
        )
        logger.debug(
            "PaymentService initialized (CryptoBot=%s, Pal24=%s)",
            bool(self.cryptobot_service),
            bool(self.pal24_service),
        )
