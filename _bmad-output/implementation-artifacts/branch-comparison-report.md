# گزارش مقایسه برنچ‌ها و تحلیل تضادها

**پروژه:** remnabot Multi-Tenant SaaS  
**تاریخ:** 2025-12-26  
**نویسنده:** Winston (Architect Agent)  
**هدف:** شناسایی کدهای تمیز قابل merge و کدهای آلوده نیازمند بازنویسی

---

## 📊 خلاصه اجرایی

### وضعیت برنچ‌ها

| برنچ | Commit Count | وضعیت | توضیحات |
|------|-------------|-------|---------|
| **reagain-init** (فعلی) | 314 commits ahead | ✅ Active Development | شامل BMAD artifacts + CloudPayments |
| **origin/dev** | 27 commits ahead | ✅ Upstream | شامل تغییرات جدید از upstream |
| **origin/fix/replace-kopek-to-toman** | - | ⚠️ Currency Fix | تبدیل kopek به toman - **مفید** |
| **origin/debug/language** | - | ⚠️ Language Debug | بهبود localization - **مفید** |
| **origin/feat/payments** | - | ⚠️ Payments Feature | تغییرات پرداخت - **نیاز به بررسی** |
| **origin/feat/tenant** | - | ⚠️ Tenant Feature | تغییرات tenant - **نیاز به بررسی** |
| **origin/feat/multi-tenant-0** | - | 🚨 **انحراف از PRD** | استفاده از "Bot" به جای "Tenant" |
| **origin/feat/multi-tenant-1** | - | 🚨 **انحراف از PRD** | ادامه multi-tenant-0 |

### آمار تفاوت‌ها

- **145 فایل** تغییر کرده‌اند
- **31,630 خط** اضافه شده
- **1,037 خط** حذف شده
- **خالص:** +30,593 خط کد

---

## 🎯 استراتژی کلی

### رویکرد پیشنهادی

1. **کدهای تمیز** → Merge مستقیم (بدون conflict)
2. **کدهای آلوده** → بازنویسی بر اساس PRD (حذف Russian gateways)
3. **کدهای جدید** → ارزیابی و یکپارچه‌سازی

---

## ✅ فایل‌های تمیز - قابل Merge مستقیم

### دسته 1: BMAD Artifacts (100% تمیز)

این فایل‌ها فقط مستندات و planning هستند و هیچ conflict ندارند:

```
✅ _bmad-output/analysis/brainstorming-session-2025-12-25.md
✅ _bmad-output/architecture.md
✅ _bmad-output/prd.md
✅ _bmad-output/project-context.md
✅ _bmad-output/project-planning-artifacts/* (تمام فایل‌ها)
✅ _bmad-output/implementation-artifacts/* (تمام فایل‌ها)
```

**راهکار:** Merge مستقیم - این فایل‌ها فقط مستندات هستند.

---

### دسته 2: فایل‌های جدید بدون Russian Gateway

این فایل‌ها جدید هستند و در origin/dev وجود ندارند:

#### CloudPayments Integration (14 فایل)

```
✅ app/database/crud/cloudpayments.py          # NEW - تمیز
✅ app/services/cloudpayments_service.py       # NEW - تمیز
✅ app/services/payment/cloudpayments.py       # NEW - تمیز
✅ app/handlers/balance/cloudpayments.py      # NEW - تمیز
```

**وضعیت:** ✅ **تمیز - قابل Merge**

**نکته:** CloudPayments یک درگاه پرداخت روسی است اما:
- در PRD ذکر نشده (نه در لیست حذف، نه در لیست نگه‌داری)
- باید تصمیم بگیریم: حذف یا نگه‌داری؟

**راهکار پیشنهادی:**
- **گزینه 1:** حذف CloudPayments (همراه با سایر Russian gateways)
- **گزینه 2:** نگه‌داری موقت تا تصمیم نهایی (flag کردن)

---

#### Features جدید (تمیز)

