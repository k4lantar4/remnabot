# Tenant Bots Admin UX - Visual Diagram & Complete Mapping

**Version:** 1.0  
**Date:** 2025-12-14  
**Status:** Design Complete

---

## 🎨 Visual Menu Structure Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    ADMIN PANEL (Main)                        │
│  [🤖 Tenant Bots] ← Click here                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              🤖 TENANT BOTS MANAGEMENT                        │
│                                                              │
│  📊 Statistics:                                              │
│  • Total bots: 5                                            │
│  • Active: 4                                                 │
│  • Inactive: 1                                              │
│                                                              │
│  [📋 List Bots]  [➕ Create Bot]                            │
│  [📊 Statistics] [⚙️ Settings]                              │
│  [🔙 Back]                                                   │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         │                    │                    │
         ▼                    ▼                    ▼
    ┌─────────┐         ┌─────────┐         ┌─────────┐
    │ List    │         │ Create  │         │ Stats   │
    │ Bots    │         │ Bot     │         │ Overview│
    └─────────┘         └─────────┘         └─────────┘
         │
         ▼ (Click on Bot)
┌─────────────────────────────────────────────────────────────┐
│         🤖 BOT DETAIL: My VPN Bot (ID: 2)                    │
│                                                              │
│  📊 Quick Stats:                                             │
│  • Status: ✅ Active                                         │
│  • Users: 234                                                │
│  • Revenue: 25,000 Toman                                     │
│                                                              │
│  [📊 Statistics] [⚙️ General Settings]                      │
│  [🎛️ Feature Flags] [💳 Payment Methods]                   │
│  [📦 Plans] [🔧 Configuration] [📈 Analytics]                │
│  [🧪 Test] [🗑️ Delete] [🔙 Back]                             │
└─────────────────────────────────────────────────────────────┘
    │         │         │         │         │         │
    │         │         │         │         │         │
    ▼         ▼         ▼         ▼         ▼         ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│Stats │ │Gen   │ │Feat  │ │Pay   │ │Plans │ │Config│
│      │ │Set   │ │Flags │ │Meth  │ │      │ │      │
└──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘
```

---

## 🔄 Complete Navigation Flow

### Flow 1: List & Select Bot

```
Admin Panel
    │
    ├─→ 🤖 Tenant Bots Menu
    │       │
    │       ├─→ 📋 List Bots
    │       │       │
    │       │       ├─→ Page 1: [Bot 1] [Bot 2] [Bot 3]
    │       │       │       │
    │       │       │       └─→ Click Bot 1
    │       │       │               │
    │       │       │               ▼
    │       │       │           Bot Detail Menu
    │       │       │
    │       │       └─→ [Next ➡️] → Page 2
    │       │
    │       └─→ 🔙 Back → Admin Panel
```

### Flow 2: Bot Detail Navigation

```
Bot Detail Menu
    │
    ├─→ 📊 Statistics
    │       ├─→ Overview
    │       ├─→ Detailed Stats
    │       ├─→ Revenue Chart
    │       └─→ 🔙 Back → Bot Detail
    │
    ├─→ ⚙️ General Settings
    │       ├─→ Edit Name (FSM)
    │       ├─→ Edit Language (FSM)
    │       ├─→ Edit Support (FSM)
    │       └─→ 🔙 Back → Bot Detail
    │
    ├─→ 🎛️ Feature Flags
    │       ├─→ Toggle Feature (Instant)
    │       ├─→ View Plan Limits
    │       └─→ 🔙 Back → Bot Detail
    │
    ├─→ 💳 Payment Methods
    │       ├─→ Card-to-Card
    │       │       ├─→ Configure Cards
    │       │       └─→ Toggle
    │       ├─→ Zarinpal
    │       │       ├─→ Configure (FSM)
    │       │       └─→ Toggle
    │       └─→ 🔙 Back → Bot Detail
    │
    ├─→ 📦 Subscription Plans
    │       ├─→ List Plans
    │       ├─→ Create Plan (FSM)
    │       ├─→ Edit Plan (FSM)
    │       └─→ 🔙 Back → Bot Detail
    │
    ├─→ 🔧 Configuration
    │       ├─→ 📝 Basic Settings
    │       │       └─→ Edit Fields (FSM)
    │       ├─→ 💬 Support Settings
    │       ├─→ 🔔 Notifications
    │       ├─→ 📦 Subscription Settings
    │       ├─→ 💰 Pricing Settings
    │       ├─→ 🎨 UI/UX Settings
    │       ├─→ 🔗 Integrations
    │       └─→ ⚙️ Advanced Settings
    │
    └─→ 🔙 Back → List Bots
