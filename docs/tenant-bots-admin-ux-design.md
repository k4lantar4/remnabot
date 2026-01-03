# Tenant Bots Admin UX Design - Complete Guide

**Version:** 1.0  
**Date:** 2025-12-14  
**Status:** Design Complete  
**Author:** Development Team

---

## 📋 Executive Summary

این مستند طراحی کامل UX برای مدیریت Tenant Bots در Master Admin Panel را ارائه می‌دهد. شامل:
- ساختار منو و navigation
- دسته‌بندی configs از `.env.example`
- ارتباط با جداول دیتابیس
- دیاگرام کامل جریان‌ها

---

## 🎯 Design Principles

1. **Consistency**: پیروی از الگوی سایر منوهای admin
2. **Completeness**: دسترسی به تمام تنظیمات قابل شخصی‌سازی
3. **Usability**: ساده و واضح برای استفاده
4. **Security**: دسترسی master admin به tenant bots برای رفع مشکل
5. **Data-Driven**: همه configs از دیتابیس (نه .env)

---

## 📊 Config Categorization from .env.example

### Category 1: MASTER_ONLY (Never Configurable for Tenants)

این configs فقط برای master bot هستند و هرگز به tenant bots داده نمی‌شوند:

```python
MASTER_ONLY_CONFIGS = [
    # RemnaWave API (Master Infrastructure)
    'REMNAWAVE_API_URL',
    'REMNAWAVE_API_KEY',
    'REMNAWAVE_SECRET_KEY',
    'REMNAWAVE_USERNAME',
    'REMNAWAVE_PASSWORD',
    'REMNAWAVE_AUTH_TYPE',
    'REMNAWAVE_USER_DESCRIPTION_TEMPLATE',
    'REMNAWAVE_USER_USERNAME_TEMPLATE',
    'REMNAWAVE_USER_DELETE_MODE',
    'REMNAWAVE_AUTO_SYNC_ENABLED',
    'REMNAWAVE_AUTO_SYNC_TIMES',
    
    # Database (Shared Infrastructure)
    'DATABASE_URL',
    'DATABASE_MODE',
    'POSTGRES_HOST',
    'POSTGRES_PORT',
    'POSTGRES_DB',
    'POSTGRES_USER',
    'POSTGRES_PASSWORD',
    'SQLITE_PATH',
    
    # Redis (Shared Infrastructure)
    'REDIS_URL',
    
    # Master Bot Token
    'BOT_TOKEN',  # Each tenant has its own
    
    # Master Admin IDs
    'ADMIN_IDS',  # Master admin IDs
    
    # Master Notifications (System Level)
    'ADMIN_NOTIFICATIONS_CHAT_ID',  # Master notifications
    'ADMIN_NOTIFICATIONS_TOPIC_ID',
    'ADMIN_REPORTS_CHAT_ID',
    'ADMIN_REPORTS_TOPIC_ID',
    'BACKUP_SEND_CHAT_ID',  # Master backup destination
    'BACKUP_SEND_TOPIC_ID',
    
    # System Level Settings
    'LOCALES_PATH',
    'LOG_FILE',
    'LOG_LEVEL',
    'DEBUG',
    'WEBHOOK_URL',
    'WEBHOOK_PATH',
    'WEBHOOK_SECRET_TOKEN',
    'WEBHOOK_DROP_PENDING_UPDATES',
    'WEBHOOK_MAX_QUEUE_SIZE',
    'WEBHOOK_WORKERS',
    'WEBHOOK_ENQUEUE_TIMEOUT',
    'WEBHOOK_WORKER_SHUTDOWN_TIMEOUT',
    'BOT_RUN_MODE',
    'WEB_API_ENABLED',
    'WEB_API_HOST',
    'WEB_API_PORT',
    'WEB_API_ALLOWED_ORIGINS',
    'WEB_API_DOCS_ENABLED',
    'WEB_API_DEFAULT_TOKEN',
    'WEB_API_DEFAULT_TOKEN_NAME',
    'VERSION_CHECK_ENABLED',
    'VERSION_CHECK_REPO',
    'VERSION_CHECK_INTERVAL_HOURS',
]
```

### Category 2: TENANT_CONFIGURABLE (Can be Set per Tenant)

این configs قابل تنظیم برای هر tenant هستند:

#### 2.1. Basic Settings
```python
BASIC_SETTINGS = [
    'DEFAULT_LANGUAGE',
    'AVAILABLE_LANGUAGES',
    'LANGUAGE_SELECTION_ENABLED',
    'SUPPORT_USERNAME',
    'SUPPORT_MENU_ENABLED',
    'SUPPORT_SYSTEM_MODE',  # tickets, contact, both
    'SUPPORT_TICKET_SLA_ENABLED',
    'SUPPORT_TICKET_SLA_MINUTES',
    'SUPPORT_TICKET_SLA_CHECK_INTERVAL_SECONDS',
    'SUPPORT_TICKET_SLA_REMINDER_COOLDOWN_MINUTES',
    'TZ',  # Timezone
]
```

#### 2.2. Notifications (Tenant-Specific)
```python
TENANT_NOTIFICATIONS = [
    'ADMIN_NOTIFICATIONS_ENABLED',
    'ADMIN_NOTIFICATIONS_CHAT_ID',  # Tenant's admin chat
    'ADMIN_NOTIFICATIONS_TOPIC_ID',
    'ADMIN_NOTIFICATIONS_TICKET_TOPIC_ID',
    'ADMIN_REPORTS_ENABLED',
    'ADMIN_REPORTS_CHAT_ID',  # Tenant's reports chat
    'ADMIN_REPORTS_TOPIC_ID',
    'ADMIN_REPORTS_SEND_TIME',
    'TRIAL_WARNING_HOURS',
    'ENABLE_NOTIFICATIONS',
    'NOTIFICATION_RETRY_ATTEMPTS',
    'MONITORING_LOGS_RETENTION_DAYS',
    'NOTIFICATION_CACHE_HOURS',
]
```