```
✅ app/handlers/admin/blacklist.py            # NEW - تمیز
✅ app/handlers/admin/bulk_ban.py             # NEW - تمیز
✅ app/handlers/admin/contests.py             # NEW - تمیز
✅ app/handlers/admin/daily_contests.py       # NEW - تمیز
✅ app/handlers/contests.py                   # NEW - تمیز
✅ app/services/blacklist_service.py         # NEW - تمیز
✅ app/services/bulk_ban_service.py          # NEW - تمیز
✅ app/services/contest_rotation_service.py   # NEW - تمیز
✅ app/services/referral_contest_service.py  # NEW - تمیز
✅ app/services/pinned_message_service.py    # NEW - تمیز
✅ app/services/traffic_monitoring_service.py # NEW - تمیز
✅ app/services/nalogo_service.py            # NEW - تمیز
✅ app/services/menu_layout/*                 # NEW - تمیز (5 فایل)
✅ app/middlewares/button_stats.py           # NEW - تمیز
✅ app/webserver/payments.py                  # NEW - تمیز
```

**وضعیت:** ✅ **تمیز - قابل Merge**

**راهکار:** Merge مستقیم - این فایل‌ها feature جدید هستند و با PRD سازگارند.

---

### دسته 3: فایل‌های تغییر یافته - بدون Russian Gateway

این فایل‌ها تغییر کرده‌اند اما تغییرات تمیز هستند:

```
✅ app/database/crud/contest.py               # NEW - تمیز
✅ app/database/crud/referral_contest.py      # NEW - تمیز
✅ app/database/crud/subscription.py          # MODIFIED - بررسی نیاز دارد
✅ app/database/crud/transaction.py           # MODIFIED - بررسی نیاز دارد
✅ app/database/crud/user.py                  # MODIFIED - بررسی نیاز دارد
✅ app/database/models.py                     # MODIFIED - ⚠️ نیاز به بررسی
✅ app/database/database.py                   # MODIFIED - بررسی نیاز دارد
✅ app/database/universal_migration.py        # MODIFIED - بررسی نیاز دارد
```

**راهکار:** بررسی دقیق‌تر برای اطمینان از عدم وجود Russian gateway references.

---

## ⚠️ فایل‌های آلوده - نیازمند بازنویسی

### دسته 1: فایل‌های حاوی Russian Gateway (حذف کامل)

#### External Layer (7 فایل)

```
❌ app/external/yookassa_webhook.py          # DELETE - Russian gateway
❌ app/external/wata_webhook.py               # DELETE - Russian gateway
❌ app/external/pal24_client.py               # DELETE - Russian gateway
❌ app/external/pal24_webhook.py              # DELETE - Russian gateway
❌ app/external/heleket.py                    # DELETE - Russian gateway
❌ app/external/heleket_webhook.py            # DELETE - Russian gateway
❌ app/external/tribute.py                    # DELETE - Russian gateway
```

**راهکار:** 
- ❌ **Merge نکنید** - این فایل‌ها باید حذف شوند
- ✅ از origin/dev استفاده نکنید - این فایل‌ها در PRD برای حذف مشخص شده‌اند

---

#### Service Layer - Gateway-Specific (13 فایل)

```
❌ app/services/wata_service.py               # DELETE
❌ app/services/yookassa_service.py           # DELETE
❌ app/services/tribute_service.py            # DELETE
❌ app/services/mulenpay_service.py           # DELETE
❌ app/services/pal24_service.py              # DELETE
❌ app/services/platega_service.py           # DELETE
❌ app/services/payment/heleket.py            # DELETE
❌ app/services/payment/mulenpay.py           # DELETE
❌ app/services/payment/pal24.py              # DELETE
❌ app/services/payment/tribute.py            # DELETE
❌ app/services/payment/wata.py               # DELETE
❌ app/services/payment/platega.py            # DELETE
❌ app/services/payment/yookassa.py           # DELETE
```

**راهکار:**
- ❌ **Merge نکنید** - حذف کامل
- ✅ بازنویسی بر اساس PRD FR10.1

---

#### Handler Layer - Balance (7 فایل)

```
❌ app/handlers/balance/wata.py               # DELETE
❌ app/handlers/balance/yookassa.py           # DELETE
❌ app/handlers/balance/heleket.py            # DELETE
❌ app/handlers/balance/mulenpay.py           # DELETE
❌ app/handlers/balance/pal24.py              # DELETE
❌ app/handlers/balance/platega.py            # DELETE
❌ app/handlers/balance/tribute.py             # DELETE
```

