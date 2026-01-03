# Telegram Keyboards & Buttons Map

This document gives a **button‑centric** view of the bot:

- Which keyboards exist.
- Which buttons they contain (text or `callback_data` patterns).
- Which handlers and states they relate to.
- Which feature bucket they belong to.

It is the primary reference for understanding **what happens when a user presses a given button**.

---

## 1. Reply Keyboards (`app/keyboards/reply.py`, `app/keyboards/admin.py`)

Reply keyboards are shown as persistent panels below the input field.

### 1.1. User Reply Keyboards (`reply.py`)

Source: `app/keyboards/reply.py`

| Keyboard Builder            | Button Label (text) | Handler Module(s)                    | State (if any)         | Feature Bucket                 |
|-----------------------------|---------------------|--------------------------------------|------------------------|--------------------------------|
| `get_main_reply_keyboard`   | `MENU_BALANCE`      | `app/handlers/balance/main.py`      | none                   | Balance & Payments             |
| `get_main_reply_keyboard`   | `MENU_SUBSCRIPTION` | `app/handlers/menu.py`              | none                   | Main Menu & Navigation         |
| `get_main_reply_keyboard`   | `MENU_PROMOCODE`    | `app/handlers/promocode.py`         | `PromoCodeStates.waiting_for_code` | Promo Code Activation |
| `get_main_reply_keyboard`   | `MENU_REFERRALS`    | `app/handlers/referral.py`          | none                   | Referral Program               |
| `get_main_reply_keyboard`   | `MENU_SUPPORT`      | `app/handlers/support.py`           | none                   | Support & Tickets              |
| `get_main_reply_keyboard`   | `MENU_RULES`        | `app/handlers/menu.py`              | none                   | Main Menu & Navigation         |
| `get_cancel_keyboard`       | `CANCEL` (localized) | Multiple handlers (all FSM flows)   | Various FSM states     | Cross‑cutting (all flows)      |
| `get_confirmation_reply_keyboard` | `YES` / `NO` (localized) | Feature-specific handlers        | Feature states         | Cross‑cutting (confirmations)   |
| `get_skip_keyboard`        | `REFERRAL_CODE_SKIP` | `app/handlers/start.py`            | `RegistrationStates.waiting_for_referral_code` | Registration & Onboarding |
| `get_contact_keyboard`      | `SEND_CONTACT_BUTTON` | Handlers requiring contact info    | Various                | Cross‑cutting                  |
| `get_location_keyboard`     | `SEND_LOCATION_BUTTON` | Handlers requiring location        | Various                | Cross‑cutting                  |

**Note:** Button labels are localized via `get_texts(language)` - actual text depends on user's language setting.

### 1.2. Admin Reply Keyboards (`admin.py`)

Source: `app/keyboards/admin.py`

Admin keyboards are extensive and used for the admin panel flows.
Key builders (non‑exhaustive, to be expanded from code):

- `get_admin_main_keyboard()`
- `get_admin_users_submenu_keyboard()`
- `get_admin_promo_submenu_keyboard()`
- `get_admin_communications_submenu_keyboard()`
- `get_admin_support_submenu_keyboard()`
- `get_admin_settings_submenu_keyboard()`
- `get_admin_system_submenu_keyboard()`
- `get_admin_reports_keyboard()`
- `get_admin_users_keyboard()`
- `get_admin_subscriptions_keyboard()`
- `get_admin_promocodes_keyboard()`
- `get_admin_campaigns_keyboard()`
- `get_admin_messages_keyboard()`
- `get_admin_monitoring_keyboard()`
- `get_admin_remnawave_keyboard()`
- `get_admin_statistics_keyboard()`
- `get_maintenance_keyboard()`
- … (many more specialized builders, all of which will be captured here).

Planned table structure:

| Keyboard Builder                  | Button Label (text) | Handler Module(s)                         | State (if any)        | Admin Feature Bucket  |
|-----------------------------------|---------------------|-------------------------------------------|-----------------------|-----------------------|
| `get_admin_main_keyboard`         | “Users”             | `app/handlers/admin/users.py`            | none / admin main     | Admin/Users           |
| `get_admin_main_keyboard`         | “Subscriptions”     | `app/handlers/admin/subscriptions.py`    | none / admin main     | Admin/Subscriptions   |
| `get_admin_promo_submenu_keyboard`| “Promo Groups”      | `app/handlers/admin/promo_groups.py`     | promo state(s)        | Admin/Promo           |
| …                                 | …                   | …                                         | …                     | …                     |

