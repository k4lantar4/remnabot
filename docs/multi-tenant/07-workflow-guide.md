# Workflow Guide - How to Proceed

**Version:** 1.0  
**Last Updated:** 2025-12-12

---

## 🎯 هدف این راهنما

این راهنما به شما کمک می‌کند:
- انتخاب increment مناسب برای شروع
- تصمیم‌گیری درباره workflow
- جلوگیری از اشتباهات رایج
- پیشرفت بهینه در migration

---

## 📊 Increment Selection Guide

### Increment چیست؟

Increment یک واحد کاری کوچک و قابل تست است که:
- ✅ مستقل قابل انجام است
- ✅ قابل تست فوری است
- ✅ ارزش فوری دارد
- ✅ ریسک کم دارد

### معیارهای انتخاب Increment

1. **Dependencies** - آیا prerequisites آماده است؟
2. **Risk Level** - چقدر ریسک دارد؟
3. **Value** - چه ارزشی دارد؟
4. **Testability** - چقدر قابل تست است؟
5. **Time** - چقدر زمان می‌برد؟

---

## 🚀 Recommended Increment Sequence

### Phase 1: Foundation (Week 1)

#### Increment 1.1: Database Schema - New Tables
**Status:** ✅ **COMPLETED**  
**Priority:** 🔴 Critical  
**Time:** 2 hours  
**Dependencies:** None  
**Risk:** Low  
**Value:** High

**Why Start Here:**
- پایه همه چیز است
- بدون dependencies
- قابل تست فوری
- ریسک کم

**Tasks:**
1. Create migration script for new tables
2. Run migration on dev database
3. Verify tables and indexes
4. Test foreign keys

**Acceptance:**
- ✅ All 7 new tables created
- ✅ All indexes created
- ✅ Foreign keys working
- ✅ No errors

**Next:** Increment 1.2

---

#### Increment 1.2: Database Models - New Models
**Status:** ✅ **COMPLETED**  
**Priority:** 🔴 Critical  
**Time:** 3 hours  
**Dependencies:** Increment 1.1  
**Risk:** Low  
**Value:** High

**Why Next:**
- نیاز به schema دارد
- پایه CRUD operations
- قابل تست

**Tasks:**
1. Add new models to `models.py`
2. Test model creation
3. Verify relationships
4. Test imports

**Acceptance:**
- ✅ All models created
- ✅ Relationships working
- ✅ No import errors

**Next:** Increment 1.3

---

#### Increment 1.3: Bot CRUD Operations
**Status:** ✅ **COMPLETED**  
**Priority:** 🔴 Critical  
**Time:** 2 hours  
**Dependencies:** Increment 1.2  
**Risk:** Low  
**Value:** High

**Why Next:**
- نیاز به models دارد
- پایه feature flags
- قابل تست

**Tasks:**
1. Create `app/database/crud/bot.py`
2. Implement basic CRUD
3. Test all operations
4. Test API token generation

**Acceptance:**
- ✅ Create bot works
- ✅ Get bot works
- ✅ API token generation works
- ✅ All tests pass

**Next:** Increment 1.4

---

#### Increment 1.4: Feature Flag CRUD
**Priority:** 🟡 High  
**Time:** 2 hours  
**Dependencies:** Increment 1.3  
**Risk:** Low  
**Value:** High

**Why Next:**
- نیاز به bot CRUD دارد
- پایه feature system
- قابل تست

**Tasks:**
1. Create `app/database/crud/bot_feature_flag.py`
2. Implement CRUD operations:
   - `get_feature_flag(db, bot_id, feature_key)`
   - `is_feature_enabled(db, bot_id, feature_key)`
   - `get_feature_config(db, bot_id, feature_key)`
   - `set_feature_flag(db, bot_id, feature_key, enabled, config)`
   - `get_all_feature_flags(db, bot_id)`
   - `delete_feature_flag(db, bot_id, feature_key)`
3. Test feature flags
4. Test config storage

**Acceptance:**
- ✅ Set feature flag works
- ✅ Get feature flag works
- ✅ Config storage works
- ✅ All CRUD operations work
- ✅ All tests pass

**Next:** Increment 1.4a

---

#### Increment 1.4a: Bot Configuration CRUD
**Priority:** 🟡 Medium  
**Time:** 2 hours  
**Dependencies:** Increment 1.3  
**Risk:** Low  
**Value:** Medium

**Tasks:**
1. Create `app/database/crud/bot_configuration.py`
2. Implement CRUD operations:
   - `get_configuration(db, bot_id, config_key)`
   - `set_configuration(db, bot_id, config_key, config_value)`
   - `get_all_configurations(db, bot_id)`
   - `delete_configuration(db, bot_id, config_key)`
3. Test configurations

**Acceptance:**
- ✅ All CRUD operations work
- ✅ JSONB storage works
- ✅ All tests pass

**Next:** Increment 1.4b

---

#### Increment 1.4b: Payment Card CRUD
**Priority:** 🟡 Medium  
**Time:** 3 hours  
**Dependencies:** Increment 1.3  
**Risk:** Low  
**Value:** Medium

**Tasks:**
1. Create `app/database/crud/tenant_payment_card.py`
2. Implement CRUD operations:
   - `create_payment_card(db, bot_id, card_number, ...)`
   - `get_payment_card(db, card_id)`
   - `get_payment_cards(db, bot_id, active_only=True)`
   - `update_payment_card(db, card_id, ...)`
   - `delete_payment_card(db, card_id)`
   - `get_next_card_for_rotation(db, bot_id, strategy='round_robin')`
   - `update_card_usage(db, card_id, success=True)`
3. Implement rotation logic
4. Test card rotation

**Acceptance:**
- ✅ All CRUD operations work
- ✅ Rotation strategies work (round_robin, random, time_based, weighted)
- ✅ Usage tracking works
- ✅ All tests pass

**Next:** Increment 1.4c

