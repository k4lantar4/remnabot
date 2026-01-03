---
title: 'Merge Upstream Main - Implementation Tech Spec'
slug: 'merge-upstream-main-implementation'
created: '2026-01-03'
status: 'ready-for-dev'
code_review_completed: '2026-01-03'
code_review_issues_fixed: 16
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3.13+', 'FastAPI 0.115.6', 'SQLAlchemy 2.0.43', 'PostgreSQL 15+', 'Redis 5.0.1', 'aiogram 3.22.0', 'Pydantic 2.11.9', 'Alembic 1.16.5', 'structlog 23.2.0']
files_to_modify: ['app/config.py', 'app/database/models.py', 'app/database/crud/*.py', 'app/services/*.py', 'app/handlers/*.py', 'app/webapi/routes/*.py', 'app/services/nalogo_service.py', 'app/cabinet/**/*.py (NEW)', 'migrations/**/*.py']
code_patterns: ['multi-tenant', 'tenant-aware queries with bot_id parameter', 'RLS policies', 'JWT with bot_id claim', 'tenant-prefixed cache keys', 'bot_configurations table for per-tenant config', 'get_tenant_session() for DB operations', 'Depends(get_current_tenant) for FastAPI routes', 'CRUD functions with bot_id: Optional[int] parameter']
test_patterns: ['pytest with asyncio', 'tenant fixtures (test_bots)', 'RLS integration tests', 'tenant isolation verification', 'conftest.py with test database setup']
---

# Tech-Spec: Merge Upstream Main - Implementation Tech Spec

**Created:** 2026-01-03

## Overview

### Problem Statement

نیاز به مرج کردن 527 فایل تغییر یافته از `upstream/main` به برنچ فعلی `resolve-adversarial-findings` با حفظ کامل معماری multi-tenant. Upstream دارای single-tenant architecture است در حالی که برنچ فعلی multi-tenant با RLS policies و tenant isolation کامل است. چالش اصلی: تبدیل تغییرات upstream به tenant-aware بدون شکستن isolation و اطمینان از سازگاری با PRD و Architecture documents.

### Solution

تبدیل راهنمای merge موجود (`merge-implementation-guide.md`) به implementation-ready technical stories با group کردن task‌های مرتبط. هر story شامل:
- File paths مشخص
- Actions دقیق (add/modify/refactor)
- Dependencies بین stories
- Acceptance criteria با Given/When/Then
- Test requirements
- Tenant compatibility checks

Stories به ترتیب dependency اجرا می‌شوند: Core Infrastructure → Cabinet Module → CRUD → Services → Handlers → Nalogo → Bug Fixes → Testing → Documentation.

### Scope

**In Scope:**
- تمام 9 phase از merge guide (Phase 0-9)
- Cabinet module (31 فایل) - با tenant-aware refactoring
- Nalogo integration (15 فایل) - با tenant config
- Modem support
- Promocode fixes (first_purchase_only, pagination)
- Subscription fixes (auto-activation, traffic reset)
- Payment fixes (فقط ایرانی - ZarinPal, Card-to-Card)
- Admin و User Management fixes
- CRUD operations merge (50+ فایل)
- Services merge (60+ فایل)
- Handlers merge (80+ فایل)
- Testing و validation
- Documentation updates

**Out of Scope:**
- Platega fixes (درگاه روسی - مخالف PRD)
- Refactoring معماری که با multi-tenant در تضاد است
- حذف فایل‌های `_bmad-output/` (باید restore شوند)
- تغییرات که با PRD و Architecture در تضاد هستند

## Context for Development

### Codebase Patterns

**Multi-Tenant Architecture:**
- Tenant context از `app/core/tenant_context.py` با `get_current_tenant()` و `require_current_tenant()`
- Tenant middleware در `app/middleware/tenant_middleware.py` برای FastAPI routes
- Database queries باید `bot_id` filter داشته باشند (pattern: `bot_id: Optional[int] = None` در CRUD functions)
- استفاده از `get_tenant_session(bot_id)` برای database operations با RLS context
- RLS policies در PostgreSQL برای automatic tenant filtering (session variable: `app.current_tenant`)
- Redis keys باید tenant prefix داشته باشند: `{bot_id}:{key}` (via `cache_key()` utility)

**CRUD Operations Pattern:**
- Functions در `app/database/crud/` با `bot_id: Optional[int] = None` parameter
- Example: `get_users_list(db, offset=0, limit=50, bot_id: Optional[int] = None)`
- Query filtering: `if bot_id is not None: query = query.where(Model.bot_id == bot_id)`
- BotConfiguration CRUD در `app/database/crud/bot_configuration.py` برای per-tenant config

**JWT Tokens:**
- تمام JWT tokens باید `bot_id` claim داشته باشند
- Token validation باید bot_id را check کند
- Pattern: `create_access_token(user_id, telegram_id, bot_id)`
- Cabinet JWT handler باید tenant-aware باشد (نیاز به refactoring)

**API Routes:**
- FastAPI routes در `app/webapi/routes/` با `Depends(get_current_tenant)` برای tenant dependency
- Pattern: `bot_id: int = Depends(get_current_tenant)` در route functions
- Webhook routing: `/webhook/{bot_token}` برای Telegram (در `app/webserver/telegram.py`)
- Cabinet routes: `/cabinet/*` با tenant context (نیاز به ایجاد)

**Configuration:**
- Per-tenant config در `bot_configurations` table (BotConfiguration model)
- CRUD functions: `get_config_value(db, bot_id, config_key)`, `set_configuration(db, bot_id, config_key, config_value)`
- Pattern: `get_bot_config(db, bot_id, "cabinet.jwt_secret")` برای Cabinet settings
- Pattern: `get_bot_config(db, bot_id, "nalogo.inn")` برای Nalogo settings
- نه global env variables (Settings class در `app/config.py` فقط برای backward compatibility)

**Services Pattern:**
- Services در `app/services/` با tenant context
- Example: `TenantFeatureService` با `bot_id` parameter
- PaymentService و SubscriptionService با tenant-aware operations
- NalogoService موجود است اما global config دارد (نیاز به tenant-aware refactoring)

**Code Style:**
- `snake_case` برای files, functions, variables
- `PascalCase` برای classes
- Persian localization با `Texts.get("key")` (در `app/localization/`)
- Structured logging با `bot_id` در context (structlog)
- Russian comments باید حذف شوند (طبق PRD)

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `_bmad-output/merge-implementation-guide.md` | راهنمای کامل merge با تمام phases و tasks |
| `_bmad-output/project-context.md` | قوانین و patterns برای multi-tenant implementation |
| `_bmad-output/architecture.md` | معماری کامل multi-tenant |
| `_bmad-output/prd.md` | Product requirements و constraints |
| `app/core/tenant_context.py` | Tenant context management (get_current_tenant, require_current_tenant, get_tenant_session) |
| `app/middleware/tenant_middleware.py` | Tenant middleware برای FastAPI (extracts bot_token from URL) |
| `app/database/models.py` | Database models (نیاز به Cabinet columns: cabinet_email, cabinet_password_hash, etc.) |
| `app/database/crud/bot_configuration.py` | BotConfiguration CRUD (get_config_value, set_configuration) |
| `app/database/crud/user.py` | User CRUD pattern (get_users_list با bot_id parameter) |
| `app/database/crud/subscription.py` | Subscription CRUD pattern (get_subscription_by_user_id با bot_id) |
| `app/config.py` | Configuration (Settings class - نیاز به tenant-aware refactoring برای Cabinet/Nalogo) |
| `app/services/nalogo_service.py` | Nalogo service (موجود اما global config - نیاز به tenant-aware) |
| `app/webapi/dependencies.py` | FastAPI dependencies (require_api_token - نیاز به tenant dependency) |
| `app/webapi/routes/*.py` | API routes pattern (نیاز به tenant dependency) |
| `tests/integration/test_rls_policies.py` | RLS testing pattern (tenant isolation tests) |
| `tests/conftest.py` | Test fixtures pattern |
| `app/cabinet/**/*.py` | Cabinet module (NEW - باید از upstream اضافه شود) |