---

## 2. Inline Keyboards (`app/keyboards/inline.py`)

Inline keyboards attach directly under messages and use `callback_data` or URLs.

Source: `app/keyboards/inline.py`

### 2.1. Main Menu & Navigation

| Keyboard Builder                    | Button Label / Icon | `callback_data` / URL Pattern | Handler Module(s)                    | State (if any)              | Feature Bucket                    |
|-------------------------------------|---------------------|-------------------------------|--------------------------------------|-----------------------------|-----------------------------------|
| `get_main_menu_keyboard`           | Profile (WebApp)     | WebApp URL or `menu_profile_unavailable` | `app/handlers/menu.py` | none                        | Main Menu & Navigation           |
| `get_main_menu_keyboard`           | Language            | `menu_language`               | `app/handlers/menu.py`              | none                        | Main Menu & Navigation           |
| `get_main_menu_keyboard`           | Support             | `menu_support`                 | `app/handlers/support.py`           | none                        | Support & Tickets                 |
| `get_main_menu_keyboard`           | Admin Panel         | `admin_panel`                  | `app/handlers/admin/main.py`        | none                        | Admin Panel                       |
| `get_main_menu_keyboard`           | Subscription        | `menu_subscription`            | `app/handlers/subscription/purchase.py` | none                  | Subscription Purchase & Manage   |
| `get_main_menu_keyboard`           | Balance             | `menu_balance`                 | `app/handlers/balance/main.py`      | none                        | Balance & Payments                |
| `get_main_menu_keyboard`           | Trial               | `menu_trial`                   | `app/handlers/subscription/purchase.py` | none                  | Subscription Purchase & Manage   |
| `get_main_menu_keyboard`           | Buy Subscription    | `menu_buy`                     | `app/handlers/subscription/purchase.py` | none                  | Subscription Purchase & Manage   |
| `get_main_menu_keyboard`           | Simple Subscription | `simple_subscription_purchase` | `app/handlers/simple_subscription.py` | none                  | Subscription Purchase & Manage   |
| `get_main_menu_keyboard`           | Back to Menu        | `back_to_menu`                 | `app/handlers/menu.py`              | none                        | Main Menu & Navigation           |
| `get_info_menu_keyboard`           | Rules               | `menu_rules`                   | `app/handlers/menu.py`              | none                        | Main Menu & Navigation           |
| `get_info_menu_keyboard`           | FAQ                 | `menu_faq`                     | `app/handlers/menu.py`              | none                        | Main Menu & Navigation           |
| `get_info_menu_keyboard`           | Privacy Policy      | `menu_privacy_policy`          | `app/handlers/menu.py`              | none                        | Main Menu & Navigation           |
| `get_info_menu_keyboard`           | Public Offer        | `menu_public_offer`            | `app/handlers/menu.py`              | none                        | Main Menu & Navigation           |
| `get_info_menu_keyboard`           | Promo Groups Info   | `menu_info_promo_groups`       | `app/handlers/menu.py`              | none                        | Main Menu & Navigation           |
| `get_language_selection_keyboard`   | Language options    | `language_select:*`            | `app/handlers/start.py`, `app/handlers/menu.py` | `RegistrationStates.waiting_for_language` or None | Registration & Onboarding / Main Menu |

### 2.2. Registration & Onboarding

