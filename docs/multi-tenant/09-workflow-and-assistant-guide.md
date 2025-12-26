# Workflow & Assistant Guide - چگونه شروع کنیم؟

**Version:** 1.0  
**Last Updated:** 2025-12-12

---

## 🎯 هدف این راهنما

این راهنما به شما کمک می‌کند:
- انتخاب workflow مناسب
- استفاده بهینه از AI Assistant (Cursor/Claude)
- شروع سریع و موثر
- جلوگیری از اشتباهات

---

## 🤖 استفاده از AI Assistant

### چرا از Assistant استفاده کنیم؟

- ✅ Code generation سریع
- ✅ Error detection و fix
- ✅ Documentation review
- ✅ Best practices
- ✅ Code review

### چگونه از Assistant استفاده کنیم؟

#### 1. برای Code Generation

**Prompt Example:**
```
@docs/multi-tenant/01-database-schema.md
@docs/multi-tenant/02-code-changes.md

بر اساس این مستندات، migration script برای ایجاد 7 جدول جدید بنویس.
فایل: migrations/001_create_multi_tenant_tables.sql
```

**چرا این prompt خوب است:**
- ✅ Reference به مستندات
- ✅ Task واضح
- ✅ Output مشخص

#### 2. برای Code Review

**Prompt Example:**
```
این migration script را review کن و بگو:
1. آیا همه indexes درست هستند؟
2. آیا foreign keys درست تعریف شده‌اند؟
3. آیا مشکلی وجود دارد؟

@migrations/001_create_multi_tenant_tables.sql
```

#### 3. برای Error Fixing

**Prompt Example:**
```
این error را fix کن:
[Error message]

کد مربوطه:
@app/database/models.py
```

#### 4. برای Understanding

**Prompt Example:**
```
@docs/multi-tenant/01-database-schema.md

این schema را توضیح بده:
1. چرا این indexes نیاز هستند؟
2. چرا foreign keys اینطوری تعریف شده‌اند؟
3. آیا optimization لازم است؟
```

---

## 🔄 Workflow Recommendations

### Workflow 1: AI-Assisted Sequential (توصیه می‌شود)

**Best For:**
- تیم‌های کوچک (1-2 developer)
- اولین بار migration
- نیاز به یادگیری
- استفاده از AI assistant

**Process:**

```
1. Read Documentation
   ↓
2. Ask AI: "بر اساس مستندات، migration script بنویس"
   ↓
3. Review AI Output
   ↓
4. Test Migration
   ↓
5. Ask AI: "این migration را review کن"
   ↓
6. Fix Issues (با کمک AI)
   ↓
7. Commit
   ↓
8. Move to Next Increment
```

**Pros:**
- ✅ سریع (با AI)
- ✅ کم ریسک
- ✅ یادگیری بهتر
- ✅ کیفیت بالا

**Cons:**
- ⚠️ نیاز به review AI output

---

### Workflow 2: AI-Assisted Parallel

**Best For:**
- تیم‌های بزرگ (3+ developers)
- تجربه بالا
- نیاز به سرعت

**Process:**

```
Developer A: Increment 1.1 (Database Schema)
  ↓ Ask AI: "Migration script بنویس"
  ↓ Review & Test
  ↓ Commit

Developer B: Increment 1.2 (Models) - بعد از 1.1
  ↓ Ask AI: "Models را بر اساس schema بنویس"
  ↓ Review & Test
  ↓ Commit

Developer C: Increment 1.3 (CRUD) - بعد از 1.2
  ↓ Ask AI: "CRUD operations بنویس"
  ↓ Review & Test
  ↓ Commit
```

**Pros:**
- ✅ سریعتر
- ✅ استفاده بهتر از resources
- ✅ AI کمک می‌کند

**Cons:**
- ⚠️ نیاز به coordination
- ⚠️ نیاز به merge management

---

### Workflow 3: Hybrid AI-Assisted (بهترین تعادل)

**Best For:**
- بیشتر تیم‌ها
- تعادل بین سرعت و کیفیت

