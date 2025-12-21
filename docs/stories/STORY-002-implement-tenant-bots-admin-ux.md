# Story: Implement Tenant Bots Admin UX Panel

**Story ID:** STORY-002  
**Epic:** Multi-Tenant Architecture - Admin Panel  
**Priority:** ⚠️ HIGH  
**Status:** Draft  
**Created:** 2025-12-15  
**Estimated Effort:** 50-70 hours (updated based on validation)

---

## 🚨 CRITICAL DEPENDENCIES - READ BEFORE STARTING

**⚠️ BLOCKER:** This story **CANNOT START** until the following are complete:

1. **STORY-001 (BotConfigService)** - **MUST BE COMPLETE**
   - BotConfigService must be fully implemented and tested
   - Required for: AC5, AC6, AC7, AC9
   - Verify service exists at: `app/services/bot_config_service.py`
   - Verify all methods work: `is_feature_enabled()`, `get_config()`, `set_feature_enabled()`, `set_config()`

2. **Database Schema Verification** - **MUST VERIFY BEFORE STARTING**
   - Verify these tables exist:
     - `tenant_subscriptions` (referenced in AC2, AC6)
     - `tenant_subscription_plans` (referenced in AC2, AC6)
     - `plan_feature_grants` (referenced in AC6)
   - If tables don't exist, add migration tasks to this story
   - Or update queries to use existing schema

**Action Required:** Verify dependencies before sprint planning.

---

## 📋 Story Summary

Implement a comprehensive admin panel UX for managing tenant bots, including menu navigation, statistics, feature flags management, payment methods configuration, subscription plans management, and categorized configuration settings.

**Note:** Some basic functionality already exists in `app/handlers/admin/tenant_bots.py` (menu, list, detail, create bot, basic settings). This story extends and completes the implementation.

---

## 🎯 Business Value

- **Master Admin Control** - Complete visibility and control over all tenant bots
- **Operational Efficiency** - Easy management of tenant configurations without code changes
- **Troubleshooting** - Quick access to tenant bot settings for issue resolution
- **Business Intelligence** - Statistics and analytics for tenant performance
- **Scalability** - Support for managing multiple tenant bots from single interface

---

## 📖 User Story

**As a** master admin  
**I want** a comprehensive admin panel to manage tenant bots, view statistics, configure settings, and toggle features  
**So that** I can efficiently manage multiple tenant bots, troubleshoot issues, and monitor performance without direct database access

---

## ✅ Acceptance Criteria

### AC1: Main Tenant Bots Menu
- [x] Handler exists: `app/handlers/admin/tenant_bots.py::show_tenant_bots_menu` ✅ **PARTIALLY IMPLEMENTED**
- [ ] Main menu displays tenant bots overview with statistics
- [ ] Shows total bots count (active/inactive breakdown)
- [ ] Shows aggregate statistics (total users, total revenue) - **UPDATE QUERY TO MATCH SPEC BELOW**
- [ ] Provides navigation to: List Bots, Create Bot, Statistics, Settings - **ADD MISSING BUTTONS**
- [ ] Menu follows existing admin panel design patterns
- [ ] Callback: `admin_tenant_bots_menu`

**Database Query:**
```sql
SELECT 
    COUNT(*) FILTER (WHERE is_master = FALSE) as total_bots,
    COUNT(*) FILTER (WHERE is_master = FALSE AND is_active = TRUE) as active_bots,
    COUNT(*) FILTER (WHERE is_master = FALSE AND is_active = FALSE) as inactive_bots,
    (SELECT COUNT(*) FROM users WHERE bot_id IN (SELECT id FROM bots WHERE is_master = FALSE)) as total_users,
    (SELECT COALESCE(SUM(amount_toman), 0) FROM transactions WHERE bot_id IN (SELECT id FROM bots WHERE is_master = FALSE) AND type = 'deposit') as total_revenue
FROM bots;
```

### AC2: List Bots with Pagination
- [x] Handler exists: `app/handlers/admin/tenant_bots.py::list_tenant_bots` ✅ **IMPLEMENTED**
- [x] Displays paginated list of tenant bots (5 per page) ✅
- [x] Each bot shows: Name, ID, Status, User Count, Revenue, Plan ✅ **COMPLETE**
- [x] Clicking a bot navigates to bot detail menu ✅
- [x] Pagination controls (Previous/Next) work correctly ✅
- [x] Callback: `admin_tenant_bots_list` or `admin_tenant_bots_list:{page}` ✅ **COMPLETE**
- [x] **UPDATE QUERY** - Query updated to match spec below (includes tenant_subscriptions join) ✅ **COMPLETE**

