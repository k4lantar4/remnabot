# گزارش مرحله‌ای پیاده‌سازی Multi-Tenant - برنچ feat/payments

**تاریخ:** 2025-12-15  
**برنچ:** feat/payments  
**Base:** main  
**وضعیت:** در حال پیاده‌سازی (68% تکمیل)

---

## 📊 خلاصه اجرایی

### آمار تغییرات
- **64 فایل تغییر یافته**
- **19,442 خط اضافه شده**
- **335 خط حذف شده**
- **7 فایل جدید**
- **57 فایل اصلاح شده**

### وضعیت کلی
- ✅ **Database Schema:** 85% - تکمیل شده
- ✅ **Models & CRUD:** 70% - نیاز به تکمیل
- ✅ **Middleware:** 75% - درست پیاده شده
- ⚠️ **Handlers:** 55% - نیاز به کار زیاد
- ✅ **Multi-Bot Support:** 80% - خوب
- ⚠️ **Feature Flags:** 70% - استفاده محدود
- ⚠️ **Security:** 60% - مشکلات امنیتی

**امتیاز کلی: 68%**

---

## 🏗️ Phase 1: Foundation (Database & Models)

### Increment 1.1: Database Schema - New Tables

#### قبل از تغییرات
```sql
-- هیچ جدول multi-tenant وجود نداشت
-- تمام داده‌ها در جداول single-tenant بودند
```

#### بعد از تغییرات
```sql
-- 7 جدول جدید ایجاد شد:
CREATE TABLE bots (...);                    -- مدیریت bot instances
CREATE TABLE bot_feature_flags (...);       -- Feature flags per tenant
CREATE TABLE bot_configurations (...);      -- Configurations per tenant
CREATE TABLE tenant_payment_cards (...);    -- Payment cards with rotation
CREATE TABLE bot_plans (...);               -- Subscription plans per tenant
CREATE TABLE card_to_card_payments (...);   -- Card-to-card payment tracking
CREATE TABLE zarinpal_payments (...);      -- Zarinpal payment tracking
```

**وضعیت:** ✅ **تکمیل شده**

**جزئیات:**
- ✅ تمام جداول با indexes مناسب
- ✅ Foreign keys با CASCADE delete
- ✅ Unique constraints برای multi-tenant
- ✅ Migration script موجود: `migrations/001_create_multi_tenant_tables.sql`

**پیشنهادات دیباگ:**
```sql
-- 1. بررسی وجود تمام جداول
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('bots', 'bot_feature_flags', 'bot_configurations', 
                   'tenant_payment_cards', 'bot_plans', 
                   'card_to_card_payments', 'zarinpal_payments');
-- باید 7 ردیف برگرداند

-- 2. بررسی indexes
SELECT tablename, indexname FROM pg_indexes 
WHERE tablename IN ('bots', 'bot_feature_flags')
ORDER BY tablename, indexname;

-- 3. تست Foreign Key
INSERT INTO bot_feature_flags (bot_id, feature_key, enabled) 
VALUES (99999, 'test', true);
-- باید خطا بدهد: foreign key constraint violation
```

---

### Increment 1.2: Database Models - New Models

#### قبل از تغییرات
```python
# app/database/models.py
Base = declarative_base()

# فقط مدل‌های single-tenant وجود داشت
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True)  # ❌ بدون bot_id
    # ...
```

#### بعد از تغییرات
```python
# app/database/models.py
Base = declarative_base()

# ============================================================================
# Multi-Tenant Models (Increment 1.2)
# ============================================================================

class Bot(Base):
    __tablename__ = "bots"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    telegram_bot_token = Column(String(255), unique=True, nullable=False)
    api_token = Column(String(255), unique=True, nullable=False)
    api_token_hash = Column(String(128), nullable=False)
    is_master = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    # ... relationships
    users = relationship("User", back_populates="bot")
    feature_flags = relationship("BotFeatureFlag", back_populates="bot")

class BotFeatureFlag(Base):
    __tablename__ = "bot_feature_flags"
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), primary_key=True)
    feature_key = Column(String(100), primary_key=True)
    enabled = Column(Boolean, default=False, nullable=False)
    config = Column(JSONB, default={}, nullable=False)
    bot = relationship("Bot", back_populates="feature_flags")

# ... 5 مدل دیگر (BotConfiguration, TenantPaymentCard, BotPlan, 
# CardToCardPayment, ZarinpalPayment)

# ============================================================================
# Modified Existing Models
# ============================================================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, nullable=False)  # ✅ unique constraint حذف شد
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=True)  # ✅ اضافه شد
    # ...
    bot = relationship("Bot", back_populates="users")
    # ✅ Unique constraint جدید: UniqueConstraint('telegram_id', 'bot_id')
```