---

#### Increment 1.4c: Bot Plans CRUD
**Priority:** 🟡 Medium  
**Time:** 2 hours  
**Dependencies:** Increment 1.3  
**Risk:** Low  
**Value:** Medium

**Tasks:**
1. Create `app/database/crud/bot_plan.py`
2. Implement CRUD operations:
   - `create_plan(db, bot_id, name, period_days, price_toman, ...)`
   - `get_plan(db, plan_id)`
   - `get_plans(db, bot_id, active_only=True)`
   - `update_plan(db, plan_id, ...)`
   - `delete_plan(db, plan_id)`
   - `activate_plan(db, plan_id)`
   - `deactivate_plan(db, plan_id)`
3. Test plans

**Acceptance:**
- ✅ All CRUD operations work
- ✅ Plans filtered by bot_id
- ✅ Active/inactive filtering works
- ✅ All tests pass

**Next:** Increment 1.5

---

#### Increment 1.5: Bot Context Middleware
**Priority:** 🔴 Critical  
**Time:** 2 hours  
**Dependencies:** Increment 1.3  
**Risk:** Medium  
**Value:** High

**Why Next:**
- نیاز به bot CRUD دارد
- پایه همه handlers
- قابل تست

**Tasks:**
1. Create `app/middlewares/bot_context.py`
2. Register middleware
3. Test injection
4. Test error handling

**Acceptance:**
- ✅ Middleware injects bot_id
- ✅ Works for all event types
- ✅ Error handling works
- ✅ No performance issues

**Next:** Increment 2.1

---

### Phase 2: Core Features (Week 2)

#### Increment 2.1: Add bot_id to Users Table
**Status:** ✅ **COMPLETED**  
**Priority:** 🔴 Critical  
**Time:** 3 hours  
**Dependencies:** Increment 1.1  
**Risk:** Medium  
**Value:** High

**Why Next:**
- پایه data isolation
- نیاز به schema migration
- قابل تست

**Tasks:**
1. Create migration script
2. Add bot_id column (nullable)
3. Create index
4. Update unique constraint
5. Test migration

**Acceptance:**
- ✅ Column added
- ✅ Index created
- ✅ Unique constraint updated
- ✅ No data loss

**Implementation Summary:**
- `bot_id` column added to User model (nullable=True, indexed)
- Unique constraint updated: `(telegram_id, bot_id)`
- Relationship to Bot model established
- Model verified and tested

**Next:** Increment 2.2

---

#### Increment 2.2: Update User CRUD
**Status:** ✅ **COMPLETED**  
**Priority:** 🔴 Critical  
**Time:** 4 hours  
**Dependencies:** Increment 2.1, 1.5  
**Risk:** Medium  
**Value:** High

**Why Next:**
- نیاز به bot_id column دارد
- پایه همه user operations
- قابل تست

**Tasks:**
1. Update all user CRUD functions
2. Add bot_id parameter
3. Add bot_id filter
4. Update all call sites
5. Test all operations

**Acceptance:**
- ✅ All functions updated
- ✅ All queries filter by bot_id
- ✅ All tests pass
- ✅ No regressions

**Implementation Summary:**
- Updated 11 CRUD functions to accept optional `bot_id` parameter
- Added `bot_id` filtering to all query functions
- Added helper function `get_user_by_telegram_id_and_bot_id()`
- Maintained backward compatibility (bot_id is optional)
- All functions tested and verified

**Next:** Increment 2.3

---

#### Increment 2.3: Update Subscription CRUD
**Status:** ✅ **COMPLETED**  
**Priority:** 🟡 High  
**Time:** 3 hours  
**Dependencies:** Increment 2.2  
**Risk:** Medium  
**Value:** High

**Why Next:**
- نیاز به user CRUD دارد
- پایه subscription operations
- قابل تست

**Tasks:**
1. Add bot_id to subscriptions table (migration)
2. Update `app/database/crud/subscription.py`
3. Add `bot_id` parameter to all functions
4. Add `bot_id` filter to all queries
5. Update all call sites
6. Test all operations

**Acceptance:**
- ✅ Migration script created and tested
- ✅ All functions updated
- ✅ All queries filter by bot_id
- ✅ All call sites updated
- ✅ All tests pass

**Implementation Summary:**
- Updated 9 CRUD functions to accept optional `bot_id` parameter:
  - `get_subscription_by_user_id()` - Added bot_id filter
  - `create_trial_subscription()` - Added bot_id parameter
  - `create_paid_subscription()` - Added bot_id parameter
  - `create_subscription()` - Added bot_id parameter
  - `create_subscription_no_commit()` - Added bot_id parameter
  - `get_expiring_subscriptions()` - Added bot_id filter
  - `get_expired_subscriptions()` - Added bot_id filter
  - `get_subscriptions_for_autopay()` - Added bot_id filter
  - `get_all_subscriptions()` - Added bot_id filter
- Updated statistics functions:
  - `get_subscriptions_statistics()` - Added bot_id filter to all queries
  - `get_trial_statistics()` - Added bot_id filter to all queries
- Maintained backward compatibility (bot_id is optional)
- All functions tested and verified

**Next:** Increment 2.3a

---

#### Increment 2.3a: Update Transaction CRUD
**Priority:** 🟡 High  
**Time:** 2 hours  
**Dependencies:** Increment 2.3  
**Risk:** Medium  
**Value:** High

**Tasks:**
1. Add bot_id to transactions table (migration)
2. Update `app/database/crud/transaction.py`
3. Add `bot_id` parameter to all functions
4. Add `bot_id` filter to all queries
5. Update all call sites
6. Test all operations

**Acceptance:**
- ✅ Migration script created and tested
- ✅ All functions updated
- ✅ All queries filter by bot_id
- ✅ All call sites updated
- ✅ All tests pass

**Next:** Increment 2.3b

---