### Technical Decisions

1. **Incremental Merge**: مرج به صورت phase-by-phase با testing بعد از هر phase
2. **Tenant-First**: تمام تغییرات باید tenant-aware باشند - هیچ global state
3. **Test-Driven**: هر story باید tests داشته باشد قبل از merge
4. **Validation Scripts**: استفاده از scripts برای بررسی bot_id در queries و tenant context
5. **Backward Compatibility**: برای transition period، backward compatibility حفظ شود
6. **Group Related Tasks**: Task‌های مرتبط در یک story (مثلاً تمام Cabinet routes)
7. **Dependency Tracking**: Dependencies بین stories مشخص شود

**Investigation Findings:**

- **Cabinet Module**: وجود ندارد - باید از upstream اضافه شود (31 فایل)
  - Structure: `app/cabinet/auth/`, `app/cabinet/routes/`, `app/cabinet/dependencies.py`
  - نیاز به tenant-aware refactoring برای تمام routes و auth handlers

- **Cabinet Columns**: در `app/database/models.py` نیست
  - نیاز: `cabinet_email`, `cabinet_email_verified`, `cabinet_password_hash`, `cabinet_email_verification_token`, `cabinet_email_verification_expires_at`, `cabinet_password_reset_token`, `cabinet_password_reset_expires_at`

- **Nalogo Service**: موجود است (`app/services/nalogo_service.py`) اما global config دارد
  - نیاز به refactoring برای استفاده از `bot_configurations` table
  - Pattern: `get_config_value(db, bot_id, "nalogo.inn")`, `get_config_value(db, bot_id, "nalogo.password")`

- **CRUD Pattern**: استفاده از `bot_id: Optional[int] = None` در functions
  - Example: `get_users_list(db, offset=0, limit=50, bot_id: Optional[int] = None)`
  - Query filtering: `if bot_id is not None: query = query.where(Model.bot_id == bot_id)`

- **Test Pattern**: استفاده از tenant fixtures در `tests/conftest.py`
  - RLS integration tests در `tests/integration/test_rls_policies.py`
  - Pattern: `test_bots` fixture برای ایجاد multiple tenants

- **Config Pattern**: استفاده از `BotConfiguration` model و CRUD functions
  - `get_config_value(db, bot_id, config_key)` برای خواندن
  - `set_configuration(db, bot_id, config_key, config_value)` برای نوشتن

## Implementation Plan

### Tasks

#### Story 0.1: Setup and Backup
- [ ] **Task:** Create backup branch and merge branch
  - **Files:** N/A (git operations)
  - **Actions:**
    1. Create backup branch: `git branch backup-before-upstream-merge-$(date +%Y%m%d)`
    2. Create SQL dump: `pg_dump -U postgres remnabot > backup_db_$(date +%Y%m%d).sql`
    3. Create merge branch: `git checkout -b merge/upstream-main-$(date +%Y%m%d)`
    4. Fetch upstream: `git fetch upstream main`
    5. Document rollback procedure (see Rollback Strategy section below)
  - **Dependencies:** None
  - **Estimated Time:** 1 hour
  - **Notes:** Critical first step - must complete before any merge work

#### Story 0.1.1: Rollback Procedure
- [ ] **Task:** Document and test rollback procedure
  - **Files:** `docs/rollback-procedure.md` (NEW)
  - **Actions:**
    1. Document rollback steps for each phase
    2. Test rollback in staging environment
    3. Create rollback scripts for database migrations
    4. Document git rollback commands per phase
  - **Dependencies:** Story 0.1
  - **Estimated Time:** 2 hours
  - **Notes:** Safety net for failed merges

#### Story 0.2: Create Validation Scripts
- [ ] **Task:** Create validation scripts for tenant compatibility
  - **Files:** `scripts/validate_bot_id_queries.py`, `scripts/validate_tenant_context.py`, `scripts/validate_redis_keys.py`
  - **Actions:**
    1. **validate_bot_id_queries.py:**
       - Check all `select()` queries have `.where(Model.bot_id == bot_id)` OR
       - Query uses RLS via `get_tenant_session()` OR
       - Query is explicitly marked as global (admin-only with comment `# GLOBAL_QUERY`)
       - Pattern: `rg -A 5 "select\(.*\)" app/ | grep -v "bot_id\|get_tenant_session\|# GLOBAL_QUERY"`
       - Output: List of files:line with violations
       - Exit code: 0 if clean, 1 if violations found
    2. **validate_tenant_context.py:**
       - Verify `get_current_tenant()` or `require_current_tenant()` is called in route handlers
       - Check FastAPI routes have `Depends(get_current_tenant)` parameter
       - Pattern: Check `@router.get/post/put/delete` decorators
       - Output: List of routes missing tenant dependency
    3. **validate_redis_keys.py:**
       - Check Redis key patterns include `bot_id` prefix
       - Pattern: `redis.get/set/delete` calls should use `f"{bot_id}:{key}"` format
       - Output: List of Redis operations without tenant prefix
    4. Integrate with CI/CD: Fail build if violations found (configurable)
  - **Dependencies:** None
  - **Estimated Time:** 4 hours
  - **Notes:** These scripts will be used throughout merge process

#### Story 1.1: Refactor Config for Tenant-Aware Cabinet and Nalogo
- [ ] **Task:** Convert Cabinet and Nalogo config from global env to tenant config
  - **Files:** `app/config.py`, `app/database/crud/bot_configuration.py`
  - **Actions:**
    1. Remove `CABINET_JWT_SECRET`, `NALOGO_INN`, `NALOGO_PASSWORD` from Settings class
    2. Create helper functions using consistent pattern:
       - `get_cabinet_jwt_secret(db: AsyncSession, bot_id: int) -> Optional[str]`
       - `get_nalogo_config(db: AsyncSession, bot_id: int) -> Dict[str, str]`
       - Both use `get_config_value(db, bot_id, "cabinet.jwt_secret")` pattern
    3. Update config accessors to use `bot_configurations` table
    4. Add backward compatibility warning (deprecated) for direct Settings access
    5. Add tests for tenant config isolation
  - **Dependencies:** None
  - **Estimated Time:** 4 hours
  - **Notes:** Critical for Cabinet and Nalogo modules

#### Story 1.2: Add Cabinet Columns to User Model
- [ ] **Task:** Add Cabinet authentication columns to User model
  - **Files:** `app/database/models.py`, `migrations/versions/xxx_add_cabinet_columns.py`
  - **Actions:**
    1. Add columns to User model:
       - `cabinet_email: String(255), nullable=True`
       - `cabinet_email_verified: Boolean, default=False, nullable=False`
       - `cabinet_password_hash: String(255), nullable=True`
       - `cabinet_email_verification_token: String(255), nullable=True`
       - `cabinet_email_verification_expires_at: DateTime, nullable=True`
       - `cabinet_password_reset_token: String(255), nullable=True`
       - `cabinet_password_reset_expires_at: DateTime, nullable=True`
    2. Create Alembic migration script with migration strategy:
       - All Cabinet columns default to NULL for existing users (backward compatible)
       - No NOT NULL constraints initially (add in separate migration after data migration)
       - Add indexes: `idx_users_cabinet_email` on `cabinet_email`
    3. Verify `bot_id` exists in User model
    4. Test migration rollback procedure
  - **Dependencies:** None
  - **Estimated Time:** 6 hours
  - **Notes:** High risk - requires database migration. See Migration Strategy section.

