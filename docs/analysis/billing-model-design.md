# طراحی مدل بیلینگ Multi-Tenant

**تاریخ:** 2025-12-15  
**نسخه:** 1.0  
**وضعیت:** تایید شده

---

## 📋 خلاصه تصمیمات

| موضوع | تصمیم | توضیح |
|-------|-------|-------|
| Servers/Squads | **Shared** | متعلق به Master، مشترک بین همه Tenants |
| Pricing | **Per-Tenant** | هر Tenant قیمت‌های خودش را تعیین می‌کند |
| Plans | **Per-Tenant** | پلن‌های دلخواه برای هر Tenant |
| PromoGroups | **Per-Tenant** | هر Tenant گروه‌های تخفیف خودش را دارد |
| Campaigns | **Per-Tenant** | هر Tenant کمپین‌های خودش را دارد |
| Billing | **Traffic-based** | کسر از کیف پول به ازای مصرف/فروش ترافیک |

---

## 💰 مدل بیلینگ

### نحوه کار

```
┌─────────────────────────────────────────────────────────────────┐
│                        Master Bot                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Shared Servers                        │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │    │
│  │  │ Server 1 │  │ Server 2 │  │ Server N │              │    │
│  │  └──────────┘  └──────────┘  └──────────┘              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐              │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌────────────┐       ┌────────────┐       ┌────────────┐       │
│  │  Tenant A  │       │  Tenant B  │       │  Tenant C  │       │
│  │ Wallet: 50K│       │ Wallet: 30K│       │ Wallet: 100K│      │
│  │ Users: 500 │       │ Users: 200 │       │ Users: 1000│       │
│  └────────────┘       └────────────┘       └────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### روش‌های کسر از کیف پول

#### روش 1: کسر به ازای فروش اشتراک (Subscription Sale)
```
Tenant فروش اشتراک → کسر هزینه از کیف پول Tenant

مثال:
- تعرفه Master: 1000 تومان / GB
- Tenant فروخت: 30 روز × 50GB
- کسر از کیف پول Tenant: 50 × 1000 = 50,000 تومان
- Tenant می‌فروشد به هر قیمتی (مثلاً 100,000 تومان) → سود 50,000
```

#### روش 2: کسر به ازای مصرف ترافیک (Traffic Consumption)
```
User مصرف ترافیک → کسر از کیف پول Tenant

مثال:
- تعرفه Master: 1000 تومان / GB
- User مصرف کرد: 10GB
- کسر از کیف پول Tenant: 10 × 1000 = 10,000 تومان
```

#### روش 3: ترکیبی (Hybrid)
```
- پیش‌پرداخت هنگام فروش (مثلاً 50%)
- کسر مابقی به ازای مصرف واقعی
```

---

## 🗄️ Data Models برای Billing

### جدول `bots` (موجود - نیاز به بهبود)

```sql
ALTER TABLE bots ADD COLUMN IF NOT EXISTS billing_model VARCHAR(20) DEFAULT 'traffic_consumption';
-- Values: 'subscription_sale', 'traffic_consumption', 'hybrid'

ALTER TABLE bots ADD COLUMN IF NOT EXISTS traffic_rate_kopeks INTEGER DEFAULT 10000;
-- نرخ هر GB به کوپک (10000 = 100 تومان)

ALTER TABLE bots ADD COLUMN IF NOT EXISTS min_wallet_balance_kopeks BIGINT DEFAULT 0;
-- حداقل موجودی برای فعال ماندن

ALTER TABLE bots ADD COLUMN IF NOT EXISTS auto_suspend_on_low_balance BOOLEAN DEFAULT true;
-- غیرفعال‌سازی خودکار در صورت کم بودن موجودی
```

### جدول جدید: `tenant_wallet_transactions`

```sql
CREATE TABLE tenant_wallet_transactions (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    
    -- نوع تراکنش
    transaction_type VARCHAR(30) NOT NULL,
    -- Values: 'topup', 'traffic_deduction', 'subscription_sale_deduction', 
    --         'refund', 'adjustment', 'bonus'
    
    -- مقادیر
    amount_kopeks BIGINT NOT NULL,  -- مثبت یا منفی
    balance_before_kopeks BIGINT NOT NULL,
    balance_after_kopeks BIGINT NOT NULL,
    
    -- اطلاعات مرتبط
    reference_type VARCHAR(30),  -- 'subscription', 'user_traffic', 'admin_topup'
    reference_id INTEGER,  -- ID مرتبط (subscription_id, user_id, ...)
    
    -- جزئیات
    traffic_gb DECIMAL(10, 3),  -- مقدار ترافیک (اگر traffic-based باشد)
    description TEXT,
    
    -- ایجاد کننده
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    
    -- Indexes
    INDEX idx_twt_bot_id (bot_id),
    INDEX idx_twt_created_at (created_at),
    INDEX idx_twt_type (transaction_type)
);
```

### جدول جدید: `tenant_traffic_usage`

```sql
CREATE TABLE tenant_traffic_usage (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id INTEGER REFERENCES subscriptions(id) ON DELETE SET NULL,
    
    -- مصرف
    traffic_used_bytes BIGINT NOT NULL DEFAULT 0,
    traffic_sold_bytes BIGINT NOT NULL DEFAULT 0,  -- ترافیک فروخته شده در این دوره
    
    -- دوره
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    
    -- وضعیت بیلینگ
    billed BOOLEAN DEFAULT false,
    billed_at TIMESTAMP,
    wallet_transaction_id INTEGER REFERENCES tenant_wallet_transactions(id),
    
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    
    -- Indexes
    INDEX idx_ttu_bot_id (bot_id),
    INDEX idx_ttu_user_id (user_id),
    INDEX idx_ttu_period (period_start, period_end),
    INDEX idx_ttu_billed (billed)
);
```

---

## 🔄 Flow های Billing

### Flow 1: شارژ کیف پول Tenant

```
Admin Master → Tenant Management → Select Tenant → Add Balance
    │
    ▼