**Process:**

```
Phase 1: Foundation (Sequential with AI)
  - 1.1 Database Schema (AI: migration script)
  - 1.2 Models (AI: model code)
  - 1.3 CRUD (AI: CRUD functions)
  - 1.4 Feature Flags (AI: feature flag code)
  - 1.5 Middleware (AI: middleware code)

Phase 2: Core Features (Parallel with AI)
  - 2.1 Add bot_id (AI: migration script)
  - 2.2 Update User CRUD (AI: updated functions)
  - 2.3 Update Subscription CRUD (AI: updated functions)
  - 2.4 Feature Service (AI: service code)
  - 2.5 Multi-Bot (AI: multi-bot code)

Phase 3: Integration (Sequential with AI)
  - 3.1 Start Handler (AI: updated handler)
  - 3.2 Other Handlers (AI: batch update)
  - 3.3 Payment Handlers (AI: payment updates)

Phase 4: Migration (Careful with AI Review)
  - 4.1 Migration Script (AI: script + review)
  - 4.2 Production (Manual with AI support)
```

**Pros:**
- ✅ تعادل عالی
- ✅ کیفیت + سرعت
- ✅ AI کمک می‌کند

**Cons:**
- ⚠️ نیاز به planning

---

## 🚀 شروع با AI Assistant

### Step 1: Setup

```bash
# 1. Create feature branch
git checkout -b feature/multi-tenant-increment-1.1

# 2. Open Cursor/IDE
# 3. Open relevant files
```

### Step 2: First AI Prompt

**Prompt:**
```
@docs/multi-tenant/START-HERE.md
@docs/multi-tenant/01-database-schema.md

بر اساس این مستندات، migration script برای Increment 1.1 بنویس.

Requirements:
1. ایجاد 7 جدول جدید (bots, bot_feature_flags, bot_configurations, tenant_payment_cards, bot_plans, card_to_card_payments, zarinpal_payments)
2. همه indexes
3. همه foreign keys
4. Comments برای هر table

Output: migrations/001_create_multi_tenant_tables.sql
```

### Step 3: Review AI Output

**Prompt:**
```
این migration script را review کن:

1. آیا همه tables درست هستند؟
2. آیا indexes بهینه هستند؟
3. آیا foreign keys درست هستند؟
4. آیا مشکلی وجود دارد؟
5. آیا performance issue وجود دارد؟

@migrations/001_create_multi_tenant_tables.sql
```

### Step 4: Test

```bash
# Test on dev database
psql remnawave_bot_test < migrations/001_create_multi_tenant_tables.sql
```

### Step 5: Verify with AI

**Prompt:**
```
این SQL queries را برای verify migration بنویس:

1. Check all tables exist
2. Check all indexes exist
3. Check foreign keys work
4. Check data types

Output: SQL queries
```

### Step 6: Fix Issues (if any)

**Prompt:**
```
این error را fix کن:
[Error message]

Migration script:
@migrations/001_create_multi_tenant_tables.sql
```

### Step 7: Commit

```bash
git add migrations/001_create_multi_tenant_tables.sql
git commit -m "feat: Add multi-tenant tables (Increment 1.1)"
```

---

## 📋 AI Prompt Templates

### Template 1: Code Generation

```
@docs/multi-tenant/[relevant-doc].md

بر اساس این مستندات، [task description] بنویس.

Requirements:
1. [requirement 1]
2. [requirement 2]
3. [requirement 3]

Output: [file path]
```

### Template 2: Code Review

```
این [code type] را review کن:

1. آیا [check 1]؟
2. آیا [check 2]؟
3. آیا [check 3]؟
4. آیا مشکلی وجود دارد؟

@[file path]
```

### Template 3: Error Fixing

```
این error را fix کن:
[Error message]

کد مربوطه:
@[file path]

مستندات:
@docs/multi-tenant/[relevant-doc].md
```

### Template 4: Understanding

```
@docs/multi-tenant/[doc].md

این [concept] را توضیح بده:
1. [question 1]
2. [question 2]
3. [question 3]
```

