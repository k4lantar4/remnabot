# Tenant Bots Admin - Complete Callback → Handler → Database Mapping

**Version:** 1.0  
**Date:** 2025-12-14  
**Status:** Complete Reference

---

## 📋 Executive Summary

این مستند mapping کامل بین:
- Callback Data Patterns
- Handler Functions
- Database Queries
- FSM States

را برای تمام منوها و عملیات Tenant Bots Management ارائه می‌دهد.

---

## 🎯 Callback Data Pattern Structure

### Pattern Rules

1. **Main Menu:** `admin_tenant_bots_{action}`
2. **Bot-Specific:** `admin_tenant_bot_{action}:{bot_id}`
3. **With Parameters:** `admin_tenant_bot_{action}:{bot_id}:{param}`
4. **Edit Operations:** `admin_tenant_bot_edit_{field}:{bot_id}`
5. **Toggle Operations:** `admin_tenant_bot_toggle_{feature}:{bot_id}`
6. **Category Navigation:** `admin_tenant_bot_{category}:{bot_id}`

---

## 📊 Complete Mapping Table

### Level 1: Main Menu

| Callback | Handler Function | File | Database Query | Description |
|----------|-----------------|------|----------------|-------------|
| `admin_tenant_bots_menu` | `show_tenant_bots_menu()` | `app/handlers/admin/tenant_bots.py` | `SELECT COUNT(*) FROM bots WHERE is_master = FALSE`<br>`SELECT COUNT(*) FROM bots WHERE is_master = FALSE AND is_active = TRUE`<br>`SELECT COUNT(DISTINCT u.id) FROM users u JOIN bots b ON u.bot_id = b.id WHERE b.is_master = FALSE`<br>`SELECT COALESCE(SUM(t.amount_kopeks), 0) FROM transactions t JOIN bots b ON t.bot_id = b.id WHERE b.is_master = FALSE AND t.type = 'deposit'` | نمایش منوی اصلی با آمار کلی |
| `admin_tenant_bots_list` | `list_tenant_bots(page=0)` | `app/handlers/admin/tenant_bots.py` | `SELECT b.*, COUNT(DISTINCT u.id) as user_count, COALESCE(SUM(t.amount_kopeks), 0) as revenue FROM bots b LEFT JOIN users u ON u.bot_id = b.id LEFT JOIN transactions t ON t.bot_id = b.id AND t.type = 'deposit' WHERE b.is_master = FALSE GROUP BY b.id ORDER BY b.created_at DESC LIMIT 5 OFFSET {page*5}` | لیست ربات‌ها با pagination |
| `admin_tenant_bots_list:{page}` | `list_tenant_bots(page={page})` | Same | Same with different offset | Pagination |
| `admin_tenant_bots_create` | `start_create_bot()` | Same | None (FSM start) | شروع فرآیند ایجاد ربات |
| `admin_tenant_bots_stats` | `show_tenant_bots_statistics()` | Same | Multiple aggregation queries across all tenants | آمار کلی تمام tenants |
| `admin_tenant_bots_settings` | `show_tenant_bots_settings()` | Same | None (menu only) | تنظیمات کلی tenant bots |

---

### Level 2: Bot Detail Menu

| Callback | Handler Function | File | Database Query | Description |
|----------|-----------------|------|----------------|-------------|
| `admin_tenant_bot_detail:{bot_id}` | `show_bot_detail(bot_id)` | `app/handlers/admin/tenant_bots.py` | `SELECT * FROM bots WHERE id = {bot_id}`<br>`SELECT COUNT(*) FROM users WHERE bot_id = {bot_id}`<br>`SELECT COUNT(*) FROM subscriptions WHERE bot_id = {bot_id} AND status = 'active'`<br>`SELECT COALESCE(SUM(amount_kopeks), 0) FROM transactions WHERE bot_id = {bot_id} AND type = 'deposit' AND created_at >= date_trunc('month', CURRENT_DATE)`<br>`SELECT traffic_consumed_bytes, traffic_sold_bytes, wallet_balance_toman FROM bots WHERE id = {bot_id}` | نمایش جزئیات ربات با آمار سریع |
| `admin_tenant_bot_activate:{bot_id}` | `activate_tenant_bot(bot_id)` | Same | `UPDATE bots SET is_active = TRUE, updated_at = NOW() WHERE id = {bot_id}` | فعال‌سازی ربات |
| `admin_tenant_bot_deactivate:{bot_id}` | `deactivate_tenant_bot(bot_id)` | Same | `UPDATE bots SET is_active = FALSE, updated_at = NOW() WHERE id = {bot_id}` | غیرفعال‌سازی ربات |
| `admin_tenant_bot_test:{bot_id}` | `test_bot_status(bot_id)` | Same | `SELECT * FROM bots WHERE id = {bot_id}`<br>Check `active_bots` registry | تست وضعیت ربات |
| `admin_tenant_bot_delete:{bot_id}` | `start_delete_bot(bot_id)` | Same | Confirmation first | شروع فرآیند حذف |
| `admin_tenant_bot_delete_confirm:{bot_id}` | `delete_bot(bot_id)` | Same | `DELETE FROM bots WHERE id = {bot_id}` (CASCADE deletes all related data) | تایید و حذف ربات |

