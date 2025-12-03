# Comprehensive Cyrillic (Russian) Hardcode Analysis & Batching Strategy

**Analysis Date:** 2025-01-27  
**Total Files with Cyrillic:** 129  
**Total Infected Lines:** 6,791

---

## 1. Top Infected Files

| File Path | Cyrillic Line Count | Total Lines | Primary Type |
| :--- | :--- | :--- | :--- |
| `app/handlers/admin/users.py` | 584 | 5,134 | Mixed (UI, Comment, Logic) |
| `app/handlers/admin/remnawave.py` | 581 | 3,225 | Mixed (UI, Comment, Logic) |
| `app/database/universal_migration.py` | 416 | 4,397 | Mixed (UI, Log, Logic) |
| `app/handlers/simple_subscription.py` | 388 | 2,420 | Mixed (UI, Comment, Logic) |
| `app/handlers/admin/bot_configuration.py` | 245 | 2,777 | UI |
| `app/keyboards/admin.py` | 236 | 2,030 | UI |
| `app/handlers/admin/servers.py` | 200 | 1,321 | Mixed (UI, Logic) |
| `app/handlers/admin/promocodes.py` | 187 | 1,132 | Mixed (UI, Logic) |
| `app/handlers/admin/promo_offers.py` | 186 | 2,387 | Mixed (UI, Log, Logic) |
| `app/handlers/admin/campaigns.py` | 172 | 1,733 | Mixed (UI, Logic) |
| `app/handlers/admin/messages.py` | 169 | 1,214 | Mixed (UI, Comment, Logic) |
| `app/handlers/admin/monitoring.py` | 166 | 1,095 | UI |
| `app/handlers/admin/tickets.py` | 153 | 1,132 | Mixed (UI, Comment, Logic) |
| `app/handlers/tickets.py` | 146 | 1,061 | Mixed (UI, Comment) |
| `app/keyboards/inline.py` | 127 | 2,545 | Mixed (UI, Logic) |

---

## 2. Recommended Batches

### Giant Files (Need Solitary Refactoring)

These files are too large to batch with others. Each requires a dedicated refactoring session:

1. **`app/handlers/admin/users.py`** (584 lines)
   - **Type:** Mixed (UI, Comment, Logic)
   - **Focus:** Admin user management interface strings, inline comments, hardcoded logic
   - **Estimated Effort:** High - requires careful UI string extraction

2. **`app/handlers/admin/remnawave.py`** (581 lines)
   - **Type:** Mixed (UI, Comment, Logic)
   - **Focus:** RemnaWave integration UI, status messages, formatting functions
   - **Estimated Effort:** High - complex formatting logic with hardcoded strings

3. **`app/database/universal_migration.py`** (416 lines)
   - **Type:** Mixed (UI, Log, Logic)
   - **Focus:** Logger messages, error messages, migration status text
   - **Estimated Effort:** Medium - mostly logger.info/error calls

4. **`app/handlers/simple_subscription.py`** (388 lines)
   - **Type:** Mixed (UI, Comment, Logic)
   - **Focus:** Subscription purchase flow UI, docstrings, inline comments
   - **Estimated Effort:** Medium-High - user-facing purchase flow

**Total Giant Files:** 1,969 lines (29% of total)

---

### Batch 1: Critical Admin UI - Core Handlers (~650 lines)

**Target:** High-visibility admin panel interfaces

- `app/handlers/admin/bot_configuration.py` (245 lines) - UI
- `app/handlers/admin/servers.py` (200 lines) - Mixed (UI, Logic)
- `app/handlers/admin/monitoring.py` (166 lines) - UI
- `app/handlers/admin/messages.py` (169 lines) - Mixed (UI, Comment, Logic)

**Total:** ~780 lines  
**Rationale:** Core admin functionality that admins see frequently

---

### Batch 2: Admin UI - Promo & Campaigns (~550 lines)

**Target:** Promotional and campaign management

- `app/handlers/admin/promocodes.py` (187 lines) - Mixed (UI, Logic)
- `app/handlers/admin/promo_offers.py` (186 lines) - Mixed (UI, Log, Logic)
- `app/handlers/admin/campaigns.py` (172 lines) - Mixed (UI, Logic)

**Total:** ~545 lines  
**Rationale:** Related promotional features grouped together

---

### Batch 3: Admin UI - Support & Tickets (~300 lines)

**Target:** Support and ticket management

- `app/handlers/admin/tickets.py` (153 lines) - Mixed (UI, Comment, Logic)
- `app/handlers/tickets.py` (146 lines) - Mixed (UI, Comment)

**Total:** ~299 lines  
**Rationale:** Support system components

---

### Batch 4: Keyboards - Admin & Inline (~360 lines)

**Target:** All keyboard button labels

- `app/keyboards/admin.py` (236 lines) - UI
- `app/keyboards/inline.py` (127 lines) - Mixed (UI, Logic)

