# Tenant Configurations Categorization from .env.example

**Version:** 1.0  
**Date:** 2025-12-14  
**Status:** Complete Analysis

---

## 📋 Executive Summary

این مستند تمام configs موجود در `.env.example` را دسته‌بندی می‌کند و مشخص می‌کند:
- کدام configs فقط برای master bot هستند (MASTER_ONLY)
- کدام configs قابل تنظیم برای tenant bots هستند (TENANT_CONFIGURABLE)
- هر config در کدام دسته قرار می‌گیرد
- نحوه ذخیره‌سازی در دیتابیس

---

## 🚫 MASTER_ONLY Configs (Never for Tenants)

این configs **هرگز** به tenant bots داده نمی‌شوند و فقط برای master bot هستند:

### Infrastructure & System

| Config Key | Type | Description | Storage |
|------------|------|-------------|---------|
| `DATABASE_URL` | String | Database connection URL | Master .env only |
| `DATABASE_MODE` | String | Database mode (auto/postgresql/sqlite) | Master .env only |
| `POSTGRES_HOST` | String | PostgreSQL host | Master .env only |
| `POSTGRES_PORT` | Integer | PostgreSQL port | Master .env only |
| `POSTGRES_DB` | String | Database name | Master .env only |
| `POSTGRES_USER` | String | Database user | Master .env only |
| `POSTGRES_PASSWORD` | String | Database password | Master .env only |
| `SQLITE_PATH` | String | SQLite file path | Master .env only |
| `REDIS_URL` | String | Redis connection URL | Master .env only |
| `LOCALES_PATH` | String | Locales directory path | Master .env only |

### RemnaWave API (Master Infrastructure)

| Config Key | Type | Description | Storage |
|------------|------|-------------|---------|
| `REMNAWAVE_API_URL` | String | RemnaWave panel URL | Master .env only |
| `REMNAWAVE_API_KEY` | String | RemnaWave API key | Master .env only |
| `REMNAWAVE_SECRET_KEY` | String | RemnaWave secret key | Master .env only |
| `REMNAWAVE_USERNAME` | String | RemnaWave username (Basic Auth) | Master .env only |
| `REMNAWAVE_PASSWORD` | String | RemnaWave password (Basic Auth) | Master .env only |
| `REMNAWAVE_AUTH_TYPE` | String | Auth type (api_key/basic_auth) | Master .env only |
| `REMNAWAVE_USER_DESCRIPTION_TEMPLATE` | String | User description template | Master .env only |
| `REMNAWAVE_USER_USERNAME_TEMPLATE` | String | Username template | Master .env only |
| `REMNAWAVE_USER_DELETE_MODE` | String | Delete mode (delete/disable) | Master .env only |
| `REMNAWAVE_AUTO_SYNC_ENABLED` | Boolean | Auto sync enabled | Master .env only |
| `REMNAWAVE_AUTO_SYNC_TIMES` | String | Auto sync times | Master .env only |

### Master Bot Specific

| Config Key | Type | Description | Storage |
|------------|------|-------------|---------|
| `BOT_TOKEN` | String | Telegram bot token | Each tenant has own in `bots.telegram_bot_token` |
| `ADMIN_IDS` | String | Master admin IDs | Master .env only |
| `ADMIN_NOTIFICATIONS_CHAT_ID` | String | Master notifications chat | Master .env only |
| `ADMIN_NOTIFICATIONS_TOPIC_ID` | Integer | Master notifications topic | Master .env only |
| `ADMIN_REPORTS_CHAT_ID` | String | Master reports chat | Master .env only |
| `ADMIN_REPORTS_TOPIC_ID` | Integer | Master reports topic | Master .env only |
| `BACKUP_SEND_CHAT_ID` | String | Master backup destination | Master .env only |
| `BACKUP_SEND_TOPIC_ID` | Integer | Master backup topic | Master .env only |

### System & Development

| Config Key | Type | Description | Storage |
|------------|------|-------------|---------|
| `LOG_LEVEL` | String | Logging level | Master .env only |
| `LOG_FILE` | String | Log file path | Master .env only |
| `DEBUG` | Boolean | Debug mode | Master .env only |
| `WEBHOOK_URL` | String | Webhook URL | Master .env only |
| `WEBHOOK_PATH` | String | Webhook path | Master .env only |
| `WEBHOOK_SECRET_TOKEN` | String | Webhook secret | Master .env only |
| `WEBHOOK_DROP_PENDING_UPDATES` | Boolean | Drop pending updates | Master .env only |
| `WEBHOOK_MAX_QUEUE_SIZE` | Integer | Max queue size | Master .env only |
| `WEBHOOK_WORKERS` | Integer | Webhook workers | Master .env only |
| `WEBHOOK_ENQUEUE_TIMEOUT` | Float | Enqueue timeout | Master .env only |
| `WEBHOOK_WORKER_SHUTDOWN_TIMEOUT` | Float | Shutdown timeout | Master .env only |
| `BOT_RUN_MODE` | String | Bot run mode (polling/webhook/both) | Master .env only |
| `WEB_API_ENABLED` | Boolean | Web API enabled | Master .env only |
| `WEB_API_HOST` | String | Web API host | Master .env only |
| `WEB_API_PORT` | Integer | Web API port | Master .env only |
| `WEB_API_ALLOWED_ORIGINS` | String | Allowed origins | Master .env only |
| `WEB_API_DOCS_ENABLED` | Boolean | API docs enabled | Master .env only |
| `WEB_API_DEFAULT_TOKEN` | String | Default API token | Master .env only |
| `WEB_API_DEFAULT_TOKEN_NAME` | String | Token name | Master .env only |
| `VERSION_CHECK_ENABLED` | Boolean | Version check enabled | Master .env only |
| `VERSION_CHECK_REPO` | String | Version check repo | Master .env only |
| `VERSION_CHECK_INTERVAL_HOURS` | Integer | Check interval | Master .env only |

---

## ✅ TENANT_CONFIGURABLE Configs

این configs قابل تنظیم برای هر tenant bot هستند و در `bot_configurations` table ذخیره می‌شوند.

### Category 1: Basic Settings

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `DEFAULT_LANGUAGE` | String | 'fa' | Default interface language | `bot_configurations.config_value` |
| `AVAILABLE_LANGUAGES` | String | 'ru,en,ua,zh' | Available languages | `bot_configurations.config_value` |
| `LANGUAGE_SELECTION_ENABLED` | Boolean | true | Enable language selection | `bot_configurations.config_value` |
| `TZ` | String | 'Europe/Moscow' | Timezone | `bot_configurations.config_value` |
| `SKIP_RULES_ACCEPT` | Boolean | false | Skip rules acceptance | `bot_configurations.config_value` |
| `SKIP_REFERRAL_CODE` | Boolean | false | Skip referral code | `bot_configurations.config_value` |

