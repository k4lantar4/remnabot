# Tenant Registration & Personalization UX - Complete Guide

**Version:** 2.0  
**Date:** 2025-12-14  
**Status:** Design Complete  
**Author:** Development Team

---

## 🎯 Overview

این مستند راهنمای کامل UX برای:
1. **Registration Flow**: ثبت‌نام tenant با activation fee
2. **Config Cloning**: Clone کردن قابلیت‌های master bot با فیلتر موارد حساس
3. **Onboarding**: راهنمای شخصی‌سازی برای tenant admin
4. **Personalization Guide**: راهنمای تنظیمات و شخصی‌سازی

---

## 📋 Registration Flow (Complete UX)

### Phase 1: Initial Registration

#### Step 1: Welcome & Plan Selection

```
🤖 Welcome to Tenant Bot Platform!

Create your own VPN bot in minutes!

📦 Available Plans:

┌─────────────────────────────────────┐
│ 🚀 Starter Plan                     │
│ • Activation: 1,000  Toman                │
│ • Monthly: 5,000  Toman                  │
│ • Features:                        │
│   ✓ Card-to-Card                    │
│   ✓ Zarinpal                        │
│   ✓ Trial Subscriptions             │
│   ✓ Auto-renewal                    │
│   ✓ 3 Custom Plans                 │
│                                     │
│ [Select Starter]                   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 📈 Growth Plan                      │
│ • Activation: 2,000  Toman               │
│ • Monthly: 10,000  Toman                 │
│ • Features:                        │
│   ✓ All Starter features           │
│   ✓ YooKassa                        │
│   ✓ CryptoBot                       │
│   ✓ Referral Program                │
│   ✓ Unlimited Plans                 │
│                                     │
│ [Select Growth]                    │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ 🏢 Enterprise Plan                  │
│ • Activation: 5,000  Toman               │
│ • Monthly: 20,000  Toman                  │
│ • Features:                        │
│   ✓ All Growth features             │
│   ✓ All Payment Gateways             │
│   ✓ Advanced Analytics              │
│   ✓ Priority Support                │
│                                     │
│ [Select Enterprise]                │
└─────────────────────────────────────┘

[❌ Cancel]
```

**Handler:** `app/handlers/tenant/registration.py::start_registration`

#### Step 2: Bot Information

```
✅ Plan Selected: Starter Plan
💰 Activation Fee: 1,000  Toman

📝 Step 1/5: Bot Information

Please enter your bot name:
(Maximum 255 characters)

Example: "My VPN Bot"

[❌ Cancel]
```

**State:** `TenantRegistrationStates.waiting_for_bot_name`

```
✅ Bot Name: My VPN Bot

📝 Step 2/5: Telegram Bot Token

Please enter your Telegram Bot Token.

How to get:
1. Open @BotFather in Telegram
2. Send /newbot
3. Follow instructions
4. Copy the token

Token format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz

[❌ Cancel] [ℹ️ Help]
```

**State:** `TenantRegistrationStates.waiting_for_bot_token`

**Validation:**
- Check token format (contains `:`)
- Verify token with Telegram API
- Check if token already exists

#### Step 3: Basic Settings

```
✅ Bot Token Verified

📝 Step 3/5: Basic Settings

Default Language:
[🇮🇷 فارسی] [🇬🇧 English] [🇺🇦 Українська] [🇨🇳 中文]

Support Username (optional):
Enter @username or leave empty

[Skip] [Continue]
```

**State:** `TenantRegistrationStates.waiting_for_language`

#### Step 4: Payment Configuration Preview

```
✅ Basic Settings Saved

📝 Step 4/5: Payment Configuration

Based on your plan (Starter), these payment methods will be available:

✅ Card-to-Card Payments
   • You can add payment cards after registration
   • Receipt topic ID can be configured later

✅ Zarinpal Payments
   • Merchant ID required
   • Can be configured after registration

❌ YooKassa (Growth/Enterprise only)
❌ CryptoBot (Growth/Enterprise only)

[Continue] [❌ Cancel]
```

**State:** `TenantRegistrationStates.reviewing_config`

#### Step 5: Activation Payment

