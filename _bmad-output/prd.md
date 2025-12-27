---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
status: 'complete'
completedAt: '2025-12-25'
inputDocuments:
  - '_bmad-output/project-planning-artifacts/research/technical-multi-tenancy-architecture-research-2025-12-25.md'
  - '_bmad-output/analysis/brainstorming-session-2025-12-25.md'
  - '_bmad-output/project-planning-artifacts/ux-design-specification.md'
  - '_bmad-output/architecture.md'
  - 'docs/index.md'
documentCounts:
  briefs: 0
  research: 1
  brainstorming: 1
  ux: 1
  architecture: 1
  projectDocs: 1
workflowType: 'prd'
lastStep: 11
project_name: 'remnabot'
user_name: 'K4lantar4'
date: '2025-12-25'
---

# Product Requirements Document - remnabot Multi-Tenant SaaS

**Author:** K4lantar4
**Date:** 2025-12-25
**Version:** 1.0

---

## Executive Summary

### چشم‌انداز محصول

تبدیل remnabot از یک ربات VPN تک‌نفره به پلتفرم SaaS Multi-tenant که ۱۰۰-۲۰۰ ربات مستقل را با isolation کامل میزبانی کند. هر tenant (صاحب کسب‌وکار VPN) ربات اختصاصی خود را با برندینگ، تنظیمات پرداخت و کاربران مجزا خواهد داشت.

### اهداف کلیدی

| هدف | معیار موفقیت |
|-----|-------------|
| **Multi-tenancy** | پشتیبانی از ۱۰۰-۲۰۰ ربات مستقل |
| **Data Isolation** | جداسازی کامل داده‌ها با PostgreSQL RLS |
| **Iranian Payments** | ZarinPal + کارت به کارت فعال |
| **MVP Ready** | اولین tenant در ۴-۶ هفته |

### ذی‌نفعان

| نقش | نیاز اصلی |
|-----|----------|
| **Super Admin** | مدیریت پلتفرم، billing، نظارت بر tenants |
| **Tenant Admin** | مدیریت ربات، کاربران، پرداخت‌ها، تنظیمات |
| **End User** | خرید اشتراک VPN، مدیریت کیف پول، پشتیبانی |

---

## Product Scope

### در محدوده (In Scope)

#### فاز ۱ - Foundation
- ✅ افزودن جدول tenants و bot_id به تمام جداول موجود
- ✅ TenantMiddleware برای استخراج tenant از bot_token
- ✅ PostgreSQL RLS policies برای جداسازی داده
- ✅ Tenant Context با ContextVar
- ✅ Migration داده‌های موجود به default tenant

#### فاز ۲ - MVP
- ✅ Webhook routing با `/webhook/{bot_token}`
- ✅ Per-tenant configuration از دیتابیس
- ✅ سیستم پرداخت ZarinPal per-tenant
- ✅ سیستم پرداخت کارت به کارت با تأیید دستی
- ✅ کیف پول یکپارچه برای کاربران
- ✅ کانال گزارش Telegram با تاپیک‌ها
- ✅ حذف درگاه‌های پرداخت روسی
- ✅ تبدیل واحد پول از کوپک به تومان
- ✅ Localization فارسی (primary) + انگلیسی (secondary)

#### فاز ۳ - Scale (Post-MVP)
- ✅ Super Admin dashboard
- ✅ Tenant billing و subscription management
- ✅ Analytics per tenant
- ✅ API documentation برای integrations
- ✅ Horizontal scaling support

### خارج از محدوده (Out of Scope)

- ❌ MiniApp برای flowهای حیاتی (به دلایل اعتماد)
- ❌ Microservices architecture (Monolith کافی برای MVP)
- ❌ Database-per-tenant (Row-level isolation کافی)
- ❌ Kubernetes deployment (Docker Compose برای MVP)
- ❌ Real-time chat support (فاز آینده)

---

## Functional Requirements

### فاز ۱ - Foundation (هفته ۱-۲)

#### FR1: Tenant Management Core

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR1.1 | سیستم باید جدول tenants با فیلدهای id, bot_token, bot_username, owner_telegram_id, status, plan, settings ایجاد کند | P0 | جدول با تمام فیلدها ایجاد شود |
| FR1.2 | سیستم باید bot_id را به تمام جداول موجود (users, subscriptions, payments, etc.) اضافه کند | P0 | تمام ۳۵+ جدول دارای bot_id باشند |
| FR1.3 | سیستم باید داده‌های موجود را به default tenant با id=1 migrate کند | P0 | تمام رکوردهای موجود bot_id=1 داشته باشند |
| FR1.4 | سیستم باید unique constraint روی (bot_id, telegram_id) برای جدول users داشته باشد | P0 | کاربران unique per tenant باشند |

