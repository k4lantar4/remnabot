# Story: Implement Complete Tenant Bots Admin Panel

**Story ID:** STORY-003  
**Epic:** Multi-Tenant Architecture - Admin Panel  
**Priority:** ⚠️ HIGH  
**Status:** Draft  
**Created:** 2025-12-15  
**Estimated Effort:** 60-80 hours

---

## 📋 Story Summary

Implement a complete admin panel for managing tenant bots, including menu navigation, statistics, feature flags management, payment methods configuration, subscription plans management, and categorized configuration settings. This story builds upon STORY-001 (BotConfigService) and implements the UX design from `tenant-bots-admin-ux-design.md`.

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

### AC1: Main Menu Integration
- [ ] Add "🤖 Tenant Bots" button to main admin panel menu
- [ ] Main tenant bots menu displays overview statistics
- [ ] Shows: Total bots, Active/Inactive count, Total users, Total revenue
- [ ] Navigation to: List Bots, Create Bot, Statistics, Settings
- [ ] Callback: `admin_tenant_bots_menu`
- [ ] Handler: `app/handlers/admin/tenant_bots.py::show_tenant_bots_menu`
- [ ] Menu follows existing admin panel design patterns

**Integration Point:**
- Modify `app/handlers/admin/main.py` to add tenant bots menu item
- Add callback handler registration

### AC2: List Bots with Pagination
- [ ] Displays paginated list of tenant bots (5 per page)
- [ ] Each bot card shows: Name, ID, Status (Active/Inactive), User Count, Revenue, Plan
- [ ] Clicking a bot navigates to bot detail menu
- [ ] Pagination controls (Previous/Next) work correctly
- [ ] Callback: `admin_tenant_bots_list` or `admin_tenant_bots_list:{page}`
- [ ] Handler: `app/handlers/admin/tenant_bots.py::list_tenant_bots`

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

### AC3: Bot Detail Menu
- [ ] Displays bot overview with quick stats
- [ ] Shows: Status, User Count, Active Subscriptions, Monthly Revenue, Traffic Sold
- [ ] Shows current settings summary (Language, Support, Feature Flags)
- [ ] Provides navigation to all sub-menus:
  - Statistics
  - General Settings
  - Feature Flags
  - Payment Methods
  - Subscription Plans
  - Configuration
  - Analytics
  - Test Bot
  - Delete Bot
- [ ] Callback: `admin_tenant_bot_detail:{bot_id}`
- [ ] Handler: `app/handlers/admin/tenant_bots.py::show_bot_detail`

### AC4: Statistics View
- [ ] Displays comprehensive statistics for selected bot
- [ ] Shows: Overview (30 days), Revenue Breakdown, User Growth
- [ ] Revenue breakdown by payment method
- [ ] User growth metrics (Today, This Week, This Month)
- [ ] Navigation to: Detailed Stats, Revenue Chart, Users List, Subscriptions
- [ ] Callback: `admin_tenant_bot_stats:{bot_id}`
- [ ] Handler: `app/handlers/admin/tenant_bots.py::show_bot_statistics`

### AC5: General Settings Management
- [ ] Displays current general settings (Name, Bot Token, Language, Support, Notifications)
- [ ] Provides edit functionality for each setting
- [ ] Edit actions trigger FSM states for input
- [ ] Settings saved using `BotConfigService` (from STORY-001)
- [ ] Callback: `admin_tenant_bot_settings:{bot_id}`
- [ ] Edit Callbacks: `admin_tenant_bot_edit_name:{bot_id}`, etc.

**FSM States Required:**
- `AdminStates.editing_tenant_bot_name`
- `AdminStates.editing_tenant_bot_language`
- `AdminStates.editing_tenant_bot_support`
- `AdminStates.editing_tenant_bot_notifications`

### AC6: Feature Flags Management
- [ ] Displays all feature flags organized by category:
  - Payment Gateways (yookassa, cryptobot, pal24, etc.)
  - Subscription Features (trial, auto_renewal, simple_purchase)
  - Marketing Features (referral_program, polls)
  - Support Features (support_tickets)
  - Integrations (server_status, monitoring)
- [ ] Shows current enabled/disabled status for each feature
- [ ] Shows plan restrictions (if feature requires Growth/Enterprise plan)
- [ ] Toggle functionality for each feature
- [ ] Override capability for master admin (bypass plan restrictions)
- [ ] Uses `BotConfigService.is_feature_enabled()` and `set_feature_enabled()`
- [ ] Callback: `admin_tenant_bot_features:{bot_id}`
- [ ] Toggle Callback: `admin_tenant_bot_toggle_feature:{bot_id}:{feature_key}`

