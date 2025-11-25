# Data Models Documentation

## Overview

The application uses SQLAlchemy ORM with PostgreSQL as the primary database. The data model consists of 46+ tables organized into logical domains: users, subscriptions, payments, promotions, support, and system management.

## Database Schema

### Core User & Subscription Models

#### User
**Table**: `users`

Primary user entity representing Telegram bot users.

**Key Fields**:
- `id` (Integer, PK) - Internal user ID
- `telegram_id` (BigInteger, Unique) - Telegram user ID
- `username`, `first_name`, `last_name` (String) - User profile
- `status` (Enum: active, blocked, deleted)
- `language` (String) - Interface language (ru/en)
- `balance_kopeks` (Integer) - Balance in kopeks (1 ruble = 100 kopeks)
- `referral_code` (String, Unique) - Unique referral code
- `referred_by_id` (FK → users.id) - Referrer user
- `promo_group_id` (FK → promo_groups.id) - Primary promo group
- `remnawave_uuid` (String, Unique) - RemnaWave panel UUID
- `has_had_paid_subscription` (Boolean) - Payment history flag
- `has_made_first_topup` (Boolean) - First topup flag
- `lifetime_used_traffic_bytes` (BigInteger) - Lifetime traffic usage
- `auto_promo_group_assigned` (Boolean) - Auto-assignment flag
- `auto_promo_group_threshold_kopeks` (BigInteger) - Spending threshold
- `promo_offer_discount_percent` (Integer) - Active discount
- `promo_offer_discount_expires_at` (DateTime) - Discount expiration
- `created_at`, `updated_at`, `last_activity` (DateTime)

**Relationships**:
- One-to-one: `subscription`
- One-to-many: `transactions`, `referral_earnings`, `tickets`, `poll_responses`
- Many-to-many: `promo_groups` (via `user_promo_groups`)

#### Subscription
**Table**: `subscriptions`

User subscription management.

**Key Fields**:
- `id` (Integer, PK)
- `user_id` (Integer, FK → users.id, Unique) - One subscription per user
- `status` (Enum: trial, active, expired, disabled, pending)
- `is_trial` (Boolean) - Trial subscription flag
- `start_date`, `end_date` (DateTime) - Subscription period
- `traffic_limit_gb` (Integer) - Traffic limit (0 = unlimited)
- `traffic_used_gb` (Float) - Current usage
- `device_limit` (Integer) - Maximum devices
- `connected_squads` (JSON) - Array of server squad UUIDs
- `autopay_enabled` (Boolean) - Auto-renewal
- `autopay_days_before` (Integer) - Days before expiration to charge
- `subscription_url` (String) - VPN subscription link
- `subscription_crypto_link` (String) - Crypto subscription link
- `remnawave_short_uuid` (String) - RemnaWave short UUID
- `created_at`, `updated_at` (DateTime)

**Computed Properties**:
- `is_active` - Checks if subscription is currently active
- `is_expired` - Checks if subscription has expired
- `actual_status` - Returns computed status based on dates

### Payment Models

#### Transaction
**Table**: `transactions`

All financial transactions.

**Key Fields**:
- `id` (Integer, PK)
- `user_id` (Integer, FK → users.id)
- `type` (Enum: deposit, withdrawal, subscription_payment, refund, referral_reward, poll_reward)
- `amount_kopeks` (Integer) - Transaction amount
- `payment_method` (Enum) - Payment provider
- `status` (String) - Transaction status
- `description` (Text) - Transaction description
- `metadata` (JSON) - Additional transaction data
- `created_at` (DateTime)

#### Payment Provider Models

Separate tables for each payment provider:

- **YooKassaPayment** (`yookassa_payments`) - YooKassa payments
- **CryptoBotPayment** (`cryptobot_payments`) - CryptoBot payments
- **HeleketPayment** (`heleket_payments`) - Heleket payments
- **MulenPayPayment** (`mulenpay_payments`) - MulenPay payments
- **Pal24Payment** (`pal24_payments`) - PayPalych/Pal24 payments
- **WataPayment** (`wata_payments`) - WATA payments
- **PlategaPayment** (`platega_payments`) - Platega payments

Each payment table tracks:
- Payment ID from provider
- User ID
- Amount
- Status (pending, completed, failed)
- Provider-specific metadata
- Webhook data
- Timestamps

### Promo & Marketing Models

#### PromoGroup
**Table**: `promo_groups`

Discount groups for users.

**Key Fields**:
- `id` (Integer, PK)
- `name` (String) - Group name
- `server_discount_percent` (Integer) - Server discount %
- `traffic_discount_percent` (Integer) - Traffic discount %
- `device_discount_percent` (Integer) - Device discount %
- `apply_discounts_to_addons` (Boolean) - Apply to addons
- `priority` (Integer) - Group priority
- `is_enabled` (Boolean)
- `created_at`, `updated_at` (DateTime)