**وضعیت:** ✅ **تکمیل شده (90%)**

**جزئیات:**
- ✅ 7 مدل جدید اضافه شده
- ✅ Relationships درست تعریف شده
- ✅ User model به‌روزرسانی شده
- ⚠️ `bot_id` در User هنوز `nullable=True` است (باید بعد از migration تغییر کند)

**پیشنهادات دیباگ:**
```python
# 1. تست import مدل‌ها
from app.database.models import Bot, BotFeatureFlag, User
# باید بدون خطا import شود

# 2. تست ایجاد instance
from app.database.database import AsyncSessionLocal
async with AsyncSessionLocal() as db:
    bot = Bot(name="Test Bot", telegram_bot_token="test", 
              api_token="test", api_token_hash="test")
    db.add(bot)
    await db.commit()
    # باید بدون خطا کار کند

# 3. تست relationship
user = User(telegram_id=123456, bot_id=bot.id)
db.add(user)
await db.commit()
assert user.bot.id == bot.id  # باید True باشد
```

**پیشنهادات تکمیلی:**
```python
# بعد از migration داده‌ها، bot_id را required کنید:
# در migration script:
ALTER TABLE users ALTER COLUMN bot_id SET NOT NULL;

# در model:
bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), 
                nullable=False)  # ✅ NOT NULL
```

---

### Increment 1.3: Bot CRUD Operations

#### قبل از تغییرات
```python
# هیچ CRUD برای bots وجود نداشت
# فقط settings.BOT_TOKEN استفاده می‌شد
```

#### بعد از تغییرات
```python
# app/database/crud/bot.py (NEW FILE)
import secrets
import hashlib

def generate_api_token() -> str:
    """Generate a secure API token."""
    return secrets.token_urlsafe(32)

def hash_api_token(token: str) -> str:
    """Hash API token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()

async def get_bot_by_id(db: AsyncSession, bot_id: int) -> Optional[Bot]:
    """Get bot by ID."""
    result = await db.execute(select(Bot).where(Bot.id == bot_id))
    return result.scalar_one_or_none()

async def get_bot_by_token(db: AsyncSession, telegram_token: str) -> Optional[Bot]:
    """Get bot by Telegram bot token."""
    result = await db.execute(
        select(Bot).where(Bot.telegram_bot_token == telegram_token)
    )
    return result.scalar_one_or_none()

async def get_bot_by_api_token(db: AsyncSession, api_token: str) -> Optional[Bot]:
    """Get bot by API token (hashed)."""
    token_hash = hash_api_token(api_token)
    result = await db.execute(
        select(Bot).where(Bot.api_token_hash == token_hash)
    )
    return result.scalar_one_or_none()

async def get_master_bot(db: AsyncSession) -> Optional[Bot]:
    """Get master bot."""
    result = await db.execute(
        select(Bot).where(Bot.is_master == True, Bot.is_active == True)
    )
    return result.scalar_one_or_none()

async def get_active_bots(db: AsyncSession) -> List[Bot]:
    """Get all active bots."""
    result = await db.execute(
        select(Bot).where(Bot.is_active == True)
    )
    return list(result.scalars().all())

async def create_bot(db: AsyncSession, name: str, telegram_bot_token: str, 
                     is_master: bool = False, **kwargs) -> tuple[Bot, str]:
    """Create a new bot. Returns: (Bot instance, plain API token)"""
    api_token = generate_api_token()
    api_token_hash = hash_api_token(api_token)
    
    bot = Bot(
        name=name,
        telegram_bot_token=telegram_bot_token,
        api_token=api_token,  # Store temporarily
        api_token_hash=api_token_hash,
        is_master=is_master,
        **kwargs
    )
    db.add(bot)
    await db.commit()
    await db.refresh(bot)
    return bot, api_token
```

**وضعیت:** ✅ **تکمیل شده**

**پیشنهادات دیباگ:**
```python
# 1. تست ایجاد bot
from app.database.crud.bot import create_bot
async with AsyncSessionLocal() as db:
    bot, api_token = await create_bot(
        db, 
        name="Test Bot",
        telegram_bot_token="123456:ABC-DEF"
    )
    assert bot.id is not None
    assert api_token is not None
    print(f"✅ Bot created: {bot.id}, API token: {api_token}")

# 2. تست جستجو با token
from app.database.crud.bot import get_bot_by_token
bot = await get_bot_by_token(db, "123456:ABC-DEF")
assert bot.name == "Test Bot"

# 3. تست API token hash
from app.database.crud.bot import get_bot_by_api_token, hash_api_token
bot = await get_bot_by_api_token(db, api_token)
assert bot.id == bot.id
assert hash_api_token(api_token) == bot.api_token_hash
```

