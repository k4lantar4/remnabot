# Sprint Change Proposal: STORY-002 UX Pattern Alignment & Query Optimization

**Date:** 2025-12-21  
**Story:** STORY-002 - Implement Tenant Bots Admin UX Panel  
**Trigger:** UX implementation doesn't follow established admin panel patterns  
**Scope:** Moderate (requires code refactoring and pattern alignment)

---

## 1. Issue Summary

The tenant bots admin panel implementation (AC2: List Bots with Pagination) doesn't follow the established UX patterns used in other admin handlers (users, servers, subscriptions). Additionally, the database query implementation is inefficient (N+1 problem) and doesn't match the specification.

### Problems Identified:

1. **UX Pattern Mismatch:**
   - Custom pagination implementation instead of using `get_admin_pagination_keyboard()`
   - Inconsistent text formatting compared to other admin lists
   - Callback pattern doesn't match standard (`admin_tenant_bots_list:{page}` vs `admin_tenant_bots_list_page_{page}`)
   - Missing proper pagination handler registration

2. **Query Performance Issues:**
   - Current implementation loads all bots, then queries stats for each bot individually (N+1 problem)
   - Should use optimized JOIN query as specified in story
   - Plan information query uses try/except fallback instead of proper schema check

3. **Code Organization:**
   - Not following modular patterns from other admin handlers
   - Missing separation of concerns

---

## 2. Impact Analysis

### Epic Impact:
- **Epic:** Multi-Tenant Architecture - Admin Panel
- **Affected Stories:** STORY-002 (current), potentially STORY-003

### Story Impact:
- **AC1:** Main Menu - Minor impact (query optimization needed)
- **AC2:** List Bots - **MAJOR IMPACT** - Complete refactoring required
- **AC3:** Bot Detail - Minor impact (may need similar pattern alignment)
- **AC4-AC13:** No immediate impact, but should follow same patterns

### Technical Impact:
- **Code Changes:** `app/handlers/admin/tenant_bots.py` - `list_tenant_bots()` function
- **Database:** Requires `tenant_subscriptions` and `tenant_subscription_plans` tables (already created per migrations)
- **Dependencies:** Uses existing `get_admin_pagination_keyboard()` from `app/keyboards/admin.py`

### Artifact Conflicts:
- Story specification (AC2) is correct - implementation doesn't match spec
- No PRD/Architecture changes needed

---

## 3. Recommended Approach

**Path:** Direct Adjustment - Refactor AC2 implementation to match established patterns

### Rationale:
1. Story specification is correct and aligns with existing patterns
2. Implementation needs refactoring to match codebase standards
3. No scope reduction needed - just pattern alignment
4. Low risk - changes are localized to one handler function

### Effort Estimate:
- **Development:** 2-3 hours
- **Testing:** 1 hour
- **Total:** 3-4 hours

### Risk Assessment:
- **Low Risk:** Changes are isolated to one function
- **No Breaking Changes:** Only improves existing functionality
- **Backward Compatible:** Callback pattern change is additive (old pattern still works)

---

## 4. Detailed Change Proposals

### 4.1. AC2: List Bots Handler Refactoring

**File:** `app/handlers/admin/tenant_bots.py`  
**Function:** `list_tenant_bots()`

#### Current Implementation Issues:

```python
# Current: Loads all bots, then queries stats individually (N+1 problem)
all_bots = await get_all_bots(db)
tenant_bots = [b for b in all_bots if not b.is_master]
# ... then loops and queries stats for each bot
```

#### Proposed Implementation:

**OLD:**
```python
@admin_required
@error_handler
async def list_tenant_bots(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """List all tenant bots with pagination, showing user count, revenue, and plan."""
    texts = get_texts(db_user.language)
    
    # Parse page number from callback data
    page = 0
    if ":" in callback.data:
        try:
            page = int(callback.data.split(":")[1])
        except (ValueError, IndexError):
            page = 0
    
    # Get only tenant bots (exclude master)
    all_bots = await get_all_bots(db)
    tenant_bots = [b for b in all_bots if not b.is_master]
    
    page_size = 5
    total_pages = (len(tenant_bots) + page_size - 1) // page_size if tenant_bots else 1
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_bots = tenant_bots[start_idx:end_idx]
    
    # ... N+1 queries for each bot ...
    
    # Custom pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(...)
    # ...
```

