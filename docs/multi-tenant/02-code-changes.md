# Code Changes Required

**Version:** 1.0  
**Date:** 2025-12-12  
**Status:** Ready for Implementation

---

## Overview

This document describes all code changes needed for multi-tenant migration, organized by file and phase.

---

## Phase 1: Database Models

### File: `app/database/models.py`

**Location:** After line 25 (after `Base = declarative_base()`)

**Add New Models:**

See [Database Schema](./01-database-schema.md) for complete SQL definitions.

**Key Models to Add:**
1. `Bot` - Tenant bot instances
2. `BotFeatureFlag` - Feature flags per tenant
3. `BotConfiguration` - Tenant configurations
4. `TenantPaymentCard` - Payment cards with rotation
5. `BotPlan` - Tenant-specific plans
6. `CardToCardPayment` - Card-to-card payments
7. `ZarinpalPayment` - Zarinpal payments

**Modify Existing Models:**

All models that need `bot_id`:
- `User` - Add `bot_id`, update unique constraint
- `Subscription` - Add `bot_id`
- `Transaction` - Add `bot_id`
- `Ticket` - Add `bot_id`
- `PromoCode` - Add `bot_id`, update unique constraint
- `PromoGroup` - Add `bot_id`, update unique constraint
- All payment models - Add `bot_id`

---

## Phase 2: Bot Context Middleware

### File: `app/middlewares/bot_context.py` (NEW)

**Create new file:**

```python
import logging
from typing import Callable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import AsyncSessionLocal
from app.database.crud.bot import get_bot_by_token

logger = logging.getLogger(__name__)


class BotContextMiddleware(BaseMiddleware):
    """Middleware to inject bot context into handlers."""
    
    async def __call__(
        self,
        handler: Callable,
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        bot = event.bot if hasattr(event, 'bot') else None
        
        if not bot:
            logger.warning("Bot instance not found in event")
            return await handler(event, data)
        
        async with AsyncSessionLocal() as db:
            bot_config = await get_bot_by_token(db, bot.token)
            
            if not bot_config:
                logger.error(f"Bot not found in database for token: {bot.token[:10]}...")
                return await handler(event, data)
            
            data['bot_id'] = bot_config.id
            data['bot_config'] = bot_config
        
        return await handler(event, data)
```

**Register in `app/bot.py` (After line 112):**

```python
from app.middlewares.bot_context import BotContextMiddleware

bot_context_middleware = BotContextMiddleware()
dp.message.middleware(bot_context_middleware)
dp.callback_query.middleware(bot_context_middleware)
dp.pre_checkout_query.middleware(bot_context_middleware)
```

---

## Phase 3: CRUD Operations

### File: `app/database/crud/bot.py` (NEW)

**Key Functions:**
- `generate_api_token()` - Generate secure API token
- `hash_api_token(token)` - Hash token for storage
- `get_bot_by_id(db, bot_id)` - Get bot by ID
- `get_bot_by_token(db, token)` - Get bot by Telegram token
- `get_bot_by_api_token(db, api_token)` - Get bot by API token
- `get_master_bot(db)` - Get master bot
- `get_active_bots(db)` - Get all active bots
- `create_bot(db, name, token, ...)` - Create new bot

### File: `app/database/crud/bot_feature_flag.py` (NEW)

**Key Functions:**
- `get_feature_flag(db, bot_id, feature_key)` - Get feature flag
- `is_feature_enabled(db, bot_id, feature_key)` - Check if enabled
- `get_feature_config(db, bot_id, feature_key)` - Get config
- `set_feature_flag(db, bot_id, feature_key, enabled, config)` - Set flag
- `get_all_feature_flags(db, bot_id)` - Get all flags

---

## Phase 4: Update Existing CRUD

### File: `app/database/crud/user.py`

**Changes Required:**

1. **Line ~37: `get_user_by_id`**
   ```python
   # BEFORE:
   async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
       result = await db.execute(select(User).where(User.id == user_id))
   
   # AFTER:
   async def get_user_by_id(
       db: AsyncSession, 
       user_id: int,
       bot_id: int  # NEW
   ) -> Optional[User]:
       result = await db.execute(
           select(User).where(User.id == user_id, User.bot_id == bot_id)  # CHANGED
       )
   ```

2. **Line ~57: `get_user_by_telegram_id`**
   - Add `bot_id` parameter
   - Add filter: `.where(User.telegram_id == telegram_id, User.bot_id == bot_id)`

3. **Line ~77: `get_user_by_username`**
   - Add `bot_id` parameter
   - Add filter