---

### Increment 1.4: Feature Flag CRUD

#### قبل از تغییرات
```python
# Feature flags در settings بودند:
# settings.TELEGRAM_STARS_ENABLED
# settings.YOOKASSA_ENABLED
# etc.
# همه global بودند - نمی‌شد per-tenant تنظیم کرد
```

#### بعد از تغییرات
```python
# app/database/crud/bot_feature_flag.py (NEW FILE)
async def get_feature_flag(db: AsyncSession, bot_id: int, 
                           feature_key: str) -> Optional[BotFeatureFlag]:
    """Get feature flag."""
    result = await db.execute(
        select(BotFeatureFlag).where(
            BotFeatureFlag.bot_id == bot_id,
            BotFeatureFlag.feature_key == feature_key
        )
    )
    return result.scalar_one_or_none()

async def is_feature_enabled(db: AsyncSession, bot_id: int, 
                            feature_key: str) -> bool:
    """Check if feature is enabled."""
    flag = await get_feature_flag(db, bot_id, feature_key)
    return flag.enabled if flag else False

async def set_feature_flag(db: AsyncSession, bot_id: int, feature_key: str,
                          enabled: bool, config: Optional[Dict] = None) -> BotFeatureFlag:
    """Set feature flag."""
    flag = await get_feature_flag(db, bot_id, feature_key)
    if flag:
        flag.enabled = enabled
        if config is not None:
            flag.config = config
        flag.updated_at = func.now()
    else:
        flag = BotFeatureFlag(
            bot_id=bot_id,
            feature_key=feature_key,
            enabled=enabled,
            config=config or {}
        )
        db.add(flag)
    await db.commit()
    await db.refresh(flag)
    return flag
```

**وضعیت:** ✅ **تکمیل شده**

**پیشنهادات دیباگ:**
```python
# 1. تست set/get feature flag
from app.database.crud.bot_feature_flag import set_feature_flag, is_feature_enabled
async with AsyncSessionLocal() as db:
    await set_feature_flag(db, bot_id=1, feature_key='telegram_stars', enabled=True)
    enabled = await is_feature_enabled(db, bot_id=1, feature_key='telegram_stars')
    assert enabled == True

# 2. تست config storage
await set_feature_flag(db, bot_id=1, feature_key='yookassa', 
                       enabled=True, config={'merchant_id': '123'})
flag = await get_feature_flag(db, bot_id=1, feature_key='yookassa')
assert flag.config['merchant_id'] == '123'
```

---

### Increment 1.5: Bot Context Middleware

#### قبل از تغییرات
```python
# هیچ middleware برای bot context وجود نداشت
# Handlers مستقیماً از settings.BOT_TOKEN استفاده می‌کردند
# bot_id در دسترس نبود
```

#### بعد از تغییرات
```python
# app/middlewares/bot_context.py (NEW FILE)
class BotContextMiddleware(BaseMiddleware):
    """Middleware to inject bot context (bot_id, bot instance) into handlers."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Get bot instance from event
        bot = getattr(event, 'bot', None)
        
        if not bot:
            logger.warning("Bot instance not found in event")
            return await handler(event, data)
        
        # Get bot token
        bot_token = getattr(bot, 'token', None)
        if not bot_token:
            logger.warning("Bot token not found in bot instance")
            return await handler(event, data)
        
        # Get bot from database
        async for db in get_db():
            try:
                bot_config = await get_bot_by_token(db, bot_token)
                
                if not bot_config:
                    logger.error(f"Bot not found in database for token: {bot_token[:10]}...")
                    break
                
                if not bot_config.is_active:
                    logger.warning(f"Bot {bot_config.id} ({bot_config.name}) is inactive")
                
                # Inject bot context
                data['bot_id'] = bot_config.id
                data['bot_config'] = bot_config
                
                logger.debug(f"✅ Bot context injected: bot_id={bot_config.id}, name={bot_config.name}")
                break
                
            except Exception as e:
                logger.error(f"Error in BotContextMiddleware: {e}", exc_info=True)
                break
        
        return await handler(event, data)

# app/bot.py - Registration
bot_context_middleware = BotContextMiddleware()
dp.message.middleware(bot_context_middleware)
dp.callback_query.middleware(bot_context_middleware)
dp.pre_checkout_query.middleware(bot_context_middleware)
```

**وضعیت:** ✅ **تکمیل شده (75%)**

**مشکلات:**
- ⚠️ اگر bot پیدا نشود، handler بدون `bot_id` اجرا می‌شود (ریسک امنیتی)
- ⚠️ باید validation قوی‌تر باشد