| Keyboard Builder                    | Button Label / Icon | `callback_data` / URL Pattern | Handler Module(s)                    | State (if any)              | Feature Bucket                    |
|-------------------------------------|---------------------|-------------------------------|--------------------------------------|-----------------------------|-----------------------------------|
| `get_rules_keyboard`               | Accept Rules        | `rules_accept`                | `app/handlers/start.py`             | `RegistrationStates.waiting_for_rules_accept` | Registration & Onboarding |
| `get_rules_keyboard`               | Decline Rules       | `rules_decline`                | `app/handlers/start.py`             | `RegistrationStates.waiting_for_rules_accept` | Registration & Onboarding |
| `get_privacy_policy_keyboard`      | Accept Privacy      | `privacy_policy_accept`        | `app/handlers/start.py`             | `RegistrationStates.waiting_for_privacy_policy_accept` | Registration & Onboarding |
| `get_privacy_policy_keyboard`      | Decline Privacy     | `privacy_policy_decline`       | `app/handlers/start.py`             | `RegistrationStates.waiting_for_privacy_policy_accept` | Registration & Onboarding |
| `get_channel_sub_keyboard`         | Subscribe           | Channel URL                    | N/A (external link)                  | none                        | Registration & Onboarding         |
| `get_channel_sub_keyboard`         | I Subscribed        | `sub_channel_check`            | `app/handlers/start.py`             | none                        | Registration & Onboarding         |
| `get_post_registration_keyboard`   | Connect for Free    | `trial_activate`               | `app/handlers/subscription/purchase.py` | none                  | Subscription Purchase & Manage   |
| `get_post_registration_keyboard`   | Skip                | `back_to_menu`                 | `app/handlers/menu.py`              | none                        | Main Menu & Navigation           |

### 2.3. Subscription Purchase & Management

| Keyboard Builder                    | Button Label / Icon | `callback_data` / URL Pattern | Handler Module(s)                    | State (if any)              | Feature Bucket                    |
|-------------------------------------|---------------------|-------------------------------|--------------------------------------|-----------------------------|-----------------------------------|
| `get_subscription_keyboard`        | Various actions     | Multiple patterns             | `app/handlers/subscription/purchase.py` | Various subscription states | Subscription Purchase & Manage   |
| `get_trial_keyboard`               | Activate Trial      | `trial_activate`               | `app/handlers/subscription/purchase.py` | none                  | Subscription Purchase & Manage   |
| `get_subscription_period_keyboard` | Period options      | `period_*`                     | `app/handlers/subscription/purchase.py` | `SubscriptionStates.selecting_period` | Subscription Purchase & Manage |
| `get_traffic_packages_keyboard`    | Traffic options     | `traffic_*`                    | `app/handlers/subscription/purchase.py` | `SubscriptionStates.selecting_traffic` | Subscription Purchase & Manage |
| `get_countries_keyboard`           | Country options     | Country selection patterns    | `app/handlers/subscription/countries.py` | `SubscriptionStates.selecting_countries` | Subscription Purchase & Manage |
| `get_devices_keyboard`             | Device options      | `devices_*`                    | `app/handlers/subscription/devices.py` | `SubscriptionStates.selecting_devices` | Subscription Purchase & Manage |
| `get_subscription_confirm_keyboard` | Confirm Purchase   | `subscription_confirm`         | `app/handlers/subscription/purchase.py` | `SubscriptionStates.confirming_purchase` | Subscription Purchase & Manage |
| `get_subscription_confirm_keyboard_with_cart` | Confirm with Cart | `subscription_confirm`         | `app/handlers/subscription/purchase.py` | `SubscriptionStates.confirming_purchase` | Subscription Purchase & Manage |
| `get_payment_methods_keyboard_with_cart` | Payment methods | Payment method patterns       | `app/handlers/subscription/purchase.py` | Various                    | Subscription Purchase & Manage   |
| Subscription management buttons    | Add Countries       | `subscription_add_countries`   | `app/handlers/subscription/purchase.py` | none                        | Subscription Purchase & Manage   |
| Subscription management buttons    | Change Devices      | `subscription_change_devices` | `app/handlers/subscription/purchase.py` | none                        | Subscription Purchase & Manage   |
| Subscription management buttons    | Extend Subscription | `subscription_extend`          | `app/handlers/subscription/purchase.py` | none                        | Subscription Purchase & Manage   |
| Subscription management buttons    | Reset Traffic       | `subscription_reset_traffic`   | `app/handlers/subscription/purchase.py` | none                        | Subscription Purchase & Manage   |
| Subscription management buttons    | Resume Checkout     | `subscription_resume_checkout` | `app/handlers/subscription/purchase.py` | none                        | Subscription Purchase & Manage   |
| Subscription management buttons    | Return to Cart      | `return_to_saved_cart`         | `app/handlers/subscription/purchase.py` | none                        | Subscription Purchase & Manage   |
| Subscription management buttons    | Clear Cart          | `clear_saved_cart`             | `app/handlers/subscription/purchase.py` | none                        | Subscription Purchase & Manage   |
| Auto-pay buttons                   | Auto-pay Menu       | `subscription_autopay`         | `app/handlers/subscription/purchase.py` | none                        | Subscription Purchase & Manage   |
| Auto-pay buttons                   | Enable Auto-pay     | `autopay_enable`               | `app/handlers/subscription/purchase.py` | none                        | Subscription Purchase & Manage   |
| Auto-pay buttons                   | Disable Auto-pay    | `autopay_disable`              | `app/handlers/subscription/purchase.py` | none                        | Subscription Purchase & Manage   |
| Auto-pay buttons                   | Set Auto-pay Days   | `autopay_set_days`             | `app/handlers/subscription/autopay.py` | `AutoPayStates.setting_autopay_days` | Subscription Purchase & Manage |