#### FR2: Tenant Context & Isolation

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR2.1 | سیستم باید TenantMiddleware برای استخراج tenant از bot_token در URL path پیاده‌سازی کند | P0 | Tenant از `/webhook/{bot_token}` استخراج شود |
| FR2.2 | سیستم باید از Python ContextVar برای propagate کردن tenant context استفاده کند | P0 | Tenant در تمام layers قابل دسترسی باشد |
| FR2.3 | سیستم باید PostgreSQL session variable `app.current_tenant` را برای هر request تنظیم کند | P0 | RLS policies کار کنند |
| FR2.4 | سیستم باید RLS policies را روی تمام جداول tenant-aware فعال کند | P0 | Queries فقط داده‌های tenant فعلی را برگردانند |

#### FR3: Database Migration

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR3.1 | سیستم باید Alembic migrations برای تمام تغییرات schema ایجاد کند | P0 | Migration‌ها قابل rollback باشند |
| FR3.2 | سیستم باید indexes بهینه روی (bot_id, ...) ایجاد کند | P1 | Query performance مناسب باشد |
| FR3.3 | سیستم باید foreign key از bot_id به tenants.id اضافه کند | P0 | Referential integrity حفظ شود |

---

### فاز ۲ - MVP (هفته ۳-۶)

#### FR4: Webhook Routing

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR4.1 | سیستم باید webhooks را در `/webhook/{bot_token}` دریافت کند | P0 | Telegram updates به tenant صحیح route شوند |
| FR4.2 | سیستم باید برای bot_token نامعتبر 404 برگرداند | P0 | امنیت webhook حفظ شود |
| FR4.3 | سیستم باید aiogram Bot instance per tenant ایجاد کند | P0 | هر tenant Bot مجزا داشته باشد |

#### FR5: Per-Tenant Configuration

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR5.1 | سیستم باید TenantConfig را از دیتابیس (JSONB) بخواند نه env vars | P0 | تنظیمات per-tenant قابل تغییر باشد |
| FR5.2 | سیستم باید config شامل: bot_token, zarinpal_merchant_id, card_number, trial_days, default_language داشته باشد | P0 | تمام تنظیمات لازم موجود باشد |
| FR5.3 | سیستم باید TenantConfig را در Redis با TTL=5min cache کند | P1 | Performance مناسب باشد |
| FR5.4 | سیستم باید cache را در صورت تغییر config invalidate کند | P1 | تغییرات فوری اعمال شوند |

#### FR6: Payment - ZarinPal Integration

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR6.1 | سیستم باید از merchant_id هر tenant برای ZarinPal استفاده کند | P0 | پول به حساب tenant واریز شود |
| FR6.2 | سیستم باید callback URL شامل tenant identifier باشد | P0 | Callback به tenant صحیح route شود |
| FR6.3 | سیستم باید پرداخت موفق را در جدول payments با bot_id ثبت کند | P0 | تراکنش‌ها قابل ردیابی باشند |
| FR6.4 | سیستم باید در صورت نبود merchant_id، ZarinPal را غیرفعال نشان دهد | P1 | UX واضح باشد |

#### FR7: Payment - Card-to-Card

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR7.1 | سیستم باید شماره کارت tenant را به کاربر نمایش دهد | P0 | کاربر بتواند پرداخت کند |
| FR7.2 | سیستم باید امکان ارسال تصویر رسید را فراهم کند | P0 | کاربر رسید ارسال کند |
| FR7.3 | سیستم باید رسید را در کانال گزارش tenant با دکمه تأیید/رد ارسال کند | P0 | Admin بتواند تأیید کند |
| FR7.4 | سیستم باید کد پیگیری unique برای هر تراکنش ایجاد کند | P0 | ردیابی ممکن باشد |
| FR7.5 | سیستم باید پس از تأیید Admin، اشتراک را فعال کند | P0 | Flow کامل باشد |
| FR7.6 | سیستم باید پس از رد Admin، به کاربر اطلاع دهد | P0 | UX کامل باشد |

#### FR8: Wallet System

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR8.1 | سیستم باید balance کاربر را per tenant نگهداری کند | P0 | Balance جدا per tenant |
| FR8.2 | سیستم باید شارژ کیف پول با ZarinPal و کارت به کارت امکان‌پذیر کند | P0 | شارژ کار کند |
| FR8.3 | سیستم باید خرید instant با کیف پول (بدون gateway) امکان‌پذیر کند | P0 | خرید سریع کار کند |
| FR8.4 | سیستم باید تاریخچه تراکنش‌های کیف پول را نمایش دهد | P1 | شفافیت برای کاربر |