**Storage:** `bot_configurations` table  
**Access:** Master admin can edit any tenant, Tenant admin can edit own bot

---

### Category 2: Support Settings

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `SUPPORT_USERNAME` | String | '@support' | Support channel username | `bots.support_username` |
| `SUPPORT_MENU_ENABLED` | Boolean | true | Enable support menu | `bot_configurations.config_value` |
| `SUPPORT_SYSTEM_MODE` | String | 'both' | Support mode (tickets/contact/both) | `bot_configurations.config_value` |
| `SUPPORT_TICKET_SLA_ENABLED` | Boolean | true | Enable SLA for tickets | `bot_configurations.config_value` |
| `SUPPORT_TICKET_SLA_MINUTES` | Integer | 5 | SLA minutes | `bot_configurations.config_value` |
| `SUPPORT_TICKET_SLA_CHECK_INTERVAL_SECONDS` | Integer | 60 | SLA check interval | `bot_configurations.config_value` |
| `SUPPORT_TICKET_SLA_REMINDER_COOLDOWN_MINUTES` | Integer | 15 | Reminder cooldown | `bot_configurations.config_value` |

**Storage:** 
- `SUPPORT_USERNAME` → `bots.support_username`
- Others → `bot_configurations`

---

### Category 3: Notifications (Tenant-Specific)

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `ADMIN_NOTIFICATIONS_ENABLED` | Boolean | false | Enable admin notifications | `bot_configurations.config_value` |
| `ADMIN_NOTIFICATIONS_CHAT_ID` | String | null | Tenant's admin chat ID | `bots.admin_chat_id` |
| `ADMIN_NOTIFICATIONS_TOPIC_ID` | Integer | null | Tenant's admin topic ID | `bots.admin_topic_id` |
| `ADMIN_NOTIFICATIONS_TICKET_TOPIC_ID` | Integer | null | Ticket topic ID | `bot_configurations.config_value` |
| `ADMIN_REPORTS_ENABLED` | Boolean | false | Enable reports | `bot_configurations.config_value` |
| `ADMIN_REPORTS_CHAT_ID` | String | null | Tenant's reports chat | `bot_configurations.config_value` |
| `ADMIN_REPORTS_TOPIC_ID` | Integer | null | Reports topic ID | `bot_configurations.config_value` |
| `ADMIN_REPORTS_SEND_TIME` | String | '10:00' | Reports send time | `bot_configurations.config_value` |
| `TRIAL_WARNING_HOURS` | Integer | 2 | Trial warning hours | `bot_configurations.config_value` |
| `ENABLE_NOTIFICATIONS` | Boolean | true | Enable notifications | `bot_configurations.config_value` |
| `NOTIFICATION_RETRY_ATTEMPTS` | Integer | 3 | Retry attempts | `bot_configurations.config_value` |
| `MONITORING_LOGS_RETENTION_DAYS` | Integer | 30 | Log retention days | `bot_configurations.config_value` |
| `NOTIFICATION_CACHE_HOURS` | Integer | 24 | Notification cache hours | `bot_configurations.config_value` |

**Storage:**
- `ADMIN_NOTIFICATIONS_CHAT_ID` → `bots.admin_chat_id`
- `ADMIN_NOTIFICATIONS_TOPIC_ID` → `bots.admin_topic_id`
- Others → `bot_configurations`

---

### Category 4: Channel & Subscription Requirements

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `CHANNEL_SUB_ID` | String | null | Channel subscription ID | `bot_configurations.config_value` |
| `CHANNEL_IS_REQUIRED_SUB` | Boolean | false | Channel subscription required | `bot_configurations.config_value` |
| `CHANNEL_LINK` | String | null | Channel link | `bot_configurations.config_value` |
| `CHANNEL_DISABLE_TRIAL_ON_UNSUBSCRIBE` | Boolean | true | Disable trial subscriptions when user unsubscribes from channel | `bot_configurations.config_value` |

**Storage:** `bot_configurations`

---

### Category 5: Trial Subscription Settings

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `TRIAL_DURATION_DAYS` | Integer | 3 | Trial duration | `bot_configurations.config_value` |
| `TRIAL_TRAFFIC_LIMIT_GB` | Integer | 10 | Trial traffic limit | `bot_configurations.config_value` |
| `TRIAL_DEVICE_LIMIT` | Integer | 1 | Trial device limit | `bot_configurations.config_value` |
| `TRIAL_PAYMENT_ENABLED` | Boolean | false | Trial payment required | `bot_configurations.config_value` |
| `TRIAL_ACTIVATION_PRICE` | Integer | 0 | Trial activation price | `bot_configurations.config_value` |
| `TRIAL_ADD_REMAINING_DAYS_TO_PAID` | Boolean | false | Add remaining days to paid | `bot_configurations.config_value` |
| `TRIAL_USER_TAG` | String | null | Trial user tag | `bot_configurations.config_value` |

**Storage:** `bot_configurations`  
**Feature Flag:** `trial_subscription` (must be enabled)

---

### Category 6: Subscription & Pricing Settings

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `DEFAULT_DEVICE_LIMIT` | Integer | 3 | Default device limit | `bot_configurations.config_value` |
| `MAX_DEVICES_LIMIT` | Integer | 15 | Maximum devices | `bot_configurations.config_value` |
| `DEFAULT_TRAFFIC_LIMIT_GB` | Integer | 100 | Default traffic limit | `bot_configurations.config_value` |
| `DEFAULT_TRAFFIC_RESET_STRATEGY` | String | 'MONTH' | Traffic reset strategy | `bot_configurations.config_value` |
| `RESET_TRAFFIC_ON_PAYMENT` | Boolean | false | Reset traffic on payment | `bot_configurations.config_value` |
| `TRAFFIC_SELECTION_MODE` | String | 'selectable' | Traffic selection mode | `bot_configurations.config_value` |
| `FIXED_TRAFFIC_LIMIT_GB` | Integer | 100 | Fixed traffic limit | `bot_configurations.config_value` |
| `AVAILABLE_SUBSCRIPTION_PERIODS` | String | '30,90,180' | Available periods | `bot_configurations.config_value` |
| `AVAILABLE_RENEWAL_PERIODS` | String | '30,90,180' | Renewal periods | `bot_configurations.config_value` |
| `BASE_SUBSCRIPTION_PRICE` | Integer | 0 | Base subscription price | `bot_configurations.config_value` |
| `PRICE_14_DAYS` | Integer | 7000 | Price for 14 days | `bot_configurations.config_value` |
| `PRICE_30_DAYS` | Integer | 1000 | Price for 30 days | `bot_configurations.config_value` |
| `PRICE_60_DAYS` | Integer | 25900 | Price for 60 days | `bot_configurations.config_value` |
| `PRICE_90_DAYS` | Integer | 36900 | Price for 90 days | `bot_configurations.config_value` |
| `PRICE_180_DAYS` | Integer | 69900 | Price for 180 days | `bot_configurations.config_value` |
| `PRICE_360_DAYS` | Integer | 109900 | Price for 360 days | `bot_configurations.config_value` |
| `TRAFFIC_PACKAGES_CONFIG` | String | '5:2000:false,...' | Traffic packages | `bot_configurations.config_value` |
| `PRICE_PER_DEVICE` | Integer | 10000 | Price per device | `bot_configurations.config_value` |
| `DEVICES_SELECTION_ENABLED` | Boolean | true | Device selection enabled | `bot_configurations.config_value` |
| `DEVICES_SELECTION_DISABLED_AMOUNT` | Integer | 0 | Disabled amount | `bot_configurations.config_value` |
| `PAID_SUBSCRIPTION_USER_TAG` | String | null | Paid subscription tag | `bot_configurations.config_value` |