#### 2.3. Channel & Subscription Requirements
```python
CHANNEL_SETTINGS = [
    'CHANNEL_SUB_ID',
    'CHANNEL_IS_REQUIRED_SUB',
    'CHANNEL_LINK',
]
```

#### 2.4. Trial Subscription Settings
```python
TRIAL_SETTINGS = [
    'TRIAL_DURATION_DAYS',
    'TRIAL_TRAFFIC_LIMIT_GB',
    'TRIAL_DEVICE_LIMIT',
    'TRIAL_PAYMENT_ENABLED',
    'TRIAL_ACTIVATION_PRICE',
    'TRIAL_ADD_REMAINING_DAYS_TO_PAID',
    'TRIAL_USER_TAG',
]
```

#### 2.5. Subscription & Pricing Settings
```python
SUBSCRIPTION_SETTINGS = [
    'DEFAULT_DEVICE_LIMIT',
    'MAX_DEVICES_LIMIT',
    'DEFAULT_TRAFFIC_LIMIT_GB',
    'DEFAULT_TRAFFIC_RESET_STRATEGY',  # MONTH, WEEK, etc.
    'RESET_TRAFFIC_ON_PAYMENT',
    'TRAFFIC_SELECTION_MODE',  # selectable, fixed
    'FIXED_TRAFFIC_LIMIT_GB',
    'AVAILABLE_SUBSCRIPTION_PERIODS',
    'AVAILABLE_RENEWAL_PERIODS',
    'BASE_SUBSCRIPTION_PRICE',
    'PRICE_14_DAYS',
    'PRICE_30_DAYS',
    'PRICE_60_DAYS',
    'PRICE_90_DAYS',
    'PRICE_180_DAYS',
    'PRICE_360_DAYS',
    'TRAFFIC_PACKAGES_CONFIG',
    'PRICE_PER_DEVICE',
    'DEVICES_SELECTION_ENABLED',
    'DEVICES_SELECTION_DISABLED_AMOUNT',
    'PAID_SUBSCRIPTION_USER_TAG',
]
```

#### 2.6. Auto-Renewal Settings
```python
AUTOPAY_SETTINGS = [
    'AUTOPAY_WARNING_DAYS',
    'DEFAULT_AUTOPAY_ENABLED',
    'DEFAULT_AUTOPAY_DAYS_BEFORE',
    'MIN_BALANCE_FOR_AUTOPAY_TOMAN',
    'SUBSCRIPTION_RENEWAL_BALANCE_THRESHOLD_TOMAN',
]
```

#### 2.7. Simple Subscription
```python
SIMPLE_SUBSCRIPTION_SETTINGS = [
    'SIMPLE_SUBSCRIPTION_ENABLED',
    'SIMPLE_SUBSCRIPTION_PERIOD_DAYS',
    'SIMPLE_SUBSCRIPTION_DEVICE_LIMIT',
    'SIMPLE_SUBSCRIPTION_TRAFFIC_GB',
    'SIMPLE_SUBSCRIPTION_SQUAD_UUID',
]
```

#### 2.8. Referral Program
```python
REFERRAL_SETTINGS = [
    'REFERRAL_PROGRAM_ENABLED',
    'REFERRAL_MINIMUM_TOPUP_TOMAN',
    'REFERRAL_FIRST_TOPUP_BONUS_TOMAN',
    'REFERRAL_INVITER_BONUS_TOMAN',
    'REFERRAL_COMMISSION_PERCENT',
    'REFERRAL_NOTIFICATIONS_ENABLED',
    'REFERRAL_NOTIFICATION_RETRY_ATTEMPTS',
]
```

#### 2.9. Promo Groups
```python
PROMO_GROUP_SETTINGS = [
    'BASE_PROMO_GROUP_PERIOD_DISCOUNTS_ENABLED',
    'BASE_PROMO_GROUP_PERIOD_DISCOUNTS',
]
```

#### 2.10. Contests
```python
CONTEST_SETTINGS = [
    'CONTESTS_ENABLED',
    'CONTESTS_BUTTON_VISIBLE',
    'REFERRAL_CONTESTS_ENABLED',
]
```

#### 2.11. UI/UX Settings
```python
UI_UX_SETTINGS = [
    'ENABLE_LOGO_MODE',
    'LOGO_FILE',
    'MAIN_MENU_MODE',  # default, text
    'HIDE_SUBSCRIPTION_LINK',
    'CONNECT_BUTTON_MODE',  # guide, miniapp_subscription, etc.
    'MINIAPP_CUSTOM_URL',
    'MINIAPP_STATIC_PATH',
    'MINIAPP_SERVICE_NAME_EN',
    'MINIAPP_SERVICE_NAME_RU',
    'MINIAPP_SERVICE_DESCRIPTION_EN',
    'MINIAPP_SERVICE_DESCRIPTION_RU',
    'SKIP_RULES_ACCEPT',
    'SKIP_REFERRAL_CODE',
    'CONNECT_BUTTON_HAPP_DOWNLOAD_ENABLED',
    'HAPP_DOWNLOAD_LINK_IOS',
    'HAPP_DOWNLOAD_LINK_ANDROID',
    'HAPP_DOWNLOAD_LINK_MACOS',
    'HAPP_DOWNLOAD_LINK_WINDOWS',
    'HAPP_CRYPTOLINK_REDIRECT_TEMPLATE',
]
```

#### 2.12. Server Status
```python
SERVER_STATUS_SETTINGS = [
    'SERVER_STATUS_MODE',  # disabled, external_link, external_link_miniapp, xray
    'SERVER_STATUS_EXTERNAL_URL',
    'SERVER_STATUS_METRICS_URL',
    'SERVER_STATUS_METRICS_USERNAME',
    'SERVER_STATUS_METRICS_PASSWORD',
    'SERVER_STATUS_METRICS_VERIFY_SSL',
    'SERVER_STATUS_REQUEST_TIMEOUT',
    'SERVER_STATUS_ITEMS_PER_PAGE',
]
```