#### FR9: Tenant Admin Channel

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR9.1 | سیستم باید channel_id و topic_ids را در TenantConfig ذخیره کند | P0 | کانال per tenant |
| FR9.2 | سیستم باید تراکنش‌های لحظه‌ای را در تاپیک مربوطه ارسال کند | P0 | Real-time visibility |
| FR9.3 | سیستم باید رسیدهای کارت به کارت را در تاپیک جداگانه با inline buttons ارسال کند | P0 | تأیید سریع |
| FR9.4 | سیستم باید دکمه‌های ✅ تأیید و ❌ رد در پیام رسید داشته باشد | P0 | One-click approval |

#### FR10: Russian Artifacts Removal

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR10.1 | سیستم باید درگاه‌های پرداخت روسی (YooKassa, Heleket, Tribute, MulenPay, Pal24, Platega, WATA) را حذف کند | P0 | فقط ZarinPal, Card-to-Card, CryptoBot باقی بماند |
| FR10.2 | سیستم باید واحد پول را از kopeks به tomans تغییر دهد | P0 | تمام مقادیر به تومان باشد |
| FR10.3 | سیستم باید کامنت‌ها و docstring‌های روسی را به انگلیسی تبدیل کند | P1 | کد خوانا باشد |
| FR10.4 | سیستم باید logger messages روسی را به انگلیسی تغییر دهد | P1 | لاگ‌ها قابل فهم باشند |

#### FR11: Localization

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR11.1 | سیستم باید زبان پیش‌فرض per tenant قابل تنظیم باشد | P0 | هر tenant زبان خود را داشته باشد |
| FR11.2 | سیستم باید فارسی (fa) به عنوان primary language پشتیبانی کند | P0 | تمام متن‌ها فارسی موجود باشد |
| FR11.3 | سیستم باید انگلیسی (en) به عنوان secondary language پشتیبانی کند | P1 | Fallback موجود باشد |
| FR11.4 | سیستم باید تمام user-facing strings از localization keys استفاده کنند | P0 | No hardcoded strings |

#### FR12: User Journey - Purchase

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR12.1 | سیستم باید خرید اشتراک در حداکثر ۳ کلیک ممکن باشد | P0 | UX ساده |
| FR12.2 | سیستم باید لیست پلن‌ها با قیمت واضح نمایش دهد | P0 | شفافیت قیمت |
| FR12.3 | سیستم باید روش‌های پرداخت موجود (per tenant) را نمایش دهد | P0 | گزینه‌های مناسب |
| FR12.4 | سیستم باید خلاصه خرید قبل از پرداخت نهایی نمایش دهد | P0 | تأیید قبل از پرداخت |
| FR12.5 | سیستم باید پیام موفقیت 🎉 با جزئیات اشتراک ارسال کند | P0 | Feedback مناسب |

#### FR13: User Journey - Wallet

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR13.1 | سیستم باید موجودی کیف پول را در منوی اصلی نمایش دهد | P0 | Visibility |
| FR13.2 | سیستم باید شارژ کیف پول با مبلغ دلخواه امکان‌پذیر باشد | P1 | انعطاف |
| FR13.3 | سیستم باید در صورت موجودی کافی، پرداخت با کیف پول پیشنهاد دهد | P1 | Smart default |

#### FR14: Admin Journey - Approval

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR14.1 | سیستم باید تأیید پرداخت در ۱ کلیک ممکن باشد | P0 | سرعت |
| FR14.2 | سیستم باید پس از تأیید/رد، پیام تأیید به admin نمایش دهد | P0 | Feedback |
| FR14.3 | سیستم باید به‌روزرسانی خودکار وضعیت کاربر پس از تأیید انجام دهد | P0 | Automation |

---

### فاز ۳ - Scale (Post-MVP)

#### FR15: Super Admin Features

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR15.1 | سیستم باید Super Admin بتواند تمام tenants را مشاهده کند | P1 | Overview |
| FR15.2 | سیستم باید Super Admin بتواند tenant جدید ایجاد کند | P1 | Onboarding |
| FR15.3 | سیستم باید Super Admin بتواند tenant را غیرفعال کند | P1 | Control |
| FR15.4 | سیستم باید RLS را برای Super Admin bypass کند با audit logging | P1 | امنیت + دسترسی |

