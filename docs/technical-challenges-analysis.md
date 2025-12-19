# Technical Challenges Analysis - Feature Flags & Tenant Management

**Version:** 1.0  
**Date:** 2025-12-14  
**Status:** Analysis Complete  
**Author:** Development Team

---

## 📋 Executive Summary

این مستند چالش‌های فنی پیاده‌سازی سیستم Feature Flags و Tenant Management را بررسی می‌کند و راهکارهای عملی برای هر چالش ارائه می‌دهد.

---

## 🔴 Critical Challenges

### 1. Bot Initialization & Lifecycle Management

#### Challenge
- **Dynamic Bot Creation**: ایجاد و حذف botها در runtime
- **Resource Management**: مدیریت memory و connections برای هر bot
- **Graceful Shutdown**: خاموش کردن صحیح botها بدون از دست دادن messages
- **Error Recovery**: بازیابی از خطا در initialization

#### Current Implementation
```python
# app/bot.py
active_bots: Dict[int, Bot] = {}
active_dispatchers: Dict[int, Dispatcher] = {}
polling_tasks: Dict[int, asyncio.Task] = {}
```

#### Technical Issues

**1.1. Memory Leaks**
- هر bot یک Dispatcher و Bot instance دارد
- Redis connections برای FSM storage
- Middleware instances per bot
- Handler registrations

**Solution:**
```python
# app/services/bot_lifecycle_manager.py

class BotLifecycleManager:
    """Manages bot lifecycle with proper cleanup"""
    
    async def create_bot(
        self,
        bot_config: BotModel,
        db: AsyncSession
    ) -> tuple[Bot, Dispatcher]:
        """Create and initialize bot with proper resource management"""
        try:
            # 1. Initialize bot
            bot, dp = await setup_bot(bot_config)
            
            # 2. Register in global registry
            active_bots[bot_config.id] = bot
            active_dispatchers[bot_config.id] = dp
            
            # 3. Start polling/webhook
            if settings.get_bot_run_mode() in {"polling", "both"}:
                task = await start_bot_polling(bot_config.id, bot, dp)
                polling_tasks[bot_config.id] = task
            
            # 4. Setup webhook if needed
            if settings.get_bot_run_mode() in {"webhook", "both"}:
                await setup_bot_webhook(bot_config.id, bot)
            
            # 5. Register cleanup handler
            asyncio.create_task(self._monitor_bot_health(bot_config.id))
            
            return bot, dp
            
        except Exception as e:
            logger.error(f"Failed to create bot {bot_config.id}: {e}")
            await self.cleanup_bot(bot_config.id)
            raise
    
    async def cleanup_bot(self, bot_id: int) -> None:
        """Properly cleanup bot resources"""
        try:
            # 1. Stop polling
            if bot_id in polling_tasks:
                task = polling_tasks[bot_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                del polling_tasks[bot_id]
            
            # 2. Close dispatcher
            if bot_id in active_dispatchers:
                dp = active_dispatchers[bot_id]
                await dp.fsm.storage.close()
                del active_dispatchers[bot_id]
            
            # 3. Close bot session
            if bot_id in active_bots:
                bot = active_bots[bot_id]
                await bot.session.close()
                del active_bots[bot_id]
            
            logger.info(f"✅ Bot {bot_id} cleaned up")
            
        except Exception as e:
            logger.error(f"Error cleaning up bot {bot_id}: {e}")
    
    async def _monitor_bot_health(self, bot_id: int) -> None:
        """Monitor bot health and auto-recover"""
        while bot_id in active_bots:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                bot = active_bots[bot_id]
                me = await bot.get_me()
                
                if not me:
                    logger.warning(f"Bot {bot_id} health check failed")
                    # Trigger recovery
                    await self._recover_bot(bot_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error for bot {bot_id}: {e}")
    
    async def _recover_bot(self, bot_id: int) -> None:
        """Recover bot from failure"""
        from app.database.crud.bot import get_bot_by_id
        
        async with AsyncSessionLocal() as db:
            bot_config = await get_bot_by_id(db, bot_id)
            if bot_config and bot_config.is_active:
                await self.cleanup_bot(bot_id)
                await self.create_bot(bot_config, db)
```