#### Increment 2.3b: Update Ticket CRUD
**Priority:** 🟡 Medium  
**Time:** 2 hours  
**Dependencies:** Increment 2.3a  
**Risk:** Low  
**Value:** Medium

**Tasks:**
1. Add bot_id to tickets table (migration)
2. Update `app/database/crud/ticket.py`
3. Add `bot_id` parameter to all functions
4. Add `bot_id` filter to all queries
5. Update all call sites
6. Test all operations

**Acceptance:**
- ✅ Migration script created and tested
- ✅ All functions updated
- ✅ All queries filter by bot_id
- ✅ All call sites updated
- ✅ All tests pass

**Next:** Increment 2.3c

---

#### Increment 2.3c: Update PromoCode and PromoGroup CRUD
**Priority:** 🟡 Medium  
**Time:** 3 hours  
**Dependencies:** Increment 2.3b  
**Risk:** Medium  
**Value:** Medium

**Tasks:**
1. Add bot_id to promocodes and promo_groups tables (migration)
2. Update unique constraints (code + bot_id, name + bot_id)
3. Update `app/database/crud/promocode.py`
4. Update `app/database/crud/promo_group.py`
5. Add `bot_id` parameter to all functions
6. Add `bot_id` filter to all queries
7. Update all call sites
8. Test all operations

**Acceptance:**
- ✅ Migration scripts created and tested
- ✅ Unique constraints updated
- ✅ All functions updated
- ✅ All queries filter by bot_id
- ✅ All call sites updated
- ✅ All tests pass

**Next:** Increment 2.3d

---

#### Increment 2.3d: Update Payment Model CRUDs
**Priority:** 🟡 Medium  
**Time:** 4 hours  
**Dependencies:** Increment 2.3c  
**Risk:** Medium  
**Value:** Medium

**Payment CRUD Files to Update:**
- `app/database/crud/yookassa_payment.py`
- `app/database/crud/cryptobot_payment.py`
- `app/database/crud/pal24_payment.py`
- `app/database/crud/mulenpay_payment.py`
- `app/database/crud/wata_payment.py`
- `app/database/crud/platega_payment.py`
- `app/database/crud/heleket_payment.py`
- `app/database/crud/tribute_payment.py`
- (Add any other payment CRUD files)

**Tasks for Each:**
1. Add bot_id to table (migration)
2. Add `bot_id` parameter to all functions
3. Add `bot_id` filter to all queries
4. Update all call sites
5. Test all operations

**Acceptance:**
- ✅ All payment CRUD files updated
- ✅ All migrations created and tested
- ✅ All functions updated
- ✅ All queries filter by bot_id
- ✅ All call sites updated
- ✅ All tests pass

**Next:** Increment 2.4

---

#### Increment 2.4: Feature Flag Service
**Status:** ✅ **COMPLETED**  
**Priority:** 🟡 High  
**Time:** 2 hours  
**Dependencies:** Increment 1.4  
**Risk:** Low  
**Value:** High

**Why Next:**
- نیاز به feature flag CRUD دارد
- پایه feature checking
- قابل تست

**Tasks:**
1. Create `app/services/tenant_feature_service.py`
2. Implement service methods:
   - `is_feature_enabled(db, bot_id, feature_key, use_cache=True)`
   - `get_feature_config(db, bot_id, feature_key)`
   - `set_feature(db, bot_id, feature_key, enabled, config)`
   - `get_all_features(db, bot_id)`
3. Implement caching (Redis or in-memory)
4. Implement cache invalidation
5. Test service
6. Test cache invalidation

**Caching Strategy:**
- Cache key: `feature_flag:{bot_id}:{feature_key}`
- TTL: 5 minutes (configurable)
- Invalidate on update

**Acceptance:**
- ✅ Service works
- ✅ Caching works (verify cache hits)
- ✅ Cache invalidation works
- ✅ Performance acceptable
- ✅ All tests pass

**Implementation Summary:**
- Created `TenantFeatureService` class with full caching support
- Implemented `is_feature_enabled()` with Redis caching (5 min TTL)
- Implemented `get_feature_config()` with separate cache for configs
- Implemented `set_feature()` with automatic cache invalidation
- Implemented `get_all_features()` to get all flags for a bot
- Implemented `invalidate_cache()` for manual cache invalidation
- Graceful fallback to database if cache unavailable
- Comprehensive logging for cache hits/misses
- All methods tested and verified

**Next:** Increment 2.4a

---

#### Increment 2.4a: Payment Card Rotation Service
**Priority:** 🟡 Medium  
**Time:** 3 hours  
**Dependencies:** Increment 1.4b  
**Risk:** Low  
**Value:** Medium

**Tasks:**
1. Create `app/services/payment_card_service.py`
2. Implement rotation service:
   - `get_next_card(bot_id, strategy='round_robin')`
   - `record_card_usage(card_id, success=True)`
   - `rotate_cards_if_needed(bot_id)`
3. Implement all rotation strategies
4. Test rotation logic

**Acceptance:**
- ✅ Round-robin rotation works
- ✅ Random rotation works
- ✅ Time-based rotation works
- ✅ Weighted rotation works
- ✅ Usage tracking works
- ✅ All tests pass

**Next:** Increment 2.4b

---

#### Increment 2.4b: Wallet Service
**Priority:** 🟡 Medium  
**Time:** 3 hours  
**Dependencies:** Increment 1.3  
**Risk:** Low  
**Value:** Medium

**Tasks:**
1. Create `app/services/wallet_service.py`
2. Implement wallet operations:
   - `get_wallet_balance(db, bot_id)`
   - `update_wallet_balance(db, bot_id, amount_toman, operation='add')`
   - `record_traffic_consumption(db, bot_id, bytes_consumed)`
   - `record_traffic_sold(db, bot_id, bytes_sold)`
   - `get_traffic_stats(db, bot_id)`
3. Test wallet operations

