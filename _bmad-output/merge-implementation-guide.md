# راهنمای کامل پیاده‌سازی مرج upstream/main

**تاریخ:** 2026-01-03  
**تهیه‌کننده:** Scrum Master + Developer Agents  
**وضعیت:** آماده برای اجرا  
**اولویت:** ⚠️ CRITICAL  
**تخمین زمان کل:** 20-26 روز کاری (4-5 هفته)

---

## 📋 خلاصه اجرایی

این سند راهنمای کامل و جامع برای مرج کردن تغییرات `upstream/main` به برنچ فعلی `resolve-adversarial-findings` است. هدف: **فقط قابلیت‌های جدید و فیکس باگ‌ها** را با نهایت دقت و کنترل سازگاری با معماری multi-tenant مرج کنیم.

### آمار کلی تغییرات

| معیار | مقدار | سطح تأثیر |
|-------|-------|-----------|
| **کل فایل‌های تغییر یافته** | 527 | 🔴 بسیار بالا |
| **فایل‌های جدید** | 85 | 🟡 متوسط-بالا |
| **فایل‌های حذف شده** | ~50 | 🟡 متوسط |
| **فایل‌های تغییر یافته** | ~392 | 🔴 بسیار بالا |
| **خطوط اضافه شده** | ~15,000+ | 🔴 بسیار بالا |
| **خطوط حذف شده** | ~8,000+ | 🟡 متوسط |
| **Commits جدید** | 50+ | 🟡 متوسط |
| **قابلیت‌های جدید** | 3 (Cabinet, Nalogo, Modem) | 🔴 بسیار بالا |
| **فیکس باگ‌ها** | 25+ | 🟢 متوسط |

### سطح تأثیر کلی: 🔴 **بسیار بالا (Critical Impact)**

---

## 🎯 استراتژی مرج

### اصول کلی

1. ✅ **فقط قابلیت‌های جدید و فیکس باگ‌ها** - نه refactoring یا تغییرات معماری
2. ✅ **سازگاری کامل با multi-tenant** - تمام تغییرات باید tenant-aware باشند
3. ✅ **پیروی از PRD و Architecture** - هیچ تغییری نباید با مستندات در تضاد باشد
4. ✅ **بررسی تداخل‌ها** - تغییرات در کد فعلی نیاز به بررسی دقیق دارند
5. ✅ **تست کامل** - هر بخش باید جداگانه تست شود
6. ✅ **Incremental Merge** - مرج به صورت phase-by-phase
7. ✅ **Test-Driven** - هر task باید با tests همراه باشد

### مراحل کلی

```
Phase 0: آماده‌سازی و Backup
Phase 1: Core Infrastructure (Config, Models)
Phase 2: Cabinet Module (31 فایل)
Phase 3: CRUD Operations (50+ فایل)
Phase 4: Services (60+ فایل)
Phase 5: Handlers (80+ فایل)
Phase 6: Nalogo Integration (15 فایل)
Phase 7: Bug Fixes (25+ commits)
Phase 8: Testing و Validation
Phase 9: Documentation
```

---

## 🚨 چالش‌های عمیق و راهکارها

### چالش 1: تداخل با Multi-Tenant Architecture ⚠️ CRITICAL

#### مشکل اصلی
- **Upstream:** Single-tenant architecture (همه چیز global)
- **Current Branch:** Multi-tenant architecture (همه چیز tenant-aware)
- **تداخل:** 392 فایل تغییر یافته که نیاز به بررسی tenant compatibility دارند

#### جزئیات فنی

**1.1. JWT Tokens بدون bot_id**
```python
# ❌ Upstream (مشکل)
def create_access_token(user_id: int, telegram_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "telegram_id": telegram_id,
        # ❌ bot_id missing!
    }

# ✅ Current Branch (نیاز)
def create_access_token(user_id: int, telegram_id: int, bot_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "telegram_id": telegram_id,
        "bot_id": bot_id,  # ✅ required
    }
```

**1.2. Database Queries بدون bot_id filter**
```python
# ❌ Upstream (مشکل)
async def get_user_by_telegram_id(db, telegram_id: int):
    return await db.execute(
        select(User).where(User.telegram_id == telegram_id)
        # ❌ bot_id filter missing!
    )

# ✅ Current Branch (نیاز)
async def get_user_by_telegram_id(db, telegram_id: int, bot_id: int):
    return await db.execute(
        select(User).where(
            User.telegram_id == telegram_id,
            User.bot_id == bot_id  # ✅ required
        )
    )
```