**1.2. Concurrent Initialization**
- اگر چند bot همزمان ایجاد شوند، race condition ممکن است

**Solution:**
```python
import asyncio
from asyncio import Lock

_bot_creation_locks: Dict[int, Lock] = {}
_global_bot_lock = Lock()

async def create_bot_safely(
    bot_config: BotModel,
    db: AsyncSession
) -> tuple[Bot, Dispatcher]:
    """Thread-safe bot creation"""
    async with _global_bot_lock:
        if bot_config.id in active_bots:
            return active_bots[bot_config.id], active_dispatchers[bot_config.id]
        
        if bot_config.id not in _bot_creation_locks:
            _bot_creation_locks[bot_config.id] = Lock()
        
        async with _bot_creation_locks[bot_config.id]:
            # Double-check after acquiring lock
            if bot_config.id in active_bots:
                return active_bots[bot_config.id], active_dispatchers[bot_config.id]
            
            return await lifecycle_manager.create_bot(bot_config, db)
```

---

### 2. Database Query Filtering & Performance

#### Challenge
- **Query Isolation**: همه queries باید `bot_id` filter داشته باشند
- **Performance**: اضافه کردن `WHERE bot_id = ?` به همه queries
- **Index Optimization**: indexes برای `bot_id` در همه tables
- **Query Caching**: cache queries per tenant

#### Current State
```python
# Many queries don't have bot_id filter yet
async def get_user_by_telegram_id(
    db: AsyncSession,
    telegram_id: int
) -> Optional[User]:
    # Missing bot_id filter!
    return await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    ).scalar_one_or_none()
```

#### Technical Issues

**2.1. Missing bot_id Filters**
- خطر data leakage بین tenants
- Queries باید refactor شوند

**Solution:**
```python
# app/database/crud/base.py

class BaseCRUD:
    """Base CRUD with automatic bot_id filtering"""
    
    @staticmethod
    def ensure_bot_id_filter(
        query: Select,
        bot_id: Optional[int],
        model: Type[Base]
    ) -> Select:
        """Automatically add bot_id filter if column exists"""
        if bot_id is None:
            return query
        
        if hasattr(model, 'bot_id'):
            return query.where(model.bot_id == bot_id)
        
        return query

# Usage
async def get_user_by_telegram_id(
    db: AsyncSession,
    telegram_id: int,
    bot_id: Optional[int] = None
) -> Optional[User]:
    query = select(User).where(User.telegram_id == telegram_id)
    query = BaseCRUD.ensure_bot_id_filter(query, bot_id, User)
    return await db.execute(query).scalar_one_or_none()
```

**2.2. Index Strategy**
```sql
-- Critical indexes for multi-tenant performance
CREATE INDEX CONCURRENTLY idx_users_bot_telegram 
    ON users(bot_id, telegram_id) 
    WHERE bot_id IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_subscriptions_bot_user 
    ON subscriptions(bot_id, user_id) 
    WHERE bot_id IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_transactions_bot_user 
    ON transactions(bot_id, user_id, created_at) 
    WHERE bot_id IS NOT NULL;

-- Partial indexes for active records
CREATE INDEX CONCURRENTLY idx_subscriptions_bot_active 
    ON subscriptions(bot_id, status, end_date) 
    WHERE bot_id IS NOT NULL AND status = 'active';
```

**2.3. Query Performance Monitoring**
```python
# app/middlewares/query_monitor.py

class QueryMonitorMiddleware:
    """Monitor and log slow queries"""
    
    async def __call__(self, request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        
        if duration > 1.0:  # Log queries > 1 second
            logger.warning(
                f"Slow query detected: {duration:.2f}s | "
                f"Path: {request.url.path} | "
                f"Bot ID: {request.state.bot_id if hasattr(request.state, 'bot_id') else 'N/A'}"
            )
        
        return response
```

---

### 3. Config Cloning & Feature Flag Application

#### Challenge
- **Atomic Operations**: clone configs و apply features باید atomic باشد
- **Rollback Strategy**: اگر clone fail شود، rollback
- **Config Validation**: validate cloned configs
- **Feature Flag Caching**: cache feature flags per bot