```

---

## 📋 Complete Callback → Handler → Database Mapping

### Main Menu Level

| Callback | Handler Function | Database Query | Description |
|----------|-----------------|----------------|-------------|
| `admin_tenant_bots_menu` | `show_tenant_bots_menu()` | `SELECT COUNT(*) FROM bots WHERE is_master = FALSE`<br>`SELECT COUNT(*) FROM bots WHERE is_master = FALSE AND is_active = TRUE` | نمایش منوی اصلی با آمار |
| `admin_tenant_bots_list` | `list_tenant_bots(page=0)` | `SELECT b.*, COUNT(DISTINCT u.id) as user_count, COALESCE(SUM(t.amount_kopeks), 0) as revenue FROM bots b LEFT JOIN users u ON u.bot_id = b.id LEFT JOIN transactions t ON t.bot_id = b.id AND t.type = 'deposit' WHERE b.is_master = FALSE GROUP BY b.id ORDER BY b.created_at DESC LIMIT 5 OFFSET {page*5}` | لیست ربات‌ها با pagination |
| `admin_tenant_bots_list:{page}` | `list_tenant_bots(page={page})` | Same as above with different offset | Pagination |
| `admin_tenant_bots_create` | `start_create_bot()` | None (FSM start) | شروع فرآیند ایجاد ربات |
| `admin_tenant_bots_stats` | `show_tenant_bots_statistics()` | Multiple aggregation queries | آمار کلی تمام tenants |

### Bot Detail Level

| Callback | Handler Function | Database Query | Description |
|----------|-----------------|----------------|-------------|
| `admin_tenant_bot_detail:{bot_id}` | `show_bot_detail(bot_id)` | `SELECT * FROM bots WHERE id = {bot_id}`<br>`SELECT COUNT(*) FROM users WHERE bot_id = {bot_id}`<br>`SELECT COUNT(*) FROM subscriptions WHERE bot_id = {bot_id} AND status = 'active'`<br>`SELECT COALESCE(SUM(amount_kopeks), 0) FROM transactions WHERE bot_id = {bot_id} AND type = 'deposit' AND created_at >= date_trunc('month', CURRENT_DATE)` | نمایش جزئیات ربات |
| `admin_tenant_bot_activate:{bot_id}` | `activate_tenant_bot(bot_id)` | `UPDATE bots SET is_active = TRUE WHERE id = {bot_id}` | فعال‌سازی ربات |
| `admin_tenant_bot_deactivate:{bot_id}` | `deactivate_tenant_bot(bot_id)` | `UPDATE bots SET is_active = FALSE WHERE id = {bot_id}` | غیرفعال‌سازی ربات |

### Statistics Level

| Callback | Handler Function | Database Query | Description |
|----------|-----------------|----------------|-------------|
| `admin_tenant_bot_stats:{bot_id}` | `show_bot_statistics(bot_id)` | `SELECT COUNT(*) FROM users WHERE bot_id = {bot_id} AND created_at >= CURRENT_DATE - INTERVAL '30 days'`<br>`SELECT COUNT(DISTINCT user_id) FROM subscriptions WHERE bot_id = {bot_id} AND status = 'active'`<br>`SELECT payment_method, SUM(amount_kopeks) FROM transactions WHERE bot_id = {bot_id} AND type = 'deposit' AND created_at >= CURRENT_DATE - INTERVAL '30 days' GROUP BY payment_method` | آمار ربات |
| `admin_tenant_bot_stats_detailed:{bot_id}` | `show_detailed_statistics(bot_id)` | Complex analytics queries | آمار تفصیلی |
| `admin_tenant_bot_stats_revenue:{bot_id}` | `show_revenue_statistics(bot_id)` | `SELECT DATE(created_at) as date, SUM(amount_kopeks) as revenue FROM transactions WHERE bot_id = {bot_id} AND type = 'deposit' AND created_at >= CURRENT_DATE - INTERVAL '30 days' GROUP BY DATE(created_at) ORDER BY date` | نمودار درآمد |

### General Settings Level

| Callback | Handler Function | Database Query | Description |
|----------|-----------------|----------------|-------------|
| `admin_tenant_bot_settings:{bot_id}` | `show_bot_settings(bot_id)` | `SELECT * FROM bots WHERE id = {bot_id}` | نمایش تنظیمات عمومی |
| `admin_tenant_bot_edit_name:{bot_id}` | `start_edit_name(bot_id)` | FSM: `AdminStates.editing_tenant_bot_name` | شروع ویرایش نام |
| `admin_tenant_bot_edit_language:{bot_id}` | `start_edit_language(bot_id)` | FSM: `AdminStates.editing_tenant_bot_language` | شروع ویرایش زبان |
| `admin_tenant_bot_edit_support:{bot_id}` | `start_edit_support(bot_id)` | FSM: `AdminStates.editing_tenant_bot_support` | شروع ویرایش پشتیبانی |
| `admin_tenant_bot_toggle_card:{bot_id}` | `toggle_card_to_card(bot_id)` | `UPDATE bots SET card_to_card_enabled = NOT card_to_card_enabled WHERE id = {bot_id}` | تغییر وضعیت کارت به کارت |
| `admin_tenant_bot_toggle_zarinpal:{bot_id}` | `toggle_zarinpal(bot_id)` | `UPDATE bots SET zarinpal_enabled = NOT zarinpal_enabled WHERE id = {bot_id}` | تغییر وضعیت زرین‌پال |

### Feature Flags Level

| Callback | Handler Function | Database Query | Description |
|----------|-----------------|----------------|-------------|
| `admin_tenant_bot_features:{bot_id}` | `show_bot_feature_flags(bot_id)` | `SELECT * FROM bot_feature_flags WHERE bot_id = {bot_id}`<br>`SELECT pf.* FROM plan_feature_grants pf JOIN tenant_subscriptions ts ON ts.plan_tier_id = pf.plan_tier_id WHERE ts.bot_id = {bot_id} AND ts.status = 'active'` | نمایش feature flags |
| `admin_tenant_bot_toggle_feature:{bot_id}:{feature_key}` | `toggle_feature_flag(bot_id, feature_key)` | `INSERT INTO bot_feature_flags (bot_id, feature_key, enabled) VALUES ({bot_id}, '{feature_key}', {new_value}) ON CONFLICT (bot_id, feature_key) DO UPDATE SET enabled = {new_value}, updated_at = NOW()` | تغییر وضعیت feature |
| `admin_tenant_bot_features_plan:{bot_id}` | `show_plan_features(bot_id)` | `SELECT tsp.*, pf.* FROM tenant_subscriptions ts JOIN tenant_subscription_plans tsp ON ts.plan_tier_id = tsp.id JOIN plan_feature_grants pf ON pf.plan_tier_id = tsp.id WHERE ts.bot_id = {bot_id} AND ts.status = 'active'` | نمایش features پلن |

### Payment Methods Level

| Callback | Handler Function | Database Query | Description |
|----------|-----------------|----------------|-------------|
| `admin_tenant_bot_payments:{bot_id}` | `show_bot_payment_methods(bot_id)` | `SELECT card_to_card_enabled, card_receipt_topic_id, zarinpal_enabled, zarinpal_merchant_id, zarinpal_sandbox FROM bots WHERE id = {bot_id}`<br>`SELECT COUNT(*) FROM tenant_payment_cards WHERE bot_id = {bot_id} AND is_active = TRUE`<br>`SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key LIKE '%_ENABLED'` | نمایش روش‌های پرداخت |
| `admin_tenant_bot_cards:{bot_id}` | `show_bot_payment_cards(bot_id)` | `SELECT * FROM tenant_payment_cards WHERE bot_id = {bot_id} ORDER BY created_at DESC` | مدیریت کارت‌ها |
| `admin_tenant_bot_card_add:{bot_id}` | `start_add_card(bot_id)` | FSM: `AdminStates.adding_tenant_payment_card` | افزودن کارت جدید |
| `admin_tenant_bot_card_edit:{card_id}` | `start_edit_card(card_id)` | FSM: `AdminStates.editing_tenant_payment_card` | ویرایش کارت |
| `admin_tenant_bot_zarinpal:{bot_id}` | `show_zarinpal_config(bot_id)` | `SELECT zarinpal_enabled, zarinpal_merchant_id, zarinpal_sandbox FROM bots WHERE id = {bot_id}` | تنظیمات زرین‌پال |
| `admin_tenant_bot_zarinpal_edit:{bot_id}` | `start_edit_zarinpal(bot_id)` | FSM: `AdminStates.editing_tenant_zarinpal` | ویرایش زرین‌پال |
| `admin_tenant_bot_yookassa:{bot_id}` | `show_yookassa_config(bot_id)` | `SELECT config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key = 'YOOKASSA_ENABLED'`<br>`SELECT config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key = 'YOOKASSA_SHOP_ID'`<br>... (all YOOKASSA_* configs) | تنظیمات YooKassa |
| `admin_tenant_bot_yookassa_edit:{bot_id}` | `start_edit_yookassa(bot_id)` | FSM: `AdminStates.editing_tenant_yookassa` | ویرایش YooKassa |

### Subscription Plans Level

| Callback | Handler Function | Database Query | Description |
|----------|-----------------|----------------|-------------|
| `admin_tenant_bot_plans:{bot_id}` | `show_bot_plans(bot_id)` | `SELECT * FROM bot_plans WHERE bot_id = {bot_id} ORDER BY sort_order, price_kopeks` | لیست پلن‌ها |
| `admin_tenant_bot_plan_create:{bot_id}` | `start_create_plan(bot_id)` | FSM: `AdminStates.creating_tenant_plan` | ایجاد پلن جدید |
| `admin_tenant_bot_plan_edit:{plan_id}` | `start_edit_plan(plan_id)` | `SELECT * FROM bot_plans WHERE id = {plan_id}`<br>FSM: `AdminStates.editing_tenant_plan` | ویرایش پلن |
| `admin_tenant_bot_plan_delete:{plan_id}` | `delete_plan(plan_id)` | `DELETE FROM bot_plans WHERE id = {plan_id}` | حذف پلن |
| `admin_tenant_bot_plan_toggle:{plan_id}` | `toggle_plan_status(plan_id)` | `UPDATE bot_plans SET is_active = NOT is_active WHERE id = {plan_id}` | فعال/غیرفعال کردن پلن |

### Configuration Level

| Callback | Handler Function | Database Query | Description |
|----------|-----------------|----------------|-------------|
| `admin_tenant_bot_config:{bot_id}` | `show_bot_configuration_menu(bot_id)` | None (menu only) | منوی دسته‌بندی configs |
| `admin_tenant_bot_config_basic:{bot_id}` | `show_basic_settings(bot_id)` | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key IN ('DEFAULT_LANGUAGE', 'AVAILABLE_LANGUAGES', 'LANGUAGE_SELECTION_ENABLED', 'TZ', 'SKIP_RULES_ACCEPT', 'SKIP_REFERRAL_CODE')` | تنظیمات پایه |
| `admin_tenant_bot_config_support:{bot_id}` | `show_support_settings(bot_id)` | `SELECT support_username FROM bots WHERE id = {bot_id}`<br>`SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key LIKE 'SUPPORT_%'` | تنظیمات پشتیبانی |
| `admin_tenant_bot_config_notifications:{bot_id}` | `show_notification_settings(bot_id)` | `SELECT admin_chat_id, admin_topic_id, notification_group_id, notification_topic_id FROM bots WHERE id = {bot_id}`<br>`SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key LIKE '%NOTIFICATION%' OR config_key LIKE '%REPORT%'` | تنظیمات اعلان‌ها |
| `admin_tenant_bot_config_subscription:{bot_id}` | `show_subscription_settings(bot_id)` | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key IN ('TRIAL_DURATION_DAYS', 'TRIAL_TRAFFIC_LIMIT_GB', 'DEFAULT_DEVICE_LIMIT', 'MAX_DEVICES_LIMIT', ...)` | تنظیمات اشتراک |
| `admin_tenant_bot_config_pricing:{bot_id}` | `show_pricing_settings(bot_id)` | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND (config_key LIKE 'PRICE_%' OR config_key LIKE 'TRAFFIC_PACKAGES%' OR config_key = 'PRICE_PER_DEVICE')` | تنظیمات قیمت‌گذاری |
| `admin_tenant_bot_config_ui:{bot_id}` | `show_ui_settings(bot_id)` | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key IN ('ENABLE_LOGO_MODE', 'LOGO_FILE', 'MAIN_MENU_MODE', 'HIDE_SUBSCRIPTION_LINK', 'CONNECT_BUTTON_MODE', ...)` | تنظیمات UI/UX |
| `admin_tenant_bot_config_integrations:{bot_id}` | `show_integration_settings(bot_id)` | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND (config_key LIKE 'SERVER_STATUS%' OR config_key LIKE 'MONITORING%' OR config_key LIKE 'MAINTENANCE%')` | تنظیمات یکپارچه‌سازی |
| `admin_tenant_bot_config_advanced:{bot_id}` | `show_advanced_settings(bot_id)` | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND (config_key LIKE 'AUTOPAY%' OR config_key LIKE 'REFERRAL%' OR config_key LIKE 'PROMO%' OR config_key LIKE 'CONTEST%')` | تنظیمات پیشرفته |
| `admin_tenant_bot_edit_config:{bot_id}:{config_key}` | `start_edit_config(bot_id, config_key)` | FSM: `AdminStates.editing_tenant_config` | شروع ویرایش config |

### Analytics Level

| Callback | Handler Function | Database Query | Description |
|----------|-----------------|----------------|-------------|
| `admin_tenant_bot_analytics:{bot_id}` | `show_bot_analytics(bot_id)` | Complex analytics queries with date ranges | آنالیتیکس ربات |
| `admin_tenant_bot_analytics_detailed:{bot_id}` | `show_detailed_analytics(bot_id)` | More complex queries | آنالیتیکس تفصیلی |
| `admin_tenant_bot_analytics_export:{bot_id}` | `export_analytics(bot_id)` | Same as analytics + export to file | Export گزارش |

### Test & Delete Level

| Callback | Handler Function | Database Query | Description |
|----------|-----------------|----------------|-------------|
| `admin_tenant_bot_test:{bot_id}` | `test_bot_status(bot_id)` | `SELECT * FROM bots WHERE id = {bot_id}`<br>Check `active_bots` registry | تست وضعیت ربات |
| `admin_tenant_bot_delete:{bot_id}` | `start_delete_bot(bot_id)` | Confirmation first | شروع حذف ربات |
| `admin_tenant_bot_delete_confirm:{bot_id}` | `delete_bot(bot_id)` | `DELETE FROM bots WHERE id = {bot_id}` (CASCADE) | تایید و حذف ربات |

---

## 🔄 FSM States for Editing

### New States Required

```python
# app/states.py

