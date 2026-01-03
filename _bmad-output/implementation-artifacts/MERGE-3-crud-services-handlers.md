# Story MERGE-3: CRUD Operations, Services & Handlers

**Status:** ready-for-dev  
**Epic:** MERGE-UPSTREAM-MAIN (Temporary)  
**Priority:** 🟡 HIGH  
**Estimated Time:** 87 hours  
**Dependencies:** MERGE-2

---

## Story

As a **developer**,  
I want to **merge CRUD operations, services, and handlers from upstream with tenant compatibility**,  
so that **all database operations, business logic, and user-facing features work correctly with tenant isolation**.

---

## Acceptance Criteria

1. ✅ **AC 3.1:** Given a promocode with `first_purchase_only=True`, when user makes first purchase, then promocode is applied
2. ✅ **AC 3.2:** Given a subscription renewal, when traffic reset is enabled, then `traffic_consumed_bytes` is reset to 0
3. ✅ **AC 3.3:** Given a bot_id, when querying users, then only users for that tenant are returned
4. ✅ **AC 3.4:** Given a bot_id and user_id, when getting cart, then Redis key is `cart:{bot_id}:{user_id}`
5. ✅ **AC 3.5:** Given all CRUD files, when validation scripts run, then no tenant isolation violations found
6. ✅ **AC 3.6:** Given all handlers, when calling endpoints, then tenant context is properly used

---

## Tasks / Subtasks

### Phase 3: CRUD Operations (27 hours)

#### Task 3.1: Update Promocode CRUD
- [ ] **Action:** Add first_purchase_only and pagination to Promocode CRUD
  - **Files:**
    - `app/database/crud/promocode.py` (MODIFY, ~50-100 lines)
  - **Changes:**
    ```python
    # Add parameter to create_promocode():
    async def create_promocode(
        ...,
        first_purchase_only: bool = False  # ADD
    ):
        # Add validation logic
    
    # Add pagination to get_promocodes_list():
    async def get_promocodes_list(
        ...,
        offset: int = 0,  # ADD
        limit: int = 50,  # ADD
        bot_id: Optional[int] = None  # VERIFY exists
    ):
        # Add pagination logic
        # VERIFY bot_id filter exists
    ```
  - **Lines Affected:** Function signatures and implementations
  - **Verification:** Tests pass, bot_id filter verified

#### Task 3.2: Update Subscription CRUD
- [ ] **Action:** Add traffic reset and auto-activation
  - **Files:**
    - `app/database/crud/subscription.py` (MODIFY, ~50-100 lines)
  - **Changes:**
    ```python
    # Update renew_subscription():
    async def renew_subscription(...):
        # ADD: Reset traffic_consumed_bytes to 0
        subscription.traffic_consumed_bytes = 0
    
    # Update activate_subscription():
    async def activate_subscription(...):
        # ADD: Auto-activation logic
    ```
  - **Verification:** Traffic reset works, auto-activation works

#### Task 3.3: Update User CRUD
- [ ] **Action:** Add balance filter and extended filters
  - **Files:**
    - `app/database/crud/user.py` (MODIFY, ~50-100 lines)
  - **Changes:**
    ```python
    # Update get_users_list():
    async def get_users_list(
        ...,
        balance_min: Optional[int] = None,  # ADD
        balance_max: Optional[int] = None,  # ADD
        bot_id: Optional[int] = None  # VERIFY exists
    ):
        # Add filter logic
        # VERIFY bot_id filter exists
    ```
  - **Verification:** Filters work, bot_id filter verified

#### Task 3.4: Merge Remaining CRUD Files - Batch 1 (15 files)
- [ ] **Action:** Review and merge 15 CRUD files
  - **Files:** First 15 files from `app/database/crud/*.py`
  - **Process for each file:**
    1. Verify `bot_id: Optional[int] = None` parameter exists
    2. Merge changes from upstream
    3. Add `bot_id` filter to queries if missing
    4. Verify query performance (add indexes if needed)
    5. Add/update tests
  - **Verification:** Validation scripts pass, tests pass

#### Task 3.5: Merge Remaining CRUD Files - Batch 2 (16 files)
- [ ] **Action:** Review and merge next 16 CRUD files
  - **Files:** Next 16 files from `app/database/crud/*.py`
  - **Process:** Same as Task 3.4
  - **Verification:** Validation scripts pass, tests pass

#### Task 3.6: Merge Remaining CRUD Files - Batch 3 (16 files)
- [ ] **Action:** Review and merge final 16 CRUD files
  - **Files:** Final 16 files from `app/database/crud/*.py`
  - **Process:** Same as Task 3.4
  - **Verification:** Validation scripts pass, tests pass

### Phase 4: Services (31 hours)

