# تحلیل Redundancy و برنامه Refactoring

**تاریخ:** 2025-12-15  
**وضعیت:** تحلیل کامل - آماده برای اجرا  
**اولویت:** ⚠️ CRITICAL - باید قبل از پیاده‌سازی حل شود

---

## 🚨 مشکل اصلی: Redundancy در Database Schema

### مشکل چیست؟

در طراحی فعلی، برخی configs در **دو جا** ذخیره می‌شوند:

1. **در `bots` table** (به عنوان column)
2. **در `bot_feature_flags` یا `bot_configurations`** (به عنوان row)

این redundancy باعث می‌شود:
- ❌ **Data inconsistency**: ممکن است دو جا با هم هماهنگ نباشند
- ❌ **Confusion**: نمی‌دانیم کدام منبع truth است
- ❌ **Technical debt**: کد پیچیده و نگهداری سخت می‌شود
- ❌ **Bug potential**: ممکن است یک جا update شود و جای دیگر نه

---

## 📊 تحلیل دقیق Redundancy

### 1. Configs که در `bots` table هستند (اما باید جای دیگری باشند)

#### 1.1. Feature Flags (باید در `bot_feature_flags` باشند)

| Column در `bots` | باید در `bot_feature_flags` | وضعیت |
|------------------|---------------------------|-------|
| `card_to_card_enabled` | `feature_key='card_to_card'` | ❌ Redundant |
| `zarinpal_enabled` | `feature_key='zarinpal'` | ❌ Redundant |

**مشکل:** این دو column باید حذف شوند و فقط در `bot_feature_flags` باشند.

---

#### 1.2. Configurations (باید در `bot_configurations` باشند)

| Column در `bots` | باید در `bot_configurations` | وضعیت |
|------------------|----------------------------|-------|
| `default_language` | `config_key='DEFAULT_LANGUAGE'` | ❌ Redundant |
| `support_username` | `config_key='SUPPORT_USERNAME'` | ❌ Redundant |
| `admin_chat_id` | `config_key='ADMIN_NOTIFICATIONS_CHAT_ID'` | ❌ Redundant |
| `admin_topic_id` | `config_key='ADMIN_NOTIFICATIONS_TOPIC_ID'` | ❌ Redundant |
| `notification_group_id` | `config_key='NOTIFICATION_GROUP_ID'` | ❌ Redundant |
| `notification_topic_id` | `config_key='NOTIFICATION_TOPIC_ID'` | ❌ Redundant |
| `card_receipt_topic_id` | `config_key='CARD_RECEIPT_TOPIC_ID'` | ❌ Redundant |
| `zarinpal_merchant_id` | `config_key='ZARINPAL_MERCHANT_ID'` | ❌ Redundant |
| `zarinpal_sandbox` | `config_key='ZARINPAL_SANDBOX'` | ❌ Redundant |

**مشکل:** این 9 column باید حذف شوند و فقط در `bot_configurations` باشند.

---

### 2. Configs که باید در `bots` table بمانند (Identity & Billing)

این configs **نباید** جابجا شوند چون:

| Column | دلیل ماندن در `bots` |
|--------|---------------------|
| `id` | Primary key |
| `name` | Identity - نام bot |
| `telegram_bot_token` | Identity - token برای اتصال به Telegram |
| `api_token` | Identity - token برای API management |
| `api_token_hash` | Security - hash برای authentication |
| `is_master` | Identity - نوع bot |
| `is_active` | Status - فعال/غیرفعال |
| `wallet_balance_toman` | Billing - موجودی wallet |
| `traffic_consumed_bytes` | Billing - ترافیک مصرف شده |
| `traffic_sold_bytes` | Billing - ترافیک فروخته شده |
| `created_at` | Metadata |
| `updated_at` | Metadata |
| `created_by` | Metadata |

**✅ اینها درست هستند و باید بمانند.**

---

## 🎯 اصلاح طراحی: Single Source of Truth

### قانون طلایی:

```
bots table = Identity + Billing + Metadata
bot_feature_flags = Feature enable/disable
bot_configurations = All config values
```

---

## 📋 برنامه Refactoring مرحله‌ای