#### Technical Issues

**3.1. Atomic Config Cloning**
```python
# app/services/config_cloner.py

async def clone_master_config_to_tenant(
    db: AsyncSession,
    tenant_bot_id: int,
    master_bot_id: int,
    plan_tier_id: int
) -> Dict[str, Any]:
    """Atomic config cloning with rollback"""
    
    # Use transaction
    async with db.begin():
        try:
            # 1. Clone configs
            cloned_configs = []
            master_configs = await get_bot_configurations(db, master_bot_id)
            
            for config in master_configs:
                if config.config_key in MASTER_ONLY_CONFIGS:
                    continue
                
                cloned = await set_bot_configuration(
                    db,
                    tenant_bot_id,
                    config.config_key,
                    config.config_value
                )
                cloned_configs.append(cloned)
            
            # 2. Apply feature flags
            await apply_plan_features_to_tenant(
                db,
                tenant_bot_id,
                plan_tier_id
            )
            
            # 3. Validate
            await validate_tenant_config(db, tenant_bot_id)
            
            return {
                'cloned': len(cloned_configs),
                'success': True
            }
            
        except Exception as e:
            # Transaction will auto-rollback
            logger.error(f"Config cloning failed: {e}")
            raise
```

**3.2. Feature Flag Caching**
```python
# app/services/feature_flag_cache.py

from functools import lru_cache
from typing import Dict, Set
import asyncio

class FeatureFlagCache:
    """Cache feature flags per bot"""
    
    def __init__(self):
        self._cache: Dict[int, Dict[str, bool]] = {}
        self._cache_ttl: Dict[int, float] = {}
        self._lock = asyncio.Lock()
        self._ttl = 300  # 5 minutes
    
    async def get_features(
        self,
        db: AsyncSession,
        bot_id: int
    ) -> Dict[str, bool]:
        """Get cached features or fetch from DB"""
        async with self._lock:
            # Check cache
            if bot_id in self._cache:
                if time.time() - self._cache_ttl[bot_id] < self._ttl:
                    return self._cache[bot_id]
            
            # Fetch from DB
            flags = await get_all_feature_flags(db, bot_id, enabled_only=True)
            features = {flag.feature_key: flag.enabled for flag in flags}
            
            # Update cache
            self._cache[bot_id] = features
            self._cache_ttl[bot_id] = time.time()
            
            return features
    
    async def invalidate(self, bot_id: int) -> None:
        """Invalidate cache for bot"""
        async with self._lock:
            if bot_id in self._cache:
                del self._cache[bot_id]
                del self._cache_ttl[bot_id]
```

---

### 4. Payment Processing & Isolation

#### Challenge
- **Payment Gateway Isolation**: هر tenant gateway credentials خودش را دارد
- **Transaction Isolation**: transactions باید per-tenant باشند
- **Webhook Routing**: webhooks باید به bot صحیح route شوند
- **Payment Card Rotation**: rotation strategy per tenant

#### Technical Issues

**4.1. Payment Gateway Configuration**
```python
# app/services/payment_gateway_manager.py

class PaymentGatewayManager:
    """Manage payment gateway configs per tenant"""
    
    async def get_gateway_config(
        self,
        db: AsyncSession,
        bot_id: int,
        gateway: str
    ) -> Optional[Dict]:
        """Get gateway config for tenant"""
        # Check feature flag first
        is_enabled = await is_feature_enabled(db, bot_id, gateway)
        if not is_enabled:
            return None
        
        # Get config from bot_configurations
        config = await get_bot_configuration(
            db,
            bot_id,
            f"{gateway.upper()}_ENABLED"
        )
        
        if not config:
            return None
        
        # Build config dict
        return {
            'enabled': True,
            'shop_id': await get_bot_configuration(db, bot_id, f"{gateway.upper()}_SHOP_ID"),
            'secret_key': await get_bot_configuration(db, bot_id, f"{gateway.upper()}_SECRET_KEY"),
            # ... other configs
        }
```

