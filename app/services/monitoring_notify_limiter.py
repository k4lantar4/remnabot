from datetime import UTC, datetime

import structlog

from app.config import settings
from app.utils.cache import cache


logger = structlog.get_logger(__name__)

_MONITORING_USER_DAY_TTL_SECONDS = 86400


class MonitoringNotifyLimiter:
    """Per-user daily cap for monitoring Telegram notifications (Redis + in-memory fallback)."""

    def __init__(self) -> None:
        self._memory_counts: dict[int, int] = {}
        self._memory_window_start: dict[int, datetime] = {}

    @staticmethod
    def _redis_key(user_id: int) -> str:
        return f'monitoring_user_day:{user_id}'

    def _max_per_day(self) -> int:
        return settings.MONITORING_NOTIFY_MAX_PER_USER_DAY

    def _reset_memory_window_if_expired(self, user_id: int) -> None:
        window_start = self._memory_window_start.get(user_id)
        if window_start is None:
            return
        elapsed = (datetime.now(UTC) - window_start).total_seconds()
        if elapsed >= _MONITORING_USER_DAY_TTL_SECONDS:
            self._memory_counts[user_id] = 0
            self._memory_window_start[user_id] = datetime.now(UTC)

    async def _get_count(self, user_id: int) -> int:
        self._reset_memory_window_if_expired(user_id)

        key = self._redis_key(user_id)
        try:
            value = await cache.get(key)
            if value is not None:
                return int(value)
        except Exception as redis_err:
            logger.warning(
                'monitoring notify limiter: Redis read failed, using in-memory fallback',
                user_id=user_id,
                error=redis_err,
            )

        return self._memory_counts.get(user_id, 0)

    async def can_send_to_user(self, user_id: int) -> bool:
        max_per_day = self._max_per_day()
        if max_per_day <= 0:
            return True
        return await self._get_count(user_id) < max_per_day

    async def record_send(self, user_id: int) -> None:
        now = datetime.now(UTC)
        self._reset_memory_window_if_expired(user_id)

        if user_id not in self._memory_window_start:
            self._memory_window_start[user_id] = now

        new_count = self._memory_counts.get(user_id, 0) + 1
        self._memory_counts[user_id] = new_count

        key = self._redis_key(user_id)
        try:
            await cache.set(key, new_count, expire=_MONITORING_USER_DAY_TTL_SECONDS)
        except Exception as redis_err:
            logger.warning(
                'monitoring notify limiter: Redis write failed, in-memory fallback active',
                user_id=user_id,
                error=redis_err,
            )