**راهکار:**
- ❌ **Merge نکنید** - حذف کامل

---

### دسته 2: فایل‌های Contaminated - نیازمند Surgical Removal

این فایل‌ها حاوی Russian gateway references هستند اما باید پاکسازی شوند:

#### Core Service Files (P0 - Critical)

```
⚠️ app/services/payment_service.py           # MODIFIED - حاوی YooKassa + CloudPayments
⚠️ app/services/subscription_service.py      # MODIFIED - بررسی نیاز دارد
⚠️ app/services/user_service.py              # MODIFIED - بررسی نیاز دارد
⚠️ app/services/payment_verification_service.py # MODIFIED - بررسی نیاز دارد
⚠️ app/services/payment/__init__.py           # MODIFIED - بررسی نیاز دارد
⚠️ app/services/payment/common.py            # MODIFIED - بررسی نیاز دارد
```

**تحلیل `payment_service.py`:**

```python
# در برنچ فعلی:
from app.services.payment.cloudpayments import CloudPaymentsPaymentMixin  # ✅ NEW
from app.services.yookassa_service import YooKassaService                # ❌ REMOVE
from app.services.wata_service import WataService                        # ❌ REMOVE

class PaymentService(
    CloudPaymentsPaymentMixin,  # ✅ NEW
    YooKassaPaymentMixin,       # ❌ REMOVE
    WataPaymentMixin,           # ❌ REMOVE
    # ...
):
```

**راهکار:**
1. ❌ **Merge نکنید** - این فایل آلوده است
2. ✅ از برنچ فعلی استفاده کنید (CloudPayments را نگه دارید)
3. ✅ حذف YooKassa, Wata, Heleket, etc. (طبق PRD FR10.1)
4. ✅ تصمیم درباره CloudPayments (حذف یا نگه‌داری)

---

#### Core Handler Files (P0 - Critical)

```
⚠️ app/handlers/subscription/purchase.py     # MODIFIED - 3,455 lines - بررسی نیاز دارد
⚠️ app/handlers/balance/main.py              # MODIFIED - بررسی نیاز دارد
⚠️ app/handlers/simple_subscription.py       # MODIFIED - 2,420 lines - بررسی نیاز دارد
⚠️ app/handlers/webhooks.py                  # MODIFIED - بررسی نیاز دارد
⚠️ app/handlers/admin/bot_configuration.py   # MODIFIED - 2,800 lines - بررسی نیاز دارد
⚠️ app/handlers/admin/payments.py             # MODIFIED - بررسی نیاز دارد
```

**راهکار:**
- بررسی دقیق‌تر برای شناسایی Russian gateway references
- حذف inline keyboard buttons مربوط به Russian gateways
- حذف callback handlers مربوط به Russian gateways

---

#### Config Files

```
⚠️ app/config.py                             # MODIFIED - حاوی CLOUDPAYMENTS + Russian gateways
```

**تحلیل `config.py`:**

```python
# در برنچ فعلی:
CLOUDPAYMENTS_ENABLED: bool = False          # ✅ NEW - اما Russian gateway است
YOOKASSA_ENABLED: bool = False              # ❌ REMOVE
WATA_ENABLED: bool = False                  # ❌ REMOVE
HELEKET_ENABLED: bool = False               # ❌ REMOVE
# ... سایر Russian gateways
```

**راهکار:**
1. ✅ نگه‌داری CloudPayments config (موقت - تا تصمیم نهایی)
2. ❌ حذف تمام Russian gateway configs (YooKassa, Wata, Heleket, etc.)
3. ✅ اضافه کردن ZarinPal config (طبق PRD)

---

## 🔄 تضادها و راهکارهای یکپارچه

### تضاد 1: CloudPayments Integration

**مشکل:**
- در برنچ فعلی CloudPayments اضافه شده
- در PRD ذکر نشده (نه در لیست حذف، نه در لیست نگه‌داری)
- CloudPayments یک درگاه پرداخت روسی است