**Total:** ~363 lines  
**Rationale:** Button labels are self-contained and easy to refactor together

---

### Batch 5: Admin UI - Secondary Features (~450 lines)

**Target:** Less frequently used admin features

- `app/handlers/admin/backup.py` (126 lines)
- `app/handlers/admin/statistics.py` (114 lines)
- `app/handlers/admin/pricing.py` (104 lines)
- `app/handlers/admin/subscriptions.py` (94 lines)
- `app/handlers/admin/promo_groups.py` (92 lines)
- `app/handlers/admin/welcome_text.py` (92 lines)
- `app/handlers/admin/rules.py` (87 lines)

**Total:** ~709 lines  
**Rationale:** Secondary admin features, can be split if needed

---

### Batch 6: Admin UI - Communication & Content (~250 lines)

**Target:** Messaging and content management

- `app/handlers/admin/polls.py` (77 lines)
- `app/handlers/admin/faq.py` (76 lines)
- `app/handlers/admin/user_messages.py` (76 lines)
- `app/handlers/admin/maintenance.py` (66 lines)

**Total:** ~295 lines  
**Rationale:** Content management features

---

### Batch 7: User-Facing Handlers (~200 lines)

**Target:** Main user interaction points

- `app/handlers/start.py` (82 lines)
- `app/handlers/menu.py` (65 lines)
- `app/handlers/referral.py` (53 lines)

**Total:** ~200 lines  
**Rationale:** Entry points for regular users

---

### Batch 8: Payment Handlers (~200 lines)

**Target:** Payment processing interfaces

- `app/handlers/balance/yookassa.py` (114 lines)
- `app/handlers/balance/cryptobot.py` (64 lines)
- `app/handlers/balance/pal24.py` (63 lines)
- `app/handlers/balance/heleket.py` (48 lines)
- `app/handlers/balance/mulenpay.py` (45 lines)
- `app/handlers/balance/platega.py` (41 lines)
- `app/handlers/balance/wata.py` (38 lines)
- `app/handlers/balance/stars.py` (21 lines)
- `app/handlers/balance/tribute.py` (3 lines)

**Total:** ~437 lines  
**Rationale:** Payment providers grouped together

---

### Batch 9: Services - Logs & Logic (~200 lines)

**Target:** Service layer with logging

- `app/services/maintenance_service.py` (78 lines)
- `app/services/subscription_auto_purchase_service.py` (39 lines)
- `app/services/promocode_service.py` (21 lines)
- `app/services/poll_service.py` (19 lines)
- `app/services/payment_verification_service.py` (15 lines)
- `app/services/version_service.py` (13 lines)
- `app/services/campaign_service.py` (10 lines)
- `app/services/pal24_service.py` (7 lines)
- `app/services/main_menu_button_service.py` (3 lines)
- `app/services/trial_activation_service.py` (3 lines)
- `app/services/reporting_service.py` (2 lines)
- `app/services/promo_offer_service.py` (2 lines)
- `app/services/privacy_policy_service.py` (1 line)
- `app/services/web_api_token_service.py` (1 line)
- `app/services/subscription_renewal_service.py` (1 line)
- `app/services/public_offer_service.py` (1 line)

**Total:** ~221 lines  
**Rationale:** Service layer mostly has logger calls

---

### Batch 10: WebAPI Routes (~150 lines)

**Target:** API endpoint messages

- `app/webapi/routes/remnawave.py` (44 lines)
- `app/webapi/routes/miniapp.py` (32 lines)
- `app/webapi/routes/logs.py` (27 lines)
- `app/webapi/routes/servers.py` (11 lines)
- `app/webapi/routes/campaigns.py` (5 lines)
- `app/webapi/routes/backups.py` (5 lines)
- `app/webapi/routes/media.py` (5 lines)
- `app/webapi/routes/pages.py` (3 lines)
- `app/webapi/routes/config.py` (3 lines)
- `app/webapi/routes/stats.py` (2 lines)
- `app/webapi/routes/health.py` (2 lines)

**Total:** ~139 lines  
**Rationale:** API error messages and responses

---

### Batch 11: External Services & Webhooks (~100 lines)

**Target:** External integrations

- `app/external/webhook_server.py` (33 lines)
- `app/external/yookassa_webhook.py` (25 lines)
- `app/external/wata_webhook.py` (24 lines)
- `app/external/tribute.py` (23 lines)
- `app/external/remnawave_api.py` (11 lines)
- `app/external/heleket.py` (11 lines)
- `app/external/cryptobot.py` (10 lines)
- `app/external/telegram_stars.py` (8 lines)
- `app/external/pal24_webhook.py` (11 lines)
- `app/external/heleket_webhook.py` (6 lines)

**Total:** ~168 lines  
**Rationale:** External service integrations

---

### Batch 12: WebAPI Schemas & Misc (~50 lines)

**Target:** Schema validation messages and remaining files