**Database Query:**
```sql
SELECT 
    b.*,
    COUNT(DISTINCT u.id) as user_count,
    COALESCE(SUM(t.amount_toman), 0) as revenue,
    ts.plan_tier_id,
    tsp.display_name as plan_name
FROM bots b
LEFT JOIN users u ON u.bot_id = b.id
LEFT JOIN transactions t ON t.bot_id = b.id AND t.type = 'deposit' AND t.is_completed = TRUE
LEFT JOIN tenant_subscriptions ts ON ts.bot_id = b.id AND ts.status = 'active'
LEFT JOIN tenant_subscription_plans tsp ON tsp.id = ts.plan_tier_id
WHERE b.is_master = FALSE
GROUP BY b.id, ts.plan_tier_id, tsp.display_name
ORDER BY b.created_at DESC
LIMIT 5 OFFSET {page * 5};
```

**⚠️ Schema Verification Required:**
- Verify `tenant_subscriptions` table exists
- Verify `tenant_subscription_plans` table exists
- If tables don't exist, use simplified query without plan information or add migration task

### AC3: Bot Detail Menu
- [x] Handler exists: `app/handlers/admin/tenant_bots.py::show_bot_detail` ✅ **PARTIALLY IMPLEMENTED**
- [x] Displays bot overview with quick stats ✅
- [ ] Shows: Status, User Count, Active Subscriptions, Monthly Revenue, Traffic Sold - **ENHANCE WITH ALL METRICS**
- [ ] Shows current settings summary (Language, Support, Feature Flags) - **USE BotConfigService**
- [ ] Provides navigation to all sub-menus:
  - [ ] Statistics - **IMPLEMENT**
  - [x] General Settings - ✅ **EXISTS** (needs BotConfigService integration)
  - [ ] Feature Flags - **IMPLEMENT**
  - [x] Payment Methods - ✅ **PARTIAL** (only card-to-card, needs others)
  - [ ] Subscription Plans - **IMPLEMENT**
  - [ ] Configuration - **IMPLEMENT**
  - [ ] Analytics - **IMPLEMENT**
  - [x] Test Bot - ✅ **EXISTS** (`test_bot_status`)
  - [ ] Delete Bot - **IMPLEMENT**
- [ ] Callback: `admin_tenant_bot_detail:{bot_id}`
- [ ] **REPLACE DIRECT COLUMN ACCESS** - Use `BotConfigService` instead of `bot.card_to_card_enabled`, etc.

**Database Queries:**
```sql
-- Bot info
SELECT * FROM bots WHERE id = {bot_id};

-- User count
SELECT COUNT(*) FROM users WHERE bot_id = {bot_id};

-- Active subscriptions
SELECT COUNT(*) FROM subscriptions 
WHERE bot_id = {bot_id} AND status = 'active';

-- Monthly revenue
SELECT COALESCE(SUM(amount_toman), 0) 
FROM transactions 
WHERE bot_id = {bot_id} 
  AND type = 'deposit' 
  AND is_completed = TRUE
  AND created_at >= date_trunc('month', CURRENT_DATE);

-- Traffic sold
SELECT traffic_sold_bytes FROM bots WHERE id = {bot_id};
```

### AC4: Statistics View
- [ ] Displays comprehensive statistics for selected bot
- [ ] Shows: Overview (30 days), Revenue Breakdown, User Growth
- [ ] Revenue breakdown by payment method
- [ ] User growth metrics (Today, This Week, This Month)
- [ ] Navigation to: Detailed Stats, Revenue Chart, Users List, Subscriptions
- [ ] Callback: `admin_tenant_bot_stats:{bot_id}`
- [ ] Handler: `app/handlers/admin/tenant_bots.py::show_bot_statistics`