**1.3. Redis Keys بدون tenant prefix**
```python
# ❌ Upstream (مشکل)
cache_key = f"cart:{user_id}"  # ❌ global key

# ✅ Current Branch (نیاز)
cache_key = f"cart:{bot_id}:{user_id}"  # ✅ tenant-aware
```

#### راهکار
- ✅ **Manual merge** برای تمام فایل‌های با تداخل
- ✅ **Code review** برای هر فایل
- ✅ **Automated tests** برای tenant isolation
- ✅ **Validation scripts** برای بررسی bot_id در queries

---

### چالش 2: Migration Conflicts ⚠️ HIGH

#### مشکل اصلی
- **Upstream:** Cabinet columns به `users` table اضافه می‌شود
- **Current Branch:** Multi-tenant migrations قبلاً اجرا شده
- **تداخل:** ممکن است migration conflicts ایجاد شود

#### جزئیات فنی

**2.1. Cabinet Columns**
```sql
-- Upstream migration
ALTER TABLE users ADD COLUMN cabinet_email VARCHAR(255);
ALTER TABLE users ADD COLUMN cabinet_email_verified BOOLEAN;
-- ... 5 columns دیگر

-- Current Branch: users table قبلاً bot_id دارد
-- نیاز به merge migration
```

**2.2. Promocode Changes**
```sql
-- Upstream
ALTER TABLE promocodes ADD COLUMN first_purchase_only BOOLEAN;

-- Current Branch: promocodes table قبلاً bot_id دارد
-- نیاز به merge migration
```

#### راهکار
- ✅ **Migration merge** با دقت
- ✅ **Test migration** در staging
- ✅ **Backup** قبل از migration
- ✅ **Rollback plan** آماده

---

### چالش 3: Configuration Management ⚠️ HIGH

#### مشکل اصلی
- **Upstream:** Global config (env variables)
- **Current Branch:** Per-tenant config (bot_configurations table)
- **تداخل:** Cabinet settings باید per-tenant باشند

#### جزئیات فنی

**3.1. Cabinet Settings**
```python
# ❌ Upstream (مشکل)
CABINET_JWT_SECRET = os.getenv("CABINET_JWT_SECRET")  # Global

# ✅ Current Branch (نیاز)
# باید در bot_configurations ذخیره شود
async def get_cabinet_jwt_secret(bot_id: int) -> str:
    config = await get_bot_config(db, bot_id, "cabinet.jwt_secret")
    return config["value"]
```

**3.2. Nalogo Settings**
```python
# ❌ Upstream (مشکل)
NALOGO_API_KEY = os.getenv("NALOGO_API_KEY")  # Global

# ✅ Current Branch (نیاز)
# باید در bot_configurations ذخیره شود
```

#### راهکار
- ✅ **Refactor config access** برای tenant-aware
- ✅ **Migration script** برای تبدیل env → tenant config
- ✅ **Backward compatibility** برای transition period

---

### چالش 4: Dependencies Injection ⚠️ HIGH

#### مشکل اصلی
- **Upstream:** Cabinet routes نیاز به tenant dependency ندارند
- **Current Branch:** تمام routes باید tenant context داشته باشند
- **تداخل:** 31 فایل Cabinet نیاز به refactoring دارند

#### جزئیات فنی

**4.1. Cabinet Dependencies**
```python
# ❌ Upstream (مشکل)
@app.get("/cabinet/info")
async def get_info():
    # ❌ tenant context missing
    pass

# ✅ Current Branch (نیاز)
@app.get("/cabinet/info")
async def get_info(
    bot_id: int = Depends(get_current_tenant)  # ✅ required
):
    pass
```

#### راهکار
- ✅ **Refactor all Cabinet routes** برای tenant dependency
- ✅ **Update dependencies.py** برای tenant injection
- ✅ **Test all endpoints** با tenant isolation

---

### چالش 5: Testing Coverage ⚠️ HIGH

#### مشکل اصلی
- **Upstream:** Tests برای single-tenant
- **Current Branch:** Tests برای multi-tenant
- **تداخل:** نیاز به update تمام tests