---

### Level 3A: Statistics

| Callback | Handler Function | File | Database Query | Description |
|----------|-----------------|------|----------------|-------------|
| `admin_tenant_bot_stats:{bot_id}` | `show_bot_statistics(bot_id)` | `app/handlers/admin/tenant_bots.py` | `SELECT COUNT(*) FROM users WHERE bot_id = {bot_id} AND created_at >= CURRENT_DATE - INTERVAL '30 days'`<br>`SELECT COUNT(DISTINCT user_id) FROM subscriptions WHERE bot_id = {bot_id} AND status = 'active'`<br>`SELECT COUNT(*) FROM subscriptions WHERE bot_id = {bot_id} AND created_at >= CURRENT_DATE - INTERVAL '30 days'`<br>`SELECT COALESCE(SUM(amount_kopeks), 0) FROM transactions WHERE bot_id = {bot_id} AND type = 'deposit' AND created_at >= CURRENT_DATE - INTERVAL '30 days'`<br>`SELECT payment_method, COUNT(*) as count, COALESCE(SUM(amount_kopeks), 0) as revenue FROM transactions WHERE bot_id = {bot_id} AND type = 'deposit' AND created_at >= CURRENT_DATE - INTERVAL '30 days' GROUP BY payment_method` | آمار 30 روزه ربات |
| `admin_tenant_bot_stats_detailed:{bot_id}` | `show_detailed_statistics(bot_id)` | Same | Complex queries with date ranges, user segments, subscription types | آمار تفصیلی |
| `admin_tenant_bot_stats_revenue:{bot_id}` | `show_revenue_statistics(bot_id)` | Same | `SELECT DATE(created_at) as date, COALESCE(SUM(amount_kopeks), 0) as revenue FROM transactions WHERE bot_id = {bot_id} AND type = 'deposit' AND created_at >= CURRENT_DATE - INTERVAL '30 days' GROUP BY DATE(created_at) ORDER BY date` | نمودار درآمد |
| `admin_tenant_bot_stats_users:{bot_id}` | `show_user_statistics(bot_id)` | Same | `SELECT DATE(created_at) as date, COUNT(*) as new_users FROM users WHERE bot_id = {bot_id} AND created_at >= CURRENT_DATE - INTERVAL '30 days' GROUP BY DATE(created_at) ORDER BY date` | نمودار رشد کاربران |

---

### Level 3B: General Settings

| Callback | Handler Function | File | Database Query | Description |
|----------|-----------------|------|----------------|-------------|
| `admin_tenant_bot_settings:{bot_id}` | `show_bot_settings(bot_id)` | `app/handlers/admin/tenant_bots.py` | `SELECT * FROM bots WHERE id = {bot_id}` | نمایش تنظیمات عمومی |
| `admin_tenant_bot_edit_name:{bot_id}` | `start_edit_name(bot_id)` | Same | FSM: `AdminStates.editing_tenant_bot_name` | شروع ویرایش نام |
| `admin_tenant_bot_edit_language:{bot_id}` | `start_edit_language(bot_id)` | Same | FSM: `AdminStates.editing_tenant_bot_language` | شروع ویرایش زبان |
| `admin_tenant_bot_edit_support:{bot_id}` | `start_edit_support(bot_id)` | Same | FSM: `AdminStates.editing_tenant_bot_support` | شروع ویرایش پشتیبانی |
| `admin_tenant_bot_edit_notifications:{bot_id}` | `start_edit_notifications(bot_id)` | Same | FSM: `AdminStates.editing_tenant_bot_notifications` | شروع ویرایش اعلان‌ها |
| `admin_tenant_bot_toggle_card:{bot_id}` | `toggle_card_to_card(bot_id)` | Same | `UPDATE bots SET card_to_card_enabled = NOT card_to_card_enabled, updated_at = NOW() WHERE id = {bot_id}` | تغییر وضعیت کارت به کارت |
| `admin_tenant_bot_toggle_zarinpal:{bot_id}` | `toggle_zarinpal(bot_id)` | Same | `UPDATE bots SET zarinpal_enabled = NOT zarinpal_enabled, updated_at = NOW() WHERE id = {bot_id}` | تغییر وضعیت زرین‌پال |