**Acceptance:**
- ✅ Balance operations work
- ✅ Traffic tracking works
- ✅ Stats calculation works
- ✅ All tests pass

**Next:** Increment 2.5

---

#### Increment 2.5: Multi-Bot Support
**Status:** ✅ **COMPLETED**  
**Priority:** 🔴 Critical
**Time:** 4 hours
**Dependencies:** Increment 1.3, 1.5
**Risk:** High
**Value:** High

**Why Next:**
- نیاز به bot CRUD و middleware دارد
- پایه multi-tenant
- قابل تست

**Tasks:**
1. Update `app/bot.py`
2. Implement multi-bot initialization
3. Update `main.py`
4. Test bot initialization
5. Test bot shutdown

**Acceptance:**
- ✅ All bots initialize
- ✅ All bots work independently
- ✅ Clean shutdown works

**Implementation Summary:**
- Created global registry: `active_bots` and `active_dispatchers` dictionaries
- Updated `setup_bot()` to accept optional `bot_config` parameter (backward compatible)
- Implemented `initialize_all_bots()` to load all active bots from database
- Updated `main.py` to use multi-bot initialization
- Implemented multi-bot polling (all bots poll simultaneously)
- Updated shutdown logic to handle all bots
- Maintained backward compatibility (falls back to single bot from settings if no bots in DB)
- All syntax checks passed

**Next:** Increment 3.1

---

### Phase 3: Integration (Week 3)

#### Increment 3.1: Update Start Handler
**Priority:** 🔴 Critical  
**Time:** 2 hours  
**Dependencies:** Increment 2.2, 2.5  
**Risk:** Medium  
**Value:** High

**Why Next:**
- نیاز به user CRUD و multi-bot دارد
- اولین handler
- قابل تست

**Tasks:**
1. Update `app/handlers/start.py`
2. Get bot_id from middleware
3. Pass bot_id to user creation
4. Test user registration

**Acceptance:**
- ✅ User created with bot_id
- ✅ No regressions
- ✅ Tests pass

**Next:** Increment 3.2

---

#### Increment 3.2: Update Core Handlers
**Priority:** 🔴 Critical  
**Time:** 6 hours  
**Dependencies:** Increment 3.1  
**Risk:** Medium  
**Value:** High

**Why Next:**
- نیاز به start handler دارد
- پایه همه handlers
- قابل تست

**Handlers to Update:**
1. `app/handlers/menu.py` - Get bot_id, filter queries
2. `app/handlers/promocode.py` - Get bot_id, update CRUD calls
3. `app/handlers/referral.py` - Get bot_id, update CRUD calls
4. `app/handlers/tickets.py` - Get bot_id, update CRUD calls
5. `app/handlers/support.py` - Get bot_id, update CRUD calls
6. `app/handlers/server_status.py` - Get bot_id, filter queries
7. `app/handlers/common.py` - Update helper functions to accept bot_id

**Tasks for Each Handler:**
1. Add `bot_id: int = None` parameter (from middleware)
2. Update all CRUD calls to include `bot_id` parameter
3. Update all queries to filter by `bot_id`
4. Test handler functionality

**Acceptance:**
- ✅ All handlers updated
- ✅ All CRUD calls include bot_id
- ✅ All queries filter by bot_id
- ✅ No regressions
- ✅ Tests pass

**Next:** Increment 3.3

---

#### Increment 3.3: Update Payment Handlers - Card-to-Card
**Priority:** 🔴 Critical  
**Time:** 4 hours  
**Dependencies:** Increment 3.2  
**Risk:** Medium  
**Value:** High

**Why Next:**
- نیاز به core handlers دارد
- مهم برای business
- قابل تست

**Tasks:**
1. Create `app/handlers/balance/card_to_card.py` (NEW)
2. Implement card selection handler
3. Implement receipt submission handler
4. Implement admin notification
5. Implement admin approval/rejection handlers
6. Update payment flow to use card-to-card

**Card-to-Card Flow:**
1. User selects card-to-card payment
2. Display card info from `tenant_payment_cards` (with rotation)
3. User submits receipt (image/text)
4. Create `CardToCardPayment` record
5. Generate tracking number
6. Send notification to admin (with approve/reject buttons)
7. Admin reviews and approves/rejects
8. On approval: Complete transaction, create subscription

**Acceptance:**
- ✅ Card-to-card handler created
- ✅ Receipt submission works
- ✅ Admin notification sent
- ✅ Admin approval/rejection works
- ✅ Transaction completed on approval
- ✅ Tests pass

**Next:** Increment 3.4

---

#### Increment 3.4: Update Payment Handlers - Zarinpal
**Priority:** 🟡 High  
**Time:** 4 hours  
**Dependencies:** Increment 3.3  
**Risk:** Medium  
**Value:** High

**Why Next:**
- نیاز به payment handlers دارد
- مهم برای business
- قابل تست

**Tasks:**
1. Create `app/external/zarinpal.py` (NEW)
2. Implement Zarinpal client
3. Create `app/handlers/balance/zarinpal.py` (NEW)
4. Implement payment request handler
5. Implement callback handler
6. Implement payment verification
7. Update payment flow to use Zarinpal

**Zarinpal Flow:**
1. User selects Zarinpal payment
2. Create payment request via Zarinpal API
3. Get `authority` and `payment_url`
4. Redirect user to payment URL
5. Handle callback from Zarinpal
6. Verify payment with `authority`
7. On success: Complete transaction, create subscription

**Acceptance:**
- ✅ Zarinpal client created
- ✅ Payment request works
- ✅ Callback handling works
- ✅ Payment verification works
- ✅ Transaction completed on success
- ✅ Tests pass

**Next:** Increment 3.5

---

#### Increment 3.5: Update Other Payment Handlers
**Priority:** 🟡 High  
**Time:** 6 hours  
**Dependencies:** Increment 3.4  
**Risk:** Medium  
**Value:** High