**Database Queries:**
```sql
-- New users (30 days)
SELECT COUNT(*) FROM users 
WHERE bot_id = {bot_id} 
  AND created_at >= CURRENT_DATE - INTERVAL '30 days';

-- Active users
SELECT COUNT(DISTINCT user_id) FROM subscriptions
WHERE bot_id = {bot_id} AND status = 'active';

-- Revenue by payment method
SELECT payment_method, SUM(amount_toman) as total
FROM transactions
WHERE bot_id = {bot_id} 
  AND type = 'deposit'
  AND is_completed = TRUE
  AND created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY payment_method;
```

### AC5: General Settings Management
- [x] Handler exists: `app/handlers/admin/tenant_bots.py::show_bot_settings` ✅ **PARTIALLY IMPLEMENTED**
- [ ] Displays current general settings (Name, Bot Token, Language, Support, Notifications)
- [ ] Provides edit functionality for each setting
- [ ] Edit actions trigger FSM states for input
- [ ] Settings saved to appropriate tables (`bots` or `bot_configurations`) - **USE BotConfigService**
- [ ] Callback: `admin_tenant_bot_settings:{bot_id}`
- [ ] Edit Callbacks: `admin_tenant_bot_edit_name:{bot_id}`, `admin_tenant_bot_edit_language:{bot_id}`, etc.
- [ ] **REQUIRES BotConfigService** - Use `BotConfigService.get_config()` and `BotConfigService.set_config()`

**FSM States Required:**
- `AdminStates.editing_tenant_bot_name` - **ADD TO states.py** (or use existing if different name)
- `AdminStates.editing_tenant_bot_language` - **ADD TO states.py**
- `AdminStates.editing_tenant_bot_support` - **ADD TO states.py**
- `AdminStates.editing_tenant_bot_notifications` - **ADD TO states.py`

**Note:** Current implementation uses `waiting_for_bot_name`, `waiting_for_bot_token` for creation. Add separate states for editing or align naming.

### AC6: Feature Flags Management
- [ ] **REQUIRES BotConfigService** - Must use `BotConfigService.is_feature_enabled()` and `BotConfigService.set_feature_enabled()`
- [ ] Displays all feature flags organized by category:
  - Payment Gateways
  - Subscription Features
  - Marketing Features
  - Support Features
  - Integrations
- [ ] Shows current enabled/disabled status for each feature
- [ ] Shows plan restrictions (if feature requires Growth/Enterprise plan)
- [ ] Toggle functionality for each feature
- [ ] Override capability for master admin (bypass plan restrictions)
- [ ] Callback: `admin_tenant_bot_features:{bot_id}`
- [ ] Toggle Callback: `admin_tenant_bot_toggle_feature:{bot_id}:{feature_key}`
- [ ] Handler: `app/handlers/admin/tenant_bots.py::show_bot_feature_flags` - **CREATE NEW HANDLER**

**Database Queries:**
```sql
-- Get feature flags
SELECT * FROM bot_feature_flags 
WHERE bot_id = {bot_id};