#### راهکار
- ✅ **Update existing tests** برای multi-tenant
- ✅ **Add new tests** برای tenant isolation
- ✅ **Test coverage** باید >80% باشد
- ✅ **Integration tests** برای Cabinet و Nalogo

---

## 📋 برنامه عملیاتی: Phase-by-Phase

### Phase 0: آماده‌سازی (1 روز)

#### Task 0.1: Backup و Setup
- [ ] **تسک:** ایجاد backup از برنچ فعلی
  - **زمان:** 30 دقیقه
  - **دستورات:**
    ```bash
    git checkout resolve-adversarial-findings
    git branch backup-before-upstream-merge-$(date +%Y%m%d)
    pg_dump -U postgres remnabot > backup_db_$(date +%Y%m%d).sql
    ```
  - **خروجی:** Backup branch + SQL dump

- [ ] **تسک:** ایجاد برنچ مرج
  - **زمان:** 15 دقیقه
  - **دستورات:**
    ```bash
    git checkout resolve-adversarial-findings
    git checkout -b merge/upstream-main-$(date +%Y%m%d)
    git fetch upstream main
    ```
  - **خروجی:** برنچ جدید برای مرج

- [ ] **تسک:** بررسی آخرین commit در upstream
  - **زمان:** 30 دقیقه
  - **فعالیت:** بررسی commit history و تغییرات
  - **خروجی:** لیست commits برای cherry-pick

#### Task 0.2: ایجاد Validation Scripts
- [ ] **تسک:** Script برای بررسی `bot_id` در queries
  - **زمان:** 2 ساعت
  - **فعالیت:** ایجاد script برای بررسی تمام database queries
  - **خروجی:** Validation script

- [ ] **تسک:** Script برای بررسی tenant context
  - **زمان:** 1 ساعت
  - **فعالیت:** ایجاد script برای بررسی tenant context در functions
  - **خروجی:** Validation script

- [ ] **تسک:** Script برای بررسی Redis keys prefix
  - **زمان:** 1 ساعت
  - **فعالیت:** ایجاد script برای بررسی Redis keys
  - **خروجی:** Validation script

#### Task 0.3: تحلیل تداخل‌ها
- [ ] **تسک:** شناسایی فایل‌های با تداخل بالا
  - **زمان:** 2 ساعت
  - **فعالیت:**
    - بررسی `app/config.py` برای تداخل
    - بررسی `app/database/models.py` برای تداخل
    - لیست کردن تمام فایل‌های CRUD با تداخل
  - **خروجی:** لیست فایل‌های با تداخل + اولویت

- [ ] **تسک:** بررسی migration conflicts
  - **زمان:** 1 ساعت
  - **فعالیت:**
    - بررسی migrations در upstream
    - مقایسه با migrations فعلی
    - شناسایی conflicts
  - **خروجی:** لیست migration conflicts + راهکار

---

### Phase 1: Core Infrastructure (2 روز)

#### Task 1.1: Merge Config Changes
- [ ] **تسک:** Merge `app/config.py` با دقت
  - **زمان:** 4 ساعت
  - **فعالیت:**
    1. بررسی تمام Cabinet settings در upstream
    2. تبدیل به tenant-aware config
    3. حفظ تمام multi-tenant settings
    4. اضافه کردن tenant prefix برای Cabinet settings
  - **خروجی:** `app/config.py` merged + tests passing
  - **ریسک:** 🔴 بالا - نیاز به دقت زیاد

- [ ] **تسک:** Update config accessors برای tenant-aware
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. ایجاد helper functions برای tenant config
    2. Update تمام config accessors
    3. Tests برای tenant config isolation
  - **خروجی:** Tenant-aware config system + tests

#### Task 1.2: Merge Database Models
- [ ] **تسک:** Merge `app/database/models.py` - Cabinet columns
  - **زمان:** 3 ساعت
  - **فعالیت:**
    1. اضافه کردن Cabinet columns به User model:
       - `cabinet_email`
       - `cabinet_email_verified`
       - `cabinet_password_hash`
       - `cabinet_email_verification_token`
       - `cabinet_email_verification_expires_at`
       - `cabinet_password_reset_token`
       - `cabinet_password_reset_expires_at`
    2. اطمینان از وجود bot_id در تمام tables
    3. بررسی relationships
  - **خروجی:** Updated models.py + migration script
  - **ریسک:** 🔴 بالا - نیاز به migration