class AdminStates(StatesGroup):
    # ... existing states ...
    
    # Tenant Bot Creation
    waiting_for_bot_name = State()
    waiting_for_bot_token = State()
    waiting_for_bot_language = State()
    waiting_for_bot_support = State()
    
    # Tenant Bot Editing
    editing_tenant_bot_name = State()
    editing_tenant_bot_language = State()
    editing_tenant_bot_support = State()
    editing_tenant_bot_notifications = State()
    
    # Payment Cards
    adding_tenant_payment_card = State()
    editing_tenant_payment_card = State()
    waiting_for_card_number = State()
    waiting_for_card_holder = State()
    
    # Payment Gateways
    editing_tenant_zarinpal = State()
    editing_tenant_yookassa = State()
    editing_tenant_cryptobot = State()
    editing_tenant_pal24 = State()
    editing_tenant_mulenpay = State()
    editing_tenant_platega = State()
    editing_tenant_heleket = State()
    
    # Plans
    creating_tenant_plan = State()
    editing_tenant_plan = State()
    waiting_for_plan_name = State()
    waiting_for_plan_period = State()
    waiting_for_plan_price = State()
    waiting_for_plan_traffic = State()
    waiting_for_plan_devices = State()
    
    # Configuration
    editing_tenant_config = State()
    waiting_for_config_value = State()
    
    # Config Categories
    editing_basic_settings = State()
    editing_support_settings = State()
    editing_notification_settings = State()
    editing_subscription_settings = State()
    editing_pricing_settings = State()
    editing_ui_settings = State()
    editing_integration_settings = State()
    editing_advanced_settings = State()
