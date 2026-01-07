# Migration Cleanup Guide

**Date:** 2026-01-07  
**Purpose:** سبک‌سازی و بهینه‌سازی migration‌های Alembic

---

## خلاصه تغییرات

### Migration‌های ایجاد شده

1. **`b4dfcd24d5dd_drop_russian_gateway_tables.py`** (NEW)
   - حذف تمام جداول درگاه‌های پرداخت روسی
   - جداول حذف شده: `yookassa_payments`, `heleket_payments`, `mulenpay_payments`, `pal24_payments`, `wata_payments`, `platega_payments`, `tribute_payments`

### Migration‌های بهینه شده

2. **`445627bc515d_rename_kopeks_to_toman.py`** (MODIFIED)
   - حذف بخش‌های مربوط به درگاه‌های روسی (6 جدول)
   - کاهش از 253 خط به ~200 خط
   - فقط جداول ایرانی و اصلی را تبدیل می‌کند

3. **`2b3c1d4e5f6a_add_platega_payments.py`** (MODIFIED)
   - تبدیل به no-op migration (برای حفظ chain)
   - فقط اگر جدول وجود نداشته باشد، آن را می‌سازد
   - جدول در migration بعدی حذف می‌شود

---

## آمار کاهش حجم

| Migration | قبل | بعد | کاهش |
|-----------|-----|-----|------|
| `445627bc515d` | 253 خط | ~200 خط | ~53 خط (21%) |
| `2b3c1d4e5f6a` | 95 خط | ~100 خط | +5 خط (no-op) |
| **کل** | **348 خط** | **~300 خط** | **~48 خط (14%)** |

---

## اجرای Migration‌ها

### برای دیتابیس موجود

```bash
# 1. Backup (CRITICAL!)
docker compose exec postgres pg_dump -U remnawave_user remnawave_bot > backup_$(date +%Y%m%d).sql

# 2. Run migrations
docker compose exec bot alembic -c migrations/alembic/alembic.ini upgrade head

# 3. Verify tables dropped
docker compose exec postgres psql -U remnawave_user -d remnawave_bot -c "\dt" | grep -E "yookassa|platega|mulenpay|pal24|wata|heleket"
# Should return: No matches (tables dropped)
```

### برای نصب جدید

Migration‌ها به صورت خودکار اجرا می‌شوند. جداول درگاه‌های روسی هرگز ساخته نمی‌شوند.

---

## Migration Chain

```
... → 9f0f2d5a1c7b (polls)
  → 2b3c1d4e5f6a (platega - no-op now)
  → ... → e3c1e0b5b4a7
  → 445627bc515d (kopeks-to-toman - simplified)
  → c3d640fce6e9 (promocode first_purchase_only)
  → b4dfcd24d5dd (drop russian gateways) ← NEW
```

---

## جداول حذف شده

| جدول | تعداد ردیف (قبل از حذف) | وضعیت |
|------|------------------------|-------|
| `yookassa_payments` | ? | ✅ حذف شد |
| `heleket_payments` | ? | ✅ حذف شد |
| `mulenpay_payments` | ? | ✅ حذف شد |
| `pal24_payments` | ? | ✅ حذف شد |
| `wata_payments` | ? | ✅ حذف شد |
| `platega_payments` | ? | ✅ حذف شد |
| `tribute_payments` | ? | ⚠️ ممکن است وجود نداشته باشد |

---

## Rollback

⚠️ **هشدار:** Migration حذف جداول قابل rollback نیست.

اگر نیاز به rollback دارید:
1. از backup دیتابیس restore کنید
2. یا migration را به صورت دستی revert کنید

```bash
# Restore from backup
docker compose exec -T postgres psql -U remnawave_user -d remnawave_bot < backup_YYYYMMDD.sql
```

---

## بررسی و تست

### قبل از اجرا

```bash
# 1. بررسی وجود جداول
docker compose exec postgres psql -U remnawave_user -d remnawave_bot -c "
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
  'yookassa_payments', 'heleket_payments', 'mulenpay_payments',
  'pal24_payments', 'wata_payments', 'platega_payments', 'tribute_payments'
);"

# 2. بررسی تعداد ردیف‌ها (برای backup)
docker compose exec postgres psql -U remnawave_user -d remnawave_bot -c "
SELECT 
  'yookassa_payments' as table_name, COUNT(*) as row_count FROM yookassa_payments
UNION ALL
SELECT 'heleket_payments', COUNT(*) FROM heleket_payments
UNION ALL
SELECT 'mulenpay_payments', COUNT(*) FROM mulenpay_payments
UNION ALL
SELECT 'pal24_payments', COUNT(*) FROM pal24_payments
UNION ALL
SELECT 'wata_payments', COUNT(*) FROM wata_payments
UNION ALL
SELECT 'platega_payments', COUNT(*) FROM platega_payments;"
```

### بعد از اجرا

```bash
# بررسی حذف شدن جداول
docker compose exec postgres psql -U remnawave_user -d remnawave_bot -c "
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name LIKE '%payment%'
ORDER BY table_name;"

# باید فقط این جداول باقی بمانند:
# - card_to_card_payments
# - cloudpayments_payments
# - cryptobot_payments
# - tenant_payment_cards
# - zarinpal_payments
```

---

## نکات مهم

1. ✅ **Backup ضروری است** - قبل از اجرای migration حتماً backup بگیرید
2. ✅ **Migration chain حفظ شده** - migration Platega به no-op تبدیل شد تا chain نشکند
3. ✅ **Backward compatible** - migration‌ها برای دیتابیس‌های موجود و جدید کار می‌کنند
4. ⚠️ **Rollback محدود** - حذف جداول قابل rollback نیست (نیاز به backup)

---

## مراحل بعدی

- [ ] حذف مدل‌های درگاه‌های روسی از `app/database/models.py`
- [ ] حذف سرویس‌های درگاه‌های روسی از `app/external/`
- [ ] حذف handler‌های درگاه‌های روسی
- [ ] به‌روزرسانی `PaymentMethod` enum

---

**تاریخ ایجاد:** 2026-01-07  
**آخرین به‌روزرسانی:** 2026-01-07