- [ ] **تسک:** Merge `app/database/models.py` - Promocode changes
  - **زمان:** 1 ساعت
  - **فعالیت:**
    1. اضافه کردن `first_purchase_only` به Promocode
    2. بررسی bot_id در Promocode model
  - **خروجی:** Updated Promocode model

- [ ] **تسک:** ایجاد Migration برای Cabinet columns
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. ایجاد migration script
    2. Test migration در staging
    3. Backup قبل از migration
  - **خروجی:** Migration script + test results
  - **ریسک:** 🔴 بالا - نیاز به backup

---

### Phase 2: Cabinet Module (3-4 روز)

#### Task 2.1: Cabinet Auth - JWT Handler
- [ ] **تسک:** Refactor `app/cabinet/auth/jwt_handler.py` برای tenant-aware
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. اضافه کردن `bot_id` parameter به `create_access_token()`
    2. اضافه کردن `bot_id` parameter به `create_refresh_token()`
    3. اضافه کردن `bot_id` به JWT payload
    4. Update token validation برای bot_id check
  - **خروجی:** Tenant-aware JWT handler + tests
  - **وابستگی:** Task 1.1 (config)

- [ ] **تسک:** Refactor `app/cabinet/auth/telegram_auth.py` برای tenant-aware
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. اضافه کردن `bot_id` parameter به `validate_telegram_login_widget()`
    2. Update validation logic برای tenant context
    3. Tests برای tenant isolation
  - **خروجی:** Tenant-aware Telegram auth + tests

#### Task 2.2: Cabinet Dependencies
- [ ] **تسک:** Update `app/cabinet/dependencies.py` برای tenant injection
  - **زمان:** 1 ساعت
  - **فعالیت:**
    1. اضافه کردن tenant dependency
    2. Update تمام dependencies برای tenant context
  - **خروجی:** Tenant-aware dependencies
  - **وابستگی:** Task 1.1 (config)

#### Task 2.3: Cabinet Routes (17 فایل)
- [ ] **تسک:** Refactor Cabinet routes - Batch 1 (5 routes)
  - **زمان:** 4 ساعت
  - **فعالیت:**
    1. `app/cabinet/routes/auth.py` - اضافه کردن tenant dependency
    2. `app/cabinet/routes/info.py` - اضافه کردن tenant dependency
    3. `app/cabinet/routes/balance.py` - اضافه کردن tenant dependency
    4. `app/cabinet/routes/subscription.py` - اضافه کردن tenant dependency
    5. `app/cabinet/routes/tickets.py` - اضافه کردن tenant dependency
    6. Tests برای هر route
  - **خروجی:** 5 routes refactored + tests passing
  - **وابستگی:** Task 2.2 (dependencies)

- [ ] **تسک:** Refactor Cabinet routes - Batch 2 (6 routes)
  - **زمان:** 4 ساعت
  - **فعالیت:**
    1. `app/cabinet/routes/admin_*.py` (3 routes)
    2. `app/cabinet/routes/promo.py`
    3. `app/cabinet/routes/promocode.py`
    4. `app/cabinet/routes/referral.py`
    5. Tests برای هر route
  - **خروجی:** 6 routes refactored + tests passing

- [ ] **تسک:** Refactor Cabinet routes - Batch 3 (6 routes)
  - **زمان:** 4 ساعت
  - **فعالیت:**
    1. `app/cabinet/routes/branding.py`
    2. `app/cabinet/routes/contests.py`
    3. `app/cabinet/routes/notifications.py`
    4. `app/cabinet/routes/polls.py`
    5. Tests برای هر route
  - **خروجی:** 6 routes refactored + tests passing

#### Task 2.4: Cabinet Integration
- [ ] **تسک:** Register Cabinet routes در `app/webapi/app.py`
  - **زمان:** 1 ساعت
  - **فعالیت:**
    1. اضافه کردن Cabinet router
    2. Update route registration
    3. Tests برای route registration
  - **خروجی:** Cabinet routes registered + tests

- [ ] **تسک:** Integration tests برای Cabinet
  - **زمان:** 3 ساعت
  - **فعالیت:**
    1. Test authentication flow
    2. Test tenant isolation
    3. Test all endpoints
  - **خروجی:** Integration tests + coverage report

---

### Phase 3: CRUD Operations (3-4 روز)

