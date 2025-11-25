# Multi-Tenant Database Schema Design

**Author:** Architecture Team  
**Date:** 2025-11-21  
**Version:** 1.0

---

## Overview

This document defines the complete database schema for multi-tenant architecture. The design adds tenant isolation to the existing single-tenant system while maintaining backward compatibility.

---

## 1. Tenant Table (New)

### Schema Definition

```sql
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending_approval',
    bot_token VARCHAR(255) UNIQUE,
    bot_username VARCHAR(255),
    settings JSONB DEFAULT '{}'::jsonb,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_bot_token ON tenants(bot_token) WHERE bot_token IS NOT NULL;
CREATE INDEX idx_tenants_created_by ON tenants(created_by_user_id) WHERE created_by_user_id IS NOT NULL;

-- Constraints
ALTER TABLE tenants ADD CONSTRAINT chk_tenant_status 
    CHECK (status IN ('pending_approval', 'active', 'suspended', 'rejected'));

-- Comments
COMMENT ON TABLE tenants IS 'Represents a tenant (representative/dealer) who operates their own bot instance';
COMMENT ON COLUMN tenants.status IS 'Tenant status: pending_approval, active, suspended, rejected';
COMMENT ON COLUMN tenants.bot_token IS 'Telegram bot token for this tenant (unique per tenant)';
COMMENT ON COLUMN tenants.settings IS 'JSONB field for tenant-specific configuration (limits, features, branding)';
```

### Settings JSONB Schema

```json
{
  "limits": {
    "max_users": 1000,
    "max_active_subscriptions": 500,
    "daily_transaction_limit_kopeks": 1000000,
    "monthly_revenue_limit_kopeks": 10000000
  },
  "features": {
    "miniapp_enabled": true,
    "referral_program_enabled": true,
    "promo_codes_enabled": true,
    "support_tickets_enabled": true,
    "broadcasts_enabled": true,
    "polls_enabled": true
  },
  "branding": {
    "bot_name": "Custom Bot Name",
    "welcome_message": "Custom welcome message",
    "logo_url": "https://example.com/logo.png"
  },
  "payment_providers": {
    "enabled": ["telegram_stars", "yookassa"],
    "disabled": ["cryptobot", "heleket"]
  },
  "remnawave": {
    "api_url": "https://remnawave.com/api",
    "api_key": "encrypted_key"
  }
}
```

---

## 2. Tenant-Scoped Tables (Add tenant_id)

### Classification

**Tenant-Scoped Tables** (require tenant_id):
- `users` - User accounts belong to a tenant
- `subscriptions` - Subscriptions belong to tenant users
- `transactions` - Transactions belong to tenant users
- `tickets` - Support tickets belong to tenant users
- `ticket_messages` - Ticket messages belong to tenant tickets
- `promo_groups` - Promo groups are tenant-specific
- `promocodes` - Promo codes are tenant-specific
- `promocode_uses` - Promo code uses belong to tenant users
- `referral_earnings` - Referral earnings belong to tenant users
- `discount_offers` - Discount offers belong to tenant users
- `promo_offer_templates` - Templates are tenant-specific
- `promo_offer_logs` - Logs belong to tenant users
- `subscription_conversions` - Conversions belong to tenant subscriptions
- `subscription_temporary_access` - Temporary access belongs to tenant subscriptions
- `user_promo_groups` - User-promo group associations are tenant-scoped
- `broadcast_history` - Broadcasts are tenant-specific
- `polls` - Polls are tenant-specific
- `poll_questions` - Poll questions belong to tenant polls
- `poll_options` - Poll options belong to tenant poll questions
- `poll_responses` - Poll responses belong to tenant users
- `poll_answers` - Poll answers belong to tenant responses
- `advertising_campaigns` - Campaigns are tenant-specific
- `advertising_campaign_registrations` - Registrations belong to tenant campaigns
- `user_messages` - User messages belong to tenant users
- `sent_notifications` - Notifications belong to tenant users
- `web_api_tokens` - API tokens are tenant-scoped