```
💰 Step 5/5: Activation Payment

Plan: Starter Plan
Activation Fee: 1,000  Toman

Select payment method:

[💳 Card-to-Card] [💳 Zarinpal] [💳 YooKassa]

[❌ Cancel]
```

**State:** `TenantRegistrationStates.waiting_for_payment`

**Payment Flow:**
- User selects payment method
- Payment processed (existing payment handlers)
- On success → Create bot

---

### Phase 2: Bot Creation & Config Cloning

#### Config Cloning Strategy

```python
# app/services/config_cloner.py

MASTER_ONLY_CONFIGS = [
    # RemnaWave API (Master only)
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
    
    # Master Bot Token (Each tenant has own)
    'BOT_TOKEN',
    
    # Master-specific settings
    'ADMIN_IDS',  # Master admin IDs
    'ADMIN_NOTIFICATIONS_CHAT_ID',  # Master notifications
    'ADMIN_NOTIFICATIONS_TOPIC_ID',
    'ADMIN_REPORTS_CHAT_ID',
    'ADMIN_REPORTS_TOPIC_ID',
    'BACKUP_SEND_CHAT_ID',  # Master backup channel
    'BACKUP_SEND_TOPIC_ID',
]

CLONABLE_CONFIGS = [
    # UI/UX Settings
    'DEFAULT_LANGUAGE',
    'AVAILABLE_LANGUAGES',
    'LANGUAGE_SELECTION_ENABLED',
    'ENABLE_LOGO_MODE',
    'LOGO_FILE',
    'MAIN_MENU_MODE',
    'HIDE_SUBSCRIPTION_LINK',
    'CONNECT_BUTTON_MODE',
    'MINIAPP_STATIC_PATH',
    'MINIAPP_SERVICE_NAME_EN',
    'MINIAPP_SERVICE_NAME_RU',
    'MINIAPP_SERVICE_DESCRIPTION_EN',
    'MINIAPP_SERVICE_DESCRIPTION_RU',
    'SKIP_RULES_ACCEPT',
    'SKIP_REFERRAL_CODE',
    
    # Subscription Settings (Defaults)
    'TRIAL_DURATION_DAYS',
    'TRIAL_TRAFFIC_LIMIT_GB',
    'TRIAL_DEVICE_LIMIT',
    'TRIAL_ADD_REMAINING_DAYS_TO_PAID',
    'DEFAULT_DEVICE_LIMIT',
    'MAX_DEVICES_LIMIT',
    'DEFAULT_TRAFFIC_LIMIT_GB',
    'DEFAULT_TRAFFIC_RESET_STRATEGY',
    'RESET_TRAFFIC_ON_PAYMENT',
    'TRAFFIC_SELECTION_MODE',
    'FIXED_TRAFFIC_LIMIT_GB',
    'AVAILABLE_SUBSCRIPTION_PERIODS',
    'AVAILABLE_RENEWAL_PERIODS',
    
    # Pricing (Defaults - Tenant can override)
    'BASE_SUBSCRIPTION_PRICE',
    'PRICE_14_DAYS',
    'PRICE_30_DAYS',
    'PRICE_60_DAYS',
    'PRICE_90_DAYS',
    'PRICE_180_DAYS',
    'PRICE_360_DAYS',
    'PRICE_PER_DEVICE',
    'DEVICES_SELECTION_ENABLED',
    'DEVICES_SELECTION_DISABLED_AMOUNT',
    'TRAFFIC_PACKAGES_CONFIG',
    
    # Auto-renewal
    'AUTOPAY_WARNING_DAYS',
    'DEFAULT_AUTOPAY_ENABLED',
    'DEFAULT_AUTOPAY_DAYS_BEFORE',
    'MIN_BALANCE_FOR_AUTOPAY_TOMAN',
    
    # Referral (if enabled in plan)
    'REFERRAL_MINIMUM_TOPUP_TOMAN',
    'REFERRAL_FIRST_TOPUP_BONUS_TOMAN',
    'REFERRAL_INVITER_BONUS_TOMAN',
    'REFERRAL_COMMISSION_PERCENT',
    'REFERRAL_NOTIFICATIONS_ENABLED',
    'REFERRAL_NOTIFICATION_RETRY_ATTEMPTS',
    
    # Notifications
    'TRIAL_WARNING_HOURS',
    'ENABLE_NOTIFICATIONS',
    'NOTIFICATION_RETRY_ATTEMPTS',
    'MONITORING_LOGS_RETENTION_DAYS',
    'NOTIFICATION_CACHE_HOURS',
    
    # Server Status
    'SERVER_STATUS_MODE',
    'SERVER_STATUS_EXTERNAL_URL',
    'SERVER_STATUS_METRICS_URL',
    'SERVER_STATUS_METRICS_USERNAME',
    'SERVER_STATUS_METRICS_PASSWORD',
    'SERVER_STATUS_METRICS_VERIFY_SSL',
    'SERVER_STATUS_REQUEST_TIMEOUT',
    'SERVER_STATUS_ITEMS_PER_PAGE',
    
    # Maintenance
    'MAINTENANCE_MODE',
    'MAINTENANCE_CHECK_INTERVAL',
    'MAINTENANCE_AUTO_ENABLE',
    'MAINTENANCE_MONITORING_ENABLED',
    'MAINTENANCE_RETRY_ATTEMPTS',
    'MAINTENANCE_MESSAGE',
    
    # Payment Descriptions
    'PAYMENT_SERVICE_NAME',
    'PAYMENT_BALANCE_DESCRIPTION',
    'PAYMENT_SUBSCRIPTION_DESCRIPTION',
    'PAYMENT_BALANCE_TEMPLATE',
    'PAYMENT_SUBSCRIPTION_TEMPLATE',
    
    # Monitoring
    'MONITORING_INTERVAL',
    'INACTIVE_USER_DELETE_MONTHS',
    
    # Simple Subscription
    'SIMPLE_SUBSCRIPTION_ENABLED',
    'SIMPLE_SUBSCRIPTION_PERIOD_DAYS',
    'SIMPLE_SUBSCRIPTION_DEVICE_LIMIT',
    'SIMPLE_SUBSCRIPTION_TRAFFIC_GB',
    
    # Promo Groups (Defaults)
    'BASE_PROMO_GROUP_PERIOD_DISCOUNTS_ENABLED',
    'BASE_PROMO_GROUP_PERIOD_DISCOUNTS',
    
    # Support
    'SUPPORT_USERNAME',
    'SUPPORT_MENU_ENABLED',
    'SUPPORT_SYSTEM_MODE',
    'SUPPORT_TICKET_SLA_ENABLED',
    'SUPPORT_TICKET_SLA_MINUTES',
    'SUPPORT_TICKET_SLA_CHECK_INTERVAL_SECONDS',
    'SUPPORT_TICKET_SLA_REMINDER_COOLDOWN_MINUTES',
    
    # Channel
    'CHANNEL_SUB_ID',
    'CHANNEL_LINK',
    'CHANNEL_IS_REQUIRED_SUB',
    
    # Telegram Stars
    'TELEGRAM_STARS_ENABLED',
    'TELEGRAM_STARS_RATE_RUB',
    
    # Payment Gateway Configs (Settings only, not credentials)
    # Credentials are set per tenant
    'YOOKASSA_MIN_AMOUNT_TOMAN',
    'YOOKASSA_MAX_AMOUNT_TOMAN',
    'YOOKASSA_QUICK_AMOUNT_SELECTION_ENABLED',
    'YOOKASSA_VAT_CODE',
    'YOOKASSA_PAYMENT_MODE',
    'YOOKASSA_PAYMENT_SUBJECT',
    'YOOKASSA_SBP_ENABLED',
    'YOOKASSA_DEFAULT_RECEIPT_EMAIL',
    
    'CRYPTOBOT_DEFAULT_ASSET',
    'CRYPTOBOT_ASSETS',
    'CRYPTOBOT_INVOICE_EXPIRES_HOURS',
    'CRYPTOBOT_TESTNET',
    
    'PAL24_MIN_AMOUNT_TOMAN',
    'PAL24_MAX_AMOUNT_TOMAN',
    'PAL24_REQUEST_TIMEOUT',
    'PAL24_SBP_BUTTON_VISIBLE',
    'PAL24_CARD_BUTTON_VISIBLE',
    
    'MULENPAY_MIN_AMOUNT_TOMAN',
    'MULENPAY_MAX_AMOUNT_TOMAN',
    'MULENPAY_VAT_CODE',
    'MULENPAY_PAYMENT_SUBJECT',
    'MULENPAY_PAYMENT_MODE',
    'MULENPAY_LANGUAGE',
    
    'PLATEGA_MIN_AMOUNT_TOMAN',
    'PLATEGA_MAX_AMOUNT_TOMAN',
    'PLATEGA_CURRENCY',
    'PLATEGA_ACTIVE_METHODS',
    
    'HELEKET_DEFAULT_CURRENCY',
    'HELEKET_DEFAULT_NETWORK',
    'HELEKET_INVOICE_LIFETIME',
    'HELEKET_MARKUP_PERCENT',
    
    # Disable topup buttons
    'DISABLE_TOPUP_BUTTONS',
    'SUPPORT_TOPUP_ENABLED',
    
    # Payment verification
    'PAYMENT_VERIFICATION_AUTO_CHECK_ENABLED',
    'PAYMENT_VERIFICATION_AUTO_CHECK_INTERVAL_MINUTES',
    
    # Timezone
    'TZ',
    
    # App config
    'APP_CONFIG_PATH',
    'ENABLE_DEEP_LINKS',
    'APP_CONFIG_CACHE_TTL',
    
    # Backup (Settings only, not destination)
    'BACKUP_AUTO_ENABLED',
    'BACKUP_INTERVAL_HOURS',
    'BACKUP_TIME',
    'BACKUP_MAX_KEEP',
    'BACKUP_COMPRESSION',
    'BACKUP_INCLUDE_LOGS',
    'BACKUP_LOCATION',
    
    # Version check
    'VERSION_CHECK_ENABLED',
    'VERSION_CHECK_REPO',
    'VERSION_CHECK_INTERVAL_HOURS',
    
    # Logging
    'LOG_LEVEL',
    'LOG_FILE',
    
    # Debug
    'DEBUG',
]

async def clone_master_config_to_tenant(
    db: AsyncSession,
    tenant_bot_id: int,
    master_bot_id: int,
    plan_tier_id: int
) -> Dict[str, Any]:
    """Clone master bot configurations to tenant with filtering"""
    from app.database.crud.bot_configuration import (
        get_bot_configurations,
        set_bot_configuration
    )
    from app.database.crud.bot import get_bot_by_id
    from app.services.plan_feature_service import get_plan_feature_grants
    
    # Get master bot
    master_bot = await get_bot_by_id(db, master_bot_id)
    if not master_bot:
        raise ValueError("Master bot not found")
    
    # Get master configurations
    master_configs = await get_bot_configurations(db, master_bot_id)
    
    # Get plan feature grants
    plan_grants = await get_plan_feature_grants(db, plan_tier_id)
    enabled_features = {grant.feature_key for grant in plan_grants if grant.enabled}
    
    cloned_count = 0
    skipped_count = 0
    
    for config in master_configs:
        config_key = config.config_key
        
        # Skip master-only configs
        if config_key in MASTER_ONLY_CONFIGS:
            skipped_count += 1
            continue
        
        # Check if feature is enabled in plan
        # Map config key to feature key
        feature_key = _map_config_to_feature(config_key)
        if feature_key and feature_key not in enabled_features:
            # Feature not enabled in plan, skip
            skipped_count += 1
            continue
        
        # Clone config
        await set_bot_configuration(
            db,
            tenant_bot_id,
            config_key,
            config.config_value
        )
        cloned_count += 1
    
    # Set tenant-specific defaults
    await _set_tenant_defaults(db, tenant_bot_id)
    
    return {
        'cloned': cloned_count,
        'skipped': skipped_count,
        'total': len(master_configs)
    }

def _map_config_to_feature(config_key: str) -> Optional[str]:
    """Map config key to feature key"""
    mapping = {
        'YOOKASSA_ENABLED': 'yookassa',
        'CRYPTOBOT_ENABLED': 'cryptobot',
        'PAL24_ENABLED': 'pal24',
        'MULENPAY_ENABLED': 'mulenpay',
        'PLATEGA_ENABLED': 'platega',
        'HELEKET_ENABLED': 'heleket',
        'TRIBUTE_ENABLED': 'tribute',
        'TELEGRAM_STARS_ENABLED': 'telegram_stars',
        'CARD_TO_CARD_ENABLED': 'card_to_card',
        'ZARINPAL_ENABLED': 'zarinpal',
        'REFERRAL_PROGRAM_ENABLED': 'referral_program',
        'SIMPLE_SUBSCRIPTION_ENABLED': 'simple_purchase',
        'TRIAL_PAYMENT_ENABLED': 'trial_subscription',
    }
    return mapping.get(config_key)

async def _set_tenant_defaults(
    db: AsyncSession,
    tenant_bot_id: int
) -> None:
    """Set tenant-specific default configurations"""
    from app.database.crud.bot_configuration import set_bot_configuration
    
    defaults = {
        # Each tenant has its own admin IDs (empty initially)
        'ADMIN_IDS': '',
        
        # Tenant-specific notification channels (empty initially)
        'ADMIN_NOTIFICATIONS_CHAT_ID': None,
        'ADMIN_NOTIFICATIONS_TOPIC_ID': None,
        'ADMIN_REPORTS_CHAT_ID': None,
        'ADMIN_REPORTS_TOPIC_ID': None,
        
        # Tenant-specific backup destination (empty initially)
        'BACKUP_SEND_CHAT_ID': None,
        'BACKUP_SEND_TOPIC_ID': None,
        
        # Payment gateway credentials (empty - tenant must configure)
        'YOOKASSA_SHOP_ID': '',
        'YOOKASSA_SECRET_KEY': '',
        'CRYPTOBOT_API_TOKEN': '',
        'PAL24_API_TOKEN': '',
        'MULENPAY_API_KEY': '',
        'MULENPAY_SECRET_KEY': '',
        'PLATEGA_MERCHANT_ID': '',
        'PLATEGA_SECRET': '',
        'HELEKET_MERCHANT_ID': '',
        'HELEKET_API_KEY': '',
        'TRIBUTE_API_KEY': '',
        'ZARINPAL_MERCHANT_ID': '',
    }
    
    for key, value in defaults.items():
        await set_bot_configuration(db, tenant_bot_id, key, value)
```

