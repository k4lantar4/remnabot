import asyncio
import logging
import re
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from zoneinfo import ZoneInfo

from app.config import settings
from app.external.remnawave_api import (
    RemnaWaveAPI, RemnaWaveUser, RemnaWaveInternalSquad,
    RemnaWaveNode, UserStatus, TrafficLimitStrategy, RemnaWaveAPIError
)
from sqlalchemy import and_, cast, delete, func, select, update, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.crud.user import (
    create_user_no_commit,
    get_users_list,
    get_user_by_telegram_id,
    update_user,
)
from app.database.crud.subscription import (
    get_subscription_by_user_id,
    update_subscription_usage,
    decrement_subscription_server_counts,
)
from app.database.crud.server_squad import get_server_squad_by_uuid
from app.database.models import (
    User,
    Subscription,
    SubscriptionServer,
    Transaction,
    ReferralEarning,
    PromoCodeUse,
    SubscriptionStatus,
    ServerSquad,
)
from app.utils.subscription_utils import (
    resolve_hwid_device_limit_for_payload,
)
from app.utils.timezone import get_local_timezone

logger = logging.getLogger(__name__)


_UUID_MAP_MISSING = object()


class _UUIDMapMutation:
    """Tracks in-memory UUID map/user changes so they can be rolled back."""

    __slots__ = ("uuid_map", "_map_original", "_user_original")

    def __init__(self, uuid_map: Dict[str, "User"]):
        self.uuid_map = uuid_map
        self._map_original: Dict[str, Any] = {}
        self._user_original: Dict["User", Tuple[Optional[str], Optional[datetime]]] = {}

    def _capture_user_state(self, user: Optional["User"]) -> None:
        if not user or user in self._user_original:
            return
        self._user_original[user] = (
            getattr(user, "remnawave_uuid", None),
            getattr(user, "updated_at", None),
        )

    def _capture_map_entry(self, key: Optional[str]) -> None:
        if key is None or key in self._map_original:
            return
        self._map_original[key] = self.uuid_map.get(key, _UUID_MAP_MISSING)

    def set_user_uuid(self, user: Optional["User"], value: Optional[str]) -> None:
        if not user:
            return
        self._capture_user_state(user)
        user.remnawave_uuid = value

    def set_user_updated_at(self, user: Optional["User"], value: datetime) -> None:
        if not user:
            return
        self._capture_user_state(user)
        user.updated_at = value

    def remove_map_entry(self, key: Optional[str]) -> None:
        if key is None:
            return
        self._capture_map_entry(key)
        self.uuid_map.pop(key, None)

    def set_map_entry(self, key: Optional[str], value: Optional["User"]) -> None:
        if key is None:
            return
        self._capture_map_entry(key)
        if value is None:
            self.uuid_map.pop(key, None)
        else:
            self.uuid_map[key] = value

    def has_changes(self) -> bool:
        return bool(self._map_original or self._user_original)

    def rollback(self) -> None:
        for user, (uuid_value, updated_at) in self._user_original.items():
            user.remnawave_uuid = uuid_value
            user.updated_at = updated_at

        for key, original in self._map_original.items():
            if original is _UUID_MAP_MISSING:
                self.uuid_map.pop(key, None)
            else:
                self.uuid_map[key] = original


class RemnaWaveConfigurationError(Exception):
    """Raised when RemnaWave API configuration is missing."""


