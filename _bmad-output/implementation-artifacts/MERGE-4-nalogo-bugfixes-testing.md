# Story MERGE-4: Nalogo Integration, Bug Fixes & Testing

**Status:** ready-for-dev  
**Epic:** MERGE-UPSTREAM-MAIN (Temporary)  
**Priority:** 🟡 HIGH  
**Estimated Time:** 47 hours  
**Dependencies:** MERGE-3

---

## Story

As a **developer**,  
I want to **integrate Nalogo with tenant config, apply bug fixes, and complete comprehensive testing**,  
so that **all features work correctly with tenant isolation and codebase is ready for production**.

---

## Acceptance Criteria

1. ✅ **AC 4.1:** Given a bot_id, when initializing NalogoService, then it uses config from `bot_configurations` table
2. ✅ **AC 4.2:** Given two different bot_ids, when creating receipts, then they use different Nalogo credentials (tenant isolation)
3. ✅ **AC 4.3:** Given all unit tests, when running, then all tests pass with >80% coverage
4. ✅ **AC 4.4:** Given integration tests, when running, then all tests pass with tenant isolation verified
5. ✅ **AC 4.5:** Given manual testing, when complete, then all features work correctly
6. ✅ **AC 4.6:** Given database schema, when validating, then all required columns and indexes exist

---

## Tasks / Subtasks

### Phase 6: Nalogo Integration (9 hours)

#### Task 6.1: Refactor Nalogo Service for Tenant-Aware Config
- [ ] **Action:** Make Nalogo service use tenant config
  - **Files:**
    - `app/services/nalogo_service.py` (MODIFY, ~100-200 lines)
  - **Changes:**
    ```python
    # BEFORE:
    class NalogoService:
        def __init__(self):
            self.inn = settings.NALOGO_INN  # Global
            self.password = settings.NALOGO_PASSWORD  # Global
    
    # AFTER:
    class NalogoService:
        def __init__(self, bot_id: int, db: AsyncSession):  # ADD parameters
            self.bot_id = bot_id
            self.db = db
            # Load from tenant config:
            config = await get_nalogo_config(db, bot_id)
            if not config:
                raise ValueError(f"Nalogo config not found for bot_id {bot_id}")
            self.inn = config["inn"]
            self.password = config["password"]
    ```
  - **Lines Affected:** Class definition, all method signatures
  - **Verification:** Service uses tenant config, isolation works

#### Task 6.1.1: Migrate Existing Nalogo Config
- [ ] **Action:** Migrate global Nalogo config to tenant config
  - **Files:**
    - `scripts/migrate_nalogo_config.py` (NEW, ~100 lines)
    - `app/database/crud/bot_configuration.py` (uses existing functions)
  - **Script Logic:**
    ```python
    # Read existing env vars
    inn = os.getenv("NALOGO_INN")
    password = os.getenv("NALOGO_PASSWORD")
    
    # For each active bot:
    for bot in active_bots:
        await set_configuration(
            db, bot.id, "nalogo.credentials",
            {"inn": inn, "password": password}
        )
    ```
  - **Verification:** Config migrated, all bots have config

#### Task 6.2: Integrate Nalogo with Payment Service
- [ ] **Action:** Update payment service to use tenant-aware Nalogo
  - **Files:**
    - `app/services/payment_service.py` (MODIFY, ~50-100 lines)
  - **Changes:**
    ```python
    # Update NalogoService initialization:
    nalogo_service = NalogoService(bot_id=bot_id, db=db)  # ADD bot_id
    ```
  - **Verification:** Payment service uses tenant-aware Nalogo

### Phase 7: Bug Fixes (10 hours)

#### Task 7.1: Cherry-pick Promocode Bug Fixes
- [ ] **Action:** Apply promocode fixes with tenant compatibility
  - **Files:**
    - `app/database/crud/promocode.py` (MODIFY)
    - `app/handlers/admin/promocodes.py` (MODIFY)
  - **Commits to Cherry-pick:**
    - `2156f630` - first_purchase_only
    - `5a5a18d8` - pagination
    - `9cd5d8e0` - general fixes
  - **Commands:**
    ```bash
    git cherry-pick 2156f630
    git cherry-pick 5a5a18d8
    git cherry-pick 9cd5d8e0
    ```
  - **Verification:** Fixes applied, bot_id filters verified, tests pass

#### Task 7.2: Cherry-pick Subscription Bug Fixes
- [ ] **Action:** Apply subscription fixes with tenant compatibility
  - **Files:**
    - `app/services/subscription_service.py` (MODIFY)
    - `app/handlers/subscription/*.py` (MODIFY)
  - **Commits to Cherry-pick:**
    - `4bebff5c` - auto-activation
    - `e15728e3` - simple purchase
    - `56cc8bac` - purchase fix
    - `bce05d4b` - traffic reset
  - **Verification:** Fixes applied, tenant context verified, tests pass

#### Task 7.3: Cherry-pick Payment Bug Fixes (Iranian Only)
- [ ] **Action:** Apply payment fixes (only Iranian gateways)
  - **Files:**
    - `app/services/payment_service.py` (MODIFY)
    - `app/services/user_cart_service.py` (MODIFY)
  - **Commits to Cherry-pick:**
    - `bc19ec32` - persistent cart
    - `5aa9b6dd` - notification fix
    - `dd860146` - topup buttons
    - **DO NOT cherry-pick:** `9bd1944b` (platega - Russian gateway)
  - **Verification:** Fixes applied, tenant context verified, tests pass