-- Get plan features
SELECT pf.* FROM plan_feature_grants pf
JOIN tenant_subscriptions ts ON ts.plan_tier_id = pf.plan_tier_id
WHERE ts.bot_id = {bot_id} AND ts.status = 'active';
```

**⚠️ Schema Verification Required:**
- Verify `plan_feature_grants` table exists
- Verify `tenant_subscriptions` table exists
- If tables don't exist, implement without plan restrictions or add migration task

**Toggle Implementation:**
```sql
INSERT INTO bot_feature_flags (bot_id, feature_key, enabled, updated_at)
VALUES ({bot_id}, '{feature_key}', {new_value}, NOW())
ON CONFLICT (bot_id, feature_key) 
DO UPDATE SET enabled = {new_value}, updated_at = NOW();
```

### AC7: Payment Methods Management
- [x] Handler exists: `app/handlers/admin/tenant_bots.py::show_bot_payment_cards` ✅ **PARTIALLY IMPLEMENTED** (card-to-card only)
- [ ] Displays all payment methods with current status
- [ ] Shows configuration for each method (if applicable)
- [x] Card-to-Card: Shows active cards count, receipt topic ID ✅
- [ ] Zarinpal: Shows merchant ID, sandbox status - **IMPLEMENT**
- [ ] Other gateways: Shows enabled status and basic config - **IMPLEMENT**
- [ ] Toggle functionality for each payment method - **USE BotConfigService**
- [ ] Navigation to detailed configuration for each method
- [ ] Callback: `admin_tenant_bot_payments:{bot_id}` - **CREATE MAIN MENU HANDLER**
- [ ] Handler: `app/handlers/admin/tenant_bots.py::show_bot_payment_methods` - **CREATE NEW HANDLER**

**Sub-menus:**
- Card-to-Card: `admin_tenant_bot_cards:{bot_id}`
- Zarinpal: `admin_tenant_bot_zarinpal:{bot_id}`
- YooKassa: `admin_tenant_bot_yookassa:{bot_id}`
- Other gateways: Similar pattern

### AC8: Subscription Plans Management
- [ ] Displays list of all subscription plans for the bot
- [ ] Shows plan details: Period, Price, Traffic, Devices, Status
- [ ] Provides: Create Plan, Edit Plan, Delete Plan actions
- [ ] Create Plan triggers FSM flow for plan creation
- [ ] Callback: `admin_tenant_bot_plans:{bot_id}`
- [ ] Handler: `app/handlers/admin/tenant_bots.py::show_bot_plans`

**Database Query:**
```sql
SELECT * FROM bot_plans 
WHERE bot_id = {bot_id}
ORDER BY sort_order, price_toman;
```

### AC9: Configuration Management (Categorized)
- [ ] **REQUIRES BotConfigService** - Must use `BotConfigService.get_config()` and `BotConfigService.set_config()`
- [ ] **⚠️ LARGE SCOPE** - 8 categories with 450+ config keys. Consider breaking into separate stories or implementing MVP for less-used categories first.
- [ ] Displays configuration menu with categories:
  - Basic Settings
  - Support Settings
  - Notifications
  - Subscription Settings
  - Pricing Settings
  - UI/UX Settings
  - Integrations
  - Advanced Settings
- [ ] Each category navigates to detailed configuration view
- [ ] Edit functionality for each config value
- [ ] Configs saved to `bot_configurations` table via BotConfigService
- [ ] Callback: `admin_tenant_bot_config:{bot_id}`
- [ ] Category Callbacks: `admin_tenant_bot_config_basic:{bot_id}`, etc.
- [ ] Handler: `app/handlers/admin/tenant_bots.py::show_bot_configuration_menu` - **CREATE NEW HANDLER**

**Configuration Categories Implementation:**

#### 9.1. Basic Settings
- Default Language
- Available Languages
- Language Selection Enabled
- Timezone
- Skip Rules Accept
- Skip Referral Code

#### 9.2. Support Settings
- Support Username
- Support Menu Enabled
- Support Mode (tickets/contact/both)
- Ticket SLA settings

#### 9.3. Notifications
- Admin Notifications (enabled, chat_id, topic_id)
- Reports (enabled, chat_id, topic_id, send_time)
- User Notifications (enabled, trial warning, retry attempts)

#### 9.4. Subscription Settings
- Trial settings (duration, traffic, devices, payment)
- Default settings (device limit, traffic, reset strategy)
- Available periods

#### 9.5. Pricing Settings
- Period prices (14, 30, 60, 90, 180, 360 days)
- Traffic packages
- Device pricing

#### 9.6. UI/UX Settings
- Logo mode and file
- Main menu mode
- Connect button settings
- MiniApp configuration

#### 9.7. Integrations
- Server Status settings
- Monitoring settings
- Maintenance settings

#### 9.8. Advanced Settings
- Auto-Renewal settings
- Referral program settings
- Promo Groups settings
- Contests settings

### AC10: Analytics View
- [ ] Displays performance metrics (30 days)
- [ ] Shows: User Growth, Revenue Growth, Conversion Rate, ARPU
- [ ] Shows trends (Growing/Declining/Stable)
- [ ] Provides insights (Peak hours, Popular plans, Top payment methods)
- [ ] Navigation to: Detailed Analytics, Charts, Export Report
- [ ] Callback: `admin_tenant_bot_analytics:{bot_id}`
- [ ] Handler: `app/handlers/admin/tenant_bots.py::show_bot_analytics`

### AC11: Create Bot Flow
- [x] Handler exists: `app/handlers/admin/tenant_bots.py::start_create_bot` ✅ **IMPLEMENTED**
- [x] Initiates bot creation FSM flow ✅
- [x] Collects: Bot Name, Telegram Bot Token, Language, Support Username ✅
- [ ] Processes activation fee payment - **VERIFY IMPLEMENTATION**
- [x] Creates bot record in database ✅
- [x] Generates API token ✅
- [x] Sends confirmation with API token ✅
- [ ] Callback: `admin_tenant_bots_create`
- [ ] **USE BotConfigService** - Set initial configurations using BotConfigService instead of direct column writes

**FSM States:**
- `AdminStates.waiting_for_bot_name` - ✅ **EXISTS** (current implementation)
- `AdminStates.waiting_for_bot_token` - ✅ **EXISTS** (current implementation)
- `AdminStates.creating_tenant_bot_language` - **ALIGN** (current uses different pattern)
- `AdminStates.creating_tenant_bot_support` - **ALIGN** (current uses different pattern)
- `AdminStates.creating_tenant_bot_plan` - **VERIFY IF NEEDED**
- `AdminStates.creating_tenant_bot_payment` - **VERIFY IF NEEDED**

**Note:** Current implementation uses `waiting_for_bot_name` and `waiting_for_bot_token`. Either align story to match current implementation or update implementation to match story.

### AC12: Delete Bot Functionality
- [ ] Provides delete confirmation dialog
- [ ] Warns about data loss (users, subscriptions, transactions)
- [ ] Requires confirmation before deletion
- [ ] Soft delete option (set `is_active = FALSE`) or hard delete
- [ ] Callback: `admin_tenant_bot_delete:{bot_id}`
- [ ] Handler: `app/handlers/admin/tenant_bots.py::delete_bot`

### AC13: Test Bot Functionality
- [ ] Checks bot status (active/inactive)
- [ ] Verifies bot token validity
- [ ] Tests bot connectivity
- [ ] Displays bot information
- [ ] Callback: `admin_tenant_bot_test:{bot_id}`
- [ ] Handler: `app/handlers/admin/tenant_bots.py::test_bot`

---

## 🔧 Technical Implementation Details

### File Structure

```
app/handlers/admin/
├── tenant_bots.py              # Main handler file
├── tenant_bots/
│   ├── __init__.py
│   ├── menu.py                  # Menu display functions
│   ├── statistics.py             # Statistics handlers
│   ├── settings.py              # Settings management
│   ├── feature_flags.py         # Feature flags management
│   ├── payments.py              # Payment methods management
│   ├── plans.py                 # Subscription plans management
│   ├── configuration.py         # Configuration management
│   ├── analytics.py             # Analytics handlers
│   └── create_bot.py            # Bot creation flow
```

### Key Components

#### 1. Menu Display Functions
```python
# app/handlers/admin/tenant_bots/menu.py

