# نقشه کامل Handlers، Keyboards و States

**تاریخ:** 2025-12-15  
**نسخه:** 1.0

---

## 📋 فهرست

1. [Main Menu Flow](#main-menu-flow)
2. [Registration Flow](#registration-flow)
3. [Subscription Purchase Flow](#subscription-purchase-flow)
4. [Balance Top-up Flow](#balance-top-up-flow)
5. [Admin Panel Flow](#admin-panel-flow)
6. [Support & Tickets Flow](#support--tickets-flow)
7. [Referral Flow](#referral-flow)

---

## 🏠 Main Menu Flow

### Entry Point: `/start`

```
Handler: app/handlers/start.py
State: None → RegistrationStates (if new user)
Callback: None (command handler)
```

### Main Menu Keyboard

```python
# app/handlers/menu.py
# Callback patterns:
"menu_subscription"     → Subscription Menu
"menu_balance"          → Balance Menu  
"menu_referral"         → Referral Menu (if enabled)
"menu_support"          → Support Menu (if enabled)
"menu_profile"          → User Profile
"menu_faq"              → FAQ (if enabled)
"admin_panel"           → Admin Panel (if admin)
```

**Multi-Tenant Changes Required:**
- [ ] Feature flag check برای `referral`
- [ ] Feature flag check برای `support`
- [ ] Feature flag check برای `faq`
- [ ] bot_id در همه handlers

---

## 📝 Registration Flow

### Flow Diagram

```
/start
    ↓
[New User?] ──No──→ [Main Menu]
    │
   Yes
    ↓
[Language Selection]
State: RegistrationStates.waiting_for_language
    ↓
[Rules Accept]
State: RegistrationStates.waiting_for_rules_accept
    ↓
[Privacy Policy Accept] (if enabled)
State: RegistrationStates.waiting_for_privacy_policy_accept
    ↓
[Referral Code] (if enabled)
State: RegistrationStates.waiting_for_referral_code
    ↓
[Create User with bot_id]
    ↓
[Main Menu]
```

### Handlers & Callbacks

| Step | Handler File | State | Callback Pattern |
|------|--------------|-------|------------------|
| Start | `start.py` | None | `/start` command |
| Language | `start.py` | `waiting_for_language` | `lang_*` |
| Rules | `start.py` | `waiting_for_rules_accept` | `accept_rules`, `decline_rules` |
| Privacy | `start.py` | `waiting_for_privacy_policy_accept` | `accept_privacy`, `decline_privacy` |
| Referral | `start.py` | `waiting_for_referral_code` | text input |

**Multi-Tenant Changes Required:**
- [ ] `create_user(db, ..., bot_id=bot_id)`
- [ ] Feature flag check برای `privacy_policy`
- [ ] Feature flag check برای `referral`
- [ ] دریافت `rules_text` از `bot_configurations`
- [ ] دریافت `privacy_policy` از `bot_configurations`

---

## 💳 Subscription Purchase Flow

### Flow Diagram

```
[Subscription Menu]
    ↓
[Select Period] (Days)
State: SubscriptionStates.selecting_period
    ↓
[Select Traffic] (GB)
State: SubscriptionStates.selecting_traffic
    ↓
[Select Countries/Servers]
State: SubscriptionStates.selecting_countries
    ↓
[Select Devices]
State: SubscriptionStates.selecting_devices
    ↓
[Confirm Purchase]
State: SubscriptionStates.confirming_purchase
    ↓
[Select Payment Method]
    ↓
[Payment Flow] (Balance/Stars/External)
    ↓
[Create Subscription]
```

### Handlers & Callbacks

| Step | Handler File | State | Callback Pattern |
|------|--------------|-------|------------------|
| Menu | `menu.py` | None | `menu_subscription` |
| Period | `subscription/purchase.py` | `selecting_period` | `period_*` |
| Traffic | `subscription/traffic.py` | `selecting_traffic` | `traffic_*` |
| Countries | `subscription/countries.py` | `selecting_countries` | `country_*` |
| Devices | `subscription/devices.py` | `selecting_devices` | `device_*` |
| Confirm | `subscription/summary.py` | `confirming_purchase` | `confirm_purchase`, `cancel_purchase` |
| Payment | `balance/main.py` | varies | `pay_*` |

**Multi-Tenant Changes Required:**
- [ ] Plans از `bot_plans` یا global plans
- [ ] Pricing از `bot_configurations` یا global
- [ ] Feature flags برای payment methods
- [ ] `create_subscription(db, ..., bot_id=bot_id)`
- [ ] `create_transaction(db, ..., bot_id=bot_id)`

---

## 💰 Balance Top-up Flow

### Payment Methods Mapping

```
[Balance Menu]
    ↓
[Select Payment Method]
    ├── Stars         → balance/stars.py
    ├── YooKassa      → balance/yookassa.py
    ├── CryptoBot     → balance/cryptobot.py
    ├── Card-to-Card  → balance/card_to_card.py   [NEW]
    ├── Zarinpal      → balance/zarinpal.py       [NEW]
    ├── Heleket       → balance/heleket.py
    ├── PAL24         → balance/pal24.py
    ├── Tribute       → balance/tribute.py
    └── Wata          → balance/wata.py
```

### Handlers & Callbacks

| Method | Handler File | Feature Flag | Callback Pattern |
|--------|--------------|--------------|------------------|
| Stars | `balance/stars.py` | `telegram_stars` | `pay_stars`, `stars_*` |
| YooKassa | `balance/yookassa.py` | `yookassa` | `pay_yookassa`, `yookassa_*` |
| CryptoBot | `balance/cryptobot.py` | `cryptobot` | `pay_cryptobot`, `crypto_*` |
| Card-to-Card | `balance/card_to_card.py` | `card_to_card` | `pay_card`, `card_*` |
| Zarinpal | `balance/zarinpal.py` | `zarinpal` | `pay_zarinpal`, `zp_*` |
| Heleket | `balance/heleket.py` | `heleket` | `pay_heleket`, `hlk_*` |
| PAL24 | `balance/pal24.py` | `pal24` | `pay_pal24`, `pal_*` |

### Card-to-Card Flow (Detailed)

```
[Select Card-to-Card]
Callback: pay_card
    ↓
[Check Feature Flag]
await TenantFeatureService.is_feature_enabled(db, bot_id, 'card_to_card')
    ↓
[Get Card with Rotation]
card = await get_next_card_for_rotation(db, bot_id, strategy)
    ↓
[Display Card Info]
"شماره کارت: XXXX-XXXX-XXXX-XXXX"
"به نام: ..."
    ↓
[Wait for Receipt]
State: BalanceStates.waiting_for_card_to_card_receipt
    ↓
[User Sends Receipt] (Photo/Text)
    ↓
[Create CardToCardPayment]
status='pending'
    ↓
[Send Admin Notification]
to: bot_config.admin_chat_id / bot_config.card_receipt_topic_id
    ↓
[Admin Review]
Callback: approve_card_payment:{id}, reject_card_payment:{id}
    ↓
[Update Payment Status]
    ↓
[Notify User]
```

**States:**
```python
class BalanceStates(StatesGroup):
    waiting_for_card_to_card_receipt = State()
```

**Callbacks:**
```python
"pay_card"                      # Start card payment
"card_select:{amount}"          # Select amount
"approve_card_payment:{id}"     # Admin approve
"reject_card_payment:{id}"      # Admin reject
"card_payment_details:{id}"     # View details
```

---

## 👨‍💼 Admin Panel Flow

### Admin Menu Structure

```
[Admin Panel]
    ├── 👥 Users
    │   ├── List Users
    │   ├── Search User
    │   ├── User Details
    │   │   ├── Edit Balance
    │   │   ├── Edit Subscription
    │   │   ├── Send Message
    │   │   └── Block/Unblock
    │   └── Statistics
    │
    ├── 📊 Reports
    │   ├── Daily Report
    │   ├── Weekly Report
    │   ├── Monthly Report
    │   └── Export Data
    │
    ├── 🎟️ Promo
    │   ├── Promocodes
    │   │   ├── Create
    │   │   ├── List
    │   │   └── Edit/Delete
    │   └── Promo Groups
    │       ├── Create
    │       ├── List
    │       └── Edit/Delete
    │
    ├── 📢 Communications
    │   ├── Broadcast Message
    │   ├── Campaigns
    │   └── Polls
    │
    ├── ⚙️ Settings
    │   ├── Bot Configuration    ← bot_configurations
    │   ├── Pricing              ← per-tenant prices?
    │   ├── Notifications
    │   ├── Welcome Text
    │   ├── Rules
    │   ├── Privacy Policy
    │   └── FAQ
    │
    ├── 🖥️ System (Master Only)
    │   ├── Servers
    │   ├── Remnawave Sync
    │   ├── Backup
    │   └── Logs
    │
    └── 🤖 Tenant Bots (Master Only)  [NEW]
        ├── List Bots
        ├── Create Bot
        ├── Bot Details
        │   ├── Settings
        │   ├── Payment Cards
        │   ├── Feature Flags
        │   └── Test Status
        └── Update Webhooks
```

### Handler Files & Callbacks

| Menu | Handler File | Callback Pattern |
|------|--------------|------------------|
| Main | `admin/main.py` | `admin_panel`, `admin_*` |
| Users | `admin/users.py` | `admin_users_*` |
| Reports | `admin/reports.py` | `admin_reports_*` |
| Promocodes | `admin/promocodes.py` | `admin_promo_*` |
| Promo Groups | `admin/promo_groups.py` | `admin_pg_*` |
| Broadcast | `admin/messages.py` | `admin_broadcast_*` |
| Campaigns | `admin/campaigns.py` | `admin_campaign_*` |
| Settings | `admin/bot_configuration.py` | `admin_config_*` |
| Pricing | `admin/pricing.py` | `admin_pricing_*` |
| Servers | `admin/servers.py` | `admin_server_*` |
| **Tenant Bots** | `admin/tenant_bots.py` | `admin_tenant_*` |

### Critical: Admin Handlers with bot_id Issues

| Handler | Current Issue | Fix Required |
|---------|---------------|--------------|
| `admin/users.py` | `get_users_list(db)` | `get_users_list(db, bot_id=bot_id)` |
| `admin/messages.py` | `get_target_users(db)` | `get_target_users(db, bot_id=bot_id)` |
| `admin/statistics.py` | Global stats | Filter by bot_id |
| `admin/subscriptions.py` | All subscriptions | Filter by bot_id |
| `admin/promocodes.py` | All promocodes | Filter by bot_id |

### Tenant Bots Callbacks (New)

```python
# Menu
"admin_tenant_bots_menu"            # Main menu
"admin_tenant_bots_list"            # List all bots
"admin_tenant_bots_list:{page}"     # Paginated list
"admin_tenant_bots_create"          # Start create flow

# Bot Detail
"admin_tenant_bot_detail:{id}"      # Bot details
"admin_tenant_bot_settings:{id}"    # Bot settings
"admin_tenant_bot_cards:{id}"       # Payment cards
"admin_tenant_bot_cards:{id}:{page}"# Paginated cards
"admin_tenant_bot_test:{id}"        # Test bot status

# Bot Actions
"admin_tenant_bot_activate:{id}"    # Activate bot
"admin_tenant_bot_deactivate:{id}"  # Deactivate bot
"admin_tenant_bot_toggle_card:{id}" # Toggle card-to-card
"admin_tenant_bot_toggle_zarinpal:{id}" # Toggle zarinpal

# Card Management
"admin_tenant_bot_card_add:{bot_id}"    # Add card
"admin_tenant_bot_card_detail:{id}"     # Card detail
"admin_tenant_bot_card_activate:{id}"   # Activate card
"admin_tenant_bot_card_deactivate:{id}" # Deactivate card

# Webhooks
"admin_tenant_bots_update_webhooks" # Update all webhooks
```

---

## 🎫 Support & Tickets Flow

### Support Chat Flow

```
[Support Menu]
Callback: menu_support
    ↓
[Check Feature Flag]
await TenantFeatureService.is_feature_enabled(db, bot_id, 'support_chat')
    ↓
[Show Support Options]
    ├── Chat with Support → Direct message to support_username
    └── Create Ticket → Ticket flow
```

### Ticket Flow

```
[Create Ticket]
Callback: create_ticket
    ↓
[Enter Title]
State: TicketStates.waiting_for_title
    ↓
[Enter Message]
State: TicketStates.waiting_for_message
    ↓
[Create Ticket in DB]
await create_ticket(db, user_id, bot_id, title, message)
    ↓
[Send to Admin]
Forward to bot_config.admin_chat_id
```

### Handlers & Callbacks

| Action | Handler File | State | Callback |
|--------|--------------|-------|----------|
| Support Menu | `support.py` | None | `menu_support` |
| Create Ticket | `tickets.py` | `waiting_for_title` | `create_ticket` |
| Title Input | `tickets.py` | `waiting_for_message` | text |
| Message Input | `tickets.py` | None | text |
| View Ticket | `tickets.py` | None | `ticket_view:{id}` |
| Reply | `tickets.py` | `waiting_for_reply` | `ticket_reply:{id}` |

**Multi-Tenant Changes:**
- [ ] Feature flag check
- [ ] `create_ticket(db, ..., bot_id=bot_id)`
- [ ] Forward to correct admin based on bot_config

---

## 🔗 Referral Flow

### Flow Diagram

```
[Referral Menu]
Callback: menu_referral
    ↓
[Check Feature Flag]
await TenantFeatureService.is_feature_enabled(db, bot_id, 'referral')
    ↓
[Show Referral Info]
    ├── Your Code: XXXX
    ├── Invited: X users
    ├── Earnings: X  Toman
    └── Share Link
    
[New User with Referral Code]
/start ref_XXXX
    ↓
[Validate Code belongs to same bot_id]
    ↓
[Link Referrer to New User]
```

### Handlers & Callbacks

| Action | Handler File | Callback |
|--------|--------------|----------|
| Menu | `referral.py` | `menu_referral` |
| My Code | `referral.py` | `ref_my_code` |
| Share | `referral.py` | `ref_share` |
| Stats | `referral.py` | `ref_stats` |
| Enter Code | `promocode.py` | `enter_referral` |

**Multi-Tenant Changes:**
- [ ] Feature flag check
- [ ] Validate referral code belongs to same bot
- [ ] `bot_id` در همه queries

---

## 🎯 Keyboard Generation Functions

### Current Keyboards (Need Updates)

```python
# app/keyboards/inline.py

# Current - Static
def get_payment_methods_keyboard(language):
    buttons = [
        [InlineKeyboardButton("Stars", callback_data="pay_stars")],
        [InlineKeyboardButton("YooKassa", callback_data="pay_yookassa")],
        # ...
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Required - Dynamic with Feature Flags
async def get_payment_methods_keyboard(db, bot_id, language):
    buttons = []
    
    if await TenantFeatureService.is_feature_enabled(db, bot_id, 'telegram_stars'):
        buttons.append([InlineKeyboardButton("Stars", callback_data="pay_stars")])
    
    if await TenantFeatureService.is_feature_enabled(db, bot_id, 'yookassa'):
        buttons.append([InlineKeyboardButton("YooKassa", callback_data="pay_yookassa")])
    
    if await TenantFeatureService.is_feature_enabled(db, bot_id, 'card_to_card'):
        buttons.append([InlineKeyboardButton("کارت به کارت", callback_data="pay_card")])
    
    if await TenantFeatureService.is_feature_enabled(db, bot_id, 'zarinpal'):
        buttons.append([InlineKeyboardButton("زرین‌پال", callback_data="pay_zarinpal")])
    
    # ...
    return InlineKeyboardMarkup(inline_keyboard=buttons)
```

### Keyboards That Need Feature Flag Checks

| Keyboard | File | Features to Check |
|----------|------|-------------------|
| Main Menu | `reply.py` | `referral`, `support`, `faq` |
| Payment Methods | `inline.py` | All payment methods |
| Subscription Options | `inline.py` | `autopay`, `trial` |
| Admin Menu | `admin.py` | Master-only items |

---

## 📊 State Machine Summary

### User States

```
                    ┌─────────────────────────────────────┐
                    │         RegistrationStates          │
                    ├─────────────────────────────────────┤
                    │ waiting_for_language                │
                    │ waiting_for_rules_accept            │
                    │ waiting_for_privacy_policy_accept   │
                    │ waiting_for_referral_code           │
                    └─────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────┐    ┌─────────────────────────────────────┐
│   PromoCodeStates  │    │         SubscriptionStates          │
├────────────────────┤    ├─────────────────────────────────────┤
│ waiting_for_code   │    │ selecting_period                    │
│ waiting_for_ref    │    │ selecting_traffic                   │
└────────────────────┘    │ selecting_countries                 │
                          │ selecting_devices                   │
                          │ confirming_purchase                 │
                          │ adding_countries                    │
                          │ adding_traffic                      │
                          │ adding_devices                      │
                          │ extending_subscription              │
                          │ confirming_traffic_reset            │
                          │ cart_saved_for_topup                │
                          └─────────────────────────────────────┘

┌─────────────────────────────────────┐    ┌─────────────────────┐
│          BalanceStates              │    │    SupportStates    │
├─────────────────────────────────────┤    ├─────────────────────┤
│ waiting_for_amount                  │    │ waiting_for_message │
│ waiting_for_pal24_method            │    └─────────────────────┘
│ waiting_for_platega_method          │
│ waiting_for_stars_payment           │    ┌─────────────────────┐
│ waiting_for_support_request         │    │    TicketStates     │
│ waiting_for_card_to_card_receipt    │    ├─────────────────────┤
└─────────────────────────────────────┘    │ waiting_for_title   │
                                           │ waiting_for_message │
                                           │ waiting_for_reply   │
                                           └─────────────────────┘
```

### Admin States

```
┌─────────────────────────────────────────────────────────────────┐
│                        AdminStates                               │
├─────────────────────────────────────────────────────────────────┤
│ User Management                                                  │
│ ├── waiting_for_user_search                                     │
│ ├── sending_user_message                                        │
│ ├── editing_user_balance                                        │
│ ├── extending_subscription                                      │
│ ├── adding_traffic                                              │
│ ├── granting_subscription                                       │
│ └── editing_user_subscription                                   │
├─────────────────────────────────────────────────────────────────┤
│ Promocode Management                                            │
│ ├── creating_promocode                                          │
│ ├── setting_promocode_type                                      │
│ ├── setting_promocode_value                                     │
│ ├── setting_promocode_uses                                      │
│ └── setting_promocode_expiry                                    │
├─────────────────────────────────────────────────────────────────┤
│ Campaign Management                                             │
│ ├── creating_campaign_name                                      │
│ ├── creating_campaign_start                                     │
│ └── ... (many more)                                             │
├─────────────────────────────────────────────────────────────────┤
│ Broadcast                                                       │
│ ├── waiting_for_broadcast_message                               │
│ ├── waiting_for_broadcast_media                                 │
│ └── confirming_broadcast                                        │
├─────────────────────────────────────────────────────────────────┤
│ Promo Groups                                                    │
│ ├── creating_promo_group_name                                   │
│ ├── creating_promo_group_priority                               │
│ └── ... (many more)                                             │
├─────────────────────────────────────────────────────────────────┤
│ Tenant Bots (NEW)                                               │
│ ├── waiting_for_bot_name                                        │
│ └── waiting_for_bot_token                                       │
├─────────────────────────────────────────────────────────────────┤
│ Settings                                                        │
│ ├── editing_rules_page                                          │
│ ├── editing_privacy_policy                                      │
│ ├── editing_public_offer                                        │
│ ├── editing_welcome_text                                        │
│ └── ... (many more)                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📝 Migration Checklist

### Priority 1: Fix Isolation (Critical)

| File | Function | Change |
|------|----------|--------|
| `admin/users.py` | `get_users_list()` | Add `bot_id` parameter |
| `admin/users.py` | `search_user()` | Add `bot_id` parameter |
| `admin/messages.py` | `get_target_users()` | Add `bot_id` parameter |
| `admin/statistics.py` | All queries | Filter by `bot_id` |
| `admin/subscriptions.py` | All queries | Filter by `bot_id` |

### Priority 2: Feature Flags

| File | Setting | Feature Flag |
|------|---------|--------------|
| `balance/stars.py` | `settings.TELEGRAM_STARS_ENABLED` | `telegram_stars` |
| `balance/yookassa.py` | `settings.is_yookassa_enabled()` | `yookassa` |
| `balance/cryptobot.py` | `settings.is_cryptobot_enabled()` | `cryptobot` |
| `referral.py` | `settings.REFERRAL_ENABLED` | `referral` |
| `subscription/autopay.py` | `settings.AUTOPAY_ENABLED` | `autopay` |

### Priority 3: Keyboards

| File | Function | Update |
|------|----------|--------|
| `keyboards/inline.py` | `get_payment_keyboard()` | Make async, add feature checks |
| `keyboards/inline.py` | `get_main_menu_keyboard()` | Make async, add feature checks |
| `keyboards/reply.py` | `get_main_keyboard()` | Make async, add feature checks |

---

**تاریخ ایجاد:** 2025-12-15  
**آخرین به‌روزرسانی:** 2025-12-15









