# Story MERGE-2: Cabinet Module - Tenant-Aware Refactoring

**Status:** ready-for-dev  
**Epic:** MERGE-UPSTREAM-MAIN (Temporary)  
**Priority:** 🔴 CRITICAL  
**Estimated Time:** 25 hours  
**Dependencies:** MERGE-1

---

## Story

As a **developer**,  
I want to **add Cabinet module from upstream and refactor it for tenant-aware architecture**,  
so that **each tenant has isolated Cabinet access with their own JWT secrets and user data**.

---

## Acceptance Criteria

1. ✅ **AC 2.1:** Given upstream/main, when copying Cabinet files, then all 31 Cabinet files are copied with correct structure
2. ✅ **AC 2.2:** Given user_id, telegram_id, and bot_id, when calling `create_access_token()`, then JWT payload contains `bot_id` claim
3. ✅ **AC 2.3:** Given a Cabinet route, when calling endpoint, then `bot_id` is extracted from tenant dependency
4. ✅ **AC 2.4:** Given two different tenants, when calling same Cabinet endpoint, then they see only their own data (tenant isolation)
5. ✅ **AC 2.5:** Given a Cabinet route without tenant context, when calling endpoint, then it returns 401 Unauthorized
6. ✅ **AC 2.6:** Given Cabinet routes, when registering in FastAPI app, then all routes are accessible with `/cabinet` prefix

---

## Tasks / Subtasks

### Phase 2.1: Add Cabinet Module from Upstream

#### Task 2.1.1: Discover Cabinet Files in Upstream
- [ ] **Action:** Count and list all Cabinet files in upstream
  - **Command:** `git ls-tree -r upstream/main --name-only | grep "^app/cabinet/"`
  - **Expected Structure:**
    ```
    app/cabinet/
    ├── auth/
    │   ├── jwt_handler.py
    │   └── telegram_auth.py
    ├── dependencies.py
    └── routes/
        ├── auth.py
        ├── info.py
        ├── balance.py
        ├── subscription.py
        ├── tickets.py
        ├── admin_*.py (3 files)
        ├── promo.py
        ├── promocode.py
        ├── referral.py
        ├── branding.py
        ├── contests.py
        ├── notifications.py
        └── polls.py
    ```
  - **Output:** Create file inventory: `docs/cabinet-files-inventory.md`

#### Task 2.1.2: Copy Cabinet Files from Upstream
- [ ] **Action:** Copy all Cabinet files preserving structure
  - **Files:** All files in `app/cabinet/` (31 files estimated)
  - **Command:**
    ```bash
    git checkout upstream/main -- app/cabinet/
    ```
  - **Verification:** All files copied, structure preserved

### Phase 2.2: Refactor Cabinet Auth for Tenant-Aware

#### Task 2.2.1: Refactor JWT Handler
- [ ] **Action:** Make JWT handler tenant-aware
  - **Files:**
    - `app/cabinet/auth/jwt_handler.py` (MODIFY, ~100-200 lines)
  - **Changes:**
    ```python
    # BEFORE:
    def create_access_token(user_id: int, telegram_id: int) -> str:
        payload = {"sub": str(user_id), "telegram_id": telegram_id}
    
    # AFTER:
    def create_access_token(user_id: int, telegram_id: int, bot_id: int) -> str:
        payload = {
            "sub": str(user_id),
            "telegram_id": telegram_id,
            "bot_id": bot_id  # ADD
        }
        # Use tenant config:
        secret = await get_cabinet_jwt_secret(db, bot_id)
    
    def create_refresh_token(user_id: int, bot_id: int) -> str:
        # Similar changes
    ```
  - **Lines Affected:** Function signatures and payload construction
  - **Verification:** JWT contains bot_id, validation checks bot_id

#### Task 2.2.2: Refactor Telegram Auth
- [ ] **Action:** Make Telegram auth tenant-aware
  - **Files:**
    - `app/cabinet/auth/telegram_auth.py` (MODIFY, ~50-100 lines)
  - **Changes:**
    ```python
    # BEFORE:
    async def validate_telegram_login_widget(...):
        # User lookup without bot_id
    
    # AFTER:
    async def validate_telegram_login_widget(..., bot_id: int):
        # User lookup with bot_id filter
        user = await get_user_by_telegram_id(db, telegram_id, bot_id)
    ```
  - **Verification:** User lookup includes bot_id, tenant isolation works

### Phase 2.3: Update Cabinet Dependencies