#### Task 3.1: Promocode CRUD
- [ ] **تسک:** Merge `app/database/crud/promocode.py` - `first_purchase_only`
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. اضافه کردن `first_purchase_only` parameter
    2. Update `create_promocode()` function
    3. Update validation logic
    4. اطمینان از `bot_id` filter در تمام queries
    5. Tests
  - **خروجی:** Updated promocode CRUD + tests
  - **ریسک:** 🟡 متوسط - نیاز به بررسی bot_id

- [ ] **تسک:** Merge `app/database/crud/promocode.py` - Pagination
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. اضافه کردن pagination به `get_promocodes_list()`
    2. اطمینان از `bot_id` filter
    3. Tests
  - **خروجی:** Pagination added + tests

#### Task 3.2: Subscription CRUD
- [ ] **تسک:** Merge `app/database/crud/subscription.py` - Traffic reset
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. اضافه کردن traffic reset logic به `renew_subscription()`
    2. اطمینان از `bot_id` filter
    3. Tests
  - **خروجی:** Traffic reset added + tests

- [ ] **تسک:** Merge `app/database/crud/subscription.py` - Auto-activation
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. Update `activate_subscription()` برای auto-activation
    2. اطمینان از `bot_id` filter
    3. Tests
  - **خروجی:** Auto-activation updated + tests

#### Task 3.3: User CRUD
- [ ] **تسک:** Merge `app/database/crud/user.py` - Balance filter
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. اضافه کردن balance filter به `get_users_list()`
    2. اطمینان از `bot_id` filter
    3. Tests
  - **خروجی:** Balance filter added + tests

- [ ] **تسک:** Merge `app/database/crud/user.py` - Extended filters
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. اضافه کردن extended filters
    2. اطمینان از `bot_id` filter
    3. Tests
  - **خروجی:** Extended filters added + tests

#### Task 3.4: سایر CRUD Files (47 فایل)
- [ ] **تسک:** بررسی و merge سایر CRUD files - Batch 1 (15 فایل)
  - **زمان:** 6 ساعت
  - **فعالیت:**
    1. بررسی هر فایل برای bot_id filter
    2. Merge تغییرات از upstream
    3. Tests برای هر فایل
  - **خروجی:** 15 CRUD files merged + tests

- [ ] **تسک:** بررسی و merge سایر CRUD files - Batch 2 (16 فایل)
  - **زمان:** 6 ساعت
  - **فعالیت:** مشابه Batch 1
  - **خروجی:** 16 CRUD files merged + tests

- [ ] **تسک:** بررسی و merge سایر CRUD files - Batch 3 (16 فایل)
  - **زمان:** 6 ساعت
  - **فعالیت:** مشابه Batch 1
  - **خروجی:** 16 CRUD files merged + tests

---

### Phase 4: Services (3-4 روز)

#### Task 4.1: Subscription Service
- [ ] **تسک:** Merge `app/services/subscription_service.py` - Purchase flow
  - **زمان:** 3 ساعت
  - **فعالیت:**
    1. Merge تغییرات purchase flow
    2. اطمینان از tenant context
    3. Tests
  - **خروجی:** Updated subscription service + tests

- [ ] **تسک:** Merge `app/services/subscription_service.py` - Traffic reset
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. اضافه کردن traffic reset logic
    2. اطمینان از tenant context
    3. Tests
  - **خروجی:** Traffic reset added + tests

#### Task 4.2: Cart Service
- [ ] **تسک:** Refactor `app/services/user_cart_service.py` برای tenant-aware
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. اضافه کردن `bot_id` parameter به تمام functions
    2. Update Redis keys برای tenant prefix: `cart:{bot_id}:{user_id}`
    3. Tests برای tenant isolation
  - **خروجی:** Tenant-aware cart service + tests
  - **ریسک:** 🟡 متوسط - نیاز به بررسی Redis keys

#### Task 4.3: Payment Service
- [ ] **تسک:** Merge `app/services/payment_service.py` - Modular structure
  - **زمان:** 3 ساعت
  - **فعالیت:**
    1. Merge modular payment structure
    2. اطمینان از tenant context
    3. Tests
  - **خروجی:** Modular payment service + tests

#### Task 4.4: سایر Services (57 فایل)
- [ ] **تسک:** بررسی و merge سایر Services - Batch 1 (20 فایل)
  - **زمان:** 8 ساعت
  - **فعالیت:**
    1. بررسی هر service برای tenant context
    2. Merge تغییرات از upstream
    3. Tests برای هر service
  - **خروجی:** 20 services merged + tests