### Phase 1: آماده‌سازی (بدون تغییر Schema)

**هدف:** ایجاد Service Layer برای دسترسی یکپارچه

#### Step 1.1: ایجاد `BotConfigService`

```python
# app/services/bot_config_service.py

class BotConfigService:
    """
    Single source of truth برای دسترسی به configs
    این service تصمیم می‌گیرد از کجا config را بخواند
    """
    
    @staticmethod
    async def get_feature_enabled(
        db: AsyncSession,
        bot_id: int,
        feature_key: str
    ) -> bool:
        """
        بررسی feature flag
        اول از bot_feature_flags می‌خواند
        اگر نبود، از bots table (برای backward compatibility)
        """
        # 1. Try bot_feature_flags first
        flag = await get_feature_flag(db, bot_id, feature_key)
        if flag:
            return flag.enabled
        
        # 2. Fallback to bots table (legacy)
        if feature_key == 'card_to_card':
            bot = await get_bot_by_id(db, bot_id)
            return bot.card_to_card_enabled if bot else False
        elif feature_key == 'zarinpal':
            bot = await get_bot_by_id(db, bot_id)
            return bot.zarinpal_enabled if bot else False
        
        return False
    
    @staticmethod
    async def get_config_value(
        db: AsyncSession,
        bot_id: int,
        config_key: str
    ) -> Optional[Any]:
        """
        خواندن config value
        اول از bot_configurations می‌خواند
        اگر نبود، از bots table (برای backward compatibility)
        """
        # 1. Try bot_configurations first
        config = await get_configuration(db, bot_id, config_key)
        if config:
            return config.config_value
        
        # 2. Fallback to bots table (legacy)
        bot = await get_bot_by_id(db, bot_id)
        if not bot:
            return None
        
        # Map config_key to bots column
        mapping = {
            'DEFAULT_LANGUAGE': bot.default_language,
            'SUPPORT_USERNAME': bot.support_username,
            'ADMIN_NOTIFICATIONS_CHAT_ID': bot.admin_chat_id,
            'ADMIN_NOTIFICATIONS_TOPIC_ID': bot.admin_topic_id,
            'NOTIFICATION_GROUP_ID': bot.notification_group_id,
            'NOTIFICATION_TOPIC_ID': bot.notification_topic_id,
            'CARD_RECEIPT_TOPIC_ID': bot.card_receipt_topic_id,
            'ZARINPAL_MERCHANT_ID': bot.zarinpal_merchant_id,
            'ZARINPAL_SANDBOX': bot.zarinpal_sandbox,
        }
        
        return mapping.get(config_key)
    
    @staticmethod
    async def set_feature_enabled(
        db: AsyncSession,
        bot_id: int,
        feature_key: str,
        enabled: bool
    ) -> None:
        """
        تنظیم feature flag
        هم در bot_feature_flags و هم در bots table (برای backward compatibility)
        """
        # 1. Set in bot_feature_flags (primary)
        await set_feature_flag(db, bot_id, feature_key, enabled)
        
        # 2. Also set in bots table (legacy - will be removed later)
        if feature_key in ['card_to_card', 'zarinpal']:
            bot = await get_bot_by_id(db, bot_id)
            if feature_key == 'card_to_card':
                bot.card_to_card_enabled = enabled
            elif feature_key == 'zarinpal':
                bot.zarinpal_enabled = enabled
            await db.commit()
    
    @staticmethod
    async def set_config_value(
        db: AsyncSession,
        bot_id: int,
        config_key: str,
        value: Any
    ) -> None:
        """
        تنظیم config value
        هم در bot_configurations و هم در bots table (برای backward compatibility)
        """
        # 1. Set in bot_configurations (primary)
        await set_bot_configuration(db, bot_id, config_key, value)
        
        # 2. Also set in bots table (legacy - will be removed later)
        bot = await get_bot_by_id(db, bot_id)
        if not bot:
            return
        
        mapping = {
            'DEFAULT_LANGUAGE': 'default_language',
            'SUPPORT_USERNAME': 'support_username',
            'ADMIN_NOTIFICATIONS_CHAT_ID': 'admin_chat_id',
            'ADMIN_NOTIFICATIONS_TOPIC_ID': 'admin_topic_id',
            'NOTIFICATION_GROUP_ID': 'notification_group_id',
            'NOTIFICATION_TOPIC_ID': 'notification_topic_id',
            'CARD_RECEIPT_TOPIC_ID': 'card_receipt_topic_id',
            'ZARINPAL_MERCHANT_ID': 'zarinpal_merchant_id',
            'ZARINPAL_SANDBOX': 'zarinpal_sandbox',
        }
        
        column_name = mapping.get(config_key)
        if column_name:
            setattr(bot, column_name, value)
            await db.commit()
```