**4.2. Webhook Routing**
```python
# app/webserver/telegram.py

def create_multi_bot_webhook_router() -> APIRouter:
    """Router that routes webhooks to correct bot"""
    
    router = APIRouter()
    
    @router.post("/webhook/{bot_id}")
    async def webhook_handler(
        request: Request,
        bot_id: int,
        update: dict
    ):
        """Route webhook to correct bot"""
        # Get bot from registry
        if bot_id not in active_bots:
            logger.error(f"Bot {bot_id} not found in registry")
            return Response(status_code=404)
        
        bot = active_bots[bot_id]
        dp = active_dispatchers[bot_id]
        
        # Process update
        telegram_update = types.Update(**update)
        await dp.feed_update(bot, telegram_update)
        
        return Response(status_code=200)
```

---

### 5. State Management (FSM) per Bot

#### Challenge
- **FSM Isolation**: هر bot FSM storage خودش را دارد
- **State Key Collision**: جلوگیری از collision بین bots
- **Redis Key Namespace**: namespace برای Redis keys

#### Technical Issues

**5.1. FSM Key Namespacing**
```python
# app/bot.py

class NamespacedRedisStorage(RedisStorage):
    """Redis storage with bot_id namespace"""
    
    def __init__(self, redis_client, bot_id: int, *args, **kwargs):
        self.bot_id = bot_id
        self.key_prefix = f"fsm:bot_{bot_id}:"
        super().__init__(redis_client, *args, **kwargs)
    
    def _make_key(self, key: str) -> str:
        """Add bot_id prefix to key"""
        return f"{self.key_prefix}{key}"

# Usage in setup_bot
storage = NamespacedRedisStorage(redis_client, bot_id=bot_config.id)
```

---

### 6. Middleware & Context Propagation

#### Challenge
- **Bot Context**: bot_id باید در همه middlewareها در دسترس باشد
- **Request Context**: bot_id در FastAPI requests
- **Handler Context**: bot_id در aiogram handlers

#### Technical Issues

**6.1. Bot Context Middleware**
```python
# app/middlewares/bot_context.py (Enhanced)

class BotContextMiddleware(BaseMiddleware):
    """Enhanced bot context middleware"""
    
    async def __call__(
        self,
        handler: Callable,
        event: Union[types.Message, types.CallbackQuery],
        data: Dict[str, Any]
    ) -> Any:
        # Determine bot_id from event
        bot_id = await self._get_bot_id_from_event(event, data)
        
        if not bot_id:
            # Fallback: try to get from bot token
            bot_id = await self._get_bot_id_from_token(event.bot.token)
        
        if not bot_id:
            logger.error("Could not determine bot_id")
            return await handler(event, data)
        
        # Set in context
        data['bot_id'] = bot_id
        data['bot'] = active_bots.get(bot_id)
        data['dispatcher'] = active_dispatchers.get(bot_id)
        
        return await handler(event, data)
    
    async def _get_bot_id_from_event(
        self,
        event: Union[types.Message, types.CallbackQuery],
        data: Dict
    ) -> Optional[int]:
        """Extract bot_id from event"""
        # Check if bot is in registry
        for bot_id, bot in active_bots.items():
            if bot.token == event.bot.token:
                return bot_id
        return None
```

---

### 7. Error Handling & Logging

#### Challenge
- **Error Isolation**: errors یک tenant نباید دیگران را تحت تاثیر قرار دهد
- **Logging Context**: bot_id در همه logs
- **Error Reporting**: report errors per tenant

#### Technical Issues

**7.1. Contextual Logging**
```python
# app/utils/logger.py

import logging
from contextvars import ContextVar

bot_id_context: ContextVar[Optional[int]] = ContextVar('bot_id', default=None)

class BotContextFilter(logging.Filter):
    """Add bot_id to log records"""
    
    def filter(self, record):
        bot_id = bot_id_context.get()
        record.bot_id = bot_id if bot_id else 'master'
        return True

# Setup logger
logger = logging.getLogger(__name__)
logger.addFilter(BotContextFilter())

# Usage
def log_with_bot_context(bot_id: int):
    bot_id_context.set(bot_id)
    logger.info("Message with bot context")
```

---

### 8. Scalability & Resource Management