```

---

## 🗄️ Database Operations Summary

### Read Operations (SELECT)

| Operation | Table(s) | Filter | Purpose |
|-----------|---------|--------|---------|
| List bots | `bots` | `is_master = FALSE` | لیست تمام tenant bots |
| Bot details | `bots` | `id = {bot_id}` | اطلاعات ربات |
| User count | `users` | `bot_id = {bot_id}` | تعداد کاربران |
| Subscription count | `subscriptions` | `bot_id = {bot_id}` | تعداد اشتراک‌ها |
| Revenue | `transactions` | `bot_id = {bot_id} AND type = 'deposit'` | درآمد |
| Feature flags | `bot_feature_flags` | `bot_id = {bot_id}` | Feature flags فعال |
| Configurations | `bot_configurations` | `bot_id = {bot_id}` | تنظیمات |
| Payment cards | `tenant_payment_cards` | `bot_id = {bot_id}` | کارت‌های پرداخت |
| Plans | `bot_plans` | `bot_id = {bot_id}` | پلن‌های اشتراک |
| Plan features | `plan_feature_grants` + `tenant_subscriptions` | Join on `bot_id` | Features پلن |

### Write Operations (INSERT/UPDATE)

| Operation | Table | Action | Purpose |
|-----------|-------|--------|---------|
| Create bot | `bots` | `INSERT` | ایجاد ربات جدید |
| Update bot | `bots` | `UPDATE` | به‌روزرسانی اطلاعات ربات |
| Toggle feature | `bot_feature_flags` | `INSERT ... ON CONFLICT UPDATE` | تغییر وضعیت feature |
| Set config | `bot_configurations` | `INSERT ... ON CONFLICT UPDATE` | تنظیم configuration |
| Add card | `tenant_payment_cards` | `INSERT` | افزودن کارت پرداخت |
| Create plan | `bot_plans` | `INSERT` | ایجاد پلن جدید |
| Update plan | `bot_plans` | `UPDATE` | به‌روزرسانی پلن |
| Delete plan | `bot_plans` | `DELETE` | حذف پلن |

### Delete Operations

| Operation | Table | Cascade | Purpose |
|-----------|-------|---------|---------|
| Delete bot | `bots` | `CASCADE` → All related tables | حذف ربات و تمام داده‌های مرتبط |

---

## 🔐 Access Control Matrix

| Action | Master Admin | Tenant Admin | Notes |
|--------|--------------|--------------|-------|
| View tenant bots list | ✅ | ❌ | فقط master |
| Create tenant bot | ✅ | ❌ | فقط master |
| View bot details | ✅ | ✅ (own bot only) | Master: همه | Tenant: فقط خودش |
| Edit bot settings | ✅ | ✅ (own bot only) | Master: همه | Tenant: فقط خودش |
| Toggle feature flags | ✅ | ❌ | فقط master |
| Manage payment cards | ✅ | ✅ (own bot only) | Master: همه | Tenant: فقط خودش |
| Manage plans | ✅ | ✅ (own bot only) | Master: همه | Tenant: فقط خودش |
| Edit configurations | ✅ | ✅ (own bot only) | Master: همه | Tenant: فقط خودش |
| View statistics | ✅ | ✅ (own bot only) | Master: همه | Tenant: فقط خودش |
| Delete bot | ✅ | ❌ | فقط master |

---

## 📊 Statistics Queries by Category

### User Statistics

```sql
-- Total users
SELECT COUNT(*) FROM users WHERE bot_id = {bot_id};

