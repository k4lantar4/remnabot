# Story: Eliminate Schema Redundancy and Implement BotConfigService

**Story ID:** STORY-001  
**Epic:** Multi-Tenant Architecture Refactoring  
**Priority:** 🔴 CRITICAL  
**Status:** In Progress  
**Created:** 2025-12-15  
**Estimated Effort:** 8-13 hours

---

## 📋 Story Summary

Eliminate data redundancy in the `bots` table by removing redundant columns for feature flags and configurations, and implement `BotConfigService` as the single source of truth for accessing bot configurations and feature flags.

---

## 🎯 Business Value

- **Eliminates data inconsistency** - Configs stored in one place only
- **Reduces technical debt** - Cleaner, more maintainable codebase
- **Prevents bugs** - No confusion about source of truth
- **Enables multi-tenant isolation** - Proper separation of concerns

---

## 📖 User Story

**As a** system architect  
**I want** bot configurations and feature flags to be stored in dedicated tables with a unified service layer  
**So that** we have a single source of truth, eliminate redundancy, and enable proper multi-tenant isolation

---

## 🚨 Problem Statement

Currently, bot configurations are stored redundantly in two places:
1. **In `bots` table** (as columns like `card_to_card_enabled`, `default_language`, etc.)
2. **In `bot_feature_flags`/`bot_configurations` tables** (as rows)

This causes:
- ❌ Data inconsistency risk
- ❌ Confusion about which is the source of truth
- ❌ Technical debt and maintenance complexity
- ❌ Potential bugs from unsynchronized updates

---

## ✅ Acceptance Criteria

### AC1: BotConfigService Implementation
- [x] `BotConfigService` class created in `app/services/bot_config_service.py`
- [x] Service provides `is_feature_enabled(db: AsyncSession, bot_id: int, feature_key: str) -> bool` method
- [x] Service provides `get_config(db: AsyncSession, bot_id: int, config_key: str, default: Any = None) -> Any` method
- [x] Service provides `set_feature_enabled(db: AsyncSession, bot_id: int, feature_key: str, enabled: bool) -> None` method
- [x] Service provides `set_config(db: AsyncSession, bot_id: int, config_key: str, value: Any) -> None` method
- [x] Service includes backward compatibility fallback to `bots` table during transition
- [x] All methods properly handle async database operations
- [x] Service includes comprehensive docstrings

**Backward Compatibility Logic:**
- **For reads:** Check `bot_feature_flags`/`bot_configurations` tables first, if not found fallback to `bots` table columns, return default if neither exists
- **For writes:** During transition period, write to both new tables AND `bots` table columns (dual-write pattern)
- **After migration complete:** Remove fallback logic and dual-write pattern (only use new tables)

### AC2: Data Migration
- [x] Migration script created to copy data from `bots` table to `bot_feature_flags` and `bot_configurations`
- [x] Migration script handles all 2 feature flags (`card_to_card_enabled`, `zarinpal_enabled`)
- [x] Migration script handles all 9 configuration columns (see list below)
- [x] Verification script created to validate migration correctness
- [ ] Migration tested on dev database
- [ ] No data loss during migration

**Feature Flags to Migrate:**
- `card_to_card_enabled` → `bot_feature_flags` with `feature_key='card_to_card'`
- `zarinpal_enabled` → `bot_feature_flags` with `feature_key='zarinpal'`

**Configurations to Migrate:**
- `default_language` → `bot_configurations` with `config_key='DEFAULT_LANGUAGE'`
- `support_username` → `bot_configurations` with `config_key='SUPPORT_USERNAME'`
- `admin_chat_id` → `bot_configurations` with `config_key='ADMIN_NOTIFICATIONS_CHAT_ID'`
- `admin_topic_id` → `bot_configurations` with `config_key='ADMIN_NOTIFICATIONS_TOPIC_ID'`
- `notification_group_id` → `bot_configurations` with `config_key='NOTIFICATION_GROUP_ID'`
- `notification_topic_id` → `bot_configurations` with `config_key='NOTIFICATION_TOPIC_ID'`
- `card_receipt_topic_id` → `bot_configurations` with `config_key='CARD_RECEIPT_TOPIC_ID'`
- `zarinpal_merchant_id` → `bot_configurations` with `config_key='ZARINPAL_MERCHANT_ID'`
- `zarinpal_sandbox` → `bot_configurations` with `config_key='ZARINPAL_SANDBOX'`