**نکته:** این service در Phase 1 **هر دو جا** را update می‌کند (backward compatibility).

---

### Phase 2: Migration Data (بدون حذف Columns)

**هدف:** انتقال داده‌ها از `bots` table به جداول مناسب

#### Step 2.1: Migration Script

```python
# migrations/migrate_configs_from_bots_table.py

async def migrate_configs_to_proper_tables(db: AsyncSession):
    """
    انتقال configs از bots table به bot_feature_flags و bot_configurations
    """
    # 1. Get all bots
    bots = await get_all_bots(db)
    
    for bot in bots:
        # 2. Migrate feature flags
        if bot.card_to_card_enabled is not None:
            await set_feature_flag(
                db, 
                bot.id, 
                'card_to_card', 
                bot.card_to_card_enabled
            )
        
        if bot.zarinpal_enabled is not None:
            await set_feature_flag(
                db, 
                bot.id, 
                'zarinpal', 
                bot.zarinpal_enabled
            )
        
        # 3. Migrate configurations
        configs_to_migrate = {
            'DEFAULT_LANGUAGE': bot.default_language,
            'SUPPORT_USERNAME': bot.support_username,
            'ADMIN_NOTIFICATIONS_CHAT_ID': bot.admin_chat_id,
            'ADMIN_NOTIFICATIONS_TOPIC_ID': bot.admin_topic_id,
            'NOTIFICATION_GROUP_ID': bot.notification_group_id,
            'NOTIFICATION_TOPIC_ID': bot.notification_topic_id,
            'CARD_RECEIPT_TOPIC_ID': bot.card_receipt_topic_id,
            'ZARINPAL_MERCHANT_ID': bot.zarinpal_merchant_id,
            'ZARINPAL_SANDBOX': bot.zarinpal_sandbox,
        }
        
        for config_key, value in configs_to_migrate.items():
            if value is not None:
                await set_bot_configuration(
                    db, 
                    bot.id, 
                    config_key, 
                    value
                )
        
        await db.commit()
        logger.info(f"Migrated configs for bot {bot.id}")
```

#### Step 2.2: Verification Script

```python
# migrations/verify_config_migration.py

async def verify_migration(db: AsyncSession):
    """
    بررسی صحت migration
    """
    bots = await get_all_bots(db)
    
    for bot in bots:
        # Verify feature flags
        card_flag = await get_feature_flag(db, bot.id, 'card_to_card')
        assert card_flag is not None, f"Bot {bot.id}: card_to_card flag missing"
        assert card_flag.enabled == bot.card_to_card_enabled, \
            f"Bot {bot.id}: card_to_card mismatch"
        
        zarinpal_flag = await get_feature_flag(db, bot.id, 'zarinpal')
        assert zarinpal_flag is not None, f"Bot {bot.id}: zarinpal flag missing"
        assert zarinpal_flag.enabled == bot.zarinpal_enabled, \
            f"Bot {bot.id}: zarinpal mismatch"
        
        # Verify configurations
        default_lang = await get_configuration(db, bot.id, 'DEFAULT_LANGUAGE')
        assert default_lang is not None, f"Bot {bot.id}: DEFAULT_LANGUAGE missing"
        assert default_lang.config_value == bot.default_language, \
            f"Bot {bot.id}: DEFAULT_LANGUAGE mismatch"
        
        # ... verify other configs
        
        logger.info(f"✓ Bot {bot.id} migration verified")
```

---

### Phase 3: Update Code (استفاده از Service)

**هدف:** تغییر تمام کدها برای استفاده از `BotConfigService`

