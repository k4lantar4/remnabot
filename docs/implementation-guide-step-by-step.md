# راهنمای پیاده‌سازی مرحله‌ای Multi-Tenant (با رفع Redundancy)

**تاریخ:** 2025-12-15  
**وضعیت:** راهنمای کامل پیاده‌سازی  
**اولویت:** ⚠️ CRITICAL

---

## 🎯 هدف این سند

این سند راهنمای **مرحله‌به‌مرحله** برای پیاده‌سازی Multi-Tenant است که:
1. ✅ مشکل redundancy را حل می‌کند
2. ✅ از technical debt جلوگیری می‌کند
3. ✅ هر مرحله قابل تست و rollback است
4. ✅ کد تمیز و maintainable می‌ماند

---

## 📋 پیش‌نیازها

قبل از شروع، این مستندات را بخوانید:

1. ✅ `docs/TENANT-DOCS-READING-GUIDE.md` - راهنمای کلی
2. ✅ `docs/analysis/redundancy-analysis-and-refactoring-plan.md` - تحلیل redundancy
3. ✅ `docs/multi-tenant-design-document.md` - طراحی کلی
4. ✅ `docs/tenant-configs-categorization.md` - دسته‌بندی configs

---

## 🏗️ معماری نهایی (بعد از Refactoring)

### اصل Separation of Concerns:

```
┌─────────────────────────────────────────┐
│         bots table                       │
│  (Identity + Billing + Metadata)        │
│  - id, name, tokens                      │
│  - wallet_balance, traffic stats        │
│  - created_at, updated_at                │
└─────────────────────────────────────────┘
              │
              ├─────────────────┐
              │                 │
┌─────────────▼──────┐  ┌──────▼──────────────┐
│ bot_feature_flags   │  │ bot_configurations  │
│ (Feature Flags)     │  │ (All Config Values) │
│ - enabled/disabled │  │ - key-value pairs   │
└─────────────────────┘  └─────────────────────┘
```

**قانون:** هر config فقط در یک جا!

---

## 📅 Timeline پیاده‌سازی

### Week 1: Foundation & Refactoring

**Day 1-2: آماده‌سازی Schema (بدون Redundancy)**
- [ ] ایجاد migration برای جداول جدید (بدون redundant columns در bots)
- [ ] ایجاد models
- [ ] ایجاد CRUD operations

**Day 3-4: Service Layer**
- [ ] ایجاد `BotConfigService` (single source of truth)
- [ ] تست Service
- [ ] مستندسازی

**Day 5: Migration Data**
- [ ] Migration script برای داده‌های موجود
- [ ] Verification script
- [ ] تست migration

---

### Week 2: Core Implementation

**Day 1-2: Bot Context Middleware**
- [ ] ایجاد middleware
- [ ] Register در bot.py
- [ ] تست isolation

**Day 3-4: Update CRUD Operations**
- [ ] Update user CRUD (اضافه کردن bot_id filter)
- [ ] Update subscription CRUD
- [ ] Update transaction CRUD
- [ ] Update سایر CRUD files

**Day 5: Update Handlers**
- [ ] Update start handler
- [ ] Update menu handlers
- [ ] Update payment handlers
- [ ] تست handlers

---

### Week 3: Feature Flags & Configs

**Day 1-2: Feature Flag System**
- [ ] پیاده‌سازی `TenantFeatureService`
- [ ] جایگزینی تمام `settings.*` با Service
- [ ] تست feature flags

**Day 3-4: Configuration Management**
- [ ] پیاده‌سازی config sync
- [ ] پیاده‌سازی config cloning
- [ ] تست configurations

**Day 5: Multi-Bot Support**
- [ ] Update bot.py برای multi-bot
- [ ] Update main.py
- [ ] تست initialization

---

### Week 4: Admin Panel & Testing

**Day 1-3: Master Admin Panel**
- [ ] پیاده‌سازی menu structure
- [ ] پیاده‌سازی feature flags management
- [ ] پیاده‌سازی configuration management
- [ ] تست admin panel

**Day 4-5: Testing & Refinement**
- [ ] Unit tests
- [ ] Integration tests
- [ ] Performance testing
- [ ] Bug fixes

---

## 🔧 مراحل جزئی پیاده‌سازی

### Step 1: ایجاد Schema (بدون Redundancy)

#### 1.1. Migration File