#### FR16: Tenant Billing

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR16.1 | سیستم باید پلن‌های مختلف (Free, Starter, Pro) برای tenants داشته باشد | P2 | Business model |
| FR16.2 | سیستم باید محدودیت تعداد کاربران per plan اعمال کند | P2 | Enforcement |
| FR16.3 | سیستم باید درخواست تسویه از tenant admin دریافت کند | P2 | Finance |

#### FR17: Analytics

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR17.1 | سیستم باید آمار تراکنش‌ها per tenant نمایش دهد | P2 | Insights |
| FR17.2 | سیستم باید آمار کاربران فعال per tenant نمایش دهد | P2 | Metrics |
| FR17.3 | سیستم باید گزارش روزانه/هفتگی/ماهانه تولید کند | P3 | Reporting |

---

## Non-Functional Requirements

### NFR1: Performance

| ID | Requirement | Target MVP | Target 6-Month |
|----|-------------|------------|----------------|
| NFR1.1 | Response time for webhook processing | < 500ms | < 200ms |
| NFR1.2 | Database query time | < 100ms | < 50ms |
| NFR1.3 | Concurrent webhook handling | 50 req/s | 200 req/s |
| NFR1.4 | Memory usage per tenant | < 50MB | < 30MB |

### NFR2: Scalability

| ID | Requirement | Target MVP | Target 6-Month |
|----|-------------|------------|----------------|
| NFR2.1 | Number of tenants supported | 100-200 | 500+ |
| NFR2.2 | Users per tenant | 10,000 | 50,000 |
| NFR2.3 | Horizontal scaling capability | Docker Compose | Kubernetes-ready |

### NFR3: Security

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR3.1 | Data isolation via PostgreSQL RLS | P0 |
| NFR3.2 | JWT tokens with bot_id claim | P0 |
| NFR3.3 | Bot token validation per request | P0 |
| NFR3.4 | No cross-tenant data leakage | P0 |
| NFR3.5 | Audit logging for Super Admin actions | P1 |
| NFR3.6 | SSL/TLS for all communications | P0 |

### NFR4: Reliability

| ID | Requirement | Target MVP | Target 6-Month |
|----|-------------|------------|----------------|
| NFR4.1 | Uptime | 99% | 99.5% |
| NFR4.2 | Data backup frequency | Daily | Every 6 hours |
| NFR4.3 | Recovery Time Objective (RTO) | < 4 hours | < 1 hour |
| NFR4.4 | Recovery Point Objective (RPO) | < 24 hours | < 6 hours |

### NFR5: Maintainability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR5.1 | Test coverage | 70% (MVP), 85% (6-month) |
| NFR5.2 | Code documentation | English comments/docstrings |
| NFR5.3 | Structured logging with bot_id | All requests |
| NFR5.4 | Database migrations rollback capability | All migrations |

### NFR6: Usability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR6.1 | Purchase completion time | < 60 seconds |
| NFR6.2 | Maximum clicks for any action | ≤ 3 clicks |
| NFR6.3 | Admin approval time | < 10 seconds |
| NFR6.4 | Mobile-first design | 95%+ mobile users |

---

## User Interface Requirements

### UI1: Telegram Bot - End User

**Navigation (Reply Keyboard):**
```
┌──────────┬──────────┐
│ 📦 خرید  │ 👤 حساب  │
├──────────┼──────────┤
│ 💳 کیف   │ 🆘 پشتیبانی │
└──────────┴──────────┘
```

**Key Screens:**
1. Welcome message با Reply Keyboard
2. Plan selection با Inline Keyboard
3. Payment method selection
4. Confirmation summary
5. Success/failure message

### UI2: Telegram Bot - Tenant Admin

**Navigation (Reply Keyboard):**
```
┌──────────┬──────────┐
│ 📊 داشبورد│ 👥 کاربران│
├──────────┼──────────┤
│ 💰 مالی  │ ⚙️ تنظیم │
└──────────┴──────────┘
```

**Key Screens:**
1. Dashboard با آمار کلیدی
2. User management list
3. Payment approval (in channel)
4. Settings management

### UI3: Report Channel

**Topic Structure:**
- 📊 تراکنش‌های لحظه‌ای
- 🧾 رسیدهای کارت به کارت (با دکمه تأیید/رد)
- ⚠️ هشدارها

---

## Technical Constraints

