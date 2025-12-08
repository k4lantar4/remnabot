import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass

from app.config import settings
from app.external.remnawave_api import RemnaWaveAPI, test_api_connection
from app.utils.cache import cache
from app.utils.timezone import format_local_datetime

logger = logging.getLogger(__name__)


@dataclass
class MaintenanceStatus:
    is_active: bool
    enabled_at: Optional[datetime] = None
    last_check: Optional[datetime] = None
    reason: Optional[str] = None
    auto_enabled: bool = False
    api_status: bool = True
    consecutive_failures: int = 0


class MaintenanceService:
    
    def __init__(self):
        self._status = MaintenanceStatus(is_active=False)
        self._check_task: Optional[asyncio.Task] = None
        self._is_checking = False
        self._max_consecutive_failures = 3
        self._bot = None 
        self._last_notification_sent = None 
        
    def set_bot(self, bot):
        self._bot = bot
        logger.info("Bot set for maintenance_service")
    
    @property
    def status(self) -> MaintenanceStatus:
        return self._status
    
    def is_maintenance_active(self) -> bool:
        return self._status.is_active
    
    def get_maintenance_message(self) -> str:
        if self._status.auto_enabled:
            last_check_display = format_local_datetime(
                self._status.last_check, "%H:%M:%S", "unknown"
            )
            return f"""
🔧 Maintenance in progress!

Service temporarily unavailable due to server connection issues.

⏰ We are working on restoration. Please try again in a few minutes.

🔄 Last check: {last_check_display}
"""
        else:
            return settings.get_maintenance_message()
    
    async def _send_admin_notification(self, message: str, alert_type: str = "info"):
        if not self._bot:
            logger.warning("Bot not set, notifications cannot be sent")
            return False
        
        try:
            from app.services.admin_notification_service import AdminNotificationService
            
            notification_service = AdminNotificationService(self._bot)
            
            if not notification_service._is_enabled():
                logger.debug("Admin notifications disabled")
                return False
            
            emoji_map = {
                "error": "🚨",
                "warning": "⚠️", 
                "success": "✅",
                "info": "ℹ️"
            }
            emoji = emoji_map.get(alert_type, "ℹ️")
            
            timestamp = format_local_datetime(
                datetime.utcnow(), "%d.%m.%Y %H:%M:%S %Z"
            )
            formatted_message = (
                f"{emoji} <b>MAINTENANCE</b>\n\n{message}\n\n⏰ <i>{timestamp}</i>"
            )
            
            return await notification_service._send_message(formatted_message)
            
        except Exception as e:
            logger.error(f"Error sending notification via AdminNotificationService: {e}")
            return False
    
    async def _notify_admins(self, message: str, alert_type: str = "info"):
        if not self._bot:
            logger.warning("Bot not set, notifications cannot be sent")
            return
        
        notification_sent = await self._send_admin_notification(message, alert_type)
        
        if notification_sent:
            logger.info("Notification successfully sent via AdminNotificationService")
            return
        
        logger.info("Sending notification directly to admins")
        
        cache_key = f"maintenance_notification_{alert_type}"
        if await cache.get(cache_key):
            return
        
        admin_ids = settings.get_admin_ids()
        if not admin_ids:
            logger.warning("Admin list is empty")
            return
        
        emoji_map = {
            "error": "🚨",
            "warning": "⚠️", 
            "success": "✅",
            "info": "ℹ️"
        }
        emoji = emoji_map.get(alert_type, "ℹ️")
        
        formatted_message = f"{emoji} <b>Maintenance Service</b>\n\n{message}"
        
        success_count = 0
        for admin_id in admin_ids:
            try:
                await self._bot.send_message(
                    chat_id=admin_id,
                    text=formatted_message,
                    parse_mode="HTML"
                )
                success_count += 1
                await asyncio.sleep(0.1) 
                
            except Exception as e:
                logger.error(f"Error sending notification to admin {admin_id}: {e}")
        
        if success_count > 0:
            logger.info(f"Notification sent to {success_count} admins")
            await cache.set(cache_key, True, expire=300)
        else:
            logger.error("Failed to send notifications to any admin")
    
    async def enable_maintenance(self, reason: Optional[str] = None, auto: bool = False) -> bool:
        try:
            if self._status.is_active:
                logger.warning("Maintenance mode already enabled")
                return True
            
            self._status.is_active = True
            self._status.enabled_at = datetime.utcnow()
            self._status.reason = reason or ("Auto-enabled" if auto else "Enabled by admin")
            self._status.auto_enabled = auto
            
            await self._save_status_to_cache()
            
            enabled_time = format_local_datetime(
                self._status.enabled_at, "%d.%m.%Y %H:%M:%S %Z"
            )
            notification_msg = f"""Maintenance mode ENABLED

📋 <b>Reason:</b> {self._status.reason}
🤖 <b>Automatic:</b> {'Yes' if auto else 'No'}
🕐 <b>Time:</b> {enabled_time}

Regular users temporarily cannot use the bot."""
            
            await self._notify_admins(notification_msg, "warning" if auto else "info")
            
            logger.warning(f"🔧 Maintenance mode ENABLED. Reason: {self._status.reason}")
            return True
            
        except Exception as e:
            logger.error(f"Error enabling maintenance mode: {e}")
            return False
    
    async def disable_maintenance(self) -> bool:
        try:
            if not self._status.is_active:
                logger.info("Maintenance mode already disabled")
                return True
            
            was_auto = self._status.auto_enabled
            duration = None
            if self._status.enabled_at:
                duration = datetime.utcnow() - self._status.enabled_at
            
            self._status.is_active = False
            self._status.enabled_at = None
            self._status.reason = None
            self._status.auto_enabled = False
            self._status.consecutive_failures = 0
            
            await self._save_status_to_cache()
            
            duration_str = ""
            if duration:
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                if hours > 0:
                    duration_str = f"\n⏱️ <b>Duration:</b> {hours}h {minutes}min"
                else:
                    duration_str = f"\n⏱️ <b>Duration:</b> {minutes}min"
            
            notification_time = format_local_datetime(
                datetime.utcnow(), "%d.%m.%Y %H:%M:%S %Z"
            )
            notification_msg = f"""Maintenance mode DISABLED

🤖 <b>Automatic:</b> {'Yes' if was_auto else 'No'}
🕐 <b>Time:</b> {notification_time}
{duration_str}

Service is available for users again."""
            
            await self._notify_admins(notification_msg, "success")
            
            logger.info("✅ Maintenance mode DISABLED")
            return True
            
        except Exception as e:
            logger.error(f"Error disabling maintenance mode: {e}")
            return False
    
    async def start_monitoring(self) -> bool:
        try:
            if self._check_task and not self._check_task.done():
                logger.warning("Monitoring already running")
                return True
            
            await self._load_status_from_cache()
            
            self._check_task = asyncio.create_task(self._monitoring_loop())
            logger.info(
                "🔄 Started Remnawave API monitoring (interval: %ss, attempts: %s)",
                settings.get_maintenance_check_interval(),
                settings.get_maintenance_retry_attempts(),
            )

            await self._notify_admins(
                f"""Maintenance monitoring started

🔄 <b>Check interval:</b> {settings.get_maintenance_check_interval()} seconds
🤖 <b>Auto-enable:</b> {'Enabled' if settings.is_maintenance_auto_enable() else 'Disabled'}
🎯 <b>Error threshold:</b> {self._max_consecutive_failures}
🔁 <b>Retry attempts:</b> {settings.get_maintenance_retry_attempts()}

System will monitor API availability.""",
                "info",
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")
            return False
    
    async def stop_monitoring(self) -> bool:
        try:
            if self._check_task and not self._check_task.done():
                self._check_task.cancel()
                try:
                    await self._check_task
                except asyncio.CancelledError:
                    pass
            
            await self._notify_admins("Maintenance monitoring stopped", "info")
            logger.info("ℹ️ API monitoring stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping monitoring: {e}")
            return False
    
    async def check_api_status(self) -> bool:
        try:
            if self._is_checking:
                return self._status.api_status

            self._is_checking = True
            self._status.last_check = datetime.utcnow()

            auth_params = settings.get_remnawave_auth_params()
            base_url = (auth_params.get("base_url") or "").strip()
            api_key = (auth_params.get("api_key") or "").strip()
            secret_key = (auth_params.get("secret_key") or "").strip() or None
            username = (auth_params.get("username") or "").strip() or None
            password = (auth_params.get("password") or "").strip() or None

            if not base_url:
                logger.error("REMNAWAVE_API_URL not configured, skipping API check")
                self._status.api_status = False
                self._status.consecutive_failures = 0
                return False

            if not api_key:
                logger.error("REMNAWAVE_API_KEY not configured, skipping API check")
                self._status.api_status = False
                self._status.consecutive_failures = 0
                return False

            api = RemnaWaveAPI(
                base_url=base_url,
                api_key=api_key,
                secret_key=secret_key,
                username=username,
                password=password
            )

            attempts = settings.get_maintenance_retry_attempts()

            async with api:
                for attempt in range(1, attempts + 1):
                    is_connected = await test_api_connection(api)

                    if is_connected:
                        if attempt > 1:
                            logger.info(
                                "Remnawave API responded on attempt %s", attempt
                            )

                        if not self._status.api_status:
                            recovery_time = format_local_datetime(
                                self._status.last_check, "%H:%M:%S %Z"
                            )
                            await self._notify_admins(
                                f"""Remnawave API restored!

✅ <b>Status:</b> Available
🕐 <b>Recovery time:</b> {recovery_time}
🔄 <b>Failed attempts:</b> {self._status.consecutive_failures}

API is responding to requests again.""",
                                "success",
                            )

                        self._status.api_status = True
                        self._status.consecutive_failures = 0

                        if self._status.is_active and self._status.auto_enabled:
                            await self.disable_maintenance()
                            logger.info("✅ API restored, maintenance mode auto-disabled")

                        return True

                    if attempt < attempts:
                        logger.warning(
                            "Remnawave API unavailable (attempt %s/%s)",
                            attempt,
                            attempts,
                        )
                        await asyncio.sleep(1)

                was_available = self._status.api_status
                self._status.api_status = False
                self._status.consecutive_failures += 1

                if was_available:
                    detection_time = format_local_datetime(
                        self._status.last_check, "%H:%M:%S %Z"
                    )
                    await self._notify_admins(
                        f"""Remnawave API unavailable!

❌ <b>Status:</b> Unavailable
🕐 <b>Detection time:</b> {detection_time}
🔄 <b>Attempt:</b> {self._status.consecutive_failures}

Started series of failed API checks.""",
                        "error",
                    )

                if (
                    self._status.consecutive_failures >= self._max_consecutive_failures
                    and not self._status.is_active
                    and settings.is_maintenance_auto_enable()
                ):

                    await self.enable_maintenance(
                        reason=(
                            f"Auto-enabled after {self._status.consecutive_failures} "
                            "failed API checks"
                        ),
                        auto=True
                    )

                return False

        except Exception as e:
            logger.error(f"API check error: {e}")
            
            if self._status.api_status:
                error_time = format_local_datetime(datetime.utcnow(), "%H:%M:%S %Z")
                await self._notify_admins(
                    f"""Error checking Remnawave API

❌ <b>Error:</b> {str(e)}
🕐 <b>Time:</b> {error_time}

Failed to check API availability.""",
                    "error",
                )
            
            self._status.api_status = False
            self._status.consecutive_failures += 1
            return False
        finally:
            self._is_checking = False
            await self._save_status_to_cache()
    
    async def _monitoring_loop(self):
        while True:
            try:
                await self.check_api_status()
                await asyncio.sleep(settings.get_maintenance_check_interval())
                
            except asyncio.CancelledError:
                logger.info("Monitoring cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30) 
    
    async def _save_status_to_cache(self):
        try:
            status_data = {
                "is_active": self._status.is_active,
                "enabled_at": self._status.enabled_at.isoformat() if self._status.enabled_at else None,
                "reason": self._status.reason,
                "auto_enabled": self._status.auto_enabled,
                "consecutive_failures": self._status.consecutive_failures,
                "last_check": self._status.last_check.isoformat() if self._status.last_check else None
            }
            
            await cache.set("maintenance_status", status_data, expire=3600)
            
        except Exception as e:
            logger.error(f"Error saving status to cache: {e}")
    
    async def _load_status_from_cache(self):
        try:
            status_data = await cache.get("maintenance_status")
            if not status_data:
                return
            
            self._status.is_active = status_data.get("is_active", False)
            self._status.reason = status_data.get("reason")
            self._status.auto_enabled = status_data.get("auto_enabled", False)
            self._status.consecutive_failures = status_data.get("consecutive_failures", 0)
            
            if status_data.get("enabled_at"):
                self._status.enabled_at = datetime.fromisoformat(status_data["enabled_at"])
            
            if status_data.get("last_check"):
                self._status.last_check = datetime.fromisoformat(status_data["last_check"])
            
            logger.info(f"🔥 Maintenance status loaded from cache: active={self._status.is_active}")
            
        except Exception as e:
            logger.error(f"Error loading status from cache: {e}")
    
    def get_status_info(self) -> Dict[str, Any]:
        return {
            "is_active": self._status.is_active,
            "enabled_at": self._status.enabled_at,
            "last_check": self._status.last_check,
            "reason": self._status.reason,
            "auto_enabled": self._status.auto_enabled,
            "api_status": self._status.api_status,
            "consecutive_failures": self._status.consecutive_failures,
            "monitoring_active": self._check_task is not None and not self._check_task.done(),
            "monitoring_configured": settings.is_maintenance_monitoring_enabled(),
            "auto_enable_configured": settings.is_maintenance_auto_enable(),
            "check_interval": settings.get_maintenance_check_interval(),
            "bot_connected": self._bot is not None
        }
    
    async def force_api_check(self) -> Dict[str, Any]:
        start_time = datetime.utcnow()
        
        try:
            api_status = await self.check_api_status()
            end_time = datetime.utcnow()
            response_time = (end_time - start_time).total_seconds()
            
            return {
                "success": True,
                "api_available": api_status,
                "response_time": round(response_time, 2),
                "checked_at": end_time,
                "consecutive_failures": self._status.consecutive_failures
            }
            
        except Exception as e:
            end_time = datetime.utcnow()
            response_time = (end_time - start_time).total_seconds()
            
            return {
                "success": False,
                "api_available": False,
                "error": str(e),
                "response_time": round(response_time, 2),
                "checked_at": end_time,
                "consecutive_failures": self._status.consecutive_failures
            }
    
    async def send_remnawave_status_notification(self, status: str, details: str = "") -> bool:
        try:
            status_emojis = {
                "online": "🟢",
                "offline": "🔴", 
                "warning": "🟡",
                "error": "⚠️"
            }
            
            emoji = status_emojis.get(status, "ℹ️")
            
            message = f"""Remnawave panel status changed

{emoji} <b>Status:</b> {status.upper()}
🔗 <b>URL:</b> {settings.REMNAWAVE_API_URL}
{details}"""
            
            alert_type = "error" if status in ["offline", "error"] else "info"
            await self._notify_admins(message, alert_type)
            
            logger.info(f"Sent Remnawave status notification: {status}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending Remnawave status notification: {e}")
            return False


maintenance_service = MaintenanceService()
