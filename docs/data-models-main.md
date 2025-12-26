# Data Models - Main

## Overview

This project uses SQLAlchemy ORM with PostgreSQL (primary) or SQLite (development/fallback) for data persistence. All models are defined in `app/database/models.py` using SQLAlchemy declarative base.

## Database Configuration

- **Primary Database:** PostgreSQL 15+ (via asyncpg driver)
- **Fallback Database:** SQLite (via aiosqlite driver)
- **ORM:** SQLAlchemy 2.0.43
- **Migrations:** Alembic 1.16.5
- **Mode:** Auto-detection based on `DATABASE_MODE` setting

## Core Models

### User

**Table:** `users`

Primary user entity representing Telegram bot users.

**Key Fields:**
- `id` (Integer, PK) - Internal user ID
- `telegram_id` (BigInteger, Unique, Indexed) - Telegram user ID
- `username` (String) - Telegram username
- `first_name`, `last_name` (String) - User's name
- `status` (String) - User status: `active`, `blocked`, `deleted`
- `language` (String) - Interface language (default: "ru")
- `balance_toman` (Integer) - User balance in toman
- `referral_code` (String, Unique) - Referral code for this user
- `referred_by_id` (Integer, FK to users.id) - Referrer user ID
- `promo_group_id` (Integer, FK) - Primary promo group
- `remnawave_uuid` (String, Unique) - UUID in RemnaWave panel
- `has_had_paid_subscription` (Boolean) - Flag for conversion tracking
- `has_made_first_topup` (Boolean) - First topup flag
- `referral_commission_percent` (Integer) - Custom referral commission
- `promo_offer_discount_percent` (Integer) - Active promo offer discount
- `lifetime_used_traffic_bytes` (BigInteger) - Total traffic used
- `created_at`, `updated_at`, `last_activity` (DateTime) - Timestamps

**Relationships:**
- `subscription` (One-to-One) - User's subscription
- `transactions` (One-to-Many) - User's transaction history
- `referral_earnings` (One-to-Many) - Earnings from referrals
- `promo_group` (Many-to-One) - Primary promo group
- `user_promo_groups` (Many-to-Many) - Additional promo groups
- `poll_responses` (One-to-Many) - Poll responses

### Subscription

**Table:** `subscriptions`

Represents user VPN subscriptions (trial or paid).

**Key Fields:**
- `id` (Integer, PK)
- `user_id` (Integer, FK to users.id, Unique) - One subscription per user
- `status` (String) - Status: `trial`, `active`, `expired`, `disabled`, `pending`
- `is_trial` (Boolean) - Whether this is a trial subscription
- `start_date`, `end_date` (DateTime) - Subscription period
- `traffic_limit_gb` (Integer) - Traffic limit (0 = unlimited)
- `traffic_used_gb` (Float) - Current traffic usage
- `device_limit` (Integer) - Maximum allowed devices
- `connected_squads` (JSON) - Array of connected squad UUIDs
- `subscription_url` (String) - VPN subscription link
- `subscription_crypto_link` (String) - Crypto payment link
- `autopay_enabled` (Boolean) - Auto-renewal enabled
- `autopay_days_before` (Integer) - Days before expiry to charge
- `remnawave_short_uuid` (String) - Short UUID in RemnaWave panel
- `created_at`, `updated_at` (DateTime)

**Relationships:**
- `user` (Many-to-One) - Subscription owner
- `discount_offers` (One-to-Many) - Active discount offers
- `temporary_accesses` (One-to-Many) - Temporary squad access

**Properties:**
- `is_active` - Checks if subscription is currently active
- `is_expired` - Checks if subscription has expired
- `actual_status` - Calculated status considering dates
- `days_left` - Days remaining until expiry
- `traffic_used_percent` - Percentage of traffic limit used

### Transaction

**Table:** `transactions`

Financial transaction records for all user operations.

**Key Fields:**
- `id` (Integer, PK)
- `user_id` (Integer, FK to users.id)
- `type` (String) - Transaction type: `deposit`, `withdrawal`, `subscription_payment`, `refund`, `referral_reward`, `poll_reward`
- `amount_toman` (Integer) - Transaction amount in toman
- `description` (Text) - Transaction description
- `payment_method` (String) - Payment method used
- `external_id` (String) - External payment system ID
- `is_completed` (Boolean) - Transaction completion status
- `created_at`, `completed_at` (DateTime)

**Relationships:**
- `user` (Many-to-One) - Transaction owner

### PromoCode

**Table:** `promocodes`

Promotional codes for discounts and bonuses.

**Key Fields:**
- `id` (Integer, PK)
- `code` (String, Unique, Indexed) - Promo code string
- `type` (String) - Type: `balance`, `subscription_days`, `trial_subscription`, `promo_group`
- `balance_bonus_toman` (Integer) - Balance bonus amount in toman
- `subscription_days` (Integer) - Days to add to subscription
- `max_uses` (Integer) - Maximum usage count
- `current_uses` (Integer) - Current usage count
- `valid_from`, `valid_until` (DateTime) - Validity period
- `is_active` (Boolean) - Active status
- `created_by` (Integer, FK to users.id) - Creator admin
- `promo_group_id` (Integer, FK) - Promo group to assign

**Relationships:**
- `uses` (One-to-Many) - PromoCodeUse records
- `promo_group` (Many-to-One) - Associated promo group

### PromoGroup

**Table:** `promo_groups`

Discount groups with configurable discounts for servers, traffic, devices, and periods.