#### Task 2.3.1: Add Tenant Dependency
- [ ] **Action:** Add tenant dependency to Cabinet dependencies
  - **Files:**
    - `app/cabinet/dependencies.py` (MODIFY, ~20-50 lines)
  - **Changes:**
    ```python
    from app.core.tenant_context import get_current_tenant
    
    def get_cabinet_tenant() -> int:
        """Get tenant ID for Cabinet routes."""
        return get_current_tenant()
    ```
  - **Verification:** Dependency function works, returns bot_id

### Phase 2.4: Refactor All Cabinet Routes

#### Task 2.4.1: Refactor Auth Routes
- [ ] **Action:** Add tenant dependency to auth routes
  - **Files:**
    - `app/cabinet/routes/auth.py` (MODIFY, all route functions)
  - **Changes:**
    ```python
    # Add to all route functions:
    @router.post("/login")
    async def login(
        ...,
        bot_id: int = Depends(get_current_tenant)  # ADD
    ):
        # Add tenant mismatch validation:
        if user.bot_id != bot_id:
            raise HTTPException(403, "Tenant mismatch")
    ```
  - **Lines Affected:** All route function signatures (~50-100 lines)

#### Task 2.4.2: Refactor Info Routes
- [ ] **Action:** Add tenant dependency to info routes
  - **Files:**
    - `app/cabinet/routes/info.py` (MODIFY, all route functions)
  - **Changes:** Similar to Task 2.4.1
  - **Lines Affected:** All route functions

#### Task 2.4.3: Refactor Balance Routes
- [ ] **Action:** Add tenant dependency to balance routes
  - **Files:**
    - `app/cabinet/routes/balance.py` (MODIFY, all route functions)
  - **Changes:** Similar to Task 2.4.1
  - **Lines Affected:** All route functions

#### Task 2.4.4: Refactor Subscription Routes
- [ ] **Action:** Add tenant dependency to subscription routes
  - **Files:**
    - `app/cabinet/routes/subscription.py` (MODIFY, all route functions)
  - **Changes:** Similar to Task 2.4.1
  - **Lines Affected:** All route functions

#### Task 2.4.5: Refactor Tickets Routes
- [ ] **Action:** Add tenant dependency to tickets routes
  - **Files:**
    - `app/cabinet/routes/tickets.py` (MODIFY, all route functions)
  - **Changes:** Similar to Task 2.4.1
  - **Lines Affected:** All route functions

#### Task 2.4.6: Refactor Admin Routes (3 files)
- [ ] **Action:** Add tenant dependency to admin routes
  - **Files:**
    - `app/cabinet/routes/admin_*.py` (MODIFY, 3 files, all route functions)
  - **Changes:** Similar to Task 2.4.1
  - **Lines Affected:** All route functions in 3 files

#### Task 2.4.7: Refactor Remaining Routes (6 files)
- [ ] **Action:** Add tenant dependency to remaining routes
  - **Files:**
    - `app/cabinet/routes/promo.py`
    - `app/cabinet/routes/promocode.py`
    - `app/cabinet/routes/referral.py`
    - `app/cabinet/routes/branding.py`
    - `app/cabinet/routes/contests.py`
    - `app/cabinet/routes/notifications.py`
    - `app/cabinet/routes/polls.py`
  - **Changes:** Similar to Task 2.4.1
  - **Lines Affected:** All route functions in 7 files

#### Task 2.4.8: Add Error Handling to All Routes
- [ ] **Action:** Add error handling for missing tenant context
  - **Files:** All Cabinet route files (17 files)
  - **Changes:**
    ```python
    # Add to all routes:
    if bot_id is None:
        raise HTTPException(
            status_code=401,
            detail=Texts.get("cabinet.tenant_context_missing")
        )
    
    # Add tenant mismatch check:
    if user.bot_id != bot_id:
        logger.warning("Tenant mismatch", user_bot_id=user.bot_id, token_bot_id=bot_id)
        raise HTTPException(
            status_code=403,
            detail=Texts.get("cabinet.tenant_mismatch")
        )
    ```
  - **Lines Affected:** All route functions (~200-300 lines total)

### Phase 2.5: Register Cabinet Routes

#### Task 2.5.1: Register Cabinet Router
- [ ] **Action:** Register Cabinet router in FastAPI app
  - **Files:**
    - `app/webapi/app.py` (MODIFY, ~10-20 lines)
  - **Changes:**
    ```python
    from app.cabinet.routes import router as cabinet_router
    
    app.include_router(
        cabinet_router,
        prefix="/cabinet",
        tags=["cabinet"]
    )
    ```
  - **Verification:** Routes accessible, tenant middleware applied

