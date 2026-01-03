# Story MERGE-1: Setup, Validation & Core Infrastructure

**Status:** ready-for-dev  
**Epic:** MERGE-UPSTREAM-MAIN (Temporary)  
**Priority:** 🔴 CRITICAL  
**Estimated Time:** 17 hours  
**Dependencies:** None

---

## Story

As a **developer**,  
I want to **setup merge environment, create validation tools, and refactor core infrastructure for tenant-aware config**,  
so that **I have a solid foundation for merging upstream changes with tenant isolation**.

---

## Acceptance Criteria

1. ✅ **AC 1.1:** Given merge branch, when setup is complete, then backup branch and merge branch are created with database backup
2. ✅ **AC 1.2:** Given codebase, when validation scripts run, then they detect all tenant isolation violations
3. ✅ **AC 1.3:** Given bot_id, when calling `get_cabinet_jwt_secret(db, bot_id)`, then it returns JWT secret from tenant config
4. ✅ **AC 1.4:** Given bot_id, when calling `get_nalogo_config(db, bot_id)`, then it returns INN and password from tenant config
5. ✅ **AC 1.5:** Given User model, when checking schema, then all 7 Cabinet columns exist with correct types
6. ✅ **AC 1.6:** Given Promocode model, when checking schema, then `first_purchase_only` field exists

---

## Tasks / Subtasks

### Phase 0: Setup & Backup

#### Task 0.1: Create Backup and Merge Branch
- [ ] **Action:** Create backup branch and merge branch
  - **Files:** N/A (git operations)
  - **Commands:**
    ```bash
    git branch backup-before-upstream-merge-$(date +%Y%m%d)
    pg_dump -U postgres remnabot > backup_db_$(date +%Y%m%d).sql
    git checkout -b merge/upstream-main-$(date +%Y%m%d)
    git fetch upstream main
    ```
  - **Verification:** Branches created, backup file exists

#### Task 0.2: Create Validation Scripts
- [ ] **Action:** Create 3 validation scripts for tenant compatibility
  - **Files:**
    - `scripts/validate_bot_id_queries.py` (NEW, ~150 lines)
    - `scripts/validate_tenant_context.py` (NEW, ~120 lines)
    - `scripts/validate_redis_keys.py` (NEW, ~100 lines)
    - `scripts/__init__.py` (NEW, ~5 lines)
  - **Functionality:**
    - **validate_bot_id_queries.py:** Check all `select()` queries have `.where(Model.bot_id == bot_id)` OR use RLS via `get_tenant_session()` OR marked as `# GLOBAL_QUERY`
    - **validate_tenant_context.py:** Verify FastAPI routes have `Depends(get_current_tenant)` parameter
    - **validate_redis_keys.py:** Check Redis keys include `bot_id` prefix: `f"{bot_id}:{key}"`
  - **Verification:** Scripts run without errors, detect violations correctly

### Phase 1: Core Infrastructure

#### Task 1.1: Refactor Config for Tenant-Aware Cabinet and Nalogo
- [ ] **Action:** Convert global env config to tenant config
  - **Files:**
    - `app/config.py` (MODIFY, lines 243-244)
    - `app/database/crud/bot_configuration.py` (MODIFY, add lines 167-200)
    - `tests/database/crud/test_bot_configuration.py` (NEW/UPDATE, ~150 lines)
  - **Changes:**
    ```python
    # app/config.py - REMOVE lines 243-244:
    # NALOGO_INN: Optional[str] = None
    # NALOGO_PASSWORD: Optional[str] = None
    
    # app/database/crud/bot_configuration.py - ADD after line 166:
    async def get_cabinet_jwt_secret(db: AsyncSession, bot_id: int) -> Optional[str]:
        """Get Cabinet JWT secret for a tenant."""
        config = await get_config_value(db, bot_id, "cabinet.jwt_secret")
        if config and isinstance(config, dict):
            return config.get("secret")
        return None
    
    async def get_nalogo_config(db: AsyncSession, bot_id: int) -> Dict[str, str]:
        """Get Nalogo configuration for a tenant."""
        config = await get_config_value(db, bot_id, "nalogo.credentials")
        if config and isinstance(config, dict):
            return {
                "inn": config.get("inn", ""),
                "password": config.get("password", ""),
            }
        return {}
    ```
  - **Verification:** Functions work, tests pass, tenant isolation verified