- [ ] **تسک:** بررسی و merge سایر Services - Batch 2 (20 فایل)
  - **زمان:** 8 ساعت
  - **فعالیت:** مشابه Batch 1
  - **خروجی:** 20 services merged + tests

- [ ] **تسک:** بررسی و merge سایر Services - Batch 3 (17 فایل)
  - **زمان:** 7 ساعت
  - **فعالیت:** مشابه Batch 1
  - **خروجی:** 17 services merged + tests

---

### Phase 5: Handlers (2-3 روز)

#### Task 5.1: Subscription Handlers
- [ ] **تسک:** Merge `app/handlers/subscription/purchase.py`
  - **زمان:** 3 ساعت
  - **فعالیت:**
    1. Merge تغییرات purchase flow
    2. اطمینان از tenant context
    3. Tests
  - **خروجی:** Updated purchase handler + tests

- [ ] **تسک:** Merge `app/handlers/subscription/modem.py`
  - **زمان:** 1 ساعت
  - **فعالیت:**
    1. اضافه کردن modem support
    2. اطمینان از tenant context
    3. Tests
  - **خروجی:** Modem handler added + tests

#### Task 5.2: Admin Handlers
- [ ] **تسک:** Merge `app/handlers/admin/promocodes.py` - Pagination
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. اضافه کردن pagination
    2. اطمینان از tenant context
    3. Tests
  - **خروجی:** Pagination added + tests

- [ ] **تسک:** Merge `app/handlers/admin/users.py` - Filters
  - **زمان:** 3 ساعت
  - **فعالیت:**
    1. اضافه کردن balance filter
    2. اضافه کردن extended filters
    3. اضافه کردن admin purchase subscription
    4. اطمینان از tenant context
    5. Tests
  - **خروجی:** Updated admin users handler + tests

#### Task 5.3: سایر Handlers (77 فایل)
- [ ] **تسک:** بررسی و merge سایر Handlers - Batch 1 (25 فایل)
  - **زمان:** 8 ساعت
  - **فعالیت:**
    1. بررسی هر handler برای tenant context
    2. Merge تغییرات از upstream
    3. Tests برای هر handler
  - **خروجی:** 25 handlers merged + tests

- [ ] **تسک:** بررسی و merge سایر Handlers - Batch 2 (26 فایل)
  - **زمان:** 8 ساعت
  - **فعالیت:** مشابه Batch 1
  - **خروجی:** 26 handlers merged + tests

- [ ] **تسک:** بررسی و merge سایر Handlers - Batch 3 (26 فایل)
  - **زمان:** 8 ساعت
  - **فعالیت:** مشابه Batch 1
  - **خروجی:** 26 handlers merged + tests

---

### Phase 6: Nalogo Integration (2 روز)

#### Task 6.1: Nalogo Config
- [ ] **تسک:** Refactor `app/lib/nalogo/client.py` برای tenant-aware
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. Update client برای استفاده از tenant config
    2. Update auth برای tenant config
    3. Tests
  - **خروجی:** Tenant-aware Nalogo client + tests
  - **وابستگی:** Task 1.1 (config)

#### Task 6.2: Nalogo Integration
- [ ] **تسک:** Integration Nalogo با Payment Service
  - **زمان:** 3 ساعت
  - **فعالیت:**
    1. Update payment service برای Nalogo
    2. اطمینان از tenant context
    3. Tests
  - **خروجی:** Nalogo integrated + tests

#### Task 6.3: Nalogo Tests
- [ ] **تسک:** Integration tests برای Nalogo
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. Test receipt generation
    2. Test tenant isolation
    3. Test error handling
  - **خروجی:** Integration tests + coverage

---

### Phase 7: Bug Fixes (1-2 روز)

#### Task 7.1: Promocode Fixes
- [ ] **تسک:** Cherry-pick promocode fixes
  - **زمان:** 2 ساعت
  - **دستورات:**
    ```bash
    git cherry-pick 2156f630  # first_purchase_only
    git cherry-pick 5a5a18d8  # pagination
    git cherry-pick 9cd5d8e0  # general fixes
    ```
  - **فعالیت:**
    1. بررسی bot_id filters
    2. Tests
  - **خروجی:** Promocode fixes merged + tests

