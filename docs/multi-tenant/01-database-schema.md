# Database Schema Design

**Version:** 1.0  
**Date:** 2025-12-12  
**Status:** Ready for Implementation

---

## Overview

This document describes the complete database schema for multi-tenant architecture. It includes:
- 7 new tables for tenant management
- Changes to 47+ existing tables
- All indexes and constraints
- Migration scripts

---

## New Tables

### 1. `bots` (Tenants Table)

**Purpose:** Stores all bot instances (master + tenants)

**SQL:**
```sql
CREATE TABLE bots (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    telegram_bot_token VARCHAR(255) UNIQUE NOT NULL,
    api_token VARCHAR(255) UNIQUE NOT NULL,
    api_token_hash VARCHAR(128) NOT NULL,
    is_master BOOLEAN DEFAULT FALSE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    
    -- Card-to-card settings
    card_to_card_enabled BOOLEAN DEFAULT FALSE NOT NULL,
    card_receipt_topic_id INTEGER,
    
    -- Zarinpal settings
    zarinpal_enabled BOOLEAN DEFAULT FALSE NOT NULL,
    zarinpal_merchant_id VARCHAR(255),
    zarinpal_sandbox BOOLEAN DEFAULT FALSE NOT NULL,
    
    -- General settings
    default_language VARCHAR(5) DEFAULT 'fa' NOT NULL,
    support_username VARCHAR(255),
    admin_chat_id BIGINT,
    admin_topic_id INTEGER,
    notification_group_id BIGINT,
    notification_topic_id INTEGER,
    
    -- Wallet & billing
    wallet_balance_kopeks BIGINT DEFAULT 0 NOT NULL,
    traffic_consumed_bytes BIGINT DEFAULT 0 NOT NULL,
    traffic_sold_bytes BIGINT DEFAULT 0 NOT NULL,
    
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_bots_api_token_hash ON bots(api_token_hash);
CREATE INDEX idx_bots_telegram_token ON bots(telegram_bot_token);
CREATE INDEX idx_bots_is_master ON bots(is_master);
CREATE INDEX idx_bots_is_active ON bots(is_active);
```

**Key Columns:**
- `telegram_bot_token`: Unique Telegram bot token
- `api_token`: API token for management (shown once, then hashed)
- `is_master`: TRUE for master bot
- `wallet_balance_kopeks`: Tenant wallet balance

---

### 2. `bot_feature_flags` (Feature Flags)

**Purpose:** Enable/disable features per tenant

**SQL:**
```sql
CREATE TABLE bot_feature_flags (
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT FALSE NOT NULL,
    config JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    
    PRIMARY KEY (bot_id, feature_key)
);

CREATE INDEX idx_bot_feature_flags_bot_id ON bot_feature_flags(bot_id);
CREATE INDEX idx_bot_feature_flags_enabled ON bot_feature_flags(bot_id, enabled) WHERE enabled = TRUE;
```

**Feature Keys:**
- `telegram_stars`, `yookassa`, `cryptobot`, `pal24`, `mulenpay`, `wata`, `platega`, `heleket`, `tribute`
- `card_to_card`, `zarinpal`
- `trial_subscription`, `auto_renewal`, `simple_purchase`
- `referral_program`, `promo_codes`
- `support_tickets`, `support_contact`
- `mini_app`, `server_status`, `monitoring`, `polls`, `campaigns`

---

### 3. `bot_configurations` (Tenant Configurations)

**Purpose:** Store tenant-specific configuration values

**SQL:**
```sql
CREATE TABLE bot_configurations (
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    config_key VARCHAR(100) NOT NULL,
    config_value JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    
    PRIMARY KEY (bot_id, config_key)
);

CREATE INDEX idx_bot_configurations_bot_id ON bot_configurations(bot_id);
```

---

### 4. `tenant_payment_cards` (Payment Cards)

**Purpose:** Store payment cards per tenant with rotation

**SQL:**
```sql
CREATE TABLE tenant_payment_cards (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    card_number VARCHAR(50) NOT NULL,
    card_holder_name VARCHAR(255) NOT NULL,
    rotation_strategy VARCHAR(20) DEFAULT 'round_robin' NOT NULL,
    rotation_interval_minutes INTEGER DEFAULT 60,
    weight INTEGER DEFAULT 1 NOT NULL,
    success_count INTEGER DEFAULT 0 NOT NULL,
    failure_count INTEGER DEFAULT 0 NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    last_used_at TIMESTAMP,
    current_usage_count INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_tenant_payment_cards_bot_id ON tenant_payment_cards(bot_id);
CREATE INDEX idx_tenant_payment_cards_active ON tenant_payment_cards(bot_id, is_active) WHERE is_active = TRUE;
```

**Rotation Strategies:**
- `round_robin`: Cycle through cards
- `random`: Random selection
- `time_based`: Rotate every N minutes
- `weighted`: Based on success rate

---

### 5. `bot_plans` (Tenant Plans)

**Purpose:** Custom subscription plans per tenant

**SQL:**
```sql
CREATE TABLE bot_plans (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    period_days INTEGER NOT NULL,
    price_kopeks INTEGER NOT NULL,
    traffic_limit_gb INTEGER DEFAULT 0,
    device_limit INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    sort_order INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_bot_plans_bot_id ON bot_plans(bot_id);
CREATE INDEX idx_bot_plans_active ON bot_plans(bot_id, is_active) WHERE is_active = TRUE;
```

---

### 6. `card_to_card_payments` (Card Payments)