#### Task 4.1: Update Subscription Service
- [ ] **Action:** Merge purchase flow and traffic reset
  - **Files:**
    - `app/services/subscription_service.py` (MODIFY, ~100-200 lines)
  - **Changes:**
    - Merge purchase flow changes from upstream
    - Add traffic reset logic
    - Ensure tenant context in all operations
  - **Verification:** Purchase flow works, traffic reset works

#### Task 4.2: Refactor Cart Service
- [ ] **Action:** Make cart service tenant-aware with Redis keys
  - **Files:**
    - `app/services/user_cart_service.py` (MODIFY, ~50-100 lines)
  - **Changes:**
    ```python
    # Add bot_id parameter to all functions:
    async def get_cart(db, user_id: int, bot_id: int):  # ADD bot_id
        cache_key = f"cart:{bot_id}:{user_id}"  # CHANGE from cart:{user_id}
        # Use cache_key() utility if available
    ```
  - **Lines Affected:** All function signatures and Redis key generation
  - **Verification:** Tenant isolation works, keys have prefix

#### Task 4.3: Merge Payment Service
- [ ] **Action:** Merge modular payment structure
  - **Files:**
    - `app/services/payment_service.py` (MODIFY, ~100-200 lines)
  - **Changes:**
    - Merge modular payment structure from upstream
    - Ensure tenant context in all operations
  - **Verification:** Payment flow works with tenant context

#### Task 4.4: Merge Remaining Services - Batch 1 (20 files)
- [ ] **Action:** Review and merge 20 service files
  - **Files:** First 20 files from `app/services/*.py`
  - **Process for each file:**
    1. Verify tenant context usage
    2. Merge changes from upstream
    3. Add `bot_id` parameter if needed
    4. Optimize tenant config lookups (cache if needed)
    5. Add/update tests
  - **Verification:** Validation scripts pass, tests pass

#### Task 4.5: Merge Remaining Services - Batch 2 (20 files)
- [ ] **Action:** Review and merge next 20 service files
  - **Files:** Next 20 files from `app/services/*.py`
  - **Process:** Same as Task 4.4
  - **Verification:** Validation scripts pass, tests pass

#### Task 4.6: Merge Remaining Services - Batch 3 (17 files)
- [ ] **Action:** Review and merge final 17 service files
  - **Files:** Final 17 files from `app/services/*.py`
  - **Process:** Same as Task 4.4
  - **Verification:** Validation scripts pass, tests pass

### Phase 5: Handlers (29 hours)

#### Task 5.1: Merge Subscription Handlers
- [ ] **Action:** Merge subscription handlers with modem support
  - **Files:**
    - `app/handlers/subscription/purchase.py` (MODIFY, ~100-200 lines)
    - `app/handlers/subscription/modem.py` (NEW/MODIFY, ~50-100 lines)
  - **Changes:**
    - Merge purchase flow changes
    - Add modem support handler
    - Ensure tenant context
  - **Verification:** Purchase flow works, modem support works

#### Task 5.2: Merge Admin Handlers
- [ ] **Action:** Merge admin handlers with pagination and filters
  - **Files:**
    - `app/handlers/admin/promocodes.py` (MODIFY, ~50-100 lines)
    - `app/handlers/admin/users.py` (MODIFY, ~100-200 lines)
  - **Changes:**
    - Add pagination to promocodes handler
    - Add balance filter and extended filters to users handler
    - Add admin purchase subscription feature
    - Ensure tenant context
  - **Verification:** Pagination works, filters work

#### Task 5.3: Merge Remaining Handlers - Batch 1 (25 files)
- [ ] **Action:** Review and merge 25 handler files
  - **Files:** First 25 files from `app/handlers/*.py`
  - **Process for each file:**
    1. Verify tenant context usage
    2. Merge changes from upstream
    3. Add tests
  - **Verification:** Validation scripts pass, tests pass

#### Task 5.4: Code Review Checkpoint - Handlers Batch 1
- [ ] **Action:** Review first batch for tenant compatibility
  - **Files:** First 25 handler files
  - **Actions:**
    1. Review tenant context usage
    2. Fix issues before proceeding
    3. Run validation scripts
  - **Verification:** All issues fixed, validation passes

#### Task 5.5: Merge Remaining Handlers - Batch 2 (26 files)
- [ ] **Action:** Review and merge next 26 handler files
  - **Files:** Next 26 files from `app/handlers/*.py`
  - **Process:** Same as Task 5.3
  - **Verification:** Validation scripts pass, tests pass

#### Task 5.6: Code Review Checkpoint - Handlers Batch 2
- [ ] **Action:** Review second batch for tenant compatibility
  - **Files:** Next 26 handler files
  - **Process:** Same as Task 5.4
  - **Verification:** All issues fixed, validation passes

#### Task 5.7: Merge Remaining Handlers - Batch 3 (26 files)
- [ ] **Action:** Review and merge final 26 handler files
  - **Files:** Final 26 files from `app/handlers/*.py`
  - **Process:** Same as Task 5.3
  - **Verification:** Validation scripts pass, tests pass