### 2.4. Balance & Payments

| Keyboard Builder                    | Button Label / Icon | `callback_data` / URL Pattern | Handler Module(s)                    | State (if any)              | Feature Bucket                    |
|-------------------------------------|---------------------|-------------------------------|--------------------------------------|-----------------------------|-----------------------------------|
| `get_balance_keyboard`             | Balance History     | `balance_history`             | `app/handlers/balance/main.py`      | none                        | Balance & Payments                |
| `get_balance_keyboard`             | Top Up Balance     | `balance_topup`                | `app/handlers/balance/main.py`      | none                        | Balance & Payments                |
| `get_payment_methods_keyboard`      | YooKassa            | `topup_yookassa`               | `app/handlers/balance/yookassa.py`  | none                        | Balance & Payments                |
| `get_payment_methods_keyboard`      | YooKassa SBP        | `topup_yookassa_sbp`           | `app/handlers/balance/yookassa.py`  | none                        | Balance & Payments                |
| `get_payment_methods_keyboard`      | CryptoBot           | `topup_cryptobot`              | `app/handlers/balance/cryptobot.py` | none                        | Balance & Payments                |
| `get_payment_methods_keyboard`      | Telegram Stars      | `topup_stars`                  | `app/handlers/stars_payments.py`    | `BalanceStates.waiting_for_stars_payment` | Balance & Payments |
| `get_payment_methods_keyboard`      | MulenPay            | `topup_mulenpay`               | `app/handlers/balance/mulenpay.py`  | none                        | Balance & Payments                |
| `get_payment_methods_keyboard`      | Pal24               | `topup_pal24`                  | `app/handlers/balance/pal24.py`     | `BalanceStates.waiting_for_pal24_method` | Balance & Payments |
| `get_payment_methods_keyboard`      | Platega             | `topup_platega`                | `app/handlers/balance/platega.py`   | `BalanceStates.waiting_for_platega_method` | Balance & Payments |
| `get_payment_methods_keyboard`      | WATA                | `topup_wata`                   | `app/handlers/balance/wata.py`      | none                        | Balance & Payments                |
| `get_payment_methods_keyboard`      | Tribute             | `topup_tribute`                | `app/handlers/balance/tribute.py`   | none                        | Balance & Payments                |
| `get_payment_methods_keyboard`      | Support             | `topup_support`                | `app/handlers/balance/*`             | `BalanceStates.waiting_for_support_request` | Balance & Payments |
| Quick amount buttons               | Quick amounts       | `quick_amount_*`               | `app/handlers/balance/main.py`      | `BalanceStates.waiting_for_amount` | Balance & Payments |
| Payment status check buttons       | Check YooKassa      | `check_yookassa_*`             | `app/handlers/balance/yookassa.py`  | none                        | Balance & Payments                |
| Payment status check buttons       | Check CryptoBot     | `check_cryptobot_*`            | `app/handlers/balance/cryptobot.py` | none                        | Balance & Payments                |
| Payment status check buttons       | Check Heleket       | `check_heleket_*`              | `app/handlers/balance/heleket.py`   | none                        | Balance & Payments                |
| Payment status check buttons       | Check MulenPay      | `check_mulenpay_*`             | `app/handlers/balance/mulenpay.py`  | none                        | Balance & Payments                |
| Payment status check buttons       | Check WATA          | `check_wata_*`                 | `app/handlers/balance/wata.py`      | none                        | Balance & Payments                |
| Payment status check buttons       | Check Pal24         | `check_pal24_*`                | `app/handlers/balance/pal24.py`     | none                        | Balance & Payments                |
| Payment status check buttons       | Check Platega       | `check_platega_*`              | `app/handlers/balance/platega.py`   | none                        | Balance & Payments                |