**Purpose:** Track card-to-card payment requests

**SQL:**
```sql
CREATE TABLE card_to_card_payments (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
    card_id INTEGER REFERENCES tenant_payment_cards(id) ON DELETE SET NULL,
    amount_kopeks INTEGER NOT NULL,
    tracking_number VARCHAR(50) UNIQUE NOT NULL,
    receipt_type VARCHAR(20),
    receipt_text TEXT,
    receipt_image_file_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    admin_reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    admin_reviewed_at TIMESTAMP,
    admin_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_card_payments_bot_user ON card_to_card_payments(bot_id, user_id);
CREATE INDEX idx_card_payments_tracking ON card_to_card_payments(tracking_number);
CREATE INDEX idx_card_payments_status ON card_to_card_payments(bot_id, status);
```

---

### 7. `zarinpal_payments` (Zarinpal Payments)

**Purpose:** Track Zarinpal payment requests

**SQL:**
```sql
CREATE TABLE zarinpal_payments (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
    amount_kopeks INTEGER NOT NULL,
    zarinpal_authority VARCHAR(255) UNIQUE,
    zarinpal_ref_id VARCHAR(255),
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    callback_url TEXT,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_zarinpal_bot_user ON zarinpal_payments(bot_id, user_id);
CREATE INDEX idx_zarinpal_authority ON zarinpal_payments(zarinpal_authority);
```

---

## Schema Changes to Existing Tables

### Users Table

**Changes:**
1. Add `bot_id` column
2. Remove unique constraint on `telegram_id`
3. Add composite unique constraint `(telegram_id, bot_id)`

**SQL:**
```sql
ALTER TABLE users ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE;
CREATE INDEX idx_users_bot_id ON users(bot_id);
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_telegram_id_key;
CREATE UNIQUE INDEX idx_users_telegram_bot ON users(telegram_id, bot_id);
-- After migration: ALTER TABLE users ALTER COLUMN bot_id SET NOT NULL;
```

### Subscriptions Table

**SQL:**
```sql
ALTER TABLE subscriptions ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE NOT NULL;
CREATE INDEX idx_subscriptions_bot_id ON subscriptions(bot_id);
```

### Transactions Table

**SQL:**
```sql
ALTER TABLE transactions ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE NOT NULL;
CREATE INDEX idx_transactions_bot_id ON transactions(bot_id);
```

### Tickets Table

**SQL:**
```sql
ALTER TABLE tickets ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE NOT NULL;
CREATE INDEX idx_tickets_bot_id ON tickets(bot_id);
```

### Promocodes Table

**SQL:**
```sql
ALTER TABLE promocodes ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE;
CREATE INDEX idx_promocodes_bot_id ON promocodes(bot_id);
ALTER TABLE promocodes DROP CONSTRAINT IF EXISTS promocodes_code_key;
CREATE UNIQUE INDEX idx_promocodes_bot_code ON promocodes(bot_id, code);
```

### Promo Groups Table

**SQL:**
```sql
ALTER TABLE promo_groups ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE;
CREATE INDEX idx_promo_groups_bot_id ON promo_groups(bot_id);
ALTER TABLE promo_groups DROP CONSTRAINT IF EXISTS promo_groups_name_key;
CREATE UNIQUE INDEX idx_promo_groups_bot_name ON promo_groups(bot_id, name);
```

### Payment Tables

All payment tables need `bot_id`:
- `yookassa_payments`
- `cryptobot_payments`
- `heleket_payments`
- `mulenpay_payments`
- `pal24_payments`
- `wata_payments`
- `platega_payments`

**Example:**
```sql
ALTER TABLE yookassa_payments ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE NOT NULL;
CREATE INDEX idx_yookassa_payments_bot_id ON yookassa_payments(bot_id);
```

### Other Tables

All user-related tables need `bot_id`:
- `referral_earnings`
- `subscription_conversions`
- `promocode_uses`
- `discount_offers`
- `promo_offer_templates`
- `subscription_temporary_access`
- `promo_offer_logs`
- `sent_notifications`
- `subscription_events`
- `poll_responses`
- `advertising_campaigns`
- `advertising_campaign_registrations`
- `broadcast_history`
- `support_audit_logs`
- `user_messages`
- `welcome_texts`
- `main_menu_buttons`

---

## Migration Scripts

### Script 1: Create New Tables

**File:** `migrations/001_create_multi_tenant_tables.sql`

```sql
-- Run all CREATE TABLE statements above
-- Verify with: SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
```

### Script 2: Add bot_id to Existing Tables

**File:** `migrations/002_add_bot_id_to_tables.sql`

```sql
-- Run all ALTER TABLE statements above
-- Verify with: SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'bot_id';
```

### Script 3: Data Migration

**File:** `migrations/003_migrate_existing_data.py`

```python
# Create master bot
# Assign all existing data to master bot
# Make bot_id NOT NULL
```

---

## Verification Queries

### Check New Tables
```sql
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('bots', 'bot_feature_flags', 'bot_configurations', 'tenant_payment_cards');
```

### Check Indexes
```sql
SELECT indexname FROM pg_indexes 
WHERE tablename = 'bots';
```

### Check bot_id Columns
```sql
SELECT table_name, column_name, is_nullable 
FROM information_schema.columns 
WHERE column_name = 'bot_id' 
ORDER BY table_name;
```

---

## Related Documents

- [Code Changes](./02-code-changes.md)
- [Implementation Tasks](./04-implementation-tasks.md)
- [Migration Guide](./06-migration-guide.md)