| Constraint | Impact | Mitigation |
|------------|--------|------------|
| Telegram API limits | 8 buttons per row, rate limiting | Pagination, smart button layout |
| PostgreSQL RLS | All queries filtered by tenant | Proper session variable setting |
| Iranian payment gateways | Manual approval for card-to-card | Channel notification system |
| Trust requirements | No MiniApp for payments | Inline Keyboard only |
| Existing codebase | 35+ tables to migrate | Phased migration with rollback |

---

## Dependencies

### External Dependencies

| Dependency | Purpose | Risk |
|------------|---------|------|
| Telegram Bot API | Core communication | Low (stable) |
| ZarinPal API | Iranian payments | Medium (API changes) |
| PostgreSQL 15+ | RLS support | Low |
| Redis | Caching | Low |

### Internal Dependencies

| Component | Depends On |
|-----------|------------|
| Webhook Handler | TenantMiddleware |
| Payment Services | TenantConfig |
| Bot Handlers | Tenant Context |
| Database Queries | RLS Policies |

---

## Assumptions

1. ✅ تلگرام webhook را به‌درستی به سرور ما ارسال می‌کند
2. ✅ ZarinPal API برای tenants ایرانی در دسترس است
3. ✅ کاربران نهایی عمدتاً از موبایل استفاده می‌کنند (95%+)
4. ✅ Tenant admins به کانال تلگرام برای نوتیفیکیشن‌ها دسترسی دارند
5. ✅ PostgreSQL RLS performance برای ۱۰۰-۲۰۰ tenant کافی است

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Data leak between tenants | Low | Critical | RLS + Testing + Code review |
| Performance degradation | Medium | High | Caching + Index optimization |
| Migration data loss | Low | Critical | Backup before each phase |
| Payment integration bugs | Medium | High | Sandbox testing + Logging |
| Telegram API changes | Low | Medium | aiogram updates tracking |

---

## Success Metrics

### MVP Success Criteria

| Metric | Target |
|--------|--------|
| First tenant onboarded | ✅ |
| Purchase completion rate | > 80% |
| Admin approval time | < 5 minutes |
| System uptime | > 99% |
| Zero cross-tenant data leaks | ✅ |

### 6-Month Success Criteria

| Metric | Target |
|--------|--------|
| Active tenants | 50+ |
| Monthly Recurring Revenue | $500+ |
| User satisfaction | > 4/5 |
| Test coverage | > 85% |

---

## Implementation Phases

### فاز ۱ - Foundation (هفته ۱-۲)

**Scope:**
- FR1: Tenant Management Core
- FR2: Tenant Context & Isolation
- FR3: Database Migration

**Deliverables:**
- ✅ Tenants table created
- ✅ bot_id added to all tables
- ✅ RLS policies enabled
- ✅ TenantMiddleware implemented
- ✅ Existing data migrated

**Checkpoint:** تمام queries فقط داده‌های tenant فعلی را برگردانند

---

### فاز ۲ - MVP (هفته ۳-۶)

**Scope:**
- FR4: Webhook Routing
- FR5: Per-Tenant Configuration
- FR6: ZarinPal Integration
- FR7: Card-to-Card Payment
- FR8: Wallet System
- FR9: Admin Channel
- FR10: Russian Artifacts Removal
- FR11: Localization
- FR12-14: User Journeys

**Deliverables:**
- ✅ Multiple bots can run independently
- ✅ Iranian payments working
- ✅ First test tenant operational
- ✅ Russian artifacts removed

**Checkpoint:** اولین tenant واقعی بتواند کاربران را سرویس دهد

---

### فاز ۳ - Scale (Post-MVP)

**Scope:**
- FR15: Super Admin Features
- FR16: Tenant Billing
- FR17: Analytics

**Deliverables:**
- ✅ Super Admin dashboard
- ✅ Tenant subscription plans
- ✅ Analytics per tenant

**Checkpoint:** پلتفرم آماده onboarding تجاری tenants

---

## Glossary

| Term | Definition |
|------|------------|
| **Tenant** | یک مشتری پلتفرم که ربات VPN خود را دارد |
| **Tenant Admin** | مدیر/صاحب یک tenant |
| **End User** | کاربر نهایی که از ربات tenant استفاده می‌کند |
| **Super Admin** | مدیر کل پلتفرم |
| **RLS** | Row-Level Security - جداسازی داده در سطح دیتابیس |
| **bot_token** | Token یکتای هر ربات تلگرام که برای شناسایی tenant استفاده می‌شود |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-25 | K4lantar4 | Initial PRD creation |

---

*PRD تکمیل شد - 2025-12-25*
*تولید شده توسط BMAD PRD Workflow*