**Storage:** `bot_configurations`  
**Note:** These are defaults. Actual prices are in `bot_plans` table.

---

### Category 7: Auto-Renewal Settings

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `AUTOPAY_WARNING_DAYS` | String | '3,1' | Autopay warning days | `bot_configurations.config_value` |
| `DEFAULT_AUTOPAY_ENABLED` | Boolean | false | Default autopay enabled | `bot_configurations.config_value` |
| `DEFAULT_AUTOPAY_DAYS_BEFORE` | Integer | 3 | Days before renewal | `bot_configurations.config_value` |
| `MIN_BALANCE_FOR_AUTOPAY_TOMAN` | Integer | 1000000 | Minimum balance | `bot_configurations.config_value` |
| `SUBSCRIPTION_RENEWAL_BALANCE_THRESHOLD_TOMAN` | Integer | 2000000 | Renewal threshold | `bot_configurations.config_value` |

**Storage:** `bot_configurations`  
**Feature Flag:** `auto_renewal` (must be enabled)

---

### Category 8: Simple Subscription

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `SIMPLE_SUBSCRIPTION_ENABLED` | Boolean | false | Enable simple subscription | `bot_configurations.config_value` |
| `SIMPLE_SUBSCRIPTION_PERIOD_DAYS` | Integer | 30 | Simple subscription period | `bot_configurations.config_value` |
| `SIMPLE_SUBSCRIPTION_DEVICE_LIMIT` | Integer | 1 | Device limit | `bot_configurations.config_value` |
| `SIMPLE_SUBSCRIPTION_TRAFFIC_GB` | Integer | 0 | Traffic limit (0=unlimited) | `bot_configurations.config_value` |
| `SIMPLE_SUBSCRIPTION_SQUAD_UUID` | String | null | Squad UUID | `bot_configurations.config_value` |

**Storage:** `bot_configurations`  
**Feature Flag:** `simple_purchase` (must be enabled)

---

### Category 9: Referral Program

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `REFERRAL_PROGRAM_ENABLED` | Boolean | true | Enable referral program | `bot_feature_flags.enabled` |
| `REFERRAL_MINIMUM_TOPUP_TOMAN` | Integer | 1000000 | Minimum topup | `bot_configurations.config_value` |
| `REFERRAL_FIRST_TOPUP_BONUS_TOMAN` | Integer | 1000000 | First topup bonus | `bot_configurations.config_value` |
| `REFERRAL_INVITER_BONUS_TOMAN` | Integer | 1000000 | Inviter bonus | `bot_configurations.config_value` |
| `REFERRAL_COMMISSION_PERCENT` | Integer | 25 | Commission percent | `bot_configurations.config_value` |
| `REFERRAL_NOTIFICATIONS_ENABLED` | Boolean | true | Referral notifications | `bot_configurations.config_value` |
| `REFERRAL_NOTIFICATION_RETRY_ATTEMPTS` | Integer | 3 | Retry attempts | `bot_configurations.config_value` |

**Storage:**
- `REFERRAL_PROGRAM_ENABLED` → `bot_feature_flags` (feature_key: 'referral_program')
- Others → `bot_configurations`

**Feature Flag:** `referral_program` (must be enabled)

---

### Category 10: Promo Groups

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `BASE_PROMO_GROUP_PERIOD_DISCOUNTS_ENABLED` | Boolean | false | Enable period discounts | `bot_configurations.config_value` |
| `BASE_PROMO_GROUP_PERIOD_DISCOUNTS` | String | '' | Period discounts (60:10,90:20) | `bot_configurations.config_value` |

**Storage:** `bot_configurations`

---

### Category 11: Contests

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `CONTESTS_ENABLED` | Boolean | false | Enable contests | `bot_feature_flags.enabled` |
| `CONTESTS_BUTTON_VISIBLE` | Boolean | false | Contest button visible | `bot_configurations.config_value` |
| `REFERRAL_CONTESTS_ENABLED` | Boolean | false | Referral contests | `bot_configurations.config_value` |

**Storage:**
- `CONTESTS_ENABLED` → `bot_feature_flags` (feature_key: 'polls')
- Others → `bot_configurations`

**Feature Flag:** `polls` (must be enabled)

---

### Category 12: UI/UX Settings

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `ENABLE_LOGO_MODE` | Boolean | true | Enable logo | `bot_configurations.config_value` |
| `LOGO_FILE` | String | 'vpn_logo.png' | Logo file | `bot_configurations.config_value` |
| `MAIN_MENU_MODE` | String | 'default' | Main menu mode | `bot_configurations.config_value` |
| `HIDE_SUBSCRIPTION_LINK` | Boolean | false | Hide subscription link | `bot_configurations.config_value` |
| `CONNECT_BUTTON_MODE` | String | 'guide' | Connect button mode | `bot_configurations.config_value` |
| `MINIAPP_CUSTOM_URL` | String | null | MiniApp custom URL | `bot_configurations.config_value` |
| `MINIAPP_STATIC_PATH` | String | 'miniapp' | MiniApp static path | `bot_configurations.config_value` |
| `MINIAPP_SERVICE_NAME_EN` | String | 'Bedolaga VPN' | Service name (EN) | `bot_configurations.config_value` |
| `MINIAPP_SERVICE_NAME_RU` | String | 'Bedolaga VPN' | Service name (RU) | `bot_configurations.config_value` |
| `MINIAPP_SERVICE_DESCRIPTION_EN` | String | 'Secure & Fast' | Description (EN) | `bot_configurations.config_value` |
| `MINIAPP_SERVICE_DESCRIPTION_RU` | String | 'Secure & Fast' | Description (RU) | `bot_configurations.config_value` |
| `CONNECT_BUTTON_HAPP_DOWNLOAD_ENABLED` | Boolean | false | Happ download enabled | `bot_configurations.config_value` |
| `HAPP_DOWNLOAD_LINK_IOS` | String | null | iOS download link | `bot_configurations.config_value` |
| `HAPP_DOWNLOAD_LINK_ANDROID` | String | null | Android download link | `bot_configurations.config_value` |
| `HAPP_DOWNLOAD_LINK_MACOS` | String | null | macOS download link | `bot_configurations.config_value` |
| `HAPP_DOWNLOAD_LINK_WINDOWS` | String | null | Windows download link | `bot_configurations.config_value` |
| `HAPP_CRYPTOLINK_REDIRECT_TEMPLATE` | String | null | Happ redirect template | `bot_configurations.config_value` |
| `DISABLE_WEB_PAGE_PREVIEW` | Boolean | false | Disable web page preview in bot messages | `bot_configurations.config_value` |
| `ACTIVATE_BUTTON_VISIBLE` | Boolean | false | Show activate button in bot interface | `bot_configurations.config_value` |