### Template 5: Testing

```
برای این [code] test cases بنویس:

1. [test case 1]
2. [test case 2]
3. [test case 3]

کد:
@[file path]
```

---

## 🎯 Recommended Workflow برای شما

### پیشنهاد: AI-Assisted Sequential

**چرا:**
- ✅ بهترین برای شروع
- ✅ یادگیری بهتر
- ✅ کیفیت بالا
- ✅ AI کمک می‌کند

**مراحل:**

1. **Read Documentation**
   - [START-HERE.md](./START-HERE.md)
   - [Database Schema](./01-database-schema.md)

2. **Ask AI: Migration Script**
   ```
   @docs/multi-tenant/START-HERE.md
   @docs/multi-tenant/01-database-schema.md
   
   بر اساس این مستندات، migration script برای Increment 1.1 بنویس.
   همه 7 جدول جدید با indexes و foreign keys.
   ```

3. **Review AI Output**
   ```
   این migration script را review کن و بگو آیا مشکلی دارد.
   @migrations/001_create_multi_tenant_tables.sql
   ```

4. **Test**
   ```bash
   psql remnawave_bot_test < migrations/001_create_multi_tenant_tables.sql
   ```

5. **Verify with AI**
   ```
   SQL queries برای verify این migration بنویس.
   @migrations/001_create_multi_tenant_tables.sql
   ```

6. **Fix Issues (if any)**
   ```
   این error را fix کن: [error]
   @migrations/001_create_multi_tenant_tables.sql
   ```

7. **Commit & Move Next**
   ```bash
   git commit -m "feat: Add multi-tenant tables (Increment 1.1)"
   ```

---

## ⚠️ نکات مهم

### Do's ✅

1. **همیشه مستندات را reference کنید**
   ```
   @docs/multi-tenant/01-database-schema.md
   ```

2. **Review AI output**
   - همیشه output را review کنید
   - تست کنید
   - Fix کنید

3. **Small, focused prompts**
   - یک task در هر prompt
   - واضح و مشخص

4. **Test everything**
   - بعد از هر AI output
   - قبل از commit

### Don'ts ❌

1. **Blind trust**
   - AI output را بدون review استفاده نکنید
   - همیشه تست کنید

2. **Big prompts**
   - همه چیز را یکجا نپرسید
   - Incremental approach

3. **Skip tests**
   - حتی برای کوچک‌ترین تغییرات
   - Test-driven approach

---

## 📊 Progress Tracking

### با AI Assistant

**Prompt:**
```
بر اساس این checklist، progress را track کن:

Completed:
- [x] Increment 1.1
- [ ] Increment 1.2
- [ ] Increment 1.3

Next: Increment 1.2

@docs/multi-tenant/07-workflow-guide.md
```

---

## 🆘 Help با AI

### اگر stuck شدید

**Prompt:**
```
من در Increment 1.1 stuck شده‌ام.

مشکل: [describe problem]

کد:
@[relevant files]

مستندات:
@docs/multi-tenant/[relevant docs]

راه حل پیشنهاد بده.
```

---

## 🚀 Ready to Start?

### Quick Start با AI

1. **Open Cursor/IDE**

2. **First Prompt:**
   ```
   @docs/multi-tenant/START-HERE.md
   @docs/multi-tenant/01-database-schema.md
   
   بر اساس این مستندات، migration script برای Increment 1.1 بنویس.
   همه 7 جدول جدید با indexes و foreign keys.
   Output: migrations/001_create_multi_tenant_tables.sql
   ```

3. **Review & Test**

4. **Continue with next increment**

---

## 📚 Related Documents

- [START-HERE.md](./START-HERE.md) - شروع کار
- [Workflow Guide](./07-workflow-guide.md) - راهنمای workflow
- [Increment Selection](./08-increment-selection-guide.md) - انتخاب increment

---

**Remember:**
- ✅ از AI استفاده کنید
- ✅ همیشه review کنید
- ✅ تست کنید
- ✅ Incremental approach

**Good Luck! 🚀**
