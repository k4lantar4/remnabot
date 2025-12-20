# 🎯 راهنمای اصلی پیاده‌سازی Multi-Tenant

**تاریخ:** 2025-12-15  
**وضعیت:** Master Document - منبع اصلی  
**اولویت:** ⚠️ CRITICAL - این سند را بخوانید!

---

## 📋 وضعیت فعلی (Current State)

### ✅ چه چیزهایی پیاده شده:

1. **Database Models** ✅
   - `Bot`, `BotFeatureFlag`, `BotConfiguration` و سایر models
   - فایل: `app/database/models.py` (خطوط 33-206)

2. **CRUD Operations** ✅
   - `app/database/crud/bot.py`
   - `app/database/crud/bot_feature_flag.py`
   - `app/database/crud/bot_configuration.py`

3. **Middleware** ✅
   - `app/middlewares/bot_context.py` - Bot context injection

4. **Multi-Bot Support** ✅
   - `app/bot.py` - `initialize_all_bots()` function
   - `main.py` - Multi-bot initialization (خطوط 186-203)

5. **Migration File** ✅
   - `migrations/001_create_multi_tenant_tables.sql`

### ❌ چه چیزهایی پیاده نشده:

1. **BotConfigService** ❌
   - Service layer برای دسترسی یکپارچه به configs وجود ندارد

2. **Handler Updates** ❌
   - اکثر handlers هنوز `bot_id` filter ندارند
   - هنوز از `settings.*` استفاده می‌کنند (باید از Service استفاده کنند)

3. **Schema Refactoring** ❌
   - Redundant columns در `bots` table هنوز وجود دارند
   - باید حذف شوند

4. **User Model Update** ⚠️
   - `bot_id` اضافه شده اما هنوز `nullable=True` است
   - باید بعد از migration به `NOT NULL` تغییر کند

---

## 🚨 مشکلات بحرانی که باید فوراً حل شوند

### 1. ❌ REDUNDANCY در Schema

**مشکل:**
```python
# ❌ در bots table (خطوط 48-63)
card_to_card_enabled = Column(Boolean, ...)  # باید در bot_feature_flags باشد
zarinpal_enabled = Column(Boolean, ...)      # باید در bot_feature_flags باشد
default_language = Column(String, ...)       # باید در bot_configurations باشد
support_username = Column(String, ...)       # باید در bot_configurations باشد
# ... و 7 مورد دیگر
```

**راهکار:** طبق `docs/analysis/redundancy-analysis-and-refactoring-plan.md`

---

### 2. ❌ Missing BotConfigService

**مشکل:** کدها مستقیماً به `bot.card_to_card_enabled` دسترسی دارند.

**راهکار:** ایجاد `app/services/bot_config_service.py`

---

### 3. ❌ Missing bot_id Filters

**مشکل:** اکثر queries بدون `bot_id` filter هستند.

**مثال:**
```python
# ❌ بد
async def get_user_by_id(db, user_id):
    return await db.execute(select(User).where(User.id == user_id))

# ✅ خوب
async def get_user_by_id(db, user_id, bot_id):
    return await db.execute(
        select(User).where(User.id == user_id, User.bot_id == bot_id)
    )
```

---

## 📅 برنامه پیاده‌سازی (Implementation Roadmap)

### Phase 0: آماده‌سازی (1-2 روز)

**هدف:** پاکسازی و آماده‌سازی

#### Task 0.1: ایجاد BotConfigService
- [ ] ایجاد `app/services/bot_config_service.py`
- [ ] پیاده‌سازی `get_feature_enabled()`
- [ ] پیاده‌سازی `get_config()`
- [ ] پیاده‌سازی `set_feature_enabled()`
- [ ] پیاده‌سازی `set_config()`
- [ ] تست Service

**فایل مرجع:** `docs/implementation-guide-step-by-step.md` (Step 2)

---

### Phase 1: Schema Refactoring (2-3 روز)

**هدف:** حذف redundancy و clean schema

#### Task 1.1: Migration برای حذف Redundant Columns
- [ ] ایجاد migration script
- [ ] انتقال داده‌ها از `bots` به `bot_feature_flags`/`bot_configurations`
- [ ] حذف columns از `bots` table
- [ ] Update models
- [ ] تست migration

