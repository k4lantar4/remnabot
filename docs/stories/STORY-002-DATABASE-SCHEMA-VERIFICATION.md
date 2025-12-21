# Database Schema Verification Report: STORY-002

**Story:** STORY-002 - Implement Tenant Bots Admin UX Panel  
**Verification Date:** 2025-12-21  
**Verifier:** Scrum Master Agent

---

## Executive Summary

**CRITICAL FINDING:** Three database tables referenced in STORY-002 **DO NOT EXIST** in the current database schema. These tables are part of a future enhancement (Phase 5) that has not been implemented yet.

**Impact:** HIGH - Queries in AC2 and AC6 will fail if executed as written.

**Recommendation:** Either create migration to add these tables, or update story queries to use existing schema.

---

## Tables Referenced in STORY-002

### ✅ Tables That EXIST

| Table Name | Status | Location | Notes |
|------------|--------|----------|-------|
| `bots` | ✅ EXISTS | `migrations/001_create_multi_tenant_tables.sql` | Created in migration 1.1 |
| `bot_feature_flags` | ✅ EXISTS | `migrations/001_create_multi_tenant_tables.sql` | Created in migration 1.1 |
| `bot_configurations` | ✅ EXISTS | `migrations/001_create_multi_tenant_tables.sql` | Created in migration 1.1 |
| `tenant_payment_cards` | ✅ EXISTS | `migrations/001_create_multi_tenant_tables.sql` | Created in migration 1.1 |
| `bot_plans` | ✅ EXISTS | `migrations/001_create_multi_tenant_tables.sql` | Created in migration 1.1 |
| `users` | ✅ EXISTS | Existing schema | Legacy table |
| `subscriptions` | ✅ EXISTS | Existing schema | Legacy table (has `bot_id` column) |
| `transactions` | ✅ EXISTS | Existing schema | Legacy table |

### ❌ Tables That DO NOT EXIST

| Table Name | Referenced In | Status | Notes |
|------------|---------------|--------|-------|
| `tenant_subscriptions` | AC2, AC6 | ❌ **DOES NOT EXIST** | Part of Phase 5 (Future Enhancement) |
| `tenant_subscription_plans` | AC2, AC6 | ❌ **DOES NOT EXIST** | Part of Phase 5 (Future Enhancement) |
| `plan_feature_grants` | AC6 | ❌ **DOES NOT EXIST** | Part of Phase 5 (Future Enhancement) |

---

## Detailed Analysis

### 1. tenant_subscriptions

**Referenced In:**
- AC2: List Bots query (joins to get plan information)
- AC6: Feature Flags query (joins to get plan tier for restrictions)

**Current Status:** ❌ **NOT CREATED**

**Schema Definition (from docs/MASTER-IMPLEMENTATION-GUIDE.md):**
```sql
CREATE TABLE tenant_subscriptions (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    plan_tier_id INTEGER NOT NULL REFERENCES tenant_subscription_plans(id),
    status VARCHAR(20) DEFAULT 'active',
    start_date TIMESTAMP DEFAULT NOW(),
    end_date TIMESTAMP,
    auto_renewal BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(bot_id)
);
```

**Purpose:** Tracks which subscription plan tier each tenant bot has (Starter, Growth, Enterprise, etc.)

**Impact on STORY-002:**
- AC2 query will fail: `LEFT JOIN tenant_subscriptions ts ON ts.bot_id = b.id`
- AC6 query will fail: `JOIN tenant_subscriptions ts ON ts.plan_tier_id = pf.plan_tier_id`

---

### 2. tenant_subscription_plans

**Referenced In:**
- AC2: List Bots query (joins to get plan display name)
- AC6: Feature Flags query (joins to get plan tier information)

**Current Status:** ❌ **NOT CREATED**

