"""Send a production-path expiring notification smoke test (Jalali dates for fa).

Uses MonitoringService._send_subscription_expiring_notification with logo mode
and inline keyboard — no debug metadata.

Usage:
  docker compose run --rm bot python tools/send_monitoring_expiring_test.py
  docker compose run --rm bot python tools/send_monitoring_expiring_test.py --telegram-id 1713374557
  docker compose run --rm bot python tools/send_monitoring_expiring_test.py --days 3
"""

from __future__ import annotations

import argparse
import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.database.crud.subscription import get_active_subscriptions_by_user_id
from app.database.crud.user import get_user_by_telegram_id
from app.database.database import AsyncSessionLocal
from app.services.monitoring_service import MonitoringService


def _default_admin_telegram_id() -> int:
    admin_ids = settings.get_admin_ids()
    if not admin_ids:
        raise SystemExit('ADMIN_IDS is empty — pass --telegram-id')
    return admin_ids[0]


async def main_async(*, telegram_id: int, days: int) -> None:
    async with AsyncSessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if user is None:
            raise SystemExit(f'User not found for telegram_id={telegram_id}')

        subscriptions = await get_active_subscriptions_by_user_id(db, user.id)
        subscription = next((s for s in subscriptions if not s.is_trial), None) or (
            subscriptions[0] if subscriptions else None
        )
        if subscription is None:
            raise SystemExit(f'No active subscription for telegram_id={telegram_id}')

    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    service = MonitoringService(bot=bot)
    try:
        ok = await service._send_subscription_expiring_notification(
            user,
            subscription,
            days,
            has_saved_card=False,
        )
        if not ok:
            raise SystemExit('Notification send returned False')
        print(
            f'Sent expiring notification to telegram_id={telegram_id} '
            f'(subscription_id={subscription.id}, days={days}, language={user.language})'
        )
    finally:
        await bot.session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description='Smoke test: monitoring expiring notification')
    parser.add_argument('--telegram-id', type=int, default=None, help='Target Telegram user id')
    parser.add_argument('--days', type=int, default=1, help='Days-until-expiry label (default: 1)')
    args = parser.parse_args()
    telegram_id = args.telegram_id or _default_admin_telegram_id()
    asyncio.run(main_async(telegram_id=telegram_id, days=args.days))


if __name__ == '__main__':
    main()