### AC7: Payment Methods Management
- [ ] Displays all payment methods with current status
- [ ] Shows configuration for each method (if applicable)
- [ ] Card-to-Card: Shows active cards count, receipt topic ID
- [ ] Zarinpal: Shows merchant ID, sandbox status
- [ ] Other gateways: Shows enabled status and basic config
- [ ] Toggle functionality for each payment method
- [ ] Navigation to detailed configuration for each method
- [ ] Uses `BotConfigService` for feature flags
- [ ] Callback: `admin_tenant_bot_payments:{bot_id}`

### AC8: Subscription Plans Management
- [ ] Displays list of all subscription plans for the bot
- [ ] Shows plan details: Period, Price, Traffic, Devices, Status
- [ ] Provides: Create Plan, Edit Plan, Delete Plan actions
- [ ] Create Plan triggers FSM flow for plan creation
- [ ] Callback: `admin_tenant_bot_plans:{bot_id}`
- [ ] Handler: `app/handlers/admin/tenant_bots.py::show_bot_plans`

### AC9: Configuration Management (Categorized)
- [ ] Displays configuration menu with 8 categories:
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
- [ ] Configs saved using `BotConfigService.set_config()`
- [ ] All configs read using `BotConfigService.get_config()`
- [ ] Callback: `admin_tenant_bot_config:{bot_id}`
- [ ] Category Callbacks: `admin_tenant_bot_config_basic:{bot_id}`, etc.

**Configuration Categories:**
- Basic: DEFAULT_LANGUAGE, AVAILABLE_LANGUAGES, TZ, etc.
- Support: SUPPORT_USERNAME, SUPPORT_MENU_ENABLED, etc.
- Notifications: ADMIN_NOTIFICATIONS_*, ADMIN_REPORTS_*, etc.
- Subscription: TRIAL_*, DEFAULT_DEVICE_LIMIT, etc.
- Pricing: PRICE_*, TRAFFIC_PACKAGES_CONFIG, etc.
- UI/UX: ENABLE_LOGO_MODE, MAIN_MENU_MODE, MINIAPP_*, etc.
- Integrations: SERVER_STATUS_*, MONITORING_*, MAINTENANCE_*, etc.
- Advanced: AUTOPAY_*, REFERRAL_*, PROMO_*, CONTEST_*, etc.

### AC10: Analytics View
- [ ] Displays performance metrics (30 days)
- [ ] Shows: User Growth, Revenue Growth, Conversion Rate, ARPU
- [ ] Shows trends (Growing/Declining/Stable)
- [ ] Provides insights (Peak hours, Popular plans, Top payment methods)
- [ ] Navigation to: Detailed Analytics, Charts, Export Report
- [ ] Callback: `admin_tenant_bot_analytics:{bot_id}`

### AC11: Create Bot Flow
- [ ] Initiates bot creation FSM flow
- [ ] Collects: Bot Name, Telegram Bot Token, Language, Support Username, Subscription Plan
- [ ] Validates bot token with Telegram API
- [ ] Creates bot record in database
- [ ] Generates API token
- [ ] Clones configs from master bot (using `BotConfigService`)
- [ ] Sends confirmation with API token
- [ ] Callback: `admin_tenant_bots_create`
- [ ] Handler: `app/handlers/admin/tenant_bots.py::start_create_bot`

**FSM States:**
- `AdminStates.creating_tenant_bot_name`
- `AdminStates.creating_tenant_bot_token`
- `AdminStates.creating_tenant_bot_language`
- `AdminStates.creating_tenant_bot_support`
- `AdminStates.creating_tenant_bot_plan`

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

### AC14: Permission Checks
- [ ] All handlers check for master admin permission
- [ ] Only master admins can access tenant bots menu
- [ ] Permission check implemented using `is_master_admin()` utility
- [ ] Error messages for unauthorized access
- [ ] All handlers decorated with `@master_admin_required`

---

## 🔧 Technical Implementation Details

### File Structure

```
app/handlers/admin/
├── tenant_bots.py              # Main handler file (already exists, needs expansion)
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

### Key Implementation Points

#### 1. Integration with Existing Admin Panel

**Modify:** `app/handlers/admin/main.py`

```python
# Add to show_admin_panel function
keyboard.add(InlineKeyboardButton(
    text="🤖 Tenant Bots",
    callback_data="admin_tenant_bots_menu"
))
```

#### 2. Using BotConfigService

All handlers must use `BotConfigService` from STORY-001:

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

#### 3. Permission Checks

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

def master_admin_required(func):
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

#### 4. FSM States

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
    
    # Tenant bot editing
    editing_tenant_bot_name = State()
    editing_tenant_bot_language = State()
    editing_tenant_bot_support = State()
    editing_tenant_bot_notifications = State()
    
    # Configuration editing
    editing_tenant_config = State()
    editing_tenant_config_key = State()
    editing_tenant_config_value = State()
    
    # Payment card management
    adding_tenant_payment_card = State()
    editing_tenant_payment_card = State()
    
    # Plan management
    creating_tenant_plan = State()
    editing_tenant_plan = State()
```