#### Story 1.3: Add Promocode first_purchase_only Field
- [ ] **Task:** Add `first_purchase_only` field to Promocode model
  - **Files:** `app/database/models.py`, `migrations/versions/xxx_add_promocode_first_purchase.py`
  - **Actions:**
    1. Add `first_purchase_only: Boolean, default=False, nullable=False` to Promocode model
    2. Create Alembic migration script with migration strategy:
       - Default existing promocodes to `False` (backward compatible)
       - No data migration needed (default value handles it)
    3. Verify `bot_id` exists in Promocode model
  - **Dependencies:** None
  - **Estimated Time:** 2 hours
  - **Notes:** Low risk - simple field addition

#### Story 2.1: Add Cabinet Module from Upstream
- [ ] **Task:** Copy Cabinet module files from upstream and prepare for tenant refactoring
  - **Files:** `app/cabinet/auth/jwt_handler.py`, `app/cabinet/auth/telegram_auth.py`, `app/cabinet/dependencies.py`, `app/cabinet/routes/*.py` (exact count TBD from upstream)
  - **Actions:**
    1. Count exact files in upstream: `git ls-tree -r upstream/main --name-only | grep "^app/cabinet/"`
    2. Copy all Cabinet files from upstream/main (preserve structure)
    3. Review structure: `app/cabinet/auth/`, `app/cabinet/routes/`, `app/cabinet/dependencies.py`
    4. Document current single-tenant implementation
    5. Create file inventory: List all Cabinet files with paths
  - **Dependencies:** Story 1.1 (config)
  - **Estimated Time:** 2 hours
  - **Notes:** Cabinet module doesn't exist - must be added from upstream. File count will be verified during implementation.

#### Story 2.2: Refactor Cabinet JWT Handler for Tenant-Aware
- [ ] **Task:** Make Cabinet JWT handler tenant-aware
  - **Files:** `app/cabinet/auth/jwt_handler.py`
  - **Actions:**
    1. Add `bot_id: int` parameter to `create_access_token(user_id, telegram_id, bot_id)`
    2. Add `bot_id: int` parameter to `create_refresh_token(user_id, bot_id)`
    3. Add `bot_id` to JWT payload: `{"sub": str(user_id), "telegram_id": telegram_id, "bot_id": bot_id}`
    4. Update token validation to check `bot_id` claim
    5. Use tenant config: `get_cabinet_jwt_secret(db, bot_id)` instead of global env
    6. Add tests for tenant isolation
  - **Dependencies:** Story 1.1 (config), Story 2.1 (Cabinet module)
  - **Notes:** Critical for tenant isolation

#### Story 2.3: Refactor Cabinet Telegram Auth for Tenant-Aware
- [ ] **Task:** Make Cabinet Telegram auth tenant-aware
  - **Files:** `app/cabinet/auth/telegram_auth.py`
  - **Actions:**
    1. Add `bot_id: int` parameter to `validate_telegram_login_widget()`
    2. Update validation logic to use tenant context
    3. Ensure user lookup includes `bot_id` filter
    4. Add tests for tenant isolation
  - **Dependencies:** Story 2.1 (Cabinet module)
  - **Notes:** Must verify user belongs to correct tenant

#### Story 2.4: Update Cabinet Dependencies for Tenant Injection
- [ ] **Task:** Add tenant dependency to Cabinet dependencies
  - **Files:** `app/cabinet/dependencies.py`
  - **Actions:**
    1. Add `get_current_tenant()` dependency import
    2. Create tenant dependency function: `get_cabinet_tenant() -> int`
    3. Update all dependencies to include tenant context
  - **Dependencies:** Story 1.1 (config), Story 2.1 (Cabinet module)
  - **Notes:** Required for all Cabinet routes

#### Story 2.5: Refactor All Cabinet Routes for Tenant-Aware
- [ ] **Task:** Add tenant dependency to all Cabinet routes
  - **Files:** All files in `app/cabinet/routes/` (exact list from Story 2.1 file inventory)
  - **Actions:**
    1. Add `bot_id: int = Depends(get_current_tenant)` to all route functions
    2. Add error handling for missing tenant context:
       - If `get_current_tenant()` returns None, return 401 with localized error
       - Log security violation: `logger.warning("Cabinet route called without tenant context", path=request.url.path)`
    3. Update all database queries to include `bot_id` filter
    4. Add tenant mismatch validation:
       - If user belongs to different tenant than token's bot_id, return 403 Forbidden
       - Pattern: `if user.bot_id != bot_id: raise HTTPException(403, "Tenant mismatch")`
    5. Update all service calls to pass `bot_id`
    6. Add tests for each route with tenant isolation
  - **Dependencies:** Story 2.4 (dependencies)
  - **Estimated Time:** 12 hours
  - **Notes:** Grouped all routes together - largest story. See Error Handling section for details.

#### Story 2.6: Register Cabinet Routes in WebAPI App
- [ ] **Task:** Register Cabinet router in FastAPI app
  - **Files:** `app/webapi/app.py`
  - **Actions:**
    1. Import Cabinet router
    2. Add router with prefix `/cabinet`
    3. Ensure tenant middleware is applied
    4. Add tests for route registration
  - **Dependencies:** Story 2.5 (Cabinet routes)
  - **Notes:** Final step to expose Cabinet endpoints

#### Story 3.1: Update Promocode CRUD for first_purchase_only and Pagination
- [ ] **Task:** Add first_purchase_only and pagination to Promocode CRUD
  - **Files:** `app/database/crud/promocode.py`
  - **Actions:**
    1. Add `first_purchase_only: bool = False` parameter to `create_promocode()`
    2. Update validation logic for `first_purchase_only`
    3. Add pagination to `get_promocodes_list()`: `offset: int = 0, limit: int = 50`
    4. Ensure all queries have `bot_id` filter
    5. Add tests
  - **Dependencies:** Story 1.3 (Promocode model)
  - **Notes:** Grouped related changes together

#### Story 3.2: Update Subscription CRUD for Traffic Reset and Auto-Activation
- [ ] **Task:** Add traffic reset and auto-activation to Subscription CRUD
  - **Files:** `app/database/crud/subscription.py`
  - **Actions:**
    1. Add traffic reset logic to `renew_subscription()`: reset `traffic_consumed_bytes` to 0
    2. Update `activate_subscription()` for auto-activation logic
    3. Ensure all queries have `bot_id` filter
    4. Add tests
  - **Dependencies:** None
  - **Notes:** Grouped related subscription changes

#### Story 3.3: Update User CRUD for Extended Filters
- [ ] **Task:** Add balance filter and extended filters to User CRUD
  - **Files:** `app/database/crud/user.py`
  - **Actions:**
    1. Add `balance_min: Optional[int] = None`, `balance_max: Optional[int] = None` to `get_users_list()`
    2. Add extended filter parameters
    3. Ensure all queries have `bot_id` filter
    4. Add tests
  - **Dependencies:** None
  - **Notes:** Admin feature enhancement