#### 2.13. Maintenance
```python
MAINTENANCE_SETTINGS = [
    'MAINTENANCE_MODE',
    'MAINTENANCE_CHECK_INTERVAL',
    'MAINTENANCE_AUTO_ENABLE',
    'MAINTENANCE_MONITORING_ENABLED',
    'MAINTENANCE_RETRY_ATTEMPTS',
    'MAINTENANCE_MESSAGE',
]
```

#### 2.14. Monitoring
```python
MONITORING_SETTINGS = [
    'MONITORING_INTERVAL',
    'INACTIVE_USER_DELETE_MONTHS',
    'TRAFFIC_MONITORING_ENABLED',
    'TRAFFIC_THRESHOLD_GB_PER_DAY',
    'TRAFFIC_MONITORING_INTERVAL_HOURS',
    'SUSPICIOUS_NOTIFICATIONS_TOPIC_ID',
]
```

#### 2.15. Blacklist
```python
BLACKLIST_SETTINGS = [
    'BLACKLIST_CHECK_ENABLED',
    'BLACKLIST_GITHUB_URL',
    'BLACKLIST_UPDATE_INTERVAL_HOURS',
    'BLACKLIST_IGNORE_ADMINS',
]
```

#### 2.16. Payment Descriptions
```python
PAYMENT_DESCRIPTION_SETTINGS = [
    'PAYMENT_SERVICE_NAME',
    'PAYMENT_BALANCE_DESCRIPTION',
    'PAYMENT_SUBSCRIPTION_DESCRIPTION',
    'PAYMENT_BALANCE_TEMPLATE',
    'PAYMENT_SUBSCRIPTION_TEMPLATE',
]
```

#### 2.17. Payment Gateway Settings (Per Gateway)
```python
# Telegram Stars
TELEGRAM_STARS_SETTINGS = [
    'TELEGRAM_STARS_ENABLED',
    'TELEGRAM_STARS_RATE_RUB',
]

# YooKassa
YOOKASSA_SETTINGS = [
    'YOOKASSA_ENABLED',
    'YOOKASSA_SHOP_ID',
    'YOOKASSA_SECRET_KEY',
    'YOOKASSA_RETURN_URL',
    'YOOKASSA_DEFAULT_RECEIPT_EMAIL',
    'YOOKASSA_VAT_CODE',
    'YOOKASSA_SBP_ENABLED',
    'YOOKASSA_PAYMENT_MODE',
    'YOOKASSA_PAYMENT_SUBJECT',
    'YOOKASSA_MIN_AMOUNT_TOMAN',
    'YOOKASSA_MAX_AMOUNT_TOMAN',
    'YOOKASSA_QUICK_AMOUNT_SELECTION_ENABLED',
]

# CryptoBot
CRYPTOBOT_SETTINGS = [
    'CRYPTOBOT_ENABLED',
    'CRYPTOBOT_API_TOKEN',
    'CRYPTOBOT_WEBHOOK_SECRET',
    'CRYPTOBOT_BASE_URL',
    'CRYPTOBOT_TESTNET',
    'CRYPTOBOT_DEFAULT_ASSET',
    'CRYPTOBOT_ASSETS',
    'CRYPTOBOT_INVOICE_EXPIRES_HOURS',
]

# Heleket
HELEKET_SETTINGS = [
    'HELEKET_ENABLED',
    'HELEKET_MERCHANT_ID',
    'HELEKET_API_KEY',
    'HELEKET_BASE_URL',
    'HELEKET_DEFAULT_CURRENCY',
    'HELEKET_DEFAULT_NETWORK',
    'HELEKET_INVOICE_LIFETIME',
    'HELEKET_MARKUP_PERCENT',
    'HELEKET_CALLBACK_URL',
    'HELEKET_RETURN_URL',
    'HELEKET_SUCCESS_URL',
]

# MulenPay
MULENPAY_SETTINGS = [
    'MULENPAY_ENABLED',
    'MULENPAY_API_KEY',
    'MULENPAY_SECRET_KEY',
    'MULENPAY_SHOP_ID',
    'MULENPAY_BASE_URL',
    'MULENPAY_DESCRIPTION',
    'MULENPAY_LANGUAGE',
    'MULENPAY_VAT_CODE',
    'MULENPAY_PAYMENT_SUBJECT',
    'MULENPAY_PAYMENT_MODE',
    'MULENPAY_MIN_AMOUNT_TOMAN',
    'MULENPAY_MAX_AMOUNT_TOMAN',
]

# PAL24
PAL24_SETTINGS = [
    'PAL24_ENABLED',
    'PAL24_API_TOKEN',
    'PAL24_SHOP_ID',
    'PAL24_SIGNATURE_TOKEN',
    'PAL24_BASE_URL',
    'PAL24_PAYMENT_DESCRIPTION',
    'PAL24_MIN_AMOUNT_TOMAN',
    'PAL24_MAX_AMOUNT_TOMAN',
    'PAL24_REQUEST_TIMEOUT',
    'PAL24_SBP_BUTTON_VISIBLE',
    'PAL24_CARD_BUTTON_VISIBLE',
    'PAL24_SBP_BUTTON_TEXT',
    'PAL24_CARD_BUTTON_TEXT',
]

# Platega
PLATEGA_SETTINGS = [
    'PLATEGA_ENABLED',
    'PLATEGA_MERCHANT_ID',
    'PLATEGA_SECRET',
    'PLATEGA_BASE_URL',
    'PLATEGA_RETURN_URL',
    'PLATEGA_FAILED_URL',
    'PLATEGA_CURRENCY',
    'PLATEGA_ACTIVE_METHODS',
    'PLATEGA_MIN_AMOUNT_TOMAN',
    'PLATEGA_MAX_AMOUNT_TOMAN',
]

# Tribute
TRIBUTE_SETTINGS = [
    'TRIBUTE_ENABLED',
    'TRIBUTE_API_KEY',
    'TRIBUTE_DONATE_LINK',
]

# WATA
WATA_SETTINGS = [
    'WATA_ENABLED',
    'WATA_BASE_URL',
    'WATA_ACCESS_TOKEN',
    'WATA_TERMINAL_PUBLIC_ID',
    'WATA_PAYMENT_DESCRIPTION',
    'WATA_PAYMENT_TYPE',
    'WATA_SUCCESS_REDIRECT_URL',
    'WATA_FAIL_REDIRECT_URL',
    'WATA_LINK_TTL_MINUTES',
]

# NaloGO (Tax Service)
NALOGO_SETTINGS = [
    'NALOGO_ENABLED',
    'NALOGO_INN',
    'NALOGO_PASSWORD',
    'NALOGO_DEVICE_ID',
    'NALOGO_STORAGE_PATH',
]

# Card-to-Card (Managed via tenant_payment_cards table)
# Zarinpal (Stored in bots table)
```