#### Step 3.1: Update Feature Flag Checks

**قبل:**
```python
# ❌ بد
if bot.card_to_card_enabled:
    # handle card payment
```

**بعد:**
```python
# ✅ خوب
from app.services.bot_config_service import BotConfigService

if await BotConfigService.get_feature_enabled(db, bot_id, 'card_to_card'):
    # handle card payment
```

#### Step 3.2: Update Config Reads

**قبل:**
```python
# ❌ بد
default_lang = bot.default_language
```

**بعد:**
```python
# ✅ خوب
default_lang = await BotConfigService.get_config_value(
    db, bot_id, 'DEFAULT_LANGUAGE'
) or 'fa'  # fallback
```

#### Step 3.3: Update Config Writes

**قبل:**
```python
# ❌ بد
bot.default_language = 'en'
await db.commit()
```

**بعد:**
```python
# ✅ خوب
await BotConfigService.set_config_value(
    db, bot_id, 'DEFAULT_LANGUAGE', 'en'
)
```

---

### Phase 4: حذف Columns از `bots` Table

**⚠️ فقط بعد از اینکه مطمئن شدیم همه کدها از Service استفاده می‌کنند**

#### Step 4.1: Migration Script برای حذف Columns

```sql
-- migrations/remove_redundant_columns_from_bots.sql

-- 1. حذف feature flag columns
ALTER TABLE bots 
    DROP COLUMN IF EXISTS card_to_card_enabled,
    DROP COLUMN IF EXISTS zarinpal_enabled;

-- 2. حذف configuration columns
ALTER TABLE bots 
    DROP COLUMN IF EXISTS default_language,
    DROP COLUMN IF EXISTS support_username,
    DROP COLUMN IF EXISTS admin_chat_id,
    DROP COLUMN IF EXISTS admin_topic_id,
    DROP COLUMN IF EXISTS notification_group_id,
    DROP COLUMN IF EXISTS notification_topic_id,
    DROP COLUMN IF EXISTS card_receipt_topic_id,
    DROP COLUMN IF EXISTS zarinpal_merchant_id,
    DROP COLUMN IF EXISTS zarinpal_sandbox;
```

#### Step 4.2: Update Models

```python
# app/database/models.py

class Bot(Base):
    __tablename__ = "bots"
    
    # ✅ Identity
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    telegram_bot_token = Column(String(255), unique=True, nullable=False, index=True)
    api_token = Column(String(255), unique=True, nullable=False)
    api_token_hash = Column(String(128), nullable=False, index=True)
    is_master = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # ✅ Billing
    wallet_balance_toman = Column(BigInteger, default=0, nullable=False)
    traffic_consumed_bytes = Column(BigInteger, default=0, nullable=False)
    traffic_sold_bytes = Column(BigInteger, default=0, nullable=False)
    
    # ✅ Metadata
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # ❌ حذف شده:
    # - card_to_card_enabled → bot_feature_flags
    # - zarinpal_enabled → bot_feature_flags
    # - default_language → bot_configurations
    # - support_username → bot_configurations
    # - admin_chat_id → bot_configurations
    # - admin_topic_id → bot_configurations
    # - notification_group_id → bot_configurations
    # - notification_topic_id → bot_configurations
    # - card_receipt_topic_id → bot_configurations
    # - zarinpal_merchant_id → bot_configurations
    # - zarinpal_sandbox → bot_configurations
```

#### Step 4.3: Update BotConfigService (حذف Fallback)

```python
# app/services/bot_config_service.py

class BotConfigService:
    """
    بعد از Phase 4، دیگر fallback به bots table نداریم
    """
    
    @staticmethod
    async def get_feature_enabled(
        db: AsyncSession,
        bot_id: int,
        feature_key: str
    ) -> bool:
        """فقط از bot_feature_flags می‌خواند"""
        flag = await get_feature_flag(db, bot_id, feature_key)
        return flag.enabled if flag else False
    
    @staticmethod
    async def get_config_value(
        db: AsyncSession,
        bot_id: int,
        config_key: str
    ) -> Optional[Any]:
        """فقط از bot_configurations می‌خواند"""
        config = await get_configuration(db, bot_id, config_key)
        return config.config_value if config else None
    
    # set_feature_enabled و set_config_value هم ساده می‌شوند
    # دیگر نیازی به update کردن bots table نیست
```