**پیشنهادات دیباگ:**
```python
# 1. تست middleware injection
# در handler:
async def test_handler(message: types.Message, bot_id: int):
    assert bot_id is not None
    print(f"✅ bot_id injected: {bot_id}")

# 2. تست error handling
# اگر bot token در database نباشد، باید log شود اما handler اجرا شود
# (برای backward compatibility در migration)

# 3. تست inactive bot
# اگر bot.is_active = False باشد، باید warning log شود
```

**پیشنهادات تکمیلی:**
```python
# بهبود middleware برای امنیت بیشتر:
class BotContextMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        # ... existing code ...
        
        if not bot_config:
            # ❌ بهتر است handler را block کنیم برای امنیت
            logger.error(f"Bot not found - blocking handler")
            if hasattr(event, 'answer'):
                await event.answer("Bot configuration error. Please contact admin.")
            return  # Block handler
        
        if not bot_config.is_active:
            logger.warning(f"Bot {bot_config.id} is inactive")
            if hasattr(event, 'answer'):
                await event.answer("This bot is currently inactive.")
            return  # Block handler
        
        # ... rest of code ...
```

---

## 🔄 Phase 2: Core Features (CRUD Updates)

### Increment 2.1: Update User CRUD

#### قبل از تغییرات
```python
# app/database/crud/user.py
async def get_user_by_telegram_id(
    db: AsyncSession, 
    telegram_id: int
) -> Optional[User]:
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()
    # ❌ بدون bot_id - می‌تواند user از هر bot را برگرداند
```

#### بعد از تغییرات
```python
# app/database/crud/user.py
async def get_user_by_telegram_id(
    db: AsyncSession, 
    telegram_id: int, 
    bot_id: Optional[int] = None  # ⚠️ هنوز optional است
) -> Optional[User]:
    query = select(User).where(User.telegram_id == telegram_id)
    
    if bot_id is not None:
        query = query.where(User.bot_id == bot_id)
    
    result = await db.execute(query)
    return result.scalar_one_or_none()

# ✅ Helper function برای required bot_id
async def get_user_by_telegram_id_and_bot_id(
    db: AsyncSession,
    telegram_id: int,
    bot_id: int  # ✅ Required
) -> Optional[User]:
    """Get user by telegram_id and bot_id (required for multi-tenant isolation)."""
    return await get_user_by_telegram_id(db, telegram_id, bot_id)
```

**وضعیت:** ⚠️ **70% - نیاز به بهبود**

**مشکلات:**
- ⚠️ `bot_id` هنوز optional است - باید required باشد
- ⚠️ برخی functions هنوز `bot_id` ندارند

**پیشنهادات دیباگ:**
```python
# 1. تست isolation
async with AsyncSessionLocal() as db:
    # Create user in bot 1
    user1 = await create_user(db, telegram_id=123456, bot_id=1)
    
    # Try to get user from bot 2
    user2 = await get_user_by_telegram_id(db, telegram_id=123456, bot_id=2)
    assert user2 is None  # ✅ باید None باشد - isolation کار می‌کند
    
    # Get user from bot 1
    user3 = await get_user_by_telegram_id(db, telegram_id=123456, bot_id=1)
    assert user3.id == user1.id  # ✅ باید پیدا شود
```

**پیشنهادات تکمیلی:**
```python
# بعد از migration، همه functions را required کنید:
async def get_user_by_telegram_id(
    db: AsyncSession, 
    telegram_id: int, 
    bot_id: int  # ✅ Required - نه Optional
) -> Optional[User]:
    result = await db.execute(
        select(User).where(
            User.telegram_id == telegram_id,
            User.bot_id == bot_id  # ✅ همیشه filter می‌شود
        )
    )
    return result.scalar_one_or_none()
```

---

### Increment 2.2: Update Subscription CRUD

#### قبل از تغییرات
```python
# app/database/crud/subscription.py
async def get_subscription_by_user_id(
    db: AsyncSession, 
    user_id: int
) -> Optional[Subscription]:
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    return result.scalar_one_or_none()
    # ❌ بدون bot_id
```

#### بعد از تغییرات
```python
# app/database/crud/subscription.py
async def get_subscription_by_user_id(
    db: AsyncSession, 
    user_id: int, 
    bot_id: Optional[int] = None  # ⚠️ هنوز optional
) -> Optional[Subscription]:
    query = select(Subscription).where(Subscription.user_id == user_id)
    
    if bot_id is not None:
        query = query.where(Subscription.bot_id == bot_id)
    
    result = await db.execute(query)
    subscription = result.scalar_one_or_none()
    return subscription

async def create_trial_subscription(
    db: AsyncSession,
    user_id: int,
    duration_days: int = None,
    bot_id: Optional[int] = None  # ✅ اضافه شده
) -> Subscription:
    subscription = Subscription(
        user_id=user_id,
        bot_id=bot_id,  # ✅ اضافه شده
        status=SubscriptionStatus.ACTIVE.value,
        # ...
    )
    db.add(subscription)
    await db.commit()
    return subscription
```