async def show_tenant_bots_menu(
    callback: types.CallbackQuery,
    db: AsyncSession
) -> None:
    """Display main tenant bots menu with statistics"""
    # Query database for statistics
    # Build inline keyboard
    # Send message
    pass

async def list_tenant_bots(
    callback: types.CallbackQuery,
    db: AsyncSession,
    page: int = 0
) -> None:
    """Display paginated list of tenant bots"""
    # Query bots with pagination
    # Build inline keyboard with bot buttons
    # Send message
    pass

async def show_bot_detail(
    callback: types.CallbackQuery,
    db: AsyncSession,
    bot_id: int
) -> None:
    """Display bot detail menu"""
    # Query bot info and statistics
    # Build inline keyboard with sub-menu options
    # Send message
    pass
```

#### 2. Statistics Handlers
```python
# app/handlers/admin/tenant_bots/statistics.py

async def show_bot_statistics(
    callback: types.CallbackQuery,
    db: AsyncSession,
    bot_id: int
) -> None:
    """Display comprehensive bot statistics"""
    # Query user statistics
    # Query revenue statistics
    # Query subscription statistics
    # Format and display
    pass
```

#### 3. Feature Flags Management
```python
# app/handlers/admin/tenant_bots/feature_flags.py

async def show_bot_feature_flags(
    callback: types.CallbackQuery,
    db: AsyncSession,
    bot_id: int
) -> None:
    """Display feature flags with plan restrictions"""
    # Query feature flags from bot_feature_flags
    # Query plan features from plan_feature_grants
    # Organize by category
    # Display with toggle buttons
    pass

async def toggle_feature_flag(
    callback: types.CallbackQuery,
    db: AsyncSession,
    bot_id: int,
    feature_key: str
) -> None:
    """Toggle feature flag on/off"""
    # Check current state
    # Toggle state
    # Update bot_feature_flags table
    # Commit transaction
    # Show confirmation
    pass
