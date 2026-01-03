# راهنمای خواندن مستندات Multi-Tenant - ترتیب مطالعه

**تاریخ به‌روزرسانی:** 2025-12-15  
**وضعیت:** به‌روزرسانی شده - فقط مستندات جدید

---

## ⭐ شروع از اینجا!

**📄 `MASTER-IMPLEMENTATION-GUIDE.md`** ⭐⭐⭐ **شروع از اینجا!**
- **هدف:** راهنمای اصلی پیاده‌سازی - منبع اصلی
- **محتوا:** وضعیت فعلی، مشکلات بحرانی، برنامه پیاده‌سازی، قوانین طلایی
- **زمان مطالعه:** 45-60 دقیقه
- **اولویت:** ⭐⭐⭐ (ضروری - ابتدا این را بخوانید!)

---

## 📚 ترتیب مطالعه مستندات

### مرحله 1: درک کلی معماری (Foundation)

#### 1.1. Master Implementation Guide
**📄 `MASTER-IMPLEMENTATION-GUIDE.md`** ⭐⭐⭐ **شروع از اینجا!**
- **هدف:** راهنمای اصلی پیاده‌سازی
- **محتوا:** 
  - وضعیت فعلی (چه چیزهایی پیاده شده/نشده)
  - مشکلات بحرانی
  - برنامه پیاده‌سازی (Phase 0-5)
  - قوانین طلایی
  - Feature Flags & Tenant Management (Phase 5)
- **زمان مطالعه:** 45-60 دقیقه
- **اولویت:** ⭐⭐⭐ (ضروری)

#### 1.2. Implementation Guide Step-by-Step
**📄 `implementation-guide-step-by-step.md`** ⭐⭐
- **هدف:** راهنمای مرحله‌به‌مرحله پیاده‌سازی
- **محتوا:** مراحل دقیق پیاده‌سازی با مثال‌های کد
- **زمان مطالعه:** 60-75 دقیقه
- **اولویت:** ⭐⭐ (مهم)

#### 1.3. Redundancy Analysis & Refactoring Plan
**📄 `analysis/redundancy-analysis-and-refactoring-plan.md`** ⭐⭐
- **هدف:** تحلیل redundancy و برنامه ریفکتور
- **محتوا:** مشکلات schema، برنامه حذف redundancy
- **زمان مطالعه:** 45-60 دقیقه
- **اولویت:** ⭐⭐ (مهم)

---

### مرحله 2: Feature Flags & Configuration (Core System)

#### 2.1. Categorization & Extraction
**📄 `tenant-configs-categorization.md`** ⭐ **شروع از اینجا برای Configs**
- **هدف:** دسته‌بندی کامل تمام configs از `.env.example`
- **محتوا:**
  - MASTER_ONLY configs (45 config)
  - TENANT_CONFIGURABLE configs (477 config)
  - Feature flag mapping
  - Storage strategy
- **زمان مطالعه:** 45-60 دقیقه
- **اولویت:** ⭐⭐⭐ (ضروری)

---

### مرحله 3: UX & User Flows (User Experience)

#### 3.1. Registration & Onboarding
**📄 `tenant-registration-ux-complete.md`**
- **هدف:** UX کامل ثبت‌نام و onboarding
- **محتوا:**
  - Registration flow (5 steps)
  - Config cloning strategy
  - Onboarding guide
  - Personalization options
- **زمان مطالعه:** 30-40 دقیقه
- **اولویت:** ⭐⭐⭐ (ضروری)

#### 3.2. Master Admin UX
**📄 `tenant-bots-admin-ux-design.md`** ⭐ **شروع از اینجا برای Admin Panel**
- **هدف:** طراحی کامل UX برای Master Admin Panel
- **محتوا:**
  - Menu structure (3 levels)
  - Config categorization
  - Database relationships
  - UI mockups
- **زمان مطالعه:** 60-75 دقیقه
- **اولویت:** ⭐⭐⭐ (ضروری)