**راهکار یکپارچه:**

**گزینه A: حذف CloudPayments (توصیه می‌شود)**
```python
# حذف تمام CloudPayments references
- app/database/crud/cloudpayments.py
- app/services/cloudpayments_service.py
- app/services/payment/cloudpayments.py
- app/handlers/balance/cloudpayments.py
- CLOUDPAYMENTS_* configs از app/config.py
```

**گزینه B: نگه‌داری موقت**
- Flag کردن CloudPayments به عنوان "deprecated"
- اضافه کردن به لیست حذف در PRD
- حذف در فاز cleanup

**توصیه:** **گزینه A** - حذف کامل برای سازگاری با PRD

---

### تضاد 2: Russian Gateway Removal vs Origin/Dev

**مشکل:**
- در origin/dev ممکن است Russian gateways وجود داشته باشند
- در PRD FR10.1 حذف کامل Russian gateways الزامی است
- در برنچ فعلی هنوز Russian gateways وجود دارند

**راهکار یکپارچه:**

1. **از origin/dev استفاده نکنید** برای فایل‌های Russian gateway
2. **از برنچ فعلی استفاده کنید** و سپس cleanup انجام دهید
3. **طبق MASTER-CLEANUP-GUIDE عمل کنید:**
   - Week 1, Days 3-5: حذف 27 فایل isolated
   - Week 2, Days 1-3: Surgical removal از core files

---

### تضاد 3: Currency Migration (Kopek → Toman)

**مشکل:**
- در PRD FR10.2: تبدیل از kopeks به tomans الزامی است
- در config.py هنوز `*_KOPEKS` وجود دارد
- در origin/dev ممکن است تغییراتی در currency وجود داشته باشد

**راهکار یکپارچه:**

1. ✅ **از برنچ فعلی استفاده کنید** (تغییرات جدیدتر)
2. ✅ **Migration script** برای تبدیل kopeks → tomans
3. ✅ **Update config.py** برای استفاده از `*_TOMANS`
4. ✅ **Update database models** برای currency fields

**مراحل:**
```python
# Step 1: Add toman columns (nullable)
ALTER TABLE subscriptions ADD COLUMN price_tomans INTEGER;
ALTER TABLE transactions ADD COLUMN amount_tomans INTEGER;

# Step 2: Convert data (1 kopek = 0.1 toman)
UPDATE subscriptions SET price_tomans = price_kopeks / 10;
UPDATE transactions SET amount_tomans = amount_kopeks / 10;

# Step 3: Make toman columns non-nullable
ALTER TABLE subscriptions ALTER COLUMN price_tomans SET NOT NULL;
ALTER TABLE transactions ALTER COLUMN amount_tomans SET NOT NULL;

# Step 4: Drop kopek columns (after verification)
ALTER TABLE subscriptions DROP COLUMN price_kopeks;
ALTER TABLE transactions DROP COLUMN amount_kopeks;
```

---

### تضاد 4: Localization (Russian → Persian/English)

**مشکل:**
- در PRD FR11: فارسی primary، انگلیسی secondary
- در config.py: `DEFAULT_LANGUAGE: str = "en"`
- در origin/dev ممکن است localization متفاوت باشد

**راهکار یکپارچه:**

1. ✅ **از برنچ فعلی استفاده کنید**
2. ✅ **Merge از `origin/debug/language`** - بهبودهای localization مفید هستند
3. ✅ **Update config.py:**
   ```python
   DEFAULT_LANGUAGE: str = "fa"  # Persian primary
   AVAILABLE_LANGUAGES: str = "fa,en"  # Persian + English
   ```
4. ✅ **Update localization files:**
   - `app/localization/locales/fa.json` (primary)
   - `app/localization/locales/en.json` (secondary)
   - حذف `ru.json`, `ua.json`, `zh.json` (طبق PRD)

---

### تضاد 5: Currency Migration (Kopek → Toman) - `origin/fix/replace-kopek-to-toman`

**وضعیت:** ✅ **مفید - قابل Merge**

**تحلیل:**
- این برنچ دقیقاً همان کاری را انجام می‌دهد که PRD FR10.2 می‌خواهد
- تبدیل از kopek به toman در تمام application
- بهبود currency formatting