#### Task 5.8: Code Review Checkpoint - Handlers Batch 3
- [ ] **Action:** Review final batch for tenant compatibility
  - **Files:** Final 26 handler files
  - **Process:** Same as Task 5.4
  - **Verification:** All issues fixed, validation passes

---

## Dev Notes

### Critical Requirements
- ✅ **MUST** verify bot_id filter in all CRUD queries
- ✅ **MUST** ensure tenant context in all service operations
- ✅ **MUST** verify Redis keys have tenant prefix
- ✅ **MUST** run validation scripts after each batch

### Files Affected

**CRUD Files (47 files):**
- `app/database/crud/promocode.py` (MODIFY)
- `app/database/crud/subscription.py` (MODIFY)
- `app/database/crud/user.py` (MODIFY)
- `app/database/crud/*.py` (44 other files, MODIFY)

**Service Files (57 files):**
- `app/services/subscription_service.py` (MODIFY)
- `app/services/user_cart_service.py` (MODIFY)
- `app/services/payment_service.py` (MODIFY)
- `app/services/*.py` (54 other files, MODIFY)

**Handler Files (77 files):**
- `app/handlers/subscription/purchase.py` (MODIFY)
- `app/handlers/subscription/modem.py` (NEW/MODIFY)
- `app/handlers/admin/promocodes.py` (MODIFY)
- `app/handlers/admin/users.py` (MODIFY)
- `app/handlers/*.py` (73 other files, MODIFY)

**Total Files:** ~181 files
**Total Lines Affected:** ~5000-10000 lines

### Implementation Details

**CRUD Pattern:**
```python
async def get_items(
    db: AsyncSession,
    offset: int = 0,
    limit: int = 50,
    bot_id: Optional[int] = None  # REQUIRED
):
    query = select(Model)
    if bot_id is not None:
        query = query.where(Model.bot_id == bot_id)
    # ... rest of query
```

**Service Pattern:**
```python
async def service_method(
    db: AsyncSession,
    user_id: int,
    bot_id: int  # REQUIRED
):
    # All operations use bot_id
    # All config lookups use bot_id
```

**Handler Pattern:**
```python
@router.get("/endpoint")
async def handler(
    ...,
    bot_id: int = Depends(get_current_tenant)  # REQUIRED
):
    # All service calls pass bot_id
```

### Testing Strategy
1. **Unit Tests:**** Each CRUD function, service method
2. **Integration Tests:**** Full flows with tenant isolation
3. **Validation Tests:**** Run scripts after each batch
4. **Performance Tests:**** Query performance with indexes

---

## Results & Issues

### Completion Status
- [ ] Phase 3 complete (CRUD Operations)
- [ ] Phase 4 complete (Services)
- [ ] Phase 5 complete (Handlers)
- [ ] All batches reviewed
- [ ] All validation scripts pass
- [ ] All ACs verified

### Issues Found
- **Issue 1:** [Description]
  - **Severity:** 🔴 Critical / 🟡 Medium / 🟢 Low
  - **Status:** Open / Fixed
  - **Location:** [File:Line]
  - **Fix:** [Solution]

### Bugs Found
- **Bug 1:** [Description]
  - **Location:** [File:Line]
  - **Status:** Open / Fixed
  - **Fix:** [Solution]

### Batch Progress
- **CRUD Batch 1:** ✅ Complete / ⏳ In Progress / ❌ Blocked
- **CRUD Batch 2:** ✅ Complete / ⏳ In Progress / ❌ Blocked
- **CRUD Batch 3:** ✅ Complete / ⏳ In Progress / ❌ Blocked
- **Services Batch 1:** ✅ Complete / ⏳ In Progress / ❌ Blocked
- **Services Batch 2:** ✅ Complete / ⏳ In Progress / ❌ Blocked
- **Services Batch 3:** ✅ Complete / ⏳ In Progress / ❌ Blocked
- **Handlers Batch 1:** ✅ Complete / ⏳ In Progress / ❌ Blocked
- **Handlers Batch 2:** ✅ Complete / ⏳ In Progress / ❌ Blocked
- **Handlers Batch 3:** ✅ Complete / ⏳ In Progress / ❌ Blocked

### Validation Results
- **Queries Checked:** [Number]
- **Violations Found:** [Number] (list files)
- **Routes Checked:** [Number]
- **Redis Keys Checked:** [Number]

### Test Results
- **Unit Tests:** [X/Y] passing
- **Integration Tests:** [X/Y] passing
- **Coverage:** [XX]%

### Next Steps
- [ ] Proceed to Story MERGE-4 (Nalogo, Bug Fixes, Testing)
- [ ] Or fix issues first

---

**Story Status:** ⏳ In Progress / ✅ Complete / ❌ Blocked  
**Completed At:** [Date/Time]  
**Completed By:** [Developer Name]