**NEW:**
```python
@admin_required
@error_handler
async def list_tenant_bots(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    page: int = 1  # Changed: 1-based like other handlers
):
    """List all tenant bots with pagination, showing user count, revenue, and plan."""
    texts = get_texts(db_user.language)
    
    # Parse page from callback if not provided
    if page == 1 and ":" in callback.data:
        try:
            page = int(callback.data.split(":")[1])
        except (ValueError, IndexError):
            page = 1
    elif page == 1 and "_page_" in callback.data:
        # Support standard pagination pattern: admin_tenant_bots_list_page_{page}
        try:
            page = int(callback.data.split("_page_")[1])
        except (ValueError, IndexError):
            page = 1
    
    page_size = 5
    offset = (page - 1) * page_size
    
    # Optimized query with JOINs (matches story spec)
    from app.database.models import Bot, User, Transaction, TransactionType
    from app.database.models import TenantSubscription, TenantSubscriptionPlan
    
    query = (
        select(
            Bot,
            func.count(func.distinct(User.id)).label('user_count'),
            func.coalesce(func.sum(Transaction.amount_toman), 0).label('revenue'),
            TenantSubscriptionPlan.display_name.label('plan_name')
        )
        .select_from(Bot)
        .outerjoin(User, User.bot_id == Bot.id)
        .outerjoin(
            Transaction,
            and_(
                Transaction.bot_id == Bot.id,
                Transaction.type == TransactionType.DEPOSIT.value,
                Transaction.is_completed == True
            )
        )
        .outerjoin(
            TenantSubscription,
            and_(
                TenantSubscription.bot_id == Bot.id,
                TenantSubscription.status == 'active'
            )
        )
        .outerjoin(
            TenantSubscriptionPlan,
            TenantSubscriptionPlan.id == TenantSubscription.plan_tier_id
        )
        .where(Bot.is_master == False)
        .group_by(Bot.id, TenantSubscriptionPlan.display_name)
        .order_by(Bot.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    # Get total count for pagination
    count_query = select(func.count(Bot.id)).where(Bot.is_master == False)
    total_count_result = await db.execute(count_query)
    total_count = total_count_result.scalar() or 0
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    
    # Format text (match other admin lists pattern)
    text = texts.t(
        "ADMIN_TENANT_BOTS_LIST_TITLE",
        "🤖 <b>Tenant Bots</b> (page {page}/{total})"
    ).format(page=page, total=total_pages) + "\n\n"
    
    if not rows:
        text += texts.t("ADMIN_TENANT_BOTS_EMPTY", "No tenant bots found.")
    else:
        text += texts.t("ADMIN_TENANT_BOTS_LIST_HINT", "Click on a bot to manage:") + "\n\n"
        
        keyboard = []
        for row in rows:
            bot = row[0]  # Bot object
            user_count = row[1] or 0
            revenue = (row[2] or 0) / 100  # Convert from kopeks to toman
            plan_name = row[3] or "N/A"
            
            status_icon = "✅" if bot.is_active else "⏸️"
            
            # Format bot info (match users list pattern)
            button_text = f"{status_icon} {bot.name} (ID: {bot.id})"
            if len(button_text) > 50:
                button_text = f"{status_icon} {bot.name[:20]}... (ID: {bot.id})"
            
            # Add stats to text (not button - matches users pattern)
            text += f"{status_icon} <b>{bot.name}</b> (ID: {bot.id})\n"
            text += f"   • Users: {user_count} | Revenue: {revenue:,.0f} Toman | Plan: {plan_name}\n\n"
            
            keyboard.append([
                types.InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"admin_tenant_bot_detail:{bot.id}"
                )
            ])
    
    # Use standard pagination keyboard (matches other handlers)
    from app.keyboards.admin import get_admin_pagination_keyboard
    pagination_row = get_admin_pagination_keyboard(
        current_page=page,
        total_pages=total_pages,
        callback_prefix="admin_tenant_bots_list",
        back_callback="admin_tenant_bots_menu",
        language=db_user.language
    )
    
    # Combine keyboard with pagination
    final_keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard + pagination_row.inline_keyboard)
    
    await callback.message.edit_text(text, reply_markup=final_keyboard, parse_mode="HTML")
    await callback.answer()
```

#### Key Changes:
1. ✅ Use optimized JOIN query (matches story spec)
2. ✅ 1-based pagination (matches other handlers)
3. ✅ Use `get_admin_pagination_keyboard()` (standard pattern)
4. ✅ Text formatting matches users/servers lists
5. ✅ Support both callback patterns (backward compatible)

### 4.2. Pagination Handler Registration

**File:** `app/handlers/admin/tenant_bots.py`  
**Function:** `register_handlers()`

#### Current:
```python
dp.callback_query.register(
    list_tenant_bots,
    F.data.startswith("admin_tenant_bots_list")
)
```

#### Proposed:
```python
# Main list handler (page 1 or no page specified)
dp.callback_query.register(
    list_tenant_bots,
    F.data == "admin_tenant_bots_list"
)

# Pagination handler (standard pattern)
dp.callback_query.register(
    handle_tenant_bots_list_pagination,
    F.data.startswith("admin_tenant_bots_list_page_")
)

# Add pagination handler function:
@admin_required
@error_handler
async def handle_tenant_bots_list_pagination(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession
):
    """Handle pagination for tenant bots list."""
    try:
        page = int(callback.data.split("_page_")[1])
        await list_tenant_bots(callback, db_user, db, page=page)
    except (ValueError, IndexError) as e:
        logger.error(f"Error parsing page number: {e}")
        await list_tenant_bots(callback, db_user, db, page=1)
```

### 4.3. Database Models Import

**File:** `app/handlers/admin/tenant_bots.py`

#### Option A: Use Table References (Recommended - Models don't exist yet)
```python
from sqlalchemy import Table, MetaData
from app.database.database import engine

# Get table references
metadata = MetaData()
metadata.reflect(bind=engine)
tenant_subscriptions_table = metadata.tables['tenant_subscriptions']
tenant_subscription_plans_table = metadata.tables['tenant_subscription_plans']
```