---

### Phase 3: Bot Creation Success

```
🎉 Bot Created Successfully!

✅ Your bot is ready to use!

📋 Bot Information:
• Name: My VPN Bot
• ID: 42
• Status: ✅ Active
• Plan: Starter Plan

🔑 API Token:
<code>tenant_abc123xyz789...</code>

⚠️ IMPORTANT: Save this API token!
It will not be shown again.

📱 Your bot is now running!
Users can start using it immediately.

[📊 View Dashboard] [⚙️ Configure Bot] [📖 Onboarding Guide]
```

**Actions:**
1. Create bot in database
2. Clone master configs (filtered)
3. Apply plan features
4. Generate API token
5. Initialize bot instance
6. Start bot (polling/webhook)

---

## 🎓 Onboarding Guide

### Step 1: Welcome Message

```
👋 Welcome to Your Bot Dashboard!

Your VPN bot is now live! Let's set it up step by step.

📋 Quick Setup Checklist:

□ Configure Payment Methods
□ Create Subscription Plans
□ Set Up Support Channel
□ Configure Notifications
□ Test Bot Functionality

[Start Setup] [Skip for Now]
```

### Step 2: Payment Configuration

```
💳 Step 1: Payment Configuration

Your plan includes these payment methods:

✅ Card-to-Card
   [Configure Cards]

✅ Zarinpal
   [Configure Zarinpal]

❌ YooKassa (Upgrade to Growth)
❌ CryptoBot (Upgrade to Growth)

[Continue] [Skip]
```