**Global Tables** (no tenant_id, shared across all tenants):
- `tenants` - Meta-table for tenant management
- `server_squads` - RemnaWave servers (shared infrastructure)
- `squads` - Server squads (shared)
- `system_settings` - Global system configuration
- `service_rules` - Global service rules
- `privacy_policies` - Global privacy policies
- `public_offers` - Global public offers
- `faq_settings` - Global FAQ settings
- `faq_pages` - Global FAQ pages
- `monitoring_logs` - System monitoring (global)
- `welcome_texts` - Global welcome texts
- `main_menu_buttons` - Global menu buttons (or tenant-specific? TBD)

---

## 3. Migration Strategy

### Step 1: Create Tenant Table

```sql
-- Migration: 001_create_tenants_table
CREATE TABLE tenants (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending_approval',
    bot_token VARCHAR(255) UNIQUE,
    bot_username VARCHAR(255),
    settings JSONB DEFAULT '{}'::jsonb,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_bot_token ON tenants(bot_token) WHERE bot_token IS NOT NULL;
```

### Step 2: Create Main Tenant (tenant_id = 1)

```sql
-- Migration: 002_create_main_tenant
INSERT INTO tenants (id, name, status, created_at, updated_at)
VALUES (1, 'Main Bot', 'active', NOW(), NOW());

-- Set sequence to start from 2
SELECT setval('tenants_id_seq', 2, false);
```

### Step 3: Add tenant_id to Tenant-Scoped Tables

```sql
-- Migration: 003_add_tenant_id_to_users
ALTER TABLE users 
ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT DEFAULT 1;

-- Update existing data
UPDATE users SET tenant_id = 1 WHERE tenant_id IS NULL;

-- Make NOT NULL after data migration
ALTER TABLE users ALTER COLUMN tenant_id SET NOT NULL;

-- Create index
CREATE INDEX idx_users_tenant_id ON users(tenant_id);

-- Add composite unique constraint for telegram_id per tenant
-- Note: telegram_id should be unique per tenant, not globally
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_telegram_id_key;
CREATE UNIQUE INDEX idx_users_telegram_id_tenant_id ON users(telegram_id, tenant_id);
```

```sql
-- Migration: 004_add_tenant_id_to_subscriptions
ALTER TABLE subscriptions 
ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;

-- Update via user relationship
UPDATE subscriptions s
SET tenant_id = u.tenant_id
FROM users u
WHERE s.user_id = u.id;

ALTER TABLE subscriptions ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_subscriptions_tenant_id ON subscriptions(tenant_id);
```

```sql
-- Migration: 005_add_tenant_id_to_transactions
ALTER TABLE transactions 
ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;

UPDATE transactions t
SET tenant_id = u.tenant_id
FROM users u
WHERE t.user_id = u.id;

ALTER TABLE transactions ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_transactions_tenant_id ON transactions(tenant_id);
```

```sql
-- Migration: 006_add_tenant_id_to_tickets
ALTER TABLE tickets 
ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;

UPDATE tickets t
SET tenant_id = u.tenant_id
FROM users u
WHERE t.user_id = u.id;

ALTER TABLE tickets ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_tickets_tenant_id ON tickets(tenant_id);
```

```sql
-- Migration: 007_add_tenant_id_to_ticket_messages
ALTER TABLE ticket_messages 
ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;

UPDATE ticket_messages tm
SET tenant_id = t.tenant_id
FROM tickets t
WHERE tm.ticket_id = t.id;

ALTER TABLE ticket_messages ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_ticket_messages_tenant_id ON ticket_messages(tenant_id);
```

```sql
-- Migration: 008_add_tenant_id_to_promo_groups
ALTER TABLE promo_groups 
ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT DEFAULT 1;

UPDATE promo_groups SET tenant_id = 1 WHERE tenant_id IS NULL;
ALTER TABLE promo_groups ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_promo_groups_tenant_id ON promo_groups(tenant_id);
```