#### Story 3.4: Merge Remaining CRUD Files (47 files in batches)
- [ ] **Task:** Review and merge remaining CRUD files with tenant compatibility
  - **Files:** `app/database/crud/*.py` (47 files)
  - **Actions:**
    1. For each CRUD file:
       - Verify `bot_id` parameter exists in functions
       - Merge changes from upstream
       - Add `bot_id` filter to queries if missing
       - Verify query performance: Add indexes if needed (`idx_{table}_bot_id`)
       - Add tests
    2. Process in 3 batches (15, 16, 16 files)
    3. After each batch: Run validation scripts and performance tests
  - **Dependencies:** None
  - **Estimated Time:** 16 hours (5 hours per batch + 1 hour validation)
  - **Notes:** Large batch work - systematic review required. See Performance Considerations section.

#### Story 4.1: Update Subscription Service for Purchase Flow and Traffic Reset
- [ ] **Task:** Merge subscription service changes with tenant context
  - **Files:** `app/services/subscription_service.py`
  - **Actions:**
    1. Merge purchase flow changes from upstream
    2. Add traffic reset logic
    3. Ensure tenant context in all operations
    4. Add tests
  - **Dependencies:** Story 3.2 (Subscription CRUD)
  - **Notes:** Grouped related subscription changes

#### Story 4.2: Refactor Cart Service for Tenant-Aware Redis Keys
- [ ] **Task:** Make cart service tenant-aware with prefixed Redis keys
  - **Files:** `app/services/user_cart_service.py`
  - **Actions:**
    1. Add `bot_id: int` parameter to all functions
    2. Update Redis keys: `cart:{bot_id}:{user_id}` instead of `cart:{user_id}`
    3. Use `cache_key()` utility for key generation
    4. Add tests for tenant isolation
  - **Dependencies:** None
  - **Notes:** Critical for data isolation

#### Story 4.3: Merge Payment Service Modular Structure
- [ ] **Task:** Merge payment service modular structure with tenant context
  - **Files:** `app/services/payment_service.py`
  - **Actions:**
    1. Merge modular payment structure from upstream
    2. Ensure tenant context in all payment operations
    3. Add tests
  - **Dependencies:** None
  - **Notes:** Payment service refactoring

#### Story 4.4: Merge Remaining Services (57 files in batches)
- [ ] **Task:** Review and merge remaining services with tenant compatibility
  - **Files:** `app/services/*.py` (57 files)
  - **Actions:**
    1. For each service:
       - Verify tenant context usage
       - Merge changes from upstream
       - Add `bot_id` parameter if needed
       - Optimize tenant config lookups (cache if frequently accessed)
       - Add tests
    2. Process in 3 batches (20, 20, 17 files)
    3. After each batch: Run validation scripts and performance tests
  - **Dependencies:** Story 3.4 (CRUD)
  - **Estimated Time:** 18 hours (6 hours per batch)
  - **Notes:** Large batch work. See Performance Considerations section.

#### Story 5.1: Merge Subscription Handlers with Modem Support
- [ ] **Task:** Merge subscription handlers including modem support
  - **Files:** `app/handlers/subscription/purchase.py`, `app/handlers/subscription/modem.py`
  - **Actions:**
    1. Merge purchase flow changes
    2. Add modem support handler
    3. Ensure tenant context
    4. Add tests
  - **Dependencies:** Story 4.1 (Subscription Service)
  - **Notes:** Grouped subscription handlers

#### Story 5.2: Merge Admin Handlers for Promocodes and Users
- [ ] **Task:** Merge admin handlers with pagination and filters
  - **Files:** `app/handlers/admin/promocodes.py`, `app/handlers/admin/users.py`
  - **Actions:**
    1. Add pagination to promocodes handler
    2. Add balance filter and extended filters to users handler
    3. Add admin purchase subscription feature
    4. Ensure tenant context
    5. Add tests
  - **Dependencies:** Story 3.1 (Promocode CRUD), Story 3.3 (User CRUD)
  - **Notes:** Grouped admin handlers

#### Story 5.3: Merge Remaining Handlers (77 files in batches)
- [ ] **Task:** Review and merge remaining handlers with tenant compatibility
  - **Files:** `app/handlers/*.py` (77 files)
  - **Actions:**
    1. For each handler:
       - Verify tenant context usage
       - Merge changes from upstream
       - Add tests
    2. Process in 3 batches (25, 26, 26 files)
    3. After each batch: Code review checkpoint (see Story 5.3.1, 5.3.2, 5.3.3)
  - **Dependencies:** Story 4.4 (Services)
  - **Estimated Time:** 15 hours (5 hours per batch)
  - **Notes:** Large batch work. Code review checkpoints after each batch.

#### Story 5.3.1: Code Review Checkpoint - Handlers Batch 1
- [ ] **Task:** Review first 25 handler files for tenant compatibility
  - **Files:** First batch of `app/handlers/*.py` (25 files)
  - **Actions:**
    1. Review tenant context usage
    2. Fix issues before proceeding to batch 2
    3. Run validation scripts
  - **Dependencies:** Story 5.3 (first batch)
  - **Estimated Time:** 2 hours

#### Story 5.3.2: Code Review Checkpoint - Handlers Batch 2
- [ ] **Task:** Review second 26 handler files for tenant compatibility
  - **Files:** Second batch of `app/handlers/*.py` (26 files)
  - **Actions:**
    1. Review tenant context usage
    2. Fix issues before proceeding to batch 3
    3. Run validation scripts
  - **Dependencies:** Story 5.3 (second batch)
  - **Estimated Time:** 2 hours

#### Story 5.3.3: Code Review Checkpoint - Handlers Batch 3
- [ ] **Task:** Review third 26 handler files for tenant compatibility
  - **Files:** Third batch of `app/handlers/*.py` (26 files)
  - **Actions:**
    1. Review tenant context usage
    2. Fix all issues
    3. Run validation scripts
  - **Dependencies:** Story 5.3 (third batch)
  - **Estimated Time:** 2 hours

#### Story 6.1: Refactor Nalogo Service for Tenant-Aware Config
- [ ] **Task:** Make Nalogo service use tenant config instead of global env
  - **Files:** `app/services/nalogo_service.py`
  - **Actions:**
    1. Remove global config access: `settings.NALOGO_INN`, `settings.NALOGO_PASSWORD`
    2. Add `bot_id: int` parameter to `__init__()` and methods
    3. Use `get_config_value(db, bot_id, "nalogo.inn")` for INN
    4. Use `get_config_value(db, bot_id, "nalogo.password")` for password
    5. Update all Nalogo client initialization to use tenant config
    6. Add error handling: Raise `ValueError` if config missing with clear message
    7. Add tests for tenant isolation
  - **Dependencies:** Story 1.1 (config), Story 6.1.1 (migration)
  - **Estimated Time:** 4 hours
  - **Notes:** Critical for tenant isolation. See Story 6.1.1 for migration plan.

#### Story 6.1.1: Migrate Existing Nalogo Config to Tenant Config
- [ ] **Task:** Migrate global Nalogo config to tenant config
  - **Files:** `scripts/migrate_nalogo_config.py` (NEW), `app/database/crud/bot_configuration.py`
  - **Actions:**
    1. Read existing env vars: `NALOGO_INN`, `NALOGO_PASSWORD` from Settings
    2. For each active bot in database:
       - Create `bot_configurations` entry: `config_key="nalogo.inn"`, `config_value={"inn": "...", "password": "..."}`
       - Use existing env values as default if bot has no config
    3. Add feature flag: `nalogo.use_tenant_config` (default: False) for gradual rollout
    4. Test migration script in staging
  - **Dependencies:** Story 1.1 (config)
  - **Estimated Time:** 3 hours
  - **Notes:** Migration strategy for existing Nalogo credentials

