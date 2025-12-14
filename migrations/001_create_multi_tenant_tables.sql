-- Migration: Create Multi-Tenant Tables
-- Increment: 1.1
-- Date: 2025-12-14
-- Description: Creates 7 new tables for multi-tenant architecture

-- 1. bots (Tenants Table)
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

-- 2. bot_feature_flags (Feature Flags)
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

-- 3. bot_configurations (Tenant Configurations)
CREATE TABLE bot_configurations (
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    config_key VARCHAR(100) NOT NULL,
    config_value JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    
    PRIMARY KEY (bot_id, config_key)
);

CREATE INDEX idx_bot_configurations_bot_id ON bot_configurations(bot_id);

-- 4. tenant_payment_cards (Payment Cards)
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

-- 5. bot_plans (Tenant Plans)
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

-- 6. card_to_card_payments (Card Payments)
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

-- 7. zarinpal_payments (Zarinpal Payments)
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