**Storage:** `bot_configurations`

---

### Category 13: Server Status

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `SERVER_STATUS_MODE` | String | 'disabled' | Server status mode | `bot_configurations.config_value` |
| `SERVER_STATUS_EXTERNAL_URL` | String | null | External status URL | `bot_configurations.config_value` |
| `SERVER_STATUS_METRICS_URL` | String | null | Metrics URL | `bot_configurations.config_value` |
| `SERVER_STATUS_METRICS_USERNAME` | String | null | Metrics username | `bot_configurations.config_value` |
| `SERVER_STATUS_METRICS_PASSWORD` | String | null | Metrics password | `bot_configurations.config_value` |
| `SERVER_STATUS_METRICS_VERIFY_SSL` | Boolean | true | Verify SSL | `bot_configurations.config_value` |
| `SERVER_STATUS_REQUEST_TIMEOUT` | Integer | 10 | Request timeout | `bot_configurations.config_value` |
| `SERVER_STATUS_ITEMS_PER_PAGE` | Integer | 10 | Items per page | `bot_configurations.config_value` |

**Storage:** `bot_configurations`  
**Feature Flag:** `server_status` (must be enabled for modes other than 'disabled')

---

### Category 14: Maintenance

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `MAINTENANCE_MODE` | Boolean | false | Maintenance mode | `bot_configurations.config_value` |
| `MAINTENANCE_CHECK_INTERVAL` | Integer | 30 | Check interval | `bot_configurations.config_value` |
| `MAINTENANCE_AUTO_ENABLE` | Boolean | true | Auto enable | `bot_configurations.config_value` |
| `MAINTENANCE_MONITORING_ENABLED` | Boolean | true | Monitoring enabled | `bot_configurations.config_value` |
| `MAINTENANCE_RETRY_ATTEMPTS` | Integer | 1 | Retry attempts | `bot_configurations.config_value` |
| `MAINTENANCE_MESSAGE` | String | 'Maintenance...' | Maintenance message | `bot_configurations.config_value` |

**Storage:** `bot_configurations`

---

### Category 15: Monitoring

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `MONITORING_INTERVAL` | Integer | 60 | Monitoring interval | `bot_configurations.config_value` |
| `INACTIVE_USER_DELETE_MONTHS` | Integer | 3 | Inactive user delete | `bot_configurations.config_value` |
| `TRAFFIC_MONITORING_ENABLED` | Boolean | false | Traffic monitoring | `bot_configurations.config_value` |
| `TRAFFIC_THRESHOLD_GB_PER_DAY` | Float | 10.0 | Traffic threshold | `bot_configurations.config_value` |
| `TRAFFIC_MONITORING_INTERVAL_HOURS` | Integer | 24 | Monitoring interval | `bot_configurations.config_value` |
| `SUSPICIOUS_NOTIFICATIONS_TOPIC_ID` | Integer | null | Suspicious notifications topic | `bot_configurations.config_value` |

**Storage:** `bot_configurations`  
**Feature Flag:** `monitoring` (must be enabled)

---

### Category 16: Blacklist

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `BLACKLIST_CHECK_ENABLED` | Boolean | false | Enable blacklist check | `bot_configurations.config_value` |
| `BLACKLIST_GITHUB_URL` | String | null | Blacklist GitHub URL | `bot_configurations.config_value` |
| `BLACKLIST_UPDATE_INTERVAL_HOURS` | Integer | 24 | Update interval | `bot_configurations.config_value` |
| `BLACKLIST_IGNORE_ADMINS` | Boolean | true | Ignore admins | `bot_configurations.config_value` |

**Storage:** `bot_configurations`

---

### Category 17: Payment Descriptions

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `PAYMENT_SERVICE_NAME` | String | 'Internet service' | Payment service name | `bot_configurations.config_value` |
| `PAYMENT_BALANCE_DESCRIPTION` | String | 'Balance top-up' | Balance description | `bot_configurations.config_value` |
| `PAYMENT_SUBSCRIPTION_DESCRIPTION` | String | 'Subscription payment' | Subscription description | `bot_configurations.config_value` |
| `PAYMENT_BALANCE_TEMPLATE` | String | '{service_name} - {description}' | Balance template | `bot_configurations.config_value` |
| `PAYMENT_SUBSCRIPTION_TEMPLATE` | String | '{service_name} - {description}' | Subscription template | `bot_configurations.config_value` |

**Storage:** `bot_configurations`

---

### Category 18: Payment Gateways

#### 18.1. Telegram Stars

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `TELEGRAM_STARS_ENABLED` | Boolean | false | Enable Telegram Stars | `bot_feature_flags.enabled` |
| `TELEGRAM_STARS_RATE_RUB` | Float | 1.79 | Stars to RUB rate | `bot_configurations.config_value` |

**Storage:**
- `TELEGRAM_STARS_ENABLED` → `bot_feature_flags` (feature_key: 'telegram_stars')
- `TELEGRAM_STARS_RATE_RUB` → `bot_configurations`

**Feature Flag:** `telegram_stars`

---

