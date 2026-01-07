# Migration Cleanup Summary

**Date:** 2026-01-07  
**Environment:** dev/staging (no existing database)  
**Action:** حذف migration‌های غیرضروری و ایجاد یک migration اولیه واحد

---

## خلاصه تغییرات

### Migration‌های حذف شده (17 فایل)

1. **Migration‌های مربوط به جداول که در models.py تعریف شده‌اند:**
   - `1f5f3a3f5a4d_add_promo_groups_and_user_fk.py` - PromoGroup در models.py
   - `4b6b0f58c8f9_add_period_discounts_to_promo_groups.py` - در models.py
   - `5d1f1f8b2e9a_add_advertising_campaigns.py` - AdvertisingCampaign در models.py
   - `9f0f2d5a1c7b_add_polls_tables.py` - Poll در models.py
   - `c2f9c3b5f5c4_add_subscription_events_table.py` - SubscriptionEvent در models.py
   - `8fd1e338eb45_add_sent_notifications_table.py` - SentNotification در models.py
   - `c9c71d04f0a1_add_pinned_messages_table.py` - PinnedMessage در models.py
   - `5f2a3e099427_add_media_fields_to_pinned_messages.py` - PinnedMessage در models.py
   - `7a3c0b8f5b84_add_send_before_menu_to_pinned_messages.py` - PinnedMessage در models.py
   - `1b2e3d4f5a6b_add_pinned_start_mode_and_user_last_pin.py` - PinnedMessage در models.py
   - `e3c1e0b5b4a7_add_referral_commission_percent_to_users.py` - User در models.py
   - `dde359954cb4_add_bot_prd_fields.py` - Bot در models.py
   - `d7f6e838328b_add_cabinet_columns_to_users.py` - User در models.py
   - `c3d640fce6e9_add_promocode_first_purchase_only.py` - PromoCode در models.py

2. **Migration‌های مربوط به درگاه‌های روسی:**
   - `2b3c1d4e5f6a_add_platega_payments.py` - درگاه روسی (حذف شد)
   - `b4dfcd24d5dd_drop_russian_gateway_tables.py` - حذف جداول روسی (غیرضروری)
   - `f8a9b2c3d4e5_drop_russian_gateway_tables.py` - duplicate (حذف شد)

3. **Migration کپک به تومان:**
   - `445627bc515d_rename_kopeks_to_toman.py` - غیرضروری (models.py از ابتدا تومان استفاده می‌کند)

4. **Migration RLS قدیمی:**
   - `d6abce072ea5_setup_rls_policies.py` - جایگزین شد با migration اولیه

### Migration جدید

**`3ccbf75aa775_initial_schema_with_rls.py`** (222 خط)
- ایجاد همه جداول از models.py (via Alembic autogenerate)
- تنظیم RLS policies برای tenant isolation
- ایجاد indexes ضروری

---

## آمار کاهش

| قبل | بعد | کاهش |
|-----|-----|------|
| **19 migration** | **1 migration** | **18 migration (95%)** |
| **~1593 خط** | **222 خط** | **~1371 خط (86%)** |

---

## نحوه استفاده

### برای نصب جدید (dev/staging)

```bash
# 1. ایجاد دیتابیس
docker compose up -d postgres

# 2. اجرای migration
docker compose exec bot alembic -c migrations/alembic/alembic.ini upgrade head

# یا اگر می‌خواهید از autogenerate استفاده کنید:
docker compose exec bot alembic -c migrations/alembic/alembic.ini revision --autogenerate -m "Initial schema"
docker compose exec bot alembic -c migrations/alembic/alembic.ini upgrade head
```

### برای production

⚠️ **هشدار:** این تغییرات فقط برای محیط‌های dev/staging بدون دیتابیس است.

برای production:
1. از migration‌های قدیمی استفاده کنید
2. یا migration‌های قدیمی را به migration جدید تبدیل کنید

---

## نکات مهم

1. ✅ **Migration اولیه** - همه جداول از models.py ساخته می‌شوند
2. ✅ **RLS policies** - به صورت خودکار تنظیم می‌شوند
3. ✅ **سبک و سریع** - فقط 1 migration به جای 19 migration
4. ⚠️ **فقط برای dev/staging** - برای production نیاز به migration path دارید

---

## مراحل بعدی

برای production، باید:
1. Migration path از migration‌های قدیمی به جدید ایجاد کنید
2. یا migration‌های قدیمی را نگه دارید و فقط migration‌های غیرضروری را حذف کنید

---

**تاریخ:** 2026-01-07  
**وضعیت:** ✅ تکمیل شده برای dev/staging