#### 2.18. Payment General Settings
```python
PAYMENT_GENERAL_SETTINGS = [
    'DISABLE_TOPUP_BUTTONS',
    'SUPPORT_TOPUP_ENABLED',
    'PAYMENT_VERIFICATION_AUTO_CHECK_ENABLED',
    'PAYMENT_VERIFICATION_AUTO_CHECK_INTERVAL_MINUTES',
    'AUTO_PURCHASE_AFTER_TOPUP_ENABLED',
]
```

#### 2.19. App Config
```python
APP_CONFIG_SETTINGS = [
    'APP_CONFIG_PATH',
    'ENABLE_DEEP_LINKS',
    'APP_CONFIG_CACHE_TTL',
]
```

#### 2.20. Backup (Settings Only, Not Destination)
```python
BACKUP_SETTINGS = [
    'BACKUP_AUTO_ENABLED',
    'BACKUP_INTERVAL_HOURS',
    'BACKUP_TIME',
    'BACKUP_MAX_KEEP',
    'BACKUP_COMPRESSION',
    'BACKUP_INCLUDE_LOGS',
    'BACKUP_LOCATION',
    # Note: BACKUP_SEND_CHAT_ID is MASTER_ONLY
]
```

---

## 🎨 UX Menu Structure

### Level 1: Main Tenant Bots Menu

```
🤖 Tenant Bots Management

📊 Statistics:
• Total bots: 5
• Active: 4
• Inactive: 1
• Total users: 1,234
• Total revenue: 125,000 Toman

[📋 List Bots] [➕ Create Bot]
[📊 Statistics] [⚙️ Settings]
[🔙 Back]
```

**Callback:** `admin_tenant_bots_menu`  
**Handler:** `app/handlers/admin/tenant_bots.py::show_tenant_bots_menu`  
**Database:** `SELECT COUNT(*) FROM bots WHERE is_master = FALSE`

---

### Level 2A: List Bots (with Pagination)

```
🤖 Tenant Bots List

Page 1 of 2

✅ Bot 1: My VPN Bot (ID: 2)
   • Status: Active
   • Users: 234
   • Revenue: 25,000 Toman
   • Plan: Starter

✅ Bot 2: Another Bot (ID: 3)
   • Status: Active
   • Users: 567
   • Revenue: 50,000 Toman
   • Plan: Growth

[Bot 1] [Bot 2] [Bot 3]
[⬅️ Previous] [Next ➡️]
[🔙 Back]
```

**Callback:** `admin_tenant_bots_list` or `admin_tenant_bots_list:{page}`  
**Handler:** `app/handlers/admin/tenant_bots.py::list_tenant_bots`  
**Database:** 
```sql
SELECT b.*, 
       COUNT(DISTINCT u.id) as user_count,
       COALESCE(SUM(t.amount_kopeks), 0) as revenue
FROM bots b
LEFT JOIN users u ON u.bot_id = b.id
LEFT JOIN transactions t ON t.bot_id = b.id AND t.type = 'deposit'
WHERE b.is_master = FALSE
GROUP BY b.id
ORDER BY b.created_at DESC
LIMIT 5 OFFSET {page * 5}
```

---

### Level 2B: Bot Detail Menu

```
🤖 Bot: My VPN Bot (ID: 2)

📊 Quick Stats:
• Status: ✅ Active
• Users: 234
• Active Subscriptions: 156
• Revenue (Month): 25,000 Toman
• Traffic Sold: 2.5 TB

⚙️ Settings:
• Language: fa
• Support: @support
• Card-to-Card: ✅ Enabled
• Zarinpal: ❌ Disabled

[📊 Statistics] [⚙️ General Settings]
[🎛️ Feature Flags] [💳 Payment Methods]
[📦 Subscription Plans] [🔧 Configuration]
[📈 Analytics] [🧪 Test Bot]
[🗑️ Delete Bot] [🔙 Back]
```

**Callback:** `admin_tenant_bot_detail:{bot_id}`  
**Handler:** `app/handlers/admin/tenant_bots.py::show_bot_detail`  
**Database:**
```sql
-- Bot info
SELECT * FROM bots WHERE id = {bot_id}

-- User count
SELECT COUNT(*) FROM users WHERE bot_id = {bot_id}

-- Active subscriptions
SELECT COUNT(*) FROM subscriptions 
WHERE bot_id = {bot_id} AND status = 'active'

-- Monthly revenue
SELECT COALESCE(SUM(amount_kopeks), 0) 
FROM transactions 
WHERE bot_id = {bot_id} 
  AND type = 'deposit' 
  AND created_at >= date_trunc('month', CURRENT_DATE)
```

---

### Level 3A: Statistics

```
📊 Bot Statistics: My VPN Bot

📈 Overview (Last 30 days):
• New Users: 45
• Active Users: 189
• New Subscriptions: 23
• Revenue: 25,000 Toman
• Traffic Sold: 2.5 TB

💰 Revenue Breakdown:
• Card-to-Card: 15,000 Toman (60%)
• Zarinpal: 10,000 Toman (40%)

👥 User Growth:
• Today: +5
• This Week: +23
• This Month: +45

[📊 Detailed Stats] [📈 Revenue Chart]
[👥 Users List] [📦 Subscriptions]
[🔙 Back]
```