**Relationships**:
- Many-to-many: `users` (via `user_promo_groups`)
- Many-to-many: `server_squads` (via `server_squad_promo_groups`)

#### PromoCode
**Table**: `promo_codes`

Promotional codes.

**Key Fields**:
- `id` (Integer, PK)
- `code` (String, Unique) - Code string
- `type` (Enum: balance, subscription_days, trial_subscription, promo_group)
- `value` (Integer) - Code value (kopeks, days, etc.)
- `max_uses` (Integer) - Maximum uses (null = unlimited)
- `used_count` (Integer) - Current uses
- `expires_at` (DateTime, Nullable) - Expiration date
- `is_enabled` (Boolean)
- `created_at`, `updated_at` (DateTime)

#### PromoCodeUse
**Table**: `promo_code_uses`

Tracks promo code usage.

**Key Fields**:
- `id` (Integer, PK)
- `promo_code_id` (FK → promo_codes.id)
- `user_id` (FK → users.id)
- `used_at` (DateTime)

#### PromoOfferTemplate
**Table**: `promo_offer_templates`

Templates for promotional offers.

**Key Fields**:
- `id` (Integer, PK)
- `name` (String) - Template name
- `discount_percent` (Integer) - Discount percentage
- `trial_days` (Integer, Nullable) - Trial period
- `balance_bonus_kopeks` (Integer, Nullable) - Balance bonus
- `is_enabled` (Boolean)
- `created_at`, `updated_at` (DateTime)

#### DiscountOffer
**Table**: `discount_offers`

Active discount offers for users.

**Key Fields**:
- `id` (Integer, PK)
- `user_id` (FK → users.id)
- `subscription_id` (FK → subscriptions.id, Nullable)
- `template_id` (FK → promo_offer_templates.id)
- `discount_percent` (Integer)
- `expires_at` (DateTime)
- `is_used` (Boolean)
- `created_at`, `updated_at` (DateTime)

#### PromoOfferLog
**Table**: `promo_offer_logs`

Log of promo offer activations.

**Key Fields**:
- `id` (Integer, PK)
- `user_id` (FK → users.id)
- `template_id` (FK → promo_offer_templates.id)
- `action` (String) - Activation action
- `created_at` (DateTime)

### Referral System

#### ReferralEarning
**Table**: `referral_earnings`

Referral commission tracking.

**Key Fields**:
- `id` (Integer, PK)
- `user_id` (FK → users.id) - Referrer
- `referred_user_id` (FK → users.id) - Referred user
- `amount_kopeks` (Integer) - Commission amount
- `transaction_id` (FK → transactions.id) - Related transaction
- `created_at` (DateTime)

### Server & Infrastructure Models

#### Squad
**Table**: `squads`

RemnaWave server squads (deprecated, use ServerSquad).

#### ServerSquad
**Table**: `server_squads`

RemnaWave server squads.

**Key Fields**:
- `id` (Integer, PK)
- `uuid` (String, Unique) - RemnaWave squad UUID
- `name` (String) - Squad name
- `country` (String) - Country code
- `region` (String, Nullable) - Region name
- `is_enabled` (Boolean) - Availability
- `is_trial_eligible` (Boolean) - Can be used for trials
- `created_at`, `updated_at` (DateTime)
- `last_sync_at` (DateTime) - Last RemnaWave sync

**Relationships**:
- Many-to-many: `promo_groups` (via `server_squad_promo_groups`)

#### SubscriptionServer
**Table**: `subscription_servers`

Historical subscription-server associations (deprecated).

### Support & Communication Models

#### Ticket
**Table**: `tickets`

Support tickets.

**Key Fields**:
- `id` (Integer, PK)
- `user_id` (FK → users.id)
- `title` (String) - Ticket title
- `status` (Enum: open, answered, closed, pending)
- `priority` (String) - low, normal, high, urgent
- `user_reply_block_permanent` (Boolean) - Permanent block
- `user_reply_block_until` (DateTime, Nullable) - Temporary block
- `created_at`, `updated_at`, `closed_at` (DateTime)
- `last_sla_reminder_at` (DateTime) - SLA reminder tracking

**Relationships**:
- One-to-many: `messages`

#### TicketMessage
**Table**: `ticket_messages`

Ticket messages.

**Key Fields**:
- `id` (Integer, PK)
- `ticket_id` (FK → tickets.id)
- `user_id` (FK → users.id, Nullable) - User or admin
- `is_from_admin` (Boolean) - Admin message flag
- `message_text` (Text) - Message content
- `attachments` (JSON, Nullable) - File attachments
- `created_at` (DateTime)

