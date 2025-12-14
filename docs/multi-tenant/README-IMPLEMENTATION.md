# Multi-Tenant Migration - Implementation Guide

**Version:** 2.0  
**Date:** 2025-12-14  
**Status:** Ready for AI-Assisted Implementation

---

## 🎯 هدف

این مجموعه اسناد برای **AI Assistant** (مثل Cursor AI) طراحی شده تا بتواند بدون نیاز به تفکر، فقط دستورات را دنبال کند و به یک پیاده‌سازی تمیز برسد.

---

## 📚 ساختار اسناد

### اسناد اصلی

1. **[00-overview.md](./00-overview.md)** - نمای کلی معماری
2. **[01-database-schema.md](./01-database-schema.md)** - Schema کامل دیتابیس
3. **[02-code-changes.md](./02-code-changes.md)** - تغییرات کد (خلاصه)
4. **[07-workflow-guide.md](./07-workflow-guide.md)** - راهنمای workflow با تمام incrementها
5. **[10-implementation-guide-detailed.md](./10-implementation-guide-detailed.md)** - دستورالعمل‌های step-by-step
6. **[11-payment-flows-detailed.md](./11-payment-flows-detailed.md)** - Payment flows به تفصیل

### اسناد کمکی

- **[08-increment-selection-guide.md](./08-increment-selection-guide.md)** - راهنمای انتخاب increment
- **[09-workflow-and-assistant-guide.md](./09-workflow-and-assistant-guide.md)** - راهنمای استفاده از AI
- **[START-HERE.md](./START-HERE.md)** - شروع سریع

---

## 🚀 شروع کار

### برای AI Assistant

**مرحله 1: خواندن اسناد**

```
1. Read: 00-overview.md (درک کلی)
2. Read: 01-database-schema.md (درک schema)
3. Read: 07-workflow-guide.md (درک incrementها)
4. Read: 10-implementation-guide-detailed.md (دستورالعمل‌ها)
```

**مرحله 2: شروع با Increment 1.1**

```
1. Open: 10-implementation-guide-detailed.md
2. Find: Increment 1.1
3. Follow: Step-by-step instructions
4. Test: Acceptance criteria
5. Commit: با message مناسب
```

**مرحله 3: ادامه با Increment بعدی**

```
1. Check: Dependencies (در workflow-guide.md)
2. Follow: Next increment instructions
3. Test: Acceptance criteria
4. Commit: با message مناسب
```

### برای Developer

**مرحله 1: مطالعه**

1. خواندن [00-overview.md](./00-overview.md)
2. خواندن [07-workflow-guide.md](./07-workflow-guide.md)
3. انتخاب increment برای شروع (معمولاً 1.1)

**مرحله 2: پیاده‌سازی**

1. باز کردن [10-implementation-guide-detailed.md](./10-implementation-guide-detailed.md)
2. دنبال کردن دستورالعمل‌های step-by-step
3. تست کردن با acceptance criteria
4. Commit کردن تغییرات

---

## 📋 Increment List

### Phase 1: Foundation

- ✅ **1.1** Database Schema - New Tables
- ✅ **1.2** Database Models - New Models
- ✅ **1.3** Bot CRUD Operations
- ✅ **1.4** Feature Flag CRUD
- ✅ **1.4a** Bot Configuration CRUD
- ✅ **1.4b** Payment Card CRUD
- ✅ **1.4c** Bot Plans CRUD
- ✅ **1.5** Bot Context Middleware

### Phase 2: Core Features

- ✅ **2.1** Add bot_id to Users Table
- ✅ **2.2** Update User CRUD
- ✅ **2.3** Update Subscription CRUD
- ✅ **2.3a** Update Transaction CRUD
- ✅ **2.3b** Update Ticket CRUD
- ✅ **2.3c** Update PromoCode and PromoGroup CRUD
- ✅ **2.3d** Update Payment Model CRUDs
- ✅ **2.4** Feature Flag Service
- ✅ **2.4a** Payment Card Rotation Service
- ✅ **2.4b** Wallet Service
- ✅ **2.5** Multi-Bot Support

### Phase 3: Integration

- ✅ **3.1** Update Start Handler
- ✅ **3.2** Update Core Handlers
- ✅ **3.3** Update Payment Handlers - Card-to-Card
- ✅ **3.4** Update Payment Handlers - Zarinpal
- ✅ **3.5** Update Other Payment Handlers
- ✅ **3.6** Update Subscription Handlers
- ✅ **3.7** Update Admin Handlers
- ✅ **3.8** API Endpoints for Bot Management
- ✅ **3.9** API Endpoints for Feature Flags and Config

### Phase 4: Migration

- ✅ **4.1** Data Migration Script
- ✅ **4.2** Production Deployment