**FSM Handlers:**
- `AdminStates.editing_tenant_bot_name` → `process_edit_name(message, state, db)`
- `AdminStates.editing_tenant_bot_language` → `process_edit_language(message, state, db)`
- `AdminStates.editing_tenant_bot_support` → `process_edit_support(message, state, db)`
- `AdminStates.editing_tenant_bot_notifications` → `process_edit_notifications(message, state, db)`

**Update Queries:**
- Name: `UPDATE bots SET name = {value}, updated_at = NOW() WHERE id = {bot_id}`
- Language: `UPDATE bots SET default_language = {value}, updated_at = NOW() WHERE id = {bot_id}`
- Support: `UPDATE bots SET support_username = {value}, updated_at = NOW() WHERE id = {bot_id}`
- Notifications: `UPDATE bots SET admin_chat_id = {value}, admin_topic_id = {value}, updated_at = NOW() WHERE id = {bot_id}`

---

### Level 3C: Feature Flags

| Callback | Handler Function | File | Database Query | Description |
|----------|-----------------|------|----------------|-------------|
| `admin_tenant_bot_features:{bot_id}` | `show_bot_feature_flags(bot_id)` | `app/handlers/admin/tenant_bots.py` | `SELECT * FROM bot_feature_flags WHERE bot_id = {bot_id}`<br>`SELECT pf.* FROM plan_feature_grants pf JOIN tenant_subscriptions ts ON ts.plan_tier_id = pf.plan_tier_id WHERE ts.bot_id = {bot_id} AND ts.status = 'active'`<br>`SELECT tsp.name, tsp.display_name FROM tenant_subscriptions ts JOIN tenant_subscription_plans tsp ON ts.plan_tier_id = tsp.id WHERE ts.bot_id = {bot_id} AND ts.status = 'active'` | نمایش feature flags و پلن فعلی |
| `admin_tenant_bot_toggle_feature:{bot_id}:{feature_key}` | `toggle_feature_flag(bot_id, feature_key)` | Same | `INSERT INTO bot_feature_flags (bot_id, feature_key, enabled, created_at, updated_at) VALUES ({bot_id}, '{feature_key}', {new_value}, NOW(), NOW()) ON CONFLICT (bot_id, feature_key) DO UPDATE SET enabled = {new_value}, updated_at = NOW()` | تغییر وضعیت feature |
| `admin_tenant_bot_features_plan:{bot_id}` | `show_plan_features(bot_id)` | Same | `SELECT tsp.*, pf.feature_key, pf.enabled, pf.config_override FROM tenant_subscriptions ts JOIN tenant_subscription_plans tsp ON ts.plan_tier_id = tsp.id JOIN plan_feature_grants pf ON pf.plan_tier_id = tsp.id WHERE ts.bot_id = {bot_id} AND ts.status = 'active' ORDER BY pf.feature_key` | نمایش features پلن فعلی |
| `admin_tenant_bot_features_override:{bot_id}` | `show_override_options(bot_id)` | Same | `SELECT bff.*, pf.enabled as plan_enabled FROM bot_feature_flags bff LEFT JOIN plan_feature_grants pf ON pf.feature_key = bff.feature_key JOIN tenant_subscriptions ts ON ts.plan_tier_id = pf.plan_tier_id WHERE bff.bot_id = {bot_id} AND ts.bot_id = {bot_id} AND ts.status = 'active'` | نمایش override options |

---

### Level 3D: Payment Methods