#### UserMessage
**Table**: `user_messages`

User message history for support.

**Key Fields**:
- `id` (Integer, PK)
- `user_id` (FK → users.id)
- `message_text` (Text)
- `created_at` (DateTime)

### Poll System

#### Poll
**Table**: `polls`

User polls.

**Key Fields**:
- `id` (Integer, PK)
- `title` (String) - Poll title
- `description` (Text, Nullable) - Poll description
- `reward_kopeks` (Integer, Nullable) - Reward for participation
- `is_active` (Boolean)
- `created_at`, `updated_at` (DateTime)

**Relationships**:
- One-to-many: `questions`

#### PollQuestion
**Table**: `poll_questions`

Poll questions.

**Key Fields**:
- `id` (Integer, PK)
- `poll_id` (FK → polls.id)
- `question_text` (Text) - Question text
- `question_type` (String) - Question type
- `order` (Integer) - Display order
- `created_at` (DateTime)

**Relationships**:
- One-to-many: `options`

#### PollOption
**Table**: `poll_options`

Question answer options.

**Key Fields**:
- `id` (Integer, PK)
- `question_id` (FK → poll_questions.id)
- `option_text` (Text) - Option text
- `order` (Integer) - Display order

#### PollResponse
**Table**: `poll_responses`

User poll participation.

**Key Fields**:
- `id` (Integer, PK)
- `poll_id` (FK → polls.id)
- `user_id` (FK → users.id)
- `completed_at` (DateTime)
- `reward_given` (Boolean) - Reward status

**Relationships**:
- One-to-many: `answers`

#### PollAnswer
**Table**: `poll_answers`

Individual question answers.

**Key Fields**:
- `id` (Integer, PK)
- `response_id` (FK → poll_responses.id)
- `question_id` (FK → poll_questions.id)
- `option_id` (FK → poll_options.id, Nullable)
- `answer_text` (Text, Nullable) - Free text answer
- `created_at` (DateTime)

### Content & Settings Models

#### ServiceRule
**Table**: `service_rules`

Service rules/terms.

**Key Fields**:
- `id` (Integer, PK)
- `content` (Text) - Rule content
- `language` (String) - Language code
- `is_enabled` (Boolean)
- `created_at`, `updated_at` (DateTime)

#### PrivacyPolicy
**Table**: `privacy_policies`

Privacy policy content.

**Key Fields**:
- `id` (Integer, PK)
- `content` (Text)
- `language` (String)
- `is_enabled` (Boolean)
- `created_at`, `updated_at` (DateTime)

#### PublicOffer
**Table**: `public_offers`

Public offer/terms of service.

**Key Fields**:
- `id` (Integer, PK)
- `content` (Text)
- `language` (String)
- `is_enabled` (Boolean)
- `created_at`, `updated_at` (DateTime)

#### FaqSetting
**Table**: `faq_settings`

FAQ configuration.

**Key Fields**:
- `id` (Integer, PK)
- `is_enabled` (Boolean)
- `created_at`, `updated_at` (DateTime)

#### FaqPage
**Table**: `faq_pages`

FAQ pages.

**Key Fields**:
- `id` (Integer, PK)
- `question` (String) - Question text
- `answer` (Text) - Answer text
- `language` (String)
- `order` (Integer) - Display order
- `is_enabled` (Boolean)
- `created_at`, `updated_at` (DateTime)

#### WelcomeText
**Table**: `welcome_texts`

Welcome message content.

**Key Fields**:
- `id` (Integer, PK)
- `content` (Text)
- `language` (String)
- `is_enabled` (Boolean)
- `created_at`, `updated_at` (DateTime)

### System & Administration Models

#### SystemSetting
**Table**: `system_settings`

System configuration stored in database.

**Key Fields**:
- `id` (Integer, PK)
- `key` (String, Unique) - Setting key
- `value` (Text) - Setting value (JSON)
- `description` (Text, Nullable)
- `created_at`, `updated_at` (DateTime)

#### MonitoringLog
**Table**: `monitoring_logs`

RemnaWave monitoring logs.

**Key Fields**:
- `id` (Integer, PK)
- `status` (String) - Monitoring status
- `message` (Text) - Log message
- `created_at` (DateTime)

#### SentNotification
**Table**: `sent_notifications`

Notification delivery tracking.

**Key Fields**:
- `id` (Integer, PK)
- `user_id` (FK → users.id)
- `notification_type` (String) - Notification type
- `message_id` (BigInteger, Nullable) - Telegram message ID
- `sent_at` (DateTime)
- `status` (String) - Delivery status

#### BroadcastHistory
**Table**: `broadcast_history`

Broadcast message history.