**وضعیت:** ⚠️ **70% - نیاز به بهبود**

**پیشنهادات تکمیلی:**
```python
# بعد از migration، required کنید:
async def get_subscription_by_user_id(
    db: AsyncSession, 
    user_id: int,
    bot_id: int  # ✅ Required
) -> Optional[Subscription]:
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.bot_id == bot_id  # ✅ همیشه filter
        )
    )
    return result.scalar_one_or_none()
```

---

## 🎯 Phase 3: Handlers Update

### Increment 3.1: Update Start Handler

#### قبل از تغییرات
```python
# app/handlers/start.py
async def cmd_start(
    message: types.Message, 
    state: FSMContext, 
    db: AsyncSession, 
    db_user=None
):
    if not db_user:
        db_user = await create_user(
            db,
            telegram_id=message.from_user.id,
            first_name=message.from_user.first_name,
            # ❌ bot_id missing
        )
```

#### بعد از تغییرات
```python
# app/handlers/start.py
async def cmd_start(
    message: types.Message, 
    state: FSMContext, 
    db: AsyncSession, 
    db_user=None,
    bot_id: int = None  # ✅ از middleware
):
    if not db_user:
        db_user = await create_user(
            db,
            telegram_id=message.from_user.id,
            first_name=message.from_user.first_name,
            bot_id=bot_id,  # ✅ اضافه شده
        )
    
    # استفاده از bot_id در queries
    user = await get_user_by_telegram_id(db, message.from_user.id, bot_id=bot_id)
```

**وضعیت:** ✅ **75% - خوب**

**مشکلات:**
- ⚠️ برخی handlers هنوز `bot_id` استفاده نمی‌کنند
- ⚠️ Admin handlers نیاز به `bot_id` دارند

---

### Increment 3.2: Admin Handlers - مشکل جدی

#### قبل از تغییرات
```python
# app/handlers/admin/users.py
async def list_users_handler(callback: CallbackQuery, db: AsyncSession):
    users = await get_users_list(db, limit=50)
    # ❌ تمام users از تمام bots را برمی‌گرداند
```

#### بعد از تغییرات
```python
# ⚠️ هنوز به‌روزرسانی نشده!
# app/handlers/admin/users.py
async def list_users_handler(callback: CallbackQuery, db: AsyncSession):
    users = await get_users_list(db, limit=50)
    # ❌ هنوز bot_id ندارد - نقض isolation!
```

**وضعیت:** ❌ **55% - مشکل جدی**

**مشکلات شناسایی شده:**
1. `app/handlers/admin/messages.py` - `get_target_users` بدون `bot_id`
2. `app/handlers/admin/users.py` - بسیاری از functions بدون `bot_id`
3. `app/handlers/admin/subscriptions.py` - نیاز به `bot_id`
4. `app/handlers/admin/promocodes.py` - نیاز به `bot_id`

**پیشنهادات فوری:**
```python
# Fix: app/handlers/admin/users.py
async def list_users_handler(
    callback: CallbackQuery, 
    db: AsyncSession,
    bot_id: int  # ✅ از middleware
):
    users = await get_users_list(db, limit=50, bot_id=bot_id)  # ✅ filter
    # ...

# Fix: app/handlers/admin/messages.py
async def get_target_users(
    db: AsyncSession, 
    target: str,
    bot_id: int  # ✅ اضافه کنید
) -> list:
    users: list[User] = []
    offset = 0
    batch_size = 5000

    while True:
        batch = await get_users_list(
            db,
            offset=offset,
            limit=batch_size,
            status=UserStatus.ACTIVE,
            bot_id=bot_id  # ✅ اضافه کنید
        )
        # ...
```

---

## 🌐 Phase 4: Multi-Bot Support

### Increment 4.1: Bot Initialization

#### قبل از تغییرات
```python
# app/bot.py
async def setup_bot() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.BOT_TOKEN, ...)
    dp = Dispatcher(storage=storage)
    # ... register handlers ...
    return bot, dp

# main.py
async def main():
    bot, dp = await setup_bot()
    await dp.start_polling(bot)
    # ❌ فقط یک bot
```