#### Task 2.5.2: Create Integration Tests
- [ ] **Action:** Create comprehensive Cabinet integration tests
  - **Files:**
    - `tests/integration/test_cabinet_tenant_isolation.py` (NEW, ~200 lines)
  - **Test Cases:**
    - Tenant isolation (user A cannot access user B's data)
    - JWT validation with bot_id
    - Tenant mismatch scenarios (403 Forbidden)
    - Missing tenant context (401 Unauthorized)
    - All Cabinet routes with tenant context
  - **Verification:** All tests pass

---

## Dev Notes

### Critical Requirements
- ✅ **MUST** verify all routes have tenant dependency
- ✅ **MUST** test tenant isolation for all endpoints
- ✅ **MUST** handle error cases (missing context, tenant mismatch)
- ✅ **MUST** use tenant config for JWT secrets

### Files Affected

**New Files (from upstream):**
- `app/cabinet/auth/jwt_handler.py` (~100-200 lines)
- `app/cabinet/auth/telegram_auth.py` (~50-100 lines)
- `app/cabinet/dependencies.py` (~20-50 lines)
- `app/cabinet/routes/auth.py` (~100-200 lines)
- `app/cabinet/routes/info.py` (~50-100 lines)
- `app/cabinet/routes/balance.py` (~50-100 lines)
- `app/cabinet/routes/subscription.py` (~50-100 lines)
- `app/cabinet/routes/tickets.py` (~50-100 lines)
- `app/cabinet/routes/admin_*.py` (3 files, ~150-300 lines each)
- `app/cabinet/routes/promo.py` (~50-100 lines)
- `app/cabinet/routes/promocode.py` (~50-100 lines)
- `app/cabinet/routes/referral.py` (~50-100 lines)
- `app/cabinet/routes/branding.py` (~50-100 lines)
- `app/cabinet/routes/contests.py` (~50-100 lines)
- `app/cabinet/routes/notifications.py` (~50-100 lines)
- `app/cabinet/routes/polls.py` (~50-100 lines)
- `tests/integration/test_cabinet_tenant_isolation.py` (NEW, ~200 lines)

**Modified Files:**
- All Cabinet route files (add tenant dependency, error handling)
- `app/cabinet/auth/jwt_handler.py` (add bot_id to JWT)
- `app/cabinet/auth/telegram_auth.py` (add bot_id to user lookup)
- `app/cabinet/dependencies.py` (add tenant dependency)
- `app/webapi/app.py` (register Cabinet router)

**Total Lines Affected:** ~2000-3000 lines

### Implementation Details

**JWT Token Structure:**
```json
{
  "sub": "user_id",
  "telegram_id": 123456789,
  "bot_id": 1  // NEW - required for tenant isolation
}
```

**Error Handling Pattern:**
```python
# Missing tenant context
if bot_id is None:
    raise HTTPException(401, "Tenant context missing")

# Tenant mismatch
if user.bot_id != bot_id:
    raise HTTPException(403, "Tenant mismatch")
```

**Route Pattern:**
```python
@router.get("/endpoint")
async def endpoint(
    ...,
    bot_id: int = Depends(get_current_tenant)  # Required
):
    # All queries include bot_id filter
    # All service calls pass bot_id
```

### Testing Strategy
1. **Unit Tests:** JWT creation, token validation, auth functions
2. **Integration Tests:** All routes with tenant isolation
3. **Security Tests:** Tenant mismatch, missing context, invalid tokens
4. **Performance Tests:** Route response times with tenant filtering

---

## Results & Issues

### Completion Status
- [ ] Cabinet files copied from upstream
- [ ] JWT handler refactored
- [ ] Telegram auth refactored
- [ ] All routes refactored (17 files)
- [ ] Router registered
- [ ] Integration tests created
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

### Route Refactoring Status
- **Total Routes:** [Number]
- **Routes Refactored:** [Number]
- **Routes with Tenant Dependency:** [Number]
- **Routes with Error Handling:** [Number]

### Test Results
- **Unit Tests:** [X/Y] passing
- **Integration Tests:** [X/Y] passing
- **Security Tests:** [X/Y] passing
- **Coverage:** [XX]%

### Tenant Isolation Verification
- **Routes Tested:** [Number]
- **Isolation Verified:** ✅ Yes / ❌ No
- **Violations Found:** [Number] (list if any)

### Next Steps
- [ ] Proceed to Story MERGE-3 (CRUD, Services, Handlers)
- [ ] Or fix issues first

---

**Story Status:** ⏳ In Progress / ✅ Complete / ❌ Blocked  
**Completed At:** [Date/Time]  
**Completed By:** [Developer Name]