#### 18.2. YooKassa

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `YOOKASSA_ENABLED` | Boolean | false | Enable YooKassa | `bot_feature_flags.enabled` |
| `YOOKASSA_SHOP_ID` | String | null | Shop ID | `bot_configurations.config_value` |
| `YOOKASSA_SECRET_KEY` | String | null | Secret key | `bot_configurations.config_value` |
| `YOOKASSA_RETURN_URL` | String | null | Return URL | `bot_configurations.config_value` |
| `YOOKASSA_DEFAULT_RECEIPT_EMAIL` | String | null | Receipt email | `bot_configurations.config_value` |
| `YOOKASSA_VAT_CODE` | Integer | 1 | VAT code | `bot_configurations.config_value` |
| `YOOKASSA_SBP_ENABLED` | Boolean | false | SBP enabled | `bot_configurations.config_value` |
| `YOOKASSA_PAYMENT_MODE` | String | 'full_payment' | Payment mode | `bot_configurations.config_value` |
| `YOOKASSA_PAYMENT_SUBJECT` | String | 'service' | Payment subject | `bot_configurations.config_value` |
| `YOOKASSA_MIN_AMOUNT_TOMAN` | Integer | 500000 | Min amount | `bot_configurations.config_value` |
| `YOOKASSA_MAX_AMOUNT_TOMAN` | Integer | 100000000 | Max amount | `bot_configurations.config_value` |
| `YOOKASSA_QUICK_AMOUNT_SELECTION_ENABLED` | Boolean | true | Quick amount selection | `bot_configurations.config_value` |

**Storage:**
- `YOOKASSA_ENABLED` → `bot_feature_flags` (feature_key: 'yookassa')
- Others → `bot_configurations`

**Feature Flag:** `yookassa`

---

#### 18.3. CryptoBot

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `CRYPTOBOT_ENABLED` | Boolean | false | Enable CryptoBot | `bot_feature_flags.enabled` |
| `CRYPTOBOT_API_TOKEN` | String | null | API token | `bot_configurations.config_value` |
| `CRYPTOBOT_WEBHOOK_SECRET` | String | null | Webhook secret | `bot_configurations.config_value` |
| `CRYPTOBOT_BASE_URL` | String | 'https://pay.crypt.bot' | Base URL | `bot_configurations.config_value` |
| `CRYPTOBOT_TESTNET` | Boolean | false | Testnet mode | `bot_configurations.config_value` |
| `CRYPTOBOT_DEFAULT_ASSET` | String | 'USDT' | Default asset | `bot_configurations.config_value` |
| `CRYPTOBOT_ASSETS` | String | 'USDT,TON,BTC,ETH' | Available assets | `bot_configurations.config_value` |
| `CRYPTOBOT_INVOICE_EXPIRES_HOURS` | Integer | 24 | Invoice expiry | `bot_configurations.config_value` |

**Storage:**
- `CRYPTOBOT_ENABLED` → `bot_feature_flags` (feature_key: 'cryptobot')
- Others → `bot_configurations`

**Feature Flag:** `cryptobot`

---

#### 18.4. Heleket

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `HELEKET_ENABLED` | Boolean | false | Enable Heleket | `bot_feature_flags.enabled` |
| `HELEKET_MERCHANT_ID` | String | null | Merchant ID | `bot_configurations.config_value` |
| `HELEKET_API_KEY` | String | null | API key | `bot_configurations.config_value` |
| `HELEKET_BASE_URL` | String | 'https://api.heleket.com/v1' | Base URL | `bot_configurations.config_value` |
| `HELEKET_DEFAULT_CURRENCY` | String | 'USDT' | Default currency | `bot_configurations.config_value` |
| `HELEKET_DEFAULT_NETWORK` | String | null | Default network | `bot_configurations.config_value` |
| `HELEKET_INVOICE_LIFETIME` | Integer | 3600 | Invoice lifetime | `bot_configurations.config_value` |
| `HELEKET_MARKUP_PERCENT` | Float | 0.0 | Markup percent | `bot_configurations.config_value` |
| `HELEKET_CALLBACK_URL` | String | null | Callback URL | `bot_configurations.config_value` |
| `HELEKET_RETURN_URL` | String | null | Return URL | `bot_configurations.config_value` |
| `HELEKET_SUCCESS_URL` | String | null | Success URL | `bot_configurations.config_value` |

**Storage:**
- `HELEKET_ENABLED` → `bot_feature_flags` (feature_key: 'heleket')
- Others → `bot_configurations`

**Feature Flag:** `heleket`

---

#### 18.5. MulenPay

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `MULENPAY_ENABLED` | Boolean | false | Enable MulenPay | `bot_feature_flags.enabled` |
| `MULENPAY_API_KEY` | String | null | API key | `bot_configurations.config_value` |
| `MULENPAY_SECRET_KEY` | String | null | Secret key | `bot_configurations.config_value` |
| `MULENPAY_SHOP_ID` | Integer | null | Shop ID | `bot_configurations.config_value` |
| `MULENPAY_BASE_URL` | String | 'https://mulenpay.ru/api' | Base URL | `bot_configurations.config_value` |
| `MULENPAY_DESCRIPTION` | String | 'Balance top-up' | Description | `bot_configurations.config_value` |
| `MULENPAY_LANGUAGE` | String | 'ru' | Language | `bot_configurations.config_value` |
| `MULENPAY_VAT_CODE` | Integer | 0 | VAT code | `bot_configurations.config_value` |
| `MULENPAY_PAYMENT_SUBJECT` | Integer | 4 | Payment subject | `bot_configurations.config_value` |
| `MULENPAY_PAYMENT_MODE` | Integer | 4 | Payment mode | `bot_configurations.config_value` |
| `MULENPAY_MIN_AMOUNT_TOMAN` | Integer | 1000000 | Min amount | `bot_configurations.config_value` |
| `MULENPAY_MAX_AMOUNT_TOMAN` | Integer | 1000000000 | Max amount | `bot_configurations.config_value` |

**Storage:**
- `MULENPAY_ENABLED` → `bot_feature_flags` (feature_key: 'mulenpay')
- Others → `bot_configurations`

**Feature Flag:** `mulenpay`

---

#### 18.6. PAL24

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `PAL24_ENABLED` | Boolean | false | Enable PAL24 | `bot_feature_flags.enabled` |
| `PAL24_API_TOKEN` | String | null | API token | `bot_configurations.config_value` |
| `PAL24_SHOP_ID` | String | null | Shop ID | `bot_configurations.config_value` |
| `PAL24_SIGNATURE_TOKEN` | String | null | Signature token | `bot_configurations.config_value` |
| `PAL24_BASE_URL` | String | 'https://pal24.pro/api/v1/' | Base URL | `bot_configurations.config_value` |
| `PAL24_PAYMENT_DESCRIPTION` | String | 'Balance top-up' | Description | `bot_configurations.config_value` |
| `PAL24_MIN_AMOUNT_TOMAN` | Integer | 1000000 | Min amount | `bot_configurations.config_value` |
| `PAL24_MAX_AMOUNT_TOMAN` | Integer | 10000000000 | Max amount | `bot_configurations.config_value` |
| `PAL24_REQUEST_TIMEOUT` | Integer | 30 | Request timeout | `bot_configurations.config_value` |
| `PAL24_SBP_BUTTON_VISIBLE` | Boolean | true | SBP button visible | `bot_configurations.config_value` |
| `PAL24_CARD_BUTTON_VISIBLE` | Boolean | true | Card button visible | `bot_configurations.config_value` |
| `PAL24_SBP_BUTTON_TEXT` | String | null | SBP button text | `bot_configurations.config_value` |
| `PAL24_CARD_BUTTON_TEXT` | String | null | Card button text | `bot_configurations.config_value` |