**Schema Definition (from docs/MASTER-IMPLEMENTATION-GUIDE.md):**
```sql
CREATE TABLE tenant_subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    monthly_price_kopeks INTEGER NOT NULL,
    activation_fee_kopeks INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Purpose:** Defines subscription plan tiers (Starter, Growth, Enterprise) with pricing and features

**Impact on STORY-002:**
- AC2 query will fail: `LEFT JOIN tenant_subscription_plans tsp ON tsp.id = ts.plan_tier_id`
- AC6 query will fail: References `plan_tier_id` which doesn't exist

---

### 3. plan_feature_grants

**Referenced In:**
- AC6: Feature Flags query (joins to check which features are granted by plan)

**Current Status:** ❌ **DOES NOT EXIST**

**Schema Definition (from docs/MASTER-IMPLEMENTATION-GUIDE.md):**
```sql
CREATE TABLE plan_feature_grants (
    plan_tier_id INTEGER NOT NULL REFERENCES tenant_subscription_plans(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT FALSE NOT NULL,
    config_override JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (plan_tier_id, feature_key)
);
```

**Purpose:** Defines which features are available for each plan tier (e.g., Growth plan gets feature X, Enterprise gets feature Y)

**Impact on STORY-002:**
- AC6 query will fail: `SELECT pf.* FROM plan_feature_grants pf`
- Feature flag plan restrictions cannot be implemented without this table

---

## Phase 5 Status

According to `docs/MASTER-IMPLEMENTATION-GUIDE.md`:

> **Phase 5: Feature Flags & Tenant Management (Future Enhancement)**
> 
> **نکته:** این Phase برای آینده است و بعد از تکمیل Phase 0-4 باید پیاده‌سازی شود.

**Translation:** "Note: This Phase is for the future and should be implemented after completing Phase 0-4."

**Current Status:** Phase 5 has NOT been implemented. These tables are planned but not created.

---

## Impact Assessment

### AC2: List Bots with Pagination

**Current Query (from story):**
```sql
SELECT 
    b.*,
    COUNT(DISTINCT u.id) as user_count,
    COALESCE(SUM(t.amount_toman), 0) as revenue,
    ts.plan_tier_id,                    -- ❌ FAILS: tenant_subscriptions doesn't exist
    tsp.display_name as plan_name       -- ❌ FAILS: tenant_subscription_plans doesn't exist
FROM bots b
LEFT JOIN users u ON u.bot_id = b.id
LEFT JOIN transactions t ON t.bot_id = b.id AND t.type = 'deposit' AND t.is_completed = TRUE
LEFT JOIN tenant_subscriptions ts ON ts.bot_id = b.id AND ts.status = 'active'  -- ❌ FAILS
LEFT JOIN tenant_subscription_plans tsp ON tsp.id = ts.plan_tier_id              -- ❌ FAILS
WHERE b.is_master = FALSE
GROUP BY b.id, ts.plan_tier_id, tsp.display_name
ORDER BY b.created_at DESC
LIMIT 5 OFFSET {page * 5};
```

**Impact:** Query will fail with error: `relation "tenant_subscriptions" does not exist`

**Workaround Options:**
1. Remove plan information from query (simplified version)
2. Create migration to add tables (recommended if plan system is needed)
3. Use alternative approach (store plan info in `bot_configurations`)

---

### AC6: Feature Flags Management

**Current Query (from story):**
```sql
-- Get plan features
SELECT pf.* FROM plan_feature_grants pf                    -- ❌ FAILS: plan_feature_grants doesn't exist
JOIN tenant_subscriptions ts ON ts.plan_tier_id = pf.plan_tier_id  -- ❌ FAILS: tenant_subscriptions doesn't exist
WHERE ts.bot_id = {bot_id} AND ts.status = 'active';
```

**Impact:** Query will fail with error: `relation "plan_feature_grants" does not exist`

**Workaround Options:**
1. Implement feature flags without plan restrictions (all features available to all bots)
2. Create migration to add tables (recommended if plan restrictions are needed)
3. Use alternative approach (store plan restrictions in `bot_configurations`)

---

## Recommendations

### Option 1: Create Migration (Recommended if Plan System is Needed)

**Action:** Create migration to add the three missing tables

**Migration File:** `migrations/002_create_tenant_subscription_tables.sql`

**Content:**
```sql
-- Migration: Create Tenant Subscription Tables
-- Increment: 1.2
-- Date: 2025-12-21
-- Description: Creates tables for tenant subscription plans and feature grants

-- 1. tenant_subscription_plans (Plan Tiers)
CREATE TABLE tenant_subscription_plans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    monthly_price_toman INTEGER NOT NULL,
    activation_fee_toman INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tenant_subscription_plans_active ON tenant_subscription_plans(is_active);

-- 2. plan_feature_grants (Feature Grants per Plan)
CREATE TABLE plan_feature_grants (
    plan_tier_id INTEGER NOT NULL REFERENCES tenant_subscription_plans(id) ON DELETE CASCADE,
    feature_key VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT FALSE NOT NULL,
    config_override JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (plan_tier_id, feature_key)
);

CREATE INDEX idx_plan_feature_grants_plan_tier ON plan_feature_grants(plan_tier_id);

-- 3. tenant_subscriptions (Bot Subscriptions to Plans)
CREATE TABLE tenant_subscriptions (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id) ON DELETE CASCADE,
    plan_tier_id INTEGER NOT NULL REFERENCES tenant_subscription_plans(id),
    status VARCHAR(20) DEFAULT 'active',
    start_date TIMESTAMP DEFAULT NOW(),
    end_date TIMESTAMP,
    auto_renewal BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(bot_id)
);