#### Task 7.4: Cherry-pick Other Bug Fixes
- [ ] **Action:** Apply remaining bug fixes
  - **Files:** Various handler and service files
  - **Commits:** Admin fixes, RemnaWave sync fixes, blacklist fixes
  - **Verification:** Fixes applied, tenant context verified, tests pass

### Phase 8: Testing & Validation (25 hours)

#### Task 8.1: Run All Unit Tests
- [ ] **Action:** Execute and fix all unit tests
  - **Files:** `tests/**/*.py`
  - **Commands:**
    ```bash
    pytest tests/ -v --cov=app --cov-report=html
    ```
  - **Targets:**
    - All tests pass
    - >80% coverage for new code
  - **Verification:** Coverage report generated, all tests pass

#### Task 8.2: Run Integration Tests
- [ ] **Action:** Execute integration tests for tenant isolation
  - **Files:** `tests/integration/*.py`
  - **Commands:**
    ```bash
    pytest tests/integration/ -v
    ```
  - **Test Areas:**
    - Tenant isolation for all endpoints
    - Cabinet endpoints
    - Nalogo integration
    - JWT token validation with bot_id
    - Tenant mismatch scenarios
  - **Verification:** All integration tests pass

#### Task 8.2.1: Cabinet Integration Test Scenarios
- [ ] **Action:** Create comprehensive Cabinet integration tests
  - **Files:**
    - `tests/integration/test_cabinet_tenant_isolation.py` (NEW, ~200 lines)
  - **Test Cases:**
    - Tenant isolation (user A cannot access user B's data)
    - JWT validation with bot_id
    - Email verification tenant-aware
    - Password reset tenant-aware
    - All Cabinet routes with tenant context
  - **Verification:** All Cabinet tests pass

#### Task 8.2.2: Nalogo Integration Test Scenarios
- [ ] **Action:** Create comprehensive Nalogo integration tests
  - **Files:**
    - `tests/integration/test_nalogo_tenant_isolation.py` (NEW, ~150 lines)
  - **Test Cases:**
    - Tenant isolation (receipt for tenant A, tenant B cannot access)
    - Config isolation (different tenants use different credentials)
    - Error handling (missing config raises error)
    - Receipt creation (associated with correct tenant)
  - **Verification:** All Nalogo tests pass

#### Task 8.3: Manual Testing Checklist
- [ ] **Action:** Perform manual testing for all features
  - **Checklist:**
    - [ ] Cabinet authentication
    - [ ] Cabinet routes tenant-aware
    - [ ] Promocodes with first_purchase_only
    - [ ] Subscription fixes (auto-activation, traffic reset)
    - [ ] Persistent cart tenant-aware
    - [ ] Admin features
    - [ ] Data leak prevention (verify no cross-tenant access)
  - **Verification:** All manual tests pass

#### Task 8.4: Database Schema Validation
- [ ] **Action:** Validate database schema changes
  - **SQL Queries:**
    ```sql
    -- Verify bot_id exists in all tables
    SELECT table_name 
    FROM information_schema.columns 
    WHERE column_name = 'bot_id';
    
    -- Verify Cabinet columns
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'users' 
      AND column_name LIKE 'cabinet%';
    
    -- Verify first_purchase_only
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'promocodes' 
      AND column_name = 'first_purchase_only';
    ```
  - **Verification:** All required columns and indexes exist

#### Task 8.5: Code Quality Check
- [ ] **Action:** Run code quality checks
  - **Commands:**
    ```bash
    ruff check app/
    python -m py_compile app/**/*.py
    ```
  - **Verification:** No code quality issues

---

## Dev Notes

### Critical Requirements
- ✅ **MUST** test tenant isolation for all features
- ✅ **MUST** verify no data leaks between tenants
- ✅ **MUST** achieve >80% test coverage
- ✅ **MUST** fix all failing tests

### Files Affected

**New Files:**
- `scripts/migrate_nalogo_config.py` (~100 lines)
- `tests/integration/test_cabinet_tenant_isolation.py` (~200 lines)
- `tests/integration/test_nalogo_tenant_isolation.py` (~150 lines)

**Modified Files:**
- `app/services/nalogo_service.py` (refactor for tenant config)
- `app/services/payment_service.py` (integrate tenant-aware Nalogo)
- Various files from cherry-picked bug fixes

### Implementation Details

**Nalogo Config Migration:**
- Read existing env vars as default
- Create config for each active bot
- Feature flag for gradual rollout (optional)

**Testing Strategy:**
- Unit tests for each component
- Integration tests for tenant isolation
- Manual testing for user flows
- Performance testing for queries

---

## Results & Issues

### Completion Status
- [ ] Phase 6 complete (Nalogo Integration)
- [ ] Phase 7 complete (Bug Fixes)
- [ ] Phase 8 complete (Testing & Validation)
- [ ] All tests passing
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

### Test Results
- **Unit Tests:** [X/Y] passing ([XX]% coverage)
- **Integration Tests:** [X/Y] passing
- **Cabinet Tests:** [X/Y] passing
- **Nalogo Tests:** [X/Y] passing
- **Manual Tests:** [X/Y] passing

### Tenant Isolation Verification
- **Endpoints Tested:** [Number]
- **Isolation Verified:** ✅ Yes / ❌ No
- **Data Leaks Found:** [Number] (list if any)

### Code Quality
- **Ruff Issues:** [Number] (all fixed)
- **Compilation Errors:** [Number] (all fixed)
- **Coverage:** [XX]%

### Next Steps
- [ ] Proceed to Story MERGE-5 (Documentation & Cleanup)
- [ ] Or fix issues first

---

**Story Status:** ⏳ In Progress / ✅ Complete / ❌ Blocked  
**Completed At:** [Date/Time]  
**Completed By:** [Developer Name]