**Callback:** `admin_tenant_bot_stats:{bot_id}`  
**Handler:** `app/handlers/admin/tenant_bots.py::show_bot_statistics`  
**Database:**
```sql
-- New users (30 days)
SELECT COUNT(*) FROM users 
WHERE bot_id = {bot_id} 
  AND created_at >= CURRENT_DATE - INTERVAL '30 days'

-- Active users
SELECT COUNT(DISTINCT user_id) FROM subscriptions
WHERE bot_id = {bot_id} AND status = 'active'

-- Revenue by payment method
SELECT payment_method, SUM(amount_kopeks) as total
FROM transactions
WHERE bot_id = {bot_id} 
  AND type = 'deposit'
  AND created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY payment_method
```

---

### Level 3B: General Settings

```
⚙️ General Settings: My VPN Bot

📝 Basic Information:
• Name: My VPN Bot
• Bot Token: 123456:ABC... (hidden)
• Default Language: fa
• Support Username: @support

🔔 Notifications:
• Admin Chat ID: -1001234567890
• Admin Topic ID: 123
• Notifications: ✅ Enabled

[✏️ Edit Name] [✏️ Edit Language]
[✏️ Edit Support] [✏️ Edit Notifications]
[🔙 Back]
```

**Callback:** `admin_tenant_bot_settings:{bot_id}`  
**Handler:** `app/handlers/admin/tenant_bots.py::show_bot_settings`  
**Database:**
```sql
SELECT * FROM bots WHERE id = {bot_id}
```

**Edit Callbacks:**
- `admin_tenant_bot_edit_name:{bot_id}` → FSM: `AdminStates.editing_tenant_bot_name`
- `admin_tenant_bot_edit_language:{bot_id}` → FSM: `AdminStates.editing_tenant_bot_language`
- `admin_tenant_bot_edit_support:{bot_id}` → FSM: `AdminStates.editing_tenant_bot_support`

---

### Level 3C: Feature Flags Management

```
🎛️ Feature Flags: My VPN Bot

Current Plan: Starter Plan

💳 Payment Gateways:
✅ Card-to-Card
✅ Zarinpal
❌ YooKassa (Growth/Enterprise only)
❌ CryptoBot (Growth/Enterprise only)
❌ Pal24 (Growth/Enterprise only)
❌ MulenPay (Growth/Enterprise only)
❌ Platega (Growth/Enterprise only)
❌ Heleket (Growth/Enterprise only)
❌ Tribute (Growth/Enterprise only)
❌ Telegram Stars

📦 Subscription Features:
✅ Trial Subscription
✅ Auto-Renewal
❌ Simple Purchase (Growth/Enterprise only)

📢 Marketing:
❌ Referral Program (Growth/Enterprise only)
❌ Contests (Growth/Enterprise only)

💬 Support:
✅ Support Tickets
✅ Support Contact

🔗 Integrations:
❌ Mini App (Growth/Enterprise only)
❌ Server Status
✅ Monitoring

[Toggle Feature] [View Plan Limits]
[Override Plan] [🔙 Back]
```

**Callback:** `admin_tenant_bot_features:{bot_id}`  
**Handler:** `app/handlers/admin/tenant_bots.py::show_bot_feature_flags`  
**Database:**
```sql
-- Get feature flags
SELECT * FROM bot_feature_flags 
WHERE bot_id = {bot_id}

-- Get plan features
SELECT pf.* FROM plan_feature_grants pf
JOIN tenant_subscriptions ts ON ts.plan_tier_id = pf.plan_tier_id
WHERE ts.bot_id = {bot_id} AND ts.status = 'active'
```

**Toggle Callback:** `admin_tenant_bot_toggle_feature:{bot_id}:{feature_key}`  
**Handler:** `app/handlers/admin/tenant_bots.py::toggle_feature_flag`  
**Database:**
```sql
-- Toggle feature
INSERT INTO bot_feature_flags (bot_id, feature_key, enabled)
VALUES ({bot_id}, '{feature_key}', {new_value})
ON CONFLICT (bot_id, feature_key) 
DO UPDATE SET enabled = {new_value}, updated_at = NOW()
```

---

### Level 3D: Payment Methods

```
💳 Payment Methods: My VPN Bot

💳 Card-to-Card:
Status: ✅ Enabled
Receipt Topic ID: 123
Active Cards: 2

[Configure Cards] [Toggle]

💳 Zarinpal:
Status: ❌ Disabled
Merchant ID: Not set
Sandbox: ❌

[Configure] [Toggle]

💳 YooKassa:
Status: ❌ Disabled (Plan: Growth+)
Shop ID: Not set

[Configure] [Toggle] [Upgrade Plan]

💳 CryptoBot:
Status: ❌ Disabled (Plan: Growth+)

[Configure] [Toggle] [Upgrade Plan]

[View All Gateways] [🔙 Back]
```

**Callback:** `admin_tenant_bot_payments:{bot_id}`  
**Handler:** `app/handlers/admin/tenant_bots.py::show_bot_payment_methods`  
**Database:**
```sql
-- Card-to-card status (from bots table)
SELECT card_to_card_enabled, card_receipt_topic_id 
FROM bots WHERE id = {bot_id}

-- Payment cards count
SELECT COUNT(*) FROM tenant_payment_cards 
WHERE bot_id = {bot_id} AND is_active = TRUE

-- Zarinpal (from bots table)
SELECT zarinpal_enabled, zarinpal_merchant_id, zarinpal_sandbox
FROM bots WHERE id = {bot_id}

-- Other gateways (from bot_configurations)
SELECT config_key, config_value 
FROM bot_configurations 
WHERE bot_id = {bot_id} 
  AND config_key LIKE '%_ENABLED'
```

**Sub-menu Callbacks:**
- `admin_tenant_bot_cards:{bot_id}` → Payment Cards Management
- `admin_tenant_bot_zarinpal:{bot_id}` → Zarinpal Configuration
- `admin_tenant_bot_yookassa:{bot_id}` → YooKassa Configuration
- etc.

---