#### Task 7.2: Subscription Fixes
- [ ] **تسک:** Cherry-pick subscription fixes
  - **زمان:** 3 ساعت
  - **دستورات:**
    ```bash
    git cherry-pick 4bebff5c  # auto-activation
    git cherry-pick e15728e3  # simple purchase
    git cherry-pick 56cc8bac  # purchase fix
    git cherry-pick bce05d4b  # traffic reset
    ```
  - **فعالیت:**
    1. بررسی bot_id filters
    2. Tests
  - **خروجی:** Subscription fixes merged + tests

#### Task 7.3: Payment Fixes
- [ ] **تسک:** Cherry-pick payment fixes (فقط ایرانی)
  - **زمان:** 2 ساعت
  - **دستورات:**
    ```bash
    git cherry-pick bc19ec32  # persistent cart
    git cherry-pick 5aa9b6dd  # notification fix
    git cherry-pick dd860146  # topup buttons
    # ❌ نکنید: git cherry-pick 9bd1944b  # platega (درگاه روسی)
    ```
  - **فعالیت:**
    1. بررسی tenant context
    2. Tests
  - **خروجی:** Payment fixes merged + tests

#### Task 7.4: سایر Fixes
- [ ] **تسک:** Cherry-pick سایر fixes
  - **زمان:** 3 ساعت
  - **فعالیت:**
    1. Admin fixes
    2. Remnawave sync fixes
    3. Blacklist fixes
    4. بررسی tenant context
    5. Tests
  - **خروجی:** سایر fixes merged + tests

---

### Phase 8: Testing و Validation (2 روز)

#### Task 8.1: Unit Tests
- [ ] **تسک:** اجرای تمام unit tests
  - **زمان:** 2 ساعت
  - **دستورات:**
    ```bash
    pytest tests/ -v
    ```
  - **فعالیت:**
    1. Fix failing tests
    2. Coverage report
  - **خروجی:** All tests passing + coverage report

#### Task 8.2: Integration Tests
- [ ] **تسک:** اجرای integration tests
  - **زمان:** 3 ساعت
  - **دستورات:**
    ```bash
    pytest tests/integration/ -v
    ```
  - **فعالیت:**
    1. Test tenant isolation
    2. Test Cabinet endpoints
    3. Test Nalogo integration
  - **خروجی:** Integration tests passing

#### Task 8.3: Manual Testing
- [ ] **تسک:** Manual testing checklist
  - **زمان:** 4 ساعت
  - **فعالیت:**
    1. Cabinet authentication
    2. Cabinet routes tenant-aware
    3. Promocodes با first_purchase_only
    4. Subscription fixes
    5. Persistent cart tenant-aware
    6. Admin features
    7. Data leak testing
  - **خروجی:** Manual testing report

#### Task 8.4: Database Schema Validation
- [ ] **تسک:** بررسی database schema
  - **زمان:** 1 ساعت
  - **دستورات SQL:**
    ```sql
    -- بررسی وجود bot_id در تمام tables
    SELECT table_name 
    FROM information_schema.columns 
    WHERE column_name = 'bot_id';
    
    -- بررسی cabinet columns
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'users' 
      AND column_name LIKE 'cabinet%';
    ```
  - **خروجی:** Schema validation report

#### Task 8.5: Code Quality Check
- [ ] **تسک:** بررسی code quality
  - **زمان:** 1 ساعت
  - **دستورات:**
    ```bash
    ruff check app/
    python -m py_compile app/**/*.py
    ```
  - **خروجی:** Code quality report

---

### Phase 9: Documentation (1 روز)

#### Task 9.1: Update PRD
- [ ] **تسک:** اضافه کردن Cabinet feature به PRD
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. اضافه کردن Cabinet requirements
    2. Update user stories
    3. Update acceptance criteria
  - **خروجی:** Updated PRD

#### Task 9.2: Update Architecture
- [ ] **تسک:** اضافه کردن Cabinet و Nalogo به Architecture
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. اضافه کردن Cabinet architecture
    2. اضافه کردن Nalogo integration pattern
    3. Update diagrams
  - **خروجی:** Updated Architecture

#### Task 9.3: Update API Docs
- [ ] **تسک:** مستندسازی Cabinet API
  - **زمان:** 2 ساعت
  - **فعالیت:**
    1. مستندسازی تمام endpoints
    2. اضافه کردن tenant parameters
    3. Examples
  - **خروجی:** API documentation