**Why Next:**
- نیاز به payment handlers دارد
- پشتیبانی از همه payment methods
- قابل تست

**Handlers to Update:**
1. `app/handlers/balance/yookassa.py` - Add bot_id, feature flag check
2. `app/handlers/balance/cryptobot.py` - Add bot_id, feature flag check
3. `app/handlers/balance/pal24.py` - Add bot_id, feature flag check
4. `app/handlers/balance/mulenpay.py` - Add bot_id, feature flag check
5. `app/handlers/balance/wata.py` - Add bot_id, feature flag check
6. `app/handlers/balance/platega.py` - Add bot_id, feature flag check
7. `app/handlers/balance/heleket.py` - Add bot_id, feature flag check
8. `app/handlers/balance/tribute.py` - Add bot_id, feature flag check
9. `app/handlers/stars_payments.py` - Add bot_id, feature flag check

**Tasks for Each Handler:**
1. Add `bot_id: int = None` parameter
2. Check feature flag before processing
3. Update all CRUD calls to include `bot_id`
4. Update all queries to filter by `bot_id`
5. Test handler functionality

**Acceptance:**
- ✅ All payment handlers updated
- ✅ Feature flags checked
- ✅ All CRUD calls include bot_id
- ✅ All queries filter by bot_id
- ✅ No regressions
- ✅ Tests pass

**Next:** Increment 3.6

---

#### Increment 3.6: Update Subscription Handlers
**Priority:** 🟡 High  
**Time:** 4 hours  
**Dependencies:** Increment 3.5  
**Risk:** Medium  
**Value:** High

**Why Next:**
- نیاز به payment handlers دارد
- مهم برای business
- قابل تست

**Handlers to Update:**
1. `app/handlers/subscription/purchase.py` - Add bot_id, use bot_plans
2. `app/handlers/subscription/pricing.py` - Add bot_id, filter plans by bot_id
3. `app/handlers/subscription/common.py` - Update helpers to accept bot_id
4. `app/handlers/subscription/devices.py` - Add bot_id
5. `app/handlers/subscription/traffic.py` - Add bot_id
6. `app/handlers/subscription/autopay.py` - Add bot_id
7. `app/handlers/subscription/links.py` - Add bot_id
8. `app/handlers/subscription/notifications.py` - Add bot_id

**Tasks for Each Handler:**
1. Add `bot_id: int = None` parameter
2. Update plan queries to use `bot_plans` filtered by `bot_id`
3. Update all CRUD calls to include `bot_id`
4. Update all queries to filter by `bot_id`
5. Test handler functionality

**Acceptance:**
- ✅ All subscription handlers updated
- ✅ Plans filtered by bot_id
- ✅ All CRUD calls include bot_id
- ✅ All queries filter by bot_id
- ✅ No regressions
- ✅ Tests pass

**Next:** Increment 4.1

---

#### Increment 3.7: Update Admin Handlers
**Priority:** 🟡 Medium  
**Time:** 8 hours  
**Dependencies:** Increment 3.6  
**Risk:** Low  
**Value:** Medium

**Why Next:**
- نیاز به core handlers دارد
- Admin functionality
- قابل تست

**Handlers to Update:**
All handlers in `app/handlers/admin/`:
- Add `bot_id` parameter
- Filter queries by `bot_id`
- Update CRUD calls

**Note:** This is a large increment. Can be broken into smaller increments if needed.

**Acceptance:**
- ✅ All admin handlers updated
- ✅ All queries filter by bot_id
- ✅ No regressions
- ✅ Tests pass

**Next:** Increment 4.1

---

#### Increment 3.3: Update Payment Handlers
**Priority:** 🟡 High  
**Time:** 6 hours  
**Dependencies:** Increment 3.1  
**Risk:** Medium  
**Value:** High

**Why Next:**
- نیاز به handlers دارد
- مهم برای business
- قابل تست

**Tasks:**
1. Update all payment handlers
2. Add feature flag checks
3. Test all payment flows

**Acceptance:**
- ✅ All handlers updated
- ✅ Feature flags checked
- ✅ Tests pass

**Next:** Increment 3.8

---

#### Increment 3.8: API Endpoints for Bot Management
**Priority:** 🟡 Medium  
**Time:** 6 hours  
**Dependencies:** Increment 3.7  
**Risk:** Medium  
**Value:** Medium

**Why Next:**
- نیاز به همه handlers دارد
- API برای مدیریت bots
- قابل تست

**Tasks:**
1. Create `app/webapi/middleware/auth.py` - API token authentication
2. Create `app/webapi/routes/bots.py` - Bot management endpoints
3. Implement endpoints:
   - `POST /api/v1/bots` - Create bot
   - `GET /api/v1/bots` - List bots
   - `GET /api/v1/bots/{bot_id}` - Get bot
   - `PUT /api/v1/bots/{bot_id}` - Update bot
   - `DELETE /api/v1/bots/{bot_id}` - Delete bot
   - `POST /api/v1/bots/{bot_id}/activate` - Activate bot
   - `POST /api/v1/bots/{bot_id}/deactivate` - Deactivate bot
4. Implement authentication middleware
5. Test all endpoints

**Authentication:**
- Header: `X-API-Token: <token>` or `Authorization: Bearer <token>`
- Verify token hash against database
- Return 401 if invalid

**Acceptance:**
- ✅ Authentication middleware works
- ✅ All endpoints implemented
- ✅ Token authentication works
- ✅ All CRUD operations work via API
- ✅ All tests pass

**Next:** Increment 3.9

---

#### Increment 3.9: API Endpoints for Feature Flags and Config
**Priority:** 🟡 Medium  
**Time:** 4 hours  
**Dependencies:** Increment 3.8  
**Risk:** Low  
**Value:** Medium