#### Task 1.2: Add Cabinet Columns to User Model
- [ ] **Action:** Add 7 Cabinet authentication columns to User model
  - **Files:**
    - `app/database/models.py` (MODIFY, after User model definition, ~line 850)
    - `migrations/versions/xxx_add_cabinet_columns.py` (NEW, ~100 lines)
  - **Columns to Add:**
    ```python
    # Add to User model (app/database/models.py, after line ~849):
    cabinet_email = Column(String(255), nullable=True)
    cabinet_email_verified = Column(Boolean, default=False, nullable=False)
    cabinet_password_hash = Column(String(255), nullable=True)
    cabinet_email_verification_token = Column(String(255), nullable=True)
    cabinet_email_verification_expires_at = Column(DateTime, nullable=True)
    cabinet_password_reset_token = Column(String(255), nullable=True)
    cabinet_password_reset_expires_at = Column(DateTime, nullable=True)
    ```
  - **Migration Strategy:**
    - All columns nullable=True (backward compatible)
    - Add index: `idx_users_cabinet_email` on `cabinet_email`
    - Default existing users to NULL
  - **Verification:** Migration runs successfully, rollback works, columns exist

#### Task 1.3: Add Promocode first_purchase_only Field
- [ ] **Action:** Add `first_purchase_only` field to Promocode model
  - **Files:**
    - `app/database/models.py` (MODIFY, find Promocode model, ~line 1100+)
    - `migrations/versions/xxx_add_promocode_first_purchase.py` (NEW, ~50 lines)
  - **Changes:**
    ```python
    # Add to Promocode model:
    first_purchase_only = Column(Boolean, default=False, nullable=False)
    ```
  - **Migration Strategy:**
    - Default existing promocodes to `False` (backward compatible)
    - No data migration needed
  - **Verification:** Field added, migration works, default value correct

---

## Dev Notes

### Critical Requirements
- ✅ **MUST** create backup before any changes
- ✅ **MUST** verify validation scripts work correctly
- ✅ **MUST** maintain backward compatibility
- ✅ **MUST** test tenant isolation

### Files Affected

**New Files:**
- `scripts/validate_bot_id_queries.py` (~150 lines)
- `scripts/validate_tenant_context.py` (~120 lines)
- `scripts/validate_redis_keys.py` (~100 lines)
- `scripts/__init__.py` (~5 lines)
- `migrations/versions/xxx_add_cabinet_columns.py` (~100 lines)
- `migrations/versions/xxx_add_promocode_first_purchase.py` (~50 lines)
- `tests/database/crud/test_bot_configuration.py` (~150 lines, NEW or UPDATE)

**Modified Files:**
- `app/config.py` (REMOVE lines 243-244: NALOGO_INN, NALOGO_PASSWORD)
- `app/database/crud/bot_configuration.py` (ADD lines 167-200: helper functions)
- `app/database/models.py` (ADD Cabinet columns after line ~849, ADD first_purchase_only to Promocode)

### Implementation Details

**Config Key Format:**
- Cabinet JWT: `"cabinet.jwt_secret"` → `{"secret": "..."}`
- Nalogo: `"nalogo.credentials"` → `{"inn": "...", "password": "..."}`

**Migration Safety:**
- All Cabinet columns nullable (no data loss)
- Default values for existing data
- Reversible migrations
- Test rollback procedure

**Validation Scripts:**
- Exit code 0 = clean, 1 = violations found
- Output: `file:line: violation description`
- Can be integrated into CI/CD

### Testing Strategy
1. **Unit Tests:** Helper functions, model fields
2. **Integration Tests:** Database migrations, tenant isolation
3. **Validation Tests:** Scripts detect violations correctly
4. **Rollback Tests:** Migrations can be reversed

---

## Results & Issues

### Completion Status
- [ ] Phase 0 complete (Setup & Backup)
- [ ] Phase 1 complete (Core Infrastructure)
- [ ] All validation scripts working
- [ ] All migrations tested
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

### Validation Results
- **Queries Checked:** [Number]
- **Violations Found:** [Number] (list files)
- **Routes Checked:** [Number]
- **Redis Keys Checked:** [Number]

### Migration Results
- **Cabinet Columns Migration:** ✅ Success / ❌ Failed
- **Promocode Migration:** ✅ Success / ❌ Failed
- **Rollback Tested:** ✅ Yes / ❌ No

### Test Results
- **Unit Tests:** [X/Y] passing
- **Integration Tests:** [X/Y] passing
- **Coverage:** [XX]%

### Next Steps
- [ ] Proceed to Story MERGE-2 (Cabinet Module)
- [ ] Or fix issues first

---

**Story Status:** ⏳ In Progress / ✅ Complete / ❌ Blocked  
**Completed At:** [Date/Time]  
**Completed By:** [Developer Name]