-- Active users (have active subscription)
SELECT COUNT(DISTINCT user_id) 
FROM subscriptions 
WHERE bot_id = {bot_id} AND status = 'active';

-- New users (last 30 days)
SELECT COUNT(*) 
FROM users 
WHERE bot_id = {bot_id} 
  AND created_at >= CURRENT_DATE - INTERVAL '30 days';

-- User growth trend
SELECT 
    DATE(created_at) as date,
    COUNT(*) as new_users
FROM users
WHERE bot_id = {bot_id}
  AND created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date;
```

### Subscription Statistics

```sql
-- Total subscriptions
SELECT COUNT(*) FROM subscriptions WHERE bot_id = {bot_id};

-- Active subscriptions
SELECT COUNT(*) 
FROM subscriptions 
WHERE bot_id = {bot_id} AND status = 'active';

-- Trial vs Paid
SELECT 
    COUNT(CASE WHEN is_trial = TRUE THEN 1 END) as trial_count,
    COUNT(CASE WHEN is_trial = FALSE THEN 1 END) as paid_count
FROM subscriptions
WHERE bot_id = {bot_id};

-- Subscription growth
SELECT 
    DATE(created_at) as date,
    COUNT(*) as new_subs
FROM subscriptions
WHERE bot_id = {bot_id}
  AND created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date;