[Enter Amount]
    │
    ▼
[Create tenant_wallet_transaction]
    transaction_type = 'topup'
    amount_kopeks = +X
    │
    ▼
[Update bot.wallet_balance_kopeks]
    │
    ▼
[Notify Tenant Admin] (optional)
```

### Flow 2: کسر به ازای فروش اشتراک

```
User خرید اشتراک در Tenant Bot
    │
    ▼
[Calculate Cost]
    traffic_gb = plan.traffic_limit_gb
    cost = traffic_gb × bot.traffic_rate_kopeks
    │
    ▼
[Check Wallet Balance]
    if bot.wallet_balance_kopeks < cost:
        → Error: "موجودی کیف پول Tenant کافی نیست"
    │
    ▼
[Create tenant_wallet_transaction]
    transaction_type = 'subscription_sale_deduction'
    amount_kopeks = -cost
    reference_type = 'subscription'
    reference_id = new_subscription.id
    │
    ▼
[Update bot.wallet_balance_kopeks]
    │
    ▼
[Update bot.traffic_sold_bytes]
    += traffic_gb × 1024³
    │
    ▼
[Create Subscription]
```

### Flow 3: کسر به ازای مصرف ترافیک (Background Job)

```
[Cron Job - Every Hour/Day]
    │
    ▼
[For each active Tenant]
    │
    ▼
[Get Traffic Usage from Remnawave API]
    per user, per subscription
    │
    ▼
[Calculate Unbilled Traffic]
    new_usage = current_usage - last_billed_usage
    │
    ▼
[Calculate Cost]
    cost = (new_usage_bytes / 1024³) × bot.traffic_rate_kopeks
    │
    ▼
[Create tenant_wallet_transaction]
    transaction_type = 'traffic_deduction'
    │
    ▼
[Update tenant_traffic_usage]
    billed = true
    │
    ▼
[Update bot.wallet_balance_kopeks]
    │
    ▼
[Update bot.traffic_consumed_bytes]
    │
    ▼
[Check Low Balance]
    if wallet_balance < min_wallet_balance:
        → Send Warning to Tenant Admin
        → If auto_suspend: Deactivate Tenant Bot
```

---

## 🎛️ تنظیمات Master Bot برای Billing

### Bot Configuration Keys

```python
# Master Bot Configurations (در bot_configurations)
BILLING_CONFIGS = {
    "default_traffic_rate_kopeks": 10000,      # نرخ پیش‌فرض هر GB
    "min_wallet_for_new_tenant": 100000,       # حداقل شارژ اولیه
    "low_balance_warning_threshold": 50000,    # آستانه هشدار کم بودن موجودی
    "billing_cycle_hours": 24,                 # دوره بیلینگ (ساعت)
    "allow_negative_balance": False,           # اجازه موجودی منفی
    "auto_suspend_threshold": 0,               # آستانه تعلیق خودکار
}
```

### Feature Flags برای Billing

```python
# Feature Flags (در bot_feature_flags)
BILLING_FEATURES = {
    "billing_subscription_sale": True,    # کسر هنگام فروش
    "billing_traffic_consumption": True,  # کسر به ازای مصرف
    "billing_auto_topup": False,          # شارژ خودکار (آینده)
    "billing_notifications": True,        # اعلان‌های بیلینگ
}
```

---

## 👨‍💼 Admin Panel برای Billing

### Master Bot - منوی Billing

```
[Admin Panel]
└── 💰 Billing Management
    ├── 📊 Overview
    │   ├── Total Wallet Balances
    │   ├── Today's Revenue
    │   ├── This Month's Revenue
    │   └── Active Tenants
    │
    ├── 🏦 Tenant Wallets
    │   ├── List All Tenants
    │   │   └── [Tenant] → Balance, Last Topup, Usage
    │   ├── Add Balance
    │   └── View Transactions
    │
    ├── 📈 Traffic Reports
    │   ├── By Tenant
    │   ├── By Period
    │   └── Export
    │
    └── ⚙️ Billing Settings
        ├── Default Rates
        ├── Billing Cycle
        └── Auto-suspend Rules