4. **Line ~582: `get_users_list`**
   - Add `bot_id` parameter
   - Add filter: `.where(User.bot_id == bot_id)`

**Similar changes for:**
- `subscription.py`
- `transaction.py`
- `ticket.py`
- `promocode.py`
- `promo_group.py`
- All payment CRUD files

---

## Phase 5: Update Handlers

### File: `app/handlers/start.py`

**Changes:**

```python
# BEFORE:
async def handle_start(message: types.Message, db_user: Optional[User] = None):
    if not db_user:
        db_user = await create_user(...)

# AFTER:
async def handle_start(
    message: types.Message, 
    db_user: Optional[User] = None,
    bot_id: int = None  # From middleware
):
    if not db_user:
        db_user = await create_user(..., bot_id=bot_id)  # Pass bot_id
```

**Similar changes for all handlers that:**
- Create users
- Query users
- Create subscriptions
- Create transactions
- Handle payments

---

## Phase 6: Multi-Bot Support

### File: `app/bot.py`

**Changes:**

**BEFORE (Line ~80):**
```python
async def setup_bot() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.BOT_TOKEN, ...)
    dp = Dispatcher(storage=storage)
    return bot, dp
```

**AFTER:**
```python
from typing import Dict
from aiogram import Bot as AiogramBot, Dispatcher

# Global registry
active_bots: Dict[int, AiogramBot] = {}
active_dispatchers: Dict[int, Dispatcher] = {}


async def setup_bot(bot_config: Bot) -> tuple[AiogramBot, Dispatcher]:
    """Setup a single bot instance."""
    bot = AiogramBot(
        token=bot_config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    # ... setup dispatcher, middlewares, handlers ...
    return bot, dp


async def initialize_all_bots():
    """Initialize all active bots from database."""
    from app.database.database import AsyncSessionLocal
    from app.database.crud.bot import get_active_bots
    
    async with AsyncSessionLocal() as db:
        bots = await get_active_bots(db)
        
        for bot_config in bots:
            try:
                bot, dp = await setup_bot(bot_config)
                active_bots[bot_config.id] = bot
                active_dispatchers[bot_config.id] = dp
            except Exception as e:
                logger.error(f"Failed to initialize bot {bot_config.id}: {e}")
```

### File: `main.py`

**Changes:**

**BEFORE (Line ~49):**
```python
async def main():
    bot, dp = await setup_bot()
    # ... start polling ...
```

**AFTER:**
```python
async def main():
    from app.bot import initialize_all_bots, active_bots, active_dispatchers
    
    await initialize_all_bots()
    
    if not active_bots:
        logger.error("No active bots found!")
        return
    
    # Start polling for all bots
    import asyncio
    tasks = []
    for bot_id, bot in active_bots.items():
        dp = active_dispatchers[bot_id]
        tasks.append(dp.start_polling(bot))
    
    await asyncio.gather(*tasks)
```

---

## Phase 7: Feature Flag Service

### File: `app/services/tenant_feature_service.py` (NEW)

**Key Methods:**
- `is_feature_enabled(db, bot_id, feature_key, use_cache=True)` - Check feature
- `get_feature_config(db, bot_id, feature_key)` - Get config
- `set_feature(db, bot_id, feature_key, enabled, config)` - Set feature
- `get_all_features(db, bot_id)` - Get all features

**Usage:**
```python
# BEFORE:
if settings.TELEGRAM_STARS_ENABLED:
    # ... handle stars payment ...

# AFTER:
from app.services.tenant_feature_service import TenantFeatureService

bot_id = data.get('bot_id')
if await TenantFeatureService.is_feature_enabled(db, bot_id, 'telegram_stars'):
    # ... handle stars payment ...
```

---

## Summary of Changes

### New Files (7)
1. `app/middlewares/bot_context.py`
2. `app/database/crud/bot.py`
3. `app/database/crud/bot_feature_flag.py`
4. `app/database/crud/bot_configuration.py`
5. `app/database/crud/tenant_payment_card.py`
6. `app/services/tenant_feature_service.py`
7. `app/external/zarinpal.py` (for Zarinpal integration)

### Modified Files (50+)
- `app/database/models.py` - Add 7 new models, modify 47+ existing
- `app/bot.py` - Multi-bot support
- `main.py` - Initialize all bots
- All CRUD files - Add `bot_id` parameter
- All handlers - Use `bot_id` from middleware
- All services - Check feature flags

---

## Related Documents

- [Database Schema](./01-database-schema.md)
- [Feature Flags](./03-feature-flags.md)
- [Implementation Tasks](./04-implementation-tasks.md)
- [Workflow Guide](./07-workflow-guide.md)