#### 5. Handler Registration

The file `app/handlers/admin/tenant_bots.py` already exists and has a `register_handlers()` function. We need to expand it:

```python
def register_handlers(dp: Dispatcher) -> None:
    """Register all tenant bots handlers"""
    
    # Main menu
    dp.callback_query.register(
        show_tenant_bots_menu,
        F.data == "admin_tenant_bots_menu"
    )
    
    # List bots
    dp.callback_query.register(
        list_tenant_bots,
        F.data.startswith("admin_tenant_bots_list")
    )
    
    # Bot detail
    dp.callback_query.register(
        show_bot_detail,
        F.data.startswith("admin_tenant_bot_detail:")
    )
    
    # Statistics
    dp.callback_query.register(
        show_bot_statistics,
        F.data.startswith("admin_tenant_bot_stats:")
    )
    
    # Settings
    dp.callback_query.register(
        show_bot_settings,
        F.data.startswith("admin_tenant_bot_settings:")
    )
    
    # Feature flags
    dp.callback_query.register(
        show_bot_feature_flags,
        F.data.startswith("admin_tenant_bot_features:")
    )
    
    dp.callback_query.register(
        toggle_feature_flag,
        F.data.startswith("admin_tenant_bot_toggle_feature:")
    )
    
    # Payment methods
    dp.callback_query.register(
        show_bot_payment_methods,
        F.data.startswith("admin_tenant_bot_payments:")
    )
    
    # Plans
    dp.callback_query.register(
        show_bot_plans,
        F.data.startswith("admin_tenant_bot_plans:")
    )
    
    # Configuration
    dp.callback_query.register(
        show_bot_configuration_menu,
        F.data.startswith("admin_tenant_bot_config:")
    )
    
    # Analytics
    dp.callback_query.register(
        show_bot_analytics,
        F.data.startswith("admin_tenant_bot_analytics:")
    )
    
    # Create bot
    dp.callback_query.register(
        start_create_bot,
        F.data == "admin_tenant_bots_create"
    )
    
    # Delete bot
    dp.callback_query.register(
        start_delete_bot,
        F.data.startswith("admin_tenant_bot_delete:")
    )
    
    # Test bot
    dp.callback_query.register(
        test_bot,
        F.data.startswith("admin_tenant_bot_test:")
    )
    
    # FSM handlers
    dp.message.register(
        process_bot_name,
        StateFilter(AdminStates.creating_tenant_bot_name)
    )
    
    dp.message.register(
        process_bot_token,
        StateFilter(AdminStates.creating_tenant_bot_token)
    )
    
    # ... more FSM handlers
```

---

## 📁 Files to Create/Modify

### New Files:
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
- `app/handlers/admin/tenant_bots.py` - Expand existing file with new handlers
- `app/handlers/admin/main.py` - Add tenant bots menu item
- `app/states.py` - Add FSM states
- `app/utils/permissions.py` - Add master admin permission checks
- `app/keyboards/admin.py` - Add keyboard builders (if needed)

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
async def test_permission_checks_work_correctly()
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

---

## ⚠️ Dependencies

### Prerequisites:
- **STORY-001** must be completed (BotConfigService must be implemented)
- Database tables must exist: `bots`, `bot_feature_flags`, `bot_configurations`, `bot_plans`, `tenant_payment_cards`

### Blocks:
- Future stories requiring admin panel access
- Tenant bot creation workflows

---

## 📚 References

### Documentation:
- `docs/tenant-bots-admin-ux-design.md` - Complete UX design specification
- `docs/tenant-bots-callback-handler-mapping.md` - Callback mapping reference
- `docs/tenant-configs-categorization.md` - Config categorization
- `docs/MASTER-IMPLEMENTATION-GUIDE.md` - Master implementation guide

### Related Stories:
- STORY-001: Eliminate Schema Redundancy and Implement BotConfigService (prerequisite)

---

## 📝 Definition of Done

- [ ] All menu levels implemented and functional
- [ ] All handlers use `BotConfigService` for config access
- [ ] All database queries tested and optimized
- [ ] Feature flags management working with plan restrictions
- [ ] Configuration management working for all 8 categories
- [ ] Bot creation flow complete
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

**Story Owner:** Development Team  
**Reviewers:** Architecture Team, UX Team, QA Team  
**Dependencies:** STORY-001 (BotConfigService must be implemented first)  
**Blocks:** Future stories requiring admin panel access