**فایل مرجع:** `docs/analysis/redundancy-analysis-and-refactoring-plan.md` (Phase 2-4)

---

### Phase 2: CRUD Updates (3-4 روز)

**هدف:** اضافه کردن `bot_id` filter به تمام queries

#### Task 2.1: Update User CRUD
- [ ] `get_user_by_id()` - اضافه کردن `bot_id` parameter
- [ ] `get_user_by_telegram_id()` - اضافه کردن `bot_id` filter
- [ ] `get_user_by_username()` - اضافه کردن `bot_id` filter
- [ ] `create_user()` - اضافه کردن `bot_id` parameter
- [ ] تست تمام functions

**فایل:** `app/database/crud/user.py`

#### Task 2.2: Update Subscription CRUD
- [ ] اضافه کردن `bot_id` به تمام queries
- [ ] تست

**فایل:** `app/database/crud/subscription.py`

#### Task 2.3: Update Transaction CRUD
- [ ] اضافه کردن `bot_id` به تمام queries
- [ ] تست

**فایل:** `app/database/crud/transaction.py`

#### Task 2.4: Update سایر CRUD Files
- [ ] `ticket.py`
- [ ] `promocode.py`
- [ ] `promo_group.py`
- [ ] تمام payment CRUD files

---

### Phase 3: Handler Updates (5-7 روز)

**هدف:** Update handlers برای استفاده از `bot_id` و Service

#### Task 3.1: Update Start Handler
- [ ] دریافت `bot_id` از middleware
- [ ] استفاده از `BotConfigService` برای configs
- [ ] استفاده از `TenantFeatureService` برای feature flags
- [ ] تست

**فایل:** `app/handlers/start.py`

#### Task 3.2: Update Menu Handlers
- [ ] اضافه کردن `bot_id` filter
- [ ] استفاده از Service برای configs
- [ ] تست

**فایل:** `app/handlers/menu.py`

#### Task 3.3: Update Payment Handlers
- [ ] اضافه کردن `bot_id` filter
- [ ] استفاده از feature flags
- [ ] تست

**فایل:** `app/handlers/balance/*.py`

#### Task 3.4: Update سایر Handlers
- [ ] `subscription/*.py`
- [ ] `promocode.py`
- [ ] `support/*.py`
- [ ] و سایر handlers

---

### Phase 4: Testing & Validation (2-3 روز)

**هدف:** تست کامل و validation

#### Task 4.1: Unit Tests
- [ ] تست BotConfigService
- [ ] تست CRUD operations
- [ ] تست handlers

#### Task 4.2: Integration Tests
- [ ] تست isolation (tenant A نمی‌تواند به tenant B دسترسی داشته باشد)
- [ ] تست feature flags
- [ ] تست configurations

#### Task 4.3: Manual Testing
- [ ] تست registration flow
- [ ] تست payment flows
- [ ] تست admin panel

---

### Phase 5: Feature Flags & Tenant Management (Future Enhancement)

**هدف:** پیاده‌سازی سیستم مدیریت Feature Flags و Tenant Subscription Plans

> **نکته:** این Phase برای آینده است و بعد از تکمیل Phase 0-4 باید پیاده‌سازی شود.

#### 5.1. Feature Flag Extraction System

**هدف:** استخراج خودکار Feature Flags از `.env.example`

**Tasks:**
- [ ] ایجاد `app/services/feature_flag_extractor.py`
- [ ] تعریف `FEATURE_FLAG_PATTERNS` برای mapping
- [ ] پیاده‌سازی `extract_feature_flags_from_env()`
- [ ] ایجاد feature flag categories (payment_gateways, payment_methods, etc.)

**Database Schema:**
```sql
-- Subscription Plan Tiers for Tenants
CREATE TABLE tenant_subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    monthly_price_kopeks INTEGER NOT NULL,
    activation_fee_kopeks INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Feature Grants per Plan Tier
CREATE TABLE plan_feature_grants (
    plan_tier_id INTEGER NOT NULL REFERENCES tenant_subscription_plans(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT FALSE NOT NULL,
    config_override JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (plan_tier_id, feature_key)
);

-- Tenant Subscriptions (to platform)
CREATE TABLE tenant_subscriptions (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    plan_tier_id INTEGER NOT NULL REFERENCES tenant_subscription_plans(id),
    status VARCHAR(20) DEFAULT 'active',
    start_date TIMESTAMP DEFAULT NOW(),
    end_date TIMESTAMP,
    auto_renewal BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(bot_id)
);
```