#### بعد از تغییرات
```python
# app/bot.py
# Global registry for active bots and dispatchers
active_bots: Dict[int, Bot] = {}
active_dispatchers: Dict[int, Dispatcher] = {}
polling_tasks: Dict[int, asyncio.Task] = {}

async def setup_bot(bot_config: Optional[BotModel] = None) -> tuple[Bot, Dispatcher]:
    """Setup a single bot instance."""
    if bot_config:
        bot_token = bot_config.telegram_bot_token
        bot_id = bot_config.id
    else:
        bot_token = settings.BOT_TOKEN  # Backward compatibility
        bot_id = None
    
    bot = Bot(token=bot_token, ...)
    dp = Dispatcher(storage=storage)
    # ... register handlers ...
    return bot, dp

async def initialize_all_bots() -> Dict[int, tuple[Bot, Dispatcher]]:
    """Initialize all active bots from database."""
    from app.database.database import AsyncSessionLocal
    from app.database.crud.bot import get_active_bots
    
    async with AsyncSessionLocal() as db:
        bots = await get_active_bots(db)
        initialized = {}
        
        for bot_config in bots:
            try:
                bot, dp = await setup_bot(bot_config)
                active_bots[bot_config.id] = bot
                active_dispatchers[bot_config.id] = dp
                initialized[bot_config.id] = (bot, dp)
                logger.info(f"✅ Bot {bot_config.id} ({bot_config.name}) initialized")
            except Exception as e:
                logger.error(f"❌ Failed to initialize bot {bot_config.id}: {e}")
        
        return initialized

# main.py
async def main():
    from app.bot import initialize_all_bots, active_bots, active_dispatchers
    
    initialized_bots = await initialize_all_bots()
    
    if not initialized_bots:
        logger.error("❌ No active bots found!")
        return
    
    # Start polling for all bots
    for bot_id, (bot_instance, dp_instance) in initialized_bots.items():
        task = asyncio.create_task(
            dp_instance.start_polling(bot_instance, skip_updates=True)
        )
        polling_tasks[bot_id] = task
        logger.info(f"✅ Polling started for bot {bot_id}")
```

**وضعیت:** ✅ **80% - خوب**

**پیشنهادات دیباگ:**
```python
# 1. تست initialization
from app.bot import initialize_all_bots
initialized = await initialize_all_bots()
assert len(initialized) > 0
print(f"✅ {len(initialized)} bot(s) initialized")

# 2. تست polling
# باید همه bots در حال polling باشند
for bot_id, task in polling_tasks.items():
    assert not task.done()
    print(f"✅ Bot {bot_id} is polling")

# 3. تست webhook (اگر enabled باشد)
# باید webhook برای هر bot جداگانه set شود
```

---

### Increment 4.2: Webhook Support

#### قبل از تغییرات
```python
# main.py
if telegram_webhook_enabled:
    await bot.set_webhook(url=webhook_url)
    # ❌ فقط یک bot
```

#### بعد از تغییرات
```python
# main.py
if telegram_webhook_enabled:
    base_webhook_url = settings.get_telegram_webhook_url()
    from urllib.parse import urljoin
    
    allowed_updates = dp.resolve_used_update_types()
    webhooks_set = 0
    
    for bot_id, (bot_instance, dp_instance) in initialized_bots.items():
        # Use bot-specific webhook URL: /webhook/{bot_id}
        bot_webhook_url = urljoin(base_webhook_url.rstrip('/') + '/', f'webhook/{bot_id}')
        
        try:
            await bot_instance.set_webhook(
                url=bot_webhook_url,
                secret_token=settings.WEBHOOK_SECRET_TOKEN,
                drop_pending_updates=settings.WEBHOOK_DROP_PENDING_UPDATES,
                allowed_updates=allowed_updates,
            )
            logger.info(f"✅ Webhook set for bot {bot_id}: {bot_webhook_url}")
            webhooks_set += 1
        except Exception as e:
            logger.error(f"❌ Failed to set webhook for bot {bot_id}: {e}")
```

**وضعیت:** ✅ **80% - خوب**

---

## 🔐 Phase 5: Security & API

### Increment 5.1: Web API Routes - مشکل بحرانی

#### قبل از تغییرات
```python
# app/webapi/routes/users.py
@router.get("", response_model=UserListResponse)
async def list_users(
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
):
    base_query = select(User)
    # ❌ بدون bot_id filter - تمام users از تمام bots!
    result = await db.execute(base_query)
    users = result.scalars().all()
    return UserListResponse(items=users, ...)
```