**Card-to-Card Setup:**
```
💳 Card-to-Card Payment Setup

Add payment cards for receiving payments:

[➕ Add Card]

Current Cards:
• ****1234 - John Doe (✅ Active)
• ****5678 - Jane Doe (✅ Active)

[Continue] [Skip]
```

**Zarinpal Setup:**
```
💳 Zarinpal Payment Setup

Enter your Zarinpal credentials:

Merchant ID: [_____________]
Sandbox Mode: [☐ Enable]

[Save] [Skip]
```

### Step 3: Subscription Plans

```
📦 Step 2: Create Subscription Plans

Create custom subscription plans for your users:

Current Plans: 0

[➕ Create Plan]

Example Plans:
• Basic: 30 days, 100 GB, 1,000  Toman
• Pro: 90 days, 500 GB, 2,500  Toman
• Premium: 180 days, Unlimited, 4,500  Toman

[Continue] [Skip]
```

**Create Plan Flow:**
```
📦 Create New Plan

Plan Name: [Basic Plan________]

Period (days): [30____]

Price (toman): [100000____]
(Example: 100000 = 1,000  Toman)

Traffic Limit (GB): [100____]
(0 = Unlimited)

Device Limit: [1____]

[Create] [Cancel]
```

### Step 4: Support Configuration