```

### Revenue Statistics

```sql
-- Total revenue (all time)
SELECT COALESCE(SUM(amount_kopeks), 0) 
FROM transactions 
WHERE bot_id = {bot_id} 
  AND type = 'deposit' 
  AND is_completed = TRUE;

-- Monthly revenue
SELECT COALESCE(SUM(amount_kopeks), 0) 
FROM transactions 
WHERE bot_id = {bot_id} 
  AND type = 'deposit' 
  AND is_completed = TRUE
  AND created_at >= date_trunc('month', CURRENT_DATE);

-- Revenue by payment method
SELECT 
    payment_method,
    COUNT(*) as transaction_count,
    COALESCE(SUM(amount_kopeks), 0) as total_revenue
FROM transactions
WHERE bot_id = {bot_id}
  AND type = 'deposit'
  AND is_completed = TRUE
  AND created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY payment_method
ORDER BY total_revenue DESC;

-- Daily revenue trend
SELECT 
    DATE(created_at) as date,
    COALESCE(SUM(amount_kopeks), 0) as daily_revenue
FROM transactions
WHERE bot_id = {bot_id}
  AND type = 'deposit'
  AND is_completed = TRUE
  AND created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date;
```

### Traffic Statistics

```sql
-- Traffic sold (from bots table)
SELECT traffic_sold_bytes FROM bots WHERE id = {bot_id};