#### بعد از تغییرات
```python
# ⚠️ هنوز به‌روزرسانی نشده!
# app/webapi/routes/users.py
@router.get("", response_model=UserListResponse)
async def list_users(
    _: Any = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session),
):
    base_query = select(User)  # ❌ هنوز bot_id ندارد!
    # ❌ نقض جدی isolation!
```

**وضعیت:** ❌ **65% - مشکل بحرانی امنیتی**

**پیشنهادات فوری:**
```python
# Fix: app/webapi/routes/users.py
from app.database.crud.bot import get_bot_by_api_token

def get_bot_id_from_token(
    token: str = Security(require_api_token),
    db: AsyncSession = Depends(get_db_session)
) -> int:
    """Extract bot_id from API token."""
    bot = await get_bot_by_api_token(db, token)
    if not bot:
        raise HTTPException(status_code=401, detail="Invalid API token")
    return bot.id

@router.get("", response_model=UserListResponse)
async def list_users(
    bot_id: int = Depends(get_bot_id_from_token),  # ✅ از API token
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    base_query = select(User).where(User.bot_id == bot_id)  # ✅ Filter
    # ...
```

---

## 🎛️ Phase 6: Feature Flags

### Increment 6.1: Feature Flag Service

#### قبل از تغییرات
```python
# در handlers:
if settings.TELEGRAM_STARS_ENABLED:
    # ... handle stars payment ...
# ❌ Global setting - نمی‌شد per-tenant تنظیم کرد
```

#### بعد از تغییرات
```python
# app/services/tenant_feature_service.py (NEW FILE)
class TenantFeatureService:
    CACHE_TTL = 300  # 5 minutes
    CACHE_PREFIX = "feature_flag"
    
    @staticmethod
    async def is_feature_enabled(
        db: AsyncSession,
        bot_id: int,
        feature_key: str,
        use_cache: bool = True
    ) -> bool:
        """Check if a feature is enabled for a tenant."""
        cache_key_str = TenantFeatureService._get_cache_key(bot_id, feature_key)
        
        if use_cache:
            cached = await cache.get(cache_key_str)
            if cached is not None:
                return bool(cached)
        
        # Fetch from database
        enabled = await crud_is_feature_enabled(db, bot_id, feature_key)
        
        # Cache the result
        if use_cache:
            await cache.set(cache_key_str, enabled, expire=TenantFeatureService.CACHE_TTL)
        
        return enabled

# استفاده در handlers:
from app.services.tenant_feature_service import TenantFeatureService

bot_id = data.get('bot_id')
if await TenantFeatureService.is_feature_enabled(db, bot_id, 'telegram_stars'):
    # ... handle stars payment ...
```

**وضعیت:** ⚠️ **70% - استفاده محدود**

**مشکلات:**
- ⚠️ بسیاری از handlers هنوز از `settings` استفاده می‌کنند
- ⚠️ نیاز به migration همه handlers

**پیشنهادات تکمیلی:**
```python
# Migration checklist برای handlers:
# 1. Payment handlers
#    - stars_payments.py: settings.TELEGRAM_STARS_ENABLED → feature flag
#    - balance/yookassa.py: settings.is_yookassa_enabled() → feature flag
#    - balance/cryptobot.py: settings.is_cryptobot_enabled() → feature flag
#    - ... (همه payment methods)

# 2. Subscription handlers
#    - subscription.py: settings.TRIAL_ENABLED → feature flag
#    - simple_subscription.py: settings.SIMPLE_PURCHASE_ENABLED → feature flag

# 3. Referral handlers
#    - referral.py: settings.REFERRAL_ENABLED → feature flag

# 4. Support handlers
#    - support.py: settings.SUPPORT_ENABLED → feature flag
```

---

## 📋 خلاصه مشکلات و راه‌حل‌ها

### مشکلات بحرانی (Critical) - فوری

1. **Web API Routes بدون bot_id filtering**
   - **فایل:** `app/webapi/routes/users.py`
   - **مشکل:** تمام users از تمام bots را برمی‌گرداند
   - **راه‌حل:** اضافه کردن `get_bot_id_from_token` dependency
   - **اولویت:** 🔴 فوری

2. **Admin Handlers بدون bot_id**
   - **فایل‌ها:** `app/handlers/admin/messages.py`, `users.py`, `subscriptions.py`
   - **مشکل:** Admin می‌تواند داده‌های تمام bots را ببیند
   - **راه‌حل:** اضافه کردن `bot_id` از middleware
   - **اولویت:** 🔴 فوری

3. **CRUD Functions با optional bot_id**
   - **فایل‌ها:** `app/database/crud/user.py`, `subscription.py`
   - **مشکل:** اگر `bot_id=None` باشد، isolation نقض می‌شود
   - **راه‌حل:** تبدیل به required بعد از migration
   - **اولویت:** 🟡 مهم

