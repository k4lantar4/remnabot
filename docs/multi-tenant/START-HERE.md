# 🚀 شروع کار - Multi-Tenant Migration

**Version:** 1.0  
**Last Updated:** 2025-12-12

---

## 📋 چک‌لیست شروع

قبل از شروع، این موارد را بررسی کنید:

- [ ] همه مستندات را خوانده‌ام
- [ ] Environment آماده است
- [ ] Backup گرفته شده
- [ ] Team aware است
- [ ] Increment انتخاب شده

---

## 🎯 اولین قدم: Increment 1.1

**Increment 1.1: Database Schema - New Tables**

### چرا این increment؟

- ✅ پایه همه چیز است
- ✅ بدون dependencies
- ✅ قابل تست فوری
- ✅ ریسک کم
- ✅ زمان: 2 ساعت

### چه کاری انجام می‌دهیم؟

ایجاد 7 جدول جدید برای multi-tenant:
1. `bots` - Tenant bot instances
2. `bot_feature_flags` - Feature flags
3. `bot_configurations` - Configurations
4. `tenant_payment_cards` - Payment cards
5. `bot_plans` - Tenant plans
6. `card_to_card_payments` - Card payments
7. `zarinpal_payments` - Zarinpal payments

### مراحل

1. **Create Migration Script**
   ```bash
   # Create file
   touch migrations/001_create_multi_tenant_tables.sql
   ```

2. **Add SQL**
   - Copy SQL from [Database Schema](./01-database-schema.md)
   - All 7 CREATE TABLE statements
   - All CREATE INDEX statements

3. **Test Migration**
   ```bash
   # On test database
   psql remnawave_bot_test < migrations/001_create_multi_tenant_tables.sql
   ```

4. **Verify**
   ```sql
   -- Check tables exist
   SELECT table_name FROM information_schema.tables 
   WHERE table_schema = 'public' 
   AND table_name IN ('bots', 'bot_feature_flags', 'bot_configurations', 
                      'tenant_payment_cards', 'bot_plans', 
                      'card_to_card_payments', 'zarinpal_payments');
   -- Should return 7 rows
   ```

5. **Commit**
   ```bash
   git add migrations/001_create_multi_tenant_tables.sql
   git commit -m "feat: Add multi-tenant tables (Increment 1.1)"
   ```

### Acceptance Criteria

- ✅ All 7 tables created
- ✅ All indexes created
- ✅ Foreign keys working
- ✅ No errors
- ✅ Tests pass

---

## 📚 مستندات مورد نیاز

### برای این Increment

1. **[Database Schema](./01-database-schema.md)** - SQL definitions
2. **[Workflow Guide](./07-workflow-guide.md)** - Step-by-step guide
3. **[Increment Selection Guide](./08-increment-selection-guide.md)** - Dependencies

### برای مراحل بعد

- [Code Changes](./02-code-changes.md) - بعد از Increment 1.2
- [Feature Flags](./03-feature-flags.md) - بعد از Increment 1.4
- [Implementation Tasks](./04-implementation-tasks.md) - برای جزئیات

---

## 🗺️ نقشه راه

### Phase 1: Foundation (Week 1)
- [x] 1.1 Database Schema ← **شما اینجا هستید**
- [ ] 1.2 Database Models
- [ ] 1.3 Bot CRUD
- [ ] 1.4 Feature Flag CRUD
- [ ] 1.5 Bot Context Middleware

### Phase 2: Core Features (Week 2)
- [ ] 2.1 Add bot_id to Users
- [ ] 2.2 Update User CRUD
- [ ] 2.3 Update Subscription CRUD
- [ ] 2.4 Feature Flag Service
- [ ] 2.5 Multi-Bot Support

### Phase 3: Integration (Week 3)
- [ ] 3.1 Update Start Handler
- [ ] 3.2 Update Other Handlers
- [ ] 3.3 Update Payment Handlers

### Phase 4: Migration (Week 4)
- [ ] 4.1 Data Migration
- [ ] 4.2 Production Deployment

---

## ⚠️ نکات مهم

### قبل از شروع

1. **Backup بگیرید**
   ```bash
   pg_dump remnawave_bot > backup_$(date +%Y%m%d).sql
   ```

2. **Feature Branch بسازید**
   ```bash
   git checkout -b feature/multi-tenant-increment-1.1
   ```

3. **Test Environment آماده کنید**
   ```bash
   createdb remnawave_bot_test
   ```

### در حین کار

1. **تست کنید**
   - بعد از هر تغییر کوچک
   - قبل از commit

2. **Document کنید**
   - تغییرات را document کنید
   - Comments اضافه کنید

3. **Small Commits**
   - Commit های کوچک و مکرر
   - Messages واضح

### بعد از تکمیل

1. **Review کنید**
   - Code review
   - Test results
   - Documentation

2. **Mark Complete**
   - Increment را complete کنید
   - Progress tracker را update کنید

3. **Plan Next**
   - Increment بعدی را plan کنید
   - Dependencies را چک کنید

---

## 🆘 کمک

### اگر stuck شدید

1. **Documentation را review کنید**
   - [Workflow Guide](./07-workflow-guide.md)
   - [Common Pitfalls](./07-workflow-guide.md#common-pitfalls)

2. **Tests را چک کنید**
   - Test examples
   - Run existing tests

3. **از Team بپرسید**
   - Daily standup
   - Code review
   - Architecture discussion

---

## ✅ آماده شروع؟

1. ✅ [Overview](./00-overview.md) را خوانده‌ام
2. ✅ [Database Schema](./01-database-schema.md) را review کرده‌ام
3. ✅ [Workflow Guide](./07-workflow-guide.md) را خوانده‌ام
4. ✅ [Workflow & Assistant Guide](./09-workflow-and-assistant-guide.md) را خوانده‌ام
5. ✅ Environment آماده است
6. ✅ Backup گرفته شده

**حالا می‌توانید شروع کنید! 🚀**

---

## 🤖 شروع با AI Assistant

### اولین Prompt:

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

### بعد از AI Output:

1. Review کنید
2. Test کنید
3. Fix کنید (اگر لازم باشد)
4. Commit کنید

**برای جزئیات بیشتر:** [Workflow & Assistant Guide](./09-workflow-and-assistant-guide.md)

---

**Next:** بعد از تکمیل Increment 1.1، به [Increment 1.2](./08-increment-selection-guide.md#increment-12-database-models) بروید.