CREATE INDEX idx_tenant_subscriptions_bot_id ON tenant_subscriptions(bot_id);
CREATE INDEX idx_tenant_subscriptions_status ON tenant_subscriptions(status);
```

**Pros:**
- Enables full plan restriction functionality
- Matches story requirements
- Future-proof for Phase 5

**Cons:**
- Requires additional migration work
- Need to seed initial plan data
- More complex implementation

---

### Option 2: Simplify Queries (Quick Fix)

**Action:** Update story queries to remove plan-related joins

**AC2 Simplified Query:**
```sql
SELECT 
    b.*,
    COUNT(DISTINCT u.id) as user_count,
    COALESCE(SUM(t.amount_toman), 0) as revenue
    -- Removed: ts.plan_tier_id, tsp.display_name
FROM bots b
LEFT JOIN users u ON u.bot_id = b.id
LEFT JOIN transactions t ON t.bot_id = b.id AND t.type = 'deposit' AND t.is_completed = TRUE
-- Removed: LEFT JOIN tenant_subscriptions
-- Removed: LEFT JOIN tenant_subscription_plans
WHERE b.is_master = FALSE
GROUP BY b.id
ORDER BY b.created_at DESC
LIMIT 5 OFFSET {page * 5};
```

**AC6 Simplified Query:**
```sql
-- Get feature flags (without plan restrictions)
SELECT * FROM bot_feature_flags 
WHERE bot_id = {bot_id};

-- Removed: Plan feature grants query
-- Feature flags will be available to all bots (no plan restrictions)
```

**Pros:**
- Quick fix, no migration needed
- Can implement immediately
- Simpler implementation

**Cons:**
- Loses plan restriction functionality
- Doesn't match story requirements
- May need to add later anyway

---

### Option 3: Use Alternative Storage (Hybrid Approach)

**Action:** Store plan information in `bot_configurations` table

**Approach:**
- Store `plan_tier_id` in `bot_configurations` with key `TENANT_PLAN_TIER`
- Store plan restrictions in `bot_configurations` with keys like `PLAN_FEATURE_GRANT:{feature_key}`
- Update queries to read from `bot_configurations` instead of dedicated tables

**Pros:**
- No migration needed
- Flexible approach
- Can migrate to dedicated tables later

**Cons:**
- Less normalized
- Harder to query
- Doesn't match story requirements

---

## Recommended Action Plan

### Immediate (Before Starting STORY-002)

1. **Decision Required:** Does the plan restriction system need to be implemented now?
   - **If YES:** Create migration (Option 1)
   - **If NO:** Simplify queries (Option 2)

2. **Update Story:**
   - If choosing Option 1: Add migration task to story
   - If choosing Option 2: Update AC2 and AC6 queries in story

3. **Verify with Team:**
   - Confirm plan system requirements
   - Decide on timeline for Phase 5 implementation

### Short Term (During STORY-002 Development)

1. **If Option 1 (Migration):**
   - Create migration file
   - Seed initial plan data (Starter, Growth, Enterprise)
   - Test migration on dev database
   - Update story queries to use new tables

2. **If Option 2 (Simplify):**
   - Update story queries
   - Remove plan-related UI elements
   - Document that plan restrictions will be added later

---

## Verification Checklist

Before starting STORY-002 development:

- [ ] **Decision made:** Which option to use (1, 2, or 3)?
- [ ] **If Option 1:** Migration file created and tested
- [ ] **If Option 1:** Initial plan data seeded
- [ ] **If Option 2:** Story queries updated
- [ ] **If Option 2:** Plan-related UI elements removed from story
- [ ] **Story updated:** AC2 and AC6 reflect chosen approach
- [ ] **Team notified:** Decision documented and communicated

---

## Summary

**Critical Finding:** Three tables (`tenant_subscriptions`, `tenant_subscription_plans`, `plan_feature_grants`) referenced in STORY-002 do not exist in the database schema.

**Root Cause:** These tables are part of Phase 5 (Future Enhancement) which has not been implemented yet.

**Impact:** Queries in AC2 and AC6 will fail if executed as written.

**Decision:** ✅ **Option 1 Selected** - Migration created

**Migration Files Created:**
- ✅ `migrations/002_create_tenant_subscription_tables.sql` - Creates all three tables
- ✅ `migrations/002_seed_tenant_subscription_plans.sql` - Seeds initial plan data (optional)

**Action Required:** 
1. ✅ Migration file created
2. ⏳ Run migration on dev database
3. ⏳ Test migration
4. ⏳ Seed initial plan data (optional)
5. ⏳ Update STORY-002 to note migration is ready

---

**Verified By:** Scrum Master Agent  
**Date:** 2025-12-21  
**Status:** ✅ Migration files created - Ready for testing