---

### مرحله 4: Implementation Details (Technical)

#### 4.1. Visual Diagrams & Navigation
**📄 `tenant-bots-admin-ux-diagram.md`**
- **هدف:** دیاگرام‌های بصری و navigation flows
- **محتوا:**
  - Visual menu structure
  - Complete navigation flow
  - Callback → Handler → Database mapping
  - FSM states
- **زمان مطالعه:** 40-50 دقیقه
- **اولویت:** ⭐⭐ (مهم)

#### 4.2. Complete Callback Mapping
**📄 `tenant-bots-callback-handler-mapping.md`** ⭐ **مرجع پیاده‌سازی**
- **هدف:** Mapping کامل برای پیاده‌سازی
- **محتوا:**
  - Complete callback → handler → database table
  - FSM state handlers
  - Database operations
  - Implementation checklist
- **زمان مطالعه:** 50-60 دقیقه
- **اولویت:** ⭐⭐⭐ (ضروری برای پیاده‌سازی)

---

### مرحله 5: Billing & Settlement (Financial)

#### 5.1. Billing Model Design
**📄 `docs/analysis/billing-model-design.md`** ⭐ **برای Billing**
- **هدف:** طراحی مدل بیلینگ و تسویه حساب با tenants
- **محتوا:**
  - مدل بیلینگ (Traffic-based)
  - Flowهای شارژ و کسر از کیف پول
  - جداول پیشنهادی (tenant_wallet_transactions, tenant_traffic_usage)
  - Admin Panel برای Billing
  - Reports و Notifications
- **زمان مطالعه:** 40-50 دقیقه
- **اولویت:** ⭐⭐⭐ (ضروری برای Billing)

---

### مرحله 6: Technical Challenges (Advanced)

#### 6.1. Technical Analysis
**📄 `technical-challenges-analysis.md`**
- **هدف:** تحلیل چالش‌های فنی و راهکارها
- **محتوا:**
  - Bot lifecycle management
  - Database query filtering
  - FSM isolation
  - Context propagation
  - Scalability
- **زمان مطالعه:** 45-60 دقیقه
- **اولویت:** ⭐⭐ (مهم)

#### 6.2. Comprehensive Code Review
**📄 `docs/analysis/comprehensive-code-review.md`** ⭐⭐
- **هدف:** بررسی جامع کد و مشکلات
- **محتوا:**
  - مشکلات بحرانی
  - Component mapping
  - Data flows & isolation issues
  - Feature separation (Master vs Tenant)
  - Refactoring plan
- **زمان مطالعه:** 60-75 دقیقه
- **اولویت:** ⭐⭐ (مهم)

---

## 🎯 مسیرهای مطالعه (بر اساس نیاز)

### مسیر 1: برای شروع پیاده‌سازی (Recommended)
```
1. tenant-configs-categorization.md (درک configs)
2. tenant-bots-admin-ux-design.md (درک UX)
3. tenant-bots-callback-handler-mapping.md (مرجع پیاده‌سازی)
4. technical-challenges-analysis.md (چالش‌ها)
```

### مسیر 2: برای درک کلی معماری
```
1. MASTER-IMPLEMENTATION-GUIDE.md ⭐ (شروع از اینجا)
2. implementation-guide-step-by-step.md (مراحل پیاده‌سازی)
3. tenant-configs-categorization.md (configs)
4. tenant-bots-admin-ux-design.md (admin panel)
```

### مسیر 3: برای بررسی مشکلات و ریفکتور
```
1. docs/analysis/comprehensive-code-review.md (مشکلات و بررسی کد)
2. docs/analysis/redundancy-analysis-and-refactoring-plan.md (redundancy)
3. technical-challenges-analysis.md (راهکارها)
```

---

## 📊 خلاصه مستندات (فقط مستندات جدید)