**راهکار یکپارچه:**

1. ✅ **Merge از `origin/fix/replace-kopek-to-toman`**
2. ✅ **بررسی تغییرات:**
   - `app/config.py` - تبدیل `*_KOPEKS` به `*_TOMANS`
   - `app/utils/currency_converter.py` - تبدیل currency logic
   - تمام فایل‌هایی که از kopek استفاده می‌کنند
3. ✅ **تطبیق با PRD FR10.2:**
   - اطمینان از تبدیل کامل
   - بررسی database migration scripts

**نکته مهم:** این برنچ **باید merge شود** - دقیقاً همان چیزی است که PRD می‌خواهد.

---

### 🚨 انحراف 1: Multi-Tenant Architecture - `origin/feat/multi-tenant-0` و `origin/feat/multi-tenant-1`

**وضعیت:** ✅ **قابل استفاده با نگه‌داری bot_id به عنوان bot_id**

**تحلیل جدید:**

اگر `bot_id` را همان `bot_id` نگه داریم، **85-90% کد قابل استفاده است**.

**ساختار Bot Model در multi-tenant-0/1:**

```python
class Bot(Base):
    __tablename__ = "bots"
    
    id = Column(Integer, primary_key=True)  # ✅ این همان bot_id است
    telegram_bot_token = Column(String(255), unique=True)  # ✅ PRD: bot_token
    name = Column(String(255))  # ⚠️ می‌تواند bot_username باشد
    # ... فیلدهای دیگر
    
    # ❌ Missing: bot_username, owner_telegram_id, status, plan, settings
```

**مقایسه با PRD FR1.1:**

| فیلد PRD | فیلد Bot | وضعیت | Action |
|----------|----------|-------|--------|
| `id` | `id` | ✅ **سازگار** | OK |
| `bot_token` | `telegram_bot_token` | ✅ **سازگار** | فقط نام متفاوت |
| `bot_username` | ❌ **ندارد** | ⚠️ **اضافه شود** | Migration |
| `owner_telegram_id` | ❌ **ندارد** | ⚠️ **اضافه شود** | Migration |
| `status` | `is_active` (Boolean) | ⚠️ **تبدیل شود** | Migration |
| `plan` | ❌ **ندارد** | ⚠️ **اضافه شود** | Migration |
| `settings` | ❌ **ندارد** | ⚠️ **اضافه شود** | یا از BotConfiguration |

**راهکار یکپارچه (توصیه می‌شود):**

1. ✅ **نگه‌داری bot_id به عنوان bot_id**
   - `bot_id = bot_id` (همان چیز است)
   - نیازی به rename نیست (اختیاری است)

2. ✅ **Merge Admin Panel (100% قابل استفاده)**
   ```
   ✅ app/handlers/admin/tenant_bots/*  # 16 فایل - کاملاً آماده
   ```

3. ✅ **Merge Services (100% قابل استفاده)**
   ```
   ✅ app/services/bot_config_service.py
   ✅ app/database/crud/bot.py
   ✅ app/database/crud/bot_configuration.py
   ✅ app/database/crud/bot_feature_flag.py
   ```

4. ✅ **Merge Models (80% قابل استفاده)**
   - اضافه کردن 5 فیلد missing به Bot model
   - Migration برای اضافه کردن فیلدها

**درصد سازگاری:**

| Component | درصد | توضیحات |
|-----------|------|---------|
| Admin Panel | ✅ **100%** | کاملاً قابل استفاده |
| Services | ✅ **100%** | فقط rename اختیاری |
| Database CRUD | ✅ **100%** | فقط rename اختیاری |
| Models | ✅ **80%** | نیاز به اضافه کردن فیلدها |
| **Overall** | ✅ **85-90%** | خیلی قابل استفاده |

**توصیه:** ✅ **استفاده از multi-tenant-0/1 با نگه‌داری bot_id**

**فایل‌های قابل استفاده مستقیم:**