```
💬 Step 3: Support Configuration

Set up support channel for your users:

Support Username: [@support____]

Support Mode:
[☑ Tickets] [☑ Contact] [☐ Both]

[Save] [Skip]
```

### Step 5: Notifications

```
🔔 Step 4: Notification Settings

Configure admin notifications:

Admin Chat ID: [-1001234567890____]
(Get from Telegram)

Topic ID (optional): [123____]

[Save] [Skip]
```

### Step 6: Test Bot

```
🧪 Step 5: Test Your Bot

Test your bot to make sure everything works:

1. Open your bot: @your_bot_username
2. Send /start
3. Check if menu appears
4. Try creating a subscription

[✅ I've Tested] [⏭️ Skip]
```

### Step 7: Onboarding Complete

```
🎉 Setup Complete!

Your bot is ready to use!

📊 Quick Stats:
• Users: 0
• Subscriptions: 0
• Revenue: 0  Toman

[📊 View Dashboard] [⚙️ Settings] [📖 Help]
```

---

## 🎨 Personalization Guide

### Dashboard Overview

```
📊 Your Bot Dashboard

🤖 My VPN Bot (ID: 42)
Plan: Starter Plan | Status: ✅ Active

📈 Statistics (Last 30 days):
• Total Users: 1,234
• Active Subscriptions: 567
• Revenue: 125,000  Toman
• Traffic Sold: 2.5 TB

[📊 Detailed Stats] [👥 Users] [📦 Plans] [💳 Payments]
```