#### Story 6.2: Integrate Nalogo with Payment Service
- [ ] **Task:** Update payment service to use tenant-aware Nalogo
  - **Files:** `app/services/payment_service.py`
  - **Actions:**
    1. Update NalogoService initialization to pass `bot_id`
    2. Ensure tenant context in receipt generation
    3. Add tests
  - **Dependencies:** Story 6.1 (Nalogo service)
  - **Notes:** Integration step

#### Story 7.1: Cherry-pick Promocode Bug Fixes
- [ ] **Task:** Apply promocode fixes with tenant compatibility
  - **Files:** `app/database/crud/promocode.py`, `app/handlers/admin/promocodes.py`
  - **Actions:**
    1. Cherry-pick commits: `2156f630` (first_purchase_only), `5a5a18d8` (pagination), `9cd5d8e0` (general fixes)
    2. Verify `bot_id` filters in all changes
    3. Add tests
  - **Dependencies:** Story 3.1 (Promocode CRUD)
  - **Notes:** Bug fixes from upstream

#### Story 7.2: Cherry-pick Subscription Bug Fixes
- [ ] **Task:** Apply subscription fixes with tenant compatibility
  - **Files:** `app/services/subscription_service.py`, `app/handlers/subscription/*.py`
  - **Actions:**
    1. Cherry-pick commits: `4bebff5c` (auto-activation), `e15728e3` (simple purchase), `56cc8bac` (purchase fix), `bce05d4b` (traffic reset)
    2. Verify tenant context in all changes
    3. Add tests
  - **Dependencies:** Story 4.1 (Subscription Service)
  - **Notes:** Bug fixes from upstream

#### Story 7.3: Cherry-pick Payment Bug Fixes (Iranian Only)
- [ ] **Task:** Apply payment fixes (only Iranian gateways)
  - **Files:** `app/services/payment_service.py`, `app/services/user_cart_service.py`
  - **Actions:**
    1. Cherry-pick commits: `bc19ec32` (persistent cart), `5aa9b6dd` (notification fix), `dd860146` (topup buttons)
    2. **DO NOT** cherry-pick: `9bd1944b` (platega - Russian gateway)
    3. Verify tenant context
    4. Add tests
  - **Dependencies:** Story 4.2 (Cart Service)
  - **Notes:** Only Iranian payment fixes

#### Story 7.4: Cherry-pick Other Bug Fixes
- [ ] **Task:** Apply remaining bug fixes with tenant compatibility
  - **Files:** Various handler and service files
  - **Actions:**
    1. Cherry-pick admin fixes
    2. Cherry-pick RemnaWave sync fixes
    3. Cherry-pick blacklist fixes
    4. Verify tenant context in all changes
    5. Add tests
  - **Dependencies:** Story 5.3 (Handlers)
  - **Notes:** Miscellaneous fixes

#### Story 8.1: Run All Unit Tests
- [ ] **Task:** Execute and fix all unit tests
  - **Files:** `tests/**/*.py`
  - **Actions:**
    1. Run: `pytest tests/ -v`
    2. Fix failing tests
    3. Generate coverage report
    4. Ensure >80% coverage for new code
  - **Dependencies:** All previous stories
  - **Notes:** Critical validation step

#### Story 8.2: Run Integration Tests
- [ ] **Task:** Execute integration tests for tenant isolation
  - **Files:** `tests/integration/*.py`
  - **Actions:**
    1. Run: `pytest tests/integration/ -v`
    2. Test tenant isolation for all endpoints
    3. Test Cabinet endpoints (see Story 8.2.1 for detailed scenarios)
    4. Test Nalogo integration (see Story 8.2.2 for detailed scenarios)
    5. Test JWT token validation with bot_id
    6. Test tenant mismatch scenarios
  - **Dependencies:** Story 8.1 (Unit Tests)
  - **Estimated Time:** 8 hours
  - **Notes:** Critical for data isolation verification

#### Story 8.2.1: Cabinet Integration Test Scenarios
- [ ] **Task:** Create comprehensive Cabinet integration tests
  - **Files:** `tests/integration/test_cabinet_tenant_isolation.py` (NEW)
  - **Actions:**
    1. Test tenant isolation: Create user in tenant A, try to access from tenant B → should fail with 403
    2. Test JWT validation: Token with wrong bot_id should fail validation
    3. Test email verification: Verify token belongs to correct tenant
    4. Test password reset: Reset token should only work for correct tenant
    5. Test all Cabinet routes with tenant context
  - **Dependencies:** Story 8.2
  - **Estimated Time:** 4 hours

#### Story 8.2.2: Nalogo Integration Test Scenarios
- [ ] **Task:** Create comprehensive Nalogo integration tests
  - **Files:** `tests/integration/test_nalogo_tenant_isolation.py` (NEW)
  - **Actions:**
    1. Test tenant isolation: Create receipt for tenant A, verify tenant B cannot access it
    2. Test config isolation: Different tenants use different Nalogo credentials
    3. Test error handling: Missing config raises appropriate error
    4. Test receipt creation: Receipt is associated with correct tenant
  - **Dependencies:** Story 8.2
  - **Estimated Time:** 3 hours

#### Story 8.3: Manual Testing Checklist
- [ ] **Task:** Perform manual testing for all features
  - **Files:** N/A
  - **Actions:**
    1. Test Cabinet authentication
    2. Test Cabinet routes tenant-aware
    3. Test promocodes with first_purchase_only
    4. Test subscription fixes
    5. Test persistent cart tenant-aware
    6. Test admin features
    7. Test data leak prevention
  - **Dependencies:** Story 8.2 (Integration Tests)
  - **Notes:** Final validation before documentation

#### Story 8.4: Database Schema Validation
- [ ] **Task:** Validate database schema changes
  - **Files:** N/A (SQL queries)
  - **Actions:**
    1. Verify `bot_id` exists in all tables
    2. Verify Cabinet columns in `users` table
    3. Verify `first_purchase_only` in `promocodes` table
    4. Generate validation report
  - **Dependencies:** Story 1.2 (Cabinet columns), Story 1.3 (Promocode field)
  - **Notes:** Schema verification

#### Story 8.5: Code Quality Check
- [ ] **Task:** Run code quality checks
  - **Files:** `app/**/*.py`
  - **Actions:**
    1. Run: `ruff check app/`
    2. Run: `python -m py_compile app/**/*.py`
    3. Fix any issues
    4. Generate quality report
  - **Dependencies:** Story 8.1 (Unit Tests)
  - **Notes:** Code quality validation

#### Story 9.1: Update PRD with Cabinet Feature
- [ ] **Task:** Document Cabinet feature in PRD
  - **Files:** `_bmad-output/prd.md`
  - **Actions:**
    1. Add Cabinet requirements
    2. Update user stories
    3. Update acceptance criteria
  - **Dependencies:** Story 8.3 (Manual Testing)
  - **Notes:** Documentation update

#### Story 9.2: Update Architecture Document
- [ ] **Task:** Document Cabinet and Nalogo in architecture
  - **Files:** `_bmad-output/architecture.md`
  - **Actions:**
    1. Add Cabinet architecture section
    2. Add Nalogo integration pattern
    3. Update diagrams
  - **Dependencies:** Story 9.1 (PRD Update)
  - **Notes:** Architecture documentation