```
✅ app/handlers/admin/tenant_bots/* (16 فایل - 100%)
✅ app/services/bot_config_service.py (100%)
✅ app/database/crud/bot*.py (3 فایل - 100%)
✅ app/database/models.py (Bot model - 80%)
```

**تغییرات لازم:**

1. Migration: اضافه کردن 5 فیلد به Bot model
2. Rename اختیاری: Bot → Tenant (اختیاری)
3. یکپارچه‌سازی: TenantMiddleware, ContextVar, RLS

**جزئیات بیشتر:** رجوع کنید به `multi-tenant-branches-deep-analysis.md`

---

### تضاد 6: Payments Feature - `origin/feat/payments`

**وضعیت:** ⚠️ **نیاز به بررسی دقیق**

**تحلیل:**
- این برنچ شامل تغییرات در سیستم پرداخت است
- ممکن است شامل Russian gateways باشد (نیاز به بررسی)
- ممکن است شامل بهبودهای مفید باشد

**راهکار یکپارچه:**

1. ⚠️ **بررسی دقیق** قبل از merge
2. ✅ **استفاده از تغییرات مفید:**
   - بهبودهای payment flow
   - Bug fixes
   - Performance improvements
3. ❌ **حذف Russian gateway references** (طبق PRD FR10.1)

---

## 📋 Plan اجرایی

### Phase 1: Merge فایل‌های تمیز (1-2 روز)

**مرحله 1.1: BMAD Artifacts**
```bash
# این فایل‌ها 100% تمیز هستند
git checkout origin/dev
git checkout reagain-init -- _bmad-output/
git commit -m "docs: Add BMAD planning artifacts"
```

**مرحله 1.2: Features جدید (بدون Russian gateway)**
```bash
# Merge فایل‌های تمیز
git checkout reagain-init -- \
  app/handlers/admin/blacklist.py \
  app/handlers/admin/bulk_ban.py \
  app/handlers/admin/contests.py \
  app/services/blacklist_service.py \
  app/services/bulk_ban_service.py \
  # ... سایر فایل‌های تمیز
```

**مرحله 1.3: تصمیم درباره CloudPayments**
```bash
# گزینه A: حذف CloudPayments
git rm app/database/crud/cloudpayments.py
git rm app/services/cloudpayments_service.py
# ... حذف تمام CloudPayments files

# گزینه B: نگه‌داری موقت (flag کردن)
# هیچ کاری نکنید - بعداً حذف می‌شود
```

---

### Phase 2: Cleanup فایل‌های آلوده (3-4 روز)

**مرحله 2.1: حذف Russian Gateway Files (27 فایل)**
```bash
# طبق MASTER-CLEANUP-GUIDE
# Week 1, Days 3-5
rm app/external/yookassa_webhook.py
rm app/external/wata_webhook.py
# ... 27 فایل
```

**مرحله 2.2: Surgical Removal از Core Files**
```bash
# Week 2, Days 1-3
# حذف Russian gateway references از:
# - app/services/payment_service.py
# - app/services/subscription_service.py
# - app/handlers/subscription/purchase.py
# - app/config.py
# ... 28 فایل
```

---

### Phase 3: یکپارچه‌سازی (2-3 روز)

**مرحله 3.1: Currency Migration**
```bash
# تبدیل kopeks → tomans
# طبق PRD FR10.2
```

**مرحله 3.2: Localization Update**
```bash
# فارسی primary، انگلیسی secondary
# طبق PRD FR11
```

**مرحله 3.3: Testing & Verification**
```bash
# اجرای تست‌ها
pytest tests/ -v

# بررسی عدم وجود Russian gateway references
rg "yookassa|wata|heleket" app/ --type py
```

---

## 🎯 نتیجه‌گیری

### فایل‌های قابل Merge مستقیم

✅ **~50 فایل** (BMAD artifacts + features جدید تمیز)

**برنچ‌های مفید:**
- ✅ `origin/fix/replace-kopek-to-toman` - **باید merge شود** (PRD FR10.2)
- ✅ `origin/debug/language` - **مفید** - بهبودهای localization

### فایل‌های نیازمند بازنویسی

⚠️ **~95 فایل** (Russian gateway files + contaminated core files)