```sql
-- migrations/001_create_multi_tenant_tables_clean.sql

-- bots table (فقط Identity + Billing)
CREATE TABLE bots (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    telegram_bot_token VARCHAR(255) UNIQUE NOT NULL,
    api_token VARCHAR(255) UNIQUE NOT NULL,
    api_token_hash VARCHAR(128) NOT NULL,
    is_master BOOLEAN DEFAULT FALSE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    
    -- Billing only
    wallet_balance_toman BIGINT DEFAULT 0 NOT NULL,
    traffic_consumed_bytes BIGINT DEFAULT 0 NOT NULL,
    traffic_sold_bytes BIGINT DEFAULT 0 NOT NULL,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- bot_feature_flags (تمام feature flags)
CREATE TABLE bot_feature_flags (
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT FALSE NOT NULL,
    config JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    
    PRIMARY KEY (bot_id, feature_key)
);

-- bot_configurations (تمام configs)
CREATE TABLE bot_configurations (
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    config_key VARCHAR(100) NOT NULL,
    config_value JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    
    PRIMARY KEY (bot_id, config_key)
);

-- Indexes
CREATE INDEX idx_bot_feature_flags_bot_id ON bot_feature_flags(bot_id);
CREATE INDEX idx_bot_configurations_bot_id ON bot_configurations(bot_id);
```

**✅ نکته:** هیچ redundant column در `bots` table نیست!

---

#### 1.2. Models

```python
# app/database/models.py

class Bot(Base):
    __tablename__ = "bots"
    
    # ✅ فقط Identity + Billing + Metadata
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    telegram_bot_token = Column(String(255), unique=True, nullable=False, index=True)
    api_token = Column(String(255), unique=True, nullable=False)
    api_token_hash = Column(String(128), nullable=False, index=True)
    is_master = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Billing
    wallet_balance_toman = Column(BigInteger, default=0, nullable=False)
    traffic_consumed_bytes = Column(BigInteger, default=0, nullable=False)
    traffic_sold_bytes = Column(BigInteger, default=0, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    feature_flags = relationship("BotFeatureFlag", back_populates="bot", cascade="all, delete-orphan")
    configurations = relationship("BotConfiguration", back_populates="bot", cascade="all, delete-orphan")
```

**✅ نکته:** هیچ column برای configs یا feature flags نیست!

---

### Step 2: ایجاد BotConfigService

```python
# app/services/bot_config_service.py

from typing import Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.crud.bot_feature_flag import (
    get_feature_flag,
    set_feature_flag,
    is_feature_enabled as check_feature_enabled
)
from app.database.crud.bot_configuration import (
    get_configuration,
    set_bot_configuration,
    get_config_value as get_config_value_from_db
)


class BotConfigService:
    """
    Single Source of Truth برای دسترسی به configs و feature flags
    
    قانون:
    - bots table = Identity + Billing
    - bot_feature_flags = Feature enable/disable
    - bot_configurations = All config values
    """
    
    # ========== Feature Flags ==========
    
    @staticmethod
    async def is_feature_enabled(
        db: AsyncSession,
        bot_id: int,
        feature_key: str
    ) -> bool:
        """
        بررسی اینکه feature فعال است یا نه
        
        Args:
            db: Database session
            bot_id: Bot ID
            feature_key: Feature key (مثلاً 'card_to_card', 'zarinpal')
        
        Returns:
            True if enabled, False otherwise
        """
        return await check_feature_enabled(db, bot_id, feature_key)
    
    @staticmethod
    async def set_feature_enabled(
        db: AsyncSession,
        bot_id: int,
        feature_key: str,
        enabled: bool,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        تنظیم feature flag
        
        Args:
            db: Database session
            bot_id: Bot ID
            feature_key: Feature key
            enabled: True/False
            config: Optional config dict
        """
        await set_feature_flag(db, bot_id, feature_key, enabled, config)
        await db.commit()
    
    # ========== Configurations ==========
    
    @staticmethod
    async def get_config(
        db: AsyncSession,
        bot_id: int,
        config_key: str,
        default: Any = None
    ) -> Any:
        """
        خواندن config value
        
        Args:
            db: Database session
            bot_id: Bot ID
            config_key: Config key (مثلاً 'DEFAULT_LANGUAGE')
            default: Default value if not found
        
        Returns:
            Config value or default
        """
        config = await get_configuration(db, bot_id, config_key)
        if config:
            value = config.config_value
            # اگر JSONB است و یک value ساده است، extract کن
            if isinstance(value, dict) and len(value) == 1 and 'value' in value:
                return value['value']
            return value
        return default
    
    @staticmethod
    async def set_config(
        db: AsyncSession,
        bot_id: int,
        config_key: str,
        value: Any
    ) -> None:
        """
        تنظیم config value
        
        Args:
            db: Database session
            bot_id: Bot ID
            config_key: Config key
            value: Config value (می‌تواند string, int, bool, dict باشد)
        """
        # Normalize value برای JSONB
        if not isinstance(value, dict):
            normalized_value = {'value': value}
        else:
            normalized_value = value
        
        await set_bot_configuration(db, bot_id, config_key, normalized_value)
        await db.commit()
    
    @staticmethod
    async def get_all_configs(
        db: AsyncSession,
        bot_id: int
    ) -> Dict[str, Any]:
        """
        دریافت تمام configs به صورت dict
        
        Returns:
            Dict[config_key, config_value]
        """
        from app.database.crud.bot_configuration import get_all_configurations_dict
        return await get_all_configurations_dict(db, bot_id)
```