**Key Fields:**
- `id` (Integer, PK)
- `name` (String, Unique) - Group name
- `priority` (Integer, Indexed) - Priority for auto-assignment
- `server_discount_percent` (Integer) - Server discount percentage
- `traffic_discount_percent` (Integer) - Traffic discount percentage
- `device_discount_percent` (Integer) - Device discount percentage
- `period_discounts` (JSON) - Period-based discounts (e.g., {60: 10, 90: 20})
- `auto_assign_total_spent_toman` (Integer) - Auto-assign threshold in toman
- `apply_discounts_to_addons` (Boolean) - Apply discounts to addons
- `is_default` (Boolean) - Default group flag

**Relationships:**
- `users` (One-to-Many) - Users in this group
- `user_promo_groups` (Many-to-Many) - Additional user assignments
- `server_squads` (Many-to-Many) - Allowed server squads

## Payment Models

Multiple payment provider models for different payment systems:

### YooKassaPayment
**Table:** `yookassa_payments`
- Stores YooKassa payment records
- Links to transactions and users
- Tracks payment status and confirmation

### CryptoBotPayment
**Table:** `cryptobot_payments`
- Crypto payment records (USDT, TON, BTC, ETH, etc.)
- Invoice tracking and status

### MulenPayPayment
**Table:** `mulenpay_payments`
- MulenPay payment records
- SBP payment tracking

### Pal24Payment
**Table:** `pal24_payments`
- PayPalych/Pal24 payment records
- Bill tracking and status

### HeleketPayment
**Table:** `heleket_payments`
- Heleket crypto payment records
- Exchange rate and discount tracking

### WataPayment
**Table:** `wata_payments`
- WATA payment records
- Payment link tracking

### PlategaPayment
**Table:** `platega_payments`
- Platega.io payment records
- Payment method code tracking

## Support & Tickets

### Ticket
**Table:** `tickets`

Support ticket system.

**Key Fields:**
- `id` (Integer, PK)
- `user_id` (Integer, FK) - Ticket owner
- `title` (String) - Ticket title
- `status` (String) - Status: `open`, `answered`, `closed`, `pending`
- `priority` (String) - Priority: `low`, `normal`, `high`, `urgent`
- `user_reply_block_permanent` (Boolean) - Permanent reply block
- `user_reply_block_until` (DateTime) - Temporary reply block
- `created_at`, `updated_at`, `closed_at` (DateTime)

**Relationships:**
- `user` (Many-to-One) - Ticket owner
- `messages` (One-to-Many) - TicketMessage records

### TicketMessage
**Table:** `ticket_messages`

Messages within support tickets.

**Key Fields:**
- `id` (Integer, PK)
- `ticket_id` (Integer, FK)
- `user_id` (Integer, FK)
- `message_text` (Text) - Message content
- `is_from_admin` (Boolean) - Admin message flag
- `has_media` (Boolean) - Media attachment flag
- `media_type`, `media_file_id`, `media_caption` - Media details
- `created_at` (DateTime)

## Server & Squad Management

### ServerSquad
**Table:** `server_squads`

VPN server squads (groups of servers).

**Key Fields:**
- `id` (Integer, PK)
- `squad_uuid` (String, Unique, Indexed) - RemnaWave squad UUID
- `display_name` (String) - Display name
- `country_code` (String) - Country code
- `is_available` (Boolean) - Availability status
- `is_trial_eligible` (Boolean) - Eligible for trial
- `price_toman` (Integer) - Squad price in toman
- `max_users`, `current_users` (Integer) - User limits
- `sort_order` (Integer) - Display order

**Relationships:**
- `allowed_promo_groups` (Many-to-Many) - Promo groups with access

## Additional Models

### Poll System
- `Poll` - Poll definitions
- `PollQuestion` - Questions within polls
- `PollOption` - Answer options
- `PollResponse` - User responses
- `PollAnswer` - Individual answers

### Campaigns
- `AdvertisingCampaign` - Advertising campaigns with deeplink bonuses
- `AdvertisingCampaignRegistration` - User registrations via campaigns

### Content Management
- `ServiceRule` - Service rules/terms
- `PrivacyPolicy` - Privacy policy documents
- `PublicOffer` - Public offer/terms
- `FaqSetting` - FAQ configuration
- `FaqPage` - Individual FAQ pages
- `WelcomeText` - Welcome message templates
- `UserMessage` - Custom main menu messages
- `MainMenuButton` - Custom main menu buttons

### System
- `SystemSetting` - Runtime-configurable settings
- `MonitoringLog` - Bot monitoring event logs
- `WebApiToken` - API authentication tokens
- `SentNotification` - Sent subscription notifications
- `SubscriptionEvent` - Subscription lifecycle events
- `SupportAuditLog` - Support moderator action logs
- `BroadcastHistory` - Broadcast message history

### Promo Offers
- `DiscountOffer` - Personal discount offers
- `PromoOfferTemplate` - Offer templates
- `PromoOfferLog` - Offer operation audit log
- `SubscriptionTemporaryAccess` - Temporary squad access

### Other
- `SubscriptionConversion` - Trial-to-paid conversion tracking
- `ReferralEarning` - Referral commission earnings
- `UserPromoGroup` - Many-to-many relationship between users and promo groups

## Database Migrations

Migrations are managed via Alembic. Migration files are located in `migrations/alembic/versions/`.

Key migrations include:
- Promo groups and user foreign keys
- Period discounts to promo groups
- Advertising campaigns
- Sent notifications table
- Various schema updates

## Indexes

Key indexes for performance:
- `users.telegram_id` (unique)
- `users.referral_code` (unique)
- `users.promo_group_id`
- `subscriptions.user_id` (unique)
- `transactions.user_id`
- `promocodes.code` (unique)
- `tickets.user_id`
- `server_squads.squad_uuid` (unique)
- Various foreign key indexes