| مستند | صفحات | زمان مطالعه | اولویت | وضعیت |
|-------|-------|------------|--------|-------|
| `MASTER-IMPLEMENTATION-GUIDE.md` ⭐ | ~414 lines | 45-60 min | ⭐⭐⭐ | ✅ Master Document |
| `implementation-guide-step-by-step.md` | ~558 lines | 60-75 min | ⭐⭐ | ✅ به‌روز شده |
| `analysis/redundancy-analysis-and-refactoring-plan.md` | ~628 lines | 45-60 min | ⭐⭐ | ✅ به‌روز شده |
| `tenant-configs-categorization.md` | ~790 lines | 45-60 min | ⭐⭐⭐ | ✅ به‌روز شده |
| `tenant-bots-callback-handler-mapping.md` | ~2000 lines | 50-60 min | ⭐⭐⭐ | ✅ مرجع پیاده‌سازی |
| `tenant-bots-admin-ux-design.md` | ~2000 lines | 60-75 min | ⭐⭐⭐ | ✅ UX Design |
| `analysis/comprehensive-code-review.md` | ~473+ lines | 60-75 min | ⭐⭐ | ✅ بررسی کد |
| `analysis/billing-model-design.md` | ~480 lines | 40-50 min | ⭐⭐⭐ | ✅ Billing Design |

**جمع کل:** ~8 مستند اصلی | **زمان کل:** ~6-8 ساعت

---

## 🗑️ مستندات حذف شده

### حذف شده (قدیمی/تکراری):
- ❌ `multi-tenant-design-document.md` → جایگزین شده با `MASTER-IMPLEMENTATION-GUIDE.md`
- ❌ `multi-tenant-design-document-fa.md` → duplicate
- ❌ `multi-tenant-migration-plan.md` → اطلاعات در `MASTER-IMPLEMENTATION-GUIDE.md`
- ❌ `feature-flags-and-tenant-management-design.md` → ادغام شده در `MASTER-IMPLEMENTATION-GUIDE.md` (Phase 5)
- ❌ `analysis/multi-tenant-comprehensive-analysis.md` → ادغام شده در `comprehensive-code-review.md`
- ❌ `docs/multi-tenant/` folder → اطلاعات در `MASTER-IMPLEMENTATION-GUIDE.md`

**برای لیست کامل:** به `DOCUMENTATION-CLEANUP-GUIDE.md` مراجعه کنید.

---

## 📁 ساختار فایل‌ها

```
docs/
├── TENANT-DOCS-READING-GUIDE.md ⭐ (این فایل)
├── DOCUMENTATION-CLEANUP-GUIDE.md (راهنمای پاکسازی)
│
├── Master Documents ⭐
│   └── MASTER-IMPLEMENTATION-GUIDE.md ⭐⭐⭐ (شروع از اینجا!)
│
├── Implementation Guides
│   ├── implementation-guide-step-by-step.md ⭐⭐
│   └── analysis/
│       ├── redundancy-analysis-and-refactoring-plan.md ⭐⭐
│       └── comprehensive-code-review.md ⭐⭐
│
├── Reference Documents
│   ├── tenant-configs-categorization.md ⭐ (Configs)
│   ├── tenant-bots-callback-handler-mapping.md ⭐ (Mapping)
│   ├── tenant-bots-admin-ux-design.md ⭐ (UX Design)
│   └── analysis/
│       └── billing-model-design.md ⭐ (Billing)
```

---

## ✅ چک‌لیست مطالعه

### قبل از شروع پیاده‌سازی:
- [ ] خواندن `tenant-configs-categorization.md`
- [ ] خواندن `tenant-bots-admin-ux-design.md`
- [ ] خواندن `tenant-bots-callback-handler-mapping.md`
- [ ] خواندن `technical-challenges-analysis.md`

### برای درک کامل معماری:
- [ ] خواندن `MASTER-IMPLEMENTATION-GUIDE.md` ⭐
- [ ] خواندن `implementation-guide-step-by-step.md`
- [ ] خواندن `tenant-configs-categorization.md`