---

### Step 3: استفاده در Code

#### 3.1. جایگزینی Feature Flag Checks

**قبل:**
```python
# ❌ بد - اگر bots table داشته باشد
if bot.card_to_card_enabled:
    # handle payment
```

**بعد:**
```python
# ✅ خوب
from app.services.bot_config_service import BotConfigService

bot_id = data.get('bot_id')
if await BotConfigService.is_feature_enabled(db, bot_id, 'card_to_card'):
    # handle payment
```

#### 3.2. جایگزینی Config Reads

**قبل:**
```python
# ❌ بد
default_lang = bot.default_language or 'fa'
```

**بعد:**
```python
# ✅ خوب
default_lang = await BotConfigService.get_config(
    db, bot_id, 'DEFAULT_LANGUAGE', default='fa'
)
```

#### 3.3. جایگزینی Config Writes

**قبل:**
```python
# ❌ بد
bot.default_language = 'en'
await db.commit()
```

**بعد:**
```python
# ✅ خوب
await BotConfigService.set_config(
    db, bot_id, 'DEFAULT_LANGUAGE', 'en'
)
```

---

### Step 4: Migration داده‌های موجود

اگر قبلاً داده‌هایی در `bots` table دارید که باید migrate شوند:

```python
# migrations/migrate_existing_data.py

async def migrate_existing_bot_data(db: AsyncSession):
    """
    اگر قبلاً bot data دارید که باید migrate شود
    این script داده‌ها را از .env یا settings به database منتقل می‌کند
    """
    from app.database.crud.bot import get_master_bot
    from app.services.bot_config_service import BotConfigService
    from app.config import settings
    
    # 1. Get master bot
    master_bot = await get_master_bot(db)
    if not master_bot:
        logger.error("Master bot not found!")
        return
    
    # 2. Migrate feature flags from settings
    feature_mappings = {
        'card_to_card': getattr(settings, 'CARD_TO_CARD_ENABLED', False),
        'zarinpal': getattr(settings, 'ZARINPAL_ENABLED', False),
        'telegram_stars': getattr(settings, 'TELEGRAM_STARS_ENABLED', False),
        # ... سایر feature flags
    }
    
    for feature_key, enabled in feature_mappings.items():
        await BotConfigService.set_feature_enabled(
            db, master_bot.id, feature_key, enabled
        )
    
    # 3. Migrate configs from settings
    config_mappings = {
        'DEFAULT_LANGUAGE': getattr(settings, 'DEFAULT_LANGUAGE', 'fa'),
        'SUPPORT_USERNAME': getattr(settings, 'SUPPORT_USERNAME', None),
        # ... سایر configs
    }
    
    for config_key, value in config_mappings.items():
        if value is not None:
            await BotConfigService.set_config(
                db, master_bot.id, config_key, value
            )
    
    logger.info("Migration completed!")
```

---

## ✅ چک‌لیست کامل پیاده‌سازی

### Phase 1: Schema & Models
- [ ] Migration file ایجاد شده (بدون redundant columns)
- [ ] Models ایجاد شده
- [ ] CRUD operations ایجاد شده
- [ ] Tests برای models نوشته شده

### Phase 2: Service Layer
- [ ] `BotConfigService` ایجاد شده
- [ ] تمام methods تست شده
- [ ] مستندسازی کامل

### Phase 3: Code Updates
- [ ] تمام feature flag checks جایگزین شده
- [ ] تمام config reads جایگزین شده
- [ ] تمام config writes جایگزین شده
- [ ] Tests برای updates نوشته شده

### Phase 4: Migration
- [ ] Migration script برای داده‌های موجود
- [ ] Verification script
- [ ] تست migration روی dev

### Phase 5: Testing
- [ ] Unit tests
- [ ] Integration tests
- [ ] Performance tests
- [ ] Manual testing

---

## 🎯 اصول مهم

### 1. Single Source of Truth
```
❌ هرگز مستقیماً به bots table برای configs دسترسی ندهید
✅ همیشه از BotConfigService استفاده کنید
```

### 2. Isolation
```
❌ هرگز query بدون bot_id filter ننویسید
✅ همیشه bot_id را در queries فیلتر کنید
```

### 3. Consistency
```
❌ هرگز config را در دو جا ذخیره نکنید
✅ هر config فقط در یک جا (bot_feature_flags یا bot_configurations)
```

---

## 📝 خلاصه

### Schema نهایی:
- `bots`: فقط Identity + Billing + Metadata
- `bot_feature_flags`: تمام feature flags
- `bot_configurations`: تمام config values

### Service Layer:
- `BotConfigService`: single source of truth برای دسترسی

### مزایا:
- ✅ No redundancy
- ✅ No technical debt
- ✅ Clean code
- ✅ Easy to maintain

---

**آخرین به‌روزرسانی:** 2025-12-15  
**نسخه:** 1.0