**Key Fields**:
- `id` (Integer, PK)
- `admin_id` (FK → users.id) - Admin who sent
- `message_text` (Text) - Broadcast content
- `target_type` (String) - Target audience
- `sent_count` (Integer) - Messages sent
- `failed_count` (Integer) - Failed sends
- `created_at` (DateTime)

#### SupportAuditLog
**Table**: `support_audit_logs`

Support system audit trail.

**Key Fields**:
- `id` (Integer, PK)
- `admin_id` (FK → users.id, Nullable) - Admin who performed action
- `action` (String) - Action type
- `target_type` (String) - Target entity
- `target_id` (Integer) - Target ID
- `details` (JSON, Nullable) - Action details
- `created_at` (DateTime)

### Campaign & Marketing Models

#### AdvertisingCampaign
**Table**: `advertising_campaigns`

Marketing campaigns.

**Key Fields**:
- `id` (Integer, PK)
- `name` (String) - Campaign name
- `deeplink` (String, Unique) - Campaign deeplink
- `reward_type` (String) - Reward type (subscription, balance)
- `reward_value` (Integer) - Reward value
- `is_active` (Boolean)
- `created_at`, `updated_at` (DateTime)

**Relationships**:
- One-to-many: `registrations`

#### AdvertisingCampaignRegistration
**Table**: `advertising_campaign_registrations`

Campaign user registrations.

**Key Fields**:
- `id` (Integer, PK)
- `campaign_id` (FK → advertising_campaigns.id)
- `user_id` (FK → users.id)
- `utm_source` (String, Nullable) - UTM source
- `utm_medium` (String, Nullable) - UTM medium
- `utm_campaign` (String, Nullable) - UTM campaign
- `reward_given` (Boolean) - Reward status
- `created_at` (DateTime)

### Subscription Management Models

#### SubscriptionConversion
**Table**: `subscription_conversions`

Trial to paid conversion tracking.

**Key Fields**:
- `id` (Integer, PK)
- `user_id` (FK → users.id)
- `trial_end_date` (DateTime) - Trial end
- `converted_at` (DateTime, Nullable) - Conversion time
- `converted` (Boolean) - Conversion status

#### SubscriptionTemporaryAccess
**Table**: `subscription_temporary_accesses`

Temporary server access grants.

**Key Fields**:
- `id` (Integer, PK)
- `subscription_id` (FK → subscriptions.id)
- `squad_uuid` (String) - Server squad UUID
- `expires_at` (DateTime) - Access expiration
- `created_at` (DateTime)

### API & Security Models

#### WebApiToken
**Table**: `web_api_tokens`

API authentication tokens.

**Key Fields**:
- `id` (Integer, PK)
- `token` (String, Unique) - API token hash
- `name` (String) - Token name/description
- `is_active` (Boolean) - Active status
- `last_used_at` (DateTime, Nullable) - Last usage
- `created_at`, `updated_at` (DateTime)

#### MainMenuButton
**Table**: `main_menu_buttons`

Custom main menu buttons.

**Key Fields**:
- `id` (Integer, PK)
- `text` (String) - Button text
- `action_type` (Enum: url, mini_app)
- `action_value` (String) - URL or Mini App path
- `visibility` (Enum: all, admins, subscribers)
- `order` (Integer) - Display order
- `is_enabled` (Boolean)
- `created_at`, `updated_at` (DateTime)

## Database Relationships Summary

### One-to-One
- User ↔ Subscription (one user, one subscription)

### One-to-Many
- User → Transactions
- User → Tickets
- User → ReferralEarnings
- User → PollResponses
- Subscription → DiscountOffers
- Ticket → TicketMessages
- Poll → PollQuestions
- PollQuestion → PollOptions
- PollResponse → PollAnswers
- AdvertisingCampaign → AdvertisingCampaignRegistrations

### Many-to-Many
- User ↔ PromoGroup (via `user_promo_groups`)
- ServerSquad ↔ PromoGroup (via `server_squad_promo_groups`)

## Indexes

Key indexes for performance:
- `users.telegram_id` (unique)
- `users.referral_code` (unique)
- `users.promo_group_id`
- `subscriptions.user_id` (unique)
- `transactions.user_id`
- `tickets.user_id`
- `server_squads.uuid` (unique)
- `web_api_tokens.token` (unique)

## Migration System

Database migrations managed via Alembic:
- Location: `migrations/alembic/`
- Config: `alembic.ini`
- Universal migration system: `app/database/universal_migration.py`

## Database Modes

The application supports two database modes:
- **PostgreSQL** (production): Full-featured, async via asyncpg
- **SQLite** (development/testing): Lightweight, async via aiosqlite

Mode selection via `DATABASE_MODE` environment variable.