#### Story 9.3: Update API Documentation
- [ ] **Task:** Document Cabinet API endpoints
  - **Files:** API documentation files
  - **Actions:**
    1. Document all Cabinet endpoints
    2. Add tenant parameters
    3. Add examples
  - **Dependencies:** Story 9.2 (Architecture Update)
  - **Notes:** API documentation

#### Story 9.4: Create Changelog
- [ ] **Task:** Generate changelog for merge
  - **Files:** `CHANGELOG.md`
  - **Actions:**
    1. List all changes
    2. Categorize: Added, Fixed, Changed
    3. Version bump
  - **Dependencies:** Story 9.3 (API Docs)
  - **Notes:** Final documentation step

### Acceptance Criteria

#### Story 1.1: Refactor Config for Tenant-Aware Cabinet and Nalogo
- [ ] **AC 1.1.1:** Given a bot_id, when calling `get_cabinet_jwt_secret(db, bot_id)`, then it returns the JWT secret from `bot_configurations` table for that tenant
- [ ] **AC 1.1.2:** Given a bot_id, when calling `get_nalogo_config(db, bot_id)`, then it returns INN and password from `bot_configurations` table for that tenant
- [ ] **AC 1.1.3:** Given two different bot_ids, when getting config for each, then they return different values (tenant isolation)
- [ ] **AC 1.1.4:** Given no config exists for a bot_id, when getting config, then it returns None or raises appropriate error

#### Story 1.2: Add Cabinet Columns to User Model
- [ ] **AC 1.2.1:** Given a User model, when checking schema, then all 7 Cabinet columns exist with correct types
- [ ] **AC 1.2.2:** Given a migration script, when running it, then Cabinet columns are added to `users` table without errors
- [ ] **AC 1.2.3:** Given existing users, when migration runs, then Cabinet columns are NULL (backward compatible)
- [ ] **AC 1.2.4:** Given a User instance, when accessing Cabinet columns, then they are accessible and nullable

#### Story 2.2: Refactor Cabinet JWT Handler for Tenant-Aware
- [ ] **AC 2.2.1:** Given user_id, telegram_id, and bot_id, when calling `create_access_token()`, then JWT payload contains `bot_id` claim
- [ ] **AC 2.2.2:** Given a JWT token with bot_id claim, when validating token, then bot_id is verified and matches tenant context
- [ ] **AC 2.2.3:** Given a JWT token without bot_id claim, when validating token, then validation fails
- [ ] **AC 2.2.4:** Given two different bot_ids, when creating tokens for same user, then tokens are different (tenant isolation)