- `app/webapi/schemas/logs.py` (23 lines)
- `app/webapi/schemas/pages.py` (16 lines)
- `app/webapi/schemas/servers.py` (13 lines)
- `app/webapi/schemas/config.py` (5 lines)
- `app/webapi/schemas/media.py` (4 lines)
- `app/webapi/schemas/promo_groups.py` (2 lines)
- `app/webapi/schemas/polls.py` (2 lines)
- `app/webapi/schemas/tokens.py` (2 lines)
- `app/webapi/schemas/campaigns.py` (2 lines)
- `app/webapi/schemas/backups.py` (2 lines)
- `app/webapi/schemas/health.py` (2 lines)
- `app/webapi/schemas/users.py` (1 line)
- `app/webapi/schemas/promo_offers.py` (1 line)
- `app/webapi/schemas/partners.py` (1 line)
- `app/webapi/schemas/tickets.py` (1 line)

**Total:** ~77 lines  
**Rationale:** Schema validation error messages

---

### Batch 13: Remaining Files (~100 lines)

**Target:** Miscellaneous remaining files

- `app/handlers/admin/referrals.py` (60 lines)
- `app/handlers/admin/updates.py` (50 lines)
- `app/handlers/admin/support_settings.py` (40 lines)
- `app/handlers/admin/public_offer.py` (38 lines)
- `app/handlers/admin/privacy_policy.py` (36 lines)
- `app/handlers/stars_payments.py` (34 lines)
- `app/handlers/admin/system_logs.py` (27 lines)
- `app/handlers/polls.py` (23 lines)
- `app/handlers/promocode.py` (6 lines)
- `app/handlers/admin/reports.py` (9 lines)
- `app/handlers/admin/trials.py` (9 lines)
- `app/handlers/admin/main.py` (2 lines)
- `app/handlers/admin/__init__.py` (1 line)
- `app/middlewares/display_name_restriction.py` (22 lines)
- `app/middlewares/channel_checker.py` (14 lines)
- `app/middlewares/auth.py` (9 lines)
- `app/middlewares/throttling.py` (7 lines)
- `app/middlewares/logging.py` (1 line)
- `app/webserver/telegram.py` (22 lines)
- `app/webserver/payments.py` (6 lines)
- `app/webserver/unified_app.py` (1 line)
- `app/webapi/app.py` (26 lines)
- `app/webapi/server.py` (7 lines)
- `app/webapi/middleware.py` (1 line)
- `app/webapi/__init__.py` (1 line)
- `app/bot.py` (20 lines)
- `app/database/models.py` (24 lines)
- `app/states.py` (2 lines)
- `app/config.py` (1 line)
- `app/services/__init__.py` (1 line)
- `app/services/monitoring_service.py` (27 lines)
- `app/services/user_cart_service.py` (25 lines)
- `app/services/external_admin_service.py` (17 lines)
- `app/handlers/server_status.py` (13 lines)
- `app/handlers/webhooks.py` (14 lines)

**Total:** ~500 lines  
**Rationale:** Remaining scattered files

---

## 3. Summary Statistics

- **Giant Files (Dedicated):** 4 files, 1,969 lines (29%)
- **Batchable Files:** 125 files, 4,822 lines (71%)
- **Recommended Batches:** 13 batches
- **Average Batch Size:** ~370 lines per batch

---

## 4. Refactoring Priority Recommendations

### Phase 1: High Impact (User-Facing)
1. Giant: `app/handlers/simple_subscription.py` (user purchase flow)
2. Batch 4: Keyboards (all button labels)
3. Batch 7: User-Facing Handlers (entry points)

### Phase 2: Admin Core
1. Giant: `app/handlers/admin/users.py` (most used admin feature)
2. Batch 1: Critical Admin UI - Core Handlers
3. Batch 2: Admin UI - Promo & Campaigns

### Phase 3: Admin Secondary
1. Batch 5: Admin UI - Secondary Features
2. Batch 3: Admin UI - Support & Tickets
3. Batch 6: Admin UI - Communication & Content

### Phase 4: Infrastructure
1. Giant: `app/database/universal_migration.py` (logs)
2. Giant: `app/handlers/admin/remnawave.py` (integration)
3. Batch 9: Services - Logs & Logic
4. Batch 10: WebAPI Routes

### Phase 5: Cleanup
1. Batch 8: Payment Handlers
2. Batch 11: External Services & Webhooks
3. Batch 12: WebAPI Schemas & Misc
4. Batch 13: Remaining Files

---

## 5. Notes

- **Context Limit Strategy:** Each batch is designed to stay under ~800 lines of changes to maintain AI context efficiency
- **Giant Files:** The 4 largest files should be refactored one at a time with dedicated prompts
- **Testing:** After each batch, verify that:
  - All UI strings are properly localized
  - Logger messages are in English (or use localization keys)
  - No functionality is broken
  - Tests pass (if applicable)