```

### Tenant Bot - منوی Wallet

```
[Admin Panel] (Tenant)
└── 💰 Wallet
    ├── 📊 Current Balance
    ├── 📜 Transaction History
    ├── 📈 Usage Report
    │   ├── Traffic Consumed
    │   ├── Subscriptions Sold
    │   └── Estimated Cost
    └── ⚠️ Low Balance Warning
```

---

## 🔔 Notifications

### برای Master Admin

```
🔔 Tenant Wallet Low Balance
━━━━━━━━━━━━━━━━━━━━━━
Tenant: {tenant_name}
Current Balance: {balance} تومان
Threshold: {threshold} تومان
Action Required: Top up wallet
```

### برای Tenant Admin

```
⚠️ هشدار موجودی کیف پول
━━━━━━━━━━━━━━━━━━━━━━
موجودی فعلی: {balance} تومان
حداقل مورد نیاز: {min} تومان

برای جلوگیری از قطع سرویس، لطفاً کیف پول را شارژ کنید.
```

```
❌ سرویس متوقف شد
━━━━━━━━━━━━━━━━━━━━━━
به دلیل کمبود موجودی، سرویس ربات شما موقتاً متوقف شد.

برای فعال‌سازی مجدد، با مدیریت تماس بگیرید.
```

---

## 📊 Reports

### گزارش مصرف ترافیک (برای Master)

```
📊 Traffic Usage Report
━━━━━━━━━━━━━━━━━━━━━━
Period: {start_date} - {end_date}

| Tenant | Traffic Used | Traffic Sold | Revenue |
|--------|--------------|--------------|---------|
| Bot A  | 500 GB       | 1000 GB      | 50,000  |
| Bot B  | 200 GB       | 400 GB       | 20,000  |
| Bot C  | 1000 GB      | 2000 GB      | 100,000 |
━━━━━━━━━━━━━━━━━━━━━━
Total Revenue: 170,000 تومان
```

### گزارش کیف پول (برای Tenant)

```
💰 Wallet Report
━━━━━━━━━━━━━━━━━━━━━━
Period: {month}

Opening Balance: 100,000 تومان
+ Top-ups: 50,000 تومان
- Subscription Sales: -30,000 تومان
- Traffic Usage: -20,000 تومان
━━━━━━━━━━━━━━━━━━━━━━
Closing Balance: 100,000 تومان
```

---

## 🛠️ Implementation Tasks

### Phase 1: Database (1 day)

- [ ] Add billing columns to `bots` table
- [ ] Create `tenant_wallet_transactions` table
- [ ] Create `tenant_traffic_usage` table
- [ ] Create indexes

### Phase 2: CRUD (1 day)

- [ ] `app/database/crud/tenant_wallet.py`
  - `get_wallet_balance()`
  - `add_wallet_transaction()`
  - `get_wallet_transactions()`
  - `deduct_for_subscription()`
  - `deduct_for_traffic()`

- [ ] `app/database/crud/tenant_traffic_usage.py`
  - `record_traffic_usage()`
  - `get_unbilled_usage()`
  - `mark_as_billed()`

### Phase 3: Services (2 days)

- [ ] `app/services/tenant_billing_service.py`
  - `process_subscription_sale()`
  - `process_traffic_billing()`
  - `check_wallet_balance()`
  - `send_low_balance_warning()`

- [ ] `app/services/tenant_billing_cron.py`
  - Background job for traffic billing

### Phase 4: Handlers (2 days)

- [ ] `app/handlers/admin/tenant_billing.py`
  - Master: Manage tenant wallets
  - Master: View billing reports

- [ ] Update `app/handlers/admin/tenant_bots.py`
  - Add wallet info to tenant detail
  - Add top-up flow

### Phase 5: Integration (1 day)

- [ ] Hook billing into subscription creation
- [ ] Hook billing into traffic sync
- [ ] Add balance checks before subscription creation

---

## ⚠️ نکات مهم

1. **همیشه قبل از فروش اشتراک، موجودی چک شود**
2. **تراکنش‌های کیف پول atomic باشند**
3. **لاگ کامل همه تراکنش‌ها**
4. **امکان refund در صورت لغو اشتراک**
5. **گزارش‌گیری دقیق برای تسویه حساب**

---

**تاریخ ایجاد:** 2025-12-15  
**تایید شده توسط:** User