### 2.5. Referral Program

| Keyboard Builder                    | Button Label / Icon | `callback_data` / URL Pattern | Handler Module(s)                    | State (if any)              | Feature Bucket                    |
|-------------------------------------|---------------------|-------------------------------|--------------------------------------|-----------------------------|-----------------------------------|
| `get_referral_keyboard`            | Create Invite       | `referral_create_invite`      | `app/handlers/referral.py`          | none                        | Referral Program                  |
| `get_referral_keyboard`            | Show QR Code        | `referral_show_qr`            | `app/handlers/referral.py`          | none                        | Referral Program                  |
| `get_referral_keyboard`            | Referral List       | `referral_list`               | `app/handlers/referral.py`          | none                        | Referral Program                  |
| `get_referral_keyboard`            | Analytics           | `referral_analytics`          | `app/handlers/referral.py`          | none                        | Referral Program                  |
| Referral list pagination            | Page navigation     | `referral_list_page_*`        | `app/handlers/referral.py`          | none                        | Referral Program                  |

### 2.6. Support & Tickets

| Keyboard Builder                    | Button Label / Icon | `callback_data` / URL Pattern | Handler Module(s)                    | State (if any)              | Feature Bucket                    |
|-------------------------------------|---------------------|-------------------------------|--------------------------------------|-----------------------------|-----------------------------------|
| `get_support_keyboard`             | Create Ticket       | `create_ticket`               | `app/handlers/tickets.py`            | `TicketStates.waiting_for_title` | Support & Tickets |
| `get_support_keyboard`             | My Tickets          | `my_tickets`                  | `app/handlers/tickets.py`            | none                        | Support & Tickets                 |
| `get_ticket_view_keyboard`         | Reply               | `ticket_reply:*`              | `app/handlers/tickets.py`            | `TicketStates.waiting_for_reply` | Support & Tickets |
| `get_ticket_cancel_keyboard`       | Cancel              | `ticket_cancel`               | `app/handlers/tickets.py`            | Various ticket states       | Support & Tickets                 |
| `get_my_tickets_keyboard`          | View Ticket         | `view_ticket_*`                | `app/handlers/tickets.py`            | none                        | Support & Tickets                 |
| `get_my_tickets_keyboard`          | Closed Tickets      | `my_tickets_closed`           | `app/handlers/tickets.py`            | none                        | Support & Tickets                 |
| Ticket pagination                  | Page navigation     | `ticket_view_page_*`, `my_tickets_closed_page_*` | `app/handlers/tickets.py` | none                        | Support & Tickets                 |

### 2.7. Admin Panel Keyboards

Admin keyboards are extensive. Key patterns:

| Keyboard Builder                    | Button Label / Icon | `callback_data` / URL Pattern | Handler Module(s)                    | State (if any)              | Feature Bucket                    |
|-------------------------------------|---------------------|-------------------------------|--------------------------------------|-----------------------------|-----------------------------------|
| `get_admin_main_keyboard`          | Users               | `admin_users`                 | `app/handlers/admin/users.py`       | none                        | Admin/Users                       |
| `get_admin_main_keyboard`          | Subscriptions       | `admin_subscriptions`         | `app/handlers/admin/subscriptions.py` | none                  | Admin/Subscriptions              |
| `get_admin_main_keyboard`          | Promocodes          | `admin_promocodes`            | `app/handlers/admin/promocodes.py`   | none                        | Admin/Promo                       |
| `get_admin_main_keyboard`          | Messages            | `admin_messages`              | `app/handlers/admin/messages.py`     | none                        | Admin/Communications              |
| `get_admin_main_keyboard`          | Statistics          | `admin_statistics`            | `app/handlers/admin/statistics.py`   | none                        | Admin/Statistics                  |
| `get_admin_main_keyboard`          | Monitoring          | `admin_monitoring`            | `app/handlers/admin/monitoring.py`   | none                        | Admin/Monitoring                  |
| `get_admin_main_keyboard`          | RemnaWave            | `admin_remnawave`             | `app/handlers/admin/remnawave.py`   | none                        | Admin/RemnaWave                   |
| Admin ticket keyboards              | Reply as Admin      | `admin_ticket_reply:*`        | `app/handlers/admin/tickets.py`      | `AdminTicketStates.waiting_for_reply` | Admin/Support |
| Admin ticket keyboards              | Block User          | `admin_ticket_block:*`        | `app/handlers/admin/tickets.py`      | `AdminTicketStates.waiting_for_block_duration` | Admin/Support |