---

## 📖 نحوه استفاده از اسناد

### برای Incrementهای Phase 1-2

**استفاده از:** `10-implementation-guide-detailed.md`

این فایل شامل:
- ✅ دستورالعمل‌های step-by-step
- ✅ کدهای آماده (copy-paste)
- ✅ Acceptance criteria
- ✅ Test commands
- ✅ Troubleshooting

**مثال:**
```
1. Open: 10-implementation-guide-detailed.md
2. Find: "Increment 1.1"
3. Follow: All steps in order
4. Test: Acceptance criteria
5. Commit: "feat(multi-tenant): [1.1] Database Schema - New Tables"
```

### برای Payment Flows

**استفاده از:** `11-payment-flows-detailed.md`

این فایل شامل:
- ✅ Card-to-Card flow کامل
- ✅ Zarinpal flow کامل
- ✅ کدهای آماده
- ✅ Acceptance criteria

**مثال:**
```
1. Open: 11-payment-flows-detailed.md
2. Find: "Card-to-Card Payment Flow"
3. Follow: All steps
4. Test: Acceptance criteria
```

### برای Incrementهای Phase 3-4

**استفاده از:** `07-workflow-guide.md`

این فایل شامل:
- ✅ لیست کامل incrementها
- ✅ Tasks برای هر increment
- ✅ Acceptance criteria
- ✅ Dependencies

**مثال:**
```
1. Open: 07-workflow-guide.md
2. Find: "Increment 3.2"
3. Read: Tasks and Acceptance
4. Implement: Based on tasks
5. Test: Acceptance criteria
```

---

## ✅ Checklist برای هر Increment

قبل از شروع:
- [ ] Dependencies آماده است؟
- [ ] Documentation خوانده شده؟
- [ ] Test environment آماده است؟

در حین کار:
- [ ] دستورالعمل‌ها دنبال شده؟
- [ ] کدها تست شده؟
- [ ] Acceptance criteria بررسی شده؟

بعد از تکمیل:
- [ ] All tests pass
- [ ] Acceptance criteria met
- [ ] Code committed
- [ ] Documentation updated (if needed)

---

## 🐛 Troubleshooting

### مشکل: "Dependency not found"

**راه‌حل:**
1. بررسی کنید که increment قبلی کامل شده است
2. بررسی کنید که فایل‌های مورد نیاز ایجاد شده‌اند
3. بررسی کنید که imports درست هستند

### مشکل: "Test fails"

**راه‌حل:**
1. بررسی کنید که database migration اجرا شده است
2. بررسی کنید که test data درست است
3. بررسی کنید که acceptance criteria را درست فهمیده‌اید

### مشکل: "Import error"

**راه‌حل:**
1. بررسی کنید که فایل در مسیر درست است
2. بررسی کنید که `__init__.py` وجود دارد
3. بررسی کنید که imports درست هستند

---

## 📞 کمک

اگر stuck شدید:

1. **بررسی Documentation**
   - دوباره خواندن increment
   - بررسی troubleshooting section
   - بررسی acceptance criteria

2. **بررسی Code**
   - بررسی فایل‌های مشابه
   - بررسی existing patterns
   - بررسی test examples

3. **بررسی Tests**
   - Run existing tests
   - Write test to understand
   - Check test output

---

## 🎯 Success Criteria

### برای هر Increment

- ✅ All tests pass
- ✅ Acceptance criteria met
- ✅ No regressions
- ✅ Code reviewed (if team)
- ✅ Committed with clear message

### برای کل Migration

- ✅ All increments complete
- ✅ All tests pass
- ✅ No data loss
- ✅ Performance acceptable
- ✅ Production ready

---

## 📝 Commit Message Format

```
feat(multi-tenant): [Increment X.Y] - [Brief description]

- [What was done]
- [Key changes]
- [Tests added/updated]

Related: #issue (if applicable)
```

**مثال:**
```
feat(multi-tenant): [1.1] Database Schema - New Tables

- Created 7 new tables for multi-tenant
- Added all indexes and foreign keys
- Created migration script
- Tests: All tables created, indexes verified

Related: #123
```

---

## 🚀 Ready to Start?

1. ✅ [Overview](./00-overview.md) را خوانده‌ام
2. ✅ [Workflow Guide](./07-workflow-guide.md) را خوانده‌ام
3. ✅ [Implementation Guide](./10-implementation-guide-detailed.md) را خوانده‌ام
4. ✅ Environment آماده است
5. ✅ Backup گرفته شده

**حالا می‌توانید شروع کنید! 🚀**

---

**Next Step:** [Increment 1.1](./10-implementation-guide-detailed.md#increment-11-database-schema---new-tables)
