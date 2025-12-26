import json
import logging
from typing import Optional, Dict, Any
from datetime import timedelta

import redis.asyncio as redis

from app.config import settings

logger = logging.getLogger(__name__)

class UserCartService:
    """
    Service for working with the user's cart via Redis.
    """
    
    def __init__(self):
        self.redis_client = None
        self._setup_redis()
    
    def _setup_redis(self):
        """Initialize Redis client."""
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL)
        except Exception as e:
            logger.error("Redis connection error: %s", e)
            raise
    
    async def save_user_cart(self, user_id: int, cart_data: Dict[str, Any], ttl: int = 3600) -> bool:
        """
        Save the user's cart to Redis.

        Args:
            user_id: User ID.
            cart_data: Cart data (subscription parameters).
            ttl: Key lifetime in seconds (default 1 hour).

        Returns:
            bool: Whether the cart was saved successfully.
        """
        try:
            key = f"user_cart:{user_id}"
            json_data = json.dumps(cart_data, ensure_ascii=False)
            await self.redis_client.setex(key, ttl, json_data)
            logger.info("User %s cart saved to Redis", user_id)
            return True
        except Exception as e:
            logger.error("Failed to save cart for user %s: %s", user_id, e)
            return False
    
    async def get_user_cart(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the user's cart from Redis.

        Args:
            user_id: User ID.

        Returns:
            dict: Cart data or None.
        """
        try:
            key = f"user_cart:{user_id}"
            json_data = await self.redis_client.get(key)
            if json_data:
                cart_data = json.loads(json_data)
                logger.info("User %s cart loaded from Redis", user_id)
                return cart_data
            return None
        except Exception as e:
            logger.error("Failed to fetch cart for user %s: %s", user_id, e)
            return None
    
    async def delete_user_cart(self, user_id: int) -> bool:
        """
        Delete the user's cart from Redis.

        Args:
            user_id: User ID.

        Returns:
            bool: Whether the cart was removed.
        """
        try:
            key = f"user_cart:{user_id}"
            result = await self.redis_client.delete(key)
            if result:
                logger.info("User %s cart removed from Redis", user_id)
            return bool(result)
        except Exception as e:
            logger.error("Failed to delete cart for user %s: %s", user_id, e)
            return False
    
    async def has_user_cart(self, user_id: int) -> bool:
        """
        Check whether the user has a saved cart.

        Args:
            user_id: User ID.

        Returns:
            bool: True if the cart exists.
        """
        try:
            key = f"user_cart:{user_id}"
            exists = await self.redis_client.exists(key)
            return bool(exists)
        except Exception as e:
            logger.error("Failed to check cart existence for user %s: %s", user_id, e)
            return False

# Global service instance
user_cart_service = UserCartService()