**Note:** Admin keyboards have hundreds of callback patterns. See `app/keyboards/admin.py` and `app/handlers/admin/*.py` for complete mappings.

---

## 3. Button-Centric View (Complete Flow Trace)

For every button, this section provides a complete trace from button press to final response.

### 3.1. Main Menu Buttons

| Button Text/Callback | Keyboard Builder | Handler | State | Services | Models/CRUD | Feature |
|----------------------|------------------|---------|-------|----------|-------------|---------|
| `menu_subscription` | `get_main_menu_keyboard` | `handlers/subscription/purchase.py::show_subscription_info` | none | `SubscriptionService` | `Subscription`, `User` | Subscription Purchase & Manage |
| `menu_balance` | `get_main_menu_keyboard` | `handlers/balance/main.py::show_balance_menu` | none | `PaymentService` | `User`, `Transaction` | Balance & Payments |
| `menu_trial` | `get_main_menu_keyboard` | `handlers/subscription/purchase.py::show_trial_offer` | none | `SubscriptionService`, `TrialActivationService` | `Subscription` | Subscription Purchase & Manage |
| `menu_buy` | `get_main_menu_keyboard` | `handlers/subscription/purchase.py::start_subscription_purchase` | `SubscriptionStates.selecting_period` | `SubscriptionPurchaseService`, `UserCartService` | `User`, `PromoGroup` | Subscription Purchase & Manage |
| `menu_referrals` | `get_main_menu_keyboard` | `handlers/referral.py::show_referral_info` | none | None (direct CRUD) | `User`, `ReferralEarning`, `Transaction` | Referral Program |
| `menu_support` | `get_main_menu_keyboard` | `handlers/support.py::show_support_info` | none | `SupportSettingsService` | None | Support & Tickets |
| `menu_language` | `get_main_menu_keyboard` | `handlers/menu.py::show_language_menu` | none | `UserService` | `User` | Main Menu & Navigation |
| `back_to_menu` | Various keyboards | `handlers/menu.py::handle_back_to_menu` | none | `SubscriptionService`, `UserCartService` | `User`, `Subscription` | Main Menu & Navigation |

### 3.2. Subscription Flow Buttons

| Button Text/Callback | Keyboard Builder | Handler | State | Services | Models/CRUD | Feature |
|----------------------|------------------|---------|-------|----------|-------------|---------|
| `period_*` | `get_subscription_period_keyboard` | `handlers/subscription/purchase.py::select_period` | `SubscriptionStates.selecting_period` | `SubscriptionPurchaseService` | `PromoGroup` (for discounts) | Subscription Purchase & Manage |
| `traffic_*` | `get_traffic_packages_keyboard` | `handlers/subscription/purchase.py::select_traffic` | `SubscriptionStates.selecting_traffic` | `SubscriptionPurchaseService` | `PromoGroup` (for discounts) | Subscription Purchase & Manage |
| `devices_*` | `get_devices_keyboard` | `handlers/subscription/devices.py::select_devices` | `SubscriptionStates.selecting_devices` | `SubscriptionPurchaseService` | `PromoGroup` (for discounts) | Subscription Purchase & Manage |
| `subscription_confirm` | `get_subscription_confirm_keyboard` | `handlers/subscription/purchase.py::confirm_purchase` | `SubscriptionStates.confirming_purchase` | `SubscriptionPurchaseService`, `SubscriptionService`, `PaymentService`, `RemnaWaveService` | `Subscription`, `Transaction`, `User`, `SubscriptionServer` | Subscription Purchase & Manage |
| `subscription_add_countries` | Subscription management keyboard | `handlers/subscription/purchase.py::handle_add_countries` | `SubscriptionStates.adding_countries` | `SubscriptionService` | `Subscription`, `SubscriptionServer`, `ServerSquad` | Subscription Purchase & Manage |
| `subscription_change_devices` | Subscription management keyboard | `handlers/subscription/purchase.py::handle_change_devices` | `SubscriptionStates.adding_devices` | `SubscriptionService` | `Subscription` | Subscription Purchase & Manage |
| `subscription_extend` | Subscription management keyboard | `handlers/subscription/purchase.py::handle_extend_subscription` | `SubscriptionStates.extending_subscription` | `SubscriptionService`, `PaymentService` | `Subscription`, `Transaction` | Subscription Purchase & Manage |
| `autopay_enable` / `autopay_disable` | Auto-pay keyboard | `handlers/subscription/purchase.py::toggle_autopay` | none | `SubscriptionService` | `Subscription` | Subscription Purchase & Manage |