**Tasks:**
1. Create `app/webapi/routes/features.py`
2. Create `app/webapi/routes/config.py`
3. Implement feature flag endpoints:
   - `GET /api/v1/bots/{bot_id}/features` - List features
   - `GET /api/v1/bots/{bot_id}/features/{feature_key}` - Get feature
   - `PUT /api/v1/bots/{bot_id}/features/{feature_key}` - Set feature
   - `DELETE /api/v1/bots/{bot_id}/features/{feature_key}` - Delete feature
4. Implement config endpoints:
   - `GET /api/v1/bots/{bot_id}/config` - List configs
   - `GET /api/v1/bots/{bot_id}/config/{config_key}` - Get config
   - `PUT /api/v1/bots/{bot_id}/config/{config_key}` - Set config
   - `DELETE /api/v1/bots/{bot_id}/config/{config_key}` - Delete config
5. Test all endpoints

**Acceptance:**
- ✅ All endpoints implemented
- ✅ Feature flag management works
- ✅ Config management works
- ✅ All tests pass

**Next:** Increment 4.1

---

### Phase 4: Migration (Week 4)

#### Increment 4.1: Data Migration Script
**Priority:** 🔴 Critical  
**Time:** 3 hours  
**Dependencies:** All previous increments  
**Risk:** High  
**Value:** Critical

**Why Last:**
- نیاز به همه چیز دارد
- فقط یکبار اجرا می‌شود
- نیاز به backup

**Tasks:**
1. Create `migrations/003_migrate_existing_data.py`
2. Backup database first
3. Create master bot with current BOT_TOKEN
4. Assign all existing users to master bot
5. Assign all existing subscriptions to master bot
6. Assign all existing transactions to master bot
7. Assign all existing tickets to master bot
8. Assign all existing promocodes to master bot
9. Assign all existing payment records to master bot
10. Make bot_id NOT NULL (after assignment)
11. Test migration on staging
12. Create rollback script

**Migration Script Structure:**
```python
async def migrate_existing_data():
    # 1. Create master bot
    # 2. Get master bot_id
    # 3. Update all tables: UPDATE table SET bot_id = master_bot_id WHERE bot_id IS NULL
    # 4. Make bot_id NOT NULL: ALTER TABLE table ALTER COLUMN bot_id SET NOT NULL
```

**Acceptance:**
- ✅ Backup created before migration
- ✅ Master bot created successfully
- ✅ All data assigned to master bot
- ✅ No data loss (verify counts match)
- ✅ bot_id columns set to NOT NULL
- ✅ Rollback script created and tested
- ✅ Migration tested on staging

**Next:** Increment 4.2

---

#### Increment 4.2: Production Deployment
**Priority:** 🔴 Critical  
**Time:** 4 hours  
**Dependencies:** Increment 4.1  
**Risk:** High  
**Value:** Critical

**Why Last:**
- نیاز به migration دارد
- Production deployment
- نیاز به monitoring

**Pre-Deployment Checklist:**
- [ ] All increments completed and tested
- [ ] All tests passing
- [ ] Code review completed
- [ ] Database backup taken
- [ ] Migration script tested on staging
- [ ] Rollback plan ready
- [ ] Team notified
- [ ] Monitoring set up

**Deployment Steps:**
1. **Stop Application**
   ```bash
   # Stop bot and web server
   systemctl stop remnabot
   ```

2. **Backup Database**
   ```bash
   pg_dump remnawave_bot > backup_before_migration_$(date +%Y%m%d_%H%M%S).sql
   ```

3. **Run Schema Migrations**
   ```bash
   # Run increment 1.1 migration
   psql remnawave_bot < migrations/001_create_multi_tenant_tables.sql
   
   # Run increment 2.1 migration (add bot_id columns)
   psql remnawave_bot < migrations/002_add_bot_id_to_tables.sql
   ```

4. **Deploy Code**
   ```bash
   git pull origin main
   # Or: Deploy via CI/CD
   ```

5. **Run Data Migration**
   ```bash
   python migrations/003_migrate_existing_data.py
   ```

6. **Verify Migration**
   ```sql
   -- Check master bot exists
   SELECT * FROM bots WHERE is_master = TRUE;
   
   -- Check all users have bot_id
   SELECT COUNT(*) FROM users WHERE bot_id IS NULL;  -- Should be 0
   
   -- Check data counts match
   SELECT COUNT(*) FROM users;  -- Should match pre-migration count
   ```

7. **Start Application**
   ```bash
   systemctl start remnabot
   ```

8. **Monitor**
   - Check logs for errors
   - Verify bot responds
   - Test user registration
   - Test payment flow
   - Monitor database queries

**Post-Deployment Verification:**
- [ ] Bot responds to /start
- [ ] User registration works
- [ ] Payment flows work
- [ ] No errors in logs
- [ ] Database queries include bot_id
- [ ] Performance acceptable

**Rollback Plan:**
1. Stop application
2. Restore database from backup
3. Revert code to previous version
4. Start application
5. Verify system working

**Acceptance:**
- ✅ All pre-deployment checks passed
- ✅ Database backup created
- ✅ Schema migrations successful
- ✅ Code deployed
- ✅ Data migration successful
- ✅ Application started
- ✅ All verification tests passed
- ✅ No errors in logs
- ✅ Rollback plan ready

**Next:** Post-Deployment Monitoring

---

## 🔄 Workflow Recommendations

### Workflow 1: Sequential (Recommended for First Time)

**Best For:**
- تیم‌های کوچک
- اولین بار migration
- نیاز به یادگیری

**Process:**
1. Complete increment 1.1
2. Test thoroughly
3. Review with team
4. Move to 1.2
5. Repeat

**Pros:**
- ✅ کم ریسک
- ✅ یادگیری بهتر
- ✅ کیفیت بالا

**Cons:**
- ⚠️ کندتر
- ⚠️ نیاز به patience

---

### Workflow 2: Parallel (For Experienced Teams)

**Best For:**
- تیم‌های بزرگ
- تجربه بالا
- نیاز به سرعت