### برای بررسی مشکلات:
- [ ] خواندن `docs/analysis/comprehensive-code-review.md`
- [ ] خواندن `docs/analysis/redundancy-analysis-and-refactoring-plan.md`

---

## 🚀 شروع سریع

**اگر وقت محدود دارید، این 3 مستند را بخوانید:**

1. **`MASTER-IMPLEMENTATION-GUIDE.md`** ⭐ - راهنمای اصلی
2. **`tenant-configs-categorization.md`** - درک configs
3. **`tenant-bots-callback-handler-mapping.md`** - مرجع پیاده‌سازی

---

---

## 🛠️ مراحل پیاده‌سازی (Implementation Phases)

### Phase 1: Foundation & Database (Week 1)
**هدف:** آماده‌سازی پایه و دیتابیس

**مستندات مورد نیاز:**
- `MASTER-IMPLEMENTATION-GUIDE.md` (Database Schema)
- `docs/analysis/billing-model-design.md` (Billing Tables)

**Tasks:**
- [ ] بررسی و تایید Database Schema
- [ ] ایجاد Migration برای جداول billing (tenant_wallet_transactions, tenant_traffic_usage)
- [ ] اضافه کردن columns به bots table (در صورت نیاز)
- [ ] تست Migration ها

**Deliverables:**
- ✅ Migration files
- ✅ Database schema validated

---

### Phase 2: Config Management System (Week 1-2)
**هدف:** پیاده‌سازی سیستم مدیریت configs

**مستندات مورد نیاز:**
- `tenant-configs-categorization.md` ⭐
- `MASTER-IMPLEMENTATION-GUIDE.md` (Phase 5: Feature Flags)

**Tasks:**
- [ ] ایجاد `ConfigSyncService` برای همگام‌سازی configs
- [ ] پیاده‌سازی CRUD برای `bot_configurations`
- [ ] پیاده‌سازی CRUD برای `bot_feature_flags`
- [ ] ایجاد service برای clone کردن configs از master
- [ ] تست config management

**Deliverables:**
- ✅ ConfigSyncService
- ✅ CRUD operations
- ✅ Config cloning tested

---

### Phase 3: Master Admin Panel - Core (Week 2-3)
**هدف:** پیاده‌سازی منوی اصلی Master Admin

**مستندات مورد نیاز:**
- `tenant-bots-admin-ux-design.md` ⭐
- `tenant-bots-admin-ux-diagram.md`
- `tenant-bots-callback-handler-mapping.md` ⭐

**Tasks:**
- [ ] پیاده‌سازی Main Menu (Level 1)
- [ ] پیاده‌سازی List Bots با pagination
- [ ] پیاده‌سازی Bot Detail Menu (Level 2)
- [ ] پیاده‌سازی Navigation handlers
- [ ] تست navigation flows

**Deliverables:**
- ✅ Main menu functional
- ✅ Bot list with pagination
- ✅ Bot detail view

---

### Phase 4: Master Admin Panel - Feature Flags (Week 3)
**هدف:** پیاده‌سازی مدیریت Feature Flags

**مستندات مورد نیاز:**
- `tenant-bots-admin-ux-design.md` (Section: Feature Flags)
- `tenant-bots-callback-handler-mapping.md` (Feature Flags section)

**Tasks:**
- [ ] پیاده‌سازی Feature Flags menu
- [ ] پیاده‌سازی Toggle functionality
- [ ] پیاده‌سازی Plan-based restrictions
- [ ] پیاده‌سازی Override capability
- [ ] تست feature flag management

**Deliverables:**
- ✅ Feature flags management UI
- ✅ Toggle functionality
- ✅ Plan restrictions working

---

### Phase 5: Master Admin Panel - Payment Methods (Week 3-4)
**هدف:** پیاده‌سازی مدیریت Payment Methods

**مستندات مورد نیاز:**
- `tenant-bots-admin-ux-design.md` (Section: Payment Methods)
- `tenant-bots-callback-handler-mapping.md` (Payment Methods section)

