-- Migration: Create Tenant Subscription Tables
-- Increment: 1.2
-- Date: 2025-12-21
-- Description: Creates tables for tenant subscription plans, feature grants, and tenant subscriptions
-- Related Story: STORY-002 - Implement Tenant Bots Admin UX Panel
-- 
-- This migration creates the tables needed for:
-- 1. Subscription plan tiers (Starter, Growth, Enterprise, etc.)
-- 2. Feature grants per plan tier (which features are available for each plan)
-- 3. Tenant subscriptions (which plan each tenant bot has)

-- 1. tenant_subscription_plans (Subscription Plan Tiers)
CREATE TABLE tenant_subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    monthly_price_toman INTEGER NOT NULL,
    activation_fee_toman INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    sort_order INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_tenant_subscription_plans_active ON tenant_subscription_plans(is_active);
CREATE INDEX idx_tenant_subscription_plans_sort_order ON tenant_subscription_plans(sort_order);

-- 2. plan_feature_grants (Feature Grants per Plan Tier)
CREATE TABLE plan_feature_grants (
    plan_tier_id INTEGER NOT NULL REFERENCES tenant_subscription_plans(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT FALSE NOT NULL,
    config_override JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    PRIMARY KEY (plan_tier_id, feature_key)
);

CREATE INDEX idx_plan_feature_grants_plan_tier ON plan_feature_grants(plan_tier_id);
CREATE INDEX idx_plan_feature_grants_feature_key ON plan_feature_grants(feature_key);
CREATE INDEX idx_plan_feature_grants_enabled ON plan_feature_grants(plan_tier_id, enabled) WHERE enabled = TRUE;

-- 3. tenant_subscriptions (Bot Subscriptions to Plans)
CREATE TABLE tenant_subscriptions (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    plan_tier_id INTEGER NOT NULL REFERENCES tenant_subscription_plans(id),
    status VARCHAR(20) DEFAULT 'active' NOT NULL,
    start_date TIMESTAMP DEFAULT NOW() NOT NULL,
    end_date TIMESTAMP,
    auto_renewal BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    UNIQUE(bot_id)
);

CREATE INDEX idx_tenant_subscriptions_bot_id ON tenant_subscriptions(bot_id);
CREATE INDEX idx_tenant_subscriptions_plan_tier ON tenant_subscriptions(plan_tier_id);
CREATE INDEX idx_tenant_subscriptions_status ON tenant_subscriptions(status);
CREATE INDEX idx_tenant_subscriptions_active ON tenant_subscriptions(bot_id, status) WHERE status = 'active';

-- Seed initial plan data (optional - can be done via admin panel later)
-- Uncomment and adjust prices as needed:
/*
INSERT INTO tenant_subscription_plans (name, display_name, monthly_price_toman, activation_fee_toman, description, is_active, sort_order) VALUES
('starter', 'Starter Plan', 100000, 50000, 'Basic plan for small bots', TRUE, 1),
('growth', 'Growth Plan', 200000, 100000, 'Advanced plan for growing bots', TRUE, 2),
('enterprise', 'Enterprise Plan', 500000, 200000, 'Full-featured plan for large bots', TRUE, 3);
*/