---

## 📊 Schema نهایی (بعد از Refactoring)

### `bots` Table (فقط Identity + Billing)

```sql
CREATE TABLE bots (
    -- Identity
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    telegram_bot_token VARCHAR(255) UNIQUE NOT NULL,
    api_token VARCHAR(255) UNIQUE NOT NULL,
    api_token_hash VARCHAR(128) NOT NULL,
    is_master BOOLEAN DEFAULT FALSE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    
    -- Billing
    wallet_balance_toman BIGINT DEFAULT 0 NOT NULL,
    traffic_consumed_bytes BIGINT DEFAULT 0 NOT NULL,
    traffic_sold_bytes BIGINT DEFAULT 0 NOT NULL,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);
```

### `bot_feature_flags` Table (تمام Feature Flags)

```sql
CREATE TABLE bot_feature_flags (
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT FALSE NOT NULL,
    config JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    
    PRIMARY KEY (bot_id, feature_key)
);
```

### `bot_configurations` Table (تمام Configs)

```sql
CREATE TABLE bot_configurations (
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    config_key VARCHAR(100) NOT NULL,
    config_value JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    
    PRIMARY KEY (bot_id, config_key)
);
```

---

## ✅ چک‌لیست Refactoring

### Phase 1: آماده‌سازی
- [ ] ایجاد `BotConfigService` با backward compatibility
- [ ] تست Service با داده‌های موجود
- [ ] مستندسازی Service

### Phase 2: Migration
- [ ] نوشتن migration script
- [ ] اجرای migration روی dev database
- [ ] نوشتن verification script
- [ ] اجرای verification
- [ ] تست backward compatibility

### Phase 3: Update Code
- [ ] پیدا کردن تمام استفاده‌ها از `bot.card_to_card_enabled`
- [ ] پیدا کردن تمام استفاده‌ها از `bot.zarinpal_enabled`
- [ ] پیدا کردن تمام استفاده‌ها از `bot.default_language`
- [ ] پیدا کردن تمام استفاده‌ها از سایر redundant columns
- [ ] جایگزینی با `BotConfigService`
- [ ] تست کامل

### Phase 4: حذف Columns
- [ ] نوشتن migration برای حذف columns
- [ ] اجرای migration روی dev
- [ ] Update models
- [ ] Update BotConfigService (حذف fallback)
- [ ] تست کامل
- [ ] اجرای migration روی production

---

## 🎯 مزایای این رویکرد

1. **✅ Single Source of Truth**: هر config فقط در یک جا
2. **✅ No Data Loss**: Migration با backward compatibility
3. **✅ Incremental**: می‌توانیم مرحله به مرحله پیش برویم
4. **✅ Testable**: هر phase قابل تست است
5. **✅ Rollback Safe**: می‌توانیم به عقب برگردیم
6. **✅ Clean Code**: کد ساده‌تر و قابل نگهداری‌تر

---

## ⚠️ نکات مهم

1. **هرگز مستقیماً به `bot.card_to_card_enabled` دسترسی ندهید**
   - همیشه از `BotConfigService` استفاده کنید

2. **Migration را روی dev تست کنید**
   - قبل از production، حتماً روی dev اجرا کنید

3. **Backup بگیرید**
   - قبل از Phase 4، حتماً backup بگیرید

4. **Monitoring**
   - بعد از هر phase، monitoring کنید

---

## 📝 خلاصه تغییرات

| Phase | تغییرات | زمان تخمینی | ریسک |
|-------|---------|------------|------|
| Phase 1 | ایجاد Service | 2-3 ساعت | کم |
| Phase 2 | Migration Data | 1-2 ساعت | متوسط |
| Phase 3 | Update Code | 4-6 ساعت | متوسط |
| Phase 4 | حذف Columns | 1-2 ساعت | بالا |

**جمع کل:** 8-13 ساعت

---

**آخرین به‌روزرسانی:** 2025-12-15  
**نسخه:** 1.0