### 3.3. Payment Buttons

| Button Text/Callback | Keyboard Builder | Handler | State | Services | Models/CRUD | Feature |
|----------------------|------------------|---------|-------|----------|-------------|---------|
| `balance_topup` | `get_balance_keyboard` | `handlers/balance/main.py::show_payment_methods` | none | `PaymentService` | `User` | Balance & Payments |
| `topup_yookassa` | `get_payment_methods_keyboard` | `handlers/balance/yookassa.py::start_yookassa_payment` | `BalanceStates.waiting_for_amount` | `PaymentService`, `YooKassaService` | `Transaction`, `YooKassaPayment` | Balance & Payments |
| `topup_cryptobot` | `get_payment_methods_keyboard` | `handlers/balance/cryptobot.py::start_cryptobot_payment` | `BalanceStates.waiting_for_amount` | `PaymentService`, `CryptoBotService` | `Transaction`, `CryptoBotPayment` | Balance & Payments |
| `topup_stars` | `get_payment_methods_keyboard` | `handlers/stars_payments.py::start_stars_payment` | `BalanceStates.waiting_for_stars_payment` | `PaymentService`, `TelegramStarsService` | `Transaction` | Balance & Payments |
| `quick_amount_*` | Quick amount buttons | `handlers/balance/main.py::handle_topup_amount_callback` | `BalanceStates.waiting_for_amount` | `PaymentService` | `User` (for discount calc) | Balance & Payments |

### 3.4. Support & Ticket Buttons

| Button Text/Callback | Keyboard Builder | Handler | State | Services | Models/CRUD | Feature |
|----------------------|------------------|---------|-------|----------|-------------|---------|
| `create_ticket` | `get_support_keyboard` | `handlers/tickets.py::create_ticket` | `TicketStates.waiting_for_title` | `AdminNotificationService`, `SupportSettingsService` | `Ticket`, `TicketMessage` | Support & Tickets |
| `my_tickets` | `get_support_keyboard` | `handlers/tickets.py::show_my_tickets` | none | None (direct CRUD) | `Ticket`, `TicketMessage` | Support & Tickets |
| `ticket_reply:*` | `get_ticket_view_keyboard` | `handlers/tickets.py::reply_to_ticket` | `TicketStates.waiting_for_reply` | `AdminNotificationService` | `Ticket`, `TicketMessage` | Support & Tickets |

### 3.5. Referral Buttons

| Button Text/Callback | Keyboard Builder | Handler | State | Services | Models/CRUD | Feature |
|----------------------|------------------|---------|-------|----------|-------------|---------|
| `referral_create_invite` | `get_referral_keyboard` | `handlers/referral.py::create_invite_message` | none | None (direct CRUD) | `User` | Referral Program |
| `referral_show_qr` | `get_referral_keyboard` | `handlers/referral.py::show_referral_qr` | none | None (QR generation) | `User` | Referral Program |
| `referral_list` | `get_referral_keyboard` | `handlers/referral.py::show_detailed_referral_list` | none | None (direct CRUD) | `User`, `ReferralEarning` | Referral Program |
| `referral_analytics` | `get_referral_keyboard` | `handlers/referral.py::show_referral_analytics` | none | None (direct CRUD) | `User`, `ReferralEarning`, `Transaction` | Referral Program |

## 4. From Button to Flow

For every button we can trace:

1. **Button definition** (keyboard builder and label/callback data) - See sections 1-2 above.
2. **Handler filter** that matches its text or callback pattern - See section 3 above.
3. **FSM state** (if the handler is state‑bound) - See `docs/telegram-fsm-flows.md`.
4. **Feature bucket** it belongs to - See `docs/telegram-flows-overview.md`.
5. **Services and models** involved downstream - See `docs/telegram-feature-flows.md`.

This document focuses on (1), (2), and (3); the other parts are detailed in the companion documents.