**برنچ‌های نیازمند بازنویسی:**
- 🚨 `origin/feat/multi-tenant-0` - **انحراف از PRD** - استفاده از Bot به جای Tenant
- 🚨 `origin/feat/multi-tenant-1` - **انحراف از PRD** - ادامه multi-tenant-0
- ⚠️ `origin/feat/payments` - **نیاز به بررسی** - ممکن است Russian gateways داشته باشد
- ⚠️ `origin/feat/tenant` - **نیاز به بررسی** - ممکن است با PRD سازگار باشد

### استراتژی پیشنهادی

1. ✅ **Merge فایل‌های تمیز** از برنچ فعلی
2. ✅ **Merge `origin/fix/replace-kopek-to-toman`** - دقیقاً PRD FR10.2
3. ✅ **Merge `origin/debug/language`** - بهبودهای مفید
4. ❌ **Merge نکنید** فایل‌های آلوده از origin/dev
5. ⚠️ **بررسی دقیق** `origin/feat/payments` و `origin/feat/tenant`
6. 🚨 **بازنویسی** `origin/feat/multi-tenant-0/1` - تبدیل Bot → Tenant
7. ✅ **بازنویسی** فایل‌های آلوده طبق PRD
8. ✅ **حذف CloudPayments** (برای سازگاری با PRD)

---

## 📝 نکات مهم

1. **از origin/dev استفاده نکنید** برای فایل‌های Russian gateway
2. **از برنچ فعلی استفاده کنید** و سپس cleanup انجام دهید
3. **CloudPayments را حذف کنید** (برای سازگاری با PRD)
4. **طبق MASTER-CLEANUP-GUIDE عمل کنید** (4 هفته)
5. **PRD را به‌روز کنید** با تصمیمات جدید
6. ✅ **Merge `origin/fix/replace-kopek-to-toman`** - این دقیقاً PRD FR10.2 است
7. ✅ **Merge `origin/debug/language`** - بهبودهای مفید localization
8. 🚨 **بازنویسی `origin/feat/multi-tenant-0/1`** - تبدیل Bot → Tenant طبق PRD
9. ⚠️ **بررسی دقیق `origin/feat/payments` و `origin/feat/tenant`** قبل از merge

---

## 🔍 خلاصه برنچ‌های جدید

### ✅ برنچ‌های مفید - Merge مستقیم

| برنچ | وضعیت | دلیل | Action |
|------|-------|------|--------|
| `origin/fix/replace-kopek-to-toman` | ✅ **مفید** | دقیقاً PRD FR10.2 | **Merge کنید** |
| `origin/debug/language` | ✅ **مفید** | بهبود localization | **Merge کنید** |

### ⚠️ برنچ‌های نیازمند بررسی

| برنچ | وضعیت | دلیل | Action |
|------|-------|------|--------|
| `origin/feat/payments` | ⚠️ **بررسی نیاز دارد** | ممکن است Russian gateways داشته باشد | **بررسی کنید** |
| `origin/feat/tenant` | ⚠️ **بررسی نیاز دارد** | ممکن است با PRD سازگار باشد | **بررسی کنید** |
| `origin/dev` | ⚠️ **بررسی نیاز دارد** | شامل localization refactoring + upstream changes | **بررسی کنید** |

### ✅ برنچ‌های قابل استفاده (با نگه‌داری bot_id)

| برنچ | وضعیت | درصد سازگاری | Action |
|------|-------|-------------|--------|
| `origin/feat/multi-tenant-0` | ✅ **قابل استفاده** | **85-90%** | **Merge کنید** (با نگه‌داری bot_id) |
| `origin/feat/multi-tenant-1` | ✅ **قابل استفاده** | **85-90%** | **Merge کنید** (با نگه‌داری bot_id) |

**نکته:** اگر `bot_id` را همان `bot_id` نگه داریم، 85-90% کد قابل استفاده است.

**نکته:** از ایده‌های این برنچ‌ها استفاده کنید اما با نام‌گذاری PRD بازنویسی کنید.

---

**تهیه شده توسط:** Winston (Architect Agent)  
**تاریخ:** 2025-12-26  
**وضعیت:** ✅ Ready for Review

