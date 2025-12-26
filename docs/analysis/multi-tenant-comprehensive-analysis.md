# تحلیل جامع Multi-Tenant و طراحی ریفکتور

**تاریخ:** 2025-12-15  
**نسخه:** 1.0  
**وضعیت:** در انتظار بررسی و تایید

---

## 📋 فهرست مطالب

1. [خلاصه اجرایی](#خلاصه-اجرایی)
2. [تحلیل وضعیت فعلی](#تحلیل-وضعیت-فعلی)
3. [نقشه کامل کامپوننت‌ها](#نقشه-کامل-کامپوننت‌ها)
4. [جریان داده (Data Flows)](#جریان-داده)
5. [تفکیک قابلیت‌ها - Master vs Tenant](#تفکیک-قابلیت‌ها)
6. [مشکلات شناسایی شده](#مشکلات-شناسایی-شده)
7. [برنامه ریفکتور پیشنهادی](#برنامه-ریفکتور-پیشنهادی)
8. [چک‌لیست تغییرات](#چک‌لیست-تغییرات)

---

## 📊 خلاصه اجرایی

### وضعیت پروژه
- **برنچ:** `feat/payments`
- **Phase 1 (Foundation):** ✅ 100% تکمیل شده
- **Phase 2-6:** ⚠️ 55-70% - نیاز به تکمیل
- **امتیاز کلی:** 68%

### مشکلات اصلی شناسایی شده
1. ❌ **عدم Isolation در Admin Handlers** - ادمین می‌تواند داده‌های همه tenant ها را ببیند
2. ❌ **عدم Isolation در Web API** - API routes بدون `bot_id` filtering
3. ⚠️ **CRUD با bot_id اختیاری** - ریسک نقض isolation
4. ⚠️ **Feature Flags استفاده نشده** - handlers هنوز از `settings` استفاده می‌کنند
5. ⚠️ **بدهی فنی در حال افزایش** - تغییرات بدون برنامه دقیق

### پیشنهاد کلی
قبل از ادامه پیاده‌سازی، نیاز به:
1. 🔴 **توقف تغییرات جدید** تا تکمیل تحلیل
2. 🔴 **بازنگری و اصلاح کد موجود** بر اساس این سند
3. 🟡 **ایجاد تست‌های Isolation** قبل از هر تغییر

---

## 🏗️ تحلیل وضعیت فعلی

### 1. Database Layer (✅ خوب)

| کامپوننت | وضعیت | توضیحات |
|----------|-------|---------|
| Migration Script | ✅ | 7 جدول جدید ایجاد شده |
| Models | ✅ | 7 مدل جدید + 6 مدل به‌روزرسانی شده |
| Bot CRUD | ✅ | کامل و تست شده |
| Feature Flag CRUD | ✅ | کامل و تست شده |
| Configuration CRUD | ✅ | کامل و تست شده |
| Payment Card CRUD | ✅ | با rotation logic |

### 2. Middleware Layer (⚠️ نیاز به بهبود)

| کامپوننت | وضعیت | مشکل |
|----------|-------|------|
| BotContextMiddleware | ⚠️ 75% | اگر bot پیدا نشود، handler بدون bot_id اجرا می‌شود |
| AuthMiddleware | ⚠️ | نیاز به تطبیق با multi-tenant |

### 3. Handler Layer (❌ مشکل‌دار)

| گروه Handler | وضعیت | مشکل اصلی |
|--------------|-------|-----------|
| Start Handler | ⚠️ 75% | برخی functions بدون bot_id |
| Admin Handlers | ❌ 55% | نقض کامل isolation |
| Balance Handlers | ⚠️ 60% | card_to_card ناقص |
| Subscription Handlers | ⚠️ 65% | نیاز به bot_id در همه queries |
| Payment Handlers | ⚠️ 60% | ترکیب settings و feature flags |

### 4. Service Layer (⚠️ نیاز به بهبود)

| سرویس | وضعیت | نیاز |
|-------|-------|------|
| TenantFeatureService | ✅ | کامل با caching |
| SubscriptionService | ⚠️ | نیاز به bot_id در همه methods |
| PaymentService | ⚠️ | نیاز به تفکیک per-tenant |
| Other Services | ❌ | context-aware نیستند |

---

## 🗺️ نقشه کامل کامپوننت‌ها

### Handlers Structure

```
app/handlers/
├── admin/                          # 33 فایل - نیاز به bot_id در همه
│   ├── main.py                     # ورودی اصلی ادمین
│   ├── users.py                    # ❌ بدون bot_id filter
│   ├── messages.py                 # ❌ get_target_users بدون bot_id
│   ├── subscriptions.py            # ❌ نیاز به bot_id
│   ├── promocodes.py               # ❌ نیاز به bot_id
│   ├── promo_groups.py             # ❌ نیاز به bot_id
│   ├── campaigns.py                # ❌ نیاز به bot_id
│   ├── tenant_bots.py              # ✅ جدید - مدیریت bots
│   ├── bot_configuration.py        # ⚠️ نیاز به بررسی
│   ├── statistics.py               # ❌ آمار همه bots مخلوط
│   ├── reports.py                  # ❌ گزارش‌ها بدون isolation
│   ├── referrals.py                # ❌ نیاز به bot_id
│   ├── trials.py                   # ⚠️ نیاز به بررسی
│   ├── pricing.py                  # ⚠️ فعلاً global - نیاز به تصمیم
│   ├── servers.py                  # ⚠️ servers shared یا per-tenant؟
│   ├── tickets.py                  # ❌ نیاز به bot_id
│   └── ...
│
├── balance/                        # 12 فایل - payment handlers
│   ├── main.py                     # ورودی اصلی
│   ├── card_to_card.py             # ⚠️ جدید - نیاز به تکمیل
│   ├── cryptobot.py                # ⚠️ نیاز به feature flag check
│   ├── yookassa.py                 # ⚠️ نیاز به feature flag check
│   ├── stars.py                    # ⚠️ نیاز به feature flag check
│   ├── heleket.py                  # ⚠️ نیاز به feature flag check
│   ├── pal24.py                    # ⚠️ نیاز به feature flag check
│   └── ...
│
├── subscription/                   # 13 فایل
│   ├── purchase.py                 # ⚠️ نیاز به bot_id در transactions
│   ├── pricing.py                  # ⚠️ prices per-tenant یا global؟
│   ├── autopay.py                  # ⚠️ نیاز به بررسی
│   └── ...
│
├── start.py                        # ⚠️ 75% - نیاز به تکمیل
├── menu.py                         # ⚠️ نیاز به feature flag checks
├── referral.py                     # ⚠️ نیاز به bot_id
├── promocode.py                    # ⚠️ نیاز به bot_id
├── tickets.py                      # ⚠️ نیاز به bot_id
├── support.py                      # ⚠️ نیاز به bot_id
└── ...
```

### States Structure

```
app/states.py
├── RegistrationStates              # ثبت‌نام کاربر
├── SubscriptionStates              # خرید اشتراک
├── BalanceStates                   # شارژ موجودی
├── PromoCodeStates                 # کد تخفیف
├── AdminStates                     # پنل ادمین (شامل tenant bots)
├── SupportStates                   # پشتیبانی
├── TicketStates                    # تیکت کاربر
├── AdminTicketStates               # تیکت ادمین
├── BotConfigStates                 # تنظیمات bot
├── PricingStates                   # قیمت‌گذاری
├── AutoPayStates                   # پرداخت خودکار
└── ...
```

### Keyboards Structure

```
app/keyboards/
├── admin.py                        # کیبوردهای ادمین
│   └── نیاز به: بررسی دکمه‌های مرتبط با tenant
├── inline.py                       # کیبوردهای inline
│   └── نیاز به: feature-flag based rendering
└── reply.py                        # کیبوردهای reply
    └── نیاز به: feature-flag based rendering
```

### Services Structure

```
app/services/
├── tenant_feature_service.py       # ✅ سرویس feature flags
├── subscription_service.py         # ⚠️ نیاز به bot_id
├── subscription_purchase_service.py # ⚠️ نیاز به bot_id
├── subscription_checkout_service.py # ⚠️ نیاز به bot_id
├── payment_service.py              # ⚠️ نیاز به per-tenant config
├── payment_verification_service.py # ⚠️ نیاز به bot_id
├── referral_service.py             # ⚠️ نیاز به bot_id
├── promocode_service.py            # ⚠️ نیاز به bot_id
├── broadcast_service.py            # ❌ باید per-tenant باشد
├── campaign_service.py             # ⚠️ campaigns per-tenant؟
├── reporting_service.py            # ❌ باید per-tenant باشد
├── user_service.py                 # ⚠️ نیاز به bot_id
└── ...
```

---

## 🔄 جریان داده (Data Flows)

### 1. Flow ثبت‌نام کاربر جدید

```
User Message (/start)
    ↓
[BotContextMiddleware] → Inject bot_id, bot_config
    ↓
[AuthMiddleware] → Check/Create User
    ↓                   ⚠️ مشکل: create_user باید bot_id داشته باشد
[Start Handler]
    ↓
create_user(db, telegram_id, bot_id=bot_id)  ← نیاز به اصلاح
    ↓
User Record با bot_id
```

### 2. Flow خرید اشتراک

```
User: انتخاب خرید
    ↓
[subscription/purchase.py]
    ↓
get_available_plans(db, bot_id)              ← نیاز: bot_plans vs global plans
    ↓
User: انتخاب پلن + پرداخت
    ↓
[balance/handler.py]
    ↓
check_feature_enabled(db, bot_id, 'stars')   ← نیاز: feature flag check
    ↓
create_transaction(db, user_id, bot_id, ...)
    ↓
create_subscription(db, user_id, bot_id, ...)
```

### 3. Flow پرداخت Card-to-Card (جدید)

```
User: انتخاب پرداخت کارت به کارت
    ↓
[check feature flag: card_to_card]
    ↓
get_next_card_for_rotation(db, bot_id, strategy)
    ↓
نمایش اطلاعات کارت به کاربر
    ↓
User: ارسال رسید
    ↓
create_card_payment(db, bot_id, user_id, ...)
    ↓
send_notification_to_admin(bot_config.admin_chat_id)
    ↓
Admin: تایید/رد
    ↓
complete_transaction() / reject_payment()
```

### 4. Flow پنل ادمین (مشکل‌دار)

```
Admin: /admin
    ↓
[Admin Main Menu]
    ↓
Admin: لیست کاربران
    ↓
get_users_list(db)  ← ❌ مشکل: بدون bot_id - همه کاربران نمایش داده می‌شود!
    ↓
باید باشد: get_users_list(db, bot_id=bot_id)
```

---

## 🔀 تفکیک قابلیت‌ها - Master vs Tenant

### دسته‌بندی قابلیت‌ها

#### 1. قابلیت‌های فقط Master Bot (در Enum باقی بماند)

| قابلیت | توضیح |
|--------|-------|
| `TENANT_MANAGEMENT` | مدیریت و ایجاد tenant bots |
| `GLOBAL_STATISTICS` | آمار کلی سیستم |
| `SYSTEM_SETTINGS` | تنظیمات سیستمی |
| `DATABASE_BACKUP` | پشتیبان‌گیری |
| `SYSTEM_LOGS` | لاگ‌های سیستم |
| `SERVER_MANAGEMENT` | مدیریت سرورهای Remnawave |
| `GLOBAL_PRICING` | قیمت‌گذاری پایه (که tenants می‌توانند override کنند) |
| `BILLING_TENANTS` | صورتحساب و کیف پول tenants |

#### 2. قابلیت‌های قابل شخصی‌سازی Tenant (به Database منتقل شود)

| قابلیت | Feature Flag Key | Config Options |
|--------|------------------|----------------|
| **Payment Methods** | | |
| Telegram Stars | `telegram_stars` | `enabled`, `min_amount`, `max_amount` |
| YooKassa | `yookassa` | `enabled`, `shop_id`, `secret_key` |
| CryptoBot | `cryptobot` | `enabled`, `token` |
| Card-to-Card | `card_to_card` | `enabled`, `cards[]`, `rotation_strategy` |
| Zarinpal | `zarinpal` | `enabled`, `merchant_id`, `sandbox` |
| Heleket | `heleket` | `enabled`, `api_key` |
| PAL24 | `pal24` | `enabled`, `api_key` |
| **Features** | | |
| Referral Program | `referral` | `enabled`, `bonus_percent`, `max_level` |
| Trial | `trial` | `enabled`, `days`, `traffic_gb`, `one_time` |
| PromoCode | `promocode` | `enabled` |
| Support Chat | `support_chat` | `enabled`, `username` |
| Ticket System | `tickets` | `enabled`, `admin_group_id` |
| AutoPay | `autopay` | `enabled`, `min_days` |
| **Branding** | | |
| Bot Name | config | `bot_name` |
| Welcome Message | config | `welcome_text` |
| Default Language | config | `default_language` |
| Rules | config | `rules_text` |
| Privacy Policy | config | `privacy_policy` |
| Public Offer | config | `public_offer` |
| FAQ | config | `faq_items[]` |
| **Notifications** | | |
| Admin Notifications | config | `admin_chat_id`, `admin_topic_id` |
| User Notifications | config | `notification_settings{}` |

#### 3. قابلیت‌های مشترک و تصمیمات تایید شده

| قابلیت | مدل | توضیح |
|--------|-----|-------|
| **Servers/Squads** | ✅ **Shared** | سرورها متعلق به Master - مشترک بین همه Tenants |
| **Inbounds** | ✅ **Shared** | از Remnawave API |
| **Plans** | ✅ **Per-Tenant** | هر Tenant پلن‌های دلخواه خودش را دارد |
| **Pricing** | ✅ **Per-Tenant** | هر Tenant قیمت‌گذاری دلخواه خودش را دارد |
| **PromoGroups** | ✅ **Per-Tenant** | هر Tenant گروه‌های تخفیف خودش را مدیریت می‌کند |
| **Campaigns** | ✅ **Per-Tenant** | هر Tenant کمپین‌های خودش را دارد |

#### مدل بیلینگ (تایید شده)

```
┌──────────────────────────────────────────────────────────────┐
│                     Master Bot                                │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              Shared Servers (Remnawave)               │    │
│  │  تعرفه: X تومان / هر GB                               │    │
│  └──────────────────────────────────────────────────────┘    │
│                           │                                   │
│         ┌─────────────────┼─────────────────┐                 │
│         ▼                 ▼                 ▼                 │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐          │
│  │  Tenant A  │    │  Tenant B  │    │  Tenant C  │          │
│  │ Wallet: 50K│    │ Wallet: 30K│    │ Wallet: 100K│         │
│  │ قیمت فروش: │    │ قیمت فروش: │    │ قیمت فروش: │         │
│  │ دلخواه     │    │ دلخواه     │    │ دلخواه     │         │
│  └────────────┘    └────────────┘    └────────────┘          │
└──────────────────────────────────────────────────────────────┘

Flow:
1. Tenant می‌فروشد → کسر از کیف پول (به نرخ Master)
2. User مصرف می‌کند → کسر از کیف پول Tenant
3. Tenant هر قیمتی می‌خواهد می‌فروشد → سود برای خودش
```

**جزئیات کامل:** [billing-model-design.md](./billing-model-design.md)

---

## ⚠️ مشکلات شناسایی شده

### مشکلات بحرانی (Critical)

#### 1. نقض Isolation در Admin Handlers

**فایل‌ها:**
- `app/handlers/admin/users.py`
- `app/handlers/admin/messages.py`
- `app/handlers/admin/statistics.py`
- `app/handlers/admin/reports.py`

**مشکل:**
```python
# فعلی - اشتباه:
users = await get_users_list(db, limit=50)  # همه کاربران از همه bots!

# صحیح:
users = await get_users_list(db, limit=50, bot_id=bot_id)
```

**تاثیر:** ادمین یک tenant می‌تواند داده‌های همه tenants را ببیند.

---

#### 2. نقض Isolation در Web API

**فایل‌ها:**
- `app/webapi/routes/users.py`
- `app/webapi/routes/subscriptions.py`
- همه routes

**مشکل:**
```python
# فعلی - اشتباه:
@router.get("/users")
async def list_users(db = Depends(get_db)):
    return await get_users_list(db)  # ❌ بدون bot_id

# صحیح:
@router.get("/users")
async def list_users(
    bot_id: int = Depends(get_bot_id_from_api_token),
    db = Depends(get_db)
):
    return await get_users_list(db, bot_id=bot_id)  # ✅
```

---

#### 3. CRUD Functions با Optional bot_id

**فایل‌ها:**
- `app/database/crud/user.py`
- `app/database/crud/subscription.py`
- همه CRUD files

**مشکل:**
```python
# فعلی:
async def get_user_by_telegram_id(db, telegram_id, bot_id=None):  # ⚠️ Optional
    query = select(User).where(User.telegram_id == telegram_id)
    if bot_id:
        query = query.where(User.bot_id == bot_id)
    # اگر bot_id نباشد، اولین user با این telegram_id برمی‌گردد!
```

---

### مشکلات مهم (High Priority)

#### 4. استفاده از Settings به جای Feature Flags

**فایل‌ها:**
- `app/handlers/balance/stars.py`
- `app/handlers/balance/yookassa.py`
- `app/handlers/subscription/autopay.py`
- و غیره

**مشکل:**
```python
# فعلی - اشتباه:
if settings.TELEGRAM_STARS_ENABLED:  # ❌ Global setting
    # ...

# صحیح:
if await TenantFeatureService.is_feature_enabled(db, bot_id, 'telegram_stars'):
    # ...
```

---

#### 5. Keyboards بدون Feature Flag Check

**فایل‌ها:**
- `app/keyboards/inline.py`
- `app/keyboards/reply.py`

**مشکل:** دکمه‌های payment methods و features بدون بررسی feature flags نمایش داده می‌شوند.

```python
# فعلی:
def get_payment_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Stars", callback_data="pay_stars")],  # همیشه نمایش
        [InlineKeyboardButton("YooKassa", callback_data="pay_yookassa")],
    ])

# صحیح:
async def get_payment_keyboard(db, bot_id):
    buttons = []
    if await TenantFeatureService.is_feature_enabled(db, bot_id, 'telegram_stars'):
        buttons.append([InlineKeyboardButton("Stars", callback_data="pay_stars")])
    # ...
```

---

## 📋 برنامه ریفکتور پیشنهادی

### Phase A: Audit & Fix Critical Issues (هفته 1)

#### A.1: ایجاد Isolation Tests
- تست‌های خودکار برای اطمینان از isolation
- هر query باید با bot_id فیلتر شود

#### A.2: Fix Admin Handlers
| فایل | تغییر | اولویت |
|------|-------|--------|
| `admin/users.py` | اضافه کردن bot_id به همه queries | 🔴 |
| `admin/messages.py` | اضافه کردن bot_id به get_target_users | 🔴 |
| `admin/statistics.py` | فیلتر آمار با bot_id | 🔴 |
| `admin/subscriptions.py` | اضافه کردن bot_id | 🔴 |
| `admin/promocodes.py` | اضافه کردن bot_id | 🔴 |

#### A.3: Fix Web API Routes
- ایجاد `get_bot_id_from_api_token` dependency
- اضافه کردن به همه routes

### Phase B: Feature Flags Migration (هفته 2)

#### B.1: Define Feature Flag Keys
```python
# app/constants/features.py
class FeatureFlags:
    TELEGRAM_STARS = "telegram_stars"
    YOOKASSA = "yookassa"
    CRYPTOBOT = "cryptobot"
    CARD_TO_CARD = "card_to_card"
    ZARINPAL = "zarinpal"
    REFERRAL = "referral"
    TRIAL = "trial"
    PROMOCODE = "promocode"
    SUPPORT_CHAT = "support_chat"
    TICKETS = "tickets"
    AUTOPAY = "autopay"
```

#### B.2: Migrate Handlers to Feature Flags
| Handler | Settings Key | Feature Flag |
|---------|--------------|--------------|
| `balance/stars.py` | `TELEGRAM_STARS_ENABLED` | `telegram_stars` |
| `balance/yookassa.py` | `is_yookassa_enabled()` | `yookassa` |
| `balance/cryptobot.py` | `is_cryptobot_enabled()` | `cryptobot` |
| `referral.py` | `REFERRAL_ENABLED` | `referral` |
| `subscription/autopay.py` | `AUTOPAY_ENABLED` | `autopay` |

#### B.3: Update Keyboards
- ایجاد `async get_payment_keyboard(db, bot_id)`
- فیلتر دکمه‌ها بر اساس feature flags

### Phase C: Complete Card-to-Card & Zarinpal (هفته 3)

#### C.1: Complete Card-to-Card Handler
- `app/handlers/balance/card_to_card.py`
- Admin approval/rejection handlers
- Notification system

#### C.2: Implement Zarinpal Handler
- `app/handlers/balance/zarinpal.py`
- Callback handler در Web API

### Phase D: Master Bot Menu & Tenant Registration (هفته 4)

#### D.1: Master Bot Specific Menu
- منوی مدیریت tenants
- ثبت‌نام tenant جدید
- مدیریت بیلینگ tenants

#### D.2: Tenant Registration Flow
```
User → /start در Master Bot
    → انتخاب "ایجاد Bot جدید"
    → ورود Bot Token
    → تنظیم اولیه (نام، زبان، ...)
    → فعال‌سازی Features
    → دریافت API Token
```

---

## ✅ چک‌لیست تغییرات

### Database Layer
- [x] 1.1: Database Schema (7 tables)
- [x] 1.2: Database Models
- [x] 1.3: Bot CRUD
- [x] 1.4: Feature Flag CRUD
- [x] 1.4a: Configuration CRUD
- [x] 1.4b: Payment Card CRUD
- [x] 1.4c: Bot Plans CRUD
- [x] 1.5: Bot Context Middleware
- [ ] 2.1: Make bot_id required in User CRUD
- [ ] 2.2: Make bot_id required in Subscription CRUD
- [ ] 2.3: Make bot_id required in Transaction CRUD
- [ ] 2.4: Card-to-Card Payment CRUD
- [ ] 2.5: Zarinpal Payment CRUD

### Middleware Layer
- [x] Bot Context Middleware
- [ ] Improve error handling (block if bot not found)
- [ ] Add feature flag caching to middleware

### Handler Layer
- [ ] Fix Admin/users.py (add bot_id)
- [ ] Fix Admin/messages.py (add bot_id)
- [ ] Fix Admin/statistics.py (add bot_id)
- [ ] Fix Admin/subscriptions.py (add bot_id)
- [ ] Fix Admin/promocodes.py (add bot_id)
- [ ] Update Start Handler (complete bot_id usage)
- [ ] Complete Card-to-Card Handler
- [ ] Create Zarinpal Handler
- [ ] Migrate all payment handlers to feature flags
- [ ] Create Master Bot specific handlers

### Keyboard Layer
- [ ] Create async keyboard functions
- [ ] Add feature flag checks to all keyboards
- [ ] Create tenant-specific keyboard variants

### Service Layer
- [ ] Update SubscriptionService with bot_id
- [ ] Update PaymentService with bot_id
- [ ] Update all services to be context-aware

### Web API Layer
- [ ] Create get_bot_id_from_api_token dependency
- [ ] Add bot_id to all routes
- [ ] Create Zarinpal callback route

### Testing
- [ ] Create Isolation tests
- [ ] Create Feature Flag tests
- [ ] Create Integration tests for payment flows

---

## 📝 نکات مهم برای توسعه‌دهندگان

### 1. همیشه bot_id را استفاده کنید
```python
# ❌ اشتباه
user = await get_user_by_telegram_id(db, telegram_id)

# ✅ صحیح
user = await get_user_by_telegram_id(db, telegram_id, bot_id=bot_id)
```

### 2. Feature Flags را بررسی کنید
```python
# ❌ اشتباه
if settings.FEATURE_ENABLED:
    ...

# ✅ صحیح
if await TenantFeatureService.is_feature_enabled(db, bot_id, 'feature_key'):
    ...
```

### 3. Keyboard ها را async کنید
```python
# ❌ اشتباه
keyboard = get_static_keyboard()

# ✅ صحیح
keyboard = await get_dynamic_keyboard(db, bot_id)
```

### 4. Tests قبل از Commit
```bash
# اجرای تست‌های isolation
pytest tests/test_multi_tenant_isolation.py

# اجرای تست‌های integration
pytest tests/integration/
```

---

**تاریخ ایجاد:** 2025-12-15  
**آخرین به‌روزرسانی:** 2025-12-15  
**نویسنده:** AI Assistant  
**وضعیت:** Draft - Pending Review