| Callback | Handler Function | File | Database Query | Description |
|----------|-----------------|------|----------------|-------------|
| `admin_tenant_bot_payments:{bot_id}` | `show_bot_payment_methods(bot_id)` | `app/handlers/admin/tenant_bots.py` | `SELECT card_to_card_enabled, card_receipt_topic_id, zarinpal_enabled, zarinpal_merchant_id, zarinpal_sandbox FROM bots WHERE id = {bot_id}`<br>`SELECT COUNT(*) FROM tenant_payment_cards WHERE bot_id = {bot_id} AND is_active = TRUE`<br>`SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key LIKE '%_ENABLED'`<br>`SELECT * FROM bot_feature_flags WHERE bot_id = {bot_id} AND feature_key IN ('yookassa', 'cryptobot', 'pal24', 'mulenpay', 'platega', 'heleket', 'tribute', 'telegram_stars', 'wata')` | نمایش روش‌های پرداخت و وضعیت آنها |
| `admin_tenant_bot_cards:{bot_id}` | `show_bot_payment_cards(bot_id)` | Same | `SELECT * FROM tenant_payment_cards WHERE bot_id = {bot_id} ORDER BY created_at DESC` | لیست کارت‌های پرداخت |
| `admin_tenant_bot_cards:{bot_id}:{page}` | `show_bot_payment_cards(bot_id, page)` | Same | Same with pagination | Pagination کارت‌ها |
| `admin_tenant_bot_card_add:{bot_id}` | `start_add_card(bot_id)` | Same | FSM: `AdminStates.adding_tenant_payment_card` | شروع افزودن کارت |
| `admin_tenant_bot_card_edit:{card_id}` | `start_edit_card(card_id)` | Same | `SELECT * FROM tenant_payment_cards WHERE id = {card_id}`<br>FSM: `AdminStates.editing_tenant_payment_card` | شروع ویرایش کارت |
| `admin_tenant_bot_card_delete:{card_id}` | `delete_card(card_id)` | Same | `DELETE FROM tenant_payment_cards WHERE id = {card_id}` | حذف کارت |
| `admin_tenant_bot_card_toggle:{card_id}` | `toggle_card_status(card_id)` | Same | `UPDATE tenant_payment_cards SET is_active = NOT is_active, updated_at = NOW() WHERE id = {card_id}` | فعال/غیرفعال کردن کارت |
| `admin_tenant_bot_zarinpal:{bot_id}` | `show_zarinpal_config(bot_id)` | Same | `SELECT zarinpal_enabled, zarinpal_merchant_id, zarinpal_sandbox FROM bots WHERE id = {bot_id}` | تنظیمات زرین‌پال |
| `admin_tenant_bot_zarinpal_edit:{bot_id}` | `start_edit_zarinpal(bot_id)` | Same | FSM: `AdminStates.editing_tenant_zarinpal` | شروع ویرایش زرین‌پال |
| `admin_tenant_bot_yookassa:{bot_id}` | `show_yookassa_config(bot_id)` | Same | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key LIKE 'YOOKASSA_%'`<br>`SELECT enabled FROM bot_feature_flags WHERE bot_id = {bot_id} AND feature_key = 'yookassa'` | تنظیمات YooKassa |
| `admin_tenant_bot_yookassa_edit:{bot_id}` | `start_edit_yookassa(bot_id)` | Same | FSM: `AdminStates.editing_tenant_yookassa` | شروع ویرایش YooKassa |
| `admin_tenant_bot_cryptobot:{bot_id}` | `show_cryptobot_config(bot_id)` | Same | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key LIKE 'CRYPTOBOT_%'`<br>`SELECT enabled FROM bot_feature_flags WHERE bot_id = {bot_id} AND feature_key = 'cryptobot'` | تنظیمات CryptoBot |
| `admin_tenant_bot_cryptobot_edit:{bot_id}` | `start_edit_cryptobot(bot_id)` | Same | FSM: `AdminStates.editing_tenant_cryptobot` | شروع ویرایش CryptoBot |
| `admin_tenant_bot_pal24:{bot_id}` | `show_pal24_config(bot_id)` | Same | Similar pattern for PAL24 | تنظیمات PAL24 |
| `admin_tenant_bot_mulenpay:{bot_id}` | `show_mulenpay_config(bot_id)` | Same | Similar pattern for MulenPay | تنظیمات MulenPay |
| `admin_tenant_bot_platega:{bot_id}` | `show_platega_config(bot_id)` | Same | Similar pattern for Platega | تنظیمات Platega |
| `admin_tenant_bot_heleket:{bot_id}` | `show_heleket_config(bot_id)` | Same | Similar pattern for Heleket | تنظیمات Heleket |
| `admin_tenant_bot_tribute:{bot_id}` | `show_tribute_config(bot_id)` | Same | Similar pattern for Tribute | تنظیمات Tribute |
| `admin_tenant_bot_wata:{bot_id}` | `show_wata_config(bot_id)` | Same | Similar pattern for WATA | تنظیمات WATA |
| `admin_tenant_bot_stars:{bot_id}` | `show_stars_config(bot_id)` | Same | Similar pattern for Telegram Stars | تنظیمات Telegram Stars |

**FSM States for Payment Gateways:**
- `AdminStates.editing_tenant_zarinpal` → Edit Zarinpal settings
- `AdminStates.editing_tenant_yookassa` → Edit YooKassa settings
- `AdminStates.editing_tenant_cryptobot` → Edit CryptoBot settings
- `AdminStates.editing_tenant_pal24` → Edit PAL24 settings
- `AdminStates.editing_tenant_mulenpay` → Edit MulenPay settings
- `AdminStates.editing_tenant_platega` → Edit Platega settings
- `AdminStates.editing_tenant_heleket` → Edit Heleket settings
- `AdminStates.editing_tenant_tribute` → Edit Tribute settings
- `AdminStates.editing_tenant_wata` → Edit WATA settings

---

### Level 3E: Subscription Plans