**Storage:**
- `PAL24_ENABLED` → `bot_feature_flags` (feature_key: 'pal24')
- Others → `bot_configurations`

**Feature Flag:** `pal24`

---

#### 18.7. Platega

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `PLATEGA_ENABLED` | Boolean | false | Enable Platega | `bot_feature_flags.enabled` |
| `PLATEGA_MERCHANT_ID` | String | null | Merchant ID | `bot_configurations.config_value` |
| `PLATEGA_SECRET` | String | null | Secret | `bot_configurations.config_value` |
| `PLATEGA_BASE_URL` | String | 'https://app.platega.io' | Base URL | `bot_configurations.config_value` |
| `PLATEGA_RETURN_URL` | String | null | Return URL | `bot_configurations.config_value` |
| `PLATEGA_FAILED_URL` | String | null | Failed URL | `bot_configurations.config_value` |
| `PLATEGA_CURRENCY` | String | 'RUB' | Currency | `bot_configurations.config_value` |
| `PLATEGA_ACTIVE_METHODS` | String | '2,10,11,12,13' | Active methods | `bot_configurations.config_value` |
| `PLATEGA_MIN_AMOUNT_TOMAN` | Integer | 1000000 | Min amount | `bot_configurations.config_value` |
| `PLATEGA_MAX_AMOUNT_TOMAN` | Integer | 10000000000 | Max amount | `bot_configurations.config_value` |

**Storage:**
- `PLATEGA_ENABLED` → `bot_feature_flags` (feature_key: 'platega')
- Others → `bot_configurations`

**Feature Flag:** `platega`

---

#### 18.8. Tribute

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `TRIBUTE_ENABLED` | Boolean | false | Enable Tribute | `bot_feature_flags.enabled` |
| `TRIBUTE_API_KEY` | String | null | API key | `bot_configurations.config_value` |
| `TRIBUTE_DONATE_LINK` | String | null | Donate link | `bot_configurations.config_value` |

**Storage:**
- `TRIBUTE_ENABLED` → `bot_feature_flags` (feature_key: 'tribute')
- Others → `bot_configurations`

**Feature Flag:** `tribute`

---

#### 18.9. WATA

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `WATA_ENABLED` | Boolean | false | Enable WATA | `bot_feature_flags.enabled` |
| `WATA_BASE_URL` | String | 'https://api.wata.pro/api/h2h' | Base URL | `bot_configurations.config_value` |
| `WATA_ACCESS_TOKEN` | String | null | Access token | `bot_configurations.config_value` |
| `WATA_TERMINAL_PUBLIC_ID` | String | null | Terminal public ID | `bot_configurations.config_value` |
| `WATA_PAYMENT_DESCRIPTION` | String | 'Balance top-up' | Description | `bot_configurations.config_value` |
| `WATA_PAYMENT_TYPE` | String | 'OneTime' | Payment type | `bot_configurations.config_value` |
| `WATA_SUCCESS_REDIRECT_URL` | String | null | Success redirect | `bot_configurations.config_value` |
| `WATA_FAIL_REDIRECT_URL` | String | null | Fail redirect | `bot_configurations.config_value` |
| `WATA_LINK_TTL_MINUTES` | Integer | null | Link TTL | `bot_configurations.config_value` |

**Storage:**
- `WATA_ENABLED` → `bot_feature_flags` (feature_key: 'wata')
- Others → `bot_configurations`

**Feature Flag:** `wata`

---

#### 18.10. NaloGO (Tax Service)

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `NALOGO_ENABLED` | Boolean | false | Enable NaloGO | `bot_feature_flags.enabled` |
| `NALOGO_RECEIPTS_ENABLED` | Boolean | false | Enable automatic receipt sending to tax service | `bot_configurations.config_value` |
| `NALOGO_INN` | String | null | Tax ID (INN) | `bot_configurations.config_value` |
| `NALOGO_PASSWORD` | String | null | Password | `bot_configurations.config_value` |
| `NALOGO_DEVICE_ID` | String | null | Device ID | `bot_configurations.config_value` |
| `NALOGO_STORAGE_PATH` | String | './nalogo_tokens.json' | Storage path | `bot_configurations.config_value` |

**Storage:**
- `NALOGO_ENABLED` → `bot_feature_flags` (feature_key: 'nalogo')
- Others → `bot_configurations`

**Feature Flag:** `nalogo`

---

#### 18.11. Card-to-Card (Special Case)

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `CARD_TO_CARD_ENABLED` | Boolean | false | Enable card-to-card | `bots.card_to_card_enabled` |
| `CARD_RECEIPT_TOPIC_ID` | Integer | null | Receipt topic ID | `bots.card_receipt_topic_id` |

**Storage:** `bots` table (not `bot_configurations`)  
**Additional:** Cards stored in `tenant_payment_cards` table  
**Feature Flag:** `card_to_card`

---

#### 18.12. Zarinpal (Special Case)

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `ZARINPAL_ENABLED` | Boolean | false | Enable Zarinpal | `bots.zarinpal_enabled` |
| `ZARINPAL_MERCHANT_ID` | String | null | Merchant ID | `bots.zarinpal_merchant_id` |
| `ZARINPAL_SANDBOX` | Boolean | false | Sandbox mode | `bots.zarinpal_sandbox` |

**Storage:** `bots` table (not `bot_configurations`)  
**Feature Flag:** `zarinpal`

---

### Category 19: Payment General Settings

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `DISABLE_TOPUP_BUTTONS` | Boolean | false | Disable topup buttons | `bot_configurations.config_value` |
| `SUPPORT_TOPUP_ENABLED` | Boolean | true | Support topup enabled | `bot_configurations.config_value` |
| `PAYMENT_VERIFICATION_AUTO_CHECK_ENABLED` | Boolean | false | Auto check enabled | `bot_configurations.config_value` |
| `PAYMENT_VERIFICATION_AUTO_CHECK_INTERVAL_MINUTES` | Integer | 10 | Check interval | `bot_configurations.config_value` |
| `AUTO_PURCHASE_AFTER_TOPUP_ENABLED` | Boolean | false | Auto purchase after topup | `bot_configurations.config_value` |