#### 5.2. Registration Flow with Activation Fee

**هدف:** ثبت‌نام خودکار tenant با پرداخت activation fee

**Tasks:**
- [ ] ایجاد FSM states برای registration (`TenantRegistrationState`)
- [ ] ایجاد registration handlers
- [ ] پیاده‌سازی config cloning service
- [ ] ایجاد payment processing برای activation fee
- [ ] Generate API tokens

**Registration Flow:**
```
User → /register_tenant
  ↓
Enter Bot Name
  ↓
Enter Telegram Bot Token
  ↓
Select Language
  ↓
Enter Support Username (optional)
  ↓
Select Subscription Plan
  ↓
Pay Activation Fee
  ↓
Bot Created → API Token Generated
  ↓
Send Confirmation with API Token
```

#### 5.3. Tenant Admin Dashboard

**هدف:** پنل مدیریت برای tenant admin با دسترسی محدود

**Tasks:**
- [ ] ایجاد permission system (`TENANT_ADMIN_PERMISSIONS`)
- [ ] ایجاد tenant admin handlers
- [ ] پیاده‌سازی statistics queries (filtered by bot_id)
- [ ] ایجاد plan management UI
- [ ] ایجاد traffic/revenue views

**Permissions:**
- ✅ View statistics, users, subscriptions, transactions
- ✅ Manage plans, pricing, payment cards, payment gateways
- ❌ Manage feature flags (master admin only)
- ❌ Manage remnawave (master admin only)

#### 5.4. Master Admin Control Panel

**هدف:** کنترل کامل feature flags توسط master admin

**Tasks:**
- [ ] ایجاد feature flag management handlers
- [ ] ایجاد tenant management handlers
- [ ] ایجاد plan management handlers
- [ ] پیاده‌سازی override system

**مستندات کامل:** برای جزئیات بیشتر، به `docs/feature-flags-and-tenant-management-design.md` مراجعه کنید.

---

## 📁 ساختار فایل‌های مهم

### مستندات (فقط اینها را بخوانید):

1. **این فایل** ⭐
   - `docs/MASTER-IMPLEMENTATION-GUIDE.md` - راهنمای اصلی

2. **طراحی:**
   - `docs/analysis/redundancy-analysis-and-refactoring-plan.md` - تحلیل redundancy
   - `docs/implementation-guide-step-by-step.md` - راهنمای مرحله‌به‌مرحله

3. **مرجع:**
   - `docs/tenant-configs-categorization.md` - دسته‌بندی configs
   - `docs/tenant-bots-callback-handler-mapping.md` - Mapping callbacks

### فایل‌های کد:

```
app/
├── database/
│   ├── models.py              ✅ Models اضافه شده
│   └── crud/
│       ├── bot.py             ✅
│       ├── bot_feature_flag.py ✅
│       ├── bot_configuration.py ✅
│       ├── user.py            ⚠️ نیاز به update
│       ├── subscription.py    ⚠️ نیاز به update
│       └── ...
├── middlewares/
│   └── bot_context.py         ✅
├── services/
│   ├── bot_config_service.py  ❌ باید ایجاد شود
│   └── tenant_feature_service.py ✅ (موجود است)
└── handlers/
    ├── start.py               ⚠️ نیاز به update
    └── ...
```

---

## 🎯 شروع کار (Quick Start)

### گام 1: ایجاد BotConfigService

```bash
# ایجاد فایل
touch app/services/bot_config_service.py
```

کد را از `docs/implementation-guide-step-by-step.md` (Step 2) کپی کنید.

### گام 2: تست Service

```python
# tests/test_bot_config_service.py
async def test_get_feature_enabled():
    # Test code
    pass
```

### گام 3: Update یک Handler