**Process:**
1. Assign increments to different developers
2. Work in parallel
3. Daily sync
4. Merge carefully

**Pros:**
- ✅ سریعتر
- ✅ استفاده بهتر از resources

**Cons:**
- ⚠️ نیاز به coordination
- ⚠️ ریسک merge conflicts

---

### Workflow 3: Hybrid (Recommended)

**Best For:**
- بیشتر تیم‌ها
- تعادل بین سرعت و کیفیت

**Process:**
1. Foundation increments sequential (1.1-1.5)
2. Core features parallel (2.1-2.5)
3. Integration sequential (3.1-3.3)
4. Migration careful (4.1)

**Pros:**
- ✅ تعادل خوب
- ✅ کیفیت + سرعت

**Cons:**
- ⚠️ نیاز به planning

---

## ⚠️ Common Pitfalls & Solutions

### Pitfall 1: Skipping Tests

**Problem:** 
- "این increment کوچک است، تست نمی‌کنم"
- بعداً باگ پیدا می‌شود

**Solution:**
- ✅ همیشه تست کنید
- ✅ حتی برای کوچک‌ترین تغییرات
- ✅ Test-driven approach

---

### Pitfall 2: Ignoring Dependencies

**Problem:**
- شروع increment بدون prerequisites
- بعداً باید refactor کنید

**Solution:**
- ✅ همیشه dependencies را چک کنید
- ✅ از dependency graph استفاده کنید
- ✅ اگر prerequisite ندارید، اول آن را انجام دهید

---

### Pitfall 3: Big Bang Approach

**Problem:**
- انجام همه چیز یکجا
- تست سخت می‌شود
- باگ‌ها پیدا نمی‌شوند

**Solution:**
- ✅ Incremental approach
- ✅ Small, testable increments
- ✅ Regular testing

---

### Pitfall 4: Not Updating Call Sites

**Problem:**
- CRUD را update می‌کنید
- اما call sites را فراموش می‌کنید
- Runtime errors

**Solution:**
- ✅ همیشه call sites را update کنید
- ✅ از IDE search استفاده کنید
- ✅ Test all call sites

---

### Pitfall 5: Forgetting bot_id in Queries

**Problem:**
- Query می‌نویسید
- bot_id را فراموش می‌کنید
- Data leakage بین tenants

**Solution:**
- ✅ همیشه bot_id را اضافه کنید
- ✅ از helper functions استفاده کنید
- ✅ Code review

---

## 📋 Daily Checklist

### Before Starting Work

- [ ] Review current increment
- [ ] Check dependencies
- [ ] Read relevant documentation
- [ ] Set up test environment

### During Work

- [ ] Write tests first (TDD)
- [ ] Make small commits
- [ ] Test frequently
- [ ] Document changes

### After Completing Increment

- [ ] All tests pass
- [ ] Code review
- [ ] Update documentation
- [ ] Mark increment complete
- [ ] Plan next increment

---

## 🎯 Success Criteria

### For Each Increment

- ✅ All tests pass
- ✅ No regressions
- ✅ Code reviewed
- ✅ Documented
- ✅ Ready for next increment

### For Overall Migration

- ✅ All increments complete
- ✅ All tests pass
- ✅ No data loss
- ✅ Performance acceptable
- ✅ Production ready

---

## 📞 Getting Help

### When Stuck

1. **Review Documentation**
   - Check relevant section
   - Read examples
   - Check common pitfalls

2. **Check Tests**
   - Look at test examples
   - Run existing tests
   - Write test to understand

3. **Ask Team**
   - Daily standup
   - Code review
   - Architecture discussion

4. **Review Code**
   - Look at similar patterns
   - Check existing implementations
   - Learn from codebase

---

## 🚀 Next Steps - راهنمای شروع

### مرحله 1: انتخاب Increment

**برای شروع، Increment 1.1 را انتخاب کنید:**

**Increment 1.1: Database Schema - New Tables**
- **Priority:** 🔴 Critical
- **Time:** 2 hours
- **Dependencies:** None
- **Risk:** Low
- **Value:** High

**چرا این increment:**
- ✅ پایه همه چیز است
- ✅ بدون dependencies
- ✅ قابل تست فوری
- ✅ ریسک کم

**Tasks:**
1. Create migration script: `migrations/001_create_multi_tenant_tables.sql`
2. Run migration on dev database
3. Verify tables: `SELECT table_name FROM information_schema.tables WHERE table_name IN ('bots', 'bot_feature_flags');`
4. Verify indexes: `SELECT indexname FROM pg_indexes WHERE tablename = 'bots';`
5. Test foreign keys

**Acceptance:**
- ✅ All 7 new tables created
- ✅ All indexes created
- ✅ Foreign keys working
- ✅ No errors

**Next Increment:** 1.2 (Database Models)

---

### مرحله 2: Setup Environment

**قبل از شروع:**

1. **Backup Database**
   ```bash
   pg_dump remnawave_bot > backup_$(date +%Y%m%d).sql
   ```

2. **Create Feature Branch**
   ```bash
   git checkout -b feature/multi-tenant-increment-1.1
   ```

3. **Set Up Test Environment**
   ```bash
   # Create test database
   createdb remnawave_bot_test
   
   # Run migrations
   psql remnawave_bot_test < migrations/001_create_multi_tenant_tables.sql
   ```

---

### مرحله 3: شروع کار

**مراحل:**

1. **Read Documentation**
   - [Database Schema](./01-database-schema.md)
   - [Implementation Tasks](./04-implementation-tasks.md) - Task 1

2. **Create Migration Script**
   - File: `migrations/001_create_multi_tenant_tables.sql`
   - Include all 7 tables
   - Include all indexes

3. **Test Migration**
   ```bash
   psql remnawave_bot_test < migrations/001_create_multi_tenant_tables.sql
   ```