```

#### 4. Configuration Management
```python
# app/handlers/admin/tenant_bots/configuration.py

async def show_bot_configuration_menu(
    callback: types.CallbackQuery,
    db: AsyncSession,
    bot_id: int
) -> None:
    """Display configuration category menu"""
    # Build keyboard with category buttons
    # Send message
    pass

async def show_basic_settings(
    callback: types.CallbackQuery,
    db: AsyncSession,
    bot_id: int
) -> None:
    """Display basic settings configuration"""
    # Query configs from bot_configurations
    # Display current values
    # Provide edit buttons
    pass

async def edit_config_value(
    message: types.Message,
    state: FSMContext,
    db: AsyncSession,
    bot_id: int,
    config_key: str
) -> None:
    """Edit configuration value via FSM"""
    # Set FSM state
    # Request new value
    # Validate input
    # Update bot_configurations
    # Commit transaction
    # Show confirmation
    pass
```

### Database Operations

#### Using BotConfigService
**⚠️ REQUIRED:** BotConfigService must be implemented (STORY-001) before using these patterns.

```python
from app.services.bot_config_service import BotConfigService

# Get config
default_lang = await BotConfigService.get_config(
    db, bot_id, 'DEFAULT_LANGUAGE', default='fa'
)

# Set config
await BotConfigService.set_config(
    db, bot_id, 'DEFAULT_LANGUAGE', 'en'
)

# Check feature flag
is_enabled = await BotConfigService.is_feature_enabled(
    db, bot_id, 'card_to_card'
)

# Set feature flag
await BotConfigService.set_feature_enabled(
    db, bot_id, 'card_to_card', True
)
```

**⚠️ DO NOT USE:** Direct column access like `bot.card_to_card_enabled` or `bot.default_language`. Always use BotConfigService.

### FSM States

Add to `app/states.py`:
```python
class AdminStates(StatesGroup):
    # ... existing states ...
    
    # Tenant bot creation
    creating_tenant_bot_name = State()
    creating_tenant_bot_token = State()
    creating_tenant_bot_language = State()
    creating_tenant_bot_support = State()
    creating_tenant_bot_plan = State()
    creating_tenant_bot_payment = State()
    
    # Tenant bot editing
    editing_tenant_bot_name = State()
    editing_tenant_bot_language = State()
    editing_tenant_bot_support = State()
    editing_tenant_bot_notifications = State()
    
    # Configuration editing
    editing_config_value = State()
    editing_config_key = State()
```

### Keyboard Builders

```python
# app/keyboards/admin.py

def get_tenant_bots_menu_keyboard() -> InlineKeyboardMarkup:
    """Build main tenant bots menu keyboard"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📋 List Bots", callback_data="admin_tenant_bots_list")
    keyboard.button(text="➕ Create Bot", callback_data="admin_tenant_bots_create")
    keyboard.button(text="📊 Statistics", callback_data="admin_tenant_bots_stats")
    keyboard.button(text="⚙️ Settings", callback_data="admin_tenant_bots_settings")
    keyboard.button(text="🔙 Back", callback_data="admin_main_menu")
    return keyboard.as_markup()

def get_bot_detail_keyboard(bot_id: int) -> InlineKeyboardMarkup:
    """Build bot detail menu keyboard"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📊 Statistics", callback_data=f"admin_tenant_bot_stats:{bot_id}")
    keyboard.button(text="⚙️ General Settings", callback_data=f"admin_tenant_bot_settings:{bot_id}")
    keyboard.button(text="🎛️ Feature Flags", callback_data=f"admin_tenant_bot_features:{bot_id}")
    keyboard.button(text="💳 Payment Methods", callback_data=f"admin_tenant_bot_payments:{bot_id}")
    keyboard.button(text="📦 Subscription Plans", callback_data=f"admin_tenant_bot_plans:{bot_id}")
    keyboard.button(text="🔧 Configuration", callback_data=f"admin_tenant_bot_config:{bot_id}")
    keyboard.button(text="📈 Analytics", callback_data=f"admin_tenant_bot_analytics:{bot_id}")
    keyboard.button(text="🧪 Test Bot", callback_data=f"admin_tenant_bot_test:{bot_id}")
    keyboard.button(text="🗑️ Delete Bot", callback_data=f"admin_tenant_bot_delete:{bot_id}")
    keyboard.button(text="🔙 Back", callback_data="admin_tenant_bots_menu")
    return keyboard.as_markup()