| Callback | Handler Function | File | Database Query | Description |
|----------|-----------------|------|----------------|-------------|
| `admin_tenant_bot_plans:{bot_id}` | `show_bot_plans(bot_id)` | `app/handlers/admin/tenant_bots.py` | `SELECT * FROM bot_plans WHERE bot_id = {bot_id} ORDER BY sort_order, price_kopeks` | لیست پلن‌های اشتراک |
| `admin_tenant_bot_plans:{bot_id}:{page}` | `show_bot_plans(bot_id, page)` | Same | Same with pagination | Pagination پلن‌ها |
| `admin_tenant_bot_plan_create:{bot_id}` | `start_create_plan(bot_id)` | Same | FSM: `AdminStates.creating_tenant_plan` | شروع ایجاد پلن |
| `admin_tenant_bot_plan_edit:{plan_id}` | `start_edit_plan(plan_id)` | Same | `SELECT * FROM bot_plans WHERE id = {plan_id}`<br>FSM: `AdminStates.editing_tenant_plan` | شروع ویرایش پلن |
| `admin_tenant_bot_plan_delete:{plan_id}` | `delete_plan(plan_id)` | Same | `DELETE FROM bot_plans WHERE id = {plan_id}` | حذف پلن |
| `admin_tenant_bot_plan_toggle:{plan_id}` | `toggle_plan_status(plan_id)` | Same | `UPDATE bot_plans SET is_active = NOT is_active, updated_at = NOW() WHERE id = {plan_id}` | فعال/غیرفعال کردن پلن |
| `admin_tenant_bot_plan_view:{plan_id}` | `view_plan_details(plan_id)` | Same | `SELECT * FROM bot_plans WHERE id = {plan_id}`<br>`SELECT COUNT(*) FROM subscriptions WHERE bot_id = (SELECT bot_id FROM bot_plans WHERE id = {plan_id}) AND status = 'active'` | جزئیات پلن |

**FSM States:**
- `AdminStates.creating_tenant_plan` → Multi-step plan creation
  - `waiting_for_plan_name`
  - `waiting_for_plan_period`
  - `waiting_for_plan_price`
  - `waiting_for_plan_traffic`
  - `waiting_for_plan_devices`
- `AdminStates.editing_tenant_plan` → Edit existing plan

**Database Operations:**
- Create: `INSERT INTO bot_plans (bot_id, name, period_days, price_kopeks, traffic_limit_gb, device_limit, is_active, sort_order) VALUES (...)`
- Update: `UPDATE bot_plans SET name = {value}, period_days = {value}, ... WHERE id = {plan_id}`
- Delete: `DELETE FROM bot_plans WHERE id = {plan_id}`

---

### Level 3F: Configuration Categories

