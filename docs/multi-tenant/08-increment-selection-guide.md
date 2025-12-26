# Increment Selection Guide

**Version:** 1.0  
**Last Updated:** 2025-12-12

---

## 🎯 هدف

این راهنما به شما کمک می‌کند:
- انتخاب increment مناسب برای شروع
- درک dependencies
- تصمیم‌گیری درباره workflow
- جلوگیری از اشتباهات

---

## 📊 Increment چیست؟

Increment یک واحد کاری کوچک و قابل تست است که:
- ✅ مستقل قابل انجام است
- ✅ قابل تست فوری است
- ✅ ارزش فوری دارد
- ✅ ریسک کم دارد

---

## 🗺️ Increment Map

### Phase 1: Foundation (Week 1)

```
1.1 Database Schema (New Tables)
    ↓
1.2 Database Models (New Models)
    ↓
1.3 Bot CRUD Operations
    ↓
1.4 Feature Flag CRUD
    ↓
1.5 Bot Context Middleware
```

### Phase 2: Core Features (Week 2)

```
2.1 Add bot_id to Users Table
    ↓
2.2 Update User CRUD
    ↓
2.3 Update Subscription CRUD
    ↓
2.4 Feature Flag Service
    ↓
2.5 Multi-Bot Support
```

### Phase 3: Integration (Week 3)

```
3.1 Update Start Handler
    ↓
3.2 Update Other Handlers
    ↓
3.3 Update Payment Handlers
```

### Phase 4: Migration (Week 4)

```
4.1 Data Migration Script
    ↓
4.2 Production Deployment
```

---

## 🚀 Recommended Starting Point

### برای تیم‌های جدید: Increment 1.1

**چرا:**
- ✅ بدون dependencies
- ✅ پایه همه چیز
- ✅ قابل تست فوری
- ✅ ریسک کم

**چیست:**
- ایجاد 7 جدول جدید
- ایجاد indexes
- تست foreign keys

**زمان:** 2 ساعت

---

### برای تیم‌های با تجربه: Parallel Work

**چرا:**
- می‌توانید چند increment را همزمان انجام دهید
- سرعت بیشتر

**چگونه:**
1. Developer A: Increment 1.1 (Database Schema)
2. Developer B: Increment 1.2 (Models) - بعد از 1.1
3. Developer C: Increment 1.3 (CRUD) - بعد از 1.2

---

## 📋 Increment Checklist

قبل از شروع هر increment:

- [ ] Dependencies آماده است؟
- [ ] Documentation خوانده شده؟
- [ ] Test environment آماده است؟
- [ ] Backup گرفته شده؟
- [ ] Team aware است؟

---

## ⚠️ Common Mistakes

### Mistake 1: Skipping Dependencies

**Problem:** شروع increment بدون prerequisites

**Solution:** همیشه dependency graph را چک کنید

### Mistake 2: Big Bang

**Problem:** انجام همه چیز یکجا

**Solution:** Incremental approach

### Mistake 3: No Tests

**Problem:** "این کوچک است، تست نمی‌کنم"

**Solution:** همیشه تست کنید

---

## 🎯 Success Criteria

برای هر increment:

- ✅ All tests pass
- ✅ No regressions
- ✅ Code reviewed
- ✅ Documented
- ✅ Ready for next

---

## 📞 Help

اگر stuck شدید:

1. Review documentation
2. Check tests
3. Ask team
4. Review similar code

---

**Next:** [Workflow Guide](./07-workflow-guide.md)