```sql
-- Migration: 009_add_tenant_id_to_promocodes
ALTER TABLE promocodes 
ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT DEFAULT 1;

UPDATE promocodes SET tenant_id = 1 WHERE tenant_id IS NULL;
ALTER TABLE promocodes ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_promocodes_tenant_id ON promocodes(tenant_id);

-- Update unique constraint: code should be unique per tenant
ALTER TABLE promocodes DROP CONSTRAINT IF EXISTS promocodes_code_key;
CREATE UNIQUE INDEX idx_promocodes_code_tenant_id ON promocodes(code, tenant_id);
```

```sql
-- Migration: 010_add_tenant_id_to_remaining_tables
-- ReferralEarnings
ALTER TABLE referral_earnings ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE referral_earnings re SET tenant_id = u.tenant_id FROM users u WHERE re.user_id = u.id;
ALTER TABLE referral_earnings ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_referral_earnings_tenant_id ON referral_earnings(tenant_id);

-- DiscountOffers
ALTER TABLE discount_offers ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE discount_offers do SET tenant_id = u.tenant_id FROM users u WHERE do.user_id = u.id;
ALTER TABLE discount_offers ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_discount_offers_tenant_id ON discount_offers(tenant_id);

-- PromoOfferTemplates
ALTER TABLE promo_offer_templates ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT DEFAULT 1;
UPDATE promo_offer_templates SET tenant_id = 1 WHERE tenant_id IS NULL;
ALTER TABLE promo_offer_templates ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_promo_offer_templates_tenant_id ON promo_offer_templates(tenant_id);

-- PromoOfferLogs
ALTER TABLE promo_offer_logs ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE promo_offer_logs pol SET tenant_id = u.tenant_id FROM users u WHERE pol.user_id = u.id;
ALTER TABLE promo_offer_logs ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_promo_offer_logs_tenant_id ON promo_offer_logs(tenant_id);

-- SubscriptionConversions
ALTER TABLE subscription_conversions ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE subscription_conversions sc SET tenant_id = s.tenant_id FROM subscriptions s WHERE sc.subscription_id = s.id;
ALTER TABLE subscription_conversions ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_subscription_conversions_tenant_id ON subscription_conversions(tenant_id);

-- SubscriptionTemporaryAccess
ALTER TABLE subscription_temporary_access ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE subscription_temporary_access sta SET tenant_id = s.tenant_id FROM subscriptions s WHERE sta.subscription_id = s.id;
ALTER TABLE subscription_temporary_access ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_subscription_temporary_access_tenant_id ON subscription_temporary_access(tenant_id);

-- UserPromoGroups (via user relationship)
ALTER TABLE user_promo_groups ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE user_promo_groups upg SET tenant_id = u.tenant_id FROM users u WHERE upg.user_id = u.id;
ALTER TABLE user_promo_groups ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_user_promo_groups_tenant_id ON user_promo_groups(tenant_id);

-- BroadcastHistory
ALTER TABLE broadcast_history ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE broadcast_history bh SET tenant_id = u.tenant_id FROM users u WHERE bh.admin_id = u.id;
ALTER TABLE broadcast_history ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_broadcast_history_tenant_id ON broadcast_history(tenant_id);

-- Polls
ALTER TABLE polls ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT DEFAULT 1;
UPDATE polls SET tenant_id = 1 WHERE tenant_id IS NULL;
ALTER TABLE polls ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_polls_tenant_id ON polls(tenant_id);

-- PollQuestions (via poll)
ALTER TABLE poll_questions ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE poll_questions pq SET tenant_id = p.tenant_id FROM polls p WHERE pq.poll_id = p.id;
ALTER TABLE poll_questions ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_poll_questions_tenant_id ON poll_questions(tenant_id);

-- PollOptions (via poll_question -> poll)
ALTER TABLE poll_options ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE poll_options po SET tenant_id = pq.tenant_id FROM poll_questions pq WHERE po.question_id = pq.id;
ALTER TABLE poll_options ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_poll_options_tenant_id ON poll_options(tenant_id);

-- PollResponses
ALTER TABLE poll_responses ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE poll_responses pr SET tenant_id = u.tenant_id FROM users u WHERE pr.user_id = u.id;
ALTER TABLE poll_responses ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_poll_responses_tenant_id ON poll_responses(tenant_id);

-- PollAnswers (via poll_response)
ALTER TABLE poll_answers ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE poll_answers pa SET tenant_id = pr.tenant_id FROM poll_responses pr WHERE pa.response_id = pr.id;
ALTER TABLE poll_answers ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_poll_answers_tenant_id ON poll_answers(tenant_id);

-- AdvertisingCampaigns
ALTER TABLE advertising_campaigns ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT DEFAULT 1;
UPDATE advertising_campaigns SET tenant_id = 1 WHERE tenant_id IS NULL;
ALTER TABLE advertising_campaigns ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_advertising_campaigns_tenant_id ON advertising_campaigns(tenant_id);

-- AdvertisingCampaignRegistrations (via campaign)
ALTER TABLE advertising_campaign_registrations ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE advertising_campaign_registrations acr SET tenant_id = ac.tenant_id FROM advertising_campaigns ac WHERE acr.campaign_id = ac.id;
ALTER TABLE advertising_campaign_registrations ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_advertising_campaign_registrations_tenant_id ON advertising_campaign_registrations(tenant_id);

-- UserMessages
ALTER TABLE user_messages ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE user_messages um SET tenant_id = u.tenant_id FROM users u WHERE um.user_id = u.id;
ALTER TABLE user_messages ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_user_messages_tenant_id ON user_messages(tenant_id);

-- SentNotifications
ALTER TABLE sent_notifications ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE sent_notifications sn SET tenant_id = u.tenant_id FROM users u WHERE sn.user_id = u.id;
ALTER TABLE sent_notifications ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_sent_notifications_tenant_id ON sent_notifications(tenant_id);

-- WebApiTokens
ALTER TABLE web_api_tokens ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT DEFAULT 1;
UPDATE web_api_tokens SET tenant_id = 1 WHERE tenant_id IS NULL;
ALTER TABLE web_api_tokens ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_web_api_tokens_tenant_id ON web_api_tokens(tenant_id);
```

