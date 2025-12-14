"""
Tenant Feature Flag Service with caching support.

This service provides a high-level interface for managing feature flags
per tenant (bot) with Redis caching for performance.
"""
import logging
from typing import Optional, Dict, Any
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.bot_feature_flag import (
    is_feature_enabled as crud_is_feature_enabled,
    get_feature_config as crud_get_feature_config,
    set_feature_flag as crud_set_feature_flag,
    get_all_feature_flags,
)
from app.utils.cache import cache, cache_key

logger = logging.getLogger(__name__)


class TenantFeatureService:
    """
    Service for managing tenant feature flags with caching.
    
    Features:
    - Redis caching with configurable TTL
    - Automatic cache invalidation on updates
    - Fallback to database if cache unavailable
    """
    
    CACHE_TTL = 300  # 5 minutes default TTL
    CACHE_PREFIX = "feature_flag"
    
    @staticmethod
    def _get_cache_key(bot_id: int, feature_key: str) -> str:
        """Generate cache key for feature flag."""
        return cache_key(TenantFeatureService.CACHE_PREFIX, bot_id, feature_key)
    
    @staticmethod
    async def is_feature_enabled(
        db: AsyncSession,
        bot_id: int,
        feature_key: str,
        use_cache: bool = True
    ) -> bool:
        """
        Check if a feature is enabled for a tenant.
        
        Args:
            db: Database session
            bot_id: Bot/tenant ID
            feature_key: Feature key to check
            use_cache: Whether to use cache (default: True)
            
        Returns:
            True if feature is enabled, False otherwise
        """
        cache_key_str = TenantFeatureService._get_cache_key(bot_id, feature_key)
        
        if use_cache:
            try:
                cached = await cache.get(cache_key_str)
                if cached is not None:
                    logger.debug(
                        f"✅ Cache hit for feature flag: {feature_key} (bot_id={bot_id})"
                    )
                    return bool(cached)
            except Exception as e:
                logger.warning(
                    f"⚠️ Cache read error for {cache_key_str}: {e}, falling back to DB"
                )
        
        # Cache miss or cache disabled - fetch from database
        enabled = await crud_is_feature_enabled(db, bot_id, feature_key)
        
        # Cache the result
        if use_cache:
            try:
                await cache.set(
                    cache_key_str,
                    enabled,
                    expire=TenantFeatureService.CACHE_TTL
                )
                logger.debug(
                    f"💾 Cached feature flag: {feature_key} (bot_id={bot_id}) = {enabled}"
                )
            except Exception as e:
                logger.warning(
                    f"⚠️ Cache write error for {cache_key_str}: {e}"
                )
        
        return enabled
    
    @staticmethod
    async def get_feature_config(
        db: AsyncSession,
        bot_id: int,
        feature_key: str,
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get feature configuration (JSONB config field).
        
        Args:
            db: Database session
            bot_id: Bot/tenant ID
            feature_key: Feature key
            use_cache: Whether to use cache (default: True)
            
        Returns:
            Feature config dict or None if not found
        """
        cache_key_str = cache_key(
            TenantFeatureService.CACHE_PREFIX,
            bot_id,
            feature_key,
            "config"
        )
        
        if use_cache:
            try:
                cached = await cache.get(cache_key_str)
                if cached is not None:
                    logger.debug(
                        f"✅ Cache hit for feature config: {feature_key} (bot_id={bot_id})"
                    )
                    return cached if isinstance(cached, dict) else None
            except Exception as e:
                logger.warning(
                    f"⚠️ Cache read error for {cache_key_str}: {e}, falling back to DB"
                )
        
        # Cache miss or cache disabled - fetch from database
        config = await crud_get_feature_config(db, bot_id, feature_key)
        
        # Cache the result
        if use_cache and config:
            try:
                await cache.set(
                    cache_key_str,
                    config,
                    expire=TenantFeatureService.CACHE_TTL
                )
                logger.debug(
                    f"💾 Cached feature config: {feature_key} (bot_id={bot_id})"
                )
            except Exception as e:
                logger.warning(
                    f"⚠️ Cache write error for {cache_key_str}: {e}"
                )
        
        return config
    
    @staticmethod
    async def set_feature(
        db: AsyncSession,
        bot_id: int,
        feature_key: str,
        enabled: bool,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Set feature flag and clear cache.
        
        Args:
            db: Database session
            bot_id: Bot/tenant ID
            feature_key: Feature key
            enabled: Whether feature is enabled
            config: Optional feature configuration
        """
        # Update database
        await crud_set_feature_flag(db, bot_id, feature_key, enabled, config)
        await db.commit()
        
        # Invalidate cache
        try:
            cache_key_str = TenantFeatureService._get_cache_key(bot_id, feature_key)
            config_cache_key = cache_key(
                TenantFeatureService.CACHE_PREFIX,
                bot_id,
                feature_key,
                "config"
            )
            
            await cache.delete(cache_key_str)
            await cache.delete(config_cache_key)
            
            logger.info(
                f"🔄 Feature flag updated and cache invalidated: {feature_key} "
                f"(bot_id={bot_id}, enabled={enabled})"
            )
        except Exception as e:
            logger.warning(
                f"⚠️ Cache invalidation error for {feature_key} (bot_id={bot_id}): {e}"
            )
    
    @staticmethod
    async def get_all_features(
        db: AsyncSession,
        bot_id: int,
        enabled_only: bool = False
    ) -> Dict[str, bool]:
        """
        Get all feature flags for a tenant.
        
        Args:
            db: Database session
            bot_id: Bot/tenant ID
            enabled_only: If True, only return enabled features
            
        Returns:
            Dictionary mapping feature_key -> enabled status
        """
        flags = await get_all_feature_flags(db, bot_id, enabled_only=enabled_only)
        return {flag.feature_key: flag.enabled for flag in flags}
    
    @staticmethod
    async def invalidate_cache(
        bot_id: int,
        feature_key: Optional[str] = None
    ) -> None:
        """
        Manually invalidate feature flag cache.
        
        Args:
            bot_id: Bot/tenant ID
            feature_key: Specific feature key to invalidate, or None to invalidate all
        """
        try:
            if feature_key:
                # Invalidate specific feature
                cache_key_str = TenantFeatureService._get_cache_key(bot_id, feature_key)
                config_cache_key = cache_key(
                    TenantFeatureService.CACHE_PREFIX,
                    bot_id,
                    feature_key,
                    "config"
                )
                await cache.delete(cache_key_str)
                await cache.delete(config_cache_key)
                logger.info(
                    f"🗑️ Cache invalidated for feature: {feature_key} (bot_id={bot_id})"
                )
            else:
                # Invalidate all features for this bot
                # Note: This is a simple implementation. For production, you might want
                # to use Redis pattern matching (SCAN) to find all keys
                logger.warning(
                    f"⚠️ Bulk cache invalidation not fully implemented for bot_id={bot_id}. "
                    f"Consider invalidating specific features."
                )
        except Exception as e:
            logger.error(
                f"❌ Error invalidating cache for bot_id={bot_id}, feature_key={feature_key}: {e}"
            )