```python
# app/handlers/start.py
from app.services.bot_config_service import BotConfigService

async def handle_start(message, bot_id, db):
    # استفاده از Service
    default_lang = await BotConfigService.get_config(
        db, bot_id, 'DEFAULT_LANGUAGE', default='fa'
    )
    # ...
```

---

## ⚠️ قوانین طلایی (Golden Rules)

### 1. همیشه bot_id را فیلتر کنید
```python
# ❌ هرگز این کار را نکنید
query = select(User).where(User.id == user_id)

# ✅ همیشه این کار را انجام دهید
query = select(User).where(
    User.id == user_id,
    User.bot_id == bot_id  # ✅ Isolation
)
```

### 2. همیشه از Service استفاده کنید
```python
# ❌ هرگز این کار را نکنید
if bot.card_to_card_enabled:
    # ...

# ✅ همیشه این کار را انجام دهید
if await BotConfigService.is_feature_enabled(db, bot_id, 'card_to_card'):
    # ...
```

### 3. هرگز مستقیماً به bots table برای configs دسترسی ندهید
```python
# ❌ بد
default_lang = bot.default_language

# ✅ خوب
default_lang = await BotConfigService.get_config(
    db, bot_id, 'DEFAULT_LANGUAGE', default='fa'
)
```

---

## 📊 چک‌لیست پیشرفت

### Phase 0: آماده‌سازی
- [ ] BotConfigService ایجاد شده
- [ ] Tests نوشته شده
- [ ] مستندسازی کامل

### Phase 1: Schema Refactoring
- [ ] Migration script ایجاد شده
- [ ] داده‌ها migrate شده‌اند
- [ ] Columns حذف شده‌اند
- [ ] Models update شده‌اند

### Phase 2: CRUD Updates
- [ ] User CRUD update شده
- [ ] Subscription CRUD update شده
- [ ] Transaction CRUD update شده
- [ ] سایر CRUD files update شده‌اند

### Phase 3: Handler Updates
- [ ] Start handler update شده
- [ ] Menu handlers update شده‌اند
- [ ] Payment handlers update شده‌اند
- [ ] سایر handlers update شده‌اند

### Phase 4: Testing
- [ ] Unit tests نوشته شده
- [ ] Integration tests نوشته شده
- [ ] Manual testing انجام شده

---

## 🔗 لینک‌های مفید

### مستندات اصلی:
- `docs/MASTER-IMPLEMENTATION-GUIDE.md` ⭐ (این فایل)
- `docs/analysis/redundancy-analysis-and-refactoring-plan.md`
- `docs/implementation-guide-step-by-step.md`

### مستندات مرجع:
- `docs/tenant-configs-categorization.md`
- `docs/tenant-bots-callback-handler-mapping.md`

### مستندات قدیمی (می‌توانید نادیده بگیرید):
- `docs/multi-tenant-design-document.md` (قدیمی - استفاده نکنید)
- `docs/multi-tenant-migration-plan.md` (قدیمی - استفاده نکنید)
- `docs/multi-tenant/` (بسیاری از اینها قدیمی هستند)

---

## ❓ سوالات متداول

### Q: از کجا شروع کنم؟
**A:** از Phase 0 شروع کنید - ایجاد BotConfigService

### Q: کدام مستندات را بخوانم؟
**A:** فقط این فایل و `docs/analysis/redundancy-analysis-and-refactoring-plan.md`

### Q: آیا باید همه handlers را یکجا update کنم؟
**A:** خیر، مرحله‌به‌مرحله پیش بروید. اول یک handler را کامل کنید و تست کنید.

### Q: اگر مشکلی پیش آمد چه کنم؟
**A:** به `docs/analysis/comprehensive-code-review.md` مراجعه کنید.

---

## 📝 یادداشت‌های مهم

1. **هرگز مستقیماً به `bot.card_to_card_enabled` دسترسی ندهید**
   - همیشه از `BotConfigService` استفاده کنید

2. **هرگز query بدون `bot_id` filter ننویسید**
   - این isolation را می‌شکند

3. **قبل از commit، isolation را تست کنید**
   - مطمئن شوید tenant A نمی‌تواند به tenant B دسترسی داشته باشد

---

**آخرین به‌روزرسانی:** 2025-12-15  
**نسخه:** 1.0  
**وضعیت:** Master Document - منبع اصلی