| Callback | Handler Function | File | Database Query | Description |
|----------|-----------------|------|----------------|-------------|
| `admin_tenant_bot_config:{bot_id}` | `show_bot_configuration_menu(bot_id)` | `app/handlers/admin/tenant_bots.py` | None (menu only) | منوی دسته‌بندی configs |
| `admin_tenant_bot_config_basic:{bot_id}` | `show_basic_settings(bot_id)` | Same | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key IN ('DEFAULT_LANGUAGE', 'AVAILABLE_LANGUAGES', 'LANGUAGE_SELECTION_ENABLED', 'TZ', 'SKIP_RULES_ACCEPT', 'SKIP_REFERRAL_CODE')` | تنظیمات پایه |
| `admin_tenant_bot_config_support:{bot_id}` | `show_support_settings(bot_id)` | Same | `SELECT support_username FROM bots WHERE id = {bot_id}`<br>`SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key LIKE 'SUPPORT_%'` | تنظیمات پشتیبانی |
| `admin_tenant_bot_config_notifications:{bot_id}` | `show_notification_settings(bot_id)` | Same | `SELECT admin_chat_id, admin_topic_id, notification_group_id, notification_topic_id FROM bots WHERE id = {bot_id}`<br>`SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND (config_key LIKE '%NOTIFICATION%' OR config_key LIKE '%REPORT%')` | تنظیمات اعلان‌ها |
| `admin_tenant_bot_config_subscription:{bot_id}` | `show_subscription_settings(bot_id)` | Same | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key IN ('TRIAL_DURATION_DAYS', 'TRIAL_TRAFFIC_LIMIT_GB', 'TRIAL_DEVICE_LIMIT', 'TRIAL_PAYMENT_ENABLED', 'TRIAL_ACTIVATION_PRICE', 'DEFAULT_DEVICE_LIMIT', 'MAX_DEVICES_LIMIT', 'DEFAULT_TRAFFIC_LIMIT_GB', 'DEFAULT_TRAFFIC_RESET_STRATEGY', 'RESET_TRAFFIC_ON_PAYMENT', 'TRAFFIC_SELECTION_MODE', 'FIXED_TRAFFIC_LIMIT_GB', 'AVAILABLE_SUBSCRIPTION_PERIODS', 'AVAILABLE_RENEWAL_PERIODS')` | تنظیمات اشتراک |
| `admin_tenant_bot_config_pricing:{bot_id}` | `show_pricing_settings(bot_id)` | Same | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND (config_key LIKE 'PRICE_%' OR config_key = 'TRAFFIC_PACKAGES_CONFIG' OR config_key = 'PRICE_PER_DEVICE' OR config_key = 'DEVICES_SELECTION_ENABLED' OR config_key = 'DEVICES_SELECTION_DISABLED_AMOUNT')` | تنظیمات قیمت‌گذاری |
| `admin_tenant_bot_config_ui:{bot_id}` | `show_ui_settings(bot_id)` | Same | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND config_key IN ('ENABLE_LOGO_MODE', 'LOGO_FILE', 'MAIN_MENU_MODE', 'HIDE_SUBSCRIPTION_LINK', 'CONNECT_BUTTON_MODE', 'MINIAPP_CUSTOM_URL', 'MINIAPP_STATIC_PATH', 'MINIAPP_SERVICE_NAME_EN', 'MINIAPP_SERVICE_NAME_RU', 'MINIAPP_SERVICE_DESCRIPTION_EN', 'MINIAPP_SERVICE_DESCRIPTION_RU', 'CONNECT_BUTTON_HAPP_DOWNLOAD_ENABLED', 'HAPP_DOWNLOAD_LINK_IOS', 'HAPP_DOWNLOAD_LINK_ANDROID', 'HAPP_DOWNLOAD_LINK_MACOS', 'HAPP_DOWNLOAD_LINK_WINDOWS', 'HAPP_CRYPTOLINK_REDIRECT_TEMPLATE')` | تنظیمات UI/UX |
| `admin_tenant_bot_config_integrations:{bot_id}` | `show_integration_settings(bot_id)` | Same | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND (config_key LIKE 'SERVER_STATUS%' OR config_key LIKE 'MONITORING%' OR config_key LIKE 'MAINTENANCE%' OR config_key LIKE 'BLACKLIST%')` | تنظیمات یکپارچه‌سازی |
| `admin_tenant_bot_config_advanced:{bot_id}` | `show_advanced_settings(bot_id)` | Same | `SELECT config_key, config_value FROM bot_configurations WHERE bot_id = {bot_id} AND (config_key LIKE 'AUTOPAY%' OR config_key LIKE 'REFERRAL%' OR config_key LIKE 'PROMO%' OR config_key LIKE 'CONTEST%' OR config_key LIKE 'SIMPLE_SUBSCRIPTION%')` | تنظیمات پیشرفته |

**Edit Config Callbacks:**
- `admin_tenant_bot_edit_config:{bot_id}:{config_key}` → `start_edit_config(bot_id, config_key)`
- FSM: `AdminStates.editing_tenant_config`
- Handler: `process_edit_config(message, state, db)`
- Update: `INSERT INTO bot_configurations (bot_id, config_key, config_value, created_at, updated_at) VALUES ({bot_id}, '{config_key}', {value}::jsonb, NOW(), NOW()) ON CONFLICT (bot_id, config_key) DO UPDATE SET config_value = {value}::jsonb, updated_at = NOW()`

---

### Level 3G: Analytics

| Callback | Handler Function | File | Database Query | Description |
|----------|-----------------|------|----------------|-------------|
| `admin_tenant_bot_analytics:{bot_id}` | `show_bot_analytics(bot_id)` | `app/handlers/admin/tenant_bots.py` | Complex analytics queries with date ranges, user segments, conversion rates, ARPU calculations | آنالیتیکس ربات |
| `admin_tenant_bot_analytics_detailed:{bot_id}` | `show_detailed_analytics(bot_id)` | Same | More complex queries with trends, comparisons, predictions | آنالیتیکس تفصیلی |
| `admin_tenant_bot_analytics_export:{bot_id}` | `export_analytics(bot_id)` | Same | Same as analytics + export to CSV/JSON | Export گزارش |

---

## 🔄 FSM State Handlers

### Bot Creation Flow

| State | Handler | Database Operation |
|-------|---------|-------------------|
| `AdminStates.waiting_for_bot_name` | `process_bot_name(message, state, db)` | Store in FSM state |
| `AdminStates.waiting_for_bot_token` | `process_bot_token(message, state, db)` | Validate token, then `INSERT INTO bots (...) RETURNING id, api_token` |
| `AdminStates.waiting_for_bot_language` | `process_bot_language(callback, state, db)` | `UPDATE bots SET default_language = {value} WHERE id = {bot_id}` |
| `AdminStates.waiting_for_bot_support` | `process_bot_support(message, state, db)` | `UPDATE bots SET support_username = {value} WHERE id = {bot_id}` |

### Payment Card Management

| State | Handler | Database Operation |
|-------|---------|-------------------|
| `AdminStates.adding_tenant_payment_card` | `process_add_card(message, state, db)` | Multi-step: card number → holder name → strategy → `INSERT INTO tenant_payment_cards` |
| `AdminStates.editing_tenant_payment_card` | `process_edit_card(message, state, db)` | `UPDATE tenant_payment_cards SET ... WHERE id = {card_id}` |
| `AdminStates.waiting_for_card_number` | `process_card_number(message, state, db)` | Store in FSM state |
| `AdminStates.waiting_for_card_holder` | `process_card_holder(message, state, db)` | Store in FSM state |

### Plan Management

| State | Handler | Database Operation |
|-------|---------|-------------------|
| `AdminStates.creating_tenant_plan` | `process_create_plan(message, state, db)` | Multi-step plan creation |
| `AdminStates.waiting_for_plan_name` | `process_plan_name(message, state, db)` | Store in FSM state |
| `AdminStates.waiting_for_plan_period` | `process_plan_period(message, state, db)` | Store in FSM state |
| `AdminStates.waiting_for_plan_price` | `process_plan_price(message, state, db)` | Store in FSM state |
| `AdminStates.waiting_for_plan_traffic` | `process_plan_traffic(message, state, db)` | Store in FSM state |
| `AdminStates.waiting_for_plan_devices` | `process_plan_devices(message, state, db)` | Final step: `INSERT INTO bot_plans` |
| `AdminStates.editing_tenant_plan` | `process_edit_plan(message, state, db)` | `UPDATE bot_plans SET ... WHERE id = {plan_id}` |

### Configuration Editing

| State | Handler | Database Operation |
|-------|---------|-------------------|
| `AdminStates.editing_tenant_config` | `process_edit_config(message, state, db)` | `INSERT/UPDATE bot_configurations` |
| `AdminStates.waiting_for_config_value` | `process_config_value(message, state, db)` | Validate and save to `bot_configurations` |

---

## 🗄️ Database Table Usage Summary

### bots Table

**Columns Used:**
- `id` - Primary key
- `name` - Bot name
- `telegram_bot_token` - Bot token
- `is_master` - Master flag
- `is_active` - Active status
- `card_to_card_enabled` - Card-to-card enabled
- `card_receipt_topic_id` - Receipt topic
- `zarinpal_enabled` - Zarinpal enabled
- `zarinpal_merchant_id` - Zarinpal merchant ID
- `zarinpal_sandbox` - Sandbox mode
- `default_language` - Default language
- `support_username` - Support username
- `admin_chat_id` - Admin chat ID
- `admin_topic_id` - Admin topic ID
- `notification_group_id` - Notification group
- `notification_topic_id` - Notification topic
- `wallet_balance_toman` - Wallet balance
- `traffic_consumed_bytes` - Traffic consumed
- `traffic_sold_bytes` - Traffic sold

**Operations:**
- SELECT: Get bot info, statistics
- UPDATE: Edit bot settings, toggle features
- INSERT: Create new bot
- DELETE: Delete bot (CASCADE)

---

### bot_feature_flags Table

**Columns Used:**
- `bot_id` - Foreign key to bots
- `feature_key` - Feature identifier
- `enabled` - Enabled status
- `config` - Additional config (JSONB)

**Operations:**
- SELECT: Get enabled features for bot
- INSERT/UPDATE: Toggle features
- DELETE: Remove feature flag

**Feature Keys:**
- Payment Gateways: `yookassa`, `cryptobot`, `pal24`, `mulenpay`, `platega`, `heleket`, `tribute`, `wata`, `telegram_stars`
- Payment Methods: `card_to_card`, `zarinpal`
- Features: `trial_subscription`, `auto_renewal`, `simple_purchase`, `referral_program`, `polls`, `support_tickets`, `server_status`, `monitoring`

---

### bot_configurations Table

**Columns Used:**
- `bot_id` - Foreign key to bots
- `config_key` - Configuration key
- `config_value` - Configuration value (JSONB)

**Operations:**
- SELECT: Get configs for bot (filtered by category)
- INSERT/UPDATE: Set/update config
- DELETE: Remove config

**Config Keys:** All TENANT_CONFIGURABLE configs (450+ keys)

---

### tenant_payment_cards Table

**Columns Used:**
- `id` - Primary key
- `bot_id` - Foreign key to bots
- `card_number` - Card number
- `card_holder_name` - Card holder
- `rotation_strategy` - Rotation strategy
- `is_active` - Active status
- `success_count`, `failure_count` - Statistics

**Operations:**
- SELECT: List cards for bot
- INSERT: Add new card
- UPDATE: Edit card, toggle status
- DELETE: Remove card

---

### bot_plans Table

**Columns Used:**
- `id` - Primary key
- `bot_id` - Foreign key to bots
- `name` - Plan name
- `period_days` - Subscription period
- `price_kopeks` - Price
- `traffic_limit_gb` - Traffic limit
- `device_limit` - Device limit
- `is_active` - Active status
- `sort_order` - Display order

**Operations:**
- SELECT: List plans for bot
- INSERT: Create new plan
- UPDATE: Edit plan
- DELETE: Remove plan

---

### Supporting Tables (for Statistics)

| Table | Usage | Query Example |
|-------|-------|---------------|
| `users` | User count, growth | `SELECT COUNT(*) FROM users WHERE bot_id = {bot_id}` |
| `subscriptions` | Subscription stats | `SELECT COUNT(*) FROM subscriptions WHERE bot_id = {bot_id} AND status = 'active'` |
| `transactions` | Revenue stats | `SELECT SUM(amount_kopeks) FROM transactions WHERE bot_id = {bot_id} AND type = 'deposit'` |
| `tenant_subscriptions` | Tenant's plan | `SELECT * FROM tenant_subscriptions WHERE bot_id = {bot_id} AND status = 'active'` |
| `plan_feature_grants` | Plan features | `SELECT * FROM plan_feature_grants WHERE plan_tier_id = {plan_tier_id}` |

---

## 🔐 Access Control Implementation

### Master Admin Check

```python
# app/utils/permissions.py

