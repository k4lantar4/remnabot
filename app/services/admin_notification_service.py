import asyncio
import html
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog
from aiogram import Bot, types
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from sqlalchemy import select
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.crud.promo_group import get_promo_group_by_id
from app.database.crud.subscription_event import create_subscription_event
from app.database.crud.transaction import get_transaction_by_id
from app.database.crud.user import get_user_by_id
from app.database.models import (
    AdvertisingCampaign,
    AdvertisingCampaignRegistration,
    GuestPurchase,
    PromoCodeType,
    PromoGroup,
    Subscription,
    Transaction,
    User,
)
from app.utils.message_patch import caption_exceeds_telegram_limit
from app.utils.timezone import format_local_datetime


# Стандартный формат Telegram bot token: `<numeric_id>:<random_35chars>`.
# Может появиться в str(e) от aiogram при сетевых ошибках, если транспорт
# (httpx/aiohttp) сериализует URL `https://api.telegram.org/bot<TOKEN>/...`.
# Не светим токен в логи (структурированные логи могут уехать в Sentry / ELK).
# Trailing — negative lookahead, а не `\b`: иначе токены, оканчивающиеся
# на `-` или `_`, теряли последний символ при редакции (1-char leak).
# Leading `(?<![\w-])` — намеренно НЕ матчит, если перед токеном стоит word/digit
# (например `foo123456789:AAH...`). Это trade-off против false-positive'ов
# на timestamp/UUID-подобных последовательностях. Aiogram и httpx всегда
# префиксят токен либо `bot`, либо URL-границей (`/`, пробел, кавычка),
# так что реальный corpus ошибок не страдает.
_BOT_TOKEN_RE: re.Pattern[str] = re.compile(
    r'(?<![\w-])(?:bot)?\d{6,}:[A-Za-z0-9_-]{30,}(?![A-Za-z0-9_-])',
)


def _redact_telegram_secrets(text: str) -> str:
    """Replace Telegram bot tokens in an arbitrary string with a placeholder."""
    return _BOT_TOKEN_RE.sub('bot[REDACTED]', text)


class NotificationCategory(StrEnum):
    """Категории уведомлений для маршрутизации по топикам."""

    PURCHASES = 'purchases'  # Покупки подписок, покупки с лендинга
    RENEWALS = 'renewals'  # Продления
    TRIALS = 'trials'  # Триалы
    BALANCE = 'balance'  # Пополнение баланса
    ADDONS = 'addons'  # Докупка трафика/устройств/серверов
    INFRASTRUCTURE = 'infrastructure'  # Ноды, техработы, статус панели, вебхуки
    ERRORS = 'errors'  # Ошибки бота, краши
    PROMO = 'promo'  # Промокоды, кампании, промогруппы
    PARTNERS = 'partners'  # Партнёрки, выводы, админ-действия
    TICKETS = 'tickets'  # Тикеты (уже существует)


logger = structlog.get_logger(__name__)


def _admin_notify_texts():
    from app.localization.texts import get_texts

    lang = settings.DEFAULT_LANGUAGE if isinstance(settings.DEFAULT_LANGUAGE, str) else 'fa'
    return get_texts(lang)


def _referrer_none_label() -> str:
    return _admin_notify_texts().t('ADMIN_NOTIFY_REFERRER_NONE', 'Нет')


class AdminNotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.chat_id = getattr(settings, 'ADMIN_NOTIFICATIONS_CHAT_ID', None)
        self.topic_id = getattr(settings, 'ADMIN_NOTIFICATIONS_TOPIC_ID', None)
        self.ticket_topic_id = getattr(settings, 'ADMIN_NOTIFICATIONS_TICKET_TOPIC_ID', None)
        self.enabled = getattr(settings, 'ADMIN_NOTIFICATIONS_ENABLED', False)

        # Маппинг категорий на topic_id (None = fallback на self.topic_id)
        self.category_topics: dict[NotificationCategory, int | None] = {
            NotificationCategory.PURCHASES: getattr(settings, 'ADMIN_NOTIFICATIONS_PURCHASES_TOPIC_ID', None),
            NotificationCategory.RENEWALS: getattr(settings, 'ADMIN_NOTIFICATIONS_RENEWALS_TOPIC_ID', None),
            NotificationCategory.TRIALS: getattr(settings, 'ADMIN_NOTIFICATIONS_TRIALS_TOPIC_ID', None),
            NotificationCategory.BALANCE: getattr(settings, 'ADMIN_NOTIFICATIONS_BALANCE_TOPIC_ID', None),
            NotificationCategory.ADDONS: getattr(settings, 'ADMIN_NOTIFICATIONS_ADDONS_TOPIC_ID', None),
            NotificationCategory.INFRASTRUCTURE: getattr(settings, 'ADMIN_NOTIFICATIONS_INFRASTRUCTURE_TOPIC_ID', None),
            NotificationCategory.ERRORS: getattr(settings, 'ADMIN_NOTIFICATIONS_ERRORS_TOPIC_ID', None),
            NotificationCategory.PROMO: getattr(settings, 'ADMIN_NOTIFICATIONS_PROMO_TOPIC_ID', None),
            NotificationCategory.PARTNERS: getattr(settings, 'ADMIN_NOTIFICATIONS_PARTNERS_TOPIC_ID', None),
            NotificationCategory.TICKETS: self.ticket_topic_id,
        }

        # Per-category enabled flags (default True — backwards compatible)
        self.category_enabled: dict[NotificationCategory, bool] = {}
        for cat in NotificationCategory:
            key = f'ADMIN_NOTIFICATIONS_{cat.value.upper()}_ENABLED'
            self.category_enabled[cat] = getattr(settings, key, True)

    async def _get_referrer_info(self, db: AsyncSession, referred_by_id: int | None) -> str:
        notify_texts = _admin_notify_texts()
        if not referred_by_id:
            return _referrer_none_label()

        try:
            referrer = await get_user_by_id(db, referred_by_id)
            if not referrer:
                return notify_texts.t('ADMIN_NOTIFY_REFERRER_NOT_FOUND', 'ID {id} (не найден)').format(
                    id=referred_by_id
                )

            if referrer.username:
                return notify_texts.t(
                    'ADMIN_NOTIFY_REFERRER_USERNAME', '@{username} (ID: {id})'
                ).format(username=html.escape(referrer.username), id=referred_by_id)
            if referrer.telegram_id:
                return notify_texts.t('ADMIN_NOTIFY_REFERRER_TELEGRAM_ID', 'ID {telegram_id}').format(
                    telegram_id=referrer.telegram_id
                )
            if referrer.email:
                return f'📧 {html.escape(referrer.email)}'
            return f'User#{referred_by_id}'

        except Exception as e:
            logger.error('Ошибка получения данных рефера', referred_by_id=referred_by_id, error=e)
            return notify_texts.t('ADMIN_NOTIFY_REFERRER_ID_ONLY', 'ID {id}').format(id=referred_by_id)

    async def _get_user_promo_group(self, db: AsyncSession, user: User) -> PromoGroup | None:
        if getattr(user, 'promo_group', None):
            return user.promo_group

        if not user.promo_group_id:
            return None

        try:
            await db.refresh(user, attribute_names=['promo_group'])
        except Exception:
            # relationship might not be available — fallback to direct fetch
            pass

        if getattr(user, 'promo_group', None):
            return user.promo_group

        try:
            return await get_promo_group_by_id(db, user.promo_group_id)
        except Exception as e:
            logger.error(
                'Ошибка загрузки промогруппы пользователя',
                promo_group_id=user.promo_group_id,
                telegram_id=user.telegram_id,
                e=e,
            )
            return None

    def _get_user_display(self, user: User) -> str:
        first_name = getattr(user, 'first_name', '') or ''
        if first_name:
            return html.escape(first_name)

        username = getattr(user, 'username', '') or ''
        if username:
            return html.escape(username)

        telegram_id = getattr(user, 'telegram_id', None)
        if telegram_id is None:
            email = getattr(user, 'email', None)
            if email:
                return html.escape(email)
            return f'User#{getattr(user, "id", "Unknown")}'
        return f'ID{telegram_id}'

    def _get_user_identifier_display(self, user: User) -> str:
        """Get user identifier for display in notifications (telegram_id or email)."""
        telegram_id = getattr(user, 'telegram_id', None)
        if telegram_id:
            return f'<code>{telegram_id}</code>'

        email = getattr(user, 'email', None)
        if email:
            return f'📧 {html.escape(email)}'

        return f'User#{getattr(user, "id", "Unknown")}'

    def _get_user_identifier_label(self, user: User) -> str:
        """Get label for user identifier (Telegram ID or Email)."""
        notify_texts = _admin_notify_texts()
        telegram_id = getattr(user, 'telegram_id', None)
        if telegram_id:
            return notify_texts.t('ADMIN_NOTIFY_LABEL_TELEGRAM_ID', 'Telegram ID')
        email = getattr(user, 'email', None)
        if email:
            return notify_texts.t('ADMIN_NOTIFY_LABEL_EMAIL', 'Email')
        return notify_texts.t('ADMIN_NOTIFY_LABEL_ID', 'ID')

    async def _record_subscription_event(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        user: User,
        subscription: Subscription | None,
        transaction: Transaction | None = None,
        amount_kopeks: int | None = None,
        message: str | None = None,
        extra: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        """Persist subscription-related event for external dashboards."""

        try:
            await create_subscription_event(
                db,
                user_id=user.id,
                event_type=event_type,
                subscription_id=subscription.id if subscription else None,
                transaction_id=transaction.id if transaction else None,
                amount_kopeks=amount_kopeks,
                currency=None,
                message=message,
                occurred_at=occurred_at,
                extra=extra or None,
            )
        except Exception:
            logger.error(
                'Не удалось сохранить событие подписки для пользователя',
                event_type=event_type,
                getattr=getattr(user, 'id', 'unknown'),
                exc_info=True,
            )

            try:
                await db.rollback()
            except Exception:
                logger.error(
                    'Не удалось выполнить rollback после ошибки события подписки пользователя',
                    getattr=getattr(user, 'id', 'unknown'),
                    exc_info=True,
                )

    def _format_promo_group_discounts(self, promo_group: PromoGroup) -> list[str]:
        notify_texts = _admin_notify_texts()
        discount_lines: list[str] = []

        discount_map = {
            'servers': (
                notify_texts.t('ADMIN_NOTIFY_PROMO_DISCOUNT_SERVERS', 'Серверы'),
                promo_group.server_discount_percent,
            ),
            'traffic': (
                notify_texts.t('ADMIN_NOTIFY_PROMO_DISCOUNT_TRAFFIC', 'Трафик'),
                promo_group.traffic_discount_percent,
            ),
            'devices': (
                notify_texts.t('ADMIN_NOTIFY_PROMO_DISCOUNT_DEVICES', 'Устройства'),
                promo_group.device_discount_percent,
            ),
        }

        for title, percent in discount_map.values():
            if percent and percent > 0:
                discount_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_PROMO_DISCOUNT_LINE', '• {title}: -{percent}%').format(
                        title=title, percent=percent
                    )
                )

        period_discounts_raw = promo_group.period_discounts or {}
        period_items: list[tuple[int, int]] = []

        if isinstance(period_discounts_raw, dict):
            for raw_days, raw_percent in period_discounts_raw.items():
                try:
                    days = int(raw_days)
                    percent = int(raw_percent)
                except (TypeError, ValueError):
                    continue

                if percent > 0:
                    period_items.append((days, percent))

        period_items.sort(key=lambda item: item[0])

        if period_items:
            formatted_periods = ', '.join(
                notify_texts.t('ADMIN_NOTIFY_PROMO_PERIOD_ITEM', '{days} д. — -{percent}%').format(
                    days=days, percent=percent
                )
                for days, percent in period_items
            )
            discount_lines.append(
                notify_texts.t('ADMIN_NOTIFY_PROMO_PERIODS', '• Периоды: {periods}').format(periods=formatted_periods)
            )

        if promo_group.apply_discounts_to_addons:
            discount_lines.append(
                notify_texts.t('ADMIN_NOTIFY_PROMO_ADDONS_YES', '• Доп. услуги: ✅ скидка действует')
            )
        else:
            discount_lines.append(notify_texts.t('ADMIN_NOTIFY_PROMO_ADDONS_NO', '• Доп. услуги: ❌ без скидки'))

        return discount_lines

    def _format_promo_group_block(
        self,
        promo_group: PromoGroup | None,
        *,
        title: str | None = None,
        icon: str = '🏷️',
    ) -> str:
        notify_texts = _admin_notify_texts()
        block_title = title or notify_texts.t('ADMIN_NOTIFY_PROMO_GROUP_TITLE', 'Промогруппа')
        if not promo_group:
            return notify_texts.t('ADMIN_NOTIFY_PROMO_GROUP_EMPTY', '{icon} <b>{title}:</b> —').format(
                icon=icon, title=block_title
            )

        lines = [
            notify_texts.t('ADMIN_NOTIFY_PROMO_GROUP_NAMED', '{icon} <b>{title}:</b> {name}').format(
                icon=icon, title=block_title, name=html.escape(promo_group.name)
            )
        ]

        discount_lines = self._format_promo_group_discounts(promo_group)
        if discount_lines:
            lines.append(notify_texts.t('ADMIN_NOTIFY_PROMO_DISCOUNTS_HEADER', '💸 <b>Скидки:</b>'))
            lines.extend(discount_lines)
        else:
            lines.append(notify_texts.t('ADMIN_NOTIFY_PROMO_NO_DISCOUNTS', '💸 <b>Скидки:</b> отсутствуют'))

        return '\n'.join(lines)

    def _get_promocode_type_display(self, promo_type: str | None) -> str:
        notify_texts = _admin_notify_texts()
        mapping = {
            PromoCodeType.BALANCE.value: notify_texts.t(
                'ADMIN_NOTIFY_PROMOCODE_TYPE_BALANCE', '💰 Бонус на баланс'
            ),
            PromoCodeType.SUBSCRIPTION_DAYS.value: notify_texts.t(
                'ADMIN_NOTIFY_PROMOCODE_TYPE_DAYS', '⏰ Доп. дни подписки'
            ),
            PromoCodeType.TRIAL_SUBSCRIPTION.value: notify_texts.t(
                'ADMIN_NOTIFY_PROMOCODE_TYPE_TRIAL', '🎁 Триал подписка'
            ),
            PromoCodeType.PROMO_GROUP.value: notify_texts.t(
                'ADMIN_NOTIFY_PROMOCODE_TYPE_GROUP', '👥 Промогруппа'
            ),
            PromoCodeType.DISCOUNT.value: notify_texts.t('ADMIN_NOTIFY_PROMOCODE_TYPE_DISCOUNT', '💸 Скидка'),
        }

        if not promo_type:
            return notify_texts.t('ADMIN_NOTIFY_PROMOCODE_TYPE_UNKNOWN', 'ℹ️ Не указан')

        return mapping.get(
            promo_type,
            notify_texts.t('ADMIN_NOTIFY_PROMOCODE_TYPE_RAW', 'ℹ️ {type}').format(type=promo_type),
        )

    def _format_campaign_bonus(self, campaign: AdvertisingCampaign, *, tariff_name: str | None = None) -> list[str]:
        notify_texts = _admin_notify_texts()
        if campaign.is_balance_bonus:
            return [
                notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_BONUS_BALANCE', '💰 Баланс: {amount}').format(
                    amount=settings.format_price(campaign.balance_bonus_kopeks or 0)
                ),
            ]

        if campaign.is_subscription_bonus:
            default_devices = getattr(settings, 'DEFAULT_DEVICE_LIMIT', 1)
            details = [
                notify_texts.t(
                    'ADMIN_NOTIFY_CAMPAIGN_BONUS_SUBSCRIPTION',
                    '📅 {days} дн. • 📊 {traffic} ГБ • 📱 {devices} устр.',
                ).format(
                    days=campaign.subscription_duration_days or 0,
                    traffic=campaign.subscription_traffic_gb or 0,
                    devices=campaign.subscription_device_limit or default_devices,
                ),
            ]
            if campaign.subscription_squads:
                details.append(
                    notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_BONUS_SQUADS', '🌐 Сквады: {count} шт.').format(
                        count=len(campaign.subscription_squads)
                    )
                )
            return details

        if campaign.is_tariff_bonus:
            name = tariff_name or notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_TARIFF_ID', 'ID {id}').format(
                id=campaign.tariff_id
            )
            details = [
                notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_BONUS_TARIFF', '📦 Тариф: <b>{name}</b>').format(name=name)
            ]
            if campaign.tariff_duration_days:
                details.append(
                    notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_BONUS_PERIOD', '📅 Период: {days} дней').format(
                        days=campaign.tariff_duration_days
                    )
                )
            return details

        if campaign.is_none_bonus:
            return [notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_BONUS_TRACKING', '🔗 Только отслеживание')]

        return [notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_BONUS_NONE', 'ℹ️ Бонусы не предусмотрены')]

    async def send_trial_activation_notification(
        self,
        db: AsyncSession,
        user: User,
        subscription: Subscription,
        *,
        charged_amount_kopeks: int | None = None,
    ) -> bool:
        try:
            await self._record_subscription_event(
                db,
                event_type='activation',
                user=user,
                subscription=subscription,
                transaction=None,
                amount_kopeks=charged_amount_kopeks,
                message='Trial activation',
                occurred_at=datetime.now(UTC),
                extra={
                    'charged_amount_kopeks': charged_amount_kopeks,
                    'trial_duration_days': (
                        max(1, round((subscription.end_date - subscription.start_date).total_seconds() / 86400))
                        if subscription.end_date and subscription.start_date
                        else settings.TRIAL_DURATION_DAYS
                    ),
                    'traffic_limit_gb': (
                        subscription.traffic_limit_gb
                        if subscription.traffic_limit_gb is not None
                        else settings.TRIAL_TRAFFIC_LIMIT_GB
                    ),
                    'device_limit': subscription.device_limit,
                },
            )

            if not self._is_enabled():
                return False

            notify_texts = _admin_notify_texts()
            user_status = (
                notify_texts.t('ADMIN_NOTIFY_TRIAL_USER_NEW', '🆕 Новый')
                if not user.has_had_paid_subscription
                else notify_texts.t('ADMIN_NOTIFY_TRIAL_USER_EXISTING', '🔄 Существующий')
            )
            promo_group = await self._get_user_promo_group(db, user)
            user_display = self._get_user_display(user)

            trial_device_limit = subscription.device_limit
            if trial_device_limit is None:
                fallback_forced_limit = settings.get_disabled_mode_device_limit()
                if fallback_forced_limit is not None:
                    trial_device_limit = fallback_forced_limit
                else:
                    trial_device_limit = settings.TRIAL_DEVICE_LIMIT

            payment_block = ''
            if charged_amount_kopeks and charged_amount_kopeks > 0:
                payment_block = notify_texts.t(
                    'ADMIN_NOTIFY_TRIAL_ACTIVATION_PAYMENT', '\n💳 <b>Оплата за активацию:</b> {amount}'
                ).format(amount=settings.format_price(charged_amount_kopeks))

            user_id_label = self._get_user_identifier_label(user)
            user_id_display = self._get_user_identifier_display(user)

            # Получаем название тарифа (если режим тарифов)
            tariff_name = await self._get_tariff_name(db, subscription)

            message_lines = [
                notify_texts.t('ADMIN_NOTIFY_TRIAL_TITLE', '🎯 <b>АКТИВАЦИЯ ТРИАЛА</b>'),
                '',
                notify_texts.t('ADMIN_NOTIFY_TRIAL_USER', '👤 <b>Пользователь:</b> {user}').format(user=user_display),
                notify_texts.t('ADMIN_NOTIFY_TRIAL_ID', '🆔 <b>{label}:</b> {user_id}').format(
                    label=user_id_label, user_id=user_id_display
                ),
                notify_texts.t('ADMIN_NOTIFY_TRIAL_USERNAME', '📱 <b>Username:</b> @{username}').format(
                    username=html.escape(getattr(user, 'username', None) or notify_texts.t('ADMIN_NOTIFY_USERNAME_NONE', 'отсутствует'))
                ),
                notify_texts.t('ADMIN_NOTIFY_TRIAL_STATUS', '👥 <b>Статус:</b> {status}').format(status=user_status),
                '',
            ]

            # Промогруппа — только название, без скидок
            if promo_group:
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_TRIAL_PROMO_NAMED', '🏷️ <b>Промогруппа:</b> {name}').format(
                        name=html.escape(promo_group.name)
                    )
                )
            else:
                message_lines.append(notify_texts.t('ADMIN_NOTIFY_TRIAL_PROMO_EMPTY', '🏷️ <b>Промогруппа:</b> —'))

            # Тариф триала (если есть)
            if tariff_name:
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_TRIAL_TARIFF', '📦 <b>Тариф:</b> {name}').format(name=tariff_name)
                )

            message_lines.append('')

            trial_duration_days = settings.TRIAL_DURATION_DAYS
            if subscription.end_date and subscription.start_date:
                trial_duration_days = max(
                    1, round((subscription.end_date - subscription.start_date).total_seconds() / 86400)
                )

            trial_traffic_gb = (
                subscription.traffic_limit_gb
                if subscription.traffic_limit_gb is not None
                else settings.TRIAL_TRAFFIC_LIMIT_GB
            )

            default_server = notify_texts.t('ADMIN_NOTIFY_SERVER_DEFAULT', 'По умолчанию')
            message_lines.extend(
                [
                    notify_texts.t('ADMIN_NOTIFY_TRIAL_PARAMS', '⏰ <b>Параметры триала:</b>'),
                    notify_texts.t('ADMIN_NOTIFY_TRIAL_PERIOD', '📅 Период: {days} дней').format(days=trial_duration_days),
                    notify_texts.t('ADMIN_NOTIFY_TRIAL_TRAFFIC', '📊 Трафик: {traffic}').format(
                        traffic=self._format_traffic(trial_traffic_gb)
                    ),
                    notify_texts.t('ADMIN_NOTIFY_TRIAL_DEVICES', '📱 Устройства: {devices}').format(
                        devices=trial_device_limit
                    ),
                    notify_texts.t('ADMIN_NOTIFY_TRIAL_SERVER', '🌐 Сервер: {server}').format(
                        server=subscription.connected_squads[0] if subscription.connected_squads else default_server
                    ),
                ]
            )

            if payment_block:
                message_lines.append(payment_block)

            message_lines.append('')
            message_lines.append(
                notify_texts.t('ADMIN_NOTIFY_TRIAL_VALID_UNTIL', '📆 <b>Действует до:</b> {date}').format(
                    date=format_local_datetime(subscription.end_date, '%d.%m.%Y %H:%M')
                )
            )

            # Реферер — только если есть
            if user.referred_by_id:
                referrer_info = await self._get_referrer_info(db, user.referred_by_id)
                if referrer_info != _referrer_none_label():
                    message_lines.append(
                        notify_texts.t('ADMIN_NOTIFY_TRIAL_REFERRER', '🔗 <b>Реферер:</b> {referrer}').format(
                            referrer=referrer_info
                        )
                    )

            message_lines.append('')
            message_lines.append(f'⏰ <i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M:%S")}</i>')

            return await self._send_message('\n'.join(message_lines), category=NotificationCategory.TRIALS)

        except Exception as e:
            logger.error('Ошибка отправки уведомления о триале', error=e)
            return False

    async def _get_tariff_name(self, db: AsyncSession, subscription: Subscription) -> str | None:
        """Получает название тарифа подписки, если он есть."""
        if not subscription.tariff_id:
            return None

        try:
            from app.database.crud.tariff import get_tariff_by_id

            tariff = await get_tariff_by_id(db, subscription.tariff_id)
            if tariff:
                return html.escape(tariff.name)
        except Exception:
            pass
        return None

    async def _squads_for_admin_display(
        self,
        db: AsyncSession,
        subscription: Subscription,
    ) -> list[str]:
        """Resolve squad UUIDs for admin notification text only (no DB write)."""
        try:
            await db.refresh(subscription, attribute_names=['connected_squads', 'tariff_id'])
        except Exception:
            pass

        squads = list(subscription.connected_squads or [])
        if squads:
            return squads

        if subscription.tariff_id:
            from app.database.crud.tariff import get_tariff_by_id

            tariff = await get_tariff_by_id(db, subscription.tariff_id)
            if tariff and tariff.allowed_squads:
                return list(tariff.allowed_squads)

        from app.database.crud.server_squad import get_all_server_squads

        all_servers, _ = await get_all_server_squads(db, available_only=True)
        return [s.squad_uuid for s in all_servers if s.squad_uuid]

    async def send_subscription_purchase_notification(
        self,
        db: AsyncSession,
        user: User,
        subscription: Subscription,
        transaction: Transaction | None,
        period_days: int,
        was_trial_conversion: bool = False,
        amount_kopeks: int | None = None,
        purchase_type: str | None = None,  # 'first_purchase', 'renewal', 'tariff_switch', None (auto-detect)
    ) -> bool:
        try:
            total_amount = (
                amount_kopeks if amount_kopeks is not None else (abs(transaction.amount_kopeks) if transaction else 0)
            )

            await self._record_subscription_event(
                db,
                event_type='purchase',
                user=user,
                subscription=subscription,
                transaction=transaction,
                amount_kopeks=total_amount,
                message='Subscription purchase',
                occurred_at=(transaction.completed_at or transaction.created_at) if transaction else datetime.now(UTC),
                extra={
                    'period_days': period_days,
                    'was_trial_conversion': was_trial_conversion,
                    'payment_method': self._get_payment_method_display(
                        transaction.payment_method if transaction else None
                    ),
                },
            )

            if not self._is_enabled():
                return False

            notify_texts = _admin_notify_texts()
            # Определяем тип операции и заголовок
            if purchase_type == 'tariff_switch':
                event_title = notify_texts.t('ADMIN_NOTIFY_PURCHASE_TITLE_SWITCH', '🔄 СМЕНА ТАРИФА')
                user_status = notify_texts.t('ADMIN_NOTIFY_STATUS_SWITCH', 'Смена тарифа')
            elif was_trial_conversion:
                event_title = notify_texts.t('ADMIN_NOTIFY_PURCHASE_TITLE_TRIAL', '🔄 КОНВЕРСИЯ ИЗ ТРИАЛА')
                user_status = notify_texts.t('ADMIN_NOTIFY_STATUS_TRIAL', 'Конверсия')
            elif purchase_type == 'first_purchase':
                event_title = notify_texts.t('ADMIN_NOTIFY_PURCHASE_TITLE_FIRST', '💎 ПОКУПКА ПОДПИСКИ')
                user_status = notify_texts.t('ADMIN_NOTIFY_STATUS_FIRST', 'Первая покупка')
            elif purchase_type == 'renewal' or (purchase_type is None and user.has_had_paid_subscription):
                event_title = notify_texts.t('ADMIN_NOTIFY_PURCHASE_TITLE_RENEWAL', '💎 ПРОДЛЕНИЕ ПОДПИСКИ')
                user_status = notify_texts.t('ADMIN_NOTIFY_STATUS_RENEWAL', 'Продление')
            else:
                event_title = notify_texts.t('ADMIN_NOTIFY_PURCHASE_TITLE_FIRST', '💎 ПОКУПКА ПОДПИСКИ')
                user_status = notify_texts.t('ADMIN_NOTIFY_STATUS_FIRST', 'Первая покупка')

            # Получаем название тарифа
            tariff_name = await self._get_tariff_name(db, subscription)

            display_squads = await self._squads_for_admin_display(db, subscription)
            servers_info = await self._get_servers_info(display_squads)
            payment_method = self._get_payment_method_display(transaction.payment_method if transaction else None)
            user_display = self._get_user_display(user)
            user_id_display = self._get_user_identifier_display(user)

            # Формируем компактное сообщение
            message_lines = [
                f'<b>{event_title}</b>',
                '',
                f'👤 {user_display} ({user_id_display})',
            ]

            # Добавляем username только если есть
            username = getattr(user, 'username', None)
            if username:
                message_lines.append(f'📱 @{html.escape(username)}')

            message_lines.append(f'📋 {user_status}')

            # Тариф (если есть)
            if tariff_name:
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_TARIFF_LINE', '🏷️ Тариф: <b>{name}</b>').format(name=tariff_name)
                )

            message_lines.extend(
                [
                    '',
                    notify_texts.t('ADMIN_NOTIFY_PURCHASE_PAYMENT', '💵 <b>{amount}</b> • {method}').format(
                        amount=settings.format_price(total_amount), method=payment_method
                    ),
                    notify_texts.t('ADMIN_NOTIFY_PURCHASE_PERIOD', '📅 {days} дн. • до {date}').format(
                        days=period_days, date=format_local_datetime(subscription.end_date, '%d.%m.%Y')
                    ),
                    notify_texts.t('ADMIN_NOTIFY_PURCHASE_PARAMS', '📊 {traffic} • 📱 {devices} устр.').format(
                        traffic=self._format_traffic(subscription.traffic_limit_gb),
                        devices=subscription.device_limit,
                    ),
                    f'🌐 {servers_info}',
                ]
            )

            # Баланс после покупки
            message_lines.append(
                notify_texts.t('ADMIN_NOTIFY_BALANCE_LINE', '💰 Баланс: {balance}').format(
                    balance=settings.format_price(user.balance_kopeks)
                )
            )

            # Реферер (только если есть)
            if user.referred_by_id:
                referrer_info = await self._get_referrer_info(db, user.referred_by_id)
                if referrer_info != _referrer_none_label():
                    message_lines.append(
                        notify_texts.t('ADMIN_NOTIFY_REF_LINE', '🔗 Реф: {referrer}').format(referrer=referrer_info)
                    )

            # ID транзакции (только если есть)
            if transaction:
                message_lines.append(f'🆔 #{transaction.id}')

            message_lines.extend(
                [
                    '',
                    f'<i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M")}</i>',
                ]
            )

            # Маршрутизация по категориям (зеркалит логику заголовков выше)
            if purchase_type == 'renewal' or (
                not was_trial_conversion and purchase_type is None and user.has_had_paid_subscription
            ):
                cat = NotificationCategory.RENEWALS
            else:
                cat = NotificationCategory.PURCHASES

            return await self._send_message('\n'.join(message_lines), category=cat)

        except Exception as e:
            logger.error('Ошибка отправки уведомления о покупке', error=e)
            return False

    async def send_version_update_notification(self, current_version: str, latest_version, total_updates: int) -> bool:
        """Отправляет уведомление о новых обновлениях."""
        if not self._is_enabled():
            return False

        try:
            from app.utils.markdown_to_telegram import github_markdown_to_telegram_html, truncate_for_blockquote

            repo = getattr(settings, 'VERSION_CHECK_REPO', 'fr1ngg/remnawave-bedolaga-telegram-bot')
            release_url = f'https://github.com/{repo}/releases/tag/{latest_version.tag_name}'
            repo_url = f'https://github.com/{repo}'
            timestamp = format_local_datetime(datetime.now(UTC), '%d.%m.%Y %H:%M:%S')

            notify_texts = _admin_notify_texts()
            if latest_version.prerelease:
                header = notify_texts.t('ADMIN_NOTIFY_VERSION_PRERELEASE', '🧪 <b>Pre-release</b>')
            elif latest_version.is_dev:
                header = notify_texts.t('ADMIN_NOTIFY_VERSION_DEV', '🔧 <b>Dev build</b>')
            else:
                header = notify_texts.t('ADMIN_NOTIFY_VERSION_AVAILABLE', '🆕 <b>Доступно обновление</b>')

            # -- message prefix (everything before blockquote) --
            prefix_lines = [
                header,
                '',
                f'<code>{current_version}</code>  →  <b><a href="{release_url}">{latest_version.tag_name}</a></b>',
                f'📅 {latest_version.formatted_date}',
                '',
            ]
            message_prefix = '\n'.join(prefix_lines)

            # -- message suffix (everything after blockquote) --
            suffix_lines = ['']
            if total_updates > 1:
                suffix_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_VERSION_COUNT', 'Доступно обновлений: <b>{count}</b>').format(
                        count=total_updates
                    )
                )
            suffix_lines.extend(
                [
                    notify_texts.t('ADMIN_NOTIFY_VERSION_REPO', '<a href="{url}">Репозиторий</a>').format(url=repo_url),
                    '',
                    f'<i>{timestamp}</i>',
                ]
            )
            message_suffix = '\n'.join(suffix_lines)

            # -- description in blockquote --
            raw_description = getattr(latest_version, 'full_description', '') or latest_version.short_description
            description_html = github_markdown_to_telegram_html(raw_description)

            if description_html:
                description_html = truncate_for_blockquote(
                    description_html,
                    message_prefix=message_prefix,
                    message_suffix=message_suffix,
                )
                message = f'{message_prefix}<blockquote expandable>{description_html}</blockquote>{message_suffix}'
            else:
                message = f'{message_prefix}{message_suffix}'

            return await self._send_message(message, category=NotificationCategory.INFRASTRUCTURE)

        except Exception as e:
            logger.error('Ошибка отправки уведомления об обновлении', error=e)
            return False

    async def send_version_check_error_notification(self, error_message: str, current_version: str) -> bool:
        if not self._is_enabled():
            return False

        try:
            notify_texts = _admin_notify_texts()
            message = notify_texts.t(
                'ADMIN_NOTIFY_VERSION_ERROR_BODY',
                '⚠️ <b>ОШИБКА ПРОВЕРКИ ОБНОВЛЕНИЙ</b>\n\n'
                '📦 <b>Текущая версия:</b> <code>{version}</code>\n'
                '❌ <b>Ошибка:</b> {error}\n\n'
                '🔄 Следующая попытка через час.\n'
                '⚙️ Проверьте доступность GitHub API и настройки сети.\n\n'
                '⚙️ <i>Система автоматических обновлений • {timestamp}</i>',
            ).format(
                version=current_version,
                error=error_message,
                timestamp=format_local_datetime(datetime.now(UTC), '%d.%m.%Y %H:%M:%S'),
            )

            return await self._send_message(message, category=NotificationCategory.ERRORS)

        except Exception as e:
            logger.error('Ошибка отправки уведомления об ошибке проверки версий', error=e)
            return False

    def _build_balance_topup_message(
        self,
        user: User,
        transaction: Transaction,
        old_balance: int,
        *,
        topup_status: str,
        referrer_info: str,
        subscription: Subscription | None,
        promo_group: PromoGroup | None,
    ) -> str:
        notify_texts = _admin_notify_texts()
        payment_method = self._get_payment_method_display(transaction.payment_method)
        balance_change = user.balance_kopeks - old_balance
        subscription_status = self._get_subscription_status(subscription)
        timestamp = format_local_datetime(datetime.now(UTC), '%d.%m.%Y %H:%M:%S')
        user_display = self._get_user_display(user)
        user_id_display = self._get_user_identifier_display(user)

        # --- Основной блок ---
        message_lines: list[str] = [
            notify_texts.t('ADMIN_NOTIFY_TOPUP_TITLE', '💰 <b>ПОПОЛНЕНИЕ БАЛАНСА</b>'),
            '',
            notify_texts.t('ADMIN_NOTIFY_TOPUP_USER', '👤 {user} ({user_id})').format(
                user=user_display, user_id=user_id_display
            ),
        ]

        username = getattr(user, 'username', None)
        if username:
            message_lines.append(f'📱 @{html.escape(username)}')

        message_lines.append(f'💳 {topup_status}')

        # Промогруппа -- только название
        if promo_group:
            message_lines.append(
                notify_texts.t('ADMIN_NOTIFY_TOPUP_PROMO', '🏷️ Промогруппа: {name}').format(
                    name=html.escape(promo_group.name)
                )
            )

        message_lines.append('')

        # --- Детали пополнения ---
        message_lines.extend(
            [
                notify_texts.t('ADMIN_NOTIFY_TOPUP_AMOUNT', '💵 <b>{amount}</b> | {method}').format(
                    amount=settings.format_price(transaction.amount_kopeks), method=payment_method
                ),
                '',
                notify_texts.t(
                    'ADMIN_NOTIFY_TOPUP_BALANCE_CHANGE',
                    '📉 {old} → 📈 {new} (<b>+{delta}</b>)',
                ).format(
                    old=settings.format_price(old_balance),
                    new=settings.format_price(user.balance_kopeks),
                    delta=settings.format_price(balance_change),
                ),
            ]
        )

        # --- Подписка ---
        message_lines.append(
            notify_texts.t('ADMIN_NOTIFY_TOPUP_SUBSCRIPTION', '📱 Подписка: {status}').format(
                status=subscription_status
            )
        )

        # --- Реферер (только если есть) ---
        if referrer_info and referrer_info != _referrer_none_label():
            message_lines.append(
                notify_texts.t('ADMIN_NOTIFY_TOPUP_REFERRER', '🔗 Реферер: {referrer}').format(referrer=referrer_info)
            )

        # --- Expandable blockquote с техническими деталями ---
        detail_lines: list[str] = [
            notify_texts.t('ADMIN_NOTIFY_TOPUP_TX_ID', 'ID транзакции: {id}').format(id=transaction.id),
            notify_texts.t('ADMIN_NOTIFY_TOPUP_TX_METHOD', 'Способ оплаты: {method}').format(
                method=transaction.payment_method or 'balance'
            ),
        ]

        if transaction.external_id:
            detail_lines.append(
                notify_texts.t('ADMIN_NOTIFY_TOPUP_EXTERNAL_ID', 'Внешний ID: {id}').format(id=transaction.external_id)
            )

        if transaction.description:
            desc = transaction.description
            if len(desc) > 120:
                desc = desc[:117] + '...'
            detail_lines.append(
                notify_texts.t('ADMIN_NOTIFY_TOPUP_DESCRIPTION', 'Описание: {desc}').format(desc=html.escape(desc))
            )

        if transaction.created_at:
            detail_lines.append(
                notify_texts.t('ADMIN_NOTIFY_TOPUP_CREATED', 'Создана: {date}').format(
                    date=format_local_datetime(transaction.created_at, '%d.%m.%Y %H:%M:%S')
                )
            )

        if transaction.completed_at:
            detail_lines.append(
                notify_texts.t('ADMIN_NOTIFY_TOPUP_COMPLETED', 'Завершена: {date}').format(
                    date=format_local_datetime(transaction.completed_at, '%d.%m.%Y %H:%M:%S')
                )
            )

        if transaction.receipt_uuid:
            detail_lines.append(
                notify_texts.t('ADMIN_NOTIFY_TOPUP_RECEIPT', 'Чек UUID: {uuid}').format(uuid=transaction.receipt_uuid)
            )

        blockquote_body = '\n'.join(detail_lines)
        message_lines.extend(
            [
                '',
                f'<blockquote expandable>{blockquote_body}</blockquote>',
            ]
        )

        message_lines.append(f'<i>{timestamp}</i>')

        return '\n'.join(message_lines)

    async def _reload_topup_notification_entities(
        self,
        db: AsyncSession,
        user: User,
        transaction: Transaction,
    ) -> tuple[User, Transaction, Subscription | None, PromoGroup | None]:
        refreshed_user = await get_user_by_id(db, user.id)
        if not refreshed_user:
            raise ValueError(f'Не удалось повторно загрузить пользователя {user.id} для уведомления о пополнении')

        refreshed_transaction = await get_transaction_by_id(db, transaction.id)
        if not refreshed_transaction:
            raise ValueError(f'Не удалось повторно загрузить транзакцию {transaction.id} для уведомления о пополнении')

        subscription = getattr(refreshed_user, 'subscription', None)
        promo_group = await self._get_user_promo_group(db, refreshed_user)

        return refreshed_user, refreshed_transaction, subscription, promo_group

    def _is_lazy_loading_error(self, error: Exception) -> bool:
        message = str(error).lower()
        return (
            isinstance(error, MissingGreenlet)
            or 'greenlet_spawn' in message
            or 'await_only' in message
            or 'missinggreenlet' in message
        )

    async def send_balance_topup_notification(
        self,
        user: User,
        transaction: Transaction,
        old_balance: int,
        *,
        topup_status: str,
        referrer_info: str,
        subscription: Subscription | None,
        promo_group: PromoGroup | None,
        db: AsyncSession | None = None,
    ) -> bool:
        logger.info('Начинаем отправку уведомления о пополнении баланса')

        if db:
            try:
                await self._record_subscription_event(
                    db,
                    event_type='balance_topup',
                    user=user,
                    subscription=subscription,
                    transaction=transaction,
                    amount_kopeks=transaction.amount_kopeks,
                    message='Balance top-up',
                    occurred_at=transaction.completed_at or transaction.created_at,
                    extra={
                        'status': topup_status,
                        'balance_before': old_balance,
                        'balance_after': user.balance_kopeks,
                        'referrer_info': referrer_info,
                        'promo_group_id': getattr(promo_group, 'id', None),
                        'promo_group_name': getattr(promo_group, 'name', None),
                    },
                )
            except Exception:
                logger.error(
                    'Не удалось сохранить событие пополнения баланса пользователя',
                    getattr=getattr(user, 'id', 'unknown'),
                    exc_info=True,
                )

        if not self._is_enabled():
            return False

        try:
            logger.info('Пытаемся создать сообщение уведомления')
            message = self._build_balance_topup_message(
                user,
                transaction,
                old_balance,
                topup_status=topup_status,
                referrer_info=referrer_info,
                subscription=subscription,
                promo_group=promo_group,
            )
            logger.info('Сообщение уведомления создано успешно')
        except Exception as error:
            logger.info(
                'Перехвачена ошибка при создании сообщения уведомления', __name__=type(error).__name__, error=error
            )
            if not self._is_lazy_loading_error(error):
                logger.error('Ошибка подготовки уведомления о пополнении', error=error, exc_info=True)
                return False

            if db is None:
                logger.error(
                    'Недостаточно данных для уведомления о пополнении и отсутствует доступ к БД',
                    error=error,
                    exc_info=True,
                )
                return False

            logger.warning(
                'Повторная загрузка данных для уведомления о пополнении после ошибки ленивой загрузки', error=error
            )

            try:
                logger.info('Пытаемся перезагрузить данные для уведомления')
                (
                    user,
                    transaction,
                    subscription,
                    promo_group,
                ) = await self._reload_topup_notification_entities(db, user, transaction)
                logger.info('Данные успешно перезагружены')
            except Exception as reload_error:
                logger.error(
                    'Ошибка повторной загрузки данных для уведомления о пополнении',
                    reload_error=reload_error,
                    exc_info=True,
                )
                return False

            try:
                logger.info('Пытаемся создать сообщение после перезагрузки данных')
                message = self._build_balance_topup_message(
                    user,
                    transaction,
                    old_balance,
                    topup_status=topup_status,
                    referrer_info=referrer_info,
                    subscription=subscription,
                    promo_group=promo_group,
                )
                logger.info('Сообщение успешно создано после перезагрузки данных')
            except Exception as rebuild_error:
                logger.error(
                    'Ошибка повторной подготовки уведомления о пополнении после повторной загрузки',
                    rebuild_error=rebuild_error,
                    exc_info=True,
                )
                return False

        try:
            return await self._send_message(message, category=NotificationCategory.BALANCE)
        except Exception as e:
            logger.error('Ошибка отправки уведомления о пополнении', error=e, exc_info=True)
            return False

    async def send_subscription_extension_notification(
        self,
        db: AsyncSession,
        user: User,
        subscription: Subscription,
        transaction: Transaction,
        extended_days: int,
        old_end_date: datetime,
        *,
        new_end_date: datetime | None = None,
        balance_after: int | None = None,
    ) -> bool:
        try:
            current_end_date = new_end_date or subscription.end_date
            current_balance = balance_after if balance_after is not None else user.balance_kopeks

            await self._record_subscription_event(
                db,
                event_type='renewal',
                user=user,
                subscription=subscription,
                transaction=transaction,
                amount_kopeks=abs(transaction.amount_kopeks),
                message='Subscription renewed',
                occurred_at=transaction.completed_at or transaction.created_at,
                extra={
                    'extended_days': extended_days,
                    'previous_end_date': old_end_date.isoformat(),
                    'new_end_date': current_end_date.isoformat(),
                    'payment_method': transaction.payment_method,
                    'balance_after': current_balance,
                },
            )

            if not self._is_enabled():
                return False

            payment_method = self._get_payment_method_display(transaction.payment_method)
            display_squads = await self._squads_for_admin_display(db, subscription)
            servers_info = await self._get_servers_info(display_squads)
            promo_group = await self._get_user_promo_group(db, user)
            promo_block = self._format_promo_group_block(promo_group)
            user_display = self._get_user_display(user)
            user_id_label = self._get_user_identifier_label(user)
            user_id_display = self._get_user_identifier_display(user)

            notify_texts = _admin_notify_texts()
            message = '\n'.join(
                [
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_TITLE', '⏰ <b>ПРОДЛЕНИЕ ПОДПИСКИ</b>'),
                    '',
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_USER', '👤 <b>Пользователь:</b> {user}').format(
                        user=user_display
                    ),
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_ID', '🆔 <b>{label}:</b> {user_id}').format(
                        label=user_id_label, user_id=user_id_display
                    ),
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_USERNAME', '📱 <b>Username:</b> @{username}').format(
                        username=html.escape(getattr(user, 'username', None) or 'отсутствует')
                    ),
                    '',
                    promo_block,
                    '',
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_PAYMENT', '💰 <b>Платеж:</b>'),
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_AMOUNT', '💵 Сумма: {amount}').format(
                        amount=settings.format_price(abs(transaction.amount_kopeks))
                    ),
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_METHOD', '💳 Способ: {method}').format(method=payment_method),
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_TX', '🆔 ID транзакции: {tx_id}').format(tx_id=transaction.id),
                    '',
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_SECTION', '📅 <b>Продление:</b>'),
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_DAYS', '➕ Добавлено дней: {days}').format(days=extended_days),
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_WAS', '📆 Было до: {date}').format(
                        date=format_local_datetime(old_end_date, '%d.%m.%Y %H:%M')
                    ),
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_NOW', '📆 Стало до: {date}').format(
                        date=format_local_datetime(current_end_date, '%d.%m.%Y %H:%M')
                    ),
                    '',
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_PARAMS', '📱 <b>Текущие параметры:</b>'),
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_TRAFFIC', '📊 Трафик: {traffic}').format(
                        traffic=self._format_traffic(subscription.traffic_limit_gb)
                    ),
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_DEVICES', '📱 Устройства: {devices}').format(
                        devices=subscription.device_limit
                    ),
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_SERVERS', '🌐 Серверы: {servers}').format(servers=servers_info),
                    '',
                    notify_texts.t('ADMIN_NOTIFY_RENEWAL_BALANCE_AFTER', '💰 <b>Баланс после операции:</b> {balance}').format(
                        balance=settings.format_price(current_balance)
                    ),
                    '',
                    f'<i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M:%S")}</i>',
                ]
            )

            return await self._send_message(message, category=NotificationCategory.RENEWALS)

        except Exception as e:
            logger.error('Ошибка отправки уведомления о продлении', error=e)
            return False

    async def send_promocode_activation_notification(
        self,
        db: AsyncSession,
        user: User,
        promocode_data: dict[str, Any],
        effect_description: str,
        balance_before_kopeks: int | None = None,
        balance_after_kopeks: int | None = None,
    ) -> bool:
        try:
            await self._record_subscription_event(
                db,
                event_type='promocode_activation',
                user=user,
                subscription=None,
                transaction=None,
                amount_kopeks=promocode_data.get('balance_bonus_kopeks'),
                message='Promocode activation',
                occurred_at=datetime.now(UTC),
                extra={
                    'code': promocode_data.get('code'),
                    'type': promocode_data.get('type'),
                    'subscription_days': promocode_data.get('subscription_days'),
                    'balance_bonus_kopeks': promocode_data.get('balance_bonus_kopeks'),
                    'description': effect_description,
                    'valid_until': (
                        promocode_data.get('valid_until').isoformat()
                        if isinstance(promocode_data.get('valid_until'), datetime)
                        else promocode_data.get('valid_until')
                    ),
                    'balance_before_kopeks': balance_before_kopeks,
                    'balance_after_kopeks': balance_after_kopeks,
                },
            )
        except Exception:
            logger.error(
                'Не удалось сохранить событие активации промокода пользователя',
                getattr=getattr(user, 'id', 'unknown'),
                exc_info=True,
            )

        if not self._is_enabled():
            return False

        try:
            notify_texts = _admin_notify_texts()
            promo_group = await self._get_user_promo_group(db, user)
            promo_block = self._format_promo_group_block(promo_group)
            type_display = self._get_promocode_type_display(promocode_data.get('type'))
            usage_info = f'{promocode_data.get("current_uses", 0)}/{promocode_data.get("max_uses", 0)}'
            user_display = self._get_user_display(user)
            user_id_label = self._get_user_identifier_label(user)
            user_id_display = self._get_user_identifier_display(user)
            username_none = notify_texts.t('ADMIN_NOTIFY_USERNAME_NONE', 'отсутствует')

            message_lines = [
                notify_texts.t('ADMIN_NOTIFY_PROMOCODE_TITLE', '🎫 <b>АКТИВАЦИЯ ПРОМОКОДА</b>'),
                '',
                notify_texts.t('ADMIN_NOTIFY_PROMOCODE_USER', '👤 <b>Пользователь:</b> {user}').format(
                    user=user_display
                ),
                notify_texts.t('ADMIN_NOTIFY_PROMOCODE_ID', '🆔 <b>{label}:</b> {user_id}').format(
                    label=user_id_label, user_id=user_id_display
                ),
                notify_texts.t('ADMIN_NOTIFY_PROMOCODE_USERNAME', '📱 <b>Username:</b> @{username}').format(
                    username=html.escape(getattr(user, 'username', None) or username_none)
                ),
                '',
                promo_block,
                '',
                notify_texts.t('ADMIN_NOTIFY_PROMOCODE_SECTION', '🎟️ <b>Промокод:</b>'),
                notify_texts.t('ADMIN_NOTIFY_PROMOCODE_CODE', '🔖 Код: <code>{code}</code>').format(
                    code=promocode_data.get('code')
                ),
                notify_texts.t('ADMIN_NOTIFY_PROMOCODE_TYPE', '🧾 Тип: {type}').format(type=type_display),
                notify_texts.t('ADMIN_NOTIFY_PROMOCODE_USES', '📊 Использования: {uses}').format(uses=usage_info),
            ]

            promo_type = promocode_data.get('type')
            balance_bonus = promocode_data.get('balance_bonus_kopeks', 0)
            subscription_days = promocode_data.get('subscription_days', 0)

            if promo_type == PromoCodeType.DISCOUNT.value:
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_PROMOCODE_DISCOUNT', '💸 Скидка: {percent}%').format(
                        percent=balance_bonus
                    )
                )
                if subscription_days:
                    message_lines.append(
                        notify_texts.t('ADMIN_NOTIFY_PROMOCODE_DISCOUNT_HOURS', '⏳ Срок действия скидки: {hours} ч.').format(
                            hours=subscription_days
                        )
                    )
                else:
                    message_lines.append(
                        notify_texts.t(
                            'ADMIN_NOTIFY_PROMOCODE_DISCOUNT_UNTIL_PURCHASE',
                            '⏳ Срок действия скидки: до первой покупки',
                        )
                    )
            else:
                if balance_bonus:
                    message_lines.append(
                        notify_texts.t('ADMIN_NOTIFY_PROMOCODE_BALANCE_BONUS', '💰 Бонус на баланс: {amount}').format(
                            amount=settings.format_price(balance_bonus)
                        )
                    )
                if subscription_days:
                    message_lines.append(
                        notify_texts.t('ADMIN_NOTIFY_PROMOCODE_EXTRA_DAYS', '📅 Доп. дни подписки: {days}').format(
                            days=subscription_days
                        )
                    )

            valid_until = promocode_data.get('valid_until')
            if valid_until:
                valid_until_display = (
                    format_local_datetime(valid_until, '%d.%m.%Y %H:%M')
                    if isinstance(valid_until, datetime)
                    else valid_until
                )
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_PROMOCODE_VALID_UNTIL', '⏳ Действует до: {date}').format(
                        date=valid_until_display
                    )
                )

            balance_line = (
                notify_texts.t('ADMIN_NOTIFY_PROMOCODE_BALANCE_CHANGE', '{before} → {after}').format(
                    before=settings.format_price(balance_before_kopeks),
                    after=settings.format_price(balance_after_kopeks),
                )
                if balance_before_kopeks is not None and balance_after_kopeks is not None
                else notify_texts.t('ADMIN_NOTIFY_PROMOCODE_BALANCE_UNCHANGED', 'ℹ️ Баланс не изменился')
            )

            message_lines.extend(
                [
                    '',
                    notify_texts.t('ADMIN_NOTIFY_PROMOCODE_BALANCE_SECTION', '💼 <b>Баланс:</b>'),
                    balance_line,
                    '',
                    notify_texts.t('ADMIN_NOTIFY_PROMOCODE_EFFECT_SECTION', '📝 <b>Эффект:</b>'),
                    effect_description.strip()
                    or notify_texts.t('ADMIN_NOTIFY_PROMOCODE_EFFECT_DEFAULT', '✅ Промокод активирован'),
                    '',
                    f'⏰ <i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M:%S")}</i>',
                ]
            )

            return await self._send_message('\n'.join(message_lines), category=NotificationCategory.PROMO)

        except Exception as e:
            logger.error('Ошибка отправки уведомления об активации промокода', error=e)
            return False

    async def send_campaign_link_visit_notification(
        self,
        db: AsyncSession,
        telegram_user: types.User,
        campaign: AdvertisingCampaign,
        user: User | None = None,
    ) -> bool:
        # Дедуп: если юзер уже зарегистрирован в этой кампании
        # (AdvertisingCampaignRegistration.UniqueConstraint(campaign_id, user_id))
        # — повторный /start не должен слать новое уведомление в админ-чат, иначе
        # кол-во сообщений в чате превышает реальное число регистраций в БД и
        # вводит админа в заблуждение. Для новых юзеров (user is None) уведомление
        # уходит как раньше — это первичный переход.
        if user:
            existing_registration = await db.execute(
                select(AdvertisingCampaignRegistration.id).where(
                    AdvertisingCampaignRegistration.campaign_id == campaign.id,
                    AdvertisingCampaignRegistration.user_id == user.id,
                )
            )
            if existing_registration.scalar_one_or_none() is not None:
                logger.debug(
                    'Skip campaign visit notification: user already registered in campaign',
                    user_id=user.id,
                    campaign_id=campaign.id,
                )
                return False

            try:
                await self._record_subscription_event(
                    db,
                    event_type='referral_link_visit',
                    user=user,
                    subscription=None,
                    transaction=None,
                    amount_kopeks=None,
                    message='Referral link visit',
                    occurred_at=datetime.now(UTC),
                    extra={
                        'campaign_id': campaign.id,
                        'campaign_name': campaign.name,
                        'start_parameter': campaign.start_parameter,
                        'was_registered': bool(user),
                    },
                )
            except Exception:
                logger.error(
                    'Не удалось сохранить событие перехода по кампании для пользователя',
                    getattr=getattr(user, 'id', 'unknown'),
                    exc_info=True,
                )

        if not self._is_enabled():
            return False

        try:
            notify_texts = _admin_notify_texts()
            full_name = telegram_user.full_name or telegram_user.username or str(telegram_user.id)
            user_status = (
                notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_USER_NEW', '🆕 Новый')
                if not user
                else notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_USER_EXISTING', '👥 Существующий')
            )

            message_lines = [
                notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_VISIT_TITLE', '📣 <b>ПЕРЕХОД ПО РК</b>'),
                '',
                notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_HEADER', '🧾 {name} (<code>{param}</code>)').format(
                    name=html.escape(campaign.name), param=html.escape(campaign.start_parameter)
                ),
                '',
                notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_USER', '👤 {name} (<code>{id}</code>)').format(
                    name=html.escape(full_name), id=telegram_user.id
                ),
            ]

            if telegram_user.username:
                message_lines.append(f'📱 @{html.escape(telegram_user.username)}')

            message_lines.append(
                notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_STATUS', '📋 {status}').format(status=user_status)
            )

            # Промогруппа — только если есть
            if user:
                promo_group = await self._get_user_promo_group(db, user)
                if promo_group:
                    message_lines.append(
                        notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_PROMO', '🏷️ Промогруппа: {name}').format(
                            name=html.escape(promo_group.name)
                        )
                    )

            message_lines.append('')

            # Загружаем название тарифа для tariff-бонуса
            tariff_name = None
            if campaign.is_tariff_bonus and campaign.tariff_id:
                try:
                    from app.database.crud.tariff import get_tariff_by_id

                    tariff = await get_tariff_by_id(db, campaign.tariff_id)
                    if tariff:
                        tariff_name = html.escape(tariff.name)
                except Exception:
                    pass

            # Бонус кампании
            bonus_lines = self._format_campaign_bonus(campaign, tariff_name=tariff_name)
            message_lines.extend(bonus_lines)

            message_lines.extend(
                [
                    '',
                    f'<i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M:%S")}</i>',
                ]
            )

            return await self._send_message('\n'.join(message_lines), category=NotificationCategory.PROMO)

        except Exception as e:
            logger.error('Ошибка отправки уведомления о переходе по кампании', error=e)
            return False

    async def send_campaign_registration_notification(
        self,
        db: AsyncSession,
        telegram_user_id: int,
        telegram_user_name: str,
        telegram_username: str | None,
        campaign: AdvertisingCampaign,
        user: User,
        *,
        bonus_type: str,
        balance_kopeks: int = 0,
        subscription_days: int | None = None,
        subscription_traffic_gb: int | None = None,
        subscription_device_limit: int | None = None,
        tariff_name: str | None = None,
    ) -> bool:
        """Уведомление о СОВЕРШЁННОЙ регистрации по рекламной кампании.

        Шлётся ровно один раз на каждую новую запись в advertising_campaign_registrations
        (caller передаёт is_new_registration=True). Это даёт паритет: число сообщений
        в админ-чате равно числу регистраций в кабинете.
        """
        if not self._is_enabled():
            return False

        try:
            await self._record_subscription_event(
                db,
                event_type='campaign_registration',
                user=user,
                subscription=None,
                transaction=None,
                amount_kopeks=balance_kopeks or None,
                message='Campaign registration completed',
                occurred_at=datetime.now(UTC),
                extra={
                    'campaign_id': campaign.id,
                    'campaign_name': campaign.name,
                    'start_parameter': campaign.start_parameter,
                    'bonus_type': bonus_type,
                },
            )
        except Exception:
            logger.error(
                'Не удалось сохранить событие регистрации по кампании',
                user_id=user.id,
                campaign_id=campaign.id,
                exc_info=True,
            )

        try:
            notify_texts = _admin_notify_texts()
            message_lines = [
                notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_REG_TITLE', '✅ <b>РЕГИСТРАЦИЯ ПО РК</b>'),
                '',
                notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_HEADER', '🧾 {name} (<code>{param}</code>)').format(
                    name=html.escape(campaign.name), param=html.escape(campaign.start_parameter)
                ),
                '',
                notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_USER', '👤 {name} (<code>{id}</code>)').format(
                    name=html.escape(telegram_user_name), id=telegram_user_id
                ),
            ]
            if telegram_username:
                message_lines.append(f'📱 @{html.escape(telegram_username)}')

            promo_group = await self._get_user_promo_group(db, user)
            if promo_group:
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_CAMPAIGN_PROMO', '🏷️ Промогруппа: {name}').format(
                        name=html.escape(promo_group.name)
                    )
                )

            message_lines.append('')

            bonus_lines = self._format_campaign_bonus(campaign, tariff_name=tariff_name)
            message_lines.extend(bonus_lines)

            message_lines.extend(
                [
                    '',
                    f'<i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M:%S")}</i>',
                ]
            )

            return await self._send_message('\n'.join(message_lines), category=NotificationCategory.PROMO)

        except Exception as e:
            logger.error(
                'Ошибка отправки уведомления о регистрации по кампании',
                error=str(e),
                user_id=user.id,
                campaign_id=campaign.id,
                exc_info=True,
            )
            return False

    async def send_user_promo_group_change_notification(
        self,
        db: AsyncSession,
        user: User,
        old_group: PromoGroup | None,
        new_group: PromoGroup,
        *,
        reason: str | None = None,
        initiator: User | None = None,
        automatic: bool = False,
    ) -> bool:
        try:
            await self._record_subscription_event(
                db,
                event_type='promo_group_change',
                user=user,
                subscription=None,
                transaction=None,
                message='Promo group change',
                occurred_at=datetime.now(UTC),
                extra={
                    'old_group_id': getattr(old_group, 'id', None),
                    'old_group_name': getattr(old_group, 'name', None),
                    'new_group_id': new_group.id,
                    'new_group_name': new_group.name,
                    'reason': reason,
                    'initiator_id': getattr(initiator, 'id', None),
                    'initiator_telegram_id': getattr(initiator, 'telegram_id', None),
                    'automatic': automatic,
                },
            )
        except Exception:
            logger.error(
                'Не удалось сохранить событие смены промогруппы пользователя',
                getattr=getattr(user, 'id', 'unknown'),
                exc_info=True,
            )

        if not self._is_enabled():
            return False

        try:
            notify_texts = _admin_notify_texts()
            title = (
                notify_texts.t('ADMIN_NOTIFY_PROMO_CHANGE_AUTO_TITLE', '🤖 АВТОМАТИЧЕСКАЯ СМЕНА ПРОМОГРУППЫ')
                if automatic
                else notify_texts.t('ADMIN_NOTIFY_PROMO_CHANGE_TITLE', '👥 СМЕНА ПРОМОГРУППЫ')
            )
            initiator_line = None
            if initiator:
                initiator_line = notify_texts.t(
                    'ADMIN_NOTIFY_PROMO_CHANGE_INITIATOR',
                    '👮 <b>Инициатор:</b> {name} (ID: {id})',
                ).format(name=html.escape(initiator.full_name), id=initiator.telegram_id)
            elif automatic:
                initiator_line = notify_texts.t(
                    'ADMIN_NOTIFY_PROMO_CHANGE_AUTO_INITIATOR', '🤖 Автоматическое назначение'
                )
            user_display = self._get_user_display(user)
            user_id_label = self._get_user_identifier_label(user)
            user_id_display = self._get_user_identifier_display(user)
            username_none = notify_texts.t('ADMIN_NOTIFY_USERNAME_NONE', 'отсутствует')

            message_lines = [
                title,
                '',
                notify_texts.t('ADMIN_NOTIFY_PROMO_CHANGE_USER', '👤 <b>Пользователь:</b> {user}').format(
                    user=user_display
                ),
                notify_texts.t('ADMIN_NOTIFY_PROMO_CHANGE_ID', '🆔 <b>{label}:</b> {user_id}').format(
                    label=user_id_label, user_id=user_id_display
                ),
                notify_texts.t('ADMIN_NOTIFY_PROMO_CHANGE_USERNAME', '📱 <b>Username:</b> @{username}').format(
                    username=html.escape(getattr(user, 'username', None) or username_none)
                ),
                '',
                self._format_promo_group_block(
                    new_group,
                    title=notify_texts.t('ADMIN_NOTIFY_PROMO_CHANGE_NEW_GROUP', 'Новая промогруппа'),
                    icon='🏆',
                ),
            ]

            if old_group and old_group.id != new_group.id:
                message_lines.extend(
                    [
                        '',
                        self._format_promo_group_block(
                            old_group,
                            title=notify_texts.t('ADMIN_NOTIFY_PROMO_CHANGE_OLD_GROUP', 'Предыдущая промогруппа'),
                            icon='♻️',
                        ),
                    ]
                )

            if initiator_line:
                message_lines.extend(['', initiator_line])

            if reason:
                message_lines.extend(
                    [
                        '',
                        notify_texts.t('ADMIN_NOTIFY_PROMO_CHANGE_REASON', '📝 Причина: {reason}').format(reason=reason),
                    ]
                )

            message_lines.extend(
                [
                    '',
                    notify_texts.t('ADMIN_NOTIFY_PROMO_CHANGE_BALANCE', '💰 Баланс пользователя: {balance}').format(
                        balance=settings.format_price(user.balance_kopeks)
                    ),
                    f'⏰ <i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M:%S")}</i>',
                ]
            )

            return await self._send_message('\n'.join(message_lines), category=NotificationCategory.PROMO)

        except Exception as e:
            logger.error('Ошибка отправки уведомления о смене промогруппы', error=e)
            return False

    def _resolve_topic_id(self, category: NotificationCategory | None = None) -> int | None:
        """Определяет topic_id для сообщения.

        Если указана category и для неё настроен топик — возвращает его.
        Иначе — fallback на self.topic_id (общий топик).
        """
        if category:
            topic = self.category_topics.get(category)
            if topic is not None:
                return topic
        return self.topic_id

    async def _send_message(
        self,
        text: str,
        reply_markup: types.InlineKeyboardMarkup | None = None,
        *,
        category: NotificationCategory | None = None,
    ) -> bool:
        if not self.chat_id:
            logger.warning('ADMIN_NOTIFICATIONS_CHAT_ID не настроен')
            return False

        # Per-category suppression
        if category and not self.category_enabled.get(category, True):
            logger.debug('Уведомление подавлено (категория отключена)', category=category.value)
            return False

        message_kwargs: dict[str, Any] = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': True,
        }
        thread_id = self._resolve_topic_id(category)
        if thread_id:
            message_kwargs['message_thread_id'] = thread_id
        if reply_markup is not None:
            message_kwargs['reply_markup'] = reply_markup

        # ВАЖНО: вся ветка ошибок ниже логируется через logger.warning, а не
        # logger.error. Иначе TelegramNotifierProcessor попытается переслать
        # ошибку в этот же админ-чат, упрётся в тот же flood control — петля
        # усиления (баг с node.connection_lost/restored, 7-8 webhook'ов подряд).
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                await self.bot.send_message(**message_kwargs)
                logger.info('Уведомление отправлено в чат', chat_id=self.chat_id, category=category)
                return True

            except TelegramForbiddenError:
                logger.warning('Бот не имеет прав для отправки в чат', chat_id=self.chat_id)
                return False

            except TelegramBadRequest as e:
                logger.warning(
                    'Ошибка отправки уведомления в админ-чат',
                    error=_redact_telegram_secrets(str(e))[:200],
                )
                return False

            except TelegramRetryAfter as e:
                # Flood control: ждём столько, сколько сказал Telegram (cap 30s),
                # потом ретраим. До фикса исключение проваливалось в bare
                # except → logger.error → петля через TelegramNotifierProcessor.
                requested_retry_after = max(1, int(getattr(e, 'retry_after', 1)))
                retry_after = min(requested_retry_after, 30)
                log_kwargs: dict[str, Any] = {
                    'chat_id': self.chat_id,
                    'retry_after': retry_after,
                    'attempt': attempt,
                }
                if requested_retry_after > retry_after:
                    # Telegram реально просит дольше cap'а — видимый сигнал,
                    # что бот аккаунт перегружен сильнее обычного flood-control'а.
                    log_kwargs['retry_after_requested'] = requested_retry_after
                    log_kwargs['clamped'] = True
                logger.warning('Telegram flood control при отправке в админ-чат', **log_kwargs)
                if attempt < max_attempts:
                    await asyncio.sleep(retry_after)
                    continue
                return False

            except (TelegramNetworkError, TelegramServerError) as e:
                # Транзиентные сетевые/5xx — warning, не error.
                logger.warning(
                    'Транзиентная сетевая ошибка отправки в админ-чат',
                    chat_id=self.chat_id,
                    error=_redact_telegram_secrets(str(e))[:200],
                    error_type=type(e).__name__,
                    attempt=attempt,
                )
                if attempt < max_attempts:
                    await asyncio.sleep(min(2 ** (attempt - 1), 4))
                    continue
                return False

            except Exception as e:
                logger.warning(
                    'Неожиданная ошибка при отправке в админ-чат',
                    chat_id=self.chat_id,
                    error=_redact_telegram_secrets(str(e))[:200],
                    error_type=type(e).__name__,
                )
                return False

        return False

    def _is_enabled(self) -> bool:
        return self.enabled and bool(self.chat_id)

    @property
    def is_enabled(self) -> bool:
        """Public check for whether admin notifications are configured and active."""
        return self._is_enabled()

    async def send_admin_notification(
        self,
        text: str,
        reply_markup: types.InlineKeyboardMarkup | None = None,
        *,
        category: NotificationCategory | None = None,
    ) -> bool:
        """Send a generic notification to admin chat with optional inline keyboard."""
        if not self._is_enabled():
            return False
        return await self._send_message(text, reply_markup=reply_markup, category=category)

    async def send_guest_purchase_notification(
        self,
        purchase: GuestPurchase,
        tariff_name: str,
        *,
        is_pending_activation: bool = False,
    ) -> bool:
        """Send admin notification for a guest/gift purchase (landing or cabinet)."""
        if not self._is_enabled():
            return False

        try:
            notify_texts = _admin_notify_texts()
            is_cabinet = purchase.source == 'cabinet'

            # Event title
            if is_cabinet and purchase.is_gift:
                event_title = notify_texts.t('ADMIN_NOTIFY_GUEST_CABINET_GIFT', '🎁 ПОДАРОК ИЗ КАБИНЕТА')
            elif is_pending_activation:
                event_title = notify_texts.t(
                    'ADMIN_NOTIFY_GUEST_LANDING_PENDING', '⏳ ПОКУПКА С ЛЕНДИНГА (ожидает активации)'
                )
            elif purchase.is_gift:
                event_title = notify_texts.t('ADMIN_NOTIFY_GUEST_LANDING_GIFT', '🎁 ПОКУПКА В ПОДАРОК С ЛЕНДИНГА')
            else:
                event_title = notify_texts.t('ADMIN_NOTIFY_GUEST_LANDING_PURCHASE', '🛒 ПОКУПКА С ЛЕНДИНГА')

            # Contact info
            contact_display = html.escape(purchase.contact_value or '—')
            contact_icon = '📧' if purchase.contact_type == 'email' else '📱'

            payment_method = self._get_payment_method_display(purchase.payment_method)

            message_lines = [
                f'<b>{event_title}</b>',
                '',
            ]

            if is_cabinet:
                # Cabinet gift: show buyer with link to user profile
                buyer = getattr(purchase, 'buyer', None)
                if buyer:
                    buyer_name = f'@{buyer.username}' if buyer.username else buyer.email or f'id:{buyer.id}'
                    message_lines.append(
                        notify_texts.t('ADMIN_NOTIFY_GUEST_BUYER', '👤 Покупатель: <code>{contact}</code>').format(
                            contact=html.escape(buyer_name)
                        )
                    )
                else:
                    message_lines.append(
                        notify_texts.t('ADMIN_NOTIFY_GUEST_BUYER_ICON', '{icon} Покупатель: <code>{contact}</code>').format(
                            icon=contact_icon, contact=contact_display
                        )
                    )
            else:
                # Landing: show page slug and buyer contact
                landing_slug = '—'
                try:
                    landing = purchase.landing
                    if landing:
                        landing_slug = landing.slug
                    elif purchase.landing_id:
                        landing_slug = f'ID:{purchase.landing_id}'
                except Exception:
                    if purchase.landing_id:
                        landing_slug = f'ID:{purchase.landing_id}'
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_GUEST_LANDING_PAGE', '🌐 Страница: <b>/buy/{slug}</b>').format(
                        slug=html.escape(landing_slug)
                    )
                )
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_GUEST_BUYER_ICON', '{icon} Покупатель: <code>{contact}</code>').format(
                        icon=contact_icon, contact=contact_display
                    )
                )

            if purchase.is_gift:
                if purchase.gift_recipient_value:
                    recipient_icon = '📧' if purchase.gift_recipient_type == 'email' else '📱'
                    recipient_value = html.escape(purchase.gift_recipient_value)
                    message_lines.append(
                        notify_texts.t(
                            'ADMIN_NOTIFY_GUEST_RECIPIENT', '{icon} Получатель: <code>{contact}</code>'
                        ).format(icon=recipient_icon, contact=recipient_value)
                    )
                else:
                    message_lines.append(
                        notify_texts.t(
                            'ADMIN_NOTIFY_GUEST_RECIPIENT_CODE', '🔗 Получатель: <i>по коду активации</i>'
                        )
                    )
                if purchase.gift_message:
                    raw_msg = purchase.gift_message[:100]
                    suffix = '…' if len(purchase.gift_message) > 100 else ''
                    message_lines.append(f'💬 <i>{html.escape(raw_msg)}{suffix}</i>')

            # Payment details in blockquote
            payment_lines = [
                '<blockquote>',
                notify_texts.t('ADMIN_NOTIFY_GUEST_TARIFF', '🏷️ Тариф: <b>{name}</b>').format(
                    name=html.escape(tariff_name)
                ),
                notify_texts.t('ADMIN_NOTIFY_GUEST_PERIOD', '📅 Период: {days} дн.').format(days=purchase.period_days),
                notify_texts.t('ADMIN_NOTIFY_GUEST_PAYMENT', '💵 <b>{amount}</b> • {method}').format(
                    amount=settings.format_price(purchase.amount_kopeks), method=payment_method
                ),
            ]

            if purchase.payment_id:
                payment_lines.append(f'🆔 {html.escape(str(purchase.payment_id))}')

            payment_lines.append('</blockquote>')
            message_lines.extend(payment_lines)

            message_lines.append(f'<i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M")}</i>')

            return await self._send_message('\n'.join(message_lines), category=NotificationCategory.PURCHASES)

        except Exception as e:
            logger.error('Ошибка отправки уведомления о гостевой покупке', error=e)
            return False

    async def send_webhook_notification(self, text: str) -> bool:
        """Send a generic webhook/infrastructure notification to admin chat.

        Used by RemnaWaveWebhookService for node, service, and CRM events.
        The caller is responsible for HTML-escaping all untrusted data in `text`.
        """
        if not self._is_enabled():
            return False
        return await self._send_message(text, category=NotificationCategory.INFRASTRUCTURE)

    def _get_payment_method_display(self, payment_method: str | None) -> str:
        notify_texts = _admin_notify_texts()
        if not payment_method:
            return notify_texts.t('ADMIN_NOTIFY_PAYMENT_BALANCE', '💰 С баланса')

        method_names: dict[str, str] = {
            'telegram_stars': notify_texts.t('ADMIN_NOTIFY_PAYMENT_STARS', '⭐ Telegram Stars'),
            'yookassa': notify_texts.t('ADMIN_NOTIFY_PAYMENT_YOOKASSA', '💳 YooKassa (карта)'),
            'tribute': notify_texts.t('ADMIN_NOTIFY_PAYMENT_TRIBUTE', '💎 Tribute (карта)'),
            'mulenpay': notify_texts.t('ADMIN_NOTIFY_PAYMENT_MULENPAY', '💳 {name} (карта)').format(
                name=settings.get_mulenpay_display_name()
            ),
            'pal24': notify_texts.t('ADMIN_NOTIFY_PAYMENT_PAL24', '🏦 {name} (СБП)').format(
                name=settings.get_pal24_display_name()
            ),
            'cryptobot': notify_texts.t('ADMIN_NOTIFY_PAYMENT_CRYPTO', '🪙 {name} (крипто)').format(
                name=settings.get_cryptobot_display_name()
            ),
            'heleket': notify_texts.t('ADMIN_NOTIFY_PAYMENT_CRYPTO', '🪙 {name} (крипто)').format(
                name=settings.get_heleket_display_name()
            ),
            'wata': notify_texts.t('ADMIN_NOTIFY_PAYMENT_GENERIC', '💳 {name}').format(
                name=settings.get_wata_display_name()
            ),
            'platega': notify_texts.t('ADMIN_NOTIFY_PAYMENT_GENERIC', '💳 {name}').format(
                name=settings.get_platega_display_name()
            ),
            'cloudpayments': notify_texts.t('ADMIN_NOTIFY_PAYMENT_GENERIC', '💳 {name}').format(
                name=settings.get_cloudpayments_display_name()
            ),
            'freekassa': notify_texts.t('ADMIN_NOTIFY_PAYMENT_GENERIC', '💳 {name}').format(
                name=settings.get_freekassa_display_name()
            ),
            'kassa_ai': notify_texts.t('ADMIN_NOTIFY_PAYMENT_GENERIC', '💳 {name}').format(
                name=settings.get_kassa_ai_display_name()
            ),
            'manual': notify_texts.t('ADMIN_NOTIFY_PAYMENT_MANUAL', '🛠️ Вручную (админ)'),
            'balance': notify_texts.t('ADMIN_NOTIFY_PAYMENT_BALANCE', '💰 С баланса'),
        }

        return method_names.get(
            payment_method,
            notify_texts.t('ADMIN_NOTIFY_PAYMENT_OTHER', '💳 {method}').format(method=html.escape(payment_method)),
        )

    def _format_traffic(self, traffic_gb: int) -> str:
        notify_texts = _admin_notify_texts()
        if traffic_gb == 0:
            return notify_texts.t('ADMIN_NOTIFY_TRAFFIC_UNLIMITED', '∞ Безлимит')
        return notify_texts.t('ADMIN_NOTIFY_TRAFFIC_GB', '{gb} ГБ').format(gb=traffic_gb)

    def _get_subscription_status(self, subscription: Subscription | None) -> str:
        notify_texts = _admin_notify_texts()
        if not subscription:
            return notify_texts.t('ADMIN_NOTIFY_SUBSCRIPTION_NONE', '❌ Нет подписки')

        if subscription.is_trial:
            return notify_texts.t('ADMIN_NOTIFY_SUBSCRIPTION_TRIAL', '🎯 Триал (до {date})').format(
                date=format_local_datetime(subscription.end_date, '%d.%m')
            )
        if subscription.is_active:
            return notify_texts.t('ADMIN_NOTIFY_SUBSCRIPTION_ACTIVE', '✅ Активна (до {date})').format(
                date=format_local_datetime(subscription.end_date, '%d.%m')
            )
        return notify_texts.t('ADMIN_NOTIFY_SUBSCRIPTION_INACTIVE', '❌ Неактивна')

    async def _get_servers_info(self, squad_uuids: list) -> str:
        notify_texts = _admin_notify_texts()
        if not squad_uuids:
            return notify_texts.t('ADMIN_NOTIFY_SERVERS_NONE', '❌ Нет серверов')

        try:
            from app.handlers.subscription import get_servers_display_names

            servers_names = await get_servers_display_names(squad_uuids)
            return notify_texts.t('ADMIN_NOTIFY_SERVERS_WITH_NAMES', '{count} шт. ({names})').format(
                count=len(squad_uuids), names=servers_names
            )
        except Exception as e:
            logger.warning('Не удалось получить названия серверов', error=e)
            return notify_texts.t('ADMIN_NOTIFY_SERVERS_COUNT', '{count} шт.').format(count=len(squad_uuids))

    async def send_maintenance_status_notification(
        self, event_type: str, status: str, details: dict[str, Any] = None
    ) -> bool:
        if not self._is_enabled():
            return False

        try:
            notify_texts = _admin_notify_texts()
            details = details or {}
            yes_label = notify_texts.t('ADMIN_NOTIFY_YES', 'Да')
            no_label = notify_texts.t('ADMIN_NOTIFY_NO', 'Нет')

            if event_type == 'enable':
                if details.get('auto_enabled', False):
                    icon = '⚠️'
                    title = notify_texts.t('ADMIN_NOTIFY_MAINT_AUTO_ENABLE', 'АВТОМАТИЧЕСКОЕ ВКЛЮЧЕНИЕ ТЕХРАБОТ')
                else:
                    icon = '🔧'
                    title = notify_texts.t('ADMIN_NOTIFY_MAINT_ENABLE', 'ВКЛЮЧЕНИЕ ТЕХРАБОТ')

            elif event_type == 'disable':
                icon = '✅'
                title = notify_texts.t('ADMIN_NOTIFY_MAINT_DISABLE', 'ОТКЛЮЧЕНИЕ ТЕХРАБОТ')

            elif event_type == 'api_status':
                if status == 'online':
                    icon = '🟢'
                    title = notify_texts.t('ADMIN_NOTIFY_MAINT_API_ONLINE', 'API REMNAWAVE ВОССТАНОВЛЕНО')
                else:
                    icon = '🔴'
                    title = notify_texts.t('ADMIN_NOTIFY_MAINT_API_OFFLINE', 'API REMNAWAVE НЕДОСТУПНО')

            elif event_type == 'monitoring':
                if status == 'started':
                    icon = '🔍'
                    title = notify_texts.t('ADMIN_NOTIFY_MAINT_MONITOR_STARTED', 'МОНИТОРИНГ ЗАПУЩЕН')
                else:
                    icon = '⏹️'
                    title = notify_texts.t('ADMIN_NOTIFY_MAINT_MONITOR_STOPPED', 'МОНИТОРИНГ ОСТАНОВЛЕН')
            else:
                icon = 'ℹ️'
                title = notify_texts.t('ADMIN_NOTIFY_MAINT_SYSTEM', 'СИСТЕМА ТЕХРАБОТ')

            message_parts = [f'{icon} <b>{title}</b>', '']

            if event_type == 'enable':
                if details.get('reason'):
                    message_parts.append(
                        notify_texts.t('ADMIN_NOTIFY_MAINT_REASON', '📋 <b>Причина:</b> {reason}').format(
                            reason=details['reason']
                        )
                    )

                if details.get('enabled_at'):
                    enabled_at = details['enabled_at']
                    if isinstance(enabled_at, str):
                        enabled_at = datetime.fromisoformat(enabled_at)
                    message_parts.append(
                        notify_texts.t('ADMIN_NOTIFY_MAINT_ENABLED_AT', '🕐 <b>Время включения:</b> {time}').format(
                            time=format_local_datetime(enabled_at, '%d.%m.%Y %H:%M:%S')
                        )
                    )

                message_parts.append(
                    notify_texts.t('ADMIN_NOTIFY_MAINT_AUTO_FLAG', '🤖 <b>Автоматически:</b> {value}').format(
                        value=yes_label if details.get('auto_enabled', False) else no_label
                    )
                )
                message_parts.append('')
                message_parts.append(
                    notify_texts.t(
                        'ADMIN_NOTIFY_MAINT_USERS_BLOCKED',
                        '❗ Обычные пользователи временно не могут использовать бота.',
                    )
                )

            elif event_type == 'disable':
                if details.get('disabled_at'):
                    disabled_at = details['disabled_at']
                    if isinstance(disabled_at, str):
                        disabled_at = datetime.fromisoformat(disabled_at)
                    message_parts.append(
                        notify_texts.t('ADMIN_NOTIFY_MAINT_DISABLED_AT', '🕐 <b>Время отключения:</b> {time}').format(
                            time=format_local_datetime(disabled_at, '%d.%m.%Y %H:%M:%S')
                        )
                    )

                if details.get('duration'):
                    duration = details['duration']
                    if isinstance(duration, (int, float)):
                        hours = int(duration // 3600)
                        minutes = int((duration % 3600) // 60)
                        if hours > 0:
                            duration_str = notify_texts.t(
                                'ADMIN_NOTIFY_MAINT_DURATION_HM', '{hours}ч {minutes}мин'
                            ).format(hours=hours, minutes=minutes)
                        else:
                            duration_str = notify_texts.t('ADMIN_NOTIFY_MAINT_DURATION_M', '{minutes}мин').format(
                                minutes=minutes
                            )
                        message_parts.append(
                            notify_texts.t('ADMIN_NOTIFY_MAINT_DURATION', '⏱️ <b>Длительность:</b> {duration}').format(
                                duration=duration_str
                            )
                        )

                message_parts.append(
                    notify_texts.t('ADMIN_NOTIFY_MAINT_WAS_AUTO', '🤖 <b>Было автоматическим:</b> {value}').format(
                        value=yes_label if details.get('was_auto', False) else no_label
                    )
                )
                message_parts.append('')
                message_parts.append(
                    notify_texts.t('ADMIN_NOTIFY_MAINT_SERVICE_RESTORED', '✅ Сервис снова доступен для пользователей.')
                )

            elif event_type == 'api_status':
                message_parts.append(
                    notify_texts.t('ADMIN_NOTIFY_MAINT_API_URL', '🔗 <b>API URL:</b> {url}').format(
                        url=details.get('api_url', notify_texts.t('ADMIN_NOTIFY_UNKNOWN', 'неизвестно'))
                    )
                )

                if status == 'online':
                    if details.get('response_time'):
                        message_parts.append(
                            notify_texts.t('ADMIN_NOTIFY_MAINT_RESPONSE_TIME', '⚡ <b>Время отклика:</b> {sec} сек').format(
                                sec=details['response_time']
                            )
                        )

                    if details.get('consecutive_failures', 0) > 0:
                        message_parts.append(
                            notify_texts.t(
                                'ADMIN_NOTIFY_MAINT_FAILURES_WERE', '🔄 <b>Неудачных попыток было:</b> {count}'
                            ).format(count=details['consecutive_failures'])
                        )

                    message_parts.append('')
                    message_parts.append(notify_texts.t('ADMIN_NOTIFY_MAINT_API_BACK', 'API снова отвечает на запросы.'))

                else:
                    if details.get('consecutive_failures'):
                        message_parts.append(
                            notify_texts.t('ADMIN_NOTIFY_MAINT_ATTEMPT', '🔄 <b>Попытка №:</b> {count}').format(
                                count=details['consecutive_failures']
                            )
                        )

                    if details.get('error'):
                        error_msg = str(details['error'])[:100]
                        message_parts.append(
                            notify_texts.t('ADMIN_NOTIFY_MAINT_ERROR', '❌ <b>Ошибка:</b> {error}').format(error=error_msg)
                        )

                    message_parts.append('')
                    message_parts.append(
                        notify_texts.t('ADMIN_NOTIFY_MAINT_API_FAIL_SERIES', '⚠️ Началась серия неудачных проверок API.')
                    )

            elif event_type == 'monitoring':
                if status == 'started':
                    if details.get('check_interval'):
                        message_parts.append(
                            notify_texts.t(
                                'ADMIN_NOTIFY_MAINT_CHECK_INTERVAL', '🔄 <b>Интервал проверки:</b> {sec} сек'
                            ).format(sec=details['check_interval'])
                        )

                    if details.get('auto_enable_configured') is not None:
                        auto_enable = (
                            notify_texts.t('ADMIN_NOTIFY_ENABLED', 'Включено')
                            if details['auto_enable_configured']
                            else notify_texts.t('ADMIN_NOTIFY_DISABLED', 'Отключено')
                        )
                        message_parts.append(
                            notify_texts.t('ADMIN_NOTIFY_MAINT_AUTO_ENABLE_CFG', '🤖 <b>Автовключение:</b> {value}').format(
                                value=auto_enable
                            )
                        )

                    if details.get('max_failures'):
                        message_parts.append(
                            notify_texts.t('ADMIN_NOTIFY_MAINT_MAX_FAILURES', '🎯 <b>Порог ошибок:</b> {count}').format(
                                count=details['max_failures']
                            )
                        )

                    message_parts.append('')
                    message_parts.append(
                        notify_texts.t('ADMIN_NOTIFY_MAINT_MONITOR_ACTIVE', 'Система будет следить за доступностью API.')
                    )

                else:
                    message_parts.append(
                        notify_texts.t('ADMIN_NOTIFY_MAINT_MONITOR_STOPPED_MSG', 'Автоматический мониторинг API остановлен.')
                    )

            message_parts.append('')
            message_parts.append(f'⏰ <i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M:%S")}</i>')

            message = '\n'.join(message_parts)

            return await self._send_message(message, category=NotificationCategory.INFRASTRUCTURE)

        except Exception as e:
            logger.error('Ошибка отправки уведомления о техработах', error=e)
            return False

    async def send_remnawave_panel_status_notification(self, status: str, details: dict[str, Any] = None) -> bool:
        if not self._is_enabled():
            return False

        try:
            notify_texts = _admin_notify_texts()
            details = details or {}

            status_config = {
                'online': {
                    'icon': '🟢',
                    'title': notify_texts.t('ADMIN_NOTIFY_PANEL_ONLINE', 'ПАНЕЛЬ REMNAWAVE ДОСТУПНА'),
                },
                'offline': {
                    'icon': '🔴',
                    'title': notify_texts.t('ADMIN_NOTIFY_PANEL_OFFLINE', 'ПАНЕЛЬ REMNAWAVE НЕДОСТУПНА'),
                },
                'degraded': {
                    'icon': '🟡',
                    'title': notify_texts.t('ADMIN_NOTIFY_PANEL_DEGRADED', 'ПАНЕЛЬ REMNAWAVE РАБОТАЕТ СО СБОЯМИ'),
                },
                'maintenance': {
                    'icon': '🔧',
                    'title': notify_texts.t('ADMIN_NOTIFY_PANEL_MAINTENANCE', 'ПАНЕЛЬ REMNAWAVE НА ОБСЛУЖИВАНИИ'),
                },
            }

            config = status_config.get(status, status_config['offline'])

            message_parts = [f'{config["icon"]} <b>{config["title"]}</b>', '']

            if details.get('api_url'):
                message_parts.append(
                    notify_texts.t('ADMIN_NOTIFY_PANEL_URL', '🔗 <b>URL:</b> {url}').format(url=details['api_url'])
                )

            if details.get('response_time'):
                message_parts.append(
                    notify_texts.t('ADMIN_NOTIFY_PANEL_RESPONSE', '⚡ <b>Время отклика:</b> {sec} сек').format(
                        sec=details['response_time']
                    )
                )

            if details.get('last_check'):
                last_check = details['last_check']
                if isinstance(last_check, str):
                    last_check = datetime.fromisoformat(last_check)
                message_parts.append(
                    notify_texts.t('ADMIN_NOTIFY_PANEL_LAST_CHECK', '🕐 <b>Последняя проверка:</b> {time}').format(
                        time=format_local_datetime(last_check, '%H:%M:%S')
                    )
                )

            if status == 'online':
                if details.get('uptime'):
                    message_parts.append(
                        notify_texts.t('ADMIN_NOTIFY_PANEL_UPTIME', '⏱️ <b>Время работы:</b> {uptime}').format(
                            uptime=details['uptime']
                        )
                    )

                if details.get('users_online'):
                    message_parts.append(
                        notify_texts.t('ADMIN_NOTIFY_PANEL_USERS_ONLINE', '👥 <b>Пользователей онлайн:</b> {count}').format(
                            count=details['users_online']
                        )
                    )

                message_parts.append('')
                message_parts.append(notify_texts.t('ADMIN_NOTIFY_PANEL_ALL_OK', '✅ Все системы работают нормально.'))

            elif status == 'offline':
                if details.get('error'):
                    error_msg = str(details['error'])[:150]
                    message_parts.append(
                        notify_texts.t('ADMIN_NOTIFY_PANEL_ERROR', '❌ <b>Ошибка:</b> {error}').format(error=error_msg)
                    )

                if details.get('consecutive_failures'):
                    message_parts.append(
                        notify_texts.t('ADMIN_NOTIFY_PANEL_FAILURES', '🔄 <b>Неудачных попыток:</b> {count}').format(
                            count=details['consecutive_failures']
                        )
                    )

                message_parts.append('')
                message_parts.append(
                    notify_texts.t(
                        'ADMIN_NOTIFY_PANEL_OFFLINE_HINT',
                        '⚠️ Панель недоступна. Проверьте соединение и статус сервера.',
                    )
                )

            elif status == 'degraded':
                if details.get('issues'):
                    issues = details['issues']
                    if isinstance(issues, list):
                        message_parts.append(
                            notify_texts.t('ADMIN_NOTIFY_PANEL_ISSUES', '⚠️ <b>Обнаруженные проблемы:</b>')
                        )
                        for issue in issues[:3]:
                            message_parts.append(f'   • {issue}')
                    else:
                        message_parts.append(
                            notify_texts.t('ADMIN_NOTIFY_PANEL_ISSUE', '⚠️ <b>Проблема:</b> {issue}').format(issue=issues)
                        )

                message_parts.append('')
                message_parts.append(
                    notify_texts.t('ADMIN_NOTIFY_PANEL_DEGRADED_HINT', 'Панель работает, но возможны задержки или сбои.')
                )

            elif status == 'maintenance':
                if details.get('maintenance_reason'):
                    message_parts.append(
                        notify_texts.t('ADMIN_NOTIFY_PANEL_MAINT_REASON', '🔧 <b>Причина:</b> {reason}').format(
                            reason=html.escape(details['maintenance_reason'])
                        )
                    )

                if details.get('estimated_duration'):
                    message_parts.append(
                        notify_texts.t('ADMIN_NOTIFY_PANEL_MAINT_DURATION', '⏰ <b>Ожидаемая длительность:</b> {duration}').format(
                            duration=details['estimated_duration']
                        )
                    )

                message_parts.append('')
                message_parts.append(
                    notify_texts.t('ADMIN_NOTIFY_PANEL_MAINT_HINT', 'Панель временно недоступна для обслуживания.')
                )

            message_parts.append('')
            message_parts.append(f'⏰ <i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M:%S")}</i>')

            message = '\n'.join(message_parts)

            return await self._send_message(message, category=NotificationCategory.INFRASTRUCTURE)

        except Exception as e:
            logger.error('Ошибка отправки уведомления о статусе панели Remnawave', error=e)
            return False

    async def send_subscription_update_notification(
        self,
        db: AsyncSession,
        user: User,
        subscription: Subscription,
        update_type: str,
        old_value: Any,
        new_value: Any,
        price_paid: int = 0,
    ) -> bool:
        if not self._is_enabled():
            return False

        try:
            notify_texts = _admin_notify_texts()
            user_display = self._get_user_display(user)
            user_id_display = self._get_user_identifier_display(user)

            # Определяем заголовок по типу операции
            update_titles = {
                'traffic': notify_texts.t('ADMIN_NOTIFY_ADDON_TRAFFIC_TITLE', '📊 ДОКУПКА ТРАФИКА'),
                'devices': notify_texts.t('ADMIN_NOTIFY_ADDON_DEVICES_TITLE', '📱 ДОКУПКА УСТРОЙСТВ'),
                'servers': notify_texts.t('ADMIN_NOTIFY_ADDON_SERVERS_TITLE', '🌐 СМЕНА СЕРВЕРОВ'),
            }
            title = update_titles.get(
                update_type, notify_texts.t('ADMIN_NOTIFY_ADDON_GENERIC_TITLE', '⚙️ ИЗМЕНЕНИЕ ПОДПИСКИ')
            )

            # Получаем название тарифа
            tariff_name = await self._get_tariff_name(db, subscription)

            # Формируем компактное сообщение
            message_lines = [
                f'<b>{title}</b>',
                '',
                notify_texts.t('ADMIN_NOTIFY_ADDON_USER', '👤 {user} ({user_id})').format(
                    user=user_display, user_id=user_id_display
                ),
            ]

            # Добавляем username только если есть
            username = getattr(user, 'username', None)
            if username:
                message_lines.append(f'📱 @{html.escape(username)}')

            # Тариф (если есть)
            if tariff_name:
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_ADDON_TARIFF', '🏷️ Тариф: <b>{name}</b>').format(name=tariff_name)
                )

            message_lines.append('')

            # Форматируем изменение в зависимости от типа
            if update_type == 'servers':
                old_servers_info = await self._format_servers_detailed(old_value)
                new_servers_info = await self._format_servers_detailed(new_value)
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_ADDON_CHANGE', '🔄 {old} → {new}').format(
                        old=old_servers_info, new=new_servers_info
                    )
                )
            elif update_type == 'traffic':
                old_formatted = self._format_update_value(old_value, update_type)
                new_formatted = self._format_update_value(new_value, update_type)
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_ADDON_CHANGE', '🔄 {old} → {new}').format(
                        old=old_formatted, new=new_formatted
                    )
                )
            elif update_type == 'devices':
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_ADDON_DEVICES_CHANGE', '🔄 {old} → {new} устр.').format(
                        old=old_value, new=new_value
                    )
                )
            else:
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_ADDON_CHANGE', '🔄 {old} → {new}').format(old=old_value, new=new_value)
                )

            # Стоимость операции
            if price_paid > 0:
                message_lines.append(f'💵 <b>{settings.format_price(price_paid)}</b>')
            else:
                message_lines.append(notify_texts.t('ADMIN_NOTIFY_ADDON_FREE', '💸 Бесплатно'))

            message_lines.extend(
                [
                    '',
                    notify_texts.t('ADMIN_NOTIFY_ADDON_UNTIL', '📅 До {date}').format(
                        date=format_local_datetime(subscription.end_date, '%d.%m.%Y')
                    ),
                    notify_texts.t('ADMIN_NOTIFY_ADDON_BALANCE', '💰 Баланс: {balance}').format(
                        balance=settings.format_price(user.balance_kopeks)
                    ),
                ]
            )

            # Реферер (только если есть)
            if user.referred_by_id:
                referrer_info = await self._get_referrer_info(db, user.referred_by_id)
                if referrer_info != _referrer_none_label():
                    message_lines.append(
                        notify_texts.t('ADMIN_NOTIFY_ADDON_REF', '🔗 Реф: {referrer}').format(referrer=referrer_info)
                    )

            message_lines.extend(
                [
                    '',
                    f'<i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M")}</i>',
                ]
            )

            return await self._send_message('\n'.join(message_lines), category=NotificationCategory.ADDONS)

        except Exception as e:
            logger.error('Ошибка отправки уведомления об изменении подписки', error=e)
            return False

    async def _format_servers_detailed(self, server_uuids: list[str]) -> str:
        notify_texts = _admin_notify_texts()
        if not server_uuids:
            return notify_texts.t('ADMIN_NOTIFY_SERVERS_NONE_SHORT', 'Нет серверов')

        try:
            from app.handlers.subscription import get_servers_display_names

            servers_names = await get_servers_display_names(server_uuids)
            none_label = notify_texts.t('ADMIN_NOTIFY_SERVERS_NONE_SHORT', 'Нет серверов')

            if servers_names and servers_names != none_label:
                return notify_texts.t('ADMIN_NOTIFY_SERVERS_DETAILED', '{count} серверов ({names})').format(
                    count=len(server_uuids), names=servers_names
                )
            return notify_texts.t('ADMIN_NOTIFY_SERVERS_COUNT_ONLY', '{count} серверов').format(
                count=len(server_uuids)
            )

        except Exception as e:
            logger.warning('Ошибка получения названий серверов для уведомления', error=e)
            return notify_texts.t('ADMIN_NOTIFY_SERVERS_COUNT_ONLY', '{count} серверов').format(
                count=len(server_uuids)
            )

    def _format_update_value(self, value: Any, update_type: str) -> str:
        notify_texts = _admin_notify_texts()
        if update_type == 'traffic':
            if value == 0:
                return notify_texts.t('ADMIN_NOTIFY_TRAFFIC_UNLIMITED_SHORT', '♾ Безлимитный')
            return notify_texts.t('ADMIN_NOTIFY_TRAFFIC_GB', '{gb} ГБ').format(gb=value)
        if update_type == 'devices':
            return notify_texts.t('ADMIN_NOTIFY_DEVICES_COUNT', '{count} устройств').format(count=value)
        if update_type == 'servers':
            if isinstance(value, list):
                return notify_texts.t('ADMIN_NOTIFY_SERVERS_COUNT_ONLY', '{count} серверов').format(
                    count=len(value)
                )
            return str(value)
        return str(value)

    async def send_partner_application_notification(
        self,
        user: User,
        application_data: dict[str, Any],
    ) -> bool:
        """Уведомление о новой заявке на партнёрку."""
        if not self._is_enabled():
            return False

        try:
            notify_texts = _admin_notify_texts()
            user_display = self._get_user_display(user)
            user_id_display = self._get_user_identifier_display(user)

            message_lines = [
                notify_texts.t('ADMIN_NOTIFY_PARTNER_APP_TITLE', '🤝 <b>ЗАЯВКА НА ПАРТНЁРКУ</b>'),
                '',
                notify_texts.t('ADMIN_NOTIFY_PARTNER_USER', '👤 {user} ({user_id})').format(
                    user=user_display, user_id=user_id_display
                ),
            ]

            username = getattr(user, 'username', None)
            if username:
                message_lines.append(f'📱 @{html.escape(username)}')

            message_lines.append('')

            if application_data.get('company_name'):
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_PARTNER_COMPANY', '🏢 Компания: {name}').format(
                        name=html.escape(str(application_data['company_name']))
                    )
                )
            if application_data.get('telegram_channel'):
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_PARTNER_CHANNEL', '📢 Канал: {channel}').format(
                        channel=html.escape(str(application_data['telegram_channel']))
                    )
                )
            if application_data.get('website_url'):
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_PARTNER_WEBSITE', '🌐 Сайт: {url}').format(
                        url=html.escape(str(application_data['website_url']))
                    )
                )
            if application_data.get('description'):
                desc = str(application_data['description'])
                if len(desc) > 200:
                    desc = desc[:197] + '...'
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_PARTNER_DESCRIPTION', '📝 {desc}').format(desc=html.escape(desc))
                )
            if application_data.get('expected_monthly_referrals'):
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_PARTNER_REFERRALS', '👥 Ожидаемых рефералов: {count}/мес').format(
                        count=application_data['expected_monthly_referrals']
                    )
                )
            if application_data.get('desired_commission_percent'):
                message_lines.append(
                    notify_texts.t('ADMIN_NOTIFY_PARTNER_COMMISSION', '💰 Желаемая комиссия: {percent}%').format(
                        percent=application_data['desired_commission_percent']
                    )
                )

            message_lines.extend(
                [
                    '',
                    f'⏰ <i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M:%S")}</i>',
                ]
            )

            return await self._send_message('\n'.join(message_lines), category=NotificationCategory.PARTNERS)

        except Exception as e:
            logger.error('Ошибка отправки уведомления о заявке на партнёрку', error=e)
            return False

    async def send_withdrawal_request_notification(
        self,
        user: User,
        amount_kopeks: int,
        payment_details: str | None = None,
    ) -> bool:
        """Уведомление о запросе на вывод средств."""
        if not self._is_enabled():
            return False

        try:
            notify_texts = _admin_notify_texts()
            user_display = self._get_user_display(user)
            user_id_display = self._get_user_identifier_display(user)

            message_lines = [
                notify_texts.t('ADMIN_NOTIFY_WITHDRAWAL_TITLE', '💸 <b>ЗАПРОС НА ВЫВОД СРЕДСТВ</b>'),
                '',
                notify_texts.t('ADMIN_NOTIFY_PARTNER_USER', '👤 {user} ({user_id})').format(
                    user=user_display, user_id=user_id_display
                ),
            ]

            username = getattr(user, 'username', None)
            if username:
                message_lines.append(f'📱 @{html.escape(username)}')

            message_lines.extend(
                [
                    '',
                    notify_texts.t('ADMIN_NOTIFY_WITHDRAWAL_AMOUNT', '💵 <b>Сумма: {amount}</b>').format(
                        amount=settings.format_price(amount_kopeks)
                    ),
                    notify_texts.t('ADMIN_NOTIFY_WITHDRAWAL_BALANCE', '💰 Баланс: {balance}').format(
                        balance=settings.format_price(user.balance_kopeks)
                    ),
                ]
            )

            if payment_details:
                details = str(payment_details)
                if len(details) > 200:
                    details = details[:197] + '...'
                message_lines.extend(
                    [
                        '',
                        notify_texts.t('ADMIN_NOTIFY_WITHDRAWAL_DETAILS', '💳 Реквизиты: {details}').format(
                            details=html.escape(details)
                        ),
                    ]
                )

            message_lines.extend(
                [
                    '',
                    f'⏰ <i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M:%S")}</i>',
                ]
            )

            return await self._send_message('\n'.join(message_lines), category=NotificationCategory.PARTNERS)

        except Exception as e:
            logger.error('Ошибка отправки уведомления о запросе на вывод', error=e)
            return False

    async def send_bulk_ban_notification(
        self,
        admin_user_id: int,
        successfully_banned: int,
        not_found: int,
        errors: int,
        admin_name: str = 'Администратор',
    ) -> bool:
        """Отправляет уведомление о массовой блокировке пользователей"""
        if not self._is_enabled():
            return False

        try:
            message_lines = [
                '🛑 <b>МАССОВАЯ БЛОКИРОВКА ПОЛЬЗОВАТЕЛЕЙ</b>',
                '',
                f'👮 <b>Администратор:</b> {html.escape(admin_name)}',
                f'🆔 <b>ID администратора:</b> {admin_user_id}',
                '',
                '📊 <b>Результаты:</b>',
                f'✅ Успешно заблокировано: {successfully_banned}',
                f'❌ Не найдено: {not_found}',
                f'💥 Ошибок: {errors}',
            ]

            total_processed = successfully_banned + not_found + errors
            if total_processed > 0:
                success_rate = (successfully_banned / total_processed) * 100
                message_lines.append(f'📈 Успешность: {success_rate:.1f}%')

            message_lines.extend(
                [
                    '',
                    f'⏰ <i>{format_local_datetime(datetime.now(UTC), "%d.%m.%Y %H:%M:%S")}</i>',
                ]
            )

            message = '\n'.join(message_lines)
            return await self._send_message(message, category=NotificationCategory.PARTNERS)

        except Exception as e:
            logger.error('Ошибка отправки уведомления о массовой блокировке', error=e)
            return False

    async def send_ticket_event_notification(
        self,
        text: str,
        keyboard: types.InlineKeyboardMarkup | None = None,
        *,
        media_file_id: str | None = None,
        media_type: str | None = None,
    ) -> bool:
        """Публичный метод для отправки уведомлений по тикетам в админ-топик.
        Учитывает настройки включенности в settings.
        Если передан media_file_id, отправляет медиа в тот же топик вместе с текстом.
        """
        # Respect runtime toggle for admin ticket notifications
        try:
            from app.services.support_settings_service import SupportSettingsService

            runtime_enabled = SupportSettingsService.get_admin_ticket_notifications_enabled()
        except Exception:
            runtime_enabled = True
        if not (self._is_enabled() and runtime_enabled):
            logger.info(
                'Ticket notification skipped: _is_enabled=, runtime_enabled',
                _is_enabled=self._is_enabled(),
                runtime_enabled=runtime_enabled,
            )
            return False

        # Если есть медиа, отправляем фото с текстом как caption (если влезает) или текст + фото
        if media_file_id and media_type == 'photo':
            return await self._send_ticket_photo_notification(text, media_file_id, keyboard)

        return await self._send_message(text, reply_markup=keyboard, category=NotificationCategory.TICKETS)

    async def _send_ticket_photo_notification(
        self,
        text: str,
        photo_file_id: str,
        keyboard: types.InlineKeyboardMarkup | None = None,
    ) -> bool:
        """Отправить фото с текстом в тикет-топик.
        Если текст помещается в caption (≤1024 символов после парсинга HTML) — фото с caption.
        Иначе — сначала текст, потом фото в тот же топик.
        """
        if not self.chat_id:
            return False

        thread_id = self._resolve_topic_id(category=NotificationCategory.TICKETS)

        try:
            if not caption_exceeds_telegram_limit(text):
                # Фото с caption — всё в одном сообщении
                photo_kwargs: dict = {
                    'chat_id': self.chat_id,
                    'photo': photo_file_id,
                    'caption': text,
                    'parse_mode': 'HTML',
                }
                if thread_id:
                    photo_kwargs['message_thread_id'] = thread_id
                if keyboard:
                    photo_kwargs['reply_markup'] = keyboard
                await self.bot.send_photo(**photo_kwargs)
            else:
                # Текст отдельно, фото следом в тот же топик
                await self._send_message(text, reply_markup=keyboard, category=NotificationCategory.TICKETS)
                photo_kwargs = {
                    'chat_id': self.chat_id,
                    'photo': photo_file_id,
                }
                if thread_id:
                    photo_kwargs['message_thread_id'] = thread_id
                await self.bot.send_photo(**photo_kwargs)

            return True
        except Exception as e:
            logger.error('Ошибка отправки фото-уведомления тикета', error=e)
            # Fallback: отправляем хотя бы текст
            return await self._send_message(text, reply_markup=keyboard, category=NotificationCategory.TICKETS)

    async def send_suspicious_traffic_notification(self, message: str, bot: Bot, topic_id: int | None = None) -> bool:
        """
        Отправляет уведомление о подозрительной активности трафика

        Args:
            message: текст уведомления
            bot: экземпляр бота для отправки сообщения
            topic_id: ID топика для отправки уведомления (если не указан, использует стандартный)
        """
        if not self.chat_id:
            logger.warning('ADMIN_NOTIFICATIONS_CHAT_ID не настроен')
            return False

        # Используем специальный топик для подозрительной активности, если он задан
        notification_topic_id = topic_id or self.topic_id

        try:
            message_kwargs = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True,
            }

            if notification_topic_id:
                message_kwargs['message_thread_id'] = notification_topic_id

            await bot.send_message(**message_kwargs)
            logger.info(
                'Уведомление о подозрительной активности отправлено в чат топик',
                chat_id=self.chat_id,
                notification_topic_id=notification_topic_id,
            )
            return True

        except TelegramForbiddenError:
            logger.error('Бот не имеет прав для отправки в чат', chat_id=self.chat_id)
            return False
        except TelegramBadRequest as e:
            logger.error('Ошибка отправки уведомления о подозрительной активности', error=e)
            return False
        except Exception as e:
            logger.error('Неожиданная ошибка при отправке уведомления о подозрительной активности', error=e)
            return False