**Tasks:**
- [ ] پیاده‌سازی Payment Methods overview
- [ ] پیاده‌سازی Card-to-Card management
- [ ] پیاده‌سازی Gateway configurations (Zarinpal, YooKassa, etc.)
- [ ] پیاده‌سازی Toggle functionality
- [ ] تست payment methods management

**Deliverables:**
- ✅ Payment methods UI
- ✅ Card management functional
- ✅ Gateway configs working

---

### Phase 6: Master Admin Panel - Configuration (Week 4-5)
**هدف:** پیاده‌سازی سیستم Configuration Management

**مستندات مورد نیاز:**
- `tenant-bots-admin-ux-design.md` (Section: Configuration)
- `tenant-configs-categorization.md` (All categories)
- `tenant-bots-callback-handler-mapping.md` (Configuration section)

**Tasks:**
- [ ] پیاده‌سازی Configuration Categories menu
- [ ] پیاده‌سازی Edit forms برای هر category
- [ ] پیاده‌سازی Validation
- [ ] پیاده‌سازی Save to database
- [ ] تست configuration editing

**Deliverables:**
- ✅ Configuration categories UI
- ✅ Edit forms for all categories
- ✅ Validation and save working

---

### Phase 7: Master Admin Panel - Statistics & Analytics (Week 5)
**هدف:** پیاده‌سازی Statistics و Analytics

**مستندات مورد نیاز:**
- `tenant-bots-admin-ux-design.md` (Section: Statistics & Analytics)
- `tenant-bots-callback-handler-mapping.md` (Statistics section)

**Tasks:**
- [ ] پیاده‌سازی Statistics overview
- [ ] پیاده‌سازی Detailed statistics
- [ ] پیاده‌سازی Revenue charts
- [ ] پیاده‌سازی Analytics queries
- [ ] تست statistics display

**Deliverables:**
- ✅ Statistics views
- ✅ Analytics working
- ✅ Charts displayed

---

### Phase 8: Billing System (Week 6-7)
**هدف:** پیاده‌سازی سیستم Billing و Settlement

**مستندات مورد نیاز:**
- `docs/analysis/billing-model-design.md` ⭐

**Tasks:**
- [ ] پیاده‌سازی `TenantWalletTransaction` model
- [ ] پیاده‌سازی `TenantTrafficUsage` model
- [ ] ایجاد CRUD operations برای wallet
- [ ] پیاده‌سازی `TenantBillingService`
- [ ] پیاده‌سازی Background job برای traffic billing
- [ ] پیاده‌سازی Billing Admin Panel
- [ ] تست billing flows

**Deliverables:**
- ✅ Billing models implemented
- ✅ Billing service functional
- ✅ Background job working
- ✅ Admin panel for billing

---

### Phase 9: Registration & Onboarding (Week 7-8)
**هدف:** پیاده‌سازی Registration Flow

**مستندات مورد نیاز:**
- `tenant-registration-ux-complete.md` ⭐

**Tasks:**
- [ ] پیاده‌سازی Registration FSM
- [ ] پیاده‌سازی Plan selection
- [ ] پیاده‌سازی Activation payment
- [ ] پیاده‌سازی Config cloning
- [ ] پیاده‌سازی Onboarding guide
- [ ] تست registration flow

**Deliverables:**
- ✅ Registration flow complete
- ✅ Config cloning working
- ✅ Onboarding functional

---

### Phase 10: Testing & Refinement (Week 8-9)
**هدف:** تست کامل و رفع مشکلات

**مستندات مورد نیاز:**
- `docs/analysis/comprehensive-code-review.md`
- `docs/analysis/redundancy-analysis-and-refactoring-plan.md`

**Tasks:**
- [ ] Unit tests برای تمام services
- [ ] Integration tests برای flows
- [ ] Performance testing
- [ ] Security audit
- [ ] Bug fixes
- [ ] Documentation updates