class RemnaWaveService:

    def __init__(self):
        auth_params = settings.get_remnawave_auth_params()
        base_url = (auth_params.get("base_url") or "").strip()
        api_key = (auth_params.get("api_key") or "").strip()

        self._config_error: Optional[str] = None

        self._panel_timezone = get_local_timezone()
        self._utc_timezone = ZoneInfo("UTC")

        if not base_url:
            self._config_error = "REMNAWAVE_API_URL is not configured"
        elif not api_key:
            self._config_error = "REMNAWAVE_API_KEY is not configured"

        self.api: Optional[RemnaWaveAPI]
        if self._config_error:
            self.api = None
        else:
            self.api = RemnaWaveAPI(
                base_url=base_url,
                api_key=api_key,
                secret_key=auth_params.get("secret_key"),
                username=auth_params.get("username"),
                password=auth_params.get("password")
            )

    @property
    def is_configured(self) -> bool:
        return self._config_error is None

    @property
    def configuration_error(self) -> Optional[str]:
        return self._config_error

    def _ensure_configured(self) -> None:
        if not self.is_configured or self.api is None:
            raise RemnaWaveConfigurationError(
                self._config_error or "RemnaWave API is not configured"
            )

    def _ensure_user_remnawave_uuid(
        self,
        user: "User",
        panel_uuid: Optional[str],
        uuid_map: Dict[str, "User"],
    ) -> Tuple[bool, Optional[_UUIDMapMutation]]:
        """Updates user UUID if it changed in the panel."""

        if not panel_uuid:
            return False, None

        current_uuid = getattr(user, "remnawave_uuid", None)
        if current_uuid == panel_uuid:
            return False, None

        mutation = _UUIDMapMutation(uuid_map)

        conflicting_user = uuid_map.get(panel_uuid)
        if conflicting_user and conflicting_user is not user:
            logger.warning(
                "♻️ UUID conflict detected %s between users %s and %s. Resetting old record.",
                panel_uuid,
                getattr(conflicting_user, "telegram_id", "?"),
                getattr(user, "telegram_id", "?"),
            )
            mutation.set_user_uuid(conflicting_user, None)
            mutation.set_user_updated_at(conflicting_user, datetime.utcnow())
            mutation.remove_map_entry(panel_uuid)

        if current_uuid:
            mutation.remove_map_entry(current_uuid)

        mutation.set_user_uuid(user, panel_uuid)
        mutation.set_user_updated_at(user, datetime.utcnow())
        mutation.set_map_entry(panel_uuid, user)

        logger.info(
            "🔁 Updated RemnaWave UUID for user %s: %s → %s",
            getattr(user, "telegram_id", "?"),
            current_uuid,
            panel_uuid,
        )

        if mutation.has_changes():
            return True, mutation

        return True, None

    @asynccontextmanager
    async def get_api_client(self):
        self._ensure_configured()
        assert self.api is not None
        async with self.api as api:
            yield api

    def _now_utc(self) -> datetime:
        """Returns current time in UTC without timezone binding."""
        return datetime.now(self._utc_timezone).replace(tzinfo=None)

    def _parse_remnawave_date(self, date_str: str) -> datetime:
        if not date_str:
            return self._now_utc() + timedelta(days=30)

        try:

            cleaned_date = date_str.strip()

            if cleaned_date.endswith('Z'):
                cleaned_date = cleaned_date[:-1] + '+00:00'

            if '+00:00+00:00' in cleaned_date:
                cleaned_date = cleaned_date.replace('+00:00+00:00', '+00:00')

            cleaned_date = re.sub(r'(\+\d{2}:\d{2})\+\d{2}:\d{2}$', r'\1', cleaned_date)

            parsed_date = datetime.fromisoformat(cleaned_date)

            if parsed_date.tzinfo is not None:
                localized = parsed_date.astimezone(self._panel_timezone)
            else:
                localized = parsed_date.replace(tzinfo=self._panel_timezone)

            utc_normalized = localized.astimezone(self._utc_timezone).replace(tzinfo=None)

            logger.debug(
                f"Successfully parsed date: {date_str} -> {utc_normalized} (normalized to UTC)"
            )
            return utc_normalized

        except Exception as e:
            logger.warning(
                f"⚠️ Failed to parse date '{date_str}': {e}. Using default date."
            )
            return self._now_utc() + timedelta(days=30)

    def _safe_expire_at_for_panel(self, expire_at: Optional[datetime]) -> datetime:
        """Ensures expiration date is not in the past for the panel."""

        now = self._now_utc()
        minimum_expire = now + timedelta(minutes=1)

        if not expire_at:
            return minimum_expire

        normalized_expire = expire_at
        if normalized_expire.tzinfo is not None:
            normalized_expire = normalized_expire.replace(tzinfo=None)

        if normalized_expire < minimum_expire:
            logger.debug(
                "⚙️ Correcting expiration date (%s) to minimum allowed (%s) for panel",
                normalized_expire,
                minimum_expire,
            )
            return minimum_expire

        return normalized_expire

    def _safe_panel_expire_date(self, panel_user: Dict[str, Any]) -> datetime:
        """Parses panel user subscription expiration date for comparison."""

        expire_at_value = panel_user.get('expireAt')

        if expire_at_value is None:
            return datetime.min.replace(tzinfo=None)

        expire_at_str = str(expire_at_value).strip()
        if not expire_at_str:
            return datetime.min.replace(tzinfo=None)

        return self._parse_remnawave_date(expire_at_str)

    def _is_preferred_panel_user(
        self,
        *,
        candidate: Dict[str, Any],
        current: Dict[str, Any],
    ) -> bool:
        """Determines if new record is preferred for Telegram ID."""

        candidate_expire = self._safe_panel_expire_date(candidate)
        current_expire = self._safe_panel_expire_date(current)

        if candidate_expire > current_expire:
            return True
        if candidate_expire < current_expire:
            return False

        candidate_status = (candidate.get('status') or '').upper()
        current_status = (current.get('status') or '').upper()

        active_statuses = {'ACTIVE', 'TRIAL'}
        if candidate_status in active_statuses and current_status not in active_statuses:
            return True

        return False

    def _deduplicate_panel_users_by_telegram_id(
        self,
        panel_users: List[Dict[str, Any]],
    ) -> Dict[Any, Dict[str, Any]]:
        """Returns unique panel users by Telegram ID."""

        unique_users: Dict[Any, Dict[str, Any]] = {}

        for panel_user in panel_users:
            telegram_id = panel_user.get('telegramId')
            if telegram_id is None:
                continue

            existing_user = unique_users.get(telegram_id)
            if existing_user is None or self._is_preferred_panel_user(
                candidate=panel_user,
                current=existing_user,
            ):
                unique_users[telegram_id] = panel_user

        return unique_users

    def _extract_user_data_from_description(self, description: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extracts first name, last name and username from user description in Remnawave panel.
        
        Args:
            description: User description from panel
            
        Returns:
            Tuple[first_name, last_name, username] - extracted data
        """
        logger.debug(f"📥 Parsing user description: '{description}'")
        
        if not description:
            logger.debug("❌ Empty user description")
            return None, None, None
            
        # Look for strings in format "Bot user: ..."
        import re
        
        # Pattern to extract data from "Bot user: Name @username" or "Bot user: Name"
        # Also support just "Name @username" without prefix
        bot_user_patterns = [
            r"Bot user:\s*(.+)",  # With prefix
            r"^([\w\s]+(?:@[\w_]+)?)$",  # Without prefix
        ]
        
        user_info = None
        for pattern in bot_user_patterns:
            match = re.search(pattern, description)
            if match:
                user_info = match.group(1).strip()
                logger.debug(f"🔍 Found user information: '{user_info}'")
                break
        
        if not user_info:
            logger.debug("❌ Failed to find user information in description")
            return None, None, None
            
        # Pattern to extract username (@username at the end)
        username_pattern = r"\s+(@[\w_]+)$"
        username_match = re.search(username_pattern, user_info)
        
        if username_match:
            username_with_at = username_match.group(1)
            username = username_with_at[1:] if username_with_at.startswith('@') else username_with_at  # Remove @ symbol
            # Remove username from main information
            name_part = user_info[:username_match.start()].strip()
            logger.debug(f"📱 Found username: '{username_with_at}' (processed: '{username}'), remainder: '{name_part}'")
        else:
            username = None
            name_part = user_info
            logger.debug(f"📱 Username not found, name: '{name_part}'")
            
        # Split first and last name
        if name_part and not name_part.startswith("@"):
            # If there's a name (doesn't start with @), use it
            name_parts = name_part.split()
            logger.debug(f"🔤 Name parts: {name_parts}")
            
            if len(name_parts) >= 2:
                # First word - first name, rest - last name
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else None
                logger.debug(f"👤 First name: '{first_name}', Last name: '{last_name}'")
            elif len(name_parts) == 1 and not name_parts[0].startswith("@"):
                # Only first name
                first_name = name_parts[0]
                last_name = None
                logger.debug(f"👤 First name only: '{first_name}'")
            else:
                first_name = None
                last_name = None
                logger.debug("👤 Name not determined")
        else:
            first_name = None
            last_name = None
            logger.debug("👤 Name not determined (starts with @)")
            
        logger.debug(f"✅ Parse result: first_name='{first_name}', last_name='{last_name}', username='{username}'")
        return first_name, last_name, username

    async def _get_or_create_bot_user_from_panel(
        self,
        db: AsyncSession,
        panel_user: Dict[str, Any],
    ) -> Tuple[Optional[User], bool]:
        """Returns bot user, creating it if necessary.

        On telegram_id uniqueness conflict, reloads user
        from database and reports that record was not created anew.
        """

        telegram_id = panel_user.get("telegramId")
        if telegram_id is None:
            return None, False

        # Extract actual user name from description
        description = panel_user.get("description") or ""
        first_name_from_desc, last_name_from_desc, username_from_desc = self._extract_user_data_from_description(description)
        
        # Use extracted name or default value
        fallback_first_name = f"User {telegram_id}"
        full_first_name = fallback_first_name
        full_last_name = None

        if first_name_from_desc and last_name_from_desc:
            full_first_name = first_name_from_desc
            full_last_name = last_name_from_desc
        elif first_name_from_desc:
            full_first_name = first_name_from_desc
            full_last_name = last_name_from_desc

        username = username_from_desc or panel_user.get("username")

        try:
            create_kwargs = dict(
                db=db,
                telegram_id=telegram_id,
                username=username,
                first_name=full_first_name,
                last_name=full_last_name,
                language="ru",
            )

            db_user = await create_user_no_commit(**create_kwargs)
            return db_user, True
        except IntegrityError as create_error:
            logger.info(
                "♻️ User with telegram_id %s already exists. Using existing record.",
                telegram_id,
            )

            try:
                await db.rollback()
            except Exception:
                # create_user_no_commit already performs rollback if needed
                pass

            try:
                existing_user = await get_user_by_telegram_id(db, telegram_id)
                if existing_user is None:
                    logger.error("❌ Failed to find existing user with telegram_id %s", telegram_id)
                    return None, False

                logger.debug(
                    "Using existing user %s after uniqueness conflict: %s",
                    telegram_id,
                    create_error,
                )
                return existing_user, False
            except Exception as load_error:
                logger.error("❌ Error loading existing user %s: %s", telegram_id, load_error)
                return None, False
        except Exception as general_error:
            logger.error("❌ General error creating/loading user %s: %s", telegram_id, general_error)
            try:
                await db.rollback()
            except:
                pass
            return None, False
    
    async def get_system_statistics(self) -> Dict[str, Any]:
            try:
                async with self.get_api_client() as api:
                    logger.info("Getting RemnaWave system statistics...")
                
                    try:
                        system_stats = await api.get_system_stats()
                        logger.info(f"System statistics received")
                    except Exception as e:
                        logger.error(f"Error getting system statistics: {e}")
                        system_stats = {}
                 
                    try:
                        bandwidth_stats = await api.get_bandwidth_stats()
                        logger.info(f"Traffic statistics received")
                    except Exception as e:
                        logger.error(f"Error getting traffic statistics: {e}")
                        bandwidth_stats = {}
                
                    try:
                        realtime_usage = await api.get_nodes_realtime_usage()
                        logger.info(f"Realtime statistics received")
                    except Exception as e:
                        logger.error(f"Error getting realtime statistics: {e}")
                        realtime_usage = []
                
                    try:
                        nodes_stats = await api.get_nodes_statistics()
                    except Exception as e:
                        logger.error(f"Error getting node statistics: {e}")
                        nodes_stats = {}
                
                
                    total_download = sum(node.get('downloadBytes', 0) for node in realtime_usage)
                    total_upload = sum(node.get('uploadBytes', 0) for node in realtime_usage)
                    total_realtime_traffic = total_download + total_upload
                
                    total_user_traffic = int(system_stats.get('users', {}).get('totalTrafficBytes', '0'))
                
                    nodes_weekly_data = []
                    if nodes_stats.get('lastSevenDays'):
                        nodes_by_name = {}
                        for day_data in nodes_stats['lastSevenDays']:
                            node_name = day_data['nodeName']
                            if node_name not in nodes_by_name:
                                nodes_by_name[node_name] = {
                                    'name': node_name,
                                    'total_bytes': 0,
                                    'days_data': []
                                }
                        
                            daily_bytes = int(day_data['totalBytes'])
                            nodes_by_name[node_name]['total_bytes'] += daily_bytes
                            nodes_by_name[node_name]['days_data'].append({
                                'date': day_data['date'],
                                'bytes': daily_bytes
                            })
                    
                        nodes_weekly_data = list(nodes_by_name.values())
                        nodes_weekly_data.sort(key=lambda x: x['total_bytes'], reverse=True)
                
                    uptime_seconds = 0
                    uptime_value = system_stats.get('uptime')
                    try:
                        uptime_seconds = int(float(uptime_value)) if uptime_value is not None else 0
                    except (TypeError, ValueError):
                        logger.warning(f"Failed to convert uptime '{uptime_value}' to number, using 0")

                    result = {
                        "system": {
                            "users_online": system_stats.get('onlineStats', {}).get('onlineNow', 0),
                            "total_users": system_stats.get('users', {}).get('totalUsers', 0),
                            "active_connections": system_stats.get('onlineStats', {}).get('onlineNow', 0),
                            "nodes_online": system_stats.get('nodes', {}).get('totalOnline', 0),
                            "users_last_day": system_stats.get('onlineStats', {}).get('lastDay', 0),
                            "users_last_week": system_stats.get('onlineStats', {}).get('lastWeek', 0),
                            "users_never_online": system_stats.get('onlineStats', {}).get('neverOnline', 0),
                            "total_user_traffic": total_user_traffic
                        },
                        "users_by_status": system_stats.get('users', {}).get('statusCounts', {}),
                        "server_info": {
                            "cpu_cores": system_stats.get('cpu', {}).get('cores', 0),
                            "cpu_physical_cores": system_stats.get('cpu', {}).get('physicalCores', 0),
                            "memory_total": system_stats.get('memory', {}).get('total', 0),
                            "memory_used": system_stats.get('memory', {}).get('used', 0),
                            "memory_free": system_stats.get('memory', {}).get('free', 0),
                            "memory_available": system_stats.get('memory', {}).get('available', 0),
                            "uptime_seconds": uptime_seconds
                        },
                        "bandwidth": {
                            "realtime_download": total_download,
                            "realtime_upload": total_upload,
                            "realtime_total": total_realtime_traffic
                        },
                        "traffic_periods": {
                            "last_2_days": {
                                "current": self._parse_bandwidth_string(
                                    bandwidth_stats.get('bandwidthLastTwoDays', {}).get('current', '0 B')
                                ),
                                "previous": self._parse_bandwidth_string(
                                    bandwidth_stats.get('bandwidthLastTwoDays', {}).get('previous', '0 B')
                                ),
                                "difference": bandwidth_stats.get('bandwidthLastTwoDays', {}).get('difference', '0 B')
                            },
                            "last_7_days": {
                                "current": self._parse_bandwidth_string(
                                    bandwidth_stats.get('bandwidthLastSevenDays', {}).get('current', '0 B')
                                ),
                                "previous": self._parse_bandwidth_string(
                                    bandwidth_stats.get('bandwidthLastSevenDays', {}).get('previous', '0 B')
                                ),
                                "difference": bandwidth_stats.get('bandwidthLastSevenDays', {}).get('difference', '0 B')
                            },
                            "last_30_days": {
                                "current": self._parse_bandwidth_string(
                                    bandwidth_stats.get('bandwidthLast30Days', {}).get('current', '0 B')
                                ),
                                "previous": self._parse_bandwidth_string(
                                    bandwidth_stats.get('bandwidthLast30Days', {}).get('previous', '0 B')
                                ),
                                "difference": bandwidth_stats.get('bandwidthLast30Days', {}).get('difference', '0 B')
                            },
                            "current_month": {
                                "current": self._parse_bandwidth_string(
                                    bandwidth_stats.get('bandwidthCalendarMonth', {}).get('current', '0 B')
                                ),
                                "previous": self._parse_bandwidth_string(
                                    bandwidth_stats.get('bandwidthCalendarMonth', {}).get('previous', '0 B')
                                ),
                                "difference": bandwidth_stats.get('bandwidthCalendarMonth', {}).get('difference', '0 B')
                            },
                            "current_year": {
                                "current": self._parse_bandwidth_string(
                                    bandwidth_stats.get('bandwidthCurrentYear', {}).get('current', '0 B')
                                ),
                                "previous": self._parse_bandwidth_string(
                                    bandwidth_stats.get('bandwidthCurrentYear', {}).get('previous', '0 B')
                                ),
                                "difference": bandwidth_stats.get('bandwidthCurrentYear', {}).get('difference', '0 B')
                            }
                        },
                        "nodes_realtime": realtime_usage,
                        "nodes_weekly": nodes_weekly_data,
                        "last_updated": datetime.now()
                    }
                    
                    logger.info(f"Statistics compiled: users={result['system']['total_users']}, total traffic={total_user_traffic}")
                    return result
                
            except RemnaWaveAPIError as e:
                logger.error(f"Remnawave API error getting statistics: {e}")
                return {"error": str(e)}
            except Exception as e:
                logger.error(f"General error getting system statistics: {e}")
                return {"error": f"Internal server error: {str(e)}"}

    
    def _parse_bandwidth_string(self, bandwidth_str: str) -> int:
            try:
                if not bandwidth_str or bandwidth_str == '0 B' or bandwidth_str == '0':
                    return 0
            
                bandwidth_str = bandwidth_str.replace(' ', '').upper()
            
                units = {
                    'B': 1,
                    'KB': 1024,
                    'MB': 1024 ** 2,
                    'GB': 1024 ** 3,
                    'TB': 1024 ** 4,
                    'KIB': 1024,          
                    'MIB': 1024 ** 2,
                    'GIB': 1024 ** 3,
                    'TIB': 1024 ** 4,
                    'KBPS': 1024,      
                    'MBPS': 1024 ** 2,
                    'GBPS': 1024 ** 3
                }
            
                match = re.match(r'([0-9.,]+)([A-Z]+)', bandwidth_str)
                if match:
                    value_str = match.group(1).replace(',', '.') 
                    value = float(value_str)
                    unit = match.group(2)
                
                    if unit in units:
                        result = int(value * units[unit])
                        logger.debug(f"Parsing '{bandwidth_str}': {value} {unit} = {result} bytes")
                        return result
                    else:
                        logger.warning(f"Unknown unit: {unit}")
            
                logger.warning(f"Failed to parse traffic string: '{bandwidth_str}'")
                return 0
            
            except Exception as e:
                logger.error(f"Error parsing traffic string '{bandwidth_str}': {e}")
                return 0
    
    async def get_all_nodes(self) -> List[Dict[str, Any]]:
        
        try:
            async with self.get_api_client() as api:
                nodes = await api.get_all_nodes()
                
                result = []
                for node in nodes:
                    result.append({
                        'uuid': node.uuid,
                        'name': node.name,
                        'address': node.address,
                        'country_code': node.country_code,
                        'is_connected': node.is_connected,
                        'is_disabled': node.is_disabled,
                        'is_node_online': node.is_node_online,
                        'is_xray_running': node.is_xray_running,
                        'users_online': node.users_online,
                        'traffic_used_bytes': node.traffic_used_bytes,
                        'traffic_limit_bytes': node.traffic_limit_bytes
                    })
                
                logger.info(f"✅ Retrieved {len(result)} nodes from Remnawave")
                return result
                
        except Exception as e:
            logger.error(f"Error getting nodes from Remnawave: {e}")
            return []

    async def test_connection(self) -> bool:
        
        try:
            async with self.get_api_client() as api:
                stats = await api.get_system_stats()
                logger.info("✅ Connection to Remnawave API is working")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error connecting to Remnawave API: {e}")
            return False
    
    async def get_node_details(self, node_uuid: str) -> Optional[Dict[str, Any]]:
        try:
            async with self.get_api_client() as api:
                node = await api.get_node_by_uuid(node_uuid)
                
                if not node:
                    return None
                
                return {
                    "uuid": node.uuid,
                    "name": node.name,
                    "address": node.address,
                    "country_code": node.country_code,
                    "is_connected": node.is_connected,
                    "is_disabled": node.is_disabled,
                    "is_node_online": node.is_node_online,
                    "is_xray_running": node.is_xray_running,
                    "users_online": node.users_online or 0,
                    "traffic_used_bytes": node.traffic_used_bytes or 0,
                    "traffic_limit_bytes": node.traffic_limit_bytes or 0
                }
                
        except Exception as e:
            logger.error(f"Error getting node information for {node_uuid}: {e}")
            return None
    
    async def manage_node(self, node_uuid: str, action: str) -> bool:
        try:
            async with self.get_api_client() as api:
                if action == "enable":
                    await api.enable_node(node_uuid)
                elif action == "disable":
                    await api.disable_node(node_uuid)
                elif action == "restart":
                    await api.restart_node(node_uuid)
                else:
                    return False
                
                logger.info(f"✅ Action {action} executed for node {node_uuid}")
                return True
                
        except Exception as e:
            logger.error(f"Error managing node {node_uuid}: {e}")
            return False
    
    async def restart_all_nodes(self) -> bool:
        try:
            async with self.get_api_client() as api:
                result = await api.restart_all_nodes()
                
                if result:
                    logger.info("✅ Restart all nodes command sent")
                
                return result
                
        except Exception as e:
            logger.error(f"Error restarting all nodes: {e}")
            return False

    async def update_squad_inbounds(self, squad_uuid: str, inbound_uuids: List[str]) -> bool:
        try:
            async with self.get_api_client() as api:
                data = {
                    'uuid': squad_uuid,
                    'inbounds': inbound_uuids
                }
                response = await api._make_request('PATCH', '/api/internal-squads', data)
                return True
        except Exception as e:
            logger.error(f"Error updating squad inbounds: {e}")
            return False
    
    async def get_all_squads(self) -> List[Dict[str, Any]]:
        
        try:
            async with self.get_api_client() as api:
                squads = await api.get_internal_squads()
                
                result = []
                for squad in squads:
                    result.append({
                        'uuid': squad.uuid,
                        'name': squad.name,
                        'members_count': squad.members_count,
                        'inbounds_count': squad.inbounds_count,
                        'inbounds': squad.inbounds
                    })
                
                logger.info(f"✅ Retrieved {len(result)} squads from Remnawave")
                return result
                
        except Exception as e:
            logger.error(f"Error getting squads from Remnawave: {e}")
            return []
    
    async def create_squad(self, name: str, inbounds: List[str]) -> Optional[str]:
        try:
            async with self.get_api_client() as api:
                squad = await api.create_internal_squad(name, inbounds)
                
                logger.info(f"✅ Created new squad: {name}")
                return squad.uuid
                
        except Exception as e:
            logger.error(f"Error creating squad {name}: {e}")
            return None
    
    async def update_squad(self, uuid: str, name: str = None, inbounds: List[str] = None) -> bool:
        try:
            async with self.get_api_client() as api:
                await api.update_internal_squad(uuid, name, inbounds)
                
                logger.info(f"✅ Updated squad {uuid}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating squad {uuid}: {e}")
            return False
    
    async def delete_squad(self, uuid: str) -> bool:
        try:
            async with self.get_api_client() as api:
                result = await api.delete_internal_squad(uuid)

                if result:
                    logger.info(f"✅ Deleted squad {uuid}")
                
                return result
                
        except Exception as e:
            logger.error(f"Error deleting squad {uuid}: {e}")
            return False

    async def migrate_squad_users(
        self,
        db: AsyncSession,
        source_uuid: str,
        target_uuid: str,
    ) -> Dict[str, Any]:
        """Migrates active subscriptions from one squad to another."""

        if source_uuid == target_uuid:
            return {
                "success": False,
                "error": "same_squad",
                "message": "Source and destination are the same",
            }

        source_uuid = source_uuid.strip()
        target_uuid = target_uuid.strip()

        source_server = await get_server_squad_by_uuid(db, source_uuid)
        target_server = await get_server_squad_by_uuid(db, target_uuid)

        if not source_server or not target_server:
            return {
                "success": False,
                "error": "not_found",
                "message": "Squads not found",
            }

        subscription_query = (
            select(Subscription)
            .options(selectinload(Subscription.user))
            .where(
                Subscription.status.in_(
                    [
                        SubscriptionStatus.ACTIVE.value,
                        SubscriptionStatus.TRIAL.value,
                    ]
                ),
                cast(Subscription.connected_squads, String).like(
                    f'%"{source_uuid}"%'
                ),
            )
        )

        result = await db.execute(subscription_query)
        subscriptions = result.scalars().unique().all()

        total_candidates = len(subscriptions)
        if not subscriptions:
            logger.info(
                "🚚 Squad migration %s → %s: no matching subscriptions found",
                source_uuid,
                target_uuid,
            )
            return {
                "success": True,
                "total": 0,
                "updated": 0,
                "panel_updated": 0,
                "panel_failed": 0,
            }

        exit_stack = AsyncExitStack()
        panel_updated = 0
        panel_failed = 0
        updated_subscriptions = 0
        source_decrement = 0
        target_increment = 0

        try:
            needs_panel_update = any(
                subscription.user and subscription.user.remnawave_uuid
                for subscription in subscriptions
            )

            api = None
            if needs_panel_update:
                api = await exit_stack.enter_async_context(self.get_api_client())

            for subscription in subscriptions:
                current_squads = list(subscription.connected_squads or [])
                if source_uuid not in current_squads:
                    continue

                had_target_before = target_uuid in current_squads
                new_squads = [
                    squad_uuid for squad_uuid in current_squads if squad_uuid != source_uuid
                ]
                if not had_target_before:
                    new_squads.append(target_uuid)

                if subscription.user and subscription.user.remnawave_uuid:
                    if api is None:
                        panel_failed += 1
                        logger.error(
                            "❌ RemnaWave API unavailable for updating user %s",
                            subscription.user.telegram_id,
                        )
                        continue

                    try:
                        await api.update_user(
                            uuid=subscription.user.remnawave_uuid,
                            active_internal_squads=new_squads,
                        )
                        panel_updated += 1
                    except Exception as error:
                        panel_failed += 1
                        logger.error(
                            "❌ Error updating user %s squads: %s",
                            subscription.user.telegram_id,
                            error,
                        )
                        continue

                subscription.connected_squads = new_squads
                subscription.updated_at = datetime.utcnow()

                source_decrement += 1
                if not had_target_before:
                    target_increment += 1

                updated_subscriptions += 1

                link_result = await db.execute(
                    select(SubscriptionServer)
                    .where(
                        and_(
                            SubscriptionServer.subscription_id == subscription.id,
                            SubscriptionServer.server_squad_id == source_server.id,
                        )
                    )
                    .limit(1)
                )
                link = link_result.scalars().first()

                if link:
                    if had_target_before:
                        await db.execute(
                            delete(SubscriptionServer).where(
                                and_(
                                    SubscriptionServer.subscription_id
                                    == subscription.id,
                                    SubscriptionServer.server_squad_id
                                    == source_server.id,
                                )
                            )
                        )
                    else:
                        link.server_squad_id = target_server.id
                elif not had_target_before:
                    db.add(
                        SubscriptionServer(
                            subscription_id=subscription.id,
                            server_squad_id=target_server.id,
                            paid_price_kopeks=0,
                        )
                    )

            if updated_subscriptions:
                if source_decrement:
                    await db.execute(
                        update(ServerSquad)
                        .where(ServerSquad.id == source_server.id)
                        .values(
                            current_users=func.greatest(
                                ServerSquad.current_users - source_decrement,
                                0,
                            )
                        )
                    )
                if target_increment:
                    await db.execute(
                        update(ServerSquad)
                        .where(ServerSquad.id == target_server.id)
                        .values(
                            current_users=ServerSquad.current_users + target_increment
                        )
                    )

                await db.commit()
            else:
                await db.rollback()

            logger.info(
                "🚚 Squad migration completed %s → %s: updated %s subscriptions (%s not updated in panel)",
                source_uuid,
                target_uuid,
                updated_subscriptions,
                panel_failed,
            )

            return {
                "success": True,
                "total": total_candidates,
                "updated": updated_subscriptions,
                "panel_updated": panel_updated,
                "panel_failed": panel_failed,
                "source_removed": source_decrement,
                "target_added": target_increment,
            }

        except RemnaWaveConfigurationError:
            await db.rollback()
            raise
        except Exception as error:
            await db.rollback()
            logger.error(
                "❌ Error migrating squad %s → %s: %s",
                source_uuid,
                target_uuid,
                error,
            )
            return {
                "success": False,
                "error": "unexpected",
                "message": str(error),
            }
        finally:
            await exit_stack.aclose()

    async def sync_users_from_panel(self, db: AsyncSession, sync_type: str = "all") -> Dict[str, int]:
        try:
            stats = {"created": 0, "updated": 0, "errors": 0, "deleted": 0}
            
            logger.info(f"🔄 Starting synchronization type: {sync_type}")
            
            async with self.get_api_client() as api:
                panel_users = []
                start = 0
                size = 100 
                
                while True:
                    logger.info(f"📥 Loading users: start={start}, size={size}")
                    
                    response = await api.get_all_users(start=start, size=size)
                    users_batch = response['users']
                    total_users = response['total']
                    
                    logger.info(f"📊 Retrieved {len(users_batch)} users out of {total_users}")
                    
                    for user_obj in users_batch:
                        user_dict = {
                            'uuid': user_obj.uuid,
                            'shortUuid': user_obj.short_uuid,
                            'username': user_obj.username,
                            'status': user_obj.status.value,
                            'telegramId': user_obj.telegram_id,
                            'expireAt': user_obj.expire_at.isoformat() + 'Z',
                            'trafficLimitBytes': user_obj.traffic_limit_bytes,
                            'usedTrafficBytes': user_obj.used_traffic_bytes,
                            'hwidDeviceLimit': user_obj.hwid_device_limit,
                            'subscriptionUrl': user_obj.subscription_url,
                            'subscriptionCryptoLink': user_obj.happ_crypto_link,
                            'activeInternalSquads': user_obj.active_internal_squads
                        }
                        panel_users.append(user_dict)
                    
                    if len(users_batch) < size:
                        break
                        
                    start += size
                    
                    if start > total_users:
                        break
                
                logger.info(f"✅ Total users loaded from panel: {len(panel_users)}")
            
            # Loading users with their subscriptions in one query (bulk loading)
            from sqlalchemy.orm import selectinload
            from app.database.models import User, Subscription
            from sqlalchemy import select
            
            # Get all users with their subscriptions in one query
            bot_users_result = await db.execute(
                select(User)
                .options(selectinload(User.subscription))
            )
            bot_users = bot_users_result.scalars().all()
            bot_users_by_telegram_id = {user.telegram_id: user for user in bot_users}
            bot_users_by_uuid = {
                user.remnawave_uuid: user
                for user in bot_users
                if getattr(user, "remnawave_uuid", None)
            }

            logger.info(f"📊 Users in bot: {len(bot_users)}")
            
            panel_users_with_tg = [
                user for user in panel_users
                if user.get('telegramId') is not None
            ]

            logger.info(f"📊 Users in panel with Telegram ID: {len(panel_users_with_tg)}")

            unique_panel_users_map = self._deduplicate_panel_users_by_telegram_id(panel_users_with_tg)
            unique_panel_users = list(unique_panel_users_map.values())
            duplicates_count = len(panel_users_with_tg) - len(unique_panel_users)

            if duplicates_count:
                logger.info(
                    "♻️ Found %s duplicate users by Telegram ID. Using most recent records.",
                    duplicates_count,
                )

            panel_telegram_ids = set(unique_panel_users_map.keys())

            # For speed - prepare subscription data
            # Collect all existing subscriptions in one query
            existing_subscriptions_result = await db.execute(
                select(Subscription)
                .join(User)
                .options(selectinload(Subscription.user))
            )
            existing_subscriptions = existing_subscriptions_result.scalars().all()
            
            # Create dictionary for quick access to subscriptions
            subscriptions_by_user_id = {sub.user_id: sub for sub in existing_subscriptions}

            # For optimization commit changes every N users
            batch_size = 50
            pending_uuid_mutations: List[_UUIDMapMutation] = []

            for i, panel_user in enumerate(unique_panel_users):
                uuid_mutation: Optional[_UUIDMapMutation] = None
                try:
                    telegram_id = panel_user.get('telegramId')
                    if not telegram_id:
                        continue

                    if (i + 1) % 10 == 0:
                        logger.info(f"🔄 Processing user {i+1}/{len(unique_panel_users)}: {telegram_id}")
                    
                    db_user = bot_users_by_telegram_id.get(telegram_id)
                    
                    if not db_user:
                        if sync_type in ["new_only", "all"]:
                            logger.info(f"🆕 Creating user for telegram_id {telegram_id}")

                            db_user, is_created = await self._get_or_create_bot_user_from_panel(db, panel_user)

                            if not db_user:
                                logger.error(
                                    "❌ Failed to create or get user for telegram_id %s",
                                    telegram_id,
                                )
                                stats["errors"] += 1
                                continue

                            bot_users_by_telegram_id[telegram_id] = db_user

                            # During sync we don't update user name and username
                            # only save changes if other fields were updated (subscription etc.)
                            updated_fields = []
                            # If other fields were updated (subscription, status etc.), save changes
                            if updated_fields:
                                logger.info(f"🔄 Updated fields {updated_fields} for user {telegram_id}")
                                await db.flush()  # Save changes without commit

                            _, uuid_mutation = self._ensure_user_remnawave_uuid(
                                db_user,
                                panel_user.get('uuid'),
                                bot_users_by_uuid,
                            )

                            if is_created:
                                await self._create_subscription_from_panel_data(db, db_user, panel_user)
                                stats["created"] += 1
                                logger.info(f"✅ Created user {telegram_id} with subscription")
                            else:
                                # Update existing user data
                                # But we already loaded subscription with user, no need to reload
                                await self._update_subscription_from_panel_data(db, db_user, panel_user)
                                stats["updated"] += 1
                                logger.info(
                                    f"♻️ Updated subscription for existing user {telegram_id}"
                                )
                    
                    else:
                        if sync_type in ["update_only", "all"]:
                            logger.debug(f"🔄 Updating user {telegram_id}")
                            
                            # During sync we don't update user name and username
                            # only save changes if other fields were updated (subscription etc.)
                            updated_fields = []
                            # If other fields were updated (subscription, status etc.), save changes
                            if updated_fields:
                                logger.info(f"🔄 Updated fields {updated_fields} for user {telegram_id}")
                                await db.flush()  # Save changes without commit
                            
                            # Check if user has subscription loaded with user
                            if hasattr(db_user, 'subscription') and db_user.subscription:
                                # Use already loaded subscription
                                await self._update_subscription_from_panel_data(db, db_user, panel_user)
                            else:
                                # If no subscription, create new one
                                await self._create_subscription_from_panel_data(db, db_user, panel_user)

                            _, uuid_mutation = self._ensure_user_remnawave_uuid(
                                db_user,
                                panel_user.get('uuid'),
                                bot_users_by_uuid,
                            )

                            stats["updated"] += 1
                            logger.debug(f"✅ Updated user {telegram_id}")

                except Exception as user_error:
                    logger.error(f"❌ Error processing user {telegram_id}: {user_error}")
                    stats["errors"] += 1
                    if uuid_mutation:
                        uuid_mutation.rollback()
                    if pending_uuid_mutations:
                        for mutation in reversed(pending_uuid_mutations):
                            mutation.rollback()
                        pending_uuid_mutations.clear()
                    try:
                        await db.rollback()  # Perform rollback on error
                    except:
                        pass
                    continue

                else:
                    if uuid_mutation and uuid_mutation.has_changes():
                        pending_uuid_mutations.append(uuid_mutation)

                # Commit changes every N users for speed
                if (i + 1) % batch_size == 0:
                    try:
                        await db.commit()
                        logger.debug(f"📦 Committed changes after processing {i+1} users")
                        pending_uuid_mutations.clear()
                    except Exception as commit_error:
                        logger.error(f"❌ Commit error after processing {i+1} users: {commit_error}")
                        await db.rollback()
                        for mutation in reversed(pending_uuid_mutations):
                            mutation.rollback()
                        pending_uuid_mutations.clear()
                        stats["errors"] += batch_size  # Count errors for entire group

            # Commit remaining changes
            try:
                await db.commit()
                pending_uuid_mutations.clear()
            except Exception as final_commit_error:
                logger.error(f"❌ Final commit error: {final_commit_error}")
                await db.rollback()
                for mutation in reversed(pending_uuid_mutations):
                    mutation.rollback()
                pending_uuid_mutations.clear()

            if sync_type == "all":
                logger.info("🗑️ Deactivating subscriptions for users missing from panel...")

                batch_size = 50
                processed_count = 0
                cleanup_uuid_mutations: List[_UUIDMapMutation] = []

                for telegram_id, db_user in bot_users_by_telegram_id.items():
                    if telegram_id not in panel_telegram_ids and hasattr(db_user, 'subscription') and db_user.subscription:
                        cleanup_mutation: Optional[_UUIDMapMutation] = None
                        try:
                            logger.info(f"🗑️ Deactivating subscription for user {telegram_id} (not in panel)")

                            subscription = db_user.subscription
                            
                            if db_user.remnawave_uuid:
                                try:
                                    async with self.get_api_client() as api:
                                        devices_reset = await api.reset_user_devices(db_user.remnawave_uuid)
                                        if devices_reset:
                                            logger.info(f"🔧 Reset HWID devices for user {telegram_id}")
                                except Exception as hwid_error:
                                    logger.error(f"❌ Error resetting HWID devices for {telegram_id}: {hwid_error}")
                            
                            try:
                                from sqlalchemy import delete
                                from app.database.models import SubscriptionServer

                                await decrement_subscription_server_counts(db, subscription)

                                await db.execute(
                                    delete(SubscriptionServer).where(
                                        SubscriptionServer.subscription_id == subscription.id
                                    )
                                )
                                logger.info(f"🗑️ Deleted subscription servers for {telegram_id}")
                            except Exception as servers_error:
                                logger.warning(f"⚠️ Failed to delete subscription servers: {servers_error}")
                            
                            from app.database.models import SubscriptionStatus
                            
                            subscription.status = SubscriptionStatus.DISABLED.value
                            subscription.is_trial = True 
                            subscription.end_date = datetime.utcnow()
                            subscription.traffic_limit_gb = 0
                            subscription.traffic_used_gb = 0.0
                            subscription.device_limit = 1
                            subscription.connected_squads = []
                            subscription.autopay_enabled = False
                            subscription.remnawave_short_uuid = None
                            subscription.subscription_url = ""
                            subscription.subscription_crypto_link = ""

                            old_uuid = getattr(db_user, "remnawave_uuid", None)
                            cleanup_mutation = _UUIDMapMutation(bot_users_by_uuid)
                            if old_uuid:
                                cleanup_mutation.remove_map_entry(old_uuid)
                            cleanup_mutation.set_user_uuid(db_user, None)
                            cleanup_mutation.set_user_updated_at(db_user, datetime.utcnow())

                            stats["deleted"] += 1
                            logger.info(f"✅ Deactivated subscription for user {telegram_id} (balance preserved)")

                            processed_count += 1

                        except Exception as delete_error:
                            logger.error(f"❌ Error deactivating subscription {telegram_id}: {delete_error}")
                            stats["errors"] += 1
                            if cleanup_mutation:
                                cleanup_mutation.rollback()
                            if cleanup_uuid_mutations:
                                for mutation in reversed(cleanup_uuid_mutations):
                                    mutation.rollback()
                                cleanup_uuid_mutations.clear()
                            try:
                                await db.rollback()
                            except:
                                pass
                        else:
                            if cleanup_mutation and cleanup_mutation.has_changes():
                                cleanup_uuid_mutations.append(cleanup_mutation)

                            # Commit changes every N users
                            if processed_count % batch_size == 0:
                                try:
                                    await db.commit()
                                    logger.debug(f"📦 Committed changes after deactivating {processed_count} subscriptions")
                                    cleanup_uuid_mutations.clear()
                                except Exception as commit_error:
                                    logger.error(f"❌ Commit error after deactivating {processed_count} subscriptions: {commit_error}")
                                    await db.rollback()
                                    for mutation in reversed(cleanup_uuid_mutations):
                                        mutation.rollback()
                                    cleanup_uuid_mutations.clear()
                                    stats["errors"] += batch_size
                                    break  # Break loop on commit error
                    else:
                        # Increment counter for progress tracking
                        processed_count += 1

                # Commit remaining changes
                try:
                    await db.commit()
                    cleanup_uuid_mutations.clear()
                except Exception as final_commit_error:
                    logger.error(f"❌ Final commit error during deactivation: {final_commit_error}")
                    await db.rollback()
                    for mutation in reversed(cleanup_uuid_mutations):
                        mutation.rollback()
                    cleanup_uuid_mutations.clear()
            
            logger.info(f"🎯 Synchronization completed: created {stats['created']}, updated {stats['updated']}, deactivated {stats['deleted']}, errors {stats['errors']}")
            return stats
        
        except Exception as e:
            logger.error(f"❌ Critical error synchronizing users: {e}")
            return {"created": 0, "updated": 0, "errors": 1, "deleted": 0}

    async def _create_subscription_from_panel_data(self, db: AsyncSession, user, panel_user):
        try:
            from app.database.crud.subscription import create_subscription_no_commit
            from app.database.models import SubscriptionStatus
        
            expire_at_str = panel_user.get('expireAt', '')
            expire_at = self._parse_remnawave_date(expire_at_str)
        
            panel_status = panel_user.get('status', 'ACTIVE')
            current_time = self._now_utc()
        
            if panel_status == 'ACTIVE' and expire_at > current_time:
                status = SubscriptionStatus.ACTIVE
            elif expire_at <= current_time:
                status = SubscriptionStatus.EXPIRED
            else:
                status = SubscriptionStatus.DISABLED
        
            traffic_limit_bytes = panel_user.get('trafficLimitBytes', 0)
            traffic_limit_gb = traffic_limit_bytes // (1024**3) if traffic_limit_bytes > 0 else 0
        
            used_traffic_bytes = panel_user.get('usedTrafficBytes', 0)
            traffic_used_gb = used_traffic_bytes / (1024**3)
        
            active_squads = panel_user.get('activeInternalSquads', [])
            squad_uuids = []
            if isinstance(active_squads, list):
                for squad in active_squads:
                    if isinstance(squad, dict) and 'uuid' in squad:
                        squad_uuids.append(squad['uuid'])
                    elif isinstance(squad, str):
                        squad_uuids.append(squad)
        
            subscription_data = {
                'user_id': user.id,
                'status': status.value,
                'is_trial': False,
                'end_date': expire_at,
                'traffic_limit_gb': traffic_limit_gb,
                'traffic_used_gb': traffic_used_gb,
                'device_limit': panel_user.get('hwidDeviceLimit', 1) or 1,
                'connected_squads': squad_uuids,
                'remnawave_short_uuid': panel_user.get('shortUuid'),
                'subscription_url': panel_user.get('subscriptionUrl', ''),
                'subscription_crypto_link': (
                    panel_user.get('subscriptionCryptoLink')
                    or (panel_user.get('happ') or {}).get('cryptoLink', '')
                )
            }
        
            subscription = await create_subscription_no_commit(db, **subscription_data)
            logger.info(f"✅ Prepared subscription for user {user.telegram_id} until {expire_at}")
        
        except Exception as e:
            logger.error(f"❌ Error creating subscription for user {user.telegram_id}: {e}")
            try:
                from app.database.crud.subscription import create_subscription_no_commit
                from app.database.models import SubscriptionStatus
            
                basic_subscription = await create_subscription_no_commit(
                    db=db,
                    user_id=user.id,
                    status=SubscriptionStatus.ACTIVE.value,
                    is_trial=False,
                    end_date=self._now_utc() + timedelta(days=30),
                    traffic_limit_gb=0,
                    traffic_used_gb=0.0,
                    device_limit=1,
                    connected_squads=[],
                    remnawave_short_uuid=panel_user.get('shortUuid'),
                    subscription_url=panel_user.get('subscriptionUrl', ''),
                    subscription_crypto_link=(
                        panel_user.get('subscriptionCryptoLink')
                        or (panel_user.get('happ') or {}).get('cryptoLink', '')
                    )
                )
                logger.info(f"✅ Prepared basic subscription for user {user.telegram_id}")
            except Exception as basic_error:
                logger.error(f"❌ Error creating basic subscription: {basic_error}")

    async def _update_subscription_from_panel_data(self, db: AsyncSession, user, panel_user):
        try:
            from app.database.crud.subscription import get_subscription_by_user_id
            from app.database.models import SubscriptionStatus
            
            # First try to use already loaded subscription if available
            subscription = None
            try:
                # Check that subscription is already loaded (was loaded via selectinload)
                if hasattr(user, 'subscription') and user.subscription:
                    subscription = user.subscription
                else:
                    # Otherwise, get subscription via CRUD method
                    subscription = await get_subscription_by_user_id(db, user.id)
            except:
                # If failed to get subscription via lazy loading
                subscription = await get_subscription_by_user_id(db, user.id)
            
            if not subscription:
                await self._create_subscription_from_panel_data(db, user, panel_user)
                return
        
            panel_status = panel_user.get('status', 'ACTIVE')
            expire_at_str = panel_user.get('expireAt', '')
            
            if expire_at_str:
                expire_at = self._parse_remnawave_date(expire_at_str)
                
                if abs((subscription.end_date - expire_at).total_seconds()) > 60: 
                    subscription.end_date = expire_at
                    logger.debug(f"Updated subscription expiration date to {expire_at}")
            
            current_time = self._now_utc()
            if panel_status == 'ACTIVE' and subscription.end_date > current_time:
                new_status = SubscriptionStatus.ACTIVE.value
            elif subscription.end_date <= current_time:
                new_status = SubscriptionStatus.EXPIRED.value
            elif panel_status == 'DISABLED':
                new_status = SubscriptionStatus.DISABLED.value
            else:
                new_status = subscription.status 
            
            if subscription.status != new_status:
                subscription.status = new_status
                logger.debug(f"Updated subscription status: {new_status}")
        
            used_traffic_bytes = panel_user.get('usedTrafficBytes', 0)
            traffic_used_gb = used_traffic_bytes / (1024**3)
        
            if abs(subscription.traffic_used_gb - traffic_used_gb) > 0.01:
                subscription.traffic_used_gb = traffic_used_gb
                logger.debug(f"Updated used traffic: {traffic_used_gb} GB")
            
            traffic_limit_bytes = panel_user.get('trafficLimitBytes', 0)
            traffic_limit_gb = traffic_limit_bytes // (1024**3) if traffic_limit_bytes > 0 else 0
            
            if subscription.traffic_limit_gb != traffic_limit_gb:
                subscription.traffic_limit_gb = traffic_limit_gb
                logger.debug(f"Updated traffic limit: {traffic_limit_gb} GB")
            
            device_limit = panel_user.get('hwidDeviceLimit', 1) or 1
            if subscription.device_limit != device_limit:
                subscription.device_limit = device_limit
                logger.debug(f"Updated device limit: {device_limit}")
        
            new_short_uuid = panel_user.get('shortUuid')
            if new_short_uuid and subscription.remnawave_short_uuid != new_short_uuid:
                old_short_uuid = subscription.remnawave_short_uuid
                subscription.remnawave_short_uuid = new_short_uuid
                logger.debug(
                    "Updated subscription short UUID for user %s: %s → %s",
                    getattr(user, "telegram_id", "?"),
                    old_short_uuid,
                    new_short_uuid,
                )
        
            panel_url = panel_user.get('subscriptionUrl', '')
            if not subscription.subscription_url or subscription.subscription_url != panel_url:
                subscription.subscription_url = panel_url

            panel_crypto_link = (
                panel_user.get('subscriptionCryptoLink')
                or (panel_user.get('happ') or {}).get('cryptoLink', '')
            )
            if panel_crypto_link and subscription.subscription_crypto_link != panel_crypto_link:
                subscription.subscription_crypto_link = panel_crypto_link
        
            active_squads = panel_user.get('activeInternalSquads', [])
            squad_uuids = []
            if isinstance(active_squads, list):
                for squad in active_squads:
                    if isinstance(squad, dict) and 'uuid' in squad:
                        squad_uuids.append(squad['uuid'])
                    elif isinstance(squad, str):
                        squad_uuids.append(squad)
        
            current_squads = set(subscription.connected_squads or [])
            new_squads = set(squad_uuids)
            
            if current_squads != new_squads:
                subscription.connected_squads = squad_uuids
                logger.debug(f"Updated connected squads: {squad_uuids}")
        
            # Commit changes later, in main loop, to reduce number of transactions
            logger.debug(f"✅ Updated subscription for user {user.telegram_id}")
        
        except Exception as e:
            logger.error(f"❌ Error updating subscription for user {user.telegram_id}: {e}")
            # Don't do rollback, as it may affect other operations
            # Propagate error up for correct handling in main loop
            raise
    
    async def sync_users_to_panel(self, db: AsyncSession) -> Dict[str, int]:
        try:
            stats = {"created": 0, "updated": 0, "errors": 0}

            batch_size = 100
            offset = 0

            async with self.get_api_client() as api:
                while True:
                    users = await get_users_list(db, offset=offset, limit=batch_size)

                    if not users:
                        break

                    for user in users:
                        if not user.subscription:
                            continue

                        try:
                            subscription = user.subscription
                            hwid_limit = resolve_hwid_device_limit_for_payload(subscription)

                            expire_at = self._safe_expire_at_for_panel(subscription.end_date)
                            status = UserStatus.ACTIVE if subscription.is_active else UserStatus.DISABLED

                            username = settings.format_remnawave_username(
                                full_name=user.full_name,
                                username=user.username,
                                telegram_id=user.telegram_id,
                            )

                            create_kwargs = dict(
                                username=username,
                                expire_at=expire_at,
                                status=status,
                                traffic_limit_bytes=subscription.traffic_limit_gb * (1024**3) if subscription.traffic_limit_gb > 0 else 0,
                                traffic_limit_strategy=TrafficLimitStrategy.MONTH,
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

                            if user.remnawave_uuid:
                                update_kwargs = dict(
                                    uuid=user.remnawave_uuid,
                                    status=status,
                                    expire_at=expire_at,
                                    traffic_limit_bytes=create_kwargs['traffic_limit_bytes'],
                                    traffic_limit_strategy=TrafficLimitStrategy.MONTH,
                                    description=create_kwargs['description'],
                                    active_internal_squads=subscription.connected_squads,
                                )

                                if hwid_limit is not None:
                                    update_kwargs['hwid_device_limit'] = hwid_limit

                                try:
                                    await api.update_user(**update_kwargs)
                                    stats["updated"] += 1
                                except RemnaWaveAPIError as api_error:
                                    if api_error.status_code == 404:
                                        logger.warning(
                                            "⚠️ User %s not found in panel, creating anew",
                                            user.remnawave_uuid,
                                        )

                                        new_user = await api.create_user(**create_kwargs)
                                        user.remnawave_uuid = new_user.uuid
                                        subscription.remnawave_short_uuid = new_user.short_uuid
                                        stats["created"] += 1
                                    else:
                                        raise
                            else:
                                new_user = await api.create_user(**create_kwargs)

                                user.remnawave_uuid = new_user.uuid
                                subscription.remnawave_short_uuid = new_user.short_uuid

                                stats["created"] += 1

                        except Exception as e:
                            logger.error(f"Error syncing user {user.telegram_id} to panel: {e}")
                            stats["errors"] += 1

                    try:
                        await db.commit()
                    except Exception as commit_error:
                        logger.error(
                            "Error committing transaction during panel sync: %s",
                            commit_error,
                        )
                        await db.rollback()
                        stats["errors"] += len(users)

                    if len(users) < batch_size:
                        break

                    offset += batch_size

            logger.info(
                f"✅ Panel sync completed: created {stats['created']}, updated {stats['updated']}, errors {stats['errors']}"
            )
            return stats
            
        except Exception as e:
            logger.error(f"Error syncing users to panel: {e}")
            return {"created": 0, "updated": 0, "errors": 1}
    
    async def get_user_traffic_stats(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        try:
            async with self.get_api_client() as api:
                users = await api.get_user_by_telegram_id(telegram_id)
                
                if not users:
                    return None
                
                user = users[0]
                
                return {
                    "used_traffic_bytes": user.used_traffic_bytes,
                    "used_traffic_gb": user.used_traffic_bytes / (1024**3),
                    "lifetime_used_traffic_bytes": user.lifetime_used_traffic_bytes,
                    "lifetime_used_traffic_gb": user.lifetime_used_traffic_bytes / (1024**3),
                    "traffic_limit_bytes": user.traffic_limit_bytes,
                    "traffic_limit_gb": user.traffic_limit_bytes / (1024**3) if user.traffic_limit_bytes > 0 else 0,
                    "subscription_url": user.subscription_url
                }
                
        except Exception as e:
            logger.error(f"Error getting traffic statistics for user {telegram_id}: {e}")
            return None
    
    async def test_api_connection(self) -> Dict[str, Any]:
        if not self.is_configured:
            return {
                "status": "not_configured",
                "message": self.configuration_error or "RemnaWave API is not configured",
                "api_url": settings.REMNAWAVE_API_URL,
            }
        try:
            async with self.get_api_client() as api:
                system_stats = await api.get_system_stats()

                return {
                    "status": "connected",
                    "message": "Connection successful",
                    "api_url": settings.REMNAWAVE_API_URL,
                    "system_info": system_stats
                }

        except RemnaWaveAPIError as e:
            return {
                "status": "error",
                "message": f"API error: {e.message}",
                "status_code": e.status_code,
                "api_url": settings.REMNAWAVE_API_URL
            }
        except RemnaWaveConfigurationError as e:
            return {
                "status": "not_configured",
                "message": str(e),
                "api_url": settings.REMNAWAVE_API_URL,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Connection error: {str(e)}",
                "api_url": settings.REMNAWAVE_API_URL
            }
    
    async def get_nodes_realtime_usage(self) -> List[Dict[str, Any]]:
        try:
            async with self.get_api_client() as api:
                usage_data = await api.get_nodes_realtime_usage()
                return usage_data
                
        except Exception as e:
            logger.error(f"Error getting current node usage: {e}")
            return []

    async def get_squad_details(self, squad_uuid: str) -> Optional[Dict]:
        try:
            async with self.get_api_client() as api:
                squad = await api.get_internal_squad_by_uuid(squad_uuid)
                if squad:
                    return {
                        'uuid': squad.uuid,
                        'name': squad.name,
                        'members_count': squad.members_count,
                        'inbounds_count': squad.inbounds_count,
                        'inbounds': squad.inbounds
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting squad details: {e}")
            return None

    async def add_all_users_to_squad(self, squad_uuid: str) -> bool:
        try:
            async with self.get_api_client() as api:
                response = await api._make_request('POST', f'/api/internal-squads/{squad_uuid}/bulk-actions/add-users')
                return response.get('response', {}).get('eventSent', False)
        except Exception as e:
            logger.error(f"Error adding users to squad: {e}")
            return False

    async def remove_all_users_from_squad(self, squad_uuid: str) -> bool:
        try:
            async with self.get_api_client() as api:
                response = await api._make_request('DELETE', f'/api/internal-squads/{squad_uuid}/bulk-actions/remove-users')
                return response.get('response', {}).get('eventSent', False)
        except Exception as e:
            logger.error(f"Error removing users from squad: {e}")
            return False

    async def get_all_inbounds(self) -> List[Dict]:
        try:
            async with self.get_api_client() as api:
                response = await api._make_request('GET', '/api/config-profiles/inbounds')
                inbounds_data = response.get('response', {}).get('inbounds', [])
            
                return [
                    {
                        'uuid': inbound['uuid'],
                        'tag': inbound['tag'],
                        'type': inbound['type'],
                        'network': inbound.get('network'),
                        'security': inbound.get('security'),
                        'port': inbound.get('port')
                    }
                    for inbound in inbounds_data
                ]
        except Exception as e:
            logger.error(f"Error getting all inbounds: {e}")
            return []

    async def rename_squad(self, squad_uuid: str, new_name: str) -> bool:
        try:
            async with self.get_api_client() as api:
                data = {
                    'uuid': squad_uuid,
                    'name': new_name
                }
                response = await api._make_request('PATCH', '/api/internal-squads', data)
                return True
        except Exception as e:
            logger.error(f"Error renaming squad: {e}")
            return False

    async def get_node_user_usage_by_range(self, node_uuid: str, start_date, end_date) -> List[Dict[str, Any]]:
        try:
            async with self.get_api_client() as api:
                start_str = start_date.isoformat() + "Z"
                end_str = end_date.isoformat() + "Z"
                
                params = {
                    'start': start_str,
                    'end': end_str
                }
                
                usage_data = await api._make_request(
                    'GET', 
                    f'/api/nodes/usage/{node_uuid}/users/range',
                    params=params
                )
                
                return usage_data.get('response', [])
                
        except Exception as e:
            logger.error(f"Error getting node usage statistics for {node_uuid}: {e}")
            return []

    async def get_node_statistics(self, node_uuid: str) -> Optional[Dict[str, Any]]:
        try:
            node = await self.get_node_details(node_uuid)
            if not node:
                return None
            
            realtime_stats = await self.get_nodes_realtime_usage()
            
            node_realtime = None
            for stats in realtime_stats:
                if stats.get('nodeUuid') == node_uuid:
                    node_realtime = stats
                    break
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            usage_history = await self.get_node_user_usage_by_range(
                node_uuid, start_date, end_date
            )
            
            return {
                'node': node,
                'realtime': node_realtime,
                'usage_history': usage_history,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting node statistics for {node_uuid}: {e}")

    async def validate_user_data_before_sync(self, panel_user) -> bool:
        try:
            if not panel_user.telegram_id:
                logger.debug(f"No telegram_id for user {panel_user.uuid}")
                return False
            
            if not panel_user.uuid:
                logger.debug(f"No UUID for user {panel_user.telegram_id}")
                return False
            
            if panel_user.telegram_id <= 0:
                logger.debug(f"Invalid telegram_id: {panel_user.telegram_id}")
                return False
            
            return True
        
        except Exception as e:
            logger.error(f"Error validating user data: {e}")
            return False

    async def force_cleanup_user_data(self, db: AsyncSession, user: User) -> bool:
        try:
            logger.info(f"🗑️ FORCED full cleanup of user data {user.telegram_id}")
            
            if user.remnawave_uuid:
                try:
                    async with self.get_api_client() as api:
                        devices_reset = await api.reset_user_devices(user.remnawave_uuid)
                        if devices_reset:
                            logger.info(f"🔧 Reset HWID devices for {user.telegram_id}")
                except Exception as hwid_error:
                    logger.warning(f"⚠️ Error resetting HWID devices: {hwid_error}")
            
            try:
                from sqlalchemy import delete
                from app.database.models import (
                    SubscriptionServer, Transaction, ReferralEarning, 
                    PromoCodeUse, SubscriptionStatus
                )
                
                if user.subscription:
                    await decrement_subscription_server_counts(db, user.subscription)

                    await db.execute(
                        delete(SubscriptionServer).where(
                            SubscriptionServer.subscription_id == user.subscription.id
                        )
                    )
                    logger.info(f"🗑️ Deleted subscription servers for {user.telegram_id}")
                
                await db.execute(
                    delete(Transaction).where(Transaction.user_id == user.id)
                )
                logger.info(f"🗑️ Deleted transactions for {user.telegram_id}")
                
                await db.execute(
                    delete(ReferralEarning).where(ReferralEarning.user_id == user.id)
                )
                await db.execute(
                    delete(ReferralEarning).where(ReferralEarning.referral_id == user.id)
                )
                logger.info(f"🗑️ Deleted referral earnings for {user.telegram_id}")
                
                await db.execute(
                    delete(PromoCodeUse).where(PromoCodeUse.user_id == user.id)
                )
                logger.info(f"🗑️ Deleted promo code uses for {user.telegram_id}")
                
            except Exception as records_error:
                logger.error(f"❌ Error deleting related records: {records_error}")
            
            try:
                
                user.balance_kopeks = 0
                user.remnawave_uuid = None
                user.has_had_paid_subscription = False
                user.used_promocodes = 0
                user.updated_at = self._now_utc()
                
                if user.subscription:
                    user.subscription.status = SubscriptionStatus.DISABLED.value
                    user.subscription.is_trial = True
                    user.subscription.end_date = self._now_utc()
                    user.subscription.traffic_limit_gb = 0
                    user.subscription.traffic_used_gb = 0.0
                    user.subscription.device_limit = 1
                    user.subscription.connected_squads = []
                    user.subscription.autopay_enabled = False
                    user.subscription.autopay_days_before = settings.DEFAULT_AUTOPAY_DAYS_BEFORE
                    user.subscription.remnawave_short_uuid = None
                    user.subscription.subscription_url = ""
                    user.subscription.subscription_crypto_link = ""
                    user.subscription.updated_at = self._now_utc()
                
                await db.commit()
                
                logger.info(f"✅ FORCED cleanup of ALL data for user {user.telegram_id}")
                return True
                
            except Exception as cleanup_error:
                logger.error(f"❌ Error during final user cleanup: {cleanup_error}")
                await db.rollback()
                return False
        
        except Exception as e:
            logger.error(f"❌ Critical error during forced cleanup of user {user.telegram_id}: {e}")
            await db.rollback()
            return False

    async def cleanup_orphaned_subscriptions(self, db: AsyncSession) -> Dict[str, int]:
        try:
            stats = {"deactivated": 0, "errors": 0, "checked": 0}
        
            logger.info("🧹 Starting enhanced cleanup of outdated subscriptions...")
        
            async with self.get_api_client() as api:
                panel_users_data = await api._make_request('GET', '/api/users')
                panel_users = panel_users_data['response']['users']
        
            panel_telegram_ids = set()
            for panel_user in panel_users:
                telegram_id = panel_user.get('telegramId')
                if telegram_id:
                    panel_telegram_ids.add(telegram_id)
        
            logger.info(f"📊 Found {len(panel_telegram_ids)} users in panel")
        
            from app.database.crud.subscription import get_all_subscriptions
            from app.database.models import SubscriptionStatus
        
            page = 1
            limit = 100
        
            while True:
                subscriptions, total_count = await get_all_subscriptions(db, page, limit)
                
                if not subscriptions:
                    break
            
                for subscription in subscriptions:
                    try:
                        stats["checked"] += 1
                        user = subscription.user
                    
                        if subscription.status == SubscriptionStatus.DISABLED.value:
                            continue
                    
                        if user.telegram_id not in panel_telegram_ids:
                            logger.info(f"🗑️ FULL deactivation of subscription for user {user.telegram_id} (not in panel)")
                            
                            cleanup_success = await self.force_cleanup_user_data(db, user)
                            
                            if cleanup_success:
                                stats["deactivated"] += 1
                            else:
                                stats["errors"] += 1
                        
                    except Exception as sub_error:
                        logger.error(f"❌ Error processing subscription {subscription.id}: {sub_error}")
                        stats["errors"] += 1
            
                page += 1
                if len(subscriptions) < limit:
                    break
        
            logger.info(f"🧹 Enhanced cleanup completed: checked {stats['checked']}, deactivated {stats['deactivated']}, errors {stats['errors']}")
            return stats
        
        except Exception as e:
            logger.error(f"❌ Critical error during enhanced subscription cleanup: {e}")
            return {"deactivated": 0, "errors": 1, "checked": 0}


    async def sync_subscription_statuses(self, db: AsyncSession) -> Dict[str, int]:
        try:
            stats = {"updated": 0, "errors": 0, "checked": 0}
        
            logger.info("🔄 Starting subscription status synchronization...")
        
            async with self.get_api_client() as api:
                panel_users_data = await api._make_request('GET', '/api/users')
                panel_users = panel_users_data['response']['users']
        
            panel_users_dict = {}
            for panel_user in panel_users:
                telegram_id = panel_user.get('telegramId')
                if telegram_id:
                    panel_users_dict[telegram_id] = panel_user
        
            logger.info(f"📊 Found {len(panel_users_dict)} users in panel for synchronization")
        
            from app.database.crud.subscription import get_all_subscriptions
            from app.database.models import SubscriptionStatus
        
            page = 1
            limit = 100
        
            while True:
                subscriptions, total_count = await get_all_subscriptions(db, page, limit)
            
                if not subscriptions:
                    break
            
                for subscription in subscriptions:
                    try:
                        stats["checked"] += 1
                        user = subscription.user
                    
                        panel_user = panel_users_dict.get(user.telegram_id)
                    
                        if panel_user:
                            await self._update_subscription_from_panel_data(db, user, panel_user)
                            stats["updated"] += 1
                        else:
                            if subscription.status != SubscriptionStatus.DISABLED.value:
                                logger.info(f"🗑️ Deactivating subscription for user {user.telegram_id} (not in panel)")
                            
                                from app.database.crud.subscription import deactivate_subscription
                                await deactivate_subscription(db, subscription)
                                stats["updated"] += 1
                        
                    except Exception as sub_error:
                        logger.error(f"❌ Error synchronizing subscription {subscription.id}: {sub_error}")
                        stats["errors"] += 1
            
                page += 1
                if len(subscriptions) < limit:
                    break
        
            logger.info(f"🔄 Status synchronization completed: checked {stats['checked']}, updated {stats['updated']}, errors {stats['errors']}")
            return stats
        
        except Exception as e:
            logger.error(f"❌ Critical error during status synchronization: {e}")
            return {"updated": 0, "errors": 1, "checked": 0}


    async def validate_and_fix_subscriptions(self, db: AsyncSession) -> Dict[str, int]:
        try:
            stats = {"fixed": 0, "errors": 0, "checked": 0, "issues_found": 0}
        
            logger.info("🔍 Starting subscription validation...")
            
            from app.database.crud.subscription import get_all_subscriptions
            from app.database.models import SubscriptionStatus
        
            page = 1
            limit = 100
        
            while True:
                subscriptions, total_count = await get_all_subscriptions(db, page, limit)
            
                if not subscriptions:
                    break
            
                for subscription in subscriptions:
                    try:
                        stats["checked"] += 1
                        user = subscription.user
                        issues_fixed = 0
                    
                        current_time = self._now_utc()
                        if subscription.end_date <= current_time and subscription.status == SubscriptionStatus.ACTIVE.value:
                            logger.info(f"🔧 Fixing expired subscription status for {user.telegram_id}")
                            subscription.status = SubscriptionStatus.EXPIRED.value
                            issues_fixed += 1
                
                        if not subscription.remnawave_short_uuid and user.remnawave_uuid:
                            try:
                                async with self.get_api_client() as api:
                                    rw_user = await api.get_user_by_uuid(user.remnawave_uuid)
                                    if rw_user:
                                        subscription.remnawave_short_uuid = rw_user.short_uuid
                                        subscription.subscription_url = rw_user.subscription_url
                                        subscription.subscription_crypto_link = rw_user.happ_crypto_link
                                        logger.info(f"🔧 Restored Remnawave data for {user.telegram_id}")
                                        issues_fixed += 1
                            except Exception as rw_error:
                                logger.warning(f"⚠️ Failed to get Remnawave data for {user.telegram_id}: {rw_error}")
                    
                        if subscription.traffic_limit_gb < 0:
                            subscription.traffic_limit_gb = 0
                            logger.info(f"🔧 Fixed invalid traffic limit for {user.telegram_id}")
                            issues_fixed += 1
                    
                        if subscription.traffic_used_gb < 0:
                            subscription.traffic_used_gb = 0.0
                            logger.info(f"🔧 Fixed invalid traffic usage for {user.telegram_id}")
                            issues_fixed += 1
                    
                        if subscription.device_limit <= 0:
                            subscription.device_limit = 1
                            logger.info(f"🔧 Fixed device limit for {user.telegram_id}")
                            issues_fixed += 1
                    
                        if subscription.connected_squads is None:
                            subscription.connected_squads = []
                            logger.info(f"🔧 Initialized squad list for {user.telegram_id}")
                            issues_fixed += 1
                    
                        if issues_fixed > 0:
                            stats["issues_found"] += issues_fixed
                            stats["fixed"] += 1
                            await db.commit()
                        
                    except Exception as sub_error:
                        logger.error(f"❌ Error validating subscription {subscription.id}: {sub_error}")
                        stats["errors"] += 1
                        await db.rollback()
            
                page += 1
                if len(subscriptions) < limit:
                    break
        
            logger.info(f"🔍 Validation completed: checked {stats['checked']}, fixed subscriptions {stats['fixed']}, issues found {stats['issues_found']}, errors {stats['errors']}")
            return stats
        
        except Exception as e:
            logger.error(f"❌ Critical validation error: {e}")
            return {"fixed": 0, "errors": 1, "checked": 0, "issues_found": 0}


    async def get_sync_recommendations(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            recommendations = {
                "should_sync": False,
                "sync_type": "none",
                "reasons": [],
                "priority": "low",
                "estimated_time": "1-2 minutes"
            }
        
            from app.database.crud.user import get_users_list
            bot_users = await get_users_list(db, offset=0, limit=10000)
        
            users_without_uuid = sum(1 for user in bot_users if not user.remnawave_uuid and user.subscription)
        
            from app.database.crud.subscription import get_expired_subscriptions
            expired_subscriptions = await get_expired_subscriptions(db)
            active_expired = sum(1 for sub in expired_subscriptions if sub.status == "active")
        
            if users_without_uuid > 10:
                recommendations["should_sync"] = True
                recommendations["sync_type"] = "all"
                recommendations["priority"] = "high"
                recommendations["reasons"].append(f"Found {users_without_uuid} users without Remnawave connection")
                recommendations["estimated_time"] = "3-5 minutes"
        
            if active_expired > 5:
                recommendations["should_sync"] = True
                if recommendations["sync_type"] == "none":
                    recommendations["sync_type"] = "update_only"
                recommendations["priority"] = "medium" if recommendations["priority"] == "low" else recommendations["priority"]
                recommendations["reasons"].append(f"Found {active_expired} active subscriptions with expired dates")
        
            if not recommendations["should_sync"]:
                recommendations["sync_type"] = "update_only"
                recommendations["reasons"].append("Regular data synchronization recommended")
                recommendations["estimated_time"] = "1-2 minutes"
        
            return recommendations
        
        except Exception as e:
            logger.error(f"❌ Error getting recommendations: {e}")
            return {
                "should_sync": True,
                "sync_type": "all",
                "reasons": ["Analysis error - full synchronization recommended"],
                "priority": "medium",
                "estimated_time": "3-5 minutes"
            }

    async def monitor_panel_status(self, bot) -> Dict[str, Any]:
        try:
            from app.utils.cache import cache
            previous_status = await cache.get("remnawave_panel_status") or "unknown"
                
            status_result = await self.check_panel_health()
            current_status = status_result.get("status", "offline")
                
            if current_status != previous_status and previous_status != "unknown":
                await self._send_status_change_notification(
                    bot, 
                    previous_status, 
                    current_status, 
                    status_result
                )
                
            await cache.set("remnawave_panel_status", current_status, expire=300)
                
            return status_result
                
        except Exception as e:
            logger.error(f"Error monitoring Remnawave panel status: {e}")
            return {"status": "error", "error": str(e)}
        

        
    async def _send_status_change_notification(
        self, 
        bot, 
        old_status: str, 
        new_status: str, 
        status_data: Dict[str, Any]
    ):
        try:
            from app.services.admin_notification_service import AdminNotificationService
                
            notification_service = AdminNotificationService(bot)
                
            details = {
                "api_url": status_data.get("api_url"),
                "response_time": status_data.get("response_time"),
                "last_check": status_data.get("last_check"),
                "users_online": status_data.get("users_online"),
                "nodes_online": status_data.get("nodes_online"),
                "total_nodes": status_data.get("total_nodes"),
                "old_status": old_status
            }
                
            if new_status == "offline":
                details["error"] = status_data.get("api_error")
            elif new_status == "degraded":
                issues = []
                if status_data.get("response_time", 0) > 10:
                    issues.append(f"Slow API response ({status_data.get('response_time')}s)")
                if status_data.get("nodes_health") == "unhealthy":
                    issues.append(f"Node issues ({status_data.get('nodes_online')}/{status_data.get('total_nodes')} online)")
                details["issues"] = issues
                
            await notification_service.send_remnawave_panel_status_notification(
                new_status, 
                details
            )
                
            logger.info(f"Sent notification about panel status change: {old_status} -> {new_status}")
                
        except Exception as e:
            logger.error(f"Error sending status change notification: {e}")
        

        
    async def send_manual_status_notification(self, bot, status: str, message: str = ""):
        try:
            from app.services.admin_notification_service import AdminNotificationService
                
            notification_service = AdminNotificationService(bot)
                
            details = {
                "api_url": settings.REMNAWAVE_API_URL,
                "last_check": datetime.utcnow(),
                "manual_message": message
            }
                
            if status == "maintenance":
                details["maintenance_reason"] = message or "Scheduled maintenance"
                
            await notification_service.send_remnawave_panel_status_notification(status, details)
                
            logger.info(f"Sent manual panel status notification: {status}")
            return True
                
        except Exception as e:
            logger.error(f"Error sending manual notification: {e}")
            return False

    async def get_panel_status_summary(self) -> Dict[str, Any]:
        try:
            status_data = await self.check_panel_health()
                
            status_descriptions = {
                "online": "🟢 Panel is working normally",
                "offline": "🔴 Panel is unavailable",
                "degraded": "🟡 Panel is working with issues",
                "maintenance": "🔧 Panel is under maintenance"
            }
                
            status = status_data.get("status", "offline")
                
            summary = {
                "status": status,
                "description": status_descriptions.get(status, "❓ Status unknown"),
                "response_time": status_data.get("response_time", 0),
                "api_available": status_data.get("api_available", False),
                "nodes_status": f"{status_data.get('nodes_online', 0)}/{status_data.get('total_nodes', 0)} nodes online",
                "users_online": status_data.get("users_online", 0),
                "last_check": status_data.get("last_check"),
                "has_issues": status in ["offline", "degraded"]
            }
                
            if status == "offline":
                summary["recommendation"] = "Check server connection and panel availability"
            elif status == "degraded":
                summary["recommendation"] = "Recommended to check node status and server performance"
            else:
                summary["recommendation"] = "All systems working normally"
                
            return summary
                
        except Exception as e:
            logger.error(f"Error getting panel status summary: {e}")
            return {
                "status": "error",
                "description": "❌ Status check error",
                "response_time": 0,
                "api_available": False,
                "nodes_status": "unknown",
                "users_online": 0,
                "last_check": datetime.utcnow(),
                "has_issues": True,
                "recommendation": "Contact system administrator",
                "error": str(e)
            }
        
    async def check_panel_health(self) -> Dict[str, Any]:
        attempts = settings.get_maintenance_retry_attempts()
        attempts = max(1, attempts)

        last_result: Optional[Dict[str, Any]] = None
        last_error: Optional[Exception] = None

        for attempt in range(1, attempts + 1):
            try:
                start_time = datetime.utcnow()

                async with self.get_api_client() as api:
                    try:
                        system_stats = await api.get_system_stats()
                        api_available = True
                        api_error = None
                    except Exception as e:
                        api_available = False
                        api_error = str(e)
                        system_stats = {}

                    try:
                        nodes = await api.get_all_nodes()
                        nodes_online = sum(
                            1 for node in nodes if node.is_connected and node.is_node_online
                        )
                        total_nodes = len(nodes)
                        nodes_health = "healthy" if nodes_online > 0 else "unhealthy"
                    except Exception:
                        nodes_online = 0
                        total_nodes = 0
                        nodes_health = "unknown"

                    end_time = datetime.utcnow()
                    response_time = (end_time - start_time).total_seconds()

                    if not api_available:
                        status = "offline"
                    elif response_time > 10:
                        status = "degraded"
                    elif nodes_health == "unhealthy":
                        status = "degraded"
                    else:
                        status = "online"

                    result = {
                        "status": status,
                        "api_available": api_available,
                        "api_error": api_error,
                        "response_time": round(response_time, 2),
                        "nodes_online": nodes_online,
                        "total_nodes": total_nodes,
                        "nodes_health": nodes_health,
                        "users_online": system_stats.get('onlineStats', {}).get('onlineNow', 0),
                        "total_users": system_stats.get('users', {}).get('totalUsers', 0),
                        "last_check": end_time,
                        "api_url": settings.REMNAWAVE_API_URL,
                        "attempts_used": attempt,
                    }

                if result["api_available"]:
                    if attempt > 1:
                        logger.info("Remnawave panel responded on attempt %s", attempt)
                    return result

                last_result = result

                if attempt < attempts:
                    logger.warning(
                        "Remnawave panel unavailable (attempt %s/%s): %s",
                        attempt,
                        attempts,
                        result.get("api_error") or "unknown error",
                    )
                    await asyncio.sleep(1)

            except Exception as error:
                last_error = error
                if attempt < attempts:
                    logger.warning(
                        "Error checking panel health (attempt %s/%s): %s",
                        attempt,
                        attempts,
                        error,
                    )
                    await asyncio.sleep(1)
                    continue

                logger.error(f"Error checking panel health: {error}")

        if last_result is not None:
            return last_result

        error_message = str(last_error) if last_error else "Unknown error"
        return {
            "status": "offline",
            "api_available": False,
            "api_error": error_message,
            "response_time": 0,
            "nodes_online": 0,
            "total_nodes": 0,
            "nodes_health": "unknown",
            "last_check": datetime.utcnow(),
            "api_url": settings.REMNAWAVE_API_URL,
            "attempts_used": attempts,
        }
        

