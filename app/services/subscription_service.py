import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import Subscription, User, SubscriptionStatus, PromoGroup
from app.external.remnawave_api import (
    RemnaWaveAPI, RemnaWaveUser, UserStatus,
    TrafficLimitStrategy, RemnaWaveAPIError
)
from app.database.crud.user import get_user_by_id
from app.utils.pricing_utils import (
    calculate_months_from_days,
    get_remaining_months,
    calculate_prorated_price,
    validate_pricing_calculation
)
from app.utils.subscription_utils import (
    resolve_hwid_device_limit_for_payload,
)

logger = logging.getLogger(__name__)


def _resolve_discount_percent(
    user: Optional[User],
    promo_group: Optional[PromoGroup],
    category: str,
    *,
    period_days: Optional[int] = None,
) -> int:
    if user is not None:
        try:
            return user.get_promo_discount(category, period_days)
        except AttributeError:
            pass

    if promo_group is not None:
        return promo_group.get_discount_percent(category, period_days)

    return 0


def _resolve_addon_discount_percent(
    user: Optional[User],
    promo_group: Optional[PromoGroup],
    category: str,
    *,
    period_days: Optional[int] = None,
) -> int:
    group = promo_group or (user.get_primary_promo_group() if user else None)

    if group is not None and not getattr(group, "apply_discounts_to_addons", True):
        return 0

    return _resolve_discount_percent(
        user,
        promo_group,
        category,
        period_days=period_days,
    )

def get_traffic_reset_strategy():
    from app.config import settings
    strategy = settings.DEFAULT_TRAFFIC_RESET_STRATEGY.upper()
    
    strategy_mapping = {
        'NO_RESET': 'NO_RESET',
        'DAY': 'DAY', 
        'WEEK': 'WEEK',
        'MONTH': 'MONTH'
    }
    
    mapped_strategy = strategy_mapping.get(strategy, 'NO_RESET')
    logger.info(f"🔄 Traffic reset strategy from config: {strategy} -> {mapped_strategy}")
    return getattr(TrafficLimitStrategy, mapped_strategy)


