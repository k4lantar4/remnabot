-- Seed Data: Initial Tenant Subscription Plans
-- Increment: 1.2 (after migration 002_create_tenant_subscription_tables.sql)
-- Date: 2025-12-21
-- Description: Seeds initial subscription plan tiers
-- 
-- This script should be run AFTER migration 002_create_tenant_subscription_tables.sql
-- Adjust prices and descriptions as needed for your business model

-- Insert default subscription plans
INSERT INTO tenant_subscription_plans (name, display_name, monthly_price_toman, activation_fee_toman, description, is_active, sort_order) VALUES
('starter', 'Starter Plan', 100000, 50000, 'Basic plan for small bots with essential features', TRUE, 1),
('growth', 'Growth Plan', 200000, 100000, 'Advanced plan for growing bots with additional features', TRUE, 2),
('enterprise', 'Enterprise Plan', 500000, 200000, 'Full-featured plan for large bots with all features', TRUE, 3)
ON CONFLICT (name) DO NOTHING;

-- Example: Grant features to Starter plan
-- Uncomment and adjust feature keys as needed:
/*
INSERT INTO plan_feature_grants (plan_tier_id, feature_key, enabled, config_override) VALUES
((SELECT id FROM tenant_subscription_plans WHERE name = 'starter'), 'card_to_card', TRUE, '{}'),
((SELECT id FROM tenant_subscription_plans WHERE name = 'starter'), 'zarinpal', TRUE, '{}')
ON CONFLICT (plan_tier_id, feature_key) DO NOTHING;
*/

-- Example: Grant features to Growth plan
-- Uncomment and adjust feature keys as needed:
/*
INSERT INTO plan_feature_grants (plan_tier_id, feature_key, enabled, config_override) VALUES
((SELECT id FROM tenant_subscription_plans WHERE name = 'growth'), 'card_to_card', TRUE, '{}'),
((SELECT id FROM tenant_subscription_plans WHERE name = 'growth'), 'zarinpal', TRUE, '{}'),
((SELECT id FROM tenant_subscription_plans WHERE name = 'growth'), 'yookassa', TRUE, '{}')
ON CONFLICT (plan_tier_id, feature_key) DO NOTHING;
*/

-- Example: Grant features to Enterprise plan (all features)
-- Uncomment and adjust feature keys as needed:
/*
INSERT INTO plan_feature_grants (plan_tier_id, feature_key, enabled, config_override) VALUES
((SELECT id FROM tenant_subscription_plans WHERE name = 'enterprise'), 'card_to_card', TRUE, '{}'),
((SELECT id FROM tenant_subscription_plans WHERE name = 'enterprise'), 'zarinpal', TRUE, '{}'),
((SELECT id FROM tenant_subscription_plans WHERE name = 'enterprise'), 'yookassa', TRUE, '{}'),
((SELECT id FROM tenant_subscription_plans WHERE name = 'enterprise'), 'cryptobot', TRUE, '{}'),
((SELECT id FROM tenant_subscription_plans WHERE name = 'enterprise'), 'pal24', TRUE, '{}')
ON CONFLICT (plan_tier_id, feature_key) DO NOTHING;
*/