### Level 3E: Subscription Plans

```
📦 Subscription Plans: My VPN Bot

Current Plans: 3

┌─────────────────────────────────────┐
│ Basic Plan (ID: 1)                  │
│ • Period: 30 days                   │
│ • Price: 1,000 Toman                │
│ • Traffic: 100 GB                   │
│ • Devices: 1                        │
│ • Status: ✅ Active                 │
│                                     │
│ [✏️ Edit] [👁️ View] [❌ Delete]   │
└─────────────────────────────────────┘

[➕ Create Plan] [📊 Plans Statistics]
[🔙 Back]
```

**Callback:** `admin_tenant_bot_plans:{bot_id}`  
**Handler:** `app/handlers/admin/tenant_bots.py::show_bot_plans`  
**Database:**
```sql
SELECT * FROM bot_plans 
WHERE bot_id = {bot_id}
ORDER BY sort_order, price_kopeks
```

**Sub-menu Callbacks:**
- `admin_tenant_bot_plan_create:{bot_id}` → Create Plan Flow
- `admin_tenant_bot_plan_edit:{plan_id}` → Edit Plan
- `admin_tenant_bot_plan_delete:{plan_id}` → Delete Plan

---

### Level 3F: Configuration (Categorized)

```
🔧 Configuration: My VPN Bot

Select category:

[📝 Basic Settings]
[💬 Support Settings]
[🔔 Notifications]
[📦 Subscription Settings]
[💰 Pricing Settings]
[🎨 UI/UX Settings]
[🔗 Integrations]
[⚙️ Advanced Settings]

[📥 Import from Master] [📤 Export Config]
[🔙 Back]
```

**Callback:** `admin_tenant_bot_config:{bot_id}`  
**Handler:** `app/handlers/admin/tenant_bots.py::show_bot_configuration_menu`

---

#### Level 4: Configuration Categories

##### 4.1. Basic Settings
```
📝 Basic Settings: My VPN Bot

• Default Language: fa
• Available Languages: ru,en,ua,zh
• Language Selection: ✅ Enabled
• Timezone: Europe/Moscow
• Skip Rules Accept: ❌
• Skip Referral Code: ❌

[✏️ Edit Language] [✏️ Edit Timezone]
[Toggle Skip Rules] [Toggle Skip Referral]
[🔙 Back]
```

**Database:**
```sql
SELECT config_key, config_value 
FROM bot_configurations 
WHERE bot_id = {bot_id} 
  AND config_key IN (
    'DEFAULT_LANGUAGE',
    'AVAILABLE_LANGUAGES',
    'LANGUAGE_SELECTION_ENABLED',
    'TZ',
    'SKIP_RULES_ACCEPT',
    'SKIP_REFERRAL_CODE'
  )
```

##### 4.2. Support Settings
```
💬 Support Settings: My VPN Bot

• Support Username: @support
• Support Menu: ✅ Enabled
• Support Mode: both (tickets + contact)
• Ticket SLA: ✅ Enabled
• SLA Minutes: 5
• SLA Check Interval: 60s

[✏️ Edit Username] [✏️ Edit Mode]
[Toggle SLA] [✏️ Edit SLA Settings]
[🔙 Back]
```

**Database:**
```sql
-- From bots table
SELECT support_username FROM bots WHERE id = {bot_id}

-- From bot_configurations
SELECT config_key, config_value 
FROM bot_configurations 
WHERE bot_id = {bot_id} 
  AND config_key LIKE 'SUPPORT_%'
```

##### 4.3. Notifications
```
🔔 Notifications: My VPN Bot

Admin Notifications:
• Enabled: ✅
• Chat ID: -1001234567890
• Topic ID: 123
• Ticket Topic ID: 126

Reports:
• Enabled: ❌
• Chat ID: Not set
• Topic ID: Not set
• Send Time: 10:00

User Notifications:
• Enabled: ✅
• Trial Warning: 2 hours
• Retry Attempts: 3

[✏️ Edit Admin Notifications]
[✏️ Edit Reports]
[✏️ Edit User Notifications]
[🔙 Back]
```

##### 4.4. Subscription Settings
```
📦 Subscription Settings: My VPN Bot

Trial:
• Duration: 3 days
• Traffic Limit: 10 GB
• Device Limit: 1
• Payment Required: ❌
• Activation Price: 0 Toman

Defaults:
• Default Device Limit: 3
• Max Devices: 15
• Default Traffic: 100 GB
• Traffic Reset Strategy: MONTH
• Reset on Payment: ❌

Periods:
• Available: 30,90,180
• Renewal: 30,90,180

[✏️ Edit Trial] [✏️ Edit Defaults]
[✏️ Edit Periods] [🔙 Back]
```

##### 4.5. Pricing Settings
```
💰 Pricing Settings: My VPN Bot

Base Prices:
• 14 days: 7,000 Toman
• 30 days: 1,000 Toman
• 60 days: 25,900 Toman
• 90 days: 36,900 Toman
• 180 days: 69,900 Toman
• 360 days: 109,900 Toman

Traffic Packages:
• 5 GB: 2,000 Toman
• 10 GB: 3,500 Toman
• 25 GB: 7,000 Toman
• 50 GB: 11,000 Toman
• 100 GB: 15,000 Toman
• Unlimited: 20,000 Toman

Devices:
• Price per Device: 10,000 Toman
• Selection Enabled: ✅

[✏️ Edit Period Prices] [✏️ Edit Traffic]
[✏️ Edit Device Price] [🔙 Back]
```

##### 4.6. UI/UX Settings
```
🎨 UI/UX Settings: My VPN Bot

Display:
• Logo Mode: ✅ Enabled
• Logo File: vpn_logo.png
• Main Menu Mode: default
• Hide Subscription Link: ❌

Connect Button:
• Mode: guide
• MiniApp URL: Not set
• Happ Download: ❌

MiniApp:
• Static Path: miniapp
• Service Name (EN): Bedolaga VPN
• Service Name (RU): Bedolaga VPN
• Description (EN): Secure & Fast
• Description (RU): Secure & Fast

[✏️ Edit Display] [✏️ Edit Connect]
[✏️ Edit MiniApp] [🔙 Back]
```