```

### Permission Checks

**⚠️ VERIFY IMPLEMENTATION:** Check if `is_master_admin` function exists before using.

```python
# app/utils/permissions.py

async def is_master_admin(
    user: User,
    db: AsyncSession
) -> bool:
    """Check if user is master admin"""
    from app.database.crud.bot import get_master_bot
    from app.services.bot_config_service import BotConfigService
    
    master_bot = await get_master_bot(db)
    if not master_bot:
        return False
    
    admin_ids_str = await BotConfigService.get_config(
        db, master_bot.id, 'ADMIN_IDS', default=''
    )
    admin_ids = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
    
    return user.telegram_id in admin_ids

def admin_required(func):
    """Decorator to require master admin access"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract user and db from args/kwargs
        # Check is_master_admin
        # If not, send error message
        # If yes, call original function
        pass
    return wrapper
```

**Note:** Current implementation uses `@admin_required` decorator. Verify if this is sufficient or if `admin_required` needs to be implemented.

---

## 📁 Files to Create/Modify

### New Files:
- `app/handlers/admin/tenant_bots.py` - Main handler file
- `app/handlers/admin/tenant_bots/__init__.py`
- `app/handlers/admin/tenant_bots/menu.py` - Menu display functions
- `app/handlers/admin/tenant_bots/statistics.py` - Statistics handlers
- `app/handlers/admin/tenant_bots/settings.py` - Settings management
- `app/handlers/admin/tenant_bots/feature_flags.py` - Feature flags management
- `app/handlers/admin/tenant_bots/payments.py` - Payment methods management
- `app/handlers/admin/tenant_bots/plans.py` - Subscription plans management
- `app/handlers/admin/tenant_bots/configuration.py` - Configuration management
- `app/handlers/admin/tenant_bots/analytics.py` - Analytics handlers
- `app/handlers/admin/tenant_bots/create_bot.py` - Bot creation flow
- `tests/handlers/admin/test_tenant_bots.py` - Unit tests

### Files to Modify:
- `app/states.py` - Add FSM states for tenant bot management
- `app/keyboards/admin.py` - Add keyboard builders for tenant bots menus
- `app/utils/permissions.py` - Add master admin permission checks
- `app/handlers/admin/__init__.py` - Register new handlers
- `app/bot.py` - Register handlers in dispatcher

---

## 🧪 Testing Strategy

### Unit Tests:
```python
# tests/handlers/admin/test_tenant_bots.py

async def test_show_tenant_bots_menu_displays_statistics()
async def test_list_tenant_bots_with_pagination()
async def test_show_bot_detail_displays_correct_info()
async def test_toggle_feature_flag_updates_database()
async def test_edit_config_saves_to_database()
async def test_create_bot_flow_completes_successfully()
```

### Integration Tests:
```python
# tests/integration/test_tenant_bots_admin.py

async def test_master_admin_can_access_tenant_bots()
async def test_non_master_admin_cannot_access()
async def test_bot_creation_creates_all_required_records()
async def test_feature_flag_toggle_affects_bot_behavior()
async def test_configuration_changes_reflect_in_bot()
```

### Manual Testing Checklist:
- [ ] Navigate through all menu levels
- [ ] Test pagination in bot list
- [ ] Create a new tenant bot
- [ ] Edit bot settings
- [ ] Toggle feature flags
- [ ] Configure payment methods
- [ ] Manage subscription plans
- [ ] Edit configurations in each category
- [ ] View statistics and analytics
- [ ] Test bot deletion (with confirmation)
- [ ] Verify permission checks (master admin only)

---

## ⚠️ Risks & Mitigation

### Risk 1: Performance with Many Tenant Bots
**Mitigation:**
- Implement pagination for bot lists
- Use database indexes on `bot_id` columns
- Cache statistics for frequently accessed bots
- Limit query result sets

### Risk 2: Complex Configuration Management
**Mitigation:**
- Break configuration into logical categories
- Use FSM for multi-step edits
- Validate all inputs before saving
- Provide clear error messages

### Risk 3: Permission Security
**Mitigation:**
- Strict permission checks on all handlers
- Verify master admin status for every action
- Log all admin actions for audit trail
- Test permission boundaries thoroughly

### Risk 4: Data Consistency
**Mitigation:**
- Use transactions for multi-step operations
- Validate data before saving
- Use `BotConfigService` for all config access
- Test edge cases (missing data, null values)

---

## 📚 References

### Documentation:
- `docs/tenant-bots-admin-ux-design.md` - Complete UX design specification
- `docs/MASTER-IMPLEMENTATION-GUIDE.md` - Master implementation guide
- `docs/analysis/comprehensive-code-review.md` - Code review findings

### Related Stories:
- STORY-001: Eliminate Schema Redundancy and Implement BotConfigService (prerequisite)
- Future: Add caching to statistics queries
- Future: Implement export functionality for analytics

---

## 📝 Definition of Done

- [ ] All menu levels implemented and functional
- [ ] All database queries tested and optimized
- [ ] Feature flags management working with plan restrictions
- [ ] Configuration management working for all categories
- [ ] Bot creation flow complete with payment processing
- [ ] Statistics and analytics displaying correctly
- [ ] Permission checks implemented and tested
- [ ] All handlers registered in dispatcher
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] Manual testing completed
- [ ] Code reviewed and approved
- [ ] Documentation updated

---

## 🎯 Success Metrics

- **Navigation Completeness** - All menu levels accessible and functional
- **Performance** - Menu responses < 2 seconds
- **Data Accuracy** - Statistics match actual database values
- **User Experience** - Intuitive navigation, clear error messages
- **Security** - Only master admins can access (100% permission checks)

---

## 📅 Implementation Phases

### Phase 1: Core Menu Structure (Week 1)
- Main menu
- List bots with pagination
- Bot detail menu
- Basic navigation

### Phase 2: Statistics & Settings (Week 2)
- Statistics views
- General settings management
- Edit functionality with FSM

### Phase 3: Feature Flags & Payments (Week 3)
- Feature flags management
- Payment methods management
- Toggle functionality

### Phase 4: Configuration & Plans (Week 4)
- Configuration categories
- Subscription plans management
- Edit forms for all configs

### Phase 5: Advanced Features (Week 5)
- Analytics view
- Bot creation flow
- Bot deletion
- Test bot functionality

---

---

## 📊 Current Implementation Status

**Partially Implemented (Need Enhancement):**
- ✅ AC1: Main menu (exists, needs statistics query update)
- ✅ AC2: List bots (exists, needs plan column and query update)
- ✅ AC3: Bot detail (exists, needs sub-menu completion)
- ✅ AC5: General settings (exists, needs BotConfigService integration)
- ✅ AC7: Payment methods (card-to-card exists, needs others)
- ✅ AC11: Create bot (exists, needs BotConfigService integration)
- ✅ AC13: Test bot (exists)

**Not Implemented (Need Creation):**
- ❌ AC4: Statistics view
- ❌ AC6: Feature flags management
- ❌ AC8: Subscription plans management
- ❌ AC9: Configuration management (8 categories)
- ❌ AC10: Analytics view
- ❌ AC12: Delete bot functionality

---

## 🔍 Pre-Development Checklist

Before starting development, verify:

- [ ] **STORY-001 is complete** - BotConfigService exists and is tested
- [ ] **Database schema verified:**
  - [ ] `tenant_subscriptions` table exists
  - [ ] `tenant_subscription_plans` table exists
  - [ ] `plan_feature_grants` table exists
  - [ ] If tables don't exist, add migration tasks or update queries
- [ ] **FSM states aligned** - Decide on naming convention (story vs current implementation)
- [ ] **Permission checks verified** - `is_master_admin` function exists or needs implementation
- [ ] **BotConfigService API reviewed** - Verify method signatures match story usage

---

**Story Owner:** Development Team  
**Reviewers:** Architecture Team, UX Team, QA Team  
**Dependencies:** 
- 🔴 **CRITICAL:** STORY-001 (BotConfigService must be implemented and tested first)
- ⚠️ **HIGH:** Database schema verification (tenant_subscriptions, tenant_subscription_plans, plan_feature_grants)
- ⚠️ **MEDIUM:** Permission system verification (admin_required)

**Blocks:** Future stories requiring admin panel access

**Estimated Effort:** 50-70 hours (updated from 40-60 hours based on validation - AC9 scope is large)