-- Traffic consumed (from bots table)
SELECT traffic_consumed_bytes FROM bots WHERE id = {bot_id};

-- Traffic by subscription
SELECT 
    s.id,
    s.traffic_limit_gb,
    s.traffic_used_gb,
    (s.traffic_used_gb / NULLIF(s.traffic_limit_gb, 0) * 100) as usage_percent
FROM subscriptions s
WHERE s.bot_id = {bot_id} AND s.status = 'active';
```

---

## 🎯 Implementation Priority

### Phase 1: Core Menu Structure (Week 1)
- [ ] Main tenant bots menu
- [ ] List bots with pagination
- [ ] Bot detail menu
- [ ] Basic navigation

### Phase 2: Statistics & Overview (Week 1-2)
- [ ] Bot overview statistics
- [ ] Quick stats in detail menu
- [ ] Statistics page

### Phase 3: Feature Flags (Week 2)
- [ ] Feature flags menu
- [ ] Toggle functionality
- [ ] Plan-based restrictions

### Phase 4: Payment Methods (Week 2-3)
- [ ] Payment methods overview
- [ ] Card-to-card management
- [ ] Gateway configurations

### Phase 5: Configuration System (Week 3-4)
- [ ] Configuration categories
- [ ] Edit forms
- [ ] Save to database

### Phase 6: Plans Management (Week 4)
- [ ] Plans list
- [ ] Create/edit/delete plans

### Phase 7: Analytics (Week 5)
- [ ] Performance metrics
- [ ] Charts
- [ ] Export

---

## 📚 Related Files

- **Handlers:** `app/handlers/admin/tenant_bots.py`
- **Keyboards:** `app/keyboards/admin.py` (add tenant bots keyboards)
- **States:** `app/states.py` (add FSM states)
- **CRUD:** `app/database/crud/bot*.py`
- **Models:** `app/database/models.py`

---

**End of Document**