##### 4.7. Integrations
```
🔗 Integrations: My VPN Bot

Server Status:
• Mode: disabled
• External URL: Not set
• Metrics URL: Not set

Monitoring:
• Enabled: ✅
• Interval: 60s
• Traffic Monitoring: ❌
• Inactive Delete: 3 months

Maintenance:
• Mode: ❌
• Auto Enable: ✅
• Message: Default

[✏️ Edit Server Status]
[✏️ Edit Monitoring]
[✏️ Edit Maintenance]
[🔙 Back]
```

##### 4.8. Advanced Settings
```
⚙️ Advanced Settings: My VPN Bot

Auto-Renewal:
• Default Enabled: ❌
• Days Before: 3
• Min Balance: 1,000,000 Toman
• Warning Days: 3,1

Referral:
• Enabled: ❌ (Plan: Growth+)
• Min Topup: 1,000,000 Toman
• First Bonus: 1,000,000 Toman
• Inviter Bonus: 1,000,000 Toman
• Commission: 25%

Promo Groups:
• Period Discounts: ❌
• Discounts: Not set

Contests:
• Enabled: ❌
• Button Visible: ❌

[✏️ Edit Auto-Renewal]
[✏️ Edit Referral]
[✏️ Edit Promo Groups]
[✏️ Edit Contests]
[🔙 Back]
```

---

### Level 3G: Analytics

```
📈 Analytics: My VPN Bot

📊 Performance (Last 30 days):
• User Growth: +45 (23.5%)
• Revenue Growth: +5,000 Toman (25%)
• Conversion Rate: 12.5%
• ARPU: 107 Toman

📈 Trends:
• Users: ↗️ Growing
• Revenue: ↗️ Growing
• Subscriptions: ↗️ Growing

💡 Insights:
• Peak hours: 18:00-22:00
• Most popular plan: Basic (30 days)
• Top payment method: Card-to-Card

[📊 Detailed Analytics] [📈 Charts]
[📋 Export Report] [🔙 Back]
```

**Callback:** `admin_tenant_bot_analytics:{bot_id}`  
**Handler:** `app/handlers/admin/tenant_bots.py::show_bot_analytics`

---

## 🔄 Complete Navigation Flow Diagram

```
Admin Panel
    ↓
🤖 Tenant Bots Menu
    ├── 📋 List Bots
    │   └── Bot Detail (click on bot)
    │
    ├── ➕ Create Bot
    │   └── Registration Flow (FSM)
    │
    ├── 📊 Statistics
    │   └── Overview of all tenants
    │
    └── ⚙️ Settings
        └── Global tenant settings

Bot Detail Menu
    ├── 📊 Statistics
    │   ├── Overview
    │   ├── Detailed Stats
    │   ├── Revenue Chart
    │   └── Users List
    │
    ├── ⚙️ General Settings
    │   ├── Edit Name
    │   ├── Edit Language
    │   ├── Edit Support
    │   └── Edit Notifications
    │
    ├── 🎛️ Feature Flags
    │   ├── Payment Gateways
    │   ├── Subscription Features
    │   ├── Marketing Features
    │   └── Integrations
    │
    ├── 💳 Payment Methods
    │   ├── Card-to-Card
    │   │   ├── Configure Cards
    │   │   └── Toggle
    │   ├── Zarinpal
    │   │   ├── Configure
    │   │   └── Toggle
    │   └── Other Gateways...
    │
    ├── 📦 Subscription Plans
    │   ├── List Plans
    │   ├── Create Plan
    │   ├── Edit Plan
    │   └── Delete Plan
    │
    ├── 🔧 Configuration
    │   ├── 📝 Basic Settings
    │   ├── 💬 Support Settings
    │   ├── 🔔 Notifications
    │   ├── 📦 Subscription Settings
    │   ├── 💰 Pricing Settings
    │   ├── 🎨 UI/UX Settings
    │   ├── 🔗 Integrations
    │   └── ⚙️ Advanced Settings
    │
    ├── 📈 Analytics
    │   ├── Performance
    │   ├── Trends
    │   └── Insights
    │
    ├── 🧪 Test Bot
    │   └── Bot status check
    │
    └── 🗑️ Delete Bot
        └── Confirmation
```

---

## 🗄️ Database Relationships

### Tables Used

1. **bots** - Main bot information
2. **bot_feature_flags** - Feature flags per bot
3. **bot_configurations** - Configurations per bot
4. **bot_plans** - Subscription plans per bot
5. **tenant_payment_cards** - Payment cards per bot
6. **tenant_subscriptions** - Tenant's subscription to platform
7. **plan_feature_grants** - Features granted by plan
8. **users** - Users per bot (filtered by bot_id)
9. **subscriptions** - Subscriptions per bot (filtered by bot_id)
10. **transactions** - Transactions per bot (filtered by bot_id)

### Key Relationships

```
bots (1) ──→ (N) bot_feature_flags
bots (1) ──→ (N) bot_configurations
bots (1) ──→ (N) bot_plans
bots (1) ──→ (N) tenant_payment_cards
bots (1) ──→ (1) tenant_subscriptions ──→ (1) tenant_subscription_plans
tenant_subscription_plans (1) ──→ (N) plan_feature_grants
bots (1) ──→ (N) users
bots (1) ──→ (N) subscriptions
bots (1) ──→ (N) transactions
```

---

## 📝 Callback Data Patterns

### Pattern Structure

```
admin_tenant_bots_{action}                    # Main menu actions
admin_tenant_bot_{action}:{bot_id}            # Bot-specific actions
admin_tenant_bot_{action}:{bot_id}:{param}    # Bot actions with params
admin_tenant_bot_{category}:{bot_id}          # Configuration categories
admin_tenant_bot_edit_{field}:{bot_id}        # Edit specific field
admin_tenant_bot_toggle_{feature}:{bot_id}    # Toggle feature flag
```