### Step 4: Update Payment Provider Tables

Payment provider tables should also be tenant-scoped:

```sql
-- Migration: 011_add_tenant_id_to_payment_tables
-- YooKassaPayments
ALTER TABLE yookassa_payments ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE yookassa_payments yp SET tenant_id = u.tenant_id FROM users u WHERE yp.user_id = u.id;
ALTER TABLE yookassa_payments ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_yookassa_payments_tenant_id ON yookassa_payments(tenant_id);

-- CryptoBotPayments
ALTER TABLE cryptobot_payments ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE cryptobot_payments cp SET tenant_id = u.tenant_id FROM users u WHERE cp.user_id = u.id;
ALTER TABLE cryptobot_payments ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_cryptobot_payments_tenant_id ON cryptobot_payments(tenant_id);

-- HeleketPayments
ALTER TABLE heleket_payments ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE heleket_payments hp SET tenant_id = u.tenant_id FROM users u WHERE hp.user_id = u.id;
ALTER TABLE heleket_payments ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_heleket_payments_tenant_id ON heleket_payments(tenant_id);

-- MulenPayPayments
ALTER TABLE mulenpay_payments ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE mulenpay_payments mp SET tenant_id = u.tenant_id FROM users u WHERE mp.user_id = u.id;
ALTER TABLE mulenpay_payments ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_mulenpay_payments_tenant_id ON mulenpay_payments(tenant_id);

-- Pal24Payments
ALTER TABLE pal24_payments ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE pal24_payments p24 SET tenant_id = u.tenant_id FROM users u WHERE p24.user_id = u.id;
ALTER TABLE pal24_payments ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_pal24_payments_tenant_id ON pal24_payments(tenant_id);

-- WataPayments
ALTER TABLE wata_payments ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE wata_payments wp SET tenant_id = u.tenant_id FROM users u WHERE wp.user_id = u.id;
ALTER TABLE wata_payments ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_wata_payments_tenant_id ON wata_payments(tenant_id);

-- PlategaPayments
ALTER TABLE platega_payments ADD COLUMN tenant_id INTEGER REFERENCES tenants(id) ON DELETE RESTRICT;
UPDATE platega_payments pp SET tenant_id = u.tenant_id FROM users u WHERE pp.user_id = u.id;
ALTER TABLE platega_payments ALTER COLUMN tenant_id SET NOT NULL;
CREATE INDEX idx_platega_payments_tenant_id ON platega_payments(tenant_id);
```