**Storage:** `bot_configurations`

---

### Category 20: App Config

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `APP_CONFIG_PATH` | String | 'app-config.json' | App config path | `bot_configurations.config_value` |
| `ENABLE_DEEP_LINKS` | Boolean | true | Enable deep links | `bot_configurations.config_value` |
| `APP_CONFIG_CACHE_TTL` | Integer | 3600 | Cache TTL | `bot_configurations.config_value` |

**Storage:** `bot_configurations`

---

### Category 21: Backup (Settings Only)

| Config Key | Type | Default | Description | Database Column |
|------------|------|---------|-------------|-----------------|
| `BACKUP_AUTO_ENABLED` | Boolean | true | Auto backup enabled | `bot_configurations.config_value` |
| `BACKUP_INTERVAL_HOURS` | Integer | 24 | Backup interval | `bot_configurations.config_value` |
| `BACKUP_TIME` | String | '03:00' | Backup time | `bot_configurations.config_value` |
| `BACKUP_MAX_KEEP` | Integer | 7 | Max backups to keep | `bot_configurations.config_value` |
| `BACKUP_COMPRESSION` | Boolean | true | Compression enabled | `bot_configurations.config_value` |
| `BACKUP_INCLUDE_LOGS` | Boolean | false | Include logs | `bot_configurations.config_value` |
| `BACKUP_LOCATION` | String | '/app/data/backups' | Backup location | `bot_configurations.config_value` |

**Storage:** `bot_configurations`  
**Note:** `BACKUP_SEND_CHAT_ID` is MASTER_ONLY

---

## 📊 Summary Statistics

### Total Configs Analyzed: 522

- **MASTER_ONLY:** 45 configs (8.6%)
- **TENANT_CONFIGURABLE:** 477 configs (91.4%)

### Storage Distribution

- **bots table:** 8 configs (card_to_card, zarinpal, basic info)
- **bot_feature_flags:** 15 feature flags (enabled/disabled)
- **bot_configurations:** 450+ configs (all other settings)
- **tenant_payment_cards:** Payment cards (separate table)
- **bot_plans:** Subscription plans (separate table)

---

## 🔄 Migration Strategy

### Step 1: Extract from .env.example

```python
# app/services/config_extractor.py

def extract_all_configs_from_env_example() -> Dict[str, Any]:
    """Extract all configs from .env.example"""
    # Parse .env.example
    # Return categorized configs
    pass
```

### Step 2: Categorize

```python
def categorize_configs(configs: Dict) -> Dict:
    """Categorize configs into MASTER_ONLY and TENANT_CONFIGURABLE"""
    master_only = []
    tenant_configurable = []
    
    for key, value in configs.items():
        if key in MASTER_ONLY_CONFIGS:
            master_only.append(key)
        else:
            tenant_configurable.append(key)
    
    return {
        'master_only': master_only,
        'tenant_configurable': tenant_configurable
    }
```

### Step 3: Store in Database

```python
async def store_tenant_configs(
    db: AsyncSession,
    bot_id: int,
    configs: Dict[str, Any]
) -> None:
    """Store tenant configs in database"""
    for key, value in configs.items():
        if key in BOTS_TABLE_CONFIGS:
            # Update bots table
            await update_bot(db, bot_id, **{key.lower(): value})
        elif key.endswith('_ENABLED'):
            # Store as feature flag
            feature_key = _map_config_to_feature(key)
            await set_feature_flag(db, bot_id, feature_key, value)
        else:
            # Store in bot_configurations
            await set_bot_configuration(db, bot_id, key, value)
```

---

## 🎯 Feature Flag Mapping

| Config Key | Feature Flag Key | Category |
|------------|-----------------|----------|
| `TELEGRAM_STARS_ENABLED` | `telegram_stars` | Payment Gateway |
| `YOOKASSA_ENABLED` | `yookassa` | Payment Gateway |
| `CRYPTOBOT_ENABLED` | `cryptobot` | Payment Gateway |
| `PAL24_ENABLED` | `pal24` | Payment Gateway |
| `MULENPAY_ENABLED` | `mulenpay` | Payment Gateway |
| `PLATEGA_ENABLED` | `platega` | Payment Gateway |
| `HELEKET_ENABLED` | `heleket` | Payment Gateway |
| `TRIBUTE_ENABLED` | `tribute` | Payment Gateway |
| `WATA_ENABLED` | `wata` | Payment Gateway |
| `NALOGO_ENABLED` | `nalogo` | Payment Gateway |
| `CARD_TO_CARD_ENABLED` | `card_to_card` | Payment Method |
| `ZARINPAL_ENABLED` | `zarinpal` | Payment Method |
| `TRIAL_PAYMENT_ENABLED` | `trial_subscription` | Subscription Feature |
| `SIMPLE_SUBSCRIPTION_ENABLED` | `simple_purchase` | Subscription Feature |
| `REFERRAL_PROGRAM_ENABLED` | `referral_program` | Marketing |
| `CONTESTS_ENABLED` | `polls` | Marketing |
| `SUPPORT_SYSTEM_MODE` | `support_tickets` | Support |
| `SERVER_STATUS_MODE` | `server_status` | Integration |
| `TRAFFIC_MONITORING_ENABLED` | `monitoring` | Integration |

---

## 🔄 راهکار مدیریت Configs جدید در آینده

### فرآیند پیشنهادی برای اضافه کردن Config جدید

#### Step 1: اضافه کردن به `.env.example`
```bash
# اضافه کردن config جدید به .env.example
NEW_CONFIG_KEY=default_value
```