#### Challenge
- **Connection Pooling**: database connections per tenant
- **Memory Limits**: limit memory per bot
- **Rate Limiting**: rate limits per tenant
- **Horizontal Scaling**: scaling across multiple servers

#### Technical Issues

**8.1. Resource Limits**
```python
# app/services/resource_manager.py

class ResourceManager:
    """Manage resources per tenant"""
    
    MAX_BOTS_PER_SERVER = 100
    MAX_MEMORY_PER_BOT_MB = 50
    
    async def can_create_bot(self) -> bool:
        """Check if we can create another bot"""
        if len(active_bots) >= self.MAX_BOTS_PER_SERVER:
            return False
        
        # Check memory
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        
        if memory_mb > (self.MAX_BOTS_PER_SERVER * self.MAX_MEMORY_PER_BOT_MB):
            return False
        
        return True
```

---

### 9. Migration & Backward Compatibility

#### Challenge
- **Data Migration**: migrate existing data to multi-tenant
- **Backward Compatibility**: support single-tenant mode
- **Zero Downtime**: migration بدون downtime

#### Technical Issues

**9.1. Gradual Migration**
```python
# migrations/002_migrate_to_multi_tenant.py

async def migrate_to_multi_tenant(db: AsyncSession):
    """Gradual migration to multi-tenant"""
    
    # 1. Create master bot if not exists
    master_bot = await get_master_bot(db)
    if not master_bot:
        master_bot = await create_master_bot(db)
    
    # 2. Assign all existing data to master bot
    await assign_existing_data_to_master(db, master_bot.id)
    
    # 3. Add bot_id to tables that don't have it
    await add_bot_id_to_tables(db)
    
    # 4. Create indexes
    await create_multi_tenant_indexes(db)
```

---

### 10. Testing & Quality Assurance

#### Challenge
- **Unit Tests**: test per-tenant logic
- **Integration Tests**: test multi-tenant scenarios
- **Load Testing**: test با تعداد زیادی tenant
- **Security Testing**: test data isolation

#### Technical Issues

**10.1. Test Fixtures**
```python
# tests/fixtures/tenant_fixtures.py

@pytest.fixture
async def tenant_bot(db):
    """Create test tenant bot"""
    bot = await create_bot(
        db,
        name="Test Bot",
        telegram_bot_token="test_token",
        is_master=False
    )
    yield bot
    await cleanup_bot(db, bot.id)

@pytest.fixture
async def master_bot(db):
    """Create test master bot"""
    bot = await create_bot(
        db,
        name="Master Bot",
        telegram_bot_token="master_token",
        is_master=True
    )
    yield bot
```

---

## 📊 Performance Benchmarks

### Expected Performance

| Metric | Single Tenant | 10 Tenants | 100 Tenants |
|--------|--------------|------------|-------------|
| Bot Initialization | 2s | 20s | 200s |
| Query Latency | 50ms | 55ms | 70ms |
| Memory Usage | 200MB | 500MB | 2GB |
| Database Connections | 5 | 10 | 20 |

### Optimization Strategies

1. **Lazy Initialization**: Initialize bots on-demand
2. **Connection Pooling**: Shared connection pool
3. **Query Batching**: Batch similar queries
4. **Caching**: Cache frequently accessed data

---

## ✅ Mitigation Strategies

### Priority 1 (Critical)
1. ✅ Bot lifecycle management
2. ✅ Database query filtering
3. ✅ Feature flag caching
4. ✅ Error isolation

### Priority 2 (High)
1. ⚠️ Payment gateway isolation
2. ⚠️ Webhook routing
3. ⚠️ FSM namespacing
4. ⚠️ Resource limits

### Priority 3 (Medium)
1. 📋 Migration strategy
2. 📋 Testing framework
3. 📋 Monitoring & alerting
4. 📋 Documentation

---

## 🔧 Implementation Checklist

- [ ] Bot lifecycle manager
- [ ] Database query filtering base class
- [ ] Feature flag cache
- [ ] Payment gateway manager
- [ ] Webhook routing
- [ ] FSM namespacing
- [ ] Resource manager
- [ ] Migration scripts
- [ ] Test fixtures
- [ ] Monitoring dashboard

---

**End of Document**