class SubscriptionService:

    def __init__(self):
        self._config_error: Optional[str] = None
        self.api: Optional[RemnaWaveAPI] = None
        self._last_config_signature: Optional[Tuple[str, ...]] = None

        self._refresh_configuration()

    def _refresh_configuration(self) -> None:
        auth_params = settings.get_remnawave_auth_params()
        base_url = (auth_params.get("base_url") or "").strip()
        api_key = (auth_params.get("api_key") or "").strip()
        secret_key = (auth_params.get("secret_key") or "").strip() or None
        username = (auth_params.get("username") or "").strip() or None
        password = (auth_params.get("password") or "").strip() or None
        auth_type = (auth_params.get("auth_type") or "").strip() or None

        config_signature = (
            base_url,
            api_key,
            secret_key or "",
            username or "",
            password or "",
            auth_type or "",
        )

        if config_signature == self._last_config_signature:
            return

        if not base_url:
            self._config_error = "REMNAWAVE_API_URL not configured"
            self.api = None
        elif not api_key:
            self._config_error = "REMNAWAVE_API_KEY not configured"
            self.api = None
        else:
            self._config_error = None
            self.api = RemnaWaveAPI(
                base_url=base_url,
                api_key=api_key,
                secret_key=secret_key,
                username=username,
                password=password,
            )

        if self._config_error:
            logger.warning(
                "RemnaWave API unavailable: %s. Subscription service will work in offline mode.",
                self._config_error
            )

        self._last_config_signature = config_signature

    @property
    def is_configured(self) -> bool:
        return self._config_error is None

    @property
    def configuration_error(self) -> Optional[str]:
        return self._config_error

    def _ensure_configured(self) -> None:
        self._refresh_configuration()
        if not self.api or not self.is_configured:
            raise RemnaWaveAPIError(
                self._config_error or "RemnaWave API not configured"
            )

    @asynccontextmanager
    async def get_api_client(self):
        self._ensure_configured()
        assert self.api is not None
        async with self.api as api:
            yield api
    
    async def create_remnawave_user(
        self,
        db: AsyncSession,
        subscription: Subscription,
        *,
        reset_traffic: bool = False,
        reset_reason: Optional[str] = None,
    ) -> Optional[RemnaWaveUser]:
        
        try:
            user = await get_user_by_id(db, subscription.user_id)
            if not user:
                logger.error(f"User {subscription.user_id} not found")
                return None
            
            validation_success = await self.validate_and_clean_subscription(db, subscription, user)
            if not validation_success:
                logger.error(f"Subscription validation error for user {user.telegram_id}")
                return None
            
            async with self.get_api_client() as api:
                hwid_limit = resolve_hwid_device_limit_for_payload(subscription)
                existing_users = await api.get_user_by_telegram_id(user.telegram_id)
                if existing_users:
                    logger.info(f"🔄 Found existing user in panel for {user.telegram_id}")
                    remnawave_user = existing_users[0]
                    
                    try:
                        await api.reset_user_devices(remnawave_user.uuid)
                        logger.info(f"🔧 Reset HWID devices for user {user.telegram_id}")
                    except Exception as hwid_error:
                        logger.warning(f"⚠️ Failed to reset HWID: {hwid_error}")
                    
                    update_kwargs = dict(
                        uuid=remnawave_user.uuid,
                        status=UserStatus.ACTIVE,
                        expire_at=subscription.end_date,
                        traffic_limit_bytes=self._gb_to_bytes(subscription.traffic_limit_gb),
                        traffic_limit_strategy=get_traffic_reset_strategy(),
                        description=settings.format_remnawave_user_description(
                            full_name=user.full_name,
                            username=user.username,
                            telegram_id=user.telegram_id
                        ),
                        active_internal_squads=subscription.connected_squads,
                    )

                    if hwid_limit is not None:
                        update_kwargs['hwid_device_limit'] = hwid_limit

                    updated_user = await api.update_user(**update_kwargs)
                    
                    if reset_traffic:
                        await self._reset_user_traffic(
                            api,
                            updated_user.uuid,
                            user.telegram_id,
                            reset_reason,
                        )

                else:
                    logger.info(f"🆕 Creating new user in panel for {user.telegram_id}")
                    username = settings.format_remnawave_username(
                        full_name=user.full_name,
                        username=user.username,
                        telegram_id=user.telegram_id,
                    )
                    create_kwargs = dict(
                        username=username,
                        expire_at=subscription.end_date,
                        status=UserStatus.ACTIVE,
                        traffic_limit_bytes=self._gb_to_bytes(subscription.traffic_limit_gb),
                        traffic_limit_strategy=get_traffic_reset_strategy(),
                        telegram_id=user.telegram_id,
                        description=settings.format_remnawave_user_description(
                            full_name=user.full_name,
                            username=user.username,
                            telegram_id=user.telegram_id
                        ),
                        active_internal_squads=subscription.connected_squads,
                    )

                    if hwid_limit is not None:
                        create_kwargs['hwid_device_limit'] = hwid_limit

                    updated_user = await api.create_user(**create_kwargs)

                    if reset_traffic:
                        await self._reset_user_traffic(
                            api,
                            updated_user.uuid,
                            user.telegram_id,
                            reset_reason,
                        )

                subscription.remnawave_short_uuid = updated_user.short_uuid
                subscription.subscription_url = updated_user.subscription_url
                subscription.subscription_crypto_link = updated_user.happ_crypto_link
                user.remnawave_uuid = updated_user.uuid
                
                await db.commit()
                
                logger.info(f"✅ Created/updated RemnaWave user for subscription {subscription.id}")
                logger.info(f"🔗 Subscription link: {updated_user.subscription_url}")
                strategy_name = settings.DEFAULT_TRAFFIC_RESET_STRATEGY
                logger.info(f"📊 Traffic reset strategy: {strategy_name}")
                return updated_user
                
        except RemnaWaveAPIError as e:
            logger.error(f"RemnaWave API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating RemnaWave user: {e}")
            return None
    
    async def update_remnawave_user(
        self,
        db: AsyncSession,
        subscription: Subscription,
        *,
        reset_traffic: bool = False,
        reset_reason: Optional[str] = None,
    ) -> Optional[RemnaWaveUser]:
        
        try:
            user = await get_user_by_id(db, subscription.user_id)
            if not user or not user.remnawave_uuid:
                logger.error(f"RemnaWave UUID not found for user {subscription.user_id}")
                return None
            
            current_time = datetime.utcnow()
            is_actually_active = (subscription.status == SubscriptionStatus.ACTIVE.value and 
                                 subscription.end_date > current_time)
            
            if (subscription.status == SubscriptionStatus.ACTIVE.value and 
                subscription.end_date <= current_time):
                
                subscription.status = SubscriptionStatus.EXPIRED.value
                subscription.updated_at = current_time
                await db.commit()
                is_actually_active = False
                logger.info(f"🔔 Subscription {subscription.id} status automatically changed to 'expired'")
            
            async with self.get_api_client() as api:
                hwid_limit = resolve_hwid_device_limit_for_payload(subscription)

                update_kwargs = dict(
                    uuid=user.remnawave_uuid,
                    status=UserStatus.ACTIVE if is_actually_active else UserStatus.EXPIRED,
                    expire_at=subscription.end_date,
                    traffic_limit_bytes=self._gb_to_bytes(subscription.traffic_limit_gb),
                    traffic_limit_strategy=get_traffic_reset_strategy(),
                    description=settings.format_remnawave_user_description(
                        full_name=user.full_name,
                        username=user.username,
                        telegram_id=user.telegram_id
                    ),
                    active_internal_squads=subscription.connected_squads,
                )

                if hwid_limit is not None:
                    update_kwargs['hwid_device_limit'] = hwid_limit

                updated_user = await api.update_user(**update_kwargs)
                
                if reset_traffic:
                    await self._reset_user_traffic(
                        api,
                        user.remnawave_uuid,
                        user.telegram_id,
                        reset_reason,
                    )

                subscription.subscription_url = updated_user.subscription_url
                subscription.subscription_crypto_link = updated_user.happ_crypto_link
                await db.commit()
                
                status_text = "active" if is_actually_active else "expired"
                logger.info(f"✅ Updated RemnaWave user {user.remnawave_uuid} with status {status_text}")
                strategy_name = settings.DEFAULT_TRAFFIC_RESET_STRATEGY
                logger.info(f"📊 Traffic reset strategy: {strategy_name}")
                return updated_user

        except RemnaWaveAPIError as e:
            logger.error(f"RemnaWave API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error updating RemnaWave user: {e}")
            return None

    async def _reset_user_traffic(
        self,
        api: RemnaWaveAPI,
        user_uuid: str,
        telegram_id: int,
        reset_reason: Optional[str] = None,
    ) -> None:
        if not user_uuid:
            return

        try:
            await api.reset_user_traffic(user_uuid)
            reason_text = f" ({reset_reason})" if reset_reason else ""
            logger.info(
                f"🔄 Reset RemnaWave traffic for user {telegram_id}{reason_text}"
            )
        except Exception as exc:
            logger.warning(
                f"⚠️ Failed to reset RemnaWave traffic for user {telegram_id}: {exc}"
            )

    async def disable_remnawave_user(self, user_uuid: str) -> bool:

        try:
            async with self.get_api_client() as api:
                await api.disable_user(user_uuid)
                logger.info(f"✅ Disabled RemnaWave user {user_uuid}")
                return True
                
        except Exception as e:
            logger.error(f"Error disabling RemnaWave user: {e}")
            return False
    
    async def revoke_subscription(
        self,
        db: AsyncSession,
        subscription: Subscription
    ) -> Optional[str]:
        
        try:
            user = await get_user_by_id(db, subscription.user_id)
            if not user or not user.remnawave_uuid:
                return None
            
            async with self.get_api_client() as api:
                updated_user = await api.revoke_user_subscription(user.remnawave_uuid)
                
                subscription.remnawave_short_uuid = updated_user.short_uuid
                subscription.subscription_url = updated_user.subscription_url
                subscription.subscription_crypto_link = updated_user.happ_crypto_link
                await db.commit()
                
                logger.info(f"✅ Updated subscription link for user {user.telegram_id}")
                return updated_user.subscription_url
                
        except Exception as e:
            logger.error(f"Error updating subscription link: {e}")
            return None
    
    async def get_subscription_info(self, short_uuid: str) -> Optional[dict]:
        
        try:
            async with self.get_api_client() as api:
                info = await api.get_subscription_info(short_uuid)
                return info
                
        except Exception as e:
            logger.error(f"Error getting subscription info: {e}")
            return None
    
    async def sync_subscription_usage(
        self,
        db: AsyncSession,
        subscription: Subscription
    ) -> bool:
        
        try:
            user = await get_user_by_id(db, subscription.user_id)
            if not user or not user.remnawave_uuid:
                return False
            
            async with self.get_api_client() as api:
                remnawave_user = await api.get_user_by_uuid(user.remnawave_uuid)
                if not remnawave_user:
                    return False
                
                used_gb = self._bytes_to_gb(remnawave_user.used_traffic_bytes)
                subscription.traffic_used_gb = used_gb
                
                await db.commit()
                
                logger.debug(f"Synchronized traffic for subscription {subscription.id}: {used_gb} GB")
                return True
                
        except Exception as e:
            logger.error(f"Error synchronizing traffic: {e}")
            return False
    
    async def calculate_subscription_price(
        self,
        period_days: int,
        traffic_gb: int,
        server_squad_ids: List[int],
        devices: int,
        db: AsyncSession,
        *,
        user: Optional[User] = None,
        promo_group: Optional[PromoGroup] = None,
    ) -> Tuple[int, List[int]]:
    
        from app.config import PERIOD_PRICES
        from app.database.crud.server_squad import get_server_squad_by_id
    
        if settings.MAX_DEVICES_LIMIT > 0 and devices > settings.MAX_DEVICES_LIMIT:
            raise ValueError(f"Maximum device limit exceeded: {settings.MAX_DEVICES_LIMIT}")
    
        base_price_original = PERIOD_PRICES.get(period_days, 0)
        period_discount_percent = _resolve_discount_percent(
            user,
            promo_group,
            "period",
            period_days=period_days,
        )
        base_discount_total = base_price_original * period_discount_percent // 100
        base_price = base_price_original - base_discount_total
        
        promo_group = promo_group or (user.get_primary_promo_group() if user else None)

        traffic_price = settings.get_traffic_price(traffic_gb)
        traffic_discount_percent = _resolve_discount_percent(
            user,
            promo_group,
            "traffic",
            period_days=period_days,
        )
        traffic_discount = traffic_price * traffic_discount_percent // 100
        discounted_traffic_price = traffic_price - traffic_discount

        server_prices = []
        total_servers_price = 0
        servers_discount_percent = _resolve_discount_percent(
            user,
            promo_group,
            "servers",
            period_days=period_days,
        )

        for server_id in server_squad_ids:
            server = await get_server_squad_by_id(db, server_id)
            if server and server.is_available and not server.is_full:
                server_price = server.price_kopeks
                server_discount = server_price * servers_discount_percent // 100
                discounted_server_price = server_price - server_discount
                server_prices.append(discounted_server_price)
                total_servers_price += discounted_server_price
                log_message = f"Server {server.display_name}: {server_price/100}₽"
                if server_discount > 0:
                    log_message += (
                        f" (discount {servers_discount_percent}%: -{server_discount/100}₽ → {discounted_server_price/100}₽)"
                    )
                logger.debug(log_message)
            else:
                server_prices.append(0)
                logger.warning(f"Server ID {server_id} unavailable")

        devices_price = max(0, devices - settings.DEFAULT_DEVICE_LIMIT) * settings.PRICE_PER_DEVICE
        devices_discount_percent = _resolve_discount_percent(
            user,
            promo_group,
            "devices",
            period_days=period_days,
        )
        devices_discount = devices_price * devices_discount_percent // 100
        discounted_devices_price = devices_price - devices_discount

        total_price = base_price + discounted_traffic_price + total_servers_price + discounted_devices_price

        logger.debug("New subscription price calculation:")
        base_log = f"   Period {period_days} days: {base_price_original/100}₽"
        if base_discount_total > 0:
            base_log += (
                f" → {base_price/100}₽"
                f" (discount {period_discount_percent}%: -{base_discount_total/100}₽)"
            )
        logger.debug(base_log)
        if discounted_traffic_price > 0:
            message = f"   Traffic {traffic_gb} GB: {traffic_price/100}₽"
            if traffic_discount > 0:
                message += (
                    f" (discount {traffic_discount_percent}%: -{traffic_discount/100}₽ → {discounted_traffic_price/100}₽)"
                )
            logger.debug(message)
        if total_servers_price > 0:
            message = f"   Servers ({len(server_squad_ids)}): {total_servers_price/100}₽"
            if servers_discount_percent > 0:
                message += (
                    f" (discount {servers_discount_percent}% applied to all servers)"
                )
            logger.debug(message)
        if discounted_devices_price > 0:
            message = f"   Devices ({devices}): {devices_price/100}₽"
            if devices_discount > 0:
                message += (
                    f" (discount {devices_discount_percent}%: -{devices_discount/100}₽ → {discounted_devices_price/100}₽)"
                )
            logger.debug(message)
        logger.debug(f"   TOTAL: {total_price/100}₽")

        return total_price, server_prices
    
    async def calculate_renewal_price(
        self,
        subscription: Subscription,
        period_days: int,
        db: AsyncSession,
        *,
        user: Optional[User] = None,
        promo_group: Optional[PromoGroup] = None,
    ) -> int:
        try:
            from app.config import PERIOD_PRICES

            base_price_original = PERIOD_PRICES.get(period_days, 0)

            if user is None:
                user = getattr(subscription, "user", None)
            promo_group = promo_group or (user.get_primary_promo_group() if user else None)

            servers_price, _ = await self.get_countries_price_by_uuids(
                subscription.connected_squads,
                db,
                promo_group_id=promo_group.id if promo_group else None,
            )

            servers_discount_percent = _resolve_discount_percent(
                user,
                promo_group,
                "servers",
                period_days=period_days,
            )
            servers_discount = servers_price * servers_discount_percent // 100
            discounted_servers_price = servers_price - servers_discount

            device_limit = subscription.device_limit
            if device_limit is None:
                if settings.is_devices_selection_enabled():
                    device_limit = settings.DEFAULT_DEVICE_LIMIT
                else:
                    forced_limit = settings.get_disabled_mode_device_limit()
                    if forced_limit is None:
                        device_limit = settings.DEFAULT_DEVICE_LIMIT
                    else:
                        device_limit = forced_limit

            devices_price = max(0, (device_limit or 0) - settings.DEFAULT_DEVICE_LIMIT) * settings.PRICE_PER_DEVICE
            devices_discount_percent = _resolve_discount_percent(
                user,
                promo_group,
                "devices",
                period_days=period_days,
            )
            devices_discount = devices_price * devices_discount_percent // 100
            discounted_devices_price = devices_price - devices_discount

            traffic_price = settings.get_traffic_price(subscription.traffic_limit_gb)
            traffic_discount_percent = _resolve_discount_percent(
                user,
                promo_group,
                "traffic",
                period_days=period_days,
            )
            traffic_discount = traffic_price * traffic_discount_percent // 100
            discounted_traffic_price = traffic_price - traffic_discount

            period_discount_percent = _resolve_discount_percent(
                user,
                promo_group,
                "period",
                period_days=period_days,
            )
            base_discount_total = base_price_original * period_discount_percent // 100
            base_price = base_price_original - base_discount_total

            total_price = (
                base_price
                + discounted_servers_price
                + discounted_devices_price
                + discounted_traffic_price
            )

            logger.debug(f"💰 Renewal price calculation for subscription {subscription.id} (at current prices):")
            base_log = f"   📅 Period {period_days} days: {base_price_original/100}₽"
            if base_discount_total > 0:
                base_log += (
                    f" → {base_price/100}₽"
                    f" (discount {period_discount_percent}%: -{base_discount_total/100}₽)"
                )
            logger.debug(base_log)
            if servers_price > 0:
                message = f"   🌍 Servers ({len(subscription.connected_squads)}) at current prices: {discounted_servers_price/100}₽"
                if servers_discount > 0:
                    message += (
                        f" (discount {servers_discount_percent}%: -{servers_discount/100}₽ from {servers_price/100}₽)"
                    )
                logger.debug(message)
            if devices_price > 0:
                message = f"   📱 Devices ({device_limit}): {discounted_devices_price/100}₽"
                if devices_discount > 0:
                    message += (
                        f" (discount {devices_discount_percent}%: -{devices_discount/100}₽ from {devices_price/100}₽)"
                    )
                logger.debug(message)
            if traffic_price > 0:
                message = f"   📊 Traffic ({subscription.traffic_limit_gb} GB): {discounted_traffic_price/100}₽"
                if traffic_discount > 0:
                    message += (
                        f" (discount {traffic_discount_percent}%: -{traffic_discount/100}₽ from {traffic_price/100}₽)"
                    )
                logger.debug(message)
            logger.debug(f"   💎 TOTAL: {total_price/100}₽")

            return total_price
            
        except Exception as e:
            logger.error(f"Error calculating renewal price: {e}")
            from app.config import PERIOD_PRICES
            return PERIOD_PRICES.get(period_days, 0)

    async def validate_and_clean_subscription(
        self,
        db: AsyncSession,
        subscription: Subscription,
        user: User
    ) -> bool:
        try:
            needs_cleanup = False
            
            if user.remnawave_uuid:
                try:
                    async with self.get_api_client() as api:
                        remnawave_user = await api.get_user_by_uuid(user.remnawave_uuid)
                        
                        if not remnawave_user:
                            logger.warning(f"⚠️ User {user.telegram_id} has UUID {user.remnawave_uuid}, but not found in panel")
                            needs_cleanup = True
                        else:
                            if remnawave_user.telegram_id != user.telegram_id:
                                logger.warning(f"⚠️ Telegram ID mismatch for user {user.telegram_id}")
                                needs_cleanup = True
                except Exception as api_error:
                    logger.error(f"❌ Error checking user in panel: {api_error}")
                    needs_cleanup = True
            
            if subscription.remnawave_short_uuid and not user.remnawave_uuid:
                logger.warning(f"⚠️ Subscription has short_uuid, but user has no remnawave_uuid")
                needs_cleanup = True
                
            if needs_cleanup:
                logger.info(f"🧹 Cleaning up stale subscription data for user {user.telegram_id}")
                
                subscription.remnawave_short_uuid = None
                subscription.subscription_url = ""
                subscription.subscription_crypto_link = ""
                subscription.connected_squads = []
                
                user.remnawave_uuid = None
                
                await db.commit()
                logger.info(f"✅ Stale data cleaned up for user {user.telegram_id}")
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Subscription validation error for user {user.telegram_id}: {e}")
            await db.rollback()
            return False
    
    async def get_countries_price_by_uuids(
        self,
        country_uuids: List[str],
        db: AsyncSession,
        *,
        promo_group_id: Optional[int] = None,
    ) -> Tuple[int, List[int]]:
        try:
            from app.database.crud.server_squad import get_server_squad_by_uuid
            
            total_price = 0
            prices_list = []
            
            for country_uuid in country_uuids:
                server = await get_server_squad_by_uuid(db, country_uuid)
                is_allowed = True
                if promo_group_id is not None and server:
                    allowed_ids = {pg.id for pg in server.allowed_promo_groups}
                    is_allowed = promo_group_id in allowed_ids

                if server and server.is_available and not server.is_full and is_allowed:
                    price = server.price_kopeks
                    total_price += price
                    prices_list.append(price)
                    logger.debug(f"🏷️ Country {server.display_name}: {price/100}₽")
                else:
                    default_price = 0  
                    total_price += default_price
                    prices_list.append(default_price)
                    logger.warning(f"⚠️ Server {country_uuid} unavailable, using base price: {default_price/100}₽")
            
            logger.info(f"💰 Total countries price: {total_price/100}₽")
            return total_price, prices_list
            
        except Exception as e:
            logger.error(f"Error getting country prices: {e}")
            default_prices = [0] * len(country_uuids)
            return sum(default_prices), default_prices
    
    async def _get_countries_price(self, country_uuids: List[str], db: AsyncSession) -> int:
        try:
            total_price, _ = await self.get_countries_price_by_uuids(country_uuids, db)
            return total_price
        except Exception as e:
            logger.error(f"Error getting country prices: {e}")
            return len(country_uuids) * 1000

    async def calculate_subscription_price_with_months(
        self,
        period_days: int,
        traffic_gb: int,
        server_squad_ids: List[int],
        devices: int,
        db: AsyncSession,
        *,
        user: Optional[User] = None,
        promo_group: Optional[PromoGroup] = None,
    ) -> Tuple[int, List[int]]:
    
        from app.config import PERIOD_PRICES
        from app.database.crud.server_squad import get_server_squad_by_id
        
        if settings.MAX_DEVICES_LIMIT > 0 and devices > settings.MAX_DEVICES_LIMIT:
            raise ValueError(f"Maximum device limit exceeded: {settings.MAX_DEVICES_LIMIT}")
        
        months_in_period = calculate_months_from_days(period_days)
        
        base_price_original = PERIOD_PRICES.get(period_days, 0)
        period_discount_percent = _resolve_discount_percent(
            user,
            promo_group,
            "period",
            period_days=period_days,
        )
        base_discount_total = base_price_original * period_discount_percent // 100
        base_price = base_price_original - base_discount_total
        
        promo_group = promo_group or (user.get_primary_promo_group() if user else None)

        traffic_price_per_month = settings.get_traffic_price(traffic_gb)
        traffic_discount_percent = _resolve_discount_percent(
            user,
            promo_group,
            "traffic",
            period_days=period_days,
        )
        traffic_discount_per_month = traffic_price_per_month * traffic_discount_percent // 100
        discounted_traffic_per_month = traffic_price_per_month - traffic_discount_per_month
        total_traffic_price = discounted_traffic_per_month * months_in_period

        server_prices = []
        total_servers_price = 0
        servers_discount_percent = _resolve_discount_percent(
            user,
            promo_group,
            "servers",
            period_days=period_days,
        )

        for server_id in server_squad_ids:
            server = await get_server_squad_by_id(db, server_id)
            if server and server.is_available and not server.is_full:
                server_price_per_month = server.price_kopeks
                server_discount_per_month = server_price_per_month * servers_discount_percent // 100
                discounted_server_per_month = server_price_per_month - server_discount_per_month
                server_price_total = discounted_server_per_month * months_in_period
                server_prices.append(server_price_total)
                total_servers_price += server_price_total
                log_message = (
                    f"Server {server.display_name}: {server_price_per_month/100}₽/mo x {months_in_period} mo = {server_price_total/100}₽"
                )
                if server_discount_per_month > 0:
                    log_message += (
                        f" (discount {servers_discount_percent}%: -{server_discount_per_month * months_in_period/100}₽)"
                    )
                logger.debug(log_message)
            else:
                server_prices.append(0)
                logger.warning(f"Server ID {server_id} unavailable")

        additional_devices = max(0, devices - settings.DEFAULT_DEVICE_LIMIT)
        devices_price_per_month = additional_devices * settings.PRICE_PER_DEVICE
        devices_discount_percent = _resolve_discount_percent(
            user,
            promo_group,
            "devices",
            period_days=period_days,
        )
        devices_discount_per_month = devices_price_per_month * devices_discount_percent // 100
        discounted_devices_per_month = devices_price_per_month - devices_discount_per_month
        total_devices_price = discounted_devices_per_month * months_in_period

        total_price = base_price + total_traffic_price + total_servers_price + total_devices_price

        logger.debug(f"New subscription price calculation for {period_days} days ({months_in_period} mo):")
        base_log = f"   Period {period_days} days: {base_price_original/100}₽"
        if base_discount_total > 0:
            base_log += (
                f" → {base_price/100}₽"
                f" (discount {period_discount_percent}%: -{base_discount_total/100}₽)"
            )
        logger.debug(base_log)
        if total_traffic_price > 0:
            message = (
                f"   Traffic {traffic_gb} GB: {traffic_price_per_month/100}₽/mo x {months_in_period} = {total_traffic_price/100}₽"
            )
            if traffic_discount_per_month > 0:
                message += (
                    f" (discount {traffic_discount_percent}%: -{traffic_discount_per_month * months_in_period/100}₽)"
                )
            logger.debug(message)
        if total_servers_price > 0:
            message = f"   Servers ({len(server_squad_ids)}): {total_servers_price/100}₽"
            if servers_discount_percent > 0:
                message += (
                    f" (discount {servers_discount_percent}% applied to all servers)"
                )
            logger.debug(message)
        if total_devices_price > 0:
            message = (
                f"   Devices ({additional_devices}): {devices_price_per_month/100}₽/mo x {months_in_period} = {total_devices_price/100}₽"
            )
            if devices_discount_per_month > 0:
                message += (
                    f" (discount {devices_discount_percent}%: -{devices_discount_per_month * months_in_period/100}₽)"
                )
            logger.debug(message)
        logger.debug(f"   TOTAL: {total_price/100}₽")

        return total_price, server_prices
    
    async def calculate_renewal_price_with_months(
        self,
        subscription: Subscription,
        period_days: int,
        db: AsyncSession,
        *,
        user: Optional[User] = None,
        promo_group: Optional[PromoGroup] = None,
    ) -> int:
        try:
            from app.config import PERIOD_PRICES

            months_in_period = calculate_months_from_days(period_days)

            base_price_original = PERIOD_PRICES.get(period_days, 0)

            if user is None:
                user = getattr(subscription, "user", None)
            promo_group = promo_group or (user.get_primary_promo_group() if user else None)

            servers_price_per_month, _ = await self.get_countries_price_by_uuids(
                subscription.connected_squads,
                db,
                promo_group_id=promo_group.id if promo_group else None,
            )
            servers_discount_percent = _resolve_discount_percent(
                user,
                promo_group,
                "servers",
                period_days=period_days,
            )
            servers_discount_per_month = servers_price_per_month * servers_discount_percent // 100
            discounted_servers_per_month = servers_price_per_month - servers_discount_per_month
            total_servers_price = discounted_servers_per_month * months_in_period

            device_limit = subscription.device_limit
            if device_limit is None:
                if settings.is_devices_selection_enabled():
                    device_limit = settings.DEFAULT_DEVICE_LIMIT
                else:
                    forced_limit = settings.get_disabled_mode_device_limit()
                    if forced_limit is None:
                        device_limit = settings.DEFAULT_DEVICE_LIMIT
                    else:
                        device_limit = forced_limit

            additional_devices = max(0, (device_limit or 0) - settings.DEFAULT_DEVICE_LIMIT)
            devices_price_per_month = additional_devices * settings.PRICE_PER_DEVICE
            devices_discount_percent = _resolve_discount_percent(
                user,
                promo_group,
                "devices",
                period_days=period_days,
            )
            devices_discount_per_month = devices_price_per_month * devices_discount_percent // 100
            discounted_devices_per_month = devices_price_per_month - devices_discount_per_month
            total_devices_price = discounted_devices_per_month * months_in_period

            traffic_price_per_month = settings.get_traffic_price(subscription.traffic_limit_gb)
            traffic_discount_percent = _resolve_discount_percent(
                user,
                promo_group,
                "traffic",
                period_days=period_days,
            )
            traffic_discount_per_month = traffic_price_per_month * traffic_discount_percent // 100
            discounted_traffic_per_month = traffic_price_per_month - traffic_discount_per_month
            total_traffic_price = discounted_traffic_per_month * months_in_period

            period_discount_percent = _resolve_discount_percent(
                user,
                promo_group,
                "period",
                period_days=period_days,
            )
            base_discount_total = base_price_original * period_discount_percent // 100
            base_price = base_price_original - base_discount_total

            total_price = base_price + total_servers_price + total_devices_price + total_traffic_price

            logger.debug(f"💰 Renewal price calculation for subscription {subscription.id} for {period_days} days ({months_in_period} mo):")
            base_log = f"   📅 Period {period_days} days: {base_price_original/100}₽"
            if base_discount_total > 0:
                base_log += (
                    f" → {base_price/100}₽"
                    f" (discount {period_discount_percent}%: -{base_discount_total/100}₽)"
                )
            logger.debug(base_log)
            if total_servers_price > 0:
                message = (
                    f"   🌍 Servers: {servers_price_per_month/100}₽/mo x {months_in_period} = {total_servers_price/100}₽"
                )
                if servers_discount_per_month > 0:
                    message += (
                        f" (discount {servers_discount_percent}%: -{servers_discount_per_month * months_in_period/100}₽)"
                    )
                logger.debug(message)
            if total_devices_price > 0:
                message = (
                    f"   📱 Devices: {devices_price_per_month/100}₽/mo x {months_in_period} = {total_devices_price/100}₽"
                )
                if devices_discount_per_month > 0:
                    message += (
                        f" (discount {devices_discount_percent}%: -{devices_discount_per_month * months_in_period/100}₽)"
                    )
                logger.debug(message)
            if total_traffic_price > 0:
                message = (
                    f"   📊 Traffic: {traffic_price_per_month/100}₽/mo x {months_in_period} = {total_traffic_price/100}₽"
                )
                if traffic_discount_per_month > 0:
                    message += (
                        f" (discount {traffic_discount_percent}%: -{traffic_discount_per_month * months_in_period/100}₽)"
                    )
                logger.debug(message)
            logger.debug(f"   💎 TOTAL: {total_price/100}₽")

            return total_price
            
        except Exception as e:
            logger.error(f"Error calculating renewal price: {e}")
            from app.config import PERIOD_PRICES
            return PERIOD_PRICES.get(period_days, 0)
    
    async def calculate_addon_price_with_remaining_period(
        self,
        subscription: Subscription,
        additional_traffic_gb: int = 0,
        additional_devices: int = 0,
        additional_server_ids: List[int] = None,
        db: AsyncSession = None
    ) -> int:
        
        if additional_server_ids is None:
            additional_server_ids = []

        months_to_pay = get_remaining_months(subscription.end_date)
        period_hint_days = months_to_pay * 30 if months_to_pay > 0 else None

        user = getattr(subscription, "user", None)
        promo_group = user.promo_group if user else None

        total_price = 0

        if additional_traffic_gb > 0:
            traffic_price_per_month = settings.get_traffic_price(additional_traffic_gb)
            traffic_discount_percent = _resolve_addon_discount_percent(
                user,
                promo_group,
                "traffic",
                period_days=period_hint_days,
            )
            traffic_discount_per_month = traffic_price_per_month * traffic_discount_percent // 100
            discounted_traffic_per_month = traffic_price_per_month - traffic_discount_per_month
            traffic_total_price = discounted_traffic_per_month * months_to_pay
            total_price += traffic_total_price
            message = (
                f"Traffic +{additional_traffic_gb}GB: {traffic_price_per_month/100}₽/mo x {months_to_pay}"
                f" = {traffic_total_price/100}₽"
            )
            if traffic_discount_per_month > 0:
                message += (
                    f" (discount {traffic_discount_percent}%:"
                    f" -{traffic_discount_per_month * months_to_pay/100}₽)"
                )
            logger.info(message)

        if additional_devices > 0:
            devices_price_per_month = additional_devices * settings.PRICE_PER_DEVICE
            devices_discount_percent = _resolve_addon_discount_percent(
                user,
                promo_group,
                "devices",
                period_days=period_hint_days,
            )
            devices_discount_per_month = devices_price_per_month * devices_discount_percent // 100
            discounted_devices_per_month = devices_price_per_month - devices_discount_per_month
            devices_total_price = discounted_devices_per_month * months_to_pay
            total_price += devices_total_price
            message = (
                f"Devices +{additional_devices}: {devices_price_per_month/100}₽/mo x {months_to_pay}"
                f" = {devices_total_price/100}₽"
            )
            if devices_discount_per_month > 0:
                message += (
                    f" (discount {devices_discount_percent}%:"
                    f" -{devices_discount_per_month * months_to_pay/100}₽)"
                )
            logger.info(message)

        if additional_server_ids and db:
            for server_id in additional_server_ids:
                from app.database.crud.server_squad import get_server_squad_by_id
                server = await get_server_squad_by_id(db, server_id)
                if server and server.is_available:
                    server_price_per_month = server.price_kopeks
                    servers_discount_percent = _resolve_addon_discount_percent(
                        user,
                        promo_group,
                        "servers",
                        period_days=period_hint_days,
                    )
                    server_discount_per_month = (
                        server_price_per_month * servers_discount_percent // 100
                    )
                    discounted_server_per_month = (
                        server_price_per_month - server_discount_per_month
                    )
                    server_total_price = discounted_server_per_month * months_to_pay
                    total_price += server_total_price
                    message = (
                        f"Server {server.display_name}: {server_price_per_month/100}₽/mo x {months_to_pay}"
                        f" = {server_total_price/100}₽"
                    )
                    if server_discount_per_month > 0:
                        message += (
                            f" (discount {servers_discount_percent}%:"
                            f" -{server_discount_per_month * months_to_pay/100}₽)"
                        )
                    logger.info(message)

        logger.info(f"Total addon payment for {months_to_pay} mo: {total_price/100}₽")
        return total_price
    
    def _gb_to_bytes(self, gb: int) -> int:
        if gb == 0: 
            return 0
        return gb * 1024 * 1024 * 1024
    
    def _bytes_to_gb(self, bytes_value: int) -> float:
        if bytes_value == 0:
            return 0.0
        return bytes_value / (1024 * 1024 * 1024)