#### Step 2: دسته‌بندی خودکار
```python
# app/services/config_sync_service.py

class ConfigSyncService:
    """
    Service برای همگام‌سازی configs بین .env.example و database
    """
    
    # لیست configs که باید MASTER_ONLY باشند
    MASTER_ONLY_PATTERNS = [
        'REMNAWAVE_',
        'DATABASE_',
        'POSTGRES_',
        'SQLITE_',
        'REDIS_',
        'BOT_TOKEN',
        'ADMIN_IDS',
        'BACKUP_SEND_',
        'LOG_',
        'WEBHOOK_',
        'WEB_API_',
        'VERSION_CHECK_',
    ]
    
    async def detect_new_configs(
        self, 
        db: AsyncSession,
        master_bot_id: int
    ) -> List[Dict[str, Any]]:
        """
        تشخیص configs جدید در .env.example که در database نیستند
        """
        # 1. Parse .env.example
        env_configs = self._parse_env_example()
        
        # 2. Get existing configs from database
        existing_configs = await self._get_existing_configs(db, master_bot_id)
        
        # 3. Find new configs
        new_configs = []
        for key, value in env_configs.items():
            if key not in existing_configs:
                # Categorize automatically
                category = self._categorize_config(key)
                is_master_only = self._is_master_only(key)
                
                new_configs.append({
                    'key': key,
                    'default_value': value,
                    'category': category,
                    'is_master_only': is_master_only,
                    'storage': self._determine_storage(key)
                })
        
        return new_configs
    
    def _is_master_only(self, config_key: str) -> bool:
        """بررسی اینکه config باید MASTER_ONLY باشد"""
        # Check against patterns
        for pattern in self.MASTER_ONLY_PATTERNS:
            if config_key.startswith(pattern):
                return True
        
        # Check against explicit list
        return config_key in MASTER_ONLY_CONFIGS
    
    def _categorize_config(self, config_key: str) -> str:
        """دسته‌بندی خودکار config"""
        category_map = {
            'SUPPORT_': 'support',
            'NOTIFICATION': 'notifications',
            'CHANNEL_': 'channel',
            'TRIAL_': 'trial',
            'PRICE_': 'pricing',
            'TRAFFIC_': 'subscription',
            'DEVICE_': 'subscription',
            'AUTOPAY_': 'autopay',
            'REFERRAL_': 'referral',
            'PROMO_': 'promo',
            'CONTEST_': 'contests',
            'LOGO_': 'ui_ux',
            'MAIN_MENU_': 'ui_ux',
            'CONNECT_BUTTON_': 'ui_ux',
            'MINIAPP_': 'ui_ux',
            'HAPP_': 'ui_ux',
            'SERVER_STATUS_': 'integrations',
            'MONITORING_': 'integrations',
            'MAINTENANCE_': 'integrations',
            'BLACKLIST_': 'integrations',
            'PAYMENT_': 'payment_descriptions',
            'YOOKASSA_': 'payment_gateway',
            'CRYPTOBOT_': 'payment_gateway',
            'PAL24_': 'payment_gateway',
            'MULENPAY_': 'payment_gateway',
            'PLATEGA_': 'payment_gateway',
            'HELEKET_': 'payment_gateway',
            'TRIBUTE_': 'payment_gateway',
            'WATA_': 'payment_gateway',
            'NALOGO_': 'payment_gateway',
            'TELEGRAM_STARS_': 'payment_gateway',
            'BACKUP_': 'backup',
            'APP_CONFIG_': 'app_config',
        }
        
        for prefix, category in category_map.items():
            if config_key.startswith(prefix):
                return category
        
        return 'basic'  # Default category
    
    def _determine_storage(self, config_key: str) -> str:
        """تعیین محل ذخیره‌سازی config"""
        # Feature flags (ends with _ENABLED)
        if config_key.endswith('_ENABLED'):
            feature_key = self._map_config_to_feature(config_key)
            if feature_key:
                return 'bot_feature_flags'
        
        # Bots table (special cases)
        bots_table_configs = [
            'SUPPORT_USERNAME',
            'ADMIN_NOTIFICATIONS_CHAT_ID',
            'ADMIN_NOTIFICATIONS_TOPIC_ID',
        ]
        if config_key in bots_table_configs:
            return 'bots'
        
        # Default: bot_configurations
        return 'bot_configurations'
    
    async def sync_new_configs_to_tenants(
        self,
        db: AsyncSession,
        new_configs: List[Dict],
        tenant_bot_ids: List[int]
    ):
        """
        اضافه کردن configs جدید به tenant bots
        """
        for config in new_configs:
            if config['is_master_only']:
                continue  # Skip master-only configs
            
            for bot_id in tenant_bot_ids:
                # Clone from master or use default
                await self._set_tenant_config(
                    db, 
                    bot_id, 
                    config['key'], 
                    config['default_value'],
                    config['storage']
                )
```

#### Step 3: به‌روزرسانی مستندات
```markdown
# به tenant-configs-categorization.md اضافه کن:
- Config جدید را در category مناسب اضافه کن
- Storage location را مشخص کن
- Feature flag mapping (اگر نیاز باشد)
```

#### Step 4: همگام‌سازی با Tenant Bots
```python
# اجرای sync برای tenant bots موجود
await config_sync_service.sync_new_configs_to_tenants(
    db, 
    new_configs, 
    tenant_bot_ids
)
```

### دستورالعمل برای Developer

**وقتی config جدید اضافه می‌کنی:**

1. ✅ اضافه کردن به `.env.example`
2. ✅ اجرای `detect_new_configs()` برای شناسایی
3. ✅ بررسی دسته‌بندی خودکار
4. ✅ تایید دستی در صورت نیاز
5. ✅ اضافه کردن به `tenant-configs-categorization.md`
6. ✅ همگام‌سازی با tenant bots موجود
7. ✅ تست در محیط dev

### مثال: اضافه کردن Config جدید

```python
# مثال: اضافه کردن DISABLE_WEB_PAGE_PREVIEW

# 1. در .env.example اضافه شد:
DISABLE_WEB_PAGE_PREVIEW=false

# 2. دسته‌بندی خودکار:
# - Category: ui_ux (از prefix DISABLE_ نمی‌توان تشخیص داد، نیاز به تایید دستی)
# - Storage: bot_configurations
# - MASTER_ONLY: False

# 3. به مستندات اضافه شد:
# Category 12: UI/UX Settings
# | DISABLE_WEB_PAGE_PREVIEW | Boolean | false | ... | bot_configurations |

# 4. Sync به tenant bots:
await sync_config_to_all_tenants('DISABLE_WEB_PAGE_PREVIEW', False)
```

---

## ⚠️ نکات مهم

### 1. Isolation
- **همیشه** configs tenant bots از master جدا هستند
- هر tenant می‌تواند configs خودش را تغییر دهد
- Master admin می‌تواند configs هر tenant را override کند

### 2. Feature Flags
- Feature flags در `bot_feature_flags` ذخیره می‌شوند
- Configs مربوط به feature در `bot_configurations` ذخیره می‌شوند
- مثال: `YOOKASSA_ENABLED` → feature flag, `YOOKASSA_SHOP_ID` → config

### 3. Master-Only Configs
- این configs **هرگز** به tenant bots داده نمی‌شوند
- فقط در `.env` master bot هستند
- شامل: RemnaWave API, Database, Redis, Master admin IDs

### 4. Config Cloning
- هنگام ایجاد tenant bot جدید، configs از master clone می‌شوند
- MASTER_ONLY configs فیلتر می‌شوند
- Tenant می‌تواند بعداً configs را تغییر دهد

---

**End of Document**