### مشکلات مهم (High Priority)

1. **Handlers از settings استفاده می‌کنند**
   - **راه‌حل:** Migration به feature flags
   - **اولویت:** 🟡 مهم

2. **Services context-aware نیستند**
   - **راه‌حل:** استفاده از bot_id از context
   - **اولویت:** 🟡 مهم

---

## 🛠️ پیشنهادات دیباگ و تکمیلی

### 1. تست‌های Isolation

```python
# tests/test_multi_tenant_isolation.py
import pytest
from app.database.crud.user import create_user, get_user_by_telegram_id

async def test_user_isolation():
    """Test that users are isolated by bot_id."""
    async with AsyncSessionLocal() as db:
        # Create user in bot 1
        user1 = await create_user(db, telegram_id=123456, bot_id=1)
        
        # Try to get from bot 2
        user2 = await get_user_by_telegram_id(db, telegram_id=123456, bot_id=2)
        assert user2 is None  # ✅ Isolation works
        
        # Get from bot 1
        user3 = await get_user_by_telegram_id(db, telegram_id=123456, bot_id=1)
        assert user3.id == user1.id  # ✅ Found in correct bot
```

### 2. Monitoring و Logging

```python
# اضافه کردن logging برای tracking bot_id در تمام operations
import logging
logger = logging.getLogger(__name__)

async def get_user_by_telegram_id(db, telegram_id, bot_id):
    logger.info(f"🔍 Querying user telegram_id={telegram_id} bot_id={bot_id}")
    # ... query ...
    if user:
        logger.info(f"✅ Found user {user.id} in bot {bot_id}")
    else:
        logger.warning(f"⚠️ User not found in bot {bot_id}")
    return user
```

### 3. Migration Script

```python
# scripts/migrate_existing_data.py
async def migrate_existing_data():
    """Migrate existing single-tenant data to multi-tenant."""
    async with AsyncSessionLocal() as db:
        # 1. Create master bot
        master_bot, _ = await create_bot(
            db,
            name="Master Bot",
            telegram_bot_token=settings.BOT_TOKEN,
            is_master=True
        )
        
        # 2. Assign all existing users to master bot
        result = await db.execute(select(User).where(User.bot_id.is_(None)))
        users = result.scalars().all()
        
        for user in users:
            user.bot_id = master_bot.id
        
        await db.commit()
        
        # 3. Make bot_id NOT NULL
        await db.execute(text("ALTER TABLE users ALTER COLUMN bot_id SET NOT NULL"))
        await db.commit()
        
        logger.info(f"✅ Migrated {len(users)} users to master bot")
```

---

## ✅ چک‌لیست تکمیل

### Phase 1: Foundation
- [x] Database Schema (7 tables)
- [x] Models (7 new + modifications)
- [x] Bot CRUD
- [x] Feature Flag CRUD
- [x] Bot Context Middleware

### Phase 2: Core Features
- [x] User CRUD (70% - نیاز به required bot_id)
- [x] Subscription CRUD (70% - نیاز به required bot_id)
- [ ] Transaction CRUD
- [ ] Ticket CRUD
- [ ] PromoCode CRUD

### Phase 3: Handlers
- [x] Start Handler (75%)
- [ ] Admin Handlers (55% - مشکل جدی)
- [ ] Payment Handlers
- [ ] Subscription Handlers

### Phase 4: Multi-Bot
- [x] Bot Initialization (80%)
- [x] Webhook Support (80%)
- [ ] Service Context-Aware

### Phase 5: Security
- [ ] Web API Routes (65% - مشکل بحرانی)
- [ ] Admin Access Control

### Phase 6: Feature Flags
- [x] Feature Flag Service (70%)
- [ ] Handler Migration (30%)

---

## 📊 نتیجه‌گیری

**وضعیت کلی:** 68% تکمیل شده

**نقاط قوت:**
- ✅ Database schema و models خوب هستند
- ✅ Multi-bot support درست پیاده شده
- ✅ Middleware درست کار می‌کند
- ✅ مستندات عالی است

**نقاط ضعف:**
- ❌ Handlers به‌روزرسانی نشده‌اند (55%)
- ❌ Security issues وجود دارد
- ⚠️ Feature flags استفاده محدود دارند

**اولویت‌ها:**
1. 🔴 فوری: Fix Web API routes و Admin handlers
2. 🟡 مهم: CRUD functions را required bot_id کنید
3. 🟡 مهم: Feature flags را در handlers استفاده کنید

**زمان تخمینی برای تکمیل:** 3-4 هفته

---

**تاریخ گزارش:** 2025-12-15  
**نسخه:** 1.0










