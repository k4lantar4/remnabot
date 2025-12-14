# Multi-Tenant Migration Design Document

**Version:** 1.0  
**Date:** 2025-12-12  
**Status:** Draft  
**Author:** Development Team

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Database Schema Design](#database-schema-design)
3. [Code Changes Required](#code-changes-required)
4. [Feature Flag System](#feature-flag-system)
5. [Implementation Tasks](#implementation-tasks)
6. [Testing Strategy](#testing-strategy)
7. [Migration Strategy](#migration-strategy)
8. [Risk Analysis](#risk-analysis)
9. [Alternative Approaches](#alternative-approaches)

---

## Executive Summary

This document provides a comprehensive design for migrating the RemnaWave bot from a single-tenant to a multi-tenant SaaS architecture. The migration enables:

- Multiple bot instances (tenants) running from a single codebase
- Per-tenant feature flags and configuration
- Complete data isolation between tenants
- Tenant-specific payment methods (card-to-card with rotation)
- Wallet system per tenant with traffic-based billing
- API-based tenant management

**Key Principles:**
- Single codebase for all tenants
- Runtime feature configuration via database
- Zero technical debt
- Incremental, testable implementation
- Clean, maintainable code

---

## Database Schema Design

### 1. New Tables

#### 1.1. `bots` (Tenants Table)

**Purpose:** Stores all bot instances (master + tenants)

```sql
CREATE TABLE bots (
    id SERIAL PRIMARY KEY,
    
    -- Basic Information
    name VARCHAR(255) NOT NULL,
    telegram_bot_token VARCHAR(255) UNIQUE NOT NULL,
    api_token VARCHAR(255) UNIQUE NOT NULL,
    api_token_hash VARCHAR(128) NOT NULL,
    
    -- Tenant Type
    is_master BOOLEAN DEFAULT FALSE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    
    -- Card-to-Card Payment Settings
    card_to_card_enabled BOOLEAN DEFAULT FALSE NOT NULL,
    card_receipt_topic_id INTEGER,
    
    -- Zarinpal Payment Settings
    zarinpal_enabled BOOLEAN DEFAULT FALSE NOT NULL,
    zarinpal_merchant_id VARCHAR(255),
    zarinpal_sandbox BOOLEAN DEFAULT FALSE NOT NULL,
    
    -- General Settings
    default_language VARCHAR(5) DEFAULT 'fa' NOT NULL,
    support_username VARCHAR(255),
    admin_chat_id BIGINT,
    admin_topic_id INTEGER,
    notification_group_id BIGINT,
    notification_topic_id INTEGER,
    
    -- Wallet & Billing
    wallet_balance_kopeks BIGINT DEFAULT 0 NOT NULL,
    traffic_consumed_bytes BIGINT DEFAULT 0 NOT NULL,
    traffic_sold_bytes BIGINT DEFAULT 0 NOT NULL,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_bots_api_token_hash ON bots(api_token_hash);
CREATE INDEX idx_bots_telegram_token ON bots(telegram_bot_token);
CREATE INDEX idx_bots_is_master ON bots(is_master);
CREATE INDEX idx_bots_is_active ON bots(is_active);
```

**Columns Details:**
- `id`: Primary key, auto-increment
- `name`: Display name for the bot (e.g., "My VPN Bot")
- `telegram_bot_token`: Telegram Bot API token (unique)
- `api_token`: API token for tenant management (unique, shown once)
- `api_token_hash`: SHA-256 hash of API token for authentication
- `is_master`: TRUE for master bot, FALSE for tenant bots
- `is_active`: Whether bot is currently active
- `card_to_card_enabled`: Enable card-to-card payments
- `card_receipt_topic_id`: Topic ID for receipt notifications
- `zarinpal_enabled`: Enable Zarinpal payments
- `zarinpal_merchant_id`: Zarinpal merchant ID
- `zarinpal_sandbox`: Use sandbox mode
- `default_language`: Default interface language
- `support_username`: Support channel username
- `admin_chat_id`: Admin chat ID for notifications
- `admin_topic_id`: Admin topic ID for notifications
- `notification_group_id`: Group ID for tenant notifications
- `notification_topic_id`: Topic ID for tenant notifications
- `wallet_balance_kopeks`: Tenant wallet balance
- `traffic_consumed_bytes`: Total traffic consumed by tenant users
- `traffic_sold_bytes`: Total traffic sold to tenant users
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `created_by`: User who created this bot (nullable)

#### 1.2. `bot_feature_flags` (Feature Flags)

**Purpose:** Enable/disable features per tenant

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
- `telegram_stars`: Telegram Stars payments
- `yookassa`: YooKassa payments
- `cryptobot`: CryptoBot payments
- `pal24`: Pal24 payments
- `mulenpay`: MulenPay payments
- `wata`: WATA payments
- `platega`: Platega payments
- `heleket`: Heleket payments
- `tribute`: Tribute payments
- `card_to_card`: Card-to-card payments
- `zarinpal`: Zarinpal payments
- `trial_subscription`: Trial subscriptions
- `auto_renewal`: Auto-renewal feature
- `simple_purchase`: Simple purchase flow
- `referral_program`: Referral program
- `promo_codes`: Promo codes
- `support_tickets`: Support tickets
- `support_contact`: Support contact mode
- `mini_app`: Mini App integration
- `server_status`: Server status display
- `monitoring`: Monitoring and reports
- `polls`: Poll system
- `campaigns`: Advertising campaigns

**Config JSONB Structure:**
```json
{
  "min_amount_kopeks": 10000,
  "max_amount_kopeks": 10000000,
  "enabled_methods": [2, 10, 11],
  "custom_settings": {}
}
```

#### 1.3. `bot_configurations` (Tenant Configurations)

**Purpose:** Store tenant-specific configuration values

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

**Config Keys Examples:**
- `pricing`: Custom pricing configuration
- `subscription_periods`: Available subscription periods
- `traffic_packages`: Traffic package definitions
- `promo_groups`: Promo group settings
- `notification_settings`: Notification preferences
- `ui_customization`: UI customization settings

#### 1.4. `tenant_payment_cards` (Card-to-Card Payment Cards)

**Purpose:** Store payment cards per tenant with rotation settings

```sql
CREATE TABLE tenant_payment_cards (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    
    -- Card Information
    card_number VARCHAR(50) NOT NULL,
    card_holder_name VARCHAR(255) NOT NULL,
    
    -- Rotation Settings
    rotation_strategy VARCHAR(20) DEFAULT 'round_robin' NOT NULL,
    -- Values: 'round_robin', 'random', 'time_based', 'weighted'
    
    -- Time-based rotation (if rotation_strategy = 'time_based')
    rotation_interval_minutes INTEGER DEFAULT 60,
    
    -- Weighted rotation (if rotation_strategy = 'weighted')
    weight INTEGER DEFAULT 1 NOT NULL,
    success_count INTEGER DEFAULT 0 NOT NULL,
    failure_count INTEGER DEFAULT 0 NOT NULL,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    last_used_at TIMESTAMP,
    current_usage_count INTEGER DEFAULT 0 NOT NULL,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_tenant_payment_cards_bot_id ON tenant_payment_cards(bot_id);
CREATE INDEX idx_tenant_payment_cards_active ON tenant_payment_cards(bot_id, is_active) WHERE is_active = TRUE;
CREATE INDEX idx_tenant_payment_cards_rotation ON tenant_payment_cards(bot_id, rotation_strategy, is_active);
```

**Rotation Strategies:**
- `round_robin`: Use cards in order, cycle through
- `random`: Randomly select from active cards
- `time_based`: Rotate every N minutes
- `weighted`: Select based on success rate and weight

#### 1.5. `bot_plans` (Tenant-Specific Plans)

**Purpose:** Custom subscription plans per tenant

```sql
CREATE TABLE bot_plans (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    
    name VARCHAR(255) NOT NULL,
    period_days INTEGER NOT NULL,
    price_kopeks INTEGER NOT NULL,
    
    traffic_limit_gb INTEGER DEFAULT 0,  -- 0 = unlimited
    device_limit INTEGER DEFAULT 1,
    
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    sort_order INTEGER DEFAULT 0 NOT NULL,
    
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_bot_plans_bot_id ON bot_plans(bot_id);
CREATE INDEX idx_bot_plans_active ON bot_plans(bot_id, is_active) WHERE is_active = TRUE;
```

#### 1.6. `card_to_card_payments` (Card-to-Card Payments)

**Purpose:** Track card-to-card payment requests

```sql
CREATE TABLE card_to_card_payments (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
    
    -- Payment Details
    amount_kopeks INTEGER NOT NULL,
    tracking_number VARCHAR(50) UNIQUE NOT NULL,
    
    -- Card Used
    card_id INTEGER REFERENCES tenant_payment_cards(id) ON DELETE SET NULL,
    
    -- Receipt Information
    receipt_type VARCHAR(20),  -- 'image', 'text', 'both'
    receipt_text TEXT,
    receipt_image_file_id VARCHAR(255),  -- Telegram file_id
    
    -- Status
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    -- Values: 'pending', 'approved', 'rejected', 'cancelled'
    
    -- Admin Review
    admin_reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    admin_reviewed_at TIMESTAMP,
    admin_notes TEXT,
    
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_card_payments_bot_user ON card_to_card_payments(bot_id, user_id);
CREATE INDEX idx_card_payments_tracking ON card_to_card_payments(tracking_number);
CREATE INDEX idx_card_payments_status ON card_to_card_payments(bot_id, status);
CREATE INDEX idx_card_payments_pending ON card_to_card_payments(bot_id, status) WHERE status = 'pending';
```

#### 1.7. `zarinpal_payments` (Zarinpal Payments)

**Purpose:** Track Zarinpal payment requests

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
    -- Values: 'pending', 'paid', 'failed', 'cancelled'
    
    callback_url TEXT,
    
    created_at TIMESTAMP DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_zarinpal_bot_user ON zarinpal_payments(bot_id, user_id);
CREATE INDEX idx_zarinpal_authority ON zarinpal_payments(zarinpal_authority);
CREATE INDEX idx_zarinpal_status ON zarinpal_payments(bot_id, status);
```

### 2. Schema Changes to Existing Tables

#### 2.1. `users` Table

**Changes:**
1. Remove unique constraint on `telegram_id`
2. Add `bot_id` column
3. Add composite unique constraint on `(telegram_id, bot_id)`
4. Add index on `bot_id`

```sql
-- Step 1: Add bot_id column (nullable initially for migration)
ALTER TABLE users 
    ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE;

-- Step 2: Create index
CREATE INDEX idx_users_bot_id ON users(bot_id);

-- Step 3: Remove old unique constraint
ALTER TABLE users 
    DROP CONSTRAINT IF EXISTS users_telegram_id_key;

-- Step 4: Add composite unique constraint
CREATE UNIQUE INDEX idx_users_telegram_bot ON users(telegram_id, bot_id);

-- Step 5: After migration, make bot_id NOT NULL
ALTER TABLE users 
    ALTER COLUMN bot_id SET NOT NULL;
```

**Affected Columns:**
- `telegram_id`: Change from `UNIQUE` to `UNIQUE (telegram_id, bot_id)`
- `bot_id`: New column, foreign key to `bots.id`

#### 2.2. `subscriptions` Table

**Changes:**
1. Add `bot_id` column
2. Add index on `bot_id`

```sql
ALTER TABLE subscriptions 
    ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE NOT NULL;

CREATE INDEX idx_subscriptions_bot_id ON subscriptions(bot_id);
```

#### 2.3. `transactions` Table

**Changes:**
1. Add `bot_id` column
2. Add index on `bot_id`

```sql
ALTER TABLE transactions 
    ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE NOT NULL;

CREATE INDEX idx_transactions_bot_id ON transactions(bot_id);
```

#### 2.4. `tickets` Table

**Changes:**
1. Add `bot_id` column
2. Add index on `bot_id`

```sql
ALTER TABLE tickets 
    ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE NOT NULL;

CREATE INDEX idx_tickets_bot_id ON tickets(bot_id);
```

#### 2.5. `promocodes` Table

**Changes:**
1. Add `bot_id` column
2. Add index on `bot_id`
3. Change `code` from unique to composite unique `(bot_id, code)`

```sql
ALTER TABLE promocodes 
    ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE;

CREATE INDEX idx_promocodes_bot_id ON promocodes(bot_id);

ALTER TABLE promocodes 
    DROP CONSTRAINT IF EXISTS promocodes_code_key;

CREATE UNIQUE INDEX idx_promocodes_bot_code ON promocodes(bot_id, code);
```

#### 2.6. `promo_groups` Table

**Changes:**
1. Add `bot_id` column
2. Add index on `bot_id`
3. Change `name` from unique to composite unique `(bot_id, name)`

```sql
ALTER TABLE promo_groups 
    ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE;

CREATE INDEX idx_promo_groups_bot_id ON promo_groups(bot_id);

ALTER TABLE promo_groups 
    DROP CONSTRAINT IF EXISTS promo_groups_name_key;

CREATE UNIQUE INDEX idx_promo_groups_bot_name ON promo_groups(bot_id, name);
```

#### 2.7. Payment Tables

All payment tables need `bot_id`:

- `yookassa_payments`
- `cryptobot_payments`
- `heleket_payments`
- `mulenpay_payments`
- `pal24_payments`
- `wata_payments`
- `platega_payments`

```sql
-- Example for yookassa_payments
ALTER TABLE yookassa_payments 
    ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE NOT NULL;

CREATE INDEX idx_yookassa_payments_bot_id ON yookassa_payments(bot_id);
```

#### 2.8. Other Tables Requiring `bot_id`

All tables with user-related data need `bot_id`:

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

**Note:** Some tables like `server_squads`, `polls`, `service_rules`, `privacy_policies`, `public_offers`, `faq_settings`, `faq_pages` can be shared or per-tenant based on requirements.

---

## Code Changes Required

### Phase 1: Database Models

#### File: `app/database/models.py`

**Location:** After line 25 (after `Base = declarative_base()`)

**Add New Models:**

```python
# Line ~26: Add Bot model
class Bot(Base):
    __tablename__ = "bots"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    telegram_bot_token = Column(String(255), unique=True, nullable=False, index=True)
    api_token = Column(String(255), unique=True, nullable=False)
    api_token_hash = Column(String(128), nullable=False, index=True)
    is_master = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Card-to-card settings
    card_to_card_enabled = Column(Boolean, default=False, nullable=False)
    card_receipt_topic_id = Column(Integer, nullable=True)
    
    # Zarinpal settings
    zarinpal_enabled = Column(Boolean, default=False, nullable=False)
    zarinpal_merchant_id = Column(String(255), nullable=True)
    zarinpal_sandbox = Column(Boolean, default=False, nullable=False)
    
    # General settings
    default_language = Column(String(5), default='fa', nullable=False)
    support_username = Column(String(255), nullable=True)
    admin_chat_id = Column(BigInteger, nullable=True)
    admin_topic_id = Column(Integer, nullable=True)
    notification_group_id = Column(BigInteger, nullable=True)
    notification_topic_id = Column(Integer, nullable=True)
    
    # Wallet & billing
    wallet_balance_kopeks = Column(BigInteger, default=0, nullable=False)
    traffic_consumed_bytes = Column(BigInteger, default=0, nullable=False)
    traffic_sold_bytes = Column(BigInteger, default=0, nullable=False)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    users = relationship("User", back_populates="bot")
    subscriptions = relationship("Subscription", back_populates="bot")
    transactions = relationship("Transaction", back_populates="bot")
    feature_flags = relationship("BotFeatureFlag", back_populates="bot", cascade="all, delete-orphan")
    configurations = relationship("BotConfiguration", back_populates="bot", cascade="all, delete-orphan")
    payment_cards = relationship("TenantPaymentCard", back_populates="bot", cascade="all, delete-orphan")
    plans = relationship("BotPlan", back_populates="bot", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Bot(id={self.id}, name='{self.name}', is_master={self.is_master})>"


class BotFeatureFlag(Base):
    __tablename__ = "bot_feature_flags"
    
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), primary_key=True)
    feature_key = Column(String(100), primary_key=True)
    enabled = Column(Boolean, default=False, nullable=False)
    config = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    bot = relationship("Bot", back_populates="feature_flags")
    
    def __repr__(self):
        return f"<BotFeatureFlag(bot_id={self.bot_id}, feature='{self.feature_key}', enabled={self.enabled})>"


class BotConfiguration(Base):
    __tablename__ = "bot_configurations"
    
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), primary_key=True)
    config_key = Column(String(100), primary_key=True)
    config_value = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    bot = relationship("Bot", back_populates="configurations")
    
    def __repr__(self):
        return f"<BotConfiguration(bot_id={self.bot_id}, key='{self.config_key}')>"


class TenantPaymentCard(Base):
    __tablename__ = "tenant_payment_cards"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    
    card_number = Column(String(50), nullable=False)
    card_holder_name = Column(String(255), nullable=False)
    
    rotation_strategy = Column(String(20), default='round_robin', nullable=False)
    rotation_interval_minutes = Column(Integer, default=60, nullable=True)
    weight = Column(Integer, default=1, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    failure_count = Column(Integer, default=0, nullable=False)
    
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_used_at = Column(DateTime, nullable=True)
    current_usage_count = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    bot = relationship("Bot", back_populates="payment_cards")
    
    def __repr__(self):
        return f"<TenantPaymentCard(id={self.id}, bot_id={self.bot_id}, card='{self.card_number[-4:]}')>"


class BotPlan(Base):
    __tablename__ = "bot_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(255), nullable=False)
    period_days = Column(Integer, nullable=False)
    price_kopeks = Column(Integer, nullable=False)
    traffic_limit_gb = Column(Integer, default=0, nullable=False)
    device_limit = Column(Integer, default=1, nullable=False)
    
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    bot = relationship("Bot", back_populates="plans")
    
    def __repr__(self):
        return f"<BotPlan(id={self.id}, bot_id={self.bot_id}, name='{self.name}')>"


class CardToCardPayment(Base):
    __tablename__ = "card_to_card_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    card_id = Column(Integer, ForeignKey("tenant_payment_cards.id", ondelete="SET NULL"), nullable=True)
    
    amount_kopeks = Column(Integer, nullable=False)
    tracking_number = Column(String(50), unique=True, nullable=False, index=True)
    
    receipt_type = Column(String(20), nullable=True)
    receipt_text = Column(Text, nullable=True)
    receipt_image_file_id = Column(String(255), nullable=True)
    
    status = Column(String(20), default='pending', nullable=False, index=True)
    admin_reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_reviewed_at = Column(DateTime, nullable=True)
    admin_notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    bot = relationship("Bot")
    user = relationship("User")
    transaction = relationship("Transaction")
    card = relationship("TenantPaymentCard")
    
    def __repr__(self):
        return f"<CardToCardPayment(id={self.id}, tracking='{self.tracking_number}', status='{self.status}')>"


class ZarinpalPayment(Base):
    __tablename__ = "zarinpal_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    
    amount_kopeks = Column(Integer, nullable=False)
    zarinpal_authority = Column(String(255), unique=True, nullable=True, index=True)
    zarinpal_ref_id = Column(String(255), nullable=True)
    
    status = Column(String(20), default='pending', nullable=False, index=True)
    callback_url = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    bot = relationship("Bot")
    user = relationship("User")
    transaction = relationship("Transaction")
    
    def __repr__(self):
        return f"<ZarinpalPayment(id={self.id}, authority='{self.zarinpal_authority}', status='{self.status}')>"
```

**Modify Existing Models:**

**User Model (Line ~569):**
```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)  # NEW
    telegram_id = Column(BigInteger, nullable=False, index=True)  # REMOVED unique=True
    # ... rest of fields ...
    
    # Relationships
    bot = relationship("Bot", back_populates="users")  # NEW
    # ... rest of relationships ...
    
    __table_args__ = (
        UniqueConstraint('telegram_id', 'bot_id', name='uq_user_telegram_bot'),  # NEW
    )
```

**Subscription Model (Line ~659):**
```python
class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)  # NEW
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    # ... rest of fields ...
    
    # Relationships
    bot = relationship("Bot", back_populates="subscriptions")  # NEW
    # ... rest of relationships ...
```

**Transaction Model (Line ~825):**
```python
class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)  # NEW
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # ... rest of fields ...
    
    # Relationships
    bot = relationship("Bot", back_populates="transactions")  # NEW
    # ... rest of relationships ...
```

**Similar changes for all other models requiring `bot_id`.**

---

### Phase 2: Bot Context Middleware

#### File: `app/middlewares/bot_context.py` (NEW)

**Create new file:**

```python
import logging
from typing import Callable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import AsyncSessionLocal
from app.database.crud.bot import get_bot_by_token

logger = logging.getLogger(__name__)


class BotContextMiddleware(BaseMiddleware):
    """
    Middleware to inject bot context (bot_id, bot instance) into handlers.
    Detects bot from Telegram event and adds bot context to handler data.
    """
    
    async def __call__(
        self,
        handler: Callable,
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Get bot instance from event
        bot = event.bot if hasattr(event, 'bot') else None
        
        if not bot:
            logger.warning("Bot instance not found in event")
            return await handler(event, data)
        
        # Get bot_id from database using bot token
        async with AsyncSessionLocal() as db:
            bot_config = await get_bot_by_token(db, bot.token)
            
            if not bot_config:
                logger.error(f"Bot not found in database for token: {bot.token[:10]}...")
                return await handler(event, data)
            
            # Inject bot context
            data['bot_id'] = bot_config.id
            data['bot_config'] = bot_config
        
        return await handler(event, data)
```

**Register in `app/bot.py` (Line ~112):**

```python
# After line 112 (after GlobalErrorMiddleware)
from app.middlewares.bot_context import BotContextMiddleware

bot_context_middleware = BotContextMiddleware()
dp.message.middleware(bot_context_middleware)
dp.callback_query.middleware(bot_context_middleware)
dp.pre_checkout_query.middleware(bot_context_middleware)
```

---

### Phase 3: CRUD Operations

#### File: `app/database/crud/bot.py` (NEW)

**Create new file:**

```python
import logging
import secrets
import hashlib
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Bot, BotFeatureFlag, BotConfiguration

logger = logging.getLogger(__name__)


def generate_api_token() -> str:
    """Generate a secure API token."""
    return secrets.token_urlsafe(32)


def hash_api_token(token: str) -> str:
    """Hash API token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def get_bot_by_id(db: AsyncSession, bot_id: int) -> Optional[Bot]:
    """Get bot by ID."""
    result = await db.execute(
        select(Bot)
        .options(
            selectinload(Bot.feature_flags),
            selectinload(Bot.configurations),
        )
        .where(Bot.id == bot_id)
    )
    return result.scalar_one_or_none()


async def get_bot_by_token(db: AsyncSession, token: str) -> Optional[Bot]:
    """Get bot by Telegram bot token."""
    result = await db.execute(
        select(Bot)
        .options(
            selectinload(Bot.feature_flags),
            selectinload(Bot.configurations),
        )
        .where(Bot.telegram_bot_token == token)
    )
    return result.scalar_one_or_none()


async def get_bot_by_api_token(db: AsyncSession, api_token: str) -> Optional[Bot]:
    """Get bot by API token hash."""
    token_hash = hash_api_token(api_token)
    result = await db.execute(
        select(Bot)
        .where(Bot.api_token_hash == token_hash, Bot.is_active == True)
    )
    return result.scalar_one_or_none()


async def get_master_bot(db: AsyncSession) -> Optional[Bot]:
    """Get master bot."""
    result = await db.execute(
        select(Bot)
        .where(Bot.is_master == True, Bot.is_active == True)
    )
    return result.scalar_one_or_none()


async def get_active_bots(db: AsyncSession) -> List[Bot]:
    """Get all active bots."""
    result = await db.execute(
        select(Bot)
        .where(Bot.is_active == True)
        .order_by(Bot.created_at)
    )
    return result.scalars().all()


async def create_bot(
    db: AsyncSession,
    name: str,
    telegram_bot_token: str,
    is_master: bool = False,
    **kwargs
) -> tuple[Bot, str]:
    """
    Create a new bot.
    Returns (bot_instance, api_token).
    """
    api_token = generate_api_token()
    api_token_hash = hash_api_token(api_token)
    
    bot = Bot(
        name=name,
        telegram_bot_token=telegram_bot_token,
        api_token=api_token,  # Store plain token temporarily
        api_token_hash=api_token_hash,
        is_master=is_master,
        **kwargs
    )
    
    db.add(bot)
    await db.flush()
    
    # Clear plain token from instance (security)
    bot.api_token = None
    
    await db.refresh(bot)
    return bot, api_token
```

#### File: `app/database/crud/bot_feature_flag.py` (NEW)

**Create new file:**

```python
import logging
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import BotFeatureFlag

logger = logging.getLogger(__name__)


async def get_feature_flag(
    db: AsyncSession,
    bot_id: int,
    feature_key: str
) -> Optional[BotFeatureFlag]:
    """Get feature flag for a bot."""
    result = await db.execute(
        select(BotFeatureFlag)
        .where(
            BotFeatureFlag.bot_id == bot_id,
            BotFeatureFlag.feature_key == feature_key
        )
    )
    return result.scalar_one_or_none()


async def is_feature_enabled(
    db: AsyncSession,
    bot_id: int,
    feature_key: str
) -> bool:
    """Check if a feature is enabled for a bot."""
    flag = await get_feature_flag(db, bot_id, feature_key)
    return flag.enabled if flag else False


async def get_feature_config(
    db: AsyncSession,
    bot_id: int,
    feature_key: str
) -> Dict[str, Any]:
    """Get feature configuration."""
    flag = await get_feature_flag(db, bot_id, feature_key)
    return flag.config if flag and flag.config else {}


async def set_feature_flag(
    db: AsyncSession,
    bot_id: int,
    feature_key: str,
    enabled: bool,
    config: Optional[Dict[str, Any]] = None
) -> BotFeatureFlag:
    """Set or update feature flag."""
    flag = await get_feature_flag(db, bot_id, feature_key)
    
    if flag:
        flag.enabled = enabled
        if config is not None:
            flag.config = config
    else:
        flag = BotFeatureFlag(
            bot_id=bot_id,
            feature_key=feature_key,
            enabled=enabled,
            config=config or {}
        )
        db.add(flag)
    
    await db.flush()
    return flag


async def get_all_feature_flags(
    db: AsyncSession,
    bot_id: int
) -> List[BotFeatureFlag]:
    """Get all feature flags for a bot."""
    result = await db.execute(
        select(BotFeatureFlag)
        .where(BotFeatureFlag.bot_id == bot_id)
    )
    return result.scalars().all()
```

---

### Phase 4: Update CRUD Operations

#### File: `app/database/crud/user.py`

**Changes Required:**

1. **Line ~37: `get_user_by_id`**
   - Add `bot_id` parameter
   - Add filter: `.where(User.id == user_id, User.bot_id == bot_id)`

2. **Line ~57: `get_user_by_telegram_id`**
   - Add `bot_id` parameter
   - Change to: `.where(User.telegram_id == telegram_id, User.bot_id == bot_id)`

3. **Line ~77: `get_user_by_username`**
   - Add `bot_id` parameter
   - Add filter: `.where(..., User.bot_id == bot_id)`

4. **Line ~582: `get_users_list`**
   - Add `bot_id` parameter
   - Add filter: `.where(User.bot_id == bot_id)`

**Example Change:**

```python
# BEFORE (Line ~57):
async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> Optional[User]:
    result = await db.execute(
        select(User)
        .options(...)
        .where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()

# AFTER:
async def get_user_by_telegram_id(
    db: AsyncSession, 
    telegram_id: int,
    bot_id: int  # NEW
) -> Optional[User]:
    result = await db.execute(
        select(User)
        .options(...)
        .where(User.telegram_id == telegram_id, User.bot_id == bot_id)  # CHANGED
    )
    return result.scalar_one_or_none()
```

**Similar changes for all CRUD files:**
- `subscription.py`
- `transaction.py`
- `ticket.py`
- `promocode.py`
- `promo_group.py`
- All payment CRUD files
- All other CRUD files with user-related queries

---

### Phase 5: Update Handlers

#### File: `app/handlers/start.py`

**Changes Required:**

1. **User Registration Handler:**
   - Get `bot_id` from middleware data
   - Pass `bot_id` to user creation functions

**Example:**

```python
# BEFORE:
async def handle_start(message: types.Message, db_user: Optional[User] = None):
    if not db_user:
        db_user = await create_user(...)

# AFTER:
async def handle_start(
    message: types.Message, 
    db_user: Optional[User] = None,
    bot_id: int = None  # From middleware
):
    if not db_user:
        db_user = await create_user(..., bot_id=bot_id)  # Pass bot_id
```

**Similar changes for all handlers that:**
- Create users
- Query users
- Create subscriptions
- Create transactions
- Handle payments

---

### Phase 6: Multi-Bot Support

#### File: `app/bot.py`

**Changes Required:**

**Line ~80: `setup_bot` function**

**BEFORE:**
```python
async def setup_bot() -> tuple[Bot, Dispatcher]:
    bot = Bot(token=settings.BOT_TOKEN, ...)
    dp = Dispatcher(storage=storage)
    # ... register handlers ...
    return bot, dp
```

**AFTER:**
```python
from typing import Dict
from aiogram import Bot as AiogramBot, Dispatcher

# Global registry for active bots
active_bots: Dict[int, AiogramBot] = {}
active_dispatchers: Dict[int, Dispatcher] = {}


async def setup_bot(bot_config: Bot) -> tuple[AiogramBot, Dispatcher]:
    """Setup a single bot instance."""
    bot = AiogramBot(
        token=bot_config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # ... setup dispatcher, middlewares, handlers ...
    
    return bot, dp


async def initialize_all_bots():
    """Initialize all active bots from database."""
    from app.database.database import AsyncSessionLocal
    from app.database.crud.bot import get_active_bots
    
    async with AsyncSessionLocal() as db:
        bots = await get_active_bots(db)
        
        for bot_config in bots:
            try:
                bot, dp = await setup_bot(bot_config)
                active_bots[bot_config.id] = bot
                active_dispatchers[bot_config.id] = dp
                logger.info(f"Bot {bot_config.name} (ID: {bot_config.id}) initialized")
            except Exception as e:
                logger.error(f"Failed to initialize bot {bot_config.id}: {e}")


async def shutdown_all_bots():
    """Shutdown all active bots."""
    for bot_id, bot in active_bots.items():
        try:
            await bot.session.close()
        except Exception as e:
            logger.error(f"Error closing bot {bot_id}: {e}")
    
    active_bots.clear()
    active_dispatchers.clear()
```

#### File: `main.py`

**Changes Required:**

**Line ~49: `main` function**

**BEFORE:**
```python
async def main():
    bot, dp = await setup_bot()
    # ... start polling ...
```

**AFTER:**
```python
async def main():
    from app.bot import initialize_all_bots, active_bots, active_dispatchers
    
    # Initialize all bots
    await initialize_all_bots()
    
    if not active_bots:
        logger.error("No active bots found!")
        return
    
    # Start polling for all bots
    from aiogram import Bot as AiogramBot
    import asyncio
    
    tasks = []
    for bot_id, bot in active_bots.items():
        dp = active_dispatchers[bot_id]
        tasks.append(dp.start_polling(bot))
    
    await asyncio.gather(*tasks)
```

---

## Feature Flag System

### Service Layer

#### File: `app/services/tenant_feature_service.py` (NEW)

```python
import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.crud.bot_feature_flag import (
    is_feature_enabled as check_feature_enabled,
    get_feature_config as get_feature_config_value,
    set_feature_flag,
    get_all_feature_flags
)
from app.utils.cache import cache

logger = logging.getLogger(__name__)


class TenantFeatureService:
    """Service for managing tenant feature flags with caching."""
    
    CACHE_TTL = 300  # 5 minutes
    
    @staticmethod
    async def is_feature_enabled(
        db: AsyncSession,
        bot_id: int,
        feature_key: str,
        use_cache: bool = True
    ) -> bool:
        """Check if a feature is enabled for a tenant."""
        cache_key = f"feature_flag:{bot_id}:{feature_key}"
        
        if use_cache:
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached == "true"
        
        enabled = await check_feature_enabled(db, bot_id, feature_key)
        
        if use_cache:
            await cache.set(cache_key, "true" if enabled else "false", ttl=TenantFeatureService.CACHE_TTL)
        
        return enabled
    
    @staticmethod
    async def get_feature_config(
        db: AsyncSession,
        bot_id: int,
        feature_key: str
    ) -> Dict[str, Any]:
        """Get feature configuration."""
        return await get_feature_config_value(db, bot_id, feature_key)
    
    @staticmethod
    async def set_feature(
        db: AsyncSession,
        bot_id: int,
        feature_key: str,
        enabled: bool,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """Set feature flag and clear cache."""
        await set_feature_flag(db, bot_id, feature_key, enabled, config)
        
        # Clear cache
        cache_key = f"feature_flag:{bot_id}:{feature_key}"
        await cache.delete(cache_key)
        
        await db.commit()
    
    @staticmethod
    async def get_all_features(
        db: AsyncSession,
        bot_id: int
    ) -> Dict[str, bool]:
        """Get all feature flags for a tenant."""
        flags = await get_all_feature_flags(db, bot_id)
        return {flag.feature_key: flag.enabled for flag in flags}
```

### Usage in Code

**Before:**
```python
if settings.TELEGRAM_STARS_ENABLED:
    # ... handle stars payment ...
```

**After:**
```python
from app.services.tenant_feature_service import TenantFeatureService

# In handler:
bot_id = data.get('bot_id')
if await TenantFeatureService.is_feature_enabled(db, bot_id, 'telegram_stars'):
    # ... handle stars payment ...
```

---

## Implementation Tasks

### Task 1: Database Schema Creation

**Priority:** Critical  
**Estimated Time:** 2 hours  
**Dependencies:** None

**Steps:**
1. Create migration script: `migrations/add_multi_tenant_tables.sql`
2. Create new tables: `bots`, `bot_feature_flags`, `bot_configurations`, `tenant_payment_cards`, `bot_plans`, `card_to_card_payments`, `zarinpal_payments`
3. Test migration on development database
4. Verify all indexes are created

**Test:**
```sql
-- Verify tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('bots', 'bot_feature_flags', 'bot_configurations');

-- Verify indexes
SELECT indexname FROM pg_indexes 
WHERE tablename = 'bots';
```

**Acceptance Criteria:**
- ✅ All tables created successfully
- ✅ All indexes created
- ✅ Foreign keys working
- ✅ No errors in migration

---

### Task 2: Add bot_id to Existing Tables

**Priority:** Critical  
**Estimated Time:** 4 hours  
**Dependencies:** Task 1

**Steps:**
1. Create migration script: `migrations/add_bot_id_to_tables.sql`
2. Add `bot_id` column to all required tables (nullable initially)
3. Create indexes on `bot_id`
4. Update unique constraints (users, promocodes, promo_groups)
5. Test migration

**Test:**
```sql
-- Verify bot_id columns exist
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'users' AND column_name = 'bot_id';

-- Verify unique constraints
SELECT constraint_name, constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'users' AND constraint_type = 'UNIQUE';
```

**Acceptance Criteria:**
- ✅ All tables have `bot_id` column
- ✅ Indexes created
- ✅ Unique constraints updated
- ✅ No data loss

---

### Task 3: Create Database Models

**Priority:** Critical  
**Estimated Time:** 3 hours  
**Dependencies:** Task 1

**Steps:**
1. Add new models to `app/database/models.py`:
   - `Bot`
   - `BotFeatureFlag`
   - `BotConfiguration`
   - `TenantPaymentCard`
   - `BotPlan`
   - `CardToCardPayment`
   - `ZarinpalPayment`
2. Update existing models to add `bot_id` and relationships
3. Test model creation
4. Verify relationships work

**Test:**
```python
# Test model creation
from app.database.models import Bot
bot = Bot(name="Test Bot", ...)
assert bot.id is None  # Not saved yet

# Test relationships
bot = await get_bot_by_id(db, 1)
assert bot.users is not None
```

**Acceptance Criteria:**
- ✅ All models created
- ✅ Relationships working
- ✅ No import errors
- ✅ Models can be instantiated

---

### Task 4: Create CRUD Operations

**Priority:** Critical  
**Estimated Time:** 4 hours  
**Dependencies:** Task 3

**Steps:**
1. Create `app/database/crud/bot.py`
2. Create `app/database/crud/bot_feature_flag.py`
3. Create `app/database/crud/bot_configuration.py`
4. Create `app/database/crud/tenant_payment_card.py`
5. Test all CRUD operations

**Test:**
```python
# Test bot CRUD
bot, api_token = await create_bot(db, "Test Bot", "token123")
assert bot.id is not None
assert api_token is not None

# Test feature flag CRUD
await set_feature_flag(db, bot.id, "telegram_stars", True)
enabled = await is_feature_enabled(db, bot.id, "telegram_stars")
assert enabled == True
```

**Acceptance Criteria:**
- ✅ All CRUD functions work
- ✅ No errors
- ✅ Data persists correctly

---

### Task 5: Create Bot Context Middleware

**Priority:** Critical  
**Estimated Time:** 2 hours  
**Dependencies:** Task 4

**Steps:**
1. Create `app/middlewares/bot_context.py`
2. Register middleware in `app/bot.py`
3. Test middleware injection
4. Verify `bot_id` is available in handlers

**Test:**
```python
# Test middleware
async def test_handler(event, data):
    assert 'bot_id' in data
    assert 'bot_config' in data
    return True

# Simulate event
event = MockEvent(bot=MockBot(token="test_token"))
data = {}
await middleware(test_handler, event, data)
assert data['bot_id'] is not None
```

**Acceptance Criteria:**
- ✅ Middleware injects `bot_id`
- ✅ Middleware injects `bot_config`
- ✅ Works for all event types
- ✅ No performance issues

---

### Task 6: Update User CRUD

**Priority:** Critical  
**Estimated Time:** 3 hours  
**Dependencies:** Task 5

**Steps:**
1. Update `app/database/crud/user.py`:
   - Add `bot_id` parameter to all functions
   - Add `bot_id` filter to all queries
2. Update all call sites
3. Test all user operations

**Test:**
```python
# Test user queries with bot_id
user = await get_user_by_telegram_id(db, 123456, bot_id=1)
assert user.bot_id == 1

# Test user creation
user = await create_user(db, telegram_id=123456, bot_id=1)
assert user.bot_id == 1
```

**Acceptance Criteria:**
- ✅ All user CRUD functions updated
- ✅ All queries filter by `bot_id`
- ✅ No regressions
- ✅ Tests pass

---

### Task 7: Update Other CRUD Files

**Priority:** High  
**Estimated Time:** 8 hours  
**Dependencies:** Task 6

**Steps:**
1. Update subscription CRUD
2. Update transaction CRUD
3. Update ticket CRUD
4. Update promocode CRUD
5. Update promo_group CRUD
6. Update all payment CRUD files
7. Test all operations

**Test:**
```python
# Test subscription with bot_id
sub = await create_subscription(db, user_id=1, bot_id=1, ...)
assert sub.bot_id == 1
```

**Acceptance Criteria:**
- ✅ All CRUD files updated
- ✅ All queries filter by `bot_id`
- ✅ No regressions

---

### Task 8: Create Feature Flag Service

**Priority:** High  
**Estimated Time:** 2 hours  
**Dependencies:** Task 4

**Steps:**
1. Create `app/services/tenant_feature_service.py`
2. Implement caching
3. Test service
4. Document usage

**Test:**
```python
# Test feature service
enabled = await TenantFeatureService.is_feature_enabled(db, bot_id=1, feature_key="telegram_stars")
assert isinstance(enabled, bool)

# Test caching
enabled1 = await TenantFeatureService.is_feature_enabled(db, bot_id=1, feature_key="telegram_stars")
enabled2 = await TenantFeatureService.is_feature_enabled(db, bot_id=1, feature_key="telegram_stars")
# Second call should use cache
```

**Acceptance Criteria:**
- ✅ Service works correctly
- ✅ Caching works
- ✅ No performance issues

---

### Task 9: Update Handlers

**Priority:** High  
**Estimated Time:** 12 hours  
**Dependencies:** Task 7, Task 8

**Steps:**
1. Update `app/handlers/start.py`
2. Update `app/handlers/menu.py`
3. Update `app/handlers/balance/*.py`
4. Update `app/handlers/subscription/*.py`
5. Update `app/handlers/promocode.py`
6. Update `app/handlers/support/*.py`
7. Test all handlers

**Test:**
```python
# Test handler with bot_id
async def test_start_handler():
    message = MockMessage(from_user=MockUser(id=123456))
    data = {'bot_id': 1}
    await handle_start(message, data=data)
    # Verify user created with correct bot_id
```

**Acceptance Criteria:**
- ✅ All handlers updated
- ✅ All handlers use `bot_id`
- ✅ Feature flags checked
- ✅ No regressions

---

### Task 10: Multi-Bot Support

**Priority:** Critical  
**Estimated Time:** 4 hours  
**Dependencies:** Task 9

**Steps:**
1. Update `app/bot.py` for multi-bot support
2. Update `main.py` to initialize all bots
3. Test bot initialization
4. Test bot shutdown

**Test:**
```python
# Test multi-bot initialization
await initialize_all_bots()
assert len(active_bots) > 0

# Test each bot works
for bot_id, bot in active_bots.items():
    me = await bot.get_me()
    assert me is not None
```

**Acceptance Criteria:**
- ✅ All bots initialize
- ✅ All bots work independently
- ✅ No conflicts
- ✅ Clean shutdown

---

### Task 11: Migration Script for Existing Data

**Priority:** Critical  
**Estimated Time:** 3 hours  
**Dependencies:** Task 2

**Steps:**
1. Create migration script: `migrations/migrate_to_multi_tenant.py`
2. Create master bot
3. Assign all existing data to master bot
4. Test migration
5. Create rollback script

**Test:**
```python
# Test migration
await migrate_to_multi_tenant()

# Verify master bot exists
master = await get_master_bot(db)
assert master is not None

# Verify all users assigned
users = await get_users_list(db, bot_id=master.id)
assert len(users) > 0
```

**Acceptance Criteria:**
- ✅ Master bot created
- ✅ All data assigned
- ✅ No data loss
- ✅ Rollback works

---

### Task 12: API Endpoints for Tenant Management

**Priority:** Medium  
**Estimated Time:** 6 hours  
**Dependencies:** Task 10

**Steps:**
1. Create `app/webapi/routes/tenants.py`
2. Implement CRUD endpoints:
   - `POST /tenants` - Create tenant
   - `GET /tenants` - List tenants
   - `GET /tenants/{id}` - Get tenant
   - `PATCH /tenants/{id}` - Update tenant
   - `DELETE /tenants/{id}` - Delete tenant
3. Implement feature flag endpoints:
   - `GET /tenants/{id}/features` - List features
   - `POST /tenants/{id}/features/{key}` - Enable/disable feature
4. Test all endpoints

**Test:**
```python
# Test tenant creation
response = await client.post("/tenants", json={
    "name": "Test Bot",
    "telegram_bot_token": "123456:ABC-DEF"
})
assert response.status_code == 201

# Test feature flag
response = await client.post("/tenants/1/features/telegram_stars", json={
    "enabled": True
})
assert response.status_code == 200
```

**Acceptance Criteria:**
- ✅ All endpoints work
- ✅ Authentication works
- ✅ Validation works
- ✅ Tests pass

---

### Task 13: Card-to-Card Payment Implementation

**Priority:** Medium  
**Estimated Time:** 8 hours  
**Dependencies:** Task 9

**Steps:**
1. Create card rotation service
2. Create payment handlers
3. Create admin approval handlers
4. Test payment flow

**Test:**
```python
# Test card rotation
card = await get_next_card_for_payment(db, bot_id=1)
assert card is not None

# Test payment creation
payment = await create_card_to_card_payment(db, bot_id=1, user_id=1, amount=10000)
assert payment.tracking_number is not None
```

**Acceptance Criteria:**
- ✅ Card rotation works
- ✅ Payment flow works
- ✅ Admin approval works
- ✅ Notifications work

---

### Task 14: Zarinpal Payment Implementation

**Priority:** Medium  
**Estimated Time:** 6 hours  
**Dependencies:** Task 9

**Steps:**
1. Create Zarinpal client
2. Create payment handlers
3. Create webhook handler
4. Test payment flow

**Test:**
```python
# Test payment creation
payment = await create_zarinpal_payment(db, bot_id=1, user_id=1, amount=10000)
assert payment.zarinpal_authority is not None

# Test webhook
await handle_zarinpal_webhook(authority=payment.zarinpal_authority, status="OK")
# Verify payment updated
```

**Acceptance Criteria:**
- ✅ Payment creation works
- ✅ Webhook works
- ✅ Callback works
- ✅ Tests pass

---

### Task 15: Testing & Documentation

**Priority:** High  
**Estimated Time:** 8 hours  
**Dependencies:** All previous tasks

**Steps:**
1. Write unit tests
2. Write integration tests
3. Write migration tests
4. Update documentation
5. Create API documentation

**Test Coverage:**
- ✅ Unit tests: >80%
- ✅ Integration tests: All critical paths
- ✅ Migration tests: All scenarios

**Acceptance Criteria:**
- ✅ All tests pass
- ✅ Documentation complete
- ✅ API docs complete
- ✅ Migration guide complete

---

## Testing Strategy

### Unit Tests

**Location:** `tests/unit/`

**Test Files:**
- `test_bot_models.py` - Test Bot model
- `test_bot_crud.py` - Test bot CRUD
- `test_feature_flags.py` - Test feature flags
- `test_bot_context_middleware.py` - Test middleware
- `test_tenant_feature_service.py` - Test service

**Example:**
```python
async def test_create_bot():
    bot, api_token = await create_bot(db, "Test Bot", "token123")
    assert bot.name == "Test Bot"
    assert api_token is not None
    assert bot.api_token_hash is not None
```

### Integration Tests

**Location:** `tests/integration/`

**Test Files:**
- `test_multi_tenant_flow.py` - Test complete flow
- `test_feature_flag_integration.py` - Test feature flags in handlers
- `test_payment_flows.py` - Test payment flows

**Example:**
```python
async def test_user_registration_with_bot_id():
    # Create bot
    bot, _ = await create_bot(db, "Test Bot", "token123")
    
    # Register user
    user = await create_user(db, telegram_id=123456, bot_id=bot.id)
    
    # Verify
    assert user.bot_id == bot.id
    fetched = await get_user_by_telegram_id(db, 123456, bot_id=bot.id)
    assert fetched.id == user.id
```

### Migration Tests

**Location:** `tests/migration/`

**Test Files:**
- `test_migration_script.py` - Test migration
- `test_rollback.py` - Test rollback

**Example:**
```python
async def test_migration_assigns_all_data_to_master():
    # Pre-migration: Create test data
    user = await create_user(db, telegram_id=123456)
    
    # Run migration
    await migrate_to_multi_tenant()
    
    # Verify
    master = await get_master_bot(db)
    user = await get_user_by_id(db, user.id)
    assert user.bot_id == master.id
```

---

## Migration Strategy

### Phase 1: Preparation (Day 1)

1. **Backup Database**
   ```bash
   pg_dump remnawave_bot > backup_$(date +%Y%m%d).sql
   ```

2. **Create Migration Branch**
   ```bash
   git checkout -b feature/multi-tenant-migration
   ```

3. **Run Tests**
   ```bash
   pytest tests/ -v
   ```

### Phase 2: Schema Migration (Day 2)

1. **Create New Tables**
   ```bash
   psql remnawave_bot < migrations/add_multi_tenant_tables.sql
   ```

2. **Add bot_id Columns**
   ```bash
   psql remnawave_bot < migrations/add_bot_id_to_tables.sql
   ```

3. **Verify Schema**
   ```bash
   python scripts/verify_schema.py
   ```

### Phase 3: Code Migration (Days 3-5)

1. **Deploy Code Changes**
   - Deploy models
   - Deploy CRUD
   - Deploy middleware
   - Deploy handlers

2. **Test in Staging**
   - Test all handlers
   - Test feature flags
   - Test payments

### Phase 4: Data Migration (Day 6)

1. **Run Migration Script**
   ```bash
   python migrations/migrate_to_multi_tenant.py
   ```

2. **Verify Data**
   ```bash
   python scripts/verify_migration.py
   ```

3. **Make bot_id NOT NULL**
   ```sql
   ALTER TABLE users ALTER COLUMN bot_id SET NOT NULL;
   -- Repeat for all tables
   ```

### Phase 5: Testing (Day 7)

1. **Run Full Test Suite**
2. **Manual Testing**
3. **Performance Testing**

### Phase 6: Production Deployment (Day 8)

1. **Deploy to Production**
2. **Monitor**
3. **Rollback Plan Ready**

---

## Risk Analysis

### High Risk

1. **Data Loss During Migration**
   - **Mitigation:** Full backup before migration, test on staging first
   - **Rollback:** Restore from backup

2. **Performance Degradation**
   - **Mitigation:** Add indexes, use caching, monitor queries
   - **Rollback:** Revert to single-tenant queries

3. **Breaking Changes**
   - **Mitigation:** Comprehensive testing, gradual rollout
   - **Rollback:** Feature flag to disable multi-tenant

### Medium Risk

1. **Feature Flag Cache Issues**
   - **Mitigation:** Short TTL, cache invalidation on update
   - **Rollback:** Disable caching

2. **Bot Initialization Failures**
   - **Mitigation:** Retry logic, graceful degradation
   - **Rollback:** Disable failed bots

### Low Risk

1. **API Token Security**
   - **Mitigation:** Hash tokens, secure storage
   - **Rollback:** Regenerate tokens

---

## Alternative Approaches

### Approach 1: Separate Databases per Tenant

**Pros:**
- Complete isolation
- Easier backup/restore
- Better performance

**Cons:**
- Complex management
- Higher infrastructure costs
- Harder to share data

**Decision:** ❌ Rejected - Too complex, not needed

### Approach 2: Schema per Tenant

**Pros:**
- Good isolation
- Shared infrastructure

**Cons:**
- Complex migrations
- Harder to manage
- Limited scalability

**Decision:** ❌ Rejected - Too complex

### Approach 3: Row-Level Security (RLS)

**Pros:**
- Database-level security
- Transparent to application

**Cons:**
- PostgreSQL-specific
- Complex setup
- Performance overhead

**Decision:** ❌ Rejected - Overkill for our use case

### Approach 4: Single Codebase with bot_id (Selected)

**Pros:**
- Simple to implement
- Easy to maintain
- Good performance
- Flexible

**Cons:**
- Requires careful query design
- Need to ensure bot_id is always set

**Decision:** ✅ Selected - Best balance of simplicity and functionality

---

## Conclusion

This design document provides a comprehensive plan for migrating to a multi-tenant architecture. The approach is:

- **Incremental:** Tasks can be completed and tested independently
- **Safe:** Full backup and rollback plans
- **Clean:** No technical debt
- **Maintainable:** Well-documented and tested

**Next Steps:**
1. Review and approve this document
2. Create detailed task tickets
3. Begin implementation with Task 1
4. Regular progress reviews

---

**Document Version:** 1.0  
**Last Updated:** 2025-12-12  
**Status:** Ready for Review