### Complete Callback List

| Callback | Handler | Database Query |
|----------|---------|----------------|
| `admin_tenant_bots_menu` | `show_tenant_bots_menu` | `SELECT COUNT(*) FROM bots WHERE is_master = FALSE` |
| `admin_tenant_bots_list` | `list_tenant_bots` | `SELECT * FROM bots WHERE is_master = FALSE` |
| `admin_tenant_bots_list:{page}` | `list_tenant_bots` | Same with pagination |
| `admin_tenant_bots_create` | `start_create_bot` | None (FSM start) |
| `admin_tenant_bot_detail:{bot_id}` | `show_bot_detail` | `SELECT * FROM bots WHERE id = {bot_id}` |
| `admin_tenant_bot_stats:{bot_id}` | `show_bot_statistics` | Multiple queries for stats |
| `admin_tenant_bot_settings:{bot_id}` | `show_bot_settings` | `SELECT * FROM bots WHERE id = {bot_id}` |
| `admin_tenant_bot_features:{bot_id}` | `show_bot_feature_flags` | `SELECT * FROM bot_feature_flags WHERE bot_id = {bot_id}` |
| `admin_tenant_bot_toggle_feature:{bot_id}:{feature}` | `toggle_feature_flag` | `INSERT/UPDATE bot_feature_flags` |
| `admin_tenant_bot_payments:{bot_id}` | `show_bot_payment_methods` | Multiple queries |
| `admin_tenant_bot_cards:{bot_id}` | `show_bot_payment_cards` | `SELECT * FROM tenant_payment_cards WHERE bot_id = {bot_id}` |
| `admin_tenant_bot_plans:{bot_id}` | `show_bot_plans` | `SELECT * FROM bot_plans WHERE bot_id = {bot_id}` |
| `admin_tenant_bot_config:{bot_id}` | `show_bot_configuration_menu` | None (menu only) |
| `admin_tenant_bot_config_basic:{bot_id}` | `show_basic_settings` | `SELECT * FROM bot_configurations WHERE bot_id = {bot_id} AND config_key IN (...)` |
| `admin_tenant_bot_edit_{field}:{bot_id}` | `edit_{field}` | FSM + `UPDATE bots` or `UPDATE bot_configurations` |
| `admin_tenant_bot_analytics:{bot_id}` | `show_bot_analytics` | Complex analytics queries |

---

## 🔐 Master Admin Access to Tenant Bots

### Permission Model

Master admin can:
- ✅ View all tenant bots
- ✅ Edit any tenant bot settings
- ✅ Toggle feature flags (override plan limits)
- ✅ Access tenant bot's admin panel directly
- ✅ Fix issues in tenant bots
- ✅ View tenant statistics
- ✅ Manage tenant subscriptions

### Implementation

```python
# app/utils/permissions.py

def is_master_admin(user: User, bot_id: Optional[int] = None) -> bool:
    """Check if user is master admin"""
    # Check if user is in master bot's ADMIN_IDS
    master_bot = get_master_bot()
    admin_ids = master_bot.admin_ids.split(',')
    return str(user.telegram_id) in admin_ids

@admin_required
async def access_tenant_bot_admin(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    target_bot_id: int
):
    """Master admin accessing tenant bot's admin panel"""
    # Switch context to target bot
    # Show tenant bot's admin menu
    # All actions filtered by target_bot_id
    pass
```

---

## 📊 Statistics & Analytics Queries

### Bot Overview Statistics

```sql
-- User statistics
SELECT 
    COUNT(*) as total_users,
    COUNT(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) as new_users_30d,
    COUNT(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '7 days' THEN 1 END) as new_users_7d
FROM users
WHERE bot_id = {bot_id};

-- Subscription statistics
SELECT 
    COUNT(*) as total_subs,
    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_subs,
    COUNT(CASE WHEN is_trial = TRUE THEN 1 END) as trial_subs,
    COUNT(CASE WHEN is_trial = FALSE THEN 1 END) as paid_subs
FROM subscriptions
WHERE bot_id = {bot_id};

-- Revenue statistics
SELECT 
    COALESCE(SUM(amount_kopeks), 0) as total_revenue,
    COALESCE(SUM(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '30 days' THEN amount_kopeks END), 0) as revenue_30d,
    COALESCE(SUM(CASE WHEN created_at >= CURRENT_DATE - INTERVAL '7 days' THEN amount_kopeks END), 0) as revenue_7d,
    COUNT(*) as transaction_count
FROM transactions
WHERE bot_id = {bot_id} AND type = 'deposit' AND is_completed = TRUE;

-- Traffic statistics
SELECT 
    traffic_consumed_bytes,
    traffic_sold_bytes,
    wallet_balance_toman
FROM bots
WHERE id = {bot_id};
```

---

## 🎯 Implementation Checklist

### Phase 1: Menu Structure
- [ ] Create main tenant bots menu
- [ ] Create bot list with pagination
- [ ] Create bot detail menu
- [ ] Add navigation handlers

### Phase 2: Statistics
- [ ] Bot overview statistics
- [ ] Detailed statistics views
- [ ] Revenue charts
- [ ] User growth charts

### Phase 3: Feature Flags
- [ ] Feature flags menu
- [ ] Toggle functionality
- [ ] Plan-based restrictions
- [ ] Override capability

### Phase 4: Payment Methods
- [ ] Payment methods overview
- [ ] Card-to-card management
- [ ] Gateway configurations
- [ ] Toggle functionality

### Phase 5: Configuration
- [ ] Configuration categories
- [ ] Edit forms for each category
- [ ] Validation
- [ ] Save to database

### Phase 6: Analytics
- [ ] Performance metrics
- [ ] Trend analysis
- [ ] Insights generation
- [ ] Export functionality

---

## 📚 Related Documents

- [Feature Flags & Tenant Management Design](./feature-flags-and-tenant-management-design.md)
- [Technical Challenges Analysis](./technical-challenges-analysis.md)
- [Tenant Registration UX](./tenant-registration-ux-complete.md)

---

**End of Document**