### AC3: Code Updates
- [x] All direct accesses to `bot.card_to_card_enabled` replaced with `BotConfigService.is_feature_enabled()`
- [x] All direct accesses to `bot.zarinpal_enabled` replaced with `BotConfigService.is_feature_enabled()`
- [x] All direct accesses to `bot.default_language` replaced with `BotConfigService.get_config()`
- [x] All direct accesses to other redundant config columns replaced with `BotConfigService.get_config()`
- [x] All direct writes to redundant columns replaced with `BotConfigService.set_*()` methods
- [x] Code search performed to find all occurrences (grep for patterns)
- [x] All handlers updated to use service
- [x] All services updated to use service

### AC4: Schema Cleanup
- [x] SQL migration script created to drop redundant columns from `bots` table
- [x] Migration removes 2 feature flag columns
- [x] Migration removes 9 configuration columns
- [x] `Bot` model updated to remove redundant column definitions
- [x] `BotConfigService` updated to remove fallback logic (no longer needed)
- [ ] Migration tested on dev database
- [ ] Rollback plan documented

### AC5: Testing
- [x] Unit tests for `BotConfigService` created
- [x] Tests cover all service methods
- [x] Tests verify backward compatibility during transition
- [x] Integration tests verify data migration correctness
- [x] Integration tests verify isolation (tenant A cannot access tenant B configs)
- [ ] Manual testing performed on dev environment
- [ ] All tests pass

---

## 🔧 Technical Implementation Details

### Phase 0: Service Creation (2-3 hours)

**File:** `app/services/bot_config_service.py`

**Implementation Notes:**
- Use async/await for all database operations
- Include backward compatibility fallback to `bots` table during transition (see AC1 for explicit fallback logic)
- **JSONB Normalization:** When storing simple values (string, int, bool), wrap in `{'value': ...}` dict. When storing complex objects, store as-is. When reading, automatically unwrap simple values.
- Handle None values gracefully with defaults
- Use existing CRUD operations from `app/database/crud/`

**Reference:** See `docs/implementation-guide-step-by-step.md` Step 2 for complete implementation

### Phase 1: Data Migration (1-2 hours)

**File:** `migrations/migrate_configs_from_bots_table.py`

**Implementation Notes:**
- Iterate through all bots
- For each bot, migrate feature flags first, then configurations
- Use `BotConfigService` methods to set values (ensures both places updated during transition)
- Commit after each bot to allow partial rollback
- Log progress for each bot

**Verification Script:** `migrations/verify_config_migration.py`
- Verify all feature flags migrated correctly
- Verify all configurations migrated correctly
- Assert values match between old and new locations
- Report any mismatches

### Phase 2: Code Updates (4-6 hours)

**Search Patterns:**
```bash
# Find feature flag accesses
grep -r "\.card_to_card_enabled" app/
grep -r "\.zarinpal_enabled" app/

# Find config accesses (all 9 configuration columns)
grep -r "\.default_language" app/
grep -r "\.support_username" app/
grep -r "\.admin_chat_id" app/
grep -r "\.admin_topic_id" app/
grep -r "\.notification_group_id" app/
grep -r "\.notification_topic_id" app/
grep -r "\.card_receipt_topic_id" app/
grep -r "\.zarinpal_merchant_id" app/
grep -r "\.zarinpal_sandbox" app/
```

**Update Pattern:**
```python
# Before
if bot.card_to_card_enabled:
    # ...

# After
from app.services.bot_config_service import BotConfigService
if await BotConfigService.is_feature_enabled(db, bot_id, 'card_to_card'):
    # ...

# Example for config access:
# Before
language = bot.default_language or 'fa'

# After
language = await BotConfigService.get_config(db, bot_id, 'DEFAULT_LANGUAGE', 'fa')
```

### Phase 3: Schema Cleanup (1-2 hours)

**SQL Migration:** `migrations/remove_redundant_columns_from_bots.sql`
```sql
ALTER TABLE bots 
    DROP COLUMN IF EXISTS card_to_card_enabled,
    DROP COLUMN IF EXISTS zarinpal_enabled,
    DROP COLUMN IF EXISTS default_language,
    DROP COLUMN IF EXISTS support_username,
    DROP COLUMN IF EXISTS admin_chat_id,
    DROP COLUMN IF EXISTS admin_topic_id,
    DROP COLUMN IF EXISTS notification_group_id,
    DROP COLUMN IF EXISTS notification_topic_id,
    DROP COLUMN IF EXISTS card_receipt_topic_id,
    DROP COLUMN IF EXISTS zarinpal_merchant_id,
    DROP COLUMN IF EXISTS zarinpal_sandbox;
```