### Personalization Options

#### 1. Subscription Plans Management

```
📦 Subscription Plans

[➕ Create Plan] [📊 View Plans]

Current Plans (3):

┌─────────────────────────────────────┐
│ Basic Plan                           │
│ • Period: 30 days                    │
│ • Price: 1,000  Toman                     │
│ • Traffic: 100 GB                   │
│ • Devices: 1                         │
│ • Status: ✅ Active                  │
│                                     │
│ [✏️ Edit] [👁️ View] [❌ Delete]    │
└─────────────────────────────────────┘

[Back]
```

**Edit Plan:**
```
✏️ Edit Plan: Basic Plan

Plan Name: [Basic Plan________]

Period (days): [30____]

Price (toman): [100000____]

Traffic Limit (GB): [100____]
(0 = Unlimited)

Device Limit: [1____]

Status: [✅ Active] [⏸️ Inactive]

[Save Changes] [Cancel]
```

#### 2. Payment Cards Management

```
💳 Payment Cards

[➕ Add Card]

Active Cards (2):

┌─────────────────────────────────────┐
│ Card ****1234                        │
│ • Holder: John Doe                   │
│ • Strategy: Round-Robin              │
│ • Uses: 45 (✅ 42, ❌ 3)             │
│ • Status: ✅ Active                  │
│                                     │
│ [✏️ Edit] [⏸️ Deactivate]          │
└─────────────────────────────────────┘

[Back]
```

#### 3. Real-time Statistics