#### Option B: Create Models (Alternative - if preferred)
Add to `app/database/models.py`:
```python
class TenantSubscriptionPlan(Base):
    __tablename__ = "tenant_subscription_plans"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(255), nullable=False)
    monthly_price_toman = Column(Integer, nullable=False)
    activation_fee_toman = Column(Integer, default=0, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"
    
    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, unique=True)
    plan_tier_id = Column(Integer, ForeignKey("tenant_subscription_plans.id"), nullable=False)
    status = Column(String(20), default='active', nullable=False)
    start_date = Column(DateTime, default=func.now(), nullable=False)
    end_date = Column(DateTime, nullable=True)
    auto_renewal = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
```

**Note:** Tables exist (from migrations), but SQLAlchemy models don't. Use Option A for immediate implementation, or Option B if you prefer ORM models.

### 4.4. AC1: Main Menu Query Optimization

**File:** `app/handlers/admin/tenant_bots.py`  
**Function:** `show_tenant_bots_menu()`

#### Current:
Uses multiple separate queries. Should optimize to match story spec.

#### Proposed:
Update to use the query pattern from story spec (lines 72-79) for better performance.

---

## 5. Implementation Handoff

### Change Scope: **Moderate**

**Classification:** Code refactoring and pattern alignment  
**Impact:** Localized to tenant bots admin handlers  
**Risk:** Low - isolated changes, backward compatible

### Handoff Recipients:

1. **Development Team** (Primary)
   - Implement query optimization
   - Refactor pagination to use standard patterns
   - Add pagination handler registration
   - Test with existing data

2. **QA/Testing** (Secondary)
   - Verify pagination works correctly
   - Test with various page counts
   - Verify backward compatibility with old callback pattern
   - Performance testing (query optimization impact)

### Success Criteria:

- [ ] AC2 handler uses optimized JOIN query (matches story spec)
- [ ] Pagination uses `get_admin_pagination_keyboard()` function
- [ ] Text formatting matches other admin lists (users, servers)
- [ ] Callback pattern supports both old and new formats (backward compatible)
- [ ] Pagination handler properly registered
- [ ] No N+1 query issues
- [ ] Performance improvement verified (query time < 100ms for typical data)

### Testing Checklist:

- [ ] Test pagination with 0 bots
- [ ] Test pagination with 1-5 bots (single page)
- [ ] Test pagination with 6-10 bots (2 pages)
- [ ] Test pagination with 20+ bots (multiple pages)
- [ ] Test Previous/Next buttons
- [ ] Test direct page navigation
- [ ] Test old callback pattern (`admin_tenant_bots_list:0`)
- [ ] Test new callback pattern (`admin_tenant_bots_list_page_1`)
- [ ] Verify plan information displays correctly
- [ ] Verify user count and revenue calculations
- [ ] Performance test: Query time < 100ms

---

## 6. Additional Recommendations

### 6.1. Review Other ACs for Similar Issues

**Action:** Review AC3, AC4, AC5, etc. for similar pattern mismatches:
- Check if they use standard keyboard functions
- Verify callback patterns match established conventions
- Ensure text formatting is consistent

### 6.2. Database Schema Verification

**Action:** Verify `TenantSubscription` and `TenantSubscriptionPlan` models exist:
- Check `app/database/models.py`
- If missing, add models or update query to use table references
- Verify migrations have been applied

### 6.3. Code Review Checklist

Before merging, verify:
- [ ] Follows same patterns as `app/handlers/admin/users.py`
- [ ] Uses standard keyboard functions from `app/keyboards/admin.py`
- [ ] Callback patterns match other handlers
- [ ] Error handling matches decorator patterns
- [ ] Text localization uses `get_texts()` correctly

---

## 7. Story Updates Required

### Update STORY-002 Checklist:

**AC2: List Bots with Pagination**
- [x] Handler exists: `app/handlers/admin/tenant_bots.py::list_tenant_bots` ✅ **IMPLEMENTED**
- [x] Displays paginated list of tenant bots (5 per page) ✅
- [ ] Each bot shows: Name, ID, Status, User Count, Revenue, Plan - **IN PROGRESS** (needs query update)
- [x] Clicking a bot navigates to bot detail menu ✅
- [ ] Pagination controls (Previous/Next) work correctly - **NEEDS REFACTOR** (use standard keyboard)
- [ ] Callback: `admin_tenant_bots_list` or `admin_tenant_bots_list:{page}` - **UPDATE TO STANDARD PATTERN**
- [ ] **UPDATE QUERY** - Current implementation uses simpler query, update to match spec below (includes tenant_subscriptions join) - **IN PROGRESS**

---

## 8. Timeline

- **Analysis:** ✅ Complete
- **Implementation:** 3-4 hours
- **Testing:** 1 hour
- **Review:** 30 minutes
- **Total:** ~5 hours

---

## Approval

**Status:** Ready for Implementation  
**Approved by:** [Pending]  
**Date:** [Pending]

