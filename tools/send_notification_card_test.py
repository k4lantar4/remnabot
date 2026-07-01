"""Send production-path notification smoke tests with subscription card.

Uses MonitoringService private send methods — same path as cron, not admin preview.

Usage:
  docker compose run --rm bot python tools/send_notification_card_test.py
  docker compose run --rm bot python tools/send_notification_card_test.py --telegram-id 1713374557
  docker compose run --rm bot python tools/send_notification_card_test.py --types expiring,expired,wave2,wave3,traffic
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.database.crud.subscription import get_active_subscriptions_by_user_id, get_all_subscriptions_by_user_id
from app.database.crud.user import get_user_by_telegram_id
from app.database.database import AsyncSessionLocal
from app.localization.texts import get_texts
from app.services.monitoring_service import MonitoringService
from app.services.notification_settings_service import NotificationSettingsService
from app.utils.subscription_display import format_subscription_notify_card

ALL_TYPES = ('expiring', 'expired', 'expired_1d', 'wave2', 'wave3', 'traffic')


def _default_admin_telegram_id() -> int:
    admin_ids = settings.get_admin_ids()
    if not admin_ids:
        raise SystemExit('ADMIN_IDS is empty — pass --telegram-id')
    return admin_ids[0]


def _pick_subscription(subscriptions):
    paid = next((s for s in subscriptions if not s.is_trial), None)
    return paid or (subscriptions[0] if subscriptions else None)


async def _send_traffic_warning(service: MonitoringService, user, subscription) -> bool:
    texts = get_texts(user.language)
    traffic_limit = subscription.traffic_limit_gb or 50
    traffic_used = subscription.traffic_used_gb or (traffic_limit * 0.85)
    current_percent = (traffic_used / traffic_limit) * 100 if traffic_limit else 85.0
    notify_ctx = format_subscription_notify_card(subscription, user, texts)
    message = texts.get(
        'TRAFFIC_WARNING_ALERT',
        '⚠️ <b>Предупреждение о трафике</b>{subscription_card}\n\n'
        'Использовано: {used:.1f} / {limit} ГБ ({percent:.0f}%)\n\n'
        'Ваш лимит трафика почти исчерпан.',
    )
    message = message.format(
        used=traffic_used,
        limit=traffic_limit,
        percent=current_percent,
        subscription_card=notify_ctx['subscription_card'],
    )
    await service.bot.send_message(user.telegram_id, message, parse_mode='HTML')
    return True


async def main_async(*, telegram_id: int, types: list[str], days: int) -> None:
    async with AsyncSessionLocal() as db:
        user = await get_user_by_telegram_id(db, telegram_id)
        if user is None:
            raise SystemExit(f'User not found for telegram_id={telegram_id}')

        active = await get_active_subscriptions_by_user_id(db, user.id)
        all_subs = await get_all_subscriptions_by_user_id(db, user.id)
        subscription = _pick_subscription(active) or _pick_subscription(all_subs)
        if subscription is None:
            raise SystemExit(f'No subscription for telegram_id={telegram_id}')

    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    service = MonitoringService(bot=bot)
    sent: list[str] = []

    try:
        for kind in types:
            if kind == 'expiring':
                ok = await service._send_subscription_expiring_notification(
                    user, subscription, days, has_saved_card=False
                )
            elif kind == 'expired':
                ok = await service._send_subscription_expired_notification(user, subscription)
            elif kind == 'expired_1d':
                async with AsyncSessionLocal() as db:
                    ok = await service._send_expired_day1_notification(db, user, subscription)
            elif kind == 'wave2':
                percent = NotificationSettingsService.get_second_wave_discount_percent()
                hours = NotificationSettingsService.get_second_wave_valid_hours()
                ok = await service._send_expired_discount_notification(
                    user,
                    subscription,
                    percent,
                    datetime.now(UTC) + timedelta(hours=hours),
                    offer_id=0,
                    wave='second',
                    trigger_days=3,
                )
            elif kind == 'wave3':
                percent = NotificationSettingsService.get_third_wave_discount_percent()
                hours = NotificationSettingsService.get_third_wave_valid_hours()
                trigger_days = NotificationSettingsService.get_third_wave_trigger_days()
                ok = await service._send_expired_discount_notification(
                    user,
                    subscription,
                    percent,
                    datetime.now(UTC) + timedelta(hours=hours),
                    offer_id=0,
                    wave='third',
                    trigger_days=trigger_days,
                )
            elif kind == 'traffic':
                ok = await _send_traffic_warning(service, user, subscription)
            else:
                raise SystemExit(f'Unknown type: {kind}')

            if not ok:
                raise SystemExit(f'Notification send returned False for type={kind}')
            sent.append(kind)
            await asyncio.sleep(0.5)

        print(
            f'Sent {len(sent)} notification(s) to telegram_id={telegram_id} '
            f'(subscription_id={subscription.id}, types={",".join(sent)}, language={user.language})'
        )
    finally:
        await bot.session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description='Smoke test: subscription card notifications')
    parser.add_argument('--telegram-id', type=int, default=None, help='Target Telegram user id')
    parser.add_argument(
        '--types',
        type=str,
        default='expiring,expired,wave2,wave3,traffic',
        help=f'Comma-separated types: {",".join(ALL_TYPES)}',
    )
    parser.add_argument('--days', type=int, default=3, help='Days-until-expiry for expiring (default: 3)')
    args = parser.parse_args()

    types = [t.strip() for t in args.types.split(',') if t.strip()]
    unknown = [t for t in types if t not in ALL_TYPES]
    if unknown:
        raise SystemExit(f'Unknown types: {unknown}. Valid: {ALL_TYPES}')

    telegram_id = args.telegram_id or _default_admin_telegram_id()
    asyncio.run(main_async(telegram_id=telegram_id, types=types, days=args.days))


if __name__ == '__main__':
    main()