#### Task 9.4: Changelog
- [ ] **تسک:** ایجاد Changelog
  - **زمان:** 1 ساعت
  - **فعالیت:**
    1. لیست تمام changes
    2. Categorize (Added, Fixed, Changed)
    3. Version bump
  - **خروجی:** Changelog

---

## 📊 خلاصه زمان‌بندی

| Phase | مدت زمان | تسک‌ها | اولویت |
|-------|----------|--------|--------|
| Phase 0: آماده‌سازی | 1 روز | 3 | 🔴 Critical |
| Phase 1: Core Infrastructure | 2 روز | 4 | 🔴 Critical |
| Phase 2: Cabinet Module | 3-4 روز | 8 | 🔴 Critical |
| Phase 3: CRUD Operations | 3-4 روز | 8 | 🔴 Critical |
| Phase 4: Services | 3-4 روز | 7 | 🟡 High |
| Phase 5: Handlers | 2-3 روز | 5 | 🟡 High |
| Phase 6: Nalogo Integration | 2 روز | 3 | 🟡 High |
| Phase 7: Bug Fixes | 1-2 روز | 4 | 🟢 Medium |
| Phase 8: Testing | 2 روز | 5 | 🔴 Critical |
| Phase 9: Documentation | 1 روز | 4 | 🟢 Medium |
| **کل** | **20-26 روز کاری** | **51 تسک** | |

---

## ⚠️ ریسک‌ها و راهکارها

### ریسک 1: تداخل با Multi-Tenant Architecture
- **احتمال:** 🔴 بالا
- **تأثیر:** 🔴 بحرانی
- **راهکار:** 
  - ✅ استفاده از validation scripts
  - ✅ Code review دقیق
  - ✅ Automated tests برای tenant isolation

### ریسک 2: Migration Conflicts
- **احتمال:** 🟡 متوسط
- **تأثیر:** 🔴 بالا
- **راهکار:**
  - ✅ Test migration در staging
  - ✅ Backup قبل از migration
  - ✅ Rollback plan

### ریسک 3: Data Leakage
- **احتمال:** 🟡 متوسط
- **تأثیر:** 🔴 بحرانی
- **راهکار:**
  - ✅ بررسی تمام queries برای bot_id
  - ✅ RLS policies testing
  - ✅ Integration tests برای isolation

### ریسک 4: Breaking Changes
- **احتمال:** 🟡 متوسط
- **تأثیر:** 🟡 متوسط
- **راهکار:**
  - ✅ Backward compatibility
  - ✅ Feature flags
  - ✅ Gradual rollout

---

## ✅ چک‌لیست نهایی

### قبل از شروع
- [ ] Backup کامل
- [ ] برنچ مرج ایجاد شده
- [ ] آخرین commit بررسی شده
- [ ] این راهنما خوانده شده
- [ ] Validation scripts ایجاد شده

### در حین مرج
- [ ] هر phase کامل شده
- [ ] Tests passing
- [ ] Code review انجام شده
- [ ] Validation scripts اجرا شده
- [ ] Documentation updated

### بعد از مرج
- [ ] تمام tests pass
- [ ] Manual testing کامل
- [ ] Code review approved
- [ ] Documentation complete
- [ ] Changelog updated
- [ ] PR created
- [ ] Team approval

---

## 📝 نکات مهم

### ❌ نباید مرج شود
1. **Platega fixes** - درگاه روسی (مخالف PRD)
2. **حذف فایل‌های `_bmad-output/`** - باید restore شوند
3. **تغییرات معماری** که با multi-tenant در تضاد هستند

### ✅ باید مرج شود
1. **Cabinet feature** (با اصلاحات multi-tenant)
2. **Nalogo integration** (با tenant config)
3. **Modem support**
4. **Promocode fixes**
5. **Subscription fixes**
6. **Payment fixes** (فقط ایرانی)
7. **Admin و User Management fixes**

---

**وضعیت:** ✅ آماده برای اجرا  
**اولویت:** ⚠️ CRITICAL  
**تخمین زمان کل:** 20-26 روز کاری (4-5 هفته)

---

*این راهنما توسط Scrum Master و Developer Agents تهیه شده است.*  
*تاریخ: 2026-01-03*