#### Story 2.5: Refactor All Cabinet Routes for Tenant-Aware
- [ ] **AC 2.5.1:** Given a Cabinet route, when calling endpoint, then `bot_id` is extracted from tenant dependency
- [ ] **AC 2.5.2:** Given a Cabinet route with bot_id, when querying database, then all queries include `bot_id` filter
- [ ] **AC 2.5.3:** Given two different tenants, when calling same Cabinet endpoint, then they see only their own data (tenant isolation)
- [ ] **AC 2.5.4:** Given a Cabinet route without tenant context, when calling endpoint, then it returns 401 Unauthorized with localized error message
- [ ] **AC 2.5.5:** Given a Cabinet route with tenant mismatch (user belongs to different tenant than token's bot_id), when calling endpoint, then it returns 403 Forbidden with localized error message
- [ ] **AC 2.5.6:** Given a Cabinet route with invalid JWT token (missing bot_id claim), when calling endpoint, then it returns 401 Unauthorized

#### Story 3.1: Update Promocode CRUD for first_purchase_only and Pagination
- [ ] **AC 3.1.1:** Given a promocode with `first_purchase_only=True`, when user makes first purchase, then promocode is applied
- [ ] **AC 3.1.2:** Given a promocode with `first_purchase_only=True`, when user makes second purchase, then promocode is not applied
- [ ] **AC 3.1.3:** Given a list of promocodes, when calling `get_promocodes_list()` with pagination, then results are paginated correctly
- [ ] **AC 3.1.4:** Given a bot_id, when querying promocodes, then only promocodes for that tenant are returned
- [ ] **AC 3.1.5:** Given invalid pagination parameters (negative offset/limit), when calling `get_promocodes_list()`, then it raises ValueError with clear message
- [ ] **AC 3.1.6:** Given a promocode with `first_purchase_only=True` and user has no purchase history, when checking validity, then promocode is valid

#### Story 4.2: Refactor Cart Service for Tenant-Aware Redis Keys
- [ ] **AC 4.2.1:** Given a bot_id and user_id, when getting cart, then Redis key is `cart:{bot_id}:{user_id}`
- [ ] **AC 4.2.2:** Given two different bot_ids, when getting carts for same user_id, then they are stored separately (tenant isolation)
- [ ] **AC 4.2.3:** Given a cart operation, when executing, then Redis key includes bot_id prefix
- [ ] **AC 4.2.4:** Given cart data, when accessing from different tenant, then data is not accessible (tenant isolation)

#### Story 6.1: Refactor Nalogo Service for Tenant-Aware Config
- [ ] **AC 6.1.1:** Given a bot_id, when initializing NalogoService, then it uses config from `bot_configurations` table
- [ ] **AC 6.1.2:** Given two different bot_ids, when creating receipts, then they use different Nalogo credentials (tenant isolation)
- [ ] **AC 6.1.3:** Given a bot_id without Nalogo config, when creating receipt, then it raises ValueError with message "Nalogo config not found for bot_id {bot_id}"
- [ ] **AC 6.1.4:** Given a receipt creation, when successful, then receipt is associated with correct tenant
- [ ] **AC 6.1.5:** Given invalid Nalogo credentials (wrong INN/password), when creating receipt, then it raises appropriate error from Nalogo API
- [ ] **AC 6.1.6:** Given a bot_id with partial config (only INN, no password), when initializing NalogoService, then it raises ValueError with clear message

#### Story 8.2: Run Integration Tests
- [ ] **AC 8.2.1:** Given two tenants with data, when querying from tenant 1, then only tenant 1's data is returned
- [ ] **AC 8.2.2:** Given Cabinet endpoints, when calling from different tenants, then data is isolated correctly
- [ ] **AC 8.2.3:** Given Nalogo integration, when creating receipts for different tenants, then receipts use correct credentials
- [ ] **AC 8.2.4:** Given all integration tests, when running, then all tests pass with >80% coverage
- [ ] **AC 8.2.5:** Given tenant mismatch scenarios (user from tenant A, token from tenant B), when calling endpoints, then all return 403 Forbidden
- [ ] **AC 8.2.6:** Given missing tenant context, when calling endpoints, then all return 401 Unauthorized

## Additional Context

### Dependencies

**External Dependencies:**
- PostgreSQL 15+ with RLS enabled
- Redis 5.0.1 for caching
- Upstream/main branch access for cherry-picking
- Alembic for migrations

**Story Dependencies:**
- Story 0.1 (Setup) → All stories
- Story 0.2 (Validation Scripts) → All stories (used throughout)
- Story 1.1 (Config Refactoring) → Story 2.2, Story 2.4, Story 6.1
- Story 1.2 (Cabinet Columns) → Story 2.1, Story 2.2, Story 2.3
- Story 1.3 (Promocode Field) → Story 3.1, Story 7.1
- Story 2.1 (Cabinet Module) → Story 2.2, Story 2.3, Story 2.4, Story 2.5
- Story 2.2 (Cabinet JWT) → Story 2.5
- Story 2.4 (Cabinet Dependencies) → Story 2.5
- Story 2.5 (Cabinet Routes) → Story 2.6
- Story 3.1 (Promocode CRUD) → Story 5.2, Story 7.1
- Story 3.2 (Subscription CRUD) → Story 4.1, Story 7.2
- Story 3.3 (User CRUD) → Story 5.2
- Story 3.4 (CRUD Batch) → Story 4.4
- Story 4.1 (Subscription Service) → Story 5.1, Story 7.2
- Story 4.2 (Cart Service) → Story 7.3
- Story 4.4 (Services Batch) → Story 5.3
- Story 5.3 (Handlers Batch) → Story 7.4
- Story 6.1 (Nalogo Service) → Story 6.2
- Story 6.2 (Nalogo Integration) → Story 8.2
- All Stories → Story 8.1, Story 8.2, Story 8.3
- Story 8.3 (Manual Testing) → Story 9.1
- Story 9.1 (PRD Update) → Story 9.2
- Story 9.2 (Architecture Update) → Story 9.3
- Story 9.3 (API Docs) → Story 9.4

### Testing Strategy

**Unit Tests:**
- Each component tested separately with tenant fixtures
- Use `test_bots` fixture from `tests/conftest.py` for multiple tenants
- Test tenant isolation for each CRUD function, service, and handler
- Coverage target: >80% for new code

**Integration Tests:**
- Tenant isolation testing for all endpoints (RLS policies)
- Cabinet endpoints integration tests
- Nalogo integration tests with tenant config
- Payment flow tests with tenant context
- Run: `pytest tests/integration/ -v`

**Validation Scripts:**
- `scripts/validate_bot_id_queries.py`: Check all database queries have `bot_id` filter
- `scripts/validate_tenant_context.py`: Verify tenant context in functions
- `scripts/validate_redis_keys.py`: Validate Redis keys have tenant prefix
- Run validation scripts after each phase

**Manual Testing:**
- Cabinet authentication flow
- Cabinet routes tenant-aware behavior
- Promocodes with first_purchase_only
- Subscription fixes (auto-activation, traffic reset)
- Persistent cart tenant-aware
- Admin features
- Data leak testing (verify no cross-tenant data access)

**Test Files to Create/Update:**
- `tests/integration/test_cabinet_tenant_isolation.py` (NEW)
- `tests/integration/test_nalogo_tenant_isolation.py` (NEW)
- `tests/services/test_nalogo_service_tenant.py` (NEW)
- `tests/cabinet/test_cabinet_auth.py` (NEW)
- `tests/cabinet/test_cabinet_routes.py` (NEW)
- Update existing tests for tenant compatibility:
  - `tests/services/test_payment_service.py` - Add tenant context
  - `tests/handlers/test_subscription.py` - Add tenant fixtures
  - `tests/database/crud/test_promocode.py` - Add tenant isolation tests
  - `tests/database/crud/test_subscription.py` - Add tenant isolation tests
  - `tests/database/crud/test_user.py` - Add tenant isolation tests

### Notes

**Critical Requirements:**
- تمام تغییرات باید با `project-context.md` سازگار باشند
- هیچ Russian gateway (Platega, YooKassa, etc.) نباید merge شود
- Cabinet و Nalogo باید per-tenant config داشته باشند
- تمام JWT tokens باید bot_id claim داشته باشند
- Redis keys باید tenant prefix داشته باشند
- Database queries باید bot_id filter داشته باشند

**High-Risk Items:**
- **Migration Conflicts**: Cabinet columns migration may conflict with existing migrations - test in staging first
- **Data Leakage**: Risk of cross-tenant data access if bot_id filters are missing - use validation scripts
- **Breaking Changes**: Tenant-aware refactoring may break existing functionality - maintain backward compatibility where possible
- **Config Migration**: Moving from global env to tenant config requires careful migration - use feature flags if needed

**Known Limitations:**
- Cabinet module doesn't exist - must be added from upstream (31 files)
- Nalogo service exists but uses global config - requires refactoring
- Some upstream changes may conflict with multi-tenant architecture - manual merge required

**Future Considerations (Out of Scope):**
- Performance optimization for tenant queries (indexes, caching)
- Advanced tenant isolation features (audit logs, data encryption)
- Multi-region tenant support
- Tenant-specific feature flags beyond basic config

**Implementation Order:**
1. Phase 0: Setup (1 day) - Must complete first
2. Phase 1: Core Infrastructure (2 days) - Foundation for all other phases
3. Phase 2: Cabinet Module (3-4 days) - New feature, high priority
4. Phase 3: CRUD Operations (3-4 days) - Foundation for services
5. Phase 4: Services (3-4 days) - Foundation for handlers
6. Phase 5: Handlers (2-3 days) - User-facing features
7. Phase 6: Nalogo Integration (2 days) - Payment feature
8. Phase 7: Bug Fixes (1-2 days) - Quality improvements
9. Phase 8: Testing (2 days) - Validation
10. Phase 9: Documentation (1 day) - Final step

**Total Estimated Time:** 20-26 working days (4-5 weeks)

## Migration Strategy

### Database Migration Approach

**Principle:** All migrations must be backward compatible and reversible.

#### Cabinet Columns Migration (Story 1.2)

```python
# Migration strategy:
def upgrade():
    # Step 1: Add nullable columns (no data loss)
    op.add_column('users', sa.Column('cabinet_email', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('cabinet_email_verified', sa.Boolean(), default=False, nullable=False))
    # ... (all other columns nullable=True)
    
    # Step 2: Set defaults for existing rows (backward compatible)
    op.execute("UPDATE users SET cabinet_email_verified = false WHERE cabinet_email_verified IS NULL")
    
    # Step 3: Add indexes (performance)
    op.create_index('idx_users_cabinet_email', 'users', ['cabinet_email'])

def downgrade():
    # Reversible: Remove columns
    op.drop_index('idx_users_cabinet_email', 'users')
    op.drop_column('users', 'cabinet_password_reset_expires_at')
    # ... (remove all Cabinet columns)
```

**Rollback Plan:**
- If migration fails: `alembic downgrade -1`
- If data corruption: Restore from backup SQL dump
- Test rollback in staging before production

#### Promocode first_purchase_only Migration (Story 1.3)

```python
# Migration strategy:
def upgrade():
    # Add column with default (existing promocodes = False)
    op.add_column('promocodes', sa.Column('first_purchase_only', sa.Boolean(), default=False, nullable=False))
    # No data migration needed (default handles it)

def downgrade():
    op.drop_column('promocodes', 'first_purchase_only')
```

**Rollback Plan:**
- Simple column drop (no data loss risk)
- Test in staging first

### Config Migration Strategy

#### Nalogo Config Migration (Story 6.1.1)

**Migration Steps:**
1. Read existing env vars: `NALOGO_INN`, `NALOGO_PASSWORD`
2. For each active bot:
   - Check if `bot_configurations` entry exists for `"nalogo.inn"`
   - If not, create entry with env values as default
   - Pattern: `config_value = {"inn": env_value, "password": env_value}`
3. Add feature flag for gradual rollout
4. Test migration script in staging

**Rollback Plan:**
- Keep env vars as fallback during transition
- Feature flag allows switching back to env vars
- Document rollback procedure

## Error Handling Requirements

### Cabinet Routes Error Handling (Story 2.5)

**Required Error Cases:**

1. **Missing Tenant Context:**
   ```python
   if bot_id is None:
       raise HTTPException(
           status_code=401,
           detail=Texts.get("cabinet.tenant_context_missing")
       )
   ```

2. **Tenant Mismatch:**
   ```python
   if user.bot_id != bot_id:
       logger.warning(
           "Tenant mismatch detected",
           user_bot_id=user.bot_id,
           token_bot_id=bot_id,
           user_id=user.id
       )
       raise HTTPException(
           status_code=403,
           detail=Texts.get("cabinet.tenant_mismatch")
       )
   ```

3. **Invalid JWT Token:**
   ```python
   if "bot_id" not in token_payload:
       raise HTTPException(
           status_code=401,
           detail=Texts.get("cabinet.invalid_token")
       )
   ```

### Nalogo Service Error Handling (Story 6.1)

**Required Error Cases:**

1. **Missing Config:**
   ```python
   if not nalogo_config:
       raise ValueError(f"Nalogo config not found for bot_id {bot_id}")
   ```

2. **Invalid Credentials:**
   ```python
   try:
       receipt = nalogo_client.create_receipt(...)
   except NalogoAPIError as e:
       logger.error("Nalogo API error", bot_id=bot_id, error=str(e))
       raise ValueError(f"Failed to create receipt: {e}")
   ```

## Performance Considerations

### Query Performance (Story 3.4, 4.4)

**Index Requirements:**
- All tables with `bot_id` column must have index: `idx_{table}_bot_id`
- Composite indexes for common queries: `idx_{table}_bot_id_created_at`
- Verify index usage: `EXPLAIN ANALYZE` on critical queries

**Performance ACs:**
- **AC 3.4.5:** Given a CRUD query with bot_id filter, when executing, then query time is <100ms (with proper index)
- **AC 4.4.5:** Given a service method with tenant config lookup, when executing, then config lookup is cached (no repeated DB queries)

### Caching Strategy

**Tenant Config Caching:**
- Cache `bot_configurations` lookups in memory (TTL: 5 minutes)
- Invalidate cache on config updates
- Pattern: `cache_key = f"bot_config:{bot_id}:{config_key}"`

**Redis Key Performance:**
- Use `cache_key()` utility for consistent key generation
- Verify key patterns don't cause Redis memory issues
- Monitor Redis memory usage after merge

## Git Workflow

**Branch Strategy:**
- Branch: `merge/upstream-main-{YYYYMMDD}`
- Commit format: `[Story-X.Y] Description`
- Example: `[Story-2.5] Refactor Cabinet routes for tenant-aware`

**PR Strategy:**
- One PR per phase (Phase 0-9)
- Or: One PR per story group (e.g., all Cabinet stories together)
- Each PR must pass:
  - Validation scripts
  - Unit tests
  - Integration tests
  - Code review

**Commit Message Guidelines:**
```
[Story-X.Y] Brief description

- Detailed change 1
- Detailed change 2
- Related issue/AC reference

Dependencies: Story-A.B, Story-C.D
```

## Time Estimates Per Story

| Story | Estimated Time | Phase |
|-------|---------------|-------|
| 0.1 | 1 hour | Phase 0 |
| 0.1.1 | 2 hours | Phase 0 |
| 0.2 | 4 hours | Phase 0 |
| 1.1 | 4 hours | Phase 1 |
| 1.2 | 6 hours | Phase 1 |
| 1.3 | 2 hours | Phase 1 |
| 2.1 | 2 hours | Phase 2 |
| 2.2 | 4 hours | Phase 2 |
| 2.3 | 3 hours | Phase 2 |
| 2.4 | 2 hours | Phase 2 |
| 2.5 | 12 hours | Phase 2 |
| 2.6 | 2 hours | Phase 2 |
| 3.1 | 4 hours | Phase 3 |
| 3.2 | 4 hours | Phase 3 |
| 3.3 | 3 hours | Phase 3 |
| 3.4 | 16 hours | Phase 3 |
| 4.1 | 4 hours | Phase 4 |
| 4.2 | 4 hours | Phase 4 |
| 4.3 | 3 hours | Phase 4 |
| 4.4 | 18 hours | Phase 4 |
| 5.1 | 4 hours | Phase 5 |
| 5.2 | 4 hours | Phase 5 |
| 5.3 | 15 hours | Phase 5 |
| 5.3.1-3 | 6 hours | Phase 5 |
| 6.1 | 4 hours | Phase 6 |
| 6.1.1 | 3 hours | Phase 6 |
| 6.2 | 2 hours | Phase 6 |
| 7.1-7.4 | 8 hours | Phase 7 |
| 8.1 | 4 hours | Phase 8 |
| 8.2 | 8 hours | Phase 8 |
| 8.2.1 | 4 hours | Phase 8 |
| 8.2.2 | 3 hours | Phase 8 |
| 8.3-8.5 | 6 hours | Phase 8 |
| 9.1-9.4 | 8 hours | Phase 9 |

**Total:** ~180 hours (~22.5 working days)

---

## Code Review Fixes Applied

**Review Date:** 2026-01-03  
**Reviewer:** AI Code Review Agent  
**Status:** ✅ All Critical and Medium Issues Fixed

### Issues Fixed

#### 🔴 Critical Issues (8 fixed)
1. ✅ **Migration Strategy Added** - Added comprehensive migration strategy section with rollback procedures
2. ✅ **Error Handling Enhanced** - Added error handling requirements and ACs for all Cabinet routes
3. ✅ **Nalogo Migration Plan** - Added Story 6.1.1 for migrating existing Nalogo config
4. ✅ **Validation Scripts Detailed** - Added detailed specifications for all validation scripts
5. ✅ **Cabinet File Count Clarified** - Changed to "exact count TBD from upstream" with verification step
6. ✅ **Error Case ACs Added** - Added error handling ACs for all stories (tenant mismatch, missing config, etc.)
7. ✅ **Performance Considerations Added** - Added performance ACs and caching strategy
8. ✅ **Integration Test Scenarios Added** - Added detailed test scenarios (Story 8.2.1, 8.2.2)

#### 🟡 Medium Issues (5 fixed)
9. ✅ **Rollback Procedure Added** - Added Story 0.1.1 with rollback documentation
10. ✅ **Code Review Checkpoints Added** - Added checkpoints after each batch (Story 5.3.1-3)
11. ✅ **Test File List Completed** - Added list of existing test files to update
12. ✅ **Dependency Clarification** - Clarified dependencies and added migration story dependencies
13. ✅ **Git Workflow Added** - Added comprehensive git workflow section

#### 🟢 Low Issues (3 fixed)
14. ✅ **Helper Function Pattern Clarified** - Documented consistent pattern for config helpers
15. ✅ **Time Estimates Added** - Added time estimates for all stories
16. ✅ **Git Commit Strategy Added** - Added commit message format and PR strategy

### New Sections Added

1. **Migration Strategy** - Comprehensive database migration approach with rollback plans
2. **Error Handling Requirements** - Detailed error handling patterns for Cabinet and Nalogo
3. **Performance Considerations** - Query performance, indexing, and caching strategies
4. **Git Workflow** - Branch strategy, commit format, and PR guidelines
5. **Time Estimates Per Story** - Detailed time breakdown for sprint planning

### Stories Added

- Story 0.1.1: Rollback Procedure
- Story 5.3.1-3: Code Review Checkpoints (3 stories)
- Story 6.1.1: Migrate Existing Nalogo Config
- Story 8.2.1: Cabinet Integration Test Scenarios
- Story 8.2.2: Nalogo Integration Test Scenarios

### Acceptance Criteria Enhanced

- Added error handling ACs for all stories
- Added performance ACs for batch stories
- Added tenant mismatch ACs for Cabinet routes
- Added missing config ACs for Nalogo service

---

**Tech Spec Status:** ✅ Ready for Implementation  
**Next Step:** Begin Story 0.1 (Setup and Backup)