def is_master_admin(user: User) -> bool:
    """Check if user is master admin"""
    from app.database.crud.bot import get_master_bot
    from app.database.database import AsyncSessionLocal
    
    async with AsyncSessionLocal() as db:
        master_bot = await get_master_bot(db)
        if not master_bot:
            return False
        
        admin_ids = master_bot.admin_ids.split(',') if master_bot.admin_ids else []
        return str(user.telegram_id) in admin_ids

@admin_required
async def handler_function(...):
    """Handler that requires master admin"""
    pass
```

### Tenant Admin Check

```python
def is_tenant_admin(user: User, bot_id: int) -> bool:
    """Check if user is admin of specific tenant bot"""
    # Check if user is in bot's admin_ids (from bot_configurations)
    # Or check if user created the bot
    pass

@tenant_admin_required
async def handler_function(...):
    """Handler that requires tenant admin"""
    pass
```

---

## 📝 Implementation Notes

### 1. Keyboard Generation

```python
# app/keyboards/admin.py

def get_tenant_bots_menu_keyboard(language: str = "ru") -> InlineKeyboardMarkup:
    """Generate tenant bots main menu keyboard"""
    texts = get_texts(language)
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOTS_LIST", "📋 List Bots"),
                callback_data="admin_tenant_bots_list"
            ),
            InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOTS_CREATE", "➕ Create Bot"),
                callback_data="admin_tenant_bots_create"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOTS_STATS", "📊 Statistics"),
                callback_data="admin_tenant_bots_stats"
            ),
            InlineKeyboardButton(
                text=texts.t("ADMIN_TENANT_BOTS_SETTINGS", "⚙️ Settings"),
                callback_data="admin_tenant_bots_settings"
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.BACK,
                callback_data="admin_panel"
            )
        ]
    ])
