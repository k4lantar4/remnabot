"""Common imports and utilities for tenant bots handlers."""
import logging
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy import text as sql_text

from app.database.models import User, Bot, Transaction, TransactionType, Subscription, SubscriptionStatus
from app.database.crud.bot import get_bot_by_id
from app.localization.texts import get_texts
from app.utils.decorators import error_handler, admin_required
from app.keyboards.admin import get_admin_pagination_keyboard

logger = logging.getLogger(__name__)