---

## 4. Index Strategy

### Composite Indexes for Common Queries

```sql
-- Users: tenant_id + status (for active users per tenant)
CREATE INDEX idx_users_tenant_status ON users(tenant_id, status) WHERE status = 'active';

-- Subscriptions: tenant_id + status (for active subscriptions per tenant)
CREATE INDEX idx_subscriptions_tenant_status ON subscriptions(tenant_id, status) WHERE status = 'active';

-- Transactions: tenant_id + created_at (for tenant analytics)
CREATE INDEX idx_transactions_tenant_created ON transactions(tenant_id, created_at);

-- Tickets: tenant_id + status (for open tickets per tenant)
CREATE INDEX idx_tickets_tenant_status ON tickets(tenant_id, status) WHERE status = 'open';
```

---

## 5. Constraints and Data Integrity

### Unique Constraints Per Tenant

Some fields should be unique per tenant, not globally:

- `users.telegram_id` - Unique per tenant (same Telegram user can exist in multiple tenants)
- `users.referral_code` - Unique per tenant
- `promocodes.code` - Unique per tenant
- `tenants.bot_token` - Globally unique (one bot token per tenant)

### Foreign Key Constraints

All tenant_id foreign keys use `ON DELETE RESTRICT` to prevent accidental tenant deletion when data exists.

---

## 6. Query Patterns

### Standard Tenant Filtering Pattern

All queries should include tenant filtering:

```sql
-- Example: Get users for a tenant
SELECT * FROM users WHERE tenant_id = :tenant_id;

-- Example: Get active subscriptions for a tenant
SELECT * FROM subscriptions 
WHERE tenant_id = :tenant_id AND status = 'active';

-- Example: Get transactions for a tenant in date range
SELECT * FROM transactions 
WHERE tenant_id = :tenant_id 
  AND created_at BETWEEN :start_date AND :end_date;
```

### Cross-Tenant Queries (Admin Only)

System admins can query across tenants:

```sql
-- Example: Get all tenants with user counts
SELECT t.id, t.name, t.status, COUNT(u.id) as user_count
FROM tenants t
LEFT JOIN users u ON u.tenant_id = t.id
GROUP BY t.id, t.name, t.status;
```

---

## 7. Performance Considerations

1. **Indexes**: All tenant_id columns are indexed for fast filtering
2. **Composite Indexes**: Common query patterns have composite indexes
3. **Partial Indexes**: Status-based queries use partial indexes (WHERE status = 'active')
4. **Query Planning**: PostgreSQL query planner will use tenant_id indexes for filtering

---

## 8. Migration Rollback Strategy

If migration needs to be rolled back:

1. Drop all tenant_id columns from tenant-scoped tables
2. Restore original unique constraints
3. Drop tenant table
4. Restore original indexes

**Note**: This is a destructive operation and should only be done in development or with full database backup.

---

## 9. Model Updates Required

### SQLAlchemy Model Changes

All tenant-scoped models need:
1. `tenant_id` column added
2. Foreign key relationship to `Tenant` model
3. Index on `tenant_id`
4. Query filtering by tenant_id in CRUD operations

---

## 10. Next Steps

1. Create Alembic migration scripts for all steps above
2. Update SQLAlchemy models with tenant_id
3. Update CRUD operations to filter by tenant_id
4. Add tenant context middleware
5. Test migration on development database
6. Test data isolation between tenants

---

**Document Status**: Ready for Implementation  
**Review Required**: Yes - Architecture Team  
**Approval Required**: Yes - Technical Lead