4. **Verify**
   ```sql
   -- Check tables
   SELECT table_name FROM information_schema.tables 
   WHERE table_schema = 'public' 
   AND table_name IN ('bots', 'bot_feature_flags', 'bot_configurations', 
                      'tenant_payment_cards', 'bot_plans', 
                      'card_to_card_payments', 'zarinpal_payments');
   
   -- Should return 7 rows
   ```

5. **Commit**
   ```bash
   git add migrations/001_create_multi_tenant_tables.sql
   git commit -m "feat: Add multi-tenant tables (Increment 1.1)"
   ```

---

### مرحله 4: Track Progress

**بعد از تکمیل هر increment:**

1. ✅ Mark increment complete
2. ✅ Update documentation if needed
3. ✅ Share progress with team
4. ✅ Plan next increment
5. ✅ Review dependencies for next increment

---

## 📊 Increment Progress Tracker

### Phase 1: Foundation
- [x] 1.1 Database Schema (New Tables) - ✅ **COMPLETED**
- [x] 1.2 Database Models (New Models) - ✅ **COMPLETED**
- [x] 1.3 Bot CRUD Operations - ✅ **COMPLETED**
- [x] 1.4 Feature Flag CRUD - ✅ **COMPLETED**
- [x] 1.5 Bot Context Middleware - ✅ **COMPLETED**

### Phase 2: Core Features
- [x] 2.1 Add bot_id to Users Table - ✅ **COMPLETED**
- [x] 2.2 Update User CRUD - ✅ **COMPLETED**
- [x] 2.3 Update Subscription CRUD - ✅ **COMPLETED**
- [x] 2.4 Feature Flag Service - ✅ **COMPLETED**
- [x] 2.5 Multi-Bot Support - ✅ **COMPLETED**

### Phase 3: Integration
- [x] 3.1 Update Start Handler - ✅ **COMPLETED**
- [x] 3.2 Update Other Handlers - ✅ **COMPLETED** (referral.py, user_utils.py)
- [x] 3.3 Update Payment Handlers - ✅ **COMPLETED** (card-to-card handler + CRUD)

### Phase 4: Migration
- [ ] 4.1 Data Migration Script
- [ ] 4.2 Production Deployment

---

## 🎯 Workflow Recommendations

### برای تیم کوچک (1-2 Developer)

**Workflow: Sequential**

1. Complete increment 1.1
2. Test thoroughly
3. Review with team
4. Move to 1.2
5. Repeat

**Pros:**
- ✅ کم ریسک
- ✅ کیفیت بالا
- ✅ یادگیری بهتر

**Cons:**
- ⚠️ کندتر

---

### برای تیم بزرگ (3+ Developers)

**Workflow: Hybrid**

1. Foundation increments sequential (1.1-1.5)
2. Core features parallel (2.1-2.5)
3. Integration sequential (3.1-3.3)
4. Migration careful (4.1)

**Pros:**
- ✅ تعادل خوب
- ✅ کیفیت + سرعت

**Cons:**
- ⚠️ نیاز به coordination

---

## ⚠️ Common Pitfalls

### Pitfall 1: Skipping Tests

**Problem:** "این increment کوچک است، تست نمی‌کنم"

**Solution:**
- ✅ همیشه تست کنید
- ✅ حتی برای کوچک‌ترین تغییرات
- ✅ Test-driven approach

---

### Pitfall 2: Ignoring Dependencies

**Problem:** شروع increment بدون prerequisites

**Solution:**
- ✅ همیشه dependencies را چک کنید
- ✅ از [Increment Selection Guide](./08-increment-selection-guide.md) استفاده کنید
- ✅ اگر prerequisite ندارید، اول آن را انجام دهید

---

### Pitfall 3: Big Bang Approach

**Problem:** انجام همه چیز یکجا

**Solution:**
- ✅ Incremental approach
- ✅ Small, testable increments
- ✅ Regular testing

---

## 📋 Daily Checklist

### Before Starting Work
- [ ] Review current increment
- [ ] Check dependencies
- [ ] Read relevant documentation
- [ ] Set up test environment

### During Work
- [ ] Write tests first (TDD)
- [ ] Make small commits
- [ ] Test frequently
- [ ] Document changes

### After Completing Increment
- [ ] All tests pass
- [ ] Code review
- [ ] Update documentation
- [ ] Mark increment complete
- [ ] Plan next increment

---

## 🎯 Success Criteria

### For Each Increment
- ✅ All tests pass
- ✅ No regressions
- ✅ Code reviewed
- ✅ Documented
- ✅ Ready for next increment

### For Overall Migration
- ✅ All increments complete
- ✅ All tests pass
- ✅ No data loss
- ✅ Performance acceptable
- ✅ Production ready

---

## 📞 Getting Help

### When Stuck

1. **Review Documentation**
   - Check relevant section
   - Read examples
   - Check common pitfalls

2. **Check Tests**
   - Look at test examples
   - Run existing tests
   - Write test to understand

3. **Ask Team**
   - Daily standup
   - Code review
   - Architecture discussion

4. **Review Code**
   - Look at similar patterns
   - Check existing implementations
   - Learn from codebase

---

## 🚀 Ready to Start?

1. ✅ Read [Overview](./00-overview.md)
2. ✅ Read [Database Schema](./01-database-schema.md)
3. ✅ Read [Increment Selection Guide](./08-increment-selection-guide.md)
4. ✅ Choose increment (Start with 1.1)
5. ✅ Set up environment
6. ✅ Start working!

---

**Remember:** 
- ✅ Incremental approach
- ✅ Test everything
- ✅ Small commits
- ✅ Regular reviews
- ✅ Patience

**Good Luck! 🚀**

---

**Related Documents:**
- [Overview](./00-overview.md)
- [Database Schema](./01-database-schema.md)
- [Increment Selection Guide](./08-increment-selection-guide.md)
- [Implementation Tasks](./04-implementation-tasks.md)