```
📊 Real-time Statistics

🕐 Last Updated: 14:30:25

📈 Traffic Consumption:
• Today: 125.5 GB
• This Week: 890.2 GB
• This Month: 2.5 TB

💰 Revenue:
• Today: 5,000  Toman
• This Week: 35,000  Toman
• This Month: 125,000  Toman

👥 Users:
• Total: 1,234
• Active: 567
• New Today: 12

[Refresh] [📊 Detailed Report] [Back]
```

#### 4. Payment Gateway Configuration

```
💳 Payment Gateway Settings

Available Gateways (Based on Plan):

✅ Card-to-Card
   [Configure Cards]

✅ Zarinpal
   Merchant ID: [Set] [Edit]
   Sandbox: [☐ Enabled]

❌ YooKassa (Upgrade to Growth)
❌ CryptoBot (Upgrade to Growth)
❌ Pal24 (Upgrade to Growth)

[Back] [🔄 Upgrade Plan]
```

---

## 🔧 Configuration Best Practices

### 1. Config Cloning Strategy

**Approach: Clone with Filtering**

✅ **Advantages:**
- Minimal code changes
- Reuses existing master bot configs
- Easy to maintain
- Tenant gets proven configurations

✅ **Implementation:**
- Clone all clonable configs from master
- Filter out sensitive/master-only configs
- Apply plan-based feature flags
- Set tenant-specific defaults

### 2. Feature Flag Application

**Process:**
1. Extract feature flags from `.env.example`
2. Map to feature keys
3. Apply based on subscription plan
4. Allow master admin overrides

**Example:**
```python
# Plan: Starter
enabled_features = ['card_to_card', 'zarinpal', 'trial_subscription']

# Plan: Growth
enabled_features = [
    'card_to_card', 'zarinpal', 'yookassa', 'cryptobot',
    'trial_subscription', 'referral_program', 'simple_purchase'
]
```

### 3. Tenant Admin Permissions

**Allowed:**
- ✅ View own statistics
- ✅ Manage subscription plans (bot_plans)
- ✅ Configure payment cards
- ✅ Configure payment gateway settings (not enable/disable)
- ✅ View traffic and revenue
- ✅ Configure support settings

**Restricted:**
- ❌ Toggle feature flags (master admin only)
- ❌ Access RemnaWave API
- ❌ View other tenants' data
- ❌ Change subscription plan tier

---

## 📱 FSM States

```python
# app/states.py

class TenantRegistrationStates(StatesGroup):
    selecting_plan = State()
    waiting_for_bot_name = State()
    waiting_for_bot_token = State()
    waiting_for_language = State()
    waiting_for_support_username = State()
    reviewing_config = State()
    waiting_for_payment = State()
    processing_payment = State()
    completed = State()

class TenantOnboardingStates(StatesGroup):
    welcome = State()
    configuring_payments = State()
    creating_plans = State()
    configuring_support = State()
    configuring_notifications = State()
    testing_bot = State()
    completed = State()
```

---

## 🎯 Success Metrics

### Registration Flow
- ✅ User completes registration in < 5 minutes
- ✅ Payment processed successfully
- ✅ Bot created and initialized
- ✅ Configs cloned correctly
- ✅ Features applied based on plan

### Onboarding
- ✅ User completes setup in < 10 minutes
- ✅ At least one payment method configured
- ✅ At least one subscription plan created
- ✅ Support channel configured
- ✅ Bot tested and working

### Personalization
- ✅ Tenant admin can manage plans easily
- ✅ Real-time statistics visible
- ✅ Payment cards manageable
- ✅ Settings accessible and clear

---

## 🔐 Security Notes

1. **API Token**: Shown only once, hashed in database
2. **Bot Token**: Validated with Telegram API
3. **Payment**: Processed through existing secure payment handlers
4. **Config Cloning**: Sensitive configs never cloned
5. **Permissions**: Strict tenant admin restrictions

---

## 📚 Related Documents

- [Feature Flags & Tenant Management Design](./feature-flags-and-tenant-management-design.md)
- [Multi-Tenant Design Document](./multi-tenant-design-document.md)
- [Tenant Registration UX (Original)](./tenant-registration-ux.md)

---

**End of Document**