**Model Update:** `app/database/models.py`
- Remove redundant column definitions from `Bot` class
- Keep only: Identity, Billing, Metadata columns
- Update relationships if needed

**Service Update:** `app/services/bot_config_service.py`
- Remove fallback logic to `bots` table
- Simplify methods (no more dual-write)

---

## 📁 Files to Create/Modify

### New Files:
- `app/services/bot_config_service.py` - Main service implementation
- `migrations/migrate_configs_from_bots_table.py` - Data migration script
- `migrations/verify_config_migration.py` - Verification script
- `migrations/remove_redundant_columns_from_bots.sql` - Schema cleanup migration
- `tests/services/test_bot_config_service.py` - Unit tests
- `tests/integration/test_config_migration.py` - Integration tests

### Files to Modify:
- `app/database/models.py` - Remove redundant columns from `Bot` model
- All handler files that access redundant columns (to be identified via grep), including the modular tenant bots package under `app/handlers/admin/tenant_bots/`
- All service files that access redundant columns

---

## 🧪 Testing Strategy

### Unit Tests:
```python
# tests/services/test_bot_config_service.py
async def test_is_feature_enabled_returns_true_when_enabled()
async def test_is_feature_enabled_returns_false_when_disabled()
async def test_get_config_returns_value_when_exists()
async def test_get_config_returns_default_when_not_exists()
async def test_set_feature_enabled_updates_flag()
async def test_set_config_updates_value()
```

### Integration Tests:
```python
# tests/integration/test_config_migration.py
async def test_migration_copies_all_feature_flags()
async def test_migration_copies_all_configurations()
async def test_verification_script_detects_mismatches()
async def test_service_works_after_migration()
```

### Manual Testing Checklist:
- [ ] Create test bot with all configs set
- [ ] Run migration script
- [ ] Verify data in new tables
- [ ] Test service methods with migrated data
- [ ] Verify handlers still work correctly
- [ ] Run schema cleanup migration
- [ ] Verify service works without fallback
- [ ] Test rollback if needed

---

## ⚠️ Risks & Mitigation

### Risk 1: Data Loss During Migration
**Mitigation:**
- Backup database before migration
- Test migration on dev database first
- Use transactions with rollback capability
- Verify data after migration

### Risk 2: Breaking Changes in Handlers
**Mitigation:**
- Update handlers incrementally
- Test each handler after update
- Keep fallback logic during transition
- Comprehensive integration testing

### Risk 3: Performance Impact
**Mitigation:**
- Service uses existing CRUD (already optimized)
- Consider adding caching later (out of scope for this story)
- Monitor query performance after migration

### Risk 4: Incomplete Code Updates
**Mitigation:**
- Use comprehensive grep searches
- Code review for all changes
- Integration tests to catch missed updates

---

## 📚 References

### Documentation:
- `docs/MASTER-IMPLEMENTATION-GUIDE.md` - Master implementation guide
- `docs/analysis/redundancy-analysis-and-refactoring-plan.md` - Detailed redundancy analysis
- `docs/implementation-guide-step-by-step.md` - Step-by-step implementation guide
- `docs/analysis/comprehensive-code-review.md` - Code review findings

### Related Stories:
- Future: Add caching to `BotConfigService`
- Future: Add `bot_id` filters to all CRUD operations
- Future: Update all handlers to use `BotConfigService`

---

## 📝 Definition of Done

- [ ] `BotConfigService` implemented and tested
- [ ] Data migration completed and verified
- [ ] All code updated to use service
- [ ] Redundant columns removed from schema
- [ ] All tests passing
- [ ] Code reviewed and approved
- [ ] Documentation updated
- [ ] Migration tested on dev environment
- [ ] Rollback plan documented and tested

---

## 🎯 Success Metrics

- **Zero data loss** during migration
- **100% code coverage** for `BotConfigService`
- **All redundant columns removed** from `bots` table
- **All handlers working** after migration
- **No performance degradation** (baseline established)

---

**Story Owner:** Development Team  
**Reviewers:** Architecture Team, QA Team  
**Dependencies:** None (can start immediately)  
**Blocks:** Future stories requiring clean schema