```

### 2. Handler Registration

```python
# app/handlers/admin/tenant_bots.py

def register_handlers(dp: Dispatcher) -> None:
    """Register all tenant bots handlers"""
    
    # Main menu
    dp.callback_query.register(
        show_tenant_bots_menu,
        F.data == "admin_tenant_bots_menu"
    )
    
    # List bots
    dp.callback_query.register(
        list_tenant_bots,
        F.data.startswith("admin_tenant_bots_list")
    )
    
    # Bot detail
    dp.callback_query.register(
        show_bot_detail,
        F.data.startswith("admin_tenant_bot_detail:")
    )
    
    # Feature flags
    dp.callback_query.register(
        show_bot_feature_flags,
        F.data.startswith("admin_tenant_bot_features:")
    )
    
    dp.callback_query.register(
        toggle_feature_flag,
        F.data.startswith("admin_tenant_bot_toggle_feature:")
    )
    
    # FSM handlers
    dp.message.register(
        process_bot_name,
        StateFilter(AdminStates.waiting_for_bot_name)
    )
    
    dp.message.register(
        process_bot_token,
        StateFilter(AdminStates.waiting_for_bot_token)
    )
    
    # ... more handlers
```

---

## ✅ Implementation Checklist

### Phase 1: Core Structure
- [ ] Main menu handler
- [ ] List bots handler
- [ ] Bot detail handler
- [ ] Navigation handlers

### Phase 2: Feature Flags
- [ ] Feature flags menu
- [ ] Toggle functionality
- [ ] Plan-based restrictions

### Phase 3: Payment Methods
- [ ] Payment methods overview
- [ ] Card management
- [ ] Gateway configurations

### Phase 4: Plans
- [ ] Plans list
- [ ] Create/edit/delete plans

### Phase 5: Configuration
- [ ] Configuration categories
- [ ] Edit forms
- [ ] Save functionality

### Phase 6: Statistics & Analytics
- [ ] Statistics views
- [ ] Analytics queries
- [ ] Export functionality

---

**End of Document**