**Deliverables:**
- ✅ All tests passing
- ✅ Performance optimized
- ✅ Security validated
- ✅ Documentation complete

---

## 🤖 پرامپت برای دستیار Dev (Chat جدید)

### کپی کنید و در چت جدید با دستیار dev بفرستید:

```
من می‌خواهم پیاده‌سازی Multi-Tenant Admin Panel را شروع کنم. لطفاً قبل از شروع کد، این مستندات را مطالعه کن:

**مستندات ضروری (به ترتیب):**
1. docs/tenant-configs-categorization.md - دسته‌بندی کامل configs (477 config)
2. docs/tenant-bots-admin-ux-design.md - طراحی UX کامل
3. docs/tenant-bots-callback-handler-mapping.md - Mapping کامل callbacks → handlers → database
4. docs/analysis/billing-model-design.md - مدل بیلینگ (اگر Phase 8 را انجام می‌دهی)

**اصول پیاده‌سازی:**
- ✅ همیشه bot_id را در queries فیلتر کن (isolation)
- ✅ از FSM states برای editing استفاده کن
- ✅ تمام configs در bot_configurations ذخیره می‌شوند (نه .env)
- ✅ Feature flags در bot_feature_flags
- ✅ از patterns موجود در app/keyboards/admin.py پیروی کن
- ✅ تمام callbacks باید با prefix "admin_tenant_" شروع شوند
- ✅ قبل از هر commit، isolation را تست کن

**ساختار فایل‌ها:**
- Handlers: app/handlers/admin/tenant_bots.py
- Keyboards: app/keyboards/admin.py (add tenant functions)
- CRUD: app/database/crud/bot*.py
- Models: app/database/models.py (already exists)

**چک‌لیست قبل از commit:**
- [ ] تمام queries با bot_id فیلتر شده‌اند
- [ ] FSM states برای editing اضافه شده
- [ ] Callbacks مطابق با mapping document هستند
- [ ] UI مطابق با UX design است
- [ ] Tests نوشته شده (در صورت امکان)

لطفاً قبل از شروع کد، سوالاتت را بپرس و مطمئن شو که همه چیز را فهمیدی.
```

---

## ✅ چک‌لیست کامل پیاده‌سازی

### قبل از شروع:
- [ ] تمام مستندات Phase مربوطه را خوانده‌ای
- [ ] Database schema را بررسی کرده‌ای
- [ ] Existing code patterns را مطالعه کرده‌ای
- [ ] Environment setup شده است

### در حین پیاده‌سازی:
- [ ] هر handler با bot_id فیلتر می‌کند
- [ ] Callbacks مطابق با mapping document هستند
- [ ] UI مطابق با UX design است
- [ ] Error handling پیاده‌سازی شده
- [ ] Logging اضافه شده

### قبل از Commit:
- [ ] Code review انجام شده
- [ ] Tests نوشته شده (در صورت امکان)
- [ ] Documentation updated
- [ ] No linter errors
- [ ] Isolation tested

---

## 📝 یادداشت‌های مهم

### Configs جدید:
اگر config جدیدی به `.env.example` اضافه شد:
1. به `tenant-configs-categorization.md` اضافه کن
2. دسته‌بندی را مشخص کن (MASTER_ONLY یا TENANT_CONFIGURABLE)
3. Storage location را مشخص کن
4. به tenant bots موجود sync کن (اگر TENANT_CONFIGURABLE است)

### Billing:
- جداول billing هنوز پیاده‌سازی نشده‌اند
- قبل از Phase 8، `billing-model-design.md` را بخوان
- Migration files را از مستندات استخراج کن

### Isolation:
- **همیشه** bot_id را در queries فیلتر کن
- از BaseCRUD با ensure_bot_id_filter استفاده کن
- Test isolation برای هر handler

---

**آخرین به‌روزرسانی:** 2025-12-15  
**نسخه:** 2.0